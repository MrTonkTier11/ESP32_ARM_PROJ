"""joint_card.py - versatile card component supporting two-button jog, two-button step, and slider controls."""

import tkinter as tk
from theme import (CARD_BG, CARD_BORDER, ACCENT_CYAN, TEXT_WHITE, TEXT_MUTED,
                    SLIDER_TROUGH, COLOR_RED)


class JointCard(tk.Frame):
    def __init__(self, parent, joint_id, variable, title, subtitle,
                 card_type="two_button",  # "base", "two_button", or "slider"
                 left_text="◀ LEFT", right_text="RIGHT ▶",
                 left_sub="CCW", right_sub="CW",
                 on_slider=None, on_step=None, on_set=None,
                 on_jog_base=None, on_stop_base=None, on_nudge_base=None, on_speed_change=None,
                 min_val=0, max_val=180,
                 open_value=30, grip_value=150,
                 has_claw_actions=False):
        super().__init__(parent, bg=CARD_BG, highlightbackground=CARD_BORDER,
                         highlightthickness=1, padx=12, pady=8)
        self.joint_id = joint_id
        self.var = variable
        self.card_type = card_type
        self.on_slider = on_slider
        self.on_step = on_step
        self.on_set = on_set
        self.on_jog_base = on_jog_base
        self.on_stop_base = on_stop_base
        self.on_nudge_base = on_nudge_base
        self.on_speed_change = on_speed_change
        self.min_val = min_val
        self.max_val = max_val
        self.open_value = open_value
        self.grip_value = grip_value
        self.badge = None
        self.speed_buttons = {}

        # Auto-repeat timer for held buttons
        self._repeat_timer = None
        self._repeat_job = None
        self._is_held = False

        self._build_header(title)
        tk.Label(self, text=subtitle, font=("Segoe UI", 8), bg=CARD_BG,
                 fg=TEXT_MUTED).pack(anchor="w", pady=(0, 4))

        if self.card_type == "base":
            self._build_base_controls(left_text, right_text, left_sub, right_sub)
        elif self.card_type == "slider":
            self._build_slider_controls(left_text, right_text, has_claw_actions)
        else:  # "two_button"
            self._build_two_button_controls(left_text, right_text, left_sub, right_sub)

    # ---------- Public Methods ----------
    def update_badge(self, text_or_val, is_active=False):
        if not self.badge:
            return
        if self.card_type == "base":
            self.badge.config(text=str(text_or_val))
            if is_active:
                self.badge.config(fg=ACCENT_CYAN, highlightbackground=ACCENT_CYAN)
            else:
                self.badge.config(fg=TEXT_WHITE, highlightbackground=CARD_BORDER)
        else:
            self.badge.config(text=f"{int(text_or_val)}°")

    def set_active_speed(self, speed):
        for spd, btn in self.speed_buttons.items():
            if spd == speed:
                btn.config(bg=ACCENT_CYAN, fg="#000000")
            else:
                btn.config(bg="#121826", fg=TEXT_MUTED)

    # ---------- Layout Builders ----------
    def _build_header(self, title):
        hdr = tk.Frame(self, bg=CARD_BG)
        hdr.pack(fill="x")

        tk.Label(hdr, text=title, font=("Segoe UI", 10, "bold"),
                 bg=CARD_BG, fg=ACCENT_CYAN).pack(side="left")

        initial_badge = "STOPPED" if self.card_type == "base" else f"{self.var.get()}°"
        min_width = 10 if self.card_type == "base" else 6
        self.badge = tk.Label(
            hdr, text=initial_badge, font=("Segoe UI", 11, "bold"),
            bg="#0d1322", fg=TEXT_WHITE, padx=8, pady=1, bd=1, relief="solid",
            highlightbackground=CARD_BORDER, highlightthickness=1, width=min_width
        )
        self.badge.pack(side="right")

    # ---------- 1. BASE: Two Big Jog Buttons + Nudge + Speed (matches HTML) ----------
    def _build_base_controls(self, left_text, right_text, left_sub, right_sub):
        # Two prominent Jog Buttons side by side
        jog_row = tk.Frame(self, bg=CARD_BG)
        jog_row.pack(fill="x", pady=(4, 6))

        btn_left = tk.Button(
            jog_row, text=f"{left_text}\n[{left_sub}]", font=("Segoe UI", 9, "bold"),
            bg="#1c2844", fg=TEXT_WHITE, activebackground=ACCENT_CYAN, activeforeground="#000000",
            bd=1, relief="flat", pady=6, cursor="hand2"
        )
        btn_left.pack(side="left", fill="x", expand=True, padx=(0, 4))
        btn_left.bind("<ButtonPress-1>", lambda e: self._on_base_press(-1, btn_left))
        btn_left.bind("<ButtonRelease-1>", lambda e: self._on_base_release(btn_left))
        btn_left.bind("<Leave>", lambda e: self._on_base_release(btn_left))

        btn_right = tk.Button(
            jog_row, text=f"{right_text}\n[{right_sub}]", font=("Segoe UI", 9, "bold"),
            bg="#1c2844", fg=TEXT_WHITE, activebackground=ACCENT_CYAN, activeforeground="#000000",
            bd=1, relief="flat", pady=6, cursor="hand2"
        )
        btn_right.pack(side="right", fill="x", expand=True, padx=(4, 0))
        btn_right.bind("<ButtonPress-1>", lambda e: self._on_base_press(1, btn_right))
        btn_right.bind("<ButtonRelease-1>", lambda e: self._on_base_release(btn_right))
        btn_right.bind("<Leave>", lambda e: self._on_base_release(btn_right))

        # Fine Nudge & Stop Row
        nudge_row = tk.Frame(self, bg=CARD_BG)
        nudge_row.pack(fill="x", pady=2)

        tk.Button(
            nudge_row, text="◀ 80ms", font=("Segoe UI", 7, "bold"),
            bg="#121826", fg=TEXT_MUTED, activebackground=CARD_BORDER, activeforeground=TEXT_WHITE,
            bd=0, padx=6, pady=3, cursor="hand2",
            command=lambda: self.on_nudge_base(-1, 80) if self.on_nudge_base else None
        ).pack(side="left", padx=1)

        tk.Button(
            nudge_row, text="◀ 200ms", font=("Segoe UI", 7, "bold"),
            bg="#121826", fg=TEXT_MUTED, activebackground=CARD_BORDER, activeforeground=TEXT_WHITE,
            bd=0, padx=6, pady=3, cursor="hand2",
            command=lambda: self.on_nudge_base(-1, 200) if self.on_nudge_base else None
        ).pack(side="left", padx=1)

        tk.Button(
            nudge_row, text="⏹ STOP BASE", font=("Segoe UI", 8, "bold"),
            bg="#42131f", fg="#ff8099", activebackground=COLOR_RED, activeforeground="#fff",
            bd=0, padx=10, pady=3, cursor="hand2",
            command=lambda: self.on_stop_base() if self.on_stop_base else None
        ).pack(side="left", fill="x", expand=True, padx=4)

        tk.Button(
            nudge_row, text="200ms ▶", font=("Segoe UI", 7, "bold"),
            bg="#121826", fg=TEXT_MUTED, activebackground=CARD_BORDER, activeforeground=TEXT_WHITE,
            bd=0, padx=6, pady=3, cursor="hand2",
            command=lambda: self.on_nudge_base(1, 200) if self.on_nudge_base else None
        ).pack(side="right", padx=1)

        tk.Button(
            nudge_row, text="80ms ▶", font=("Segoe UI", 7, "bold"),
            bg="#121826", fg=TEXT_MUTED, activebackground=CARD_BORDER, activeforeground=TEXT_WHITE,
            bd=0, padx=6, pady=3, cursor="hand2",
            command=lambda: self.on_nudge_base(1, 80) if self.on_nudge_base else None
        ).pack(side="right", padx=1)

        # Speed Selection Row
        speed_row = tk.Frame(self, bg=CARD_BG)
        speed_row.pack(fill="x", pady=(4, 0))

        tk.Label(speed_row, text="Speed:", font=("Segoe UI", 8, "bold"),
                 bg=CARD_BG, fg=TEXT_MUTED).pack(side="left", padx=(0, 6))

        for spd, label in ((120, "Slow"), (200, "Normal"), (320, "Fast")):
            is_default = (spd == 200)
            btn = tk.Button(
                speed_row, text=label, font=("Segoe UI", 7, "bold"),
                bg=ACCENT_CYAN if is_default else "#121826",
                fg="#000000" if is_default else TEXT_MUTED,
                activebackground=ACCENT_CYAN, activeforeground="#000000",
                bd=0, padx=10, pady=2, cursor="hand2",
                command=lambda s=spd: self._on_speed_clicked(s)
            )
            btn.pack(side="left", padx=2)
            self.speed_buttons[spd] = btn

    def _on_base_press(self, direction, button):
        if self._is_held:
            return
        self._is_held = True
        button.config(bg=ACCENT_CYAN, fg="#000000")
        if self.on_jog_base:
            self.on_jog_base(direction)

    def _on_base_release(self, button):
        if not self._is_held:
            return
        self._is_held = False
        button.config(bg="#1c2844", fg=TEXT_WHITE)
        if self.on_stop_base:
            self.on_stop_base()

    def _on_speed_clicked(self, speed):
        self.set_active_speed(speed)
        if self.on_speed_change:
            self.on_speed_change(speed)

    # ---------- 2. TWO-BUTTON: Big Buttons with Hold-to-Move + Fine Steps (Shoulder, Elbow) ----------
    def _build_two_button_controls(self, left_text, right_text, left_sub, right_sub):
        row = tk.Frame(self, bg=CARD_BG)
        row.pack(fill="x", pady=(4, 6))

        btn_left = tk.Button(
            row, text=f"{left_text}\n[{left_sub}]", font=("Segoe UI", 9, "bold"),
            bg="#182338", fg=TEXT_WHITE, activebackground=ACCENT_CYAN, activeforeground="#000000",
            bd=1, relief="flat", pady=6, cursor="hand2"
        )
        btn_left.pack(side="left", fill="x", expand=True, padx=(0, 4))
        btn_left.bind("<ButtonPress-1>", lambda e: self._on_joint_press(-5, btn_left))
        btn_left.bind("<ButtonRelease-1>", lambda e: self._on_joint_release(btn_left))
        btn_left.bind("<Leave>", lambda e: self._on_joint_release(btn_left))

        btn_right = tk.Button(
            row, text=f"{right_text}\n[{right_sub}]", font=("Segoe UI", 9, "bold"),
            bg="#182338", fg=TEXT_WHITE, activebackground=ACCENT_CYAN, activeforeground="#000000",
            bd=1, relief="flat", pady=6, cursor="hand2"
        )
        btn_right.pack(side="right", fill="x", expand=True, padx=(4, 0))
        btn_right.bind("<ButtonPress-1>", lambda e: self._on_joint_press(5, btn_right))
        btn_right.bind("<ButtonRelease-1>", lambda e: self._on_joint_release(btn_right))
        btn_right.bind("<Leave>", lambda e: self._on_joint_release(btn_right))

        # Fine step buttons
        step_row = tk.Frame(self, bg=CARD_BG)
        step_row.pack(fill="x", pady=2)
        for step in (-5, -1, 1, 5):
            tk.Button(
                step_row, text=f"{step:+d}°", font=("Segoe UI", 8, "bold"),
                bg="#121826", fg=TEXT_MUTED, activebackground=CARD_BORDER, activeforeground=TEXT_WHITE,
                bd=0, padx=12, pady=2, cursor="hand2",
                command=lambda s=step: self.on_step(self.joint_id, s) if self.on_step else None,
            ).pack(side="left", padx=2, expand=True, fill="x")

    def _on_joint_press(self, initial_step, button):
        button.config(bg=ACCENT_CYAN, fg="#000000")
        if self.on_step:
            self.on_step(self.joint_id, initial_step)

        # Start repeating after 280ms delay
        self._cancel_repeat()
        step_unit = 2 if initial_step > 0 else -2
        self._repeat_job = self.after(280, lambda: self._joint_repeat_step(step_unit))

    def _joint_repeat_step(self, step_unit):
        if self.on_step:
            self.on_step(self.joint_id, step_unit)
        self._repeat_job = self.after(50, lambda: self._joint_repeat_step(step_unit))

    def _on_joint_release(self, button):
        button.config(bg="#182338", fg=TEXT_WHITE)
        self._cancel_repeat()

    def _cancel_repeat(self):
        if self._repeat_job:
            self.after_cancel(self._repeat_job)
            self._repeat_job = None

    # ---------- 3. SLIDER: Slider Bar + Buttons + Full Open / Grip (Claw Gripper) ----------
    def _build_slider_controls(self, left_text, right_text, has_claw_actions):
        row = tk.Frame(self, bg=CARD_BG)
        row.pack(fill="x", pady=4)

        tk.Button(
            row, text=left_text, font=("Segoe UI", 9, "bold"),
            bg="#182338", fg=TEXT_WHITE, activebackground=ACCENT_CYAN, activeforeground="#000000",
            bd=1, relief="flat", width=9, pady=5, cursor="hand2",
            command=lambda: self.on_step(self.joint_id, -5) if self.on_step else None,
        ).pack(side="left", padx=(0, 6))

        tk.Scale(
            row, from_=self.min_val, to=self.max_val, orient="horizontal",
            variable=self.var, showvalue=0,
            command=lambda val: self.on_slider(self.joint_id, val) if self.on_slider else None,
            bg=CARD_BG, troughcolor=SLIDER_TROUGH, highlightthickness=0,
            activebackground=ACCENT_CYAN, bd=0,
        ).pack(side="left", fill="x", expand=True, padx=4)

        tk.Button(
            row, text=right_text, font=("Segoe UI", 9, "bold"),
            bg="#182338", fg=TEXT_WHITE, activebackground=ACCENT_CYAN, activeforeground="#000000",
            bd=1, relief="flat", width=9, pady=5, cursor="hand2",
            command=lambda: self.on_step(self.joint_id, 5) if self.on_step else None,
        ).pack(side="right", padx=(6, 0))

        action_row = tk.Frame(self, bg=CARD_BG)
        action_row.pack(fill="x", pady=(3, 0))

        if has_claw_actions:
            tk.Button(
                action_row, text="🔓 FULL OPEN", font=("Segoe UI", 8, "bold"),
                bg="#11334c", fg="#64b5f6", activebackground="#0091ea", activeforeground="#fff",
                bd=0, padx=10, pady=3, cursor="hand2",
                command=lambda: self.on_set(self.joint_id, self.open_value) if self.on_set else None,
            ).pack(side="left", padx=2)

        for step in (-2, 2):
            tk.Button(
                action_row, text=f"{step:+d}°", font=("Segoe UI", 7, "bold"),
                bg="#121826", fg=TEXT_MUTED, activebackground=CARD_BORDER, activeforeground=TEXT_WHITE,
                bd=0, padx=8, pady=3, cursor="hand2",
                command=lambda s=step: self.on_step(self.joint_id, s) if self.on_step else None,
            ).pack(side="left", padx=2)

        if has_claw_actions:
            tk.Button(
                action_row, text="🔒 FULL GRIP", font=("Segoe UI", 8, "bold"),
                bg="#3d2a0e", fg="#ffca28", activebackground="#ff8f00", activeforeground="#fff",
                bd=0, padx=10, pady=3, cursor="hand2",
                command=lambda: self.on_set(self.joint_id, self.grip_value) if self.on_set else None,
            ).pack(side="right", padx=2)
