"""action_panel.py - Rest pose, Reset all, Emergency stop buttons."""

import tkinter as tk
from theme import CARD_BG, ACCENT_CYAN, TEXT_WHITE, COLOR_RED


class ActionPanel(tk.Frame):
    def __init__(self, parent, on_rest, on_reset, on_stop_base):
        super().__init__(parent, bg=CARD_BG)

        tk.Label(self, text="POSE", font=("Segoe UI", 10, "bold"),
                 bg=CARD_BG, fg=TEXT_WHITE).pack(anchor="w", pady=(4, 2))

        tk.Button(
            self, text="💤 Fold / Rest", font=("Segoe UI", 9, "bold"),
            bg="#192236", fg=TEXT_WHITE, activebackground=ACCENT_CYAN, activeforeground="#000",
            bd=1, relief="flat", pady=8, cursor="hand2", command=on_rest,
        ).pack(fill="x", pady=4)

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
