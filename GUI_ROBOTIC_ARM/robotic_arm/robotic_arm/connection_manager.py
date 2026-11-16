"""connection_manager.py - USB Serial / Wi-Fi TCP link to the ESP32."""

import sys
import time
import socket
import threading

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

from theme import COLOR_GREEN, COLOR_RED, COLOR_ORANGE


def list_usb_serial_ports():
    """Returns device names of real USB serial adapters only.
    Bluetooth / virtual COM ports have no USB VID and are skipped."""
    if not HAS_SERIAL:
        return []
    names = []
    for p in serial.tools.list_ports.comports():
        hwid = (p.hwid or "").upper()
        if p.vid is None or "BTHENUM" in hwid:
            continue
        names.append(p.device)
    return names


class ConnectionManager:
    """Handles communication over either USB Serial or Wi-Fi TCP Socket."""

    MODE_SERIAL = "SERIAL"
    MODE_WIFI = "WIFI"

    def __init__(self, log_callback, status_callback, disconnect_callback=None):
        self.mode = self.MODE_SERIAL
        self.serial_port = None
        self.tcp_socket = None
        self.is_connected = False
        self.running = False
        self.log_callback = log_callback
        self.status_callback = status_callback
        self.disconnect_callback = disconnect_callback
        self.lock = threading.Lock()

    # USB SERIAL
    def connect_serial(self, port_name, baud_rate=115200):
        if not HAS_SERIAL:
            raise RuntimeError("pyserial is not installed (pip install pyserial).")

        self.disconnect()
        self.status_callback("Connecting to USB Serial...", COLOR_ORANGE)

        # The USB device must actually be present right now
        if port_name not in list_usb_serial_ports():
            msg = f"USB device on {port_name} not found"
            self.status_callback("Not connected (no USB device)", COLOR_RED)
            raise RuntimeError(msg)

        # Open it (DTR/RTS off so the ESP32 is not reset on connect)
        try:
            ser = serial.Serial()
            ser.port = port_name
            ser.baudrate = baud_rate
            ser.timeout = 0.1
            ser.write_timeout = 1.0
            ser.dtr = False
            ser.rts = False
            ser.open()
        except Exception as e:
            self.status_callback("Not connected (cannot open port)", COLOR_RED)
            raise e

        with self.lock:
            self.serial_port = ser
            self.mode = self.MODE_SERIAL
            self.is_connected = True
            self.running = True

        threading.Thread(target=self._serial_read_loop, args=(ser, port_name), daemon=True).start()
        self.status_callback(f"Connected (USB Serial {port_name})", COLOR_GREEN)
        self.log_callback(f"[INFO] Connected to {port_name} at {baud_rate} baud.")
        return True

    # WI-FI
    def connect_wifi(self, ip_address, port=5000):
        self.disconnect()
        self.status_callback(f"Connecting to {ip_address}:{port}...", COLOR_ORANGE)

        try:
            sock = socket.create_connection((ip_address, int(port)), timeout=3.0)
        except Exception as e:
            self.status_callback("Not connected (ESP32 Wi-Fi not reachable)", COLOR_RED)
            raise RuntimeError(
                f"Could not reach ESP32 at {ip_address}:{port}.\n"
                "Make sure your PC is on the ESP32's Wi-Fi and it is powered on."
            ) from e

        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._enable_keepalive(sock)
        except Exception:
            pass
        sock.settimeout(1.0)

        with self.lock:
            self.tcp_socket = sock
            self.mode = self.MODE_WIFI
            self.is_connected = True
            self.running = True

        threading.Thread(target=self._wifi_read_loop, args=(sock,), daemon=True).start()
        self.status_callback(f"Connected (Wi-Fi {ip_address}:{port})", COLOR_GREEN)
        self.log_callback(f"[INFO] Connected to ESP32 Wi-Fi at {ip_address}:{port}")
        return True

    @staticmethod
    def _enable_keepalive(sock):
        """Makes a dead ESP32 (powered off / out of range) get detected."""
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if sys.platform.startswith("win"):
            # (on, idle ms, interval ms)
            sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 3000, 1000))
        else:
            if hasattr(socket, "TCP_KEEPIDLE"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 3)
            if hasattr(socket, "TCP_KEEPINTVL"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 1)
            if hasattr(socket, "TCP_KEEPCNT"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)

    # SEND
    def send(self, command):
        if not self.is_connected:
            return False

        cmd_bytes = (command.strip() + "\n").encode("utf-8")
        try:
            if self.mode == self.MODE_SERIAL and self.serial_port:
                self.serial_port.write(cmd_bytes)
                self.serial_port.flush()
            elif self.mode == self.MODE_WIFI and self.tcp_socket:
                self.tcp_socket.sendall(cmd_bytes)
            else:
                return False
            self.log_callback(f"TX: {command.strip()}")
            return True
        except socket.timeout:
            self.log_callback("[WARN] Send timed out (ESP32 busy?).")
            return False
        except Exception as e:
            self._connection_lost(f"Send error: {e}")
            return False

    # DISCONNECT
    def disconnect(self, reason=None):
        with self.lock:
            was_connected = self.is_connected
            self.running = False
            self.is_connected = False
            ser, self.serial_port = self.serial_port, None
            sock, self.tcp_socket = self.tcp_socket, None

        if ser:
            try:
                ser.close()
            except Exception:
                pass
        if sock:
            try:
                sock.close()
            except Exception:
                pass

        self.status_callback(reason or "Not connected", COLOR_RED)
        if was_connected and self.disconnect_callback:
            self.disconnect_callback()

    def _connection_lost(self, reason):
        if not self.is_connected:
            return
        self.log_callback(f"[ERROR] {reason}")
        self.disconnect(reason="Not connected (" + reason + ")")

    # READ LOOPS
    def _serial_read_loop(self, ser, port_name):
        buf = ""
        last_check = time.time()
        while self.running and self.serial_port is ser:
            try:
                waiting = ser.in_waiting
                if waiting > 0:
                    data = ser.read(waiting).decode("utf-8", errors="ignore")
                    buf += data
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line = line.strip()
                        if line:
                            self.log_callback(f"RX: {line}")
                else:
                    time.sleep(0.02)
            except Exception:
                if self.running:
                    self._connection_lost("USB device removed")
                return

            # Once per second make sure the USB device is still plugged in
            now = time.time()
            if now - last_check > 1.0:
                last_check = now
                if port_name not in list_usb_serial_ports():
                    if self.running:
                        self._connection_lost("USB device unplugged")
                    return

    def _wifi_read_loop(self, sock):
        buf = ""
        while self.running and self.tcp_socket is sock:
            try:
                data = sock.recv(1024)
                if not data:
                    if self.running:
                        self._connection_lost("ESP32 closed the connection")
                    return
                buf += data.decode("utf-8", errors="ignore")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        self.log_callback(f"RX: {line}")
            except socket.timeout:
                continue
            except Exception:
                if self.running:
                    self._connection_lost("Wi-Fi connection lost")
                return

