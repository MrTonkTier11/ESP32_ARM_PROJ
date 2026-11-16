"""status_bar.py - connection status dot + text at the bottom."""

import tkinter as tk
from theme import COLOR_RED, TEXT_MUTED

_BG = "#080b12"


class StatusBar(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=_BG, padx=18, pady=5)

        self.dot = tk.Canvas(self, width=10, height=10, bg=_BG, highlightthickness=0)
        self.dot.pack(side="left", padx=(0, 6))
        self.dot_circle = self.dot.create_oval(1, 1, 9, 9, fill=COLOR_RED, outline="")

        self.label = tk.Label(
            self, text="Not connected", font=("Segoe UI", 9, "bold"), bg=_BG, fg=COLOR_RED,
        )
        self.label.pack(side="left")

        tk.Label(
            self,
            text="📱 Smartphone Web GUI: Connect to 'RoboticArm-ESP32' Wi-Fi & open http://192.168.4.1",
            font=("Segoe UI", 8), bg=_BG, fg=TEXT_MUTED,
        ).pack(side="right")

    def set(self, text, color):
        self.label.config(text=text, fg=color)
        self.dot.itemconfig(self.dot_circle, fill=color)
