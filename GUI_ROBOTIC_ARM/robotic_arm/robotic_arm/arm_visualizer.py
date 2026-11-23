"""arm_visualizer.py - live 2D drawing of the arm with rotating base directional arrow."""

import math
import tkinter as tk
from theme import ACCENT_CYAN, CARD_BORDER, COLOR_YELLOW


class ArmVisualizer(tk.Canvas):
    LEAN_DEG = -10         # extra tilt of the whole arm
    ELBOW_BEND_DEG = 20   # natural forearm bend
    L1 = 60               # upper-arm length (px)
    L2 = 50               # forearm length (px)
    CLAW_LEN = 16

    def __init__(self, parent, state):
        super().__init__(parent, bg="#090d15", highlightthickness=1,
                         highlightbackground=CARD_BORDER, height=225)
        self.state = state
        self.bind("<Configure>", lambda e: self.redraw())

    def redraw(self):
        """Draws a 2D vector graphic of the arm with interactive rotating base direction arrow."""
        c = self
        c.delete("all")

        w = c.winfo_width()
        h = c.winfo_height()
        if w < 10:
            w = 350
        if h < 10:
            h = 225

        # Centre the whole drawing in the canvas
        bx = w // 2 - 16
        by = h - 44

        shoulder_deg = (self.state.shown(1) - 90) * 0.8
        elbow_deg = (self.state.shown(2) - 90) * 0.8
        # claw_val: 0 = fully open end of slider, 180 = full grip end.
        # Because joint 3 is inverted, a high slider value means the servo
        # is at a LOW angle (closed/gripped). We use the raw shown() value
        # (before servo inversion) so the visual spread matches the slider:
        # slider near 0  → spread large (open claw)
        # slider near 180 → spread small (gripped / closed claw)
        claw_val = self.state.shown(3)   # 0–180, same direction as the slider
        claw_spread = max(2, min(26, (180 - claw_val) * 0.144))
        base_angle = self.state.get(4)  # 0° = forward, negative = left, positive = right

        # 1. Base Pedestal Platform
        c.create_rectangle(bx - 60, by + 4, bx + 60, by + 20, fill="#151d2d", outline="#25324d", width=2)
        c.create_rectangle(bx - 70, by + 18, bx + 70, by + 26, fill="#0f1624", outline="#1c263a", width=1)

        # 2. Base Turntable Dial
        c.create_oval(bx - 32, by - 12, bx + 32, by + 16, fill="#0c121e", outline="#25324d", width=2)
        c.create_oval(bx - 26, by - 8, bx + 26, by + 12, fill="#131c2c", outline="#1f2d45", width=1)

        # 3. Base Direction Arrow
        # 0° = pointing UP/forward, negative = CCW/left, positive = CW/right
        rad_b = math.radians(base_angle)
        arrow_len = 22
        cx = bx
        cy = by + 2

        tip_x = cx + arrow_len * math.sin(rad_b)
        tip_y = cy - arrow_len * math.cos(rad_b)

        # Arrow shaft
        c.create_line(cx, cy, tip_x, tip_y, fill=ACCENT_CYAN, width=3, capstyle="round")

        # Arrowhead polygon
        barb_len = 7
        barb_w = 5
        b1_x = cx + (arrow_len - barb_len) * math.sin(rad_b) - barb_w * math.cos(rad_b)
        b1_y = cy - (arrow_len - barb_len) * math.cos(rad_b) - barb_w * math.sin(rad_b)
        b2_x = cx + (arrow_len - barb_len) * math.sin(rad_b) + barb_w * math.cos(rad_b)
        b2_y = cy - (arrow_len - barb_len) * math.cos(rad_b) + barb_w * math.sin(rad_b)
        mid_x = cx + (arrow_len - 5) * math.sin(rad_b)
        mid_y = cy - (arrow_len - 5) * math.cos(rad_b)

        c.create_polygon(tip_x, tip_y, b1_x, b1_y, mid_x, mid_y, b2_x, b2_y,
                         fill=ACCENT_CYAN, outline="#ffffff", width=1)

        # Turntable center pivot cap
        c.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill="#ffffff", outline=ACCENT_CYAN, width=2)

        # Base heading readout text below platform
        norm_ang = ((int(base_angle) + 180) % 360) - 180
        if norm_ang == 0:
            dir_label = "BASE: 0° [CENTER]"
        elif norm_ang < 0:
            dir_label = f"BASE: ◀ {abs(norm_ang)}° LEFT"
        else:
            dir_label = f"BASE: {norm_ang}° RIGHT ▶"
        c.create_text(bx, by + 34, text=dir_label, fill=ACCENT_CYAN, font=("Segoe UI", 8, "bold"))

        # 4. Upper arm kinematics (Shoulder)
        rad_s = math.radians(-80 + self.LEAN_DEG + shoulder_deg)
        ex = bx + self.L1 * math.cos(rad_s)
        ey = by + self.L1 * math.sin(rad_s)

        # 5. Forearm kinematics (Elbow)
        rad_e = rad_s + math.radians(self.ELBOW_BEND_DEG + elbow_deg)
        wx = ex + self.L2 * math.cos(rad_e)
        wy = ey + self.L2 * math.sin(rad_e)

        # Draw arm segments and joint pivots
        c.create_line(bx, by, ex, ey, fill="#00b0ff", width=7, capstyle="round")
        c.create_oval(bx - 6, by - 6, bx + 6, by + 6, fill="#ffffff", outline=ACCENT_CYAN, width=2)

        c.create_line(ex, ey, wx, wy, fill="#2979ff", width=5, capstyle="round")
        c.create_oval(ex - 5, ey - 5, ex + 5, ey + 5, fill="#ffffff", outline="#00b0ff", width=2)

        c.create_oval(wx - 4, wy - 4, wx + 4, wy + 4, fill=COLOR_YELLOW, outline="#ffab00", width=1)

        # 6. Claw dual-finger pincers
        rad_perp = rad_e + math.pi / 2

        px_l1 = wx + math.cos(rad_perp) * (claw_spread / 2)
        py_l1 = wy + math.sin(rad_perp) * (claw_spread / 2)
        px_l2 = px_l1 + math.cos(rad_e) * self.CLAW_LEN
        py_l2 = py_l1 + math.sin(rad_e) * self.CLAW_LEN

        px_r1 = wx - math.cos(rad_perp) * (claw_spread / 2)
        py_r1 = wy - math.sin(rad_perp) * (claw_spread / 2)
        px_r2 = px_r1 + math.cos(rad_e) * self.CLAW_LEN
        py_r2 = py_r1 + math.sin(rad_e) * self.CLAW_LEN

        c.create_line(wx, wy, px_l1, py_l1, fill=COLOR_YELLOW, width=3)
        c.create_line(px_l1, py_l1, px_l2, py_l2, fill=COLOR_YELLOW, width=3, capstyle="round")
        c.create_line(wx, wy, px_r1, py_r1, fill=COLOR_YELLOW, width=3)
        c.create_line(px_r1, py_r1, px_r2, py_r2, fill=COLOR_YELLOW, width=3, capstyle="round")
