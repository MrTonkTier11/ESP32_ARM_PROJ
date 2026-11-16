"""header_bar.py - title strip at the top of the window."""

import tkinter as tk
from theme import BG_DARK, ACCENT_CYAN, TEXT_MUTED


class HeaderBar(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_DARK, pady=8)

        tk.Label(
            self,
            text="ESP32 ROBOTIC ARM CONTROL STATION",
            font=("Segoe UI", 16, "bold"),
            bg=BG_DARK,
            fg=ACCENT_CYAN,
        ).pack(side="left")

        tk.Label(
            self,
            text="4-DOF Multi-Link Control · USB Serial & Wi-Fi Hotspot Ready",
            font=("Segoe UI", 9),
            bg=BG_DARK,
            fg=TEXT_MUTED,
        ).pack(side="right", pady=4)
