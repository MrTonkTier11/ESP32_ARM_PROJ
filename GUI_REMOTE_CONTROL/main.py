"""
ESP32 ROBOTIC ARM CONTROLLER - DESKTOP GUI
Features:
- Dual Connection: USB Serial (COM Port with auto-detection) & Wi-Fi TCP Socket
- Real-time Joint Mimic Controls with Directional Arrows (Shoulder, Elbow, Claw, Base)
- Live 2D Kinematic Vector Visualizer showing arm pose and claw grip in real-time
- Quick Presets: Home, Pick, Drop, Sleep
- Fast step adjustment (-5°, -1°, +1°, +5°) & One-click Claw Open / Grip
- Continuous Base Jogging & Emergency Stop
- Activity Log & Ping / Latency monitor
"""

import sys
import time
import socket
import threading
import queue
import math
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

# =====================================================================
# THEME CONFIGURATION
# =====================================================================

BG_DARK = "#0d111a"
CARD_BG = "#161d2d"
CARD_BORDER = "#25324d"
ACCENT_CYAN = "#00d9ff"
ACCENT_BLUE = "#2979ff"
COLOR_GREEN = "#00e676"
COLOR_RED = "#ff3d71"
COLOR_ORANGE = "#ff9100"
COLOR_YELLOW = "#ffd54f"
TEXT_WHITE = "#ffffff"
TEXT_MUTED = "#8ea1c0"
SLIDER_TROUGH = "#0a0e16"

# =====================================================================
# UNIFIED CONNECTION MANAGER
# =====================================================================

class ConnectionManager:
    """Handles communication over either USB Serial or Wi-Fi TCP Socket."""
    
    MODE_SERIAL = "SERIAL"
    MODE_WIFI = "WIFI"

    def __init__(self, log_callback, status_callback):
        self.mode = self.MODE_SERIAL
        self.serial_port = None
        self.tcp_socket = None
        self.is_connected = False
        self.log_callback = log_callback
        self.status_callback = status_callback
        self.rx_thread = None
        self.running = False

    def connect_serial(self, port_name, baud_rate=115200):
        if not HAS_SERIAL:
            raise RuntimeError("pyserial is not installed.")
        self.disconnect()
        self.status_callback("Connecting to USB Serial...", COLOR_ORANGE)
        
        try:
            self.serial_port = serial.Serial(
                port=port_name,
                baudrate=baud_rate,
                timeout=0.1,
                write_timeout=1.0
            )
            time.sleep(0.1) # Brief settling time
            self.mode = self.MODE_SERIAL
            self.is_connected = True
            self.running = True
            
            # Start background reader
            self.rx_thread = threading.Thread(target=self._serial_read_loop, daemon=True)
            self.rx_thread.start()
            
            self.status_callback(f"Connected (USB Serial {port_name})", COLOR_GREEN)
            self.log_callback(f"[INFO] Connected to {port_name} at {baud_rate} baud.")
            return True
        except Exception as e:
            self.disconnect()
            self.status_callback(f"Connection Failed: {e}", COLOR_RED)
            raise e

    def connect_wifi(self, ip_address, port=5000):
        self.disconnect()
        self.status_callback(f"Connecting to {ip_address}:{port}...", COLOR_ORANGE)
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(4.0)
            sock.connect((ip_address, int(port)))
            sock.settimeout(0.2)
            
            self.tcp_socket = sock
            self.mode = self.MODE_WIFI
            self.is_connected = True
            self.running = True
            
            # Start background reader
            self.rx_thread = threading.Thread(target=self._wifi_read_loop, daemon=True)
            self.rx_thread.start()
            
            self.status_callback(f"Connected (Wi-Fi {ip_address}:{port})", COLOR_GREEN)
            self.log_callback(f"[INFO] Connected to ESP32 Wi-Fi at {ip_address}:{port}")
            return True
        except Exception as e:
            self.disconnect()
            self.status_callback(f"Wi-Fi Failed: {e}", COLOR_RED)
            raise e

    def send(self, command):
        """Sends a single text command ending with newline."""
        if not self.is_connected:
            return False

        cmd_bytes = (command.strip() + "\n").encode("utf-8")
        try:
            if self.mode == self.MODE_SERIAL and self.serial_port:
                self.serial_port.write(cmd_bytes)
                self.serial_port.flush()
            elif self.mode == self.MODE_WIFI and self.tcp_socket:
                self.tcp_socket.sendall(cmd_bytes)
            self.log_callback(f"TX: {command.strip()}")
            return True
        except Exception as e:
            self.log_callback(f"[ERROR] Send error: {e}")
            self.disconnect()
            self.status_callback(f"Disconnected (Error: {e})", COLOR_RED)
            return False

    def disconnect(self):
        self.running = False
        self.is_connected = False
        
        if self.serial_port:
            try:
                self.serial_port.close()
            except Exception:
                pass
            self.serial_port = None
            
        if self.tcp_socket:
            try:
                self.tcp_socket.close()
            except Exception:
                pass
            self.tcp_socket = None
            
        self.status_callback("Disconnected", COLOR_RED)

    def _serial_read_loop(self):
        buf = ""
        while self.running and self.serial_port and self.serial_port.is_open:
            try:
                waiting = self.serial_port.in_waiting
                if waiting > 0:
                    data = self.serial_port.read(waiting).decode("utf-8", errors="ignore")
                    buf += data
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line = line.strip()
                        if line:
                            self.log_callback(f"RX: {line}")
                else:
                    time.sleep(0.02)
            except Exception:
                break
        if self.running:
            self.disconnect()

    def _wifi_read_loop(self):
        buf = ""
        while self.running and self.tcp_socket:
            try:
                data = self.tcp_socket.recv(1024)
                if not data:
                    break
                buf += data.decode("utf-8", errors="ignore")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        self.log_callback(f"RX: {line}")
            except socket.timeout:
                continue
            except Exception:
                break
        if self.running:
            self.disconnect()


