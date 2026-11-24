"""action_panel.py - Reset all joints global control."""

import tkinter as tk
from theme import CARD_BG, ACCENT_CYAN


class ActionPanel(tk.Frame):
    def __init__(self, parent, on_reset):
        super().__init__(parent, bg=CARD_BG)

        global_box = tk.Frame(self, bg=CARD_BG)
        global_box.pack(fill="x", pady=(4, 6))

        tk.Button(
            global_box, text="↺ RESET ALL JOINTS (REST POSE)", font=("Segoe UI", 9, "bold"),
            bg="#1b253b", fg=ACCENT_CYAN, activebackground=ACCENT_CYAN, activeforeground="#000000",
            bd=1, relief="flat", pady=6, cursor="hand2", command=on_reset,
        ).pack(fill="x")
