"""side_panel.py - right column: visualizer + pose buttons + activity log."""

import tkinter as tk
from theme import CARD_BG, CARD_BORDER, ACCENT_CYAN, TEXT_MUTED
from arm_visualizer import ArmVisualizer
from action_panel import ActionPanel
from log_panel import LogPanel


class SidePanel(tk.Frame):
    def __init__(self, parent, state, on_reset, on_stop_base):
        super().__init__(parent, bg=CARD_BG, highlightbackground=CARD_BORDER,
                         highlightthickness=1, padx=12, pady=12, width=380)
        self.pack_propagate(False)

        tk.Label(self, text="ARM KINEMATICS MIMIC", font=("Segoe UI", 11, "bold"),
                 bg=CARD_BG, fg=ACCENT_CYAN).pack(anchor="w")
        tk.Label(self, text="Live 2D Joint Angle & Claw Gripper Pose", font=("Segoe UI", 8),
                 bg=CARD_BG, fg=TEXT_MUTED).pack(anchor="w", pady=(0, 6))

        self.visualizer = ArmVisualizer(self, state)
        self.visualizer.pack(fill="x", pady=(0, 10))

        ActionPanel(self, on_reset, on_stop_base).pack(fill="x")

        self.log = LogPanel(self)
        self.log.pack(fill="both", expand=True)