# =====================================================================
# MAIN APPLICATION GUI
# =====================================================================

class RoboticArmApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ESP32 Robotic Arm Control Station")
        self.root.geometry("1100x740")
        self.root.minsize(980, 680)
        self.root.configure(bg=BG_DARK)

        # Servo state variables (Angles 0 to 180)
        self.joint_vars = {
            1: tk.IntVar(value=90), # Shoulder
            2: tk.IntVar(value=90), # Elbow
            3: tk.IntVar(value=90), # Claw
            4: tk.IntVar(value=90), # Base (Estimated angle)
        }
        self.pending_timers = {}

        # Connection Mode Radio: "SERIAL" or "WIFI"
        self.conn_mode_var = tk.StringVar(value="SERIAL" if HAS_SERIAL else "WIFI")

        # Serial settings
        self.serial_port_var = tk.StringVar()
        self.baud_var = tk.StringVar(value="115200")

        # Wi-Fi settings
        self.wifi_ip_var = tk.StringVar(value="192.168.4.1")
        self.wifi_port_var = tk.StringVar(value="5000")

        # Initialize Connection Manager
        self.comm = ConnectionManager(
            log_callback=self.append_log,
            status_callback=self.update_status
        )

        self._configure_styles()
        self._build_header()
        self._build_connection_bar()
        self._build_main_content()
        self._build_status_bar()

        # Initial refresh of available serial ports
        self.refresh_serial_ports()

        # Handle window closing cleanly
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Initial canvas render
        self.root.after(100, self.update_arm_canvas)

    def _configure_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background=BG_DARK)
        style.configure("Card.TFrame", background=CARD_BG, relief="solid", borderwidth=1)
        style.configure("TLabel", background=BG_DARK, foreground=TEXT_WHITE, font=("Segoe UI", 10))
        style.configure("Card.TLabel", background=CARD_BG, foreground=TEXT_WHITE, font=("Segoe UI", 10))

        style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=5, background=CARD_BORDER, foreground=TEXT_WHITE)
        style.map("TButton", background=[("active", ACCENT_CYAN)], foreground=[("active", "#000000")])

        style.configure("Action.TButton", font=("Segoe UI", 9, "bold"), padding=6, background="#1c263c", foreground=ACCENT_CYAN)
        style.map("Action.TButton", background=[("active", ACCENT_CYAN)], foreground=[("active", "#000000")])

        style.configure("Stop.TButton", font=("Segoe UI", 9, "bold"), padding=6, background="#4a1525", foreground="#ff6b8b")
        style.map("Stop.TButton", background=[("active", COLOR_RED)], foreground=[("active", "#ffffff")])

        style.configure("TRadiobutton", background=CARD_BG, foreground=TEXT_WHITE, font=("Segoe UI", 9, "bold"))
        style.map("TRadiobutton", background=[("active", CARD_BG)])

    def _build_header(self):
        header_frame = tk.Frame(self.root, bg=BG_DARK, pady=8)
        header_frame.pack(fill="x", padx=18)

        title_lbl = tk.Label(
            header_frame,
            text="ESP32 ROBOTIC ARM CONTROL STATION",
            font=("Segoe UI", 16, "bold"),
            bg=BG_DARK,
            fg=ACCENT_CYAN
        )
        title_lbl.pack(side="left")

        subtitle_lbl = tk.Label(
            header_frame,
            text="4-DOF Multi-Link Control · USB Serial & Wi-Fi Hotspot Ready",
            font=("Segoe UI", 9),
            bg=BG_DARK,
            fg=TEXT_MUTED
        )
        subtitle_lbl.pack(side="right", pady=4)

    def _build_connection_bar(self):
        conn_frame = tk.Frame(self.root, bg=CARD_BG, highlightbackground=CARD_BORDER, highlightthickness=1, padx=14, pady=10)
        conn_frame.pack(fill="x", padx=18, pady=(0, 10))

        # Mode Selection
        mode_box = tk.Frame(conn_frame, bg=CARD_BG)
        mode_box.pack(side="left", padx=(0, 15))

        tk.Label(mode_box, text="CONNECTION MODE:", font=("Segoe UI", 9, "bold"), bg=CARD_BG, fg=TEXT_MUTED).pack(anchor="w")
        radio_row = tk.Frame(mode_box, bg=CARD_BG)
        radio_row.pack(anchor="w", pady=2)

        ttk.Radiobutton(radio_row, text="🔌 USB Serial", variable=self.conn_mode_var, value="SERIAL", command=self._toggle_conn_mode).pack(side="left", padx=4)
        ttk.Radiobutton(radio_row, text="📡 Wi-Fi AP", variable=self.conn_mode_var, value="WIFI", command=self._toggle_conn_mode).pack(side="left", padx=4)

        # Dynamic Controls Container
        self.conn_inputs_frame = tk.Frame(conn_frame, bg=CARD_BG)
        self.conn_inputs_frame.pack(side="left", fill="x", expand=True)

        # Serial Inputs Frame
        self.serial_controls = tk.Frame(self.conn_inputs_frame, bg=CARD_BG)
        tk.Label(self.serial_controls, text="Port:", bg=CARD_BG, fg=TEXT_WHITE).pack(side="left", padx=2)
        self.port_combobox = ttk.Combobox(self.serial_controls, textvariable=self.serial_port_var, width=12, state="readonly")
        self.port_combobox.pack(side="left", padx=4)

        refresh_btn = ttk.Button(self.serial_controls, text="🔄 Refresh", width=9, command=self.refresh_serial_ports)
        refresh_btn.pack(side="left", padx=4)

        tk.Label(self.serial_controls, text="Baud:", bg=CARD_BG, fg=TEXT_WHITE).pack(side="left", padx=(8, 2))
        baud_box = ttk.Combobox(self.serial_controls, textvariable=self.baud_var, values=["115200", "57600", "9600"], width=8, state="readonly")
        baud_box.pack(side="left", padx=4)

        # Wi-Fi Inputs Frame
        self.wifi_controls = tk.Frame(self.conn_inputs_frame, bg=CARD_BG)
        tk.Label(self.wifi_controls, text="ESP32 IP:", bg=CARD_BG, fg=TEXT_WHITE).pack(side="left", padx=2)
        ip_entry = tk.Entry(self.wifi_controls, textvariable=self.wifi_ip_var, width=13, bg="#0d111a", fg=TEXT_WHITE, insertbackground="white", bd=1)
        ip_entry.pack(side="left", padx=4)

        tk.Label(self.wifi_controls, text="Port:", bg=CARD_BG, fg=TEXT_WHITE).pack(side="left", padx=(8, 2))
        port_entry = tk.Entry(self.wifi_controls, textvariable=self.wifi_port_var, width=6, bg="#0d111a", fg=TEXT_WHITE, insertbackground="white", bd=1)
        port_entry.pack(side="left", padx=4)

        # Connect / Disconnect Buttons
        btn_box = tk.Frame(conn_frame, bg=CARD_BG)
        btn_box.pack(side="right")

        self.btn_connect = tk.Button(
            btn_box,
            text="CONNECT",
            font=("Segoe UI", 9, "bold"),
            bg="#00b0ff",
            fg="#000000",
            activebackground=ACCENT_CYAN,
            padx=14,
            pady=4,
            bd=0,
            cursor="hand2",
            command=self.toggle_connection
        )
        self.btn_connect.pack(side="left", padx=5)

        self._toggle_conn_mode()

    def _toggle_conn_mode(self):
        mode = self.conn_mode_var.get()
        if mode == "SERIAL":
            self.wifi_controls.pack_forget()
            self.serial_controls.pack(side="left", fill="x")
        else:
            self.serial_controls.pack_forget()
            self.wifi_controls.pack(side="left", fill="x")

    def refresh_serial_ports(self):
        if not HAS_SERIAL:
            self.port_combobox["values"] = ["No pyserial"]
            return
        ports = serial.tools.list_ports.comports()
        port_names = [p.device for p in ports]
        self.port_combobox["values"] = port_names
        if port_names:
            if "COM6" in port_names:
                self.serial_port_var.set("COM6")
            else:
                self.serial_port_var.set(port_names[0])
        else:
            self.serial_port_var.set("")

    def toggle_connection(self):
        if self.comm.is_connected:
            self.comm.disconnect()
            self.btn_connect.config(text="CONNECT", bg="#00b0ff")
        else:
            mode = self.conn_mode_var.get()
            self.btn_connect.config(text="CONNECTING...", state="disabled")

            def connect_task():
                try:
                    if mode == "SERIAL":
                        port = self.serial_port_var.get().strip()
                        if not port:
                            raise ValueError("No COM port selected.")
                        baud = int(self.baud_var.get())
                        self.comm.connect_serial(port, baud)
                    else:
                        ip = self.wifi_ip_var.get().strip()
                        port = int(self.wifi_port_var.get().strip())
                        self.comm.connect_wifi(ip, port)

                    # Query initial status or sync state
                    self.root.after(200, self.sync_initial_positions)
                    self.root.after(0, lambda: self.btn_connect.config(text="DISCONNECT", bg=COLOR_RED, state="normal"))
                except Exception as e:
                    self.root.after(0, lambda: self.btn_connect.config(text="CONNECT", bg="#00b0ff", state="normal"))
                    self.root.after(0, lambda: messagebox.showerror("Connection Error", f"Failed to connect:\n{e}"))

            threading.Thread(target=connect_task, daemon=True).start()

    def sync_initial_positions(self):
        """Sends current GUI slider values to ESP32 upon connection."""
        self.comm.send(f"S1,{self.joint_vars[1].get()}")
        self.comm.send(f"S2,{self.joint_vars[2].get()}")
        self.comm.send(f"S3,{self.joint_vars[3].get()}")
        self.comm.send(f"S4,{self.joint_vars[4].get()}")

    def _build_main_content(self):
        main_split = tk.Frame(self.root, bg=BG_DARK)
        main_split.pack(fill="both", expand=True, padx=18, pady=(0, 6))

        # ----------------- LEFT: 4 Joint Control Cards -----------------
        left_col = tk.Frame(main_split, bg=BG_DARK)
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Joint 4: Base
        self.create_joint_card(
            parent=left_col,
            joint_id=4,
            title="BASE ROTATION (MG90S Continuous)",
            subtitle="Timed Position Tracking & Continuous Yaw Rotation",
            left_arrow_text="↺ ◀ CCW",
            right_arrow_text="CW ▶ ↻",
            left_tooltip="Rotate Counter-Clockwise",
            right_tooltip="Rotate Clockwise",
            has_stop_base=True
        )

        # Joint 1: Shoulder
        self.create_joint_card(
            parent=left_col,
            joint_id=1,
            title="SHOULDER JOINT (SG90 180°)",
            subtitle="Main Arm Pitch Elevation",
            left_arrow_text="▼ LOWER",
            right_arrow_text="RAISE ▲",
            left_tooltip="Lower Main Arm",
            right_tooltip="Raise Main Arm"
        )

        # Joint 2: Elbow
        self.create_joint_card(
            parent=left_col,
            joint_id=2,
            title="ELBOW JOINT (SG90 180°)",
            subtitle="Forearm Extension & Pitch Angle",
            left_arrow_text="↶ RETRACT",
            right_arrow_text="EXTEND ↷",
            left_tooltip="Retract Forearm",
            right_tooltip="Extend Forearm"
        )

        # Joint 3: Claw
        self.create_joint_card(
            parent=left_col,
            joint_id=3,
            title="CLAW / GRIPPER (SG90 180°)",
            subtitle="Pincer End-Effector Mechanism",
            left_arrow_text="◄ OPEN 🔓",
            right_arrow_text="GRIP 🔒 ►",
            left_tooltip="Open Pincers",
            right_tooltip="Grip / Close Pincers",
            has_claw_actions=True
        )

        # ----------------- RIGHT: Visual Arm Canvas & Presets -----------------
        right_col = tk.Frame(main_split, bg=CARD_BG, highlightbackground=CARD_BORDER, highlightthickness=1, padx=12, pady=12, width=380)
        right_col.pack(side="right", fill="both", padx=(0, 0))
        right_col.pack_propagate(False)

        # Visual Arm Header
        tk.Label(right_col, text="ARM KINEMATICS MIMIC", font=("Segoe UI", 11, "bold"), bg=CARD_BG, fg=ACCENT_CYAN).pack(anchor="w")
        tk.Label(right_col, text="Live 2D Joint Angle & Claw Gripper Pose", font=("Segoe UI", 8), bg=CARD_BG, fg=TEXT_MUTED).pack(anchor="w", pady=(0, 6))

        # Canvas
        self.arm_canvas = tk.Canvas(right_col, bg="#090d15", highlightthickness=1, highlightbackground=CARD_BORDER, height=210)
        self.arm_canvas.pack(fill="x", pady=(0, 10))

        # Presets Section
        tk.Label(right_col, text="QUICK POSE PRESETS", font=("Segoe UI", 10, "bold"), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor="w", pady=(4, 2))
        preset_grid = tk.Frame(right_col, bg=CARD_BG)
        preset_grid.pack(fill="x", pady=4)

        presets = [
            ("🏠 Home (90°)", 90, 90, 90, 90),
            ("📦 Pick Pose", 130, 45, 30, 90),
            ("📍 Drop Pose", 70, 110, 150, 140),
            ("💤 Fold / Rest", 45, 135, 90, 90)
        ]

        for i, (name, s1, s2, s3, s4) in enumerate(presets):
            btn = tk.Button(
                preset_grid,
                text=name,
                font=("Segoe UI", 8, "bold"),
                bg="#192236",
                fg=TEXT_WHITE,
                activebackground=ACCENT_CYAN,
                activeforeground="#000",
                bd=1,
                relief="flat",
                pady=6,
                cursor="hand2",
                command=lambda p1=s1, p2=s2, p3=s3, p4=s4: self.apply_preset(p1, p2, p3, p4)
            )
            btn.grid(row=i // 2, column=i % 2, sticky="nsew", padx=3, pady=3)
        preset_grid.columnconfigure(0, weight=1)
        preset_grid.columnconfigure(1, weight=1)

        # Global Control Buttons
        global_box = tk.Frame(right_col, bg=CARD_BG)
        global_box.pack(fill="x", pady=(8, 10))

        btn_reset_all = tk.Button(
            global_box,
            text="↺ RESET ALL JOINTS",
            font=("Segoe UI", 9, "bold"),
            bg="#1b253b",
            fg=ACCENT_CYAN,
            activebackground=ACCENT_CYAN,
            activeforeground="#000",
            bd=1,
            relief="flat",
            pady=8,
            cursor="hand2",
            command=self.reset_all_controls
        )
        btn_reset_all.pack(fill="x", pady=2)

        btn_stop_base = tk.Button(
            global_box,
            text="⏹ EMERGENCY STOP BASE",
            font=("Segoe UI", 9, "bold"),
            bg="#5a1528",
            fg="#ff7597",
            activebackground=COLOR_RED,
            activeforeground="#fff",
            bd=1,
            relief="flat",
            pady=8,
            cursor="hand2",
            command=self.stop_base
        )
        btn_stop_base.pack(fill="x", pady=2)

        # Activity Log Box
        tk.Label(right_col, text="COMMUNICATION ACTIVITY LOG", font=("Segoe UI", 9, "bold"), bg=CARD_BG, fg=TEXT_MUTED).pack(anchor="w", pady=(6, 2))
        log_frame = tk.Frame(right_col, bg=CARD_BG)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_frame, bg="#080b12", fg="#00e5ff", font=("Consolas", 8), bd=1, relief="solid", height=6)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=scrollbar.set)

    def create_joint_card(self, parent, joint_id, title, subtitle, left_arrow_text, right_arrow_text,
                          left_tooltip="", right_tooltip="", has_stop_base=False, has_claw_actions=False):
        card = tk.Frame(parent, bg=CARD_BG, highlightbackground=CARD_BORDER, highlightthickness=1, padx=12, pady=8)
        card.pack(fill="x", pady=3)

        # Header Row: Title & Angle Badge
        hdr = tk.Frame(card, bg=CARD_BG)
        hdr.pack(fill="x")

        title_lbl = tk.Label(hdr, text=title, font=("Segoe UI", 10, "bold"), bg=CARD_BG, fg=ACCENT_CYAN)
        title_lbl.pack(side="left")

        val_badge = tk.Label(
            hdr,
            text=f"{self.joint_vars[joint_id].get()}°",
            font=("Segoe UI", 12, "bold"),
            bg="#0d1322",
            fg=TEXT_WHITE,
            padx=10,
            pady=1,
            bd=1,
            relief="solid"
        )
        val_badge.pack(side="right")
        setattr(self, f"val_label_{joint_id}", val_badge)

        sub_lbl = tk.Label(card, text=subtitle, font=("Segoe UI", 8), bg=CARD_BG, fg=TEXT_MUTED)
        sub_lbl.pack(anchor="w", pady=(0, 4))

        # Main Control Row: [ Left Arrow ] --- [ Slider ] --- [ Right Arrow ]
        ctrl_row = tk.Frame(card, bg=CARD_BG)
        ctrl_row.pack(fill="x", pady=2)

        btn_left = tk.Button(
            ctrl_row,
            text=left_arrow_text,
            font=("Segoe UI", 9, "bold"),
            bg="#182338",
            fg=TEXT_WHITE,
            activebackground=ACCENT_CYAN,
            activeforeground="#000000",
            bd=1,
            relief="flat",
            width=10,
            pady=4,
            cursor="hand2",
            command=lambda: self.step_joint(joint_id, -5)
        )
        btn_left.pack(side="left", padx=(0, 6))

        slider = tk.Scale(
            ctrl_row,
            from_=0,
            to=180,
            orient="horizontal",
            variable=self.joint_vars[joint_id],
            showvalue=0,
            command=lambda val, j_id=joint_id: self.on_slider_moved(j_id, val),
            bg=CARD_BG,
            troughcolor=SLIDER_TROUGH,
            highlightthickness=0,
            activebackground=ACCENT_CYAN,
            bd=0
        )
        slider.pack(side="left", fill="x", expand=True, padx=4)

        btn_right = tk.Button(
            ctrl_row,
            text=right_arrow_text,
            font=("Segoe UI", 9, "bold"),
            bg="#182338",
            fg=TEXT_WHITE,
            activebackground=ACCENT_CYAN,
            activeforeground="#000000",
            bd=1,
            relief="flat",
            width=10,
            pady=4,
            cursor="hand2",
            command=lambda: self.step_joint(joint_id, 5)
        )
        btn_right.pack(side="right", padx=(6, 0))

        # Action / Fine-Tune Sub-Row
        action_row = tk.Frame(card, bg=CARD_BG)
        action_row.pack(fill="x", pady=(3, 0))

        # Fine-tune steps
        for step in [-5, -1, 1, 5]:
            step_text = f"{step:+d}°"
            b = tk.Button(
                action_row,
                text=step_text,
                font=("Segoe UI", 7, "bold"),
                bg="#121826",
                fg=TEXT_MUTED,
                activebackground=CARD_BORDER,
                activeforeground=TEXT_WHITE,
                bd=0,
                padx=8,
                pady=2,
                cursor="hand2",
                command=lambda s=step, j_id=joint_id: self.step_joint(j_id, s)
            )
            b.pack(side="left", padx=2)

        if has_stop_base:
            btn_stop = tk.Button(
                action_row,
                text="⏹ STOP BASE",
                font=("Segoe UI", 8, "bold"),
                bg="#42131f",
                fg="#ff8099",
                activebackground=COLOR_RED,
                activeforeground="#fff",
                bd=0,
                padx=10,
                pady=2,
                cursor="hand2",
                command=self.stop_base
            )
            btn_stop.pack(side="right", padx=2)

        if has_claw_actions:
            btn_open = tk.Button(
                action_row,
                text="🔓 FULL OPEN (30°)",
                font=("Segoe UI", 8, "bold"),
                bg="#11334c",
                fg="#64b5f6",
                activebackground="#0091ea",
                activeforeground="#fff",
                bd=0,
                padx=8,
                pady=2,
                cursor="hand2",
                command=lambda: self.set_joint_val(3, 30)
            )
            btn_open.pack(side="right", padx=2)

            btn_grip = tk.Button(
                action_row,
                text="🔒 FULL GRIP (150°)",
                font=("Segoe UI", 8, "bold"),
                bg="#3d2a0e",
                fg="#ffca28",
                activebackground="#ff8f00",
                activeforeground="#fff",
                bd=0,
                padx=8,
                pady=2,
                cursor="hand2",
                command=lambda: self.set_joint_val(3, 150)
            )
            btn_grip.pack(side="right", padx=2)

    def _build_status_bar(self):
        status_bar = tk.Frame(self.root, bg="#080b12", padx=18, pady=5)
        status_bar.pack(fill="x", side="bottom")

        self.status_dot = tk.Canvas(status_bar, width=10, height=10, bg="#080b12", highlightthickness=0)
        self.status_dot.pack(side="left", padx=(0, 6))
        self.dot_circle = self.status_dot.create_oval(1, 1, 9, 9, fill=COLOR_RED, outline="")

        self.status_label = tk.Label(
            status_bar,
            text="Disconnected",
            font=("Segoe UI", 9, "bold"),
            bg="#080b12",
            fg=COLOR_RED
        )
        self.status_label.pack(side="left")

        phone_tip = tk.Label(
            status_bar,
            text="📱 Smartphone Web GUI: Connect to 'RoboticArm-ESP32' Wi-Fi & open http://192.168.4.1",
            font=("Segoe UI", 8),
            bg="#080b12",
            fg=TEXT_MUTED
        )
        phone_tip.pack(side="right")

    def update_status(self, text, color):
        self.root.after(0, lambda: self._update_status_ui(text, color))

    def _update_status_ui(self, text, color):
        self.status_label.config(text=text, fg=color)
        self.status_dot.itemconfig(self.dot_circle, fill=color)

    def append_log(self, text):
        self.root.after(0, lambda: self._append_log_ui(text))

    def _append_log_ui(self, text):
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")

    def on_slider_moved(self, joint_id, value):
        val = int(float(value))
        val_badge = getattr(self, f"val_label_{joint_id}", None)
        if val_badge:
            val_badge.config(text=f"{val}°")

        self.update_arm_canvas()

        # Debounce/throttle serial/socket transmissions (35ms delay)
        if joint_id in self.pending_timers:
            self.root.after_cancel(self.pending_timers[joint_id])

        self.pending_timers[joint_id] = self.root.after(
            35,
            lambda j=joint_id, v=val: self.send_joint_command(j, v)
        )

    def step_joint(self, joint_id, delta):
        cur = self.joint_vars[joint_id].get()
        new_val = max(0, min(180, cur + delta))
        self.set_joint_val(joint_id, new_val)

    def set_joint_val(self, joint_id, value):
        value = max(0, min(180, int(value)))
        self.joint_vars[joint_id].set(value)
        val_badge = getattr(self, f"val_label_{joint_id}", None)
        if val_badge:
            val_badge.config(text=f"{value}°")
        self.update_arm_canvas()
        self.send_joint_command(joint_id, value)

    def send_joint_command(self, joint_id, value):
        self.pending_timers.pop(joint_id, None)
        self.comm.send(f"S{joint_id},{value}")

    def stop_base(self):
        self.comm.send("STOP4")
        self.append_log("[ACTION] STOP BASE triggered.")

    def reset_all_controls(self):
        self.apply_preset(90, 90, 90, 90)
        self.comm.send("RESET")

    def apply_preset(self, s1, s2, s3, s4):
        self.set_joint_val(1, s1)
        self.set_joint_val(2, s2)
        self.set_joint_val(3, s3)
        self.set_joint_val(4, s4)

    def update_arm_canvas(self):
        """Draws 2D vector graphic of the robotic arm and claw based on current angles."""
        c = self.arm_canvas
        c.delete("all")

        w = c.winfo_width()
        h = c.winfo_height()
        if w < 10: w = 350
        if h < 10: h = 210

        # Base origin
        bx = w // 2
        by = h - 35

        # Angles
        shoulder_deg = (self.joint_vars[1].get() - 90) * 0.8
        elbow_deg = (self.joint_vars[2].get() - 90) * 0.8
        claw_spread = max(3, min(24, (180 - self.joint_vars[3].get()) * 0.13))
        base_angle = self.joint_vars[4].get()

        # Base platform
        c.create_rectangle(bx - 55, by, bx + 55, by + 16, fill="#1c2538", outline="#2b3b59", width=2)
        c.create_oval(bx - 18, by - 6, bx + 18, by + 12, fill="#0f1624", outline=ACCENT_CYAN, width=2)
        c.create_text(bx, by + 3, text=f"Base: {base_angle}°", fill=ACCENT_CYAN, font=("Segoe UI", 7, "bold"))

        # Link lengths
        L1 = 60 # Shoulder to Elbow
        L2 = 50 # Elbow to Wrist

        # Kinematic calculations
        rad_s = math.radians(-90 + shoulder_deg)
        ex = bx + L1 * math.cos(rad_s)
        ey = by + L1 * math.sin(rad_s)

        rad_e = rad_s + math.radians(elbow_deg)
        wx = ex + L2 * math.cos(rad_e)
        wy = ey + L2 * math.sin(rad_e)

        # Draw Shoulder Beam
        c.create_line(bx, by, ex, ey, fill="#00b0ff", width=7, capstyle="round")
        c.create_oval(bx - 6, by - 6, bx + 6, by + 6, fill="#ffffff", outline=ACCENT_CYAN, width=2)

        # Draw Elbow Beam
        c.create_line(ex, ey, wx, wy, fill="#2979ff", width=5, capstyle="round")
        c.create_oval(ex - 5, ey - 5, ex + 5, ey + 5, fill="#ffffff", outline="#00b0ff", width=2)

        # Wrist Joint
        c.create_oval(wx - 4, wy - 4, wx + 4, wy + 4, fill=COLOR_YELLOW, outline="#ffab00", width=1)

        # Claw Jaws (left and right pincer lines)
        claw_len = 16
        rad_perp = rad_e + math.pi / 2

        # Pincer points
        px_l1 = wx + math.cos(rad_perp) * (claw_spread / 2)
        py_l1 = wy + math.sin(rad_perp) * (claw_spread / 2)
        px_l2 = px_l1 + math.cos(rad_e) * claw_len
        py_l2 = py_l1 + math.sin(rad_e) * claw_len

        px_r1 = wx - math.cos(rad_perp) * (claw_spread / 2)
        py_r1 = wy - math.sin(rad_perp) * (claw_spread / 2)
        px_r2 = px_r1 + math.cos(rad_e) * claw_len
        py_r2 = py_r1 + math.sin(rad_e) * claw_len

        # Claw drawing
        c.create_line(wx, wy, px_l1, py_l1, fill=COLOR_YELLOW, width=3)
        c.create_line(px_l1, py_l1, px_l2, py_l2, fill=COLOR_YELLOW, width=3, capstyle="round")

        c.create_line(wx, wy, px_r1, py_r1, fill=COLOR_YELLOW, width=3)
        c.create_line(px_r1, py_r1, px_r2, py_r2, fill=COLOR_YELLOW, width=3, capstyle="round")

        # Labels on diagram
        c.create_text(ex + 12, ey - 6, text=f"Elbow: {self.joint_vars[2].get()}°", fill=TEXT_MUTED, font=("Segoe UI", 7))
        c.create_text(wx + 14, wy + 8, text=f"Claw: {self.joint_vars[3].get()}°", fill=COLOR_YELLOW, font=("Segoe UI", 7))

    def on_closing(self):
        try:
            self.comm.disconnect()
        except Exception:
            pass
        self.root.destroy()


# =====================================================================
# ENTRY POINT
# =====================================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = RoboticArmApp(root)
    root.mainloop()
