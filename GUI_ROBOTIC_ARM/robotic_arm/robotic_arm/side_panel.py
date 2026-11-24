"""side_panel.py - right column: enlarged visualizer (70% view) + pose buttons + activity log."""

import tkinter as tk
from theme import CARD_BG, CARD_BORDER, ACCENT_CYAN, TEXT_MUTED
from arm_visualizer import ArmVisualizer
from action_panel import ActionPanel
from log_panel import LogPanel


class SidePanel(tk.Frame):
    def __init__(self, parent, state, on_reset):
        super().__init__(parent, bg=CARD_BG, highlightbackground=CARD_BORDER,
                         highlightthickness=1, padx=12, pady=10)

        header_row = tk.Frame(self, bg=CARD_BG)
        header_row.pack(fill="x", pady=(0, 4))

        tk.Label(header_row, text="ARM KINEMATICS MIMIC (LIVE 2D VIEW)", font=("Segoe UI", 11, "bold"),
                 bg=CARD_BG, fg=ACCENT_CYAN).pack(side="left")
        tk.Label(header_row, text="Real-Time Servo Angle & Pincer Gripper Feedback", font=("Segoe UI", 8),
                 bg=CARD_BG, fg=TEXT_MUTED).pack(side="left", padx=(10, 0))

        # Enlarged visualizer fills available vertical and horizontal space
        self.visualizer = ArmVisualizer(self, state)
        self.visualizer.pack(fill="both", expand=True, pady=(2, 6))

        ActionPanel(self, on_reset).pack(fill="x", pady=(0, 4))

        self.log = LogPanel(self)
        self.log.pack(fill="x")
