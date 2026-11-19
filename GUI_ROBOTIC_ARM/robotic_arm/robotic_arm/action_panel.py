"""action_panel.py - Reset all joints and Emergency stop buttons."""

import tkinter as tk
from theme import CARD_BG, ACCENT_CYAN, COLOR_RED


class ActionPanel(tk.Frame):
    def __init__(self, parent, on_reset, on_stop_base):
        super().__init__(parent, bg=CARD_BG)

        global_box = tk.Frame(self, bg=CARD_BG)
        global_box.pack(fill="x", pady=(8, 10))

        tk.Button(
            global_box, text="↺ RESET ALL JOINTS", font=("Segoe UI", 9, "bold"),
            bg="#1b253b", fg=ACCENT_CYAN, activebackground=ACCENT_CYAN, activeforeground="#000",
            bd=1, relief="flat", pady=8, cursor="hand2", command=on_reset,
        ).pack(fill="x", pady=2)

        tk.Button(
            global_box, text="⏹ EMERGENCY STOP BASE", font=("Segoe UI", 9, "bold"),
            bg="#5a1528", fg="#ff7597", activebackground=COLOR_RED, activeforeground="#fff",
            bd=1, relief="flat", pady=8, cursor="hand2", command=on_stop_base,
        ).pack(fill="x", pady=2)
