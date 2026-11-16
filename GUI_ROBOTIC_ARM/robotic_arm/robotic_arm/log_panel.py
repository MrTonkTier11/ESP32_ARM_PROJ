"""log_panel.py - scrolling communication activity log."""

import tkinter as tk
from theme import CARD_BG, TEXT_MUTED


class LogPanel(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=CARD_BG)

        tk.Label(
            self, text="COMMUNICATION ACTIVITY LOG", font=("Segoe UI", 9, "bold"),
            bg=CARD_BG, fg=TEXT_MUTED,
        ).pack(anchor="w", pady=(6, 2))

        body = tk.Frame(self, bg=CARD_BG)
        body.pack(fill="both", expand=True)

        self.text = tk.Text(body, bg="#080b12", fg="#00e5ff", font=("Consolas", 8),
                            bd=1, relief="solid", height=6)
        self.text.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(body, command=self.text.yview)
        scrollbar.pack(side="right", fill="y")
        self.text.config(yscrollcommand=scrollbar.set)

    def append(self, line):
        self.text.insert("end", line + "\n")
        self.text.see("end")
