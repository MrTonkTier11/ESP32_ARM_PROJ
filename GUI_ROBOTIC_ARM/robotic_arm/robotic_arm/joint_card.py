"""joint_card.py - one reusable card (title, slider, step buttons) per joint."""

import tkinter as tk
from theme import (CARD_BG, CARD_BORDER, ACCENT_CYAN, TEXT_WHITE, TEXT_MUTED,
                   SLIDER_TROUGH, COLOR_RED)


class JointCard(tk.Frame):
    def __init__(self, parent, joint_id, variable, title, subtitle,
                 left_text, right_text,
                 on_slider, on_step, on_set,
                 on_stop_base=None, min_val =0, max_val=180,
                 open_value=30, grip_value=150,
                 show_angle=True, has_stop_base=False, has_claw_actions=False):
        super().__init__(parent, bg=CARD_BG, highlightbackground=CARD_BORDER,
                         highlightthickness=1, padx=12, pady=8)
        self.joint_id = joint_id
        self.var = variable
        self.on_slider = on_slider      # (joint_id, value)
        self.on_step = on_step          # (joint_id, delta)
        self.on_set = on_set            # (joint_id, value)
        self.on_stop_base = on_stop_base
        self.min_val = min_val
        self.open_value =open_value
        self.grip_value = grip_value
        self.max_val = max_val
        self.badge = None

        self._build_header(title, show_angle)
        tk.Label(self, text=subtitle, font=("Segoe UI", 8), bg=CARD_BG,
                 fg=TEXT_MUTED).pack(anchor="w", pady=(0, 4))
        self._build_slider_row(left_text, right_text)
        self._build_action_row(has_stop_base, has_claw_actions)

    # ---------- public ----------
    def update_badge(self, value):
        if self.badge:
            self.badge.config(text=f"{int(value)}°")

    # ---------- building ----------
    def _build_header(self, title, show_angle):
        hdr = tk.Frame(self, bg=CARD_BG)
        hdr.pack(fill="x")

        tk.Label(hdr, text=title, font=("Segoe UI", 10, "bold"),
                 bg=CARD_BG, fg=ACCENT_CYAN).pack(side="left")

        if show_angle:
            self.badge = tk.Label(
                hdr, text=f"{self.var.get()}°", font=("Segoe UI", 12, "bold"),
                bg="#0d1322", fg=TEXT_WHITE, padx=10, pady=1, bd=1, relief="solid",
            )
            self.badge.pack(side="right")

    def _build_slider_row(self, left_text, right_text):
        row = tk.Frame(self, bg=CARD_BG)
        row.pack(fill="x", pady=2)

        tk.Button(
            row, text=left_text, font=("Segoe UI", 9, "bold"),
            bg="#182338", fg=TEXT_WHITE, activebackground=ACCENT_CYAN, activeforeground="#000000",
            bd=1, relief="flat", width=10, pady=4, cursor="hand2",
            command=lambda: self.on_step(self.joint_id, -5),
        ).pack(side="left", padx=(0, 6))

        tk.Scale(
            row, from_=self.min_val, to=self.max_val, orient="horizontal",
            variable=self.var, showvalue=0,
            command=lambda val: self.on_slider(self.joint_id, val),
            bg=CARD_BG, troughcolor=SLIDER_TROUGH, highlightthickness=0,
            activebackground=ACCENT_CYAN, bd=0,
        ).pack(side="left", fill="x", expand=True, padx=4)

        tk.Button(
            row, text=right_text, font=("Segoe UI", 9, "bold"),
            bg="#182338", fg=TEXT_WHITE, activebackground=ACCENT_CYAN, activeforeground="#000000",
            bd=1, relief="flat", width=10, pady=4, cursor="hand2",
            command=lambda: self.on_step(self.joint_id, 5),
        ).pack(side="right", padx=(6, 0))

    def _build_action_row(self, has_stop_base, has_claw_actions):
        row = tk.Frame(self, bg=CARD_BG)
        row.pack(fill="x", pady=(3, 0))

        for step in (-5, -1, 1, 5):
            tk.Button(
                row, text=f"{step:+d}°", font=("Segoe UI", 7, "bold"),
                bg="#121826", fg=TEXT_MUTED, activebackground=CARD_BORDER, activeforeground=TEXT_WHITE,
                bd=0, padx=8, pady=2, cursor="hand2",
                command=lambda s=step: self.on_step(self.joint_id, s),
            ).pack(side="left", padx=2)

        if has_stop_base:
            tk.Button(
                row, text="⏹ STOP BASE", font=("Segoe UI", 8, "bold"),
                bg="#42131f", fg="#ff8099", activebackground=COLOR_RED, activeforeground="#fff",
                bd=0, padx=10, pady=2, cursor="hand2", command=self.on_stop_base,
            ).pack(side="right", padx=2)

        if has_claw_actions:
            tk.Button(
                row, text="🔓 FULL OPEN ", font=("Segoe UI", 8, "bold"),
                bg="#11334c", fg="#64b5f6", activebackground="#0091ea", activeforeground="#fff",
                bd=0, padx=8, pady=2, cursor="hand2",
                command=lambda: self.on_set(self.joint_id, self.open_value),
            ).pack(side="right", padx=2)

            tk.Button(
                row, text="🔒 FULL GRIP", font=("Segoe UI", 8, "bold"),
                bg="#3d2a0e", fg="#ffca28", activebackground="#ff8f00", activeforeground="#fff",
                bd=0, padx=8, pady=2, cursor="hand2",
                command=lambda: self.on_set(self.joint_id, self.grip_value),
            ).pack(side="right", padx=2)
