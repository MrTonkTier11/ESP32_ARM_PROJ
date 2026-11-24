"""joint_card.py - versatile card component supporting two-button jog, two-button step, and slider controls with large icons."""

import tkinter as tk
from pathlib import Path
from theme import (CARD_BG, CARD_BORDER, ACCENT_CYAN, TEXT_WHITE, TEXT_MUTED,
                    SLIDER_TROUGH, COLOR_RED)

ICONS_DIR = Path(__file__).resolve().parent / "icons"
_ICON_CACHE = {}


def get_icon(name):
    if name not in _ICON_CACHE:
        p = ICONS_DIR / name
        if p.exists():
            try:
                _ICON_CACHE[name] = tk.PhotoImage(file=str(p))
            except Exception:
                _ICON_CACHE[name] = None
        else:
            _ICON_CACHE[name] = None
    return _ICON_CACHE[name]


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
                         highlightthickness=1, padx=10, pady=6)
        self.joint_id = joint_id
        self.var = variable
        self.card_type = card_type
        self.on_slider = on_slider
        self.on_step = on_step
        self.on_set = on_set
        self.on_jog_base = on_jog_base
        self.on_stop_base = on_stop_base
        self.min_val = min_val
        self.max_val = max_val
        self.open_value = open_value
        self.grip_value = grip_value
        self.badge = None

        # Auto-repeat timer for held buttons
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

    # ---------- Layout Builders ----------
    def _build_header(self, title):
        hdr = tk.Frame(self, bg=CARD_BG)
        hdr.pack(fill="x")

        tk.Label(hdr, text=title, font=("Segoe UI", 9, "bold"),
                 bg=CARD_BG, fg=ACCENT_CYAN).pack(side="left")

        initial_badge = "STOPPED" if self.card_type == "base" else f"{self.var.get()}°"
        min_width = 9 if self.card_type == "base" else 5
        self.badge = tk.Label(
            hdr, text=initial_badge, font=("Segoe UI", 10, "bold"),
            bg="#0d1322", fg=TEXT_WHITE, padx=6, pady=1, bd=1, relief="solid",
            highlightbackground=CARD_BORDER, highlightthickness=1, width=min_width
        )
        self.badge.pack(side="right")

    # ---------- 1. BASE: Two Prominent Jog Buttons with Large Icons (Eased Rotation) ----------
    def _build_base_controls(self, left_text, right_text, left_sub, right_sub):
        jog_row = tk.Frame(self, bg=CARD_BG)
        jog_row.pack(fill="x", pady=(2, 4))

        icon_left = get_icon("rotate_left.png")
        icon_right = get_icon("rotate_right.png")

        btn_left = tk.Button(
            jog_row, image=icon_left, text=f" {left_text}\n [{left_sub}]",
            compound="top", font=("Segoe UI", 8, "bold"),
            bg="#1c2844", fg=TEXT_WHITE, activebackground=ACCENT_CYAN, activeforeground="#000000",
            bd=1, relief="flat", pady=6, cursor="hand2"
        )
        btn_left.pack(side="left", fill="x", expand=True, padx=(0, 4))
        btn_left.bind("<ButtonPress-1>", lambda e: self._on_base_press(-1, btn_left))
        btn_left.bind("<ButtonRelease-1>", lambda e: self._on_base_release(btn_left))
        btn_left.bind("<Leave>", lambda e: self._on_base_release(btn_left))

        btn_right = tk.Button(
            jog_row, image=icon_right, text=f" {right_text}\n [{right_sub}]",
            compound="top", font=("Segoe UI", 8, "bold"),
            bg="#1c2844", fg=TEXT_WHITE, activebackground=ACCENT_CYAN, activeforeground="#000000",
            bd=1, relief="flat", pady=6, cursor="hand2"
        )
        btn_right.pack(side="right", fill="x", expand=True, padx=(4, 0))
        btn_right.bind("<ButtonPress-1>", lambda e: self._on_base_press(1, btn_right))
        btn_right.bind("<ButtonRelease-1>", lambda e: self._on_base_release(btn_right))
        btn_right.bind("<Leave>", lambda e: self._on_base_release(btn_right))

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

    # ---------- 2. TWO-BUTTON: Large Action Buttons with Icons + Fine Steps (Shoulder, Elbow) ----------
    def _build_two_button_controls(self, left_text, right_text, left_sub, right_sub):
        row = tk.Frame(self, bg=CARD_BG)
        row.pack(fill="x", pady=(2, 4))

        if self.joint_id == 1:
            icon_left = get_icon("down.png")
            icon_right = get_icon("up.png")
        else:
            icon_left = get_icon("retract.png")
            icon_right = get_icon("extend.png")

        btn_left = tk.Button(
            row, image=icon_left, text=f" {left_text}\n [{left_sub}]",
            compound="top", font=("Segoe UI", 8, "bold"),
            bg="#182338", fg=TEXT_WHITE, activebackground=ACCENT_CYAN, activeforeground="#000000",
            bd=1, relief="flat", pady=6, cursor="hand2"
        )
        btn_left.pack(side="left", fill="x", expand=True, padx=(0, 4))
        btn_left.bind("<ButtonPress-1>", lambda e: self._on_joint_press(-5, btn_left))
        btn_left.bind("<ButtonRelease-1>", lambda e: self._on_joint_release(btn_left))
        btn_left.bind("<Leave>", lambda e: self._on_joint_release(btn_left))

        btn_right = tk.Button(
            row, image=icon_right, text=f" {right_text}\n [{right_sub}]",
            compound="top", font=("Segoe UI", 8, "bold"),
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
                bd=0, padx=6, pady=2, cursor="hand2",
                command=lambda s=step: self.on_step(self.joint_id, s) if self.on_step else None,
            ).pack(side="left", padx=2, expand=True, fill="x")

    def _on_joint_press(self, initial_step, button):
        button.config(bg=ACCENT_CYAN, fg="#000000")
        if self.on_step:
            self.on_step(self.joint_id, initial_step)

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

    # ---------- 3. SLIDER: Slider Bar + Full Open / Grip (Claw Gripper) ----------
    def _build_slider_controls(self, left_text, right_text, has_claw_actions):
        row = tk.Frame(self, bg=CARD_BG)
        row.pack(fill="x", pady=3)

        tk.Button(
            row, text=left_text, font=("Segoe UI", 8, "bold"),
            bg="#182338", fg=TEXT_WHITE, activebackground=ACCENT_CYAN, activeforeground="#000000",
            bd=1, relief="flat", width=7, pady=4, cursor="hand2",
            command=lambda: self.on_step(self.joint_id, -5) if self.on_step else None,
        ).pack(side="left", padx=(0, 4))

        tk.Scale(
            row, from_=self.min_val, to=self.max_val, orient="horizontal",
            variable=self.var, showvalue=0,
            command=lambda val: self.on_slider(self.joint_id, val) if self.on_slider else None,
            bg=CARD_BG, troughcolor=SLIDER_TROUGH, highlightthickness=0,
            activebackground=ACCENT_CYAN, bd=0,
        ).pack(side="left", fill="x", expand=True, padx=4)

        tk.Button(
            row, text=right_text, font=("Segoe UI", 8, "bold"),
            bg="#182338", fg=TEXT_WHITE, activebackground=ACCENT_CYAN, activeforeground="#000000",
            bd=1, relief="flat", width=7, pady=4, cursor="hand2",
            command=lambda: self.on_step(self.joint_id, 5) if self.on_step else None,
        ).pack(side="right", padx=(4, 0))

        action_row = tk.Frame(self, bg=CARD_BG)
        action_row.pack(fill="x", pady=(2, 0))

        if has_claw_actions:
            tk.Button(
                action_row, text="🔓 FULL OPEN", font=("Segoe UI", 8, "bold"),
                bg="#11334c", fg="#64b5f6", activebackground="#0091ea", activeforeground="#fff",
                bd=0, padx=8, pady=3, cursor="hand2",
                command=lambda: self.on_set(self.joint_id, self.open_value) if self.on_set else None,
            ).pack(side="left", padx=2)

        for step in (-2, 2):
            tk.Button(
                action_row, text=f"{step:+d}°", font=("Segoe UI", 7, "bold"),
                bg="#121826", fg=TEXT_MUTED, activebackground=CARD_BORDER, activeforeground=TEXT_WHITE,
                bd=0, padx=6, pady=3, cursor="hand2",
                command=lambda s=step: self.on_step(self.joint_id, s) if self.on_step else None,
            ).pack(side="left", padx=2)

        if has_claw_actions:
            tk.Button(
                action_row, text="🔒 FULL GRIP", font=("Segoe UI", 8, "bold"),
                bg="#3d2a0e", fg="#ffca28", activebackground="#ff8f00", activeforeground="#fff",
                bd=0, padx=8, pady=3, cursor="hand2",
                command=lambda: self.on_set(self.joint_id, self.grip_value) if self.on_set else None,
            ).pack(side="right", padx=2)
