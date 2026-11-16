"""connection_bar.py - USB Serial / Wi-Fi selector and CONNECT button."""

import threading
import tkinter as tk
from tkinter import ttk, messagebox

from theme import (CARD_BG, CARD_BORDER, ACCENT_CYAN, TEXT_WHITE, TEXT_MUTED,
                   COLOR_RED, ESP32_AP_IP)
from connection_manager import HAS_SERIAL, list_usb_serial_ports

BTN_BLUE = "#00b0ff"


class ConnectionBar(tk.Frame):
    def __init__(self, parent, comm, ui_queue, status_callback, on_connected):
        super().__init__(parent, bg=CARD_BG, highlightbackground=CARD_BORDER,
                         highlightthickness=1, padx=14, pady=10)
        self.comm = comm
        self.ui_queue = ui_queue
        self.status_callback = status_callback   # (text, color)
        self.on_connected = on_connected         # called once connected

        self.conn_mode_var = tk.StringVar(value="SERIAL" if HAS_SERIAL else "WIFI")
        self.serial_port_var = tk.StringVar()
        self.baud_var = tk.StringVar(value="115200")
        self.wifi_ip_var = tk.StringVar(value=ESP32_AP_IP)
        self.wifi_port_var = tk.StringVar(value="5000")

        self._build()
        self._toggle_conn_mode()
        self.refresh_serial_ports()
        self.after(2000, self._auto_refresh_ports)

    # ---------- building ----------
    def _build(self):
        mode_box = tk.Frame(self, bg=CARD_BG)
        mode_box.pack(side="left", padx=(0, 15))

        tk.Label(mode_box, text="CONNECTION MODE:", font=("Segoe UI", 9, "bold"),
                 bg=CARD_BG, fg=TEXT_MUTED).pack(anchor="w")
        radio_row = tk.Frame(mode_box, bg=CARD_BG)
        radio_row.pack(anchor="w", pady=2)

        ttk.Radiobutton(radio_row, text="🔌 USB Serial", variable=self.conn_mode_var,
                        value="SERIAL", command=self._toggle_conn_mode).pack(side="left", padx=4)
        ttk.Radiobutton(radio_row, text="📡 Wi-Fi AP", variable=self.conn_mode_var,
                        value="WIFI", command=self._toggle_conn_mode).pack(side="left", padx=4)

        self.inputs_frame = tk.Frame(self, bg=CARD_BG)
        self.inputs_frame.pack(side="left", fill="x", expand=True)

        # Serial inputs
        self.serial_controls = tk.Frame(self.inputs_frame, bg=CARD_BG)
        tk.Label(self.serial_controls, text="Port:", bg=CARD_BG, fg=TEXT_WHITE).pack(side="left", padx=2)
        self.port_combobox = ttk.Combobox(self.serial_controls, textvariable=self.serial_port_var,
                                          width=12, state="readonly")
        self.port_combobox.pack(side="left", padx=4)
        ttk.Button(self.serial_controls, text="🔄 Refresh", width=9,
                   command=self.refresh_serial_ports).pack(side="left", padx=4)
        tk.Label(self.serial_controls, text="Baud:", bg=CARD_BG, fg=TEXT_WHITE).pack(side="left", padx=(8, 2))
        ttk.Combobox(self.serial_controls, textvariable=self.baud_var,
                     values=["115200", "57600", "9600"], width=8,
                     state="readonly").pack(side="left", padx=4)

        # Wi-Fi inputs (IP is fixed / read-only)
        self.wifi_controls = tk.Frame(self.inputs_frame, bg=CARD_BG)
        tk.Label(self.wifi_controls, text="ESP32 IP:", bg=CARD_BG, fg=TEXT_WHITE).pack(side="left", padx=2)
        tk.Entry(
            self.wifi_controls, textvariable=self.wifi_ip_var, width=13,
            state="readonly", readonlybackground="#0b0f18", fg=TEXT_MUTED,
            disabledforeground=TEXT_MUTED, insertbackground="white", bd=1,
        ).pack(side="left", padx=4)
        tk.Label(self.wifi_controls, text="Port:", bg=CARD_BG, fg=TEXT_WHITE).pack(side="left", padx=(8, 2))
        tk.Entry(self.wifi_controls, textvariable=self.wifi_port_var, width=6, bg="#0d111a",
                 fg=TEXT_WHITE, insertbackground="white", bd=1).pack(side="left", padx=4)

        btn_box = tk.Frame(self, bg=CARD_BG)
        btn_box.pack(side="right")
        self.btn_connect = tk.Button(
            btn_box, text="CONNECT", font=("Segoe UI", 9, "bold"),
            bg=BTN_BLUE, fg="#000000", activebackground=ACCENT_CYAN,
            padx=14, pady=4, bd=0, cursor="hand2", command=self.toggle_connection,
        )
        self.btn_connect.pack(side="left", padx=5)

    # ---------- mode / ports ----------
    def _toggle_conn_mode(self):
        if self.conn_mode_var.get() == "SERIAL":
            self.wifi_controls.pack_forget()
            self.serial_controls.pack(side="left", fill="x")
            self.refresh_serial_ports()
        else:
            self.serial_controls.pack_forget()
            self.wifi_controls.pack(side="left", fill="x")

    def refresh_serial_ports(self):
        if not HAS_SERIAL:
            self.port_combobox["values"] = ["No pyserial"]
            return
        port_names = list_usb_serial_ports()
        self.port_combobox["values"] = port_names
        current = self.serial_port_var.get()
        if port_names:
            if current not in port_names:
                self.serial_port_var.set(port_names[0])
        else:
            self.serial_port_var.set("")

    def _auto_refresh_ports(self):
        """Keeps the COM list current while not connected (plug/unplug)."""
        if self.conn_mode_var.get() == "SERIAL" and not self.comm.is_connected:
            self.refresh_serial_ports()
        self.after(2000, self._auto_refresh_ports)

    # ---------- connect / disconnect ----------
    def show_disconnected(self):
        self.btn_connect.config(text="CONNECT", bg=BTN_BLUE, state="normal")

    def toggle_connection(self):
        if self.comm.is_connected:
            self.comm.disconnect()
            self.show_disconnected()
            return

        mode = self.conn_mode_var.get()
        self.btn_connect.config(text="CONNECTING...", state="disabled")

        # Read Tk variables on the main thread before starting the worker
        port = self.serial_port_var.get().strip()
        baud = self.baud_var.get()
        ip = ESP32_AP_IP
        wport = self.wifi_port_var.get().strip()

        def connect_task():
            try:
                if mode == "SERIAL":
                    if not port:
                        raise ValueError("No USB serial device detected.\nPlug in the ESP32 and press Refresh.")
                    self.comm.connect_serial(port, int(baud))
                else:
                    self.comm.connect_wifi(ip, int(wport))

                self.ui_queue.put(lambda: self.btn_connect.config(text="DISCONNECT", bg=COLOR_RED, state="normal"))
                self.ui_queue.put(lambda: self.after(400, self.on_connected))
            except Exception as e:
                err = str(e)
                if mode == "SERIAL" or not self.comm.is_connected:
                    self.status_callback("Not connected", COLOR_RED)
                self.ui_queue.put(self.show_disconnected)
                self.ui_queue.put(lambda: messagebox.showerror("Not Connected", err))

        threading.Thread(target=connect_task, daemon=True).start()
