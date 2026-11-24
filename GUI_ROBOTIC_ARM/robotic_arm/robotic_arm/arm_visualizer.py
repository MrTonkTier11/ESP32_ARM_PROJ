"""arm_visualizer.py - live 2D drawing of the arm with rotating base directional arrow."""

import math
import tkinter as tk
from theme import ACCENT_CYAN, CARD_BORDER, COLOR_YELLOW


class ArmVisualizer(tk.Canvas):
    LEAN_DEG = -10         # extra tilt of the whole arm
    ELBOW_BEND_DEG = 20   # natural forearm bend
    L1 = 60               # base upper-arm length (px)
    L2 = 50               # base forearm length (px)
    CLAW_LEN = 16

    def __init__(self, parent, state):
        super().__init__(parent, bg="#090d15", highlightthickness=1,
                         highlightbackground=CARD_BORDER)
        self.state = state
        self.bind("<Configure>", lambda e: self.redraw())

    def redraw(self):
        """Draws an enlarged, responsive 2D vector graphic of the arm with interactive rotating base direction arrow."""
        c = self
        c.delete("all")

        w = c.winfo_width()
        h = c.winfo_height()
        if w < 10:
            w = 550
        if h < 10:
            h = 420

        # Responsive scale factor to enlarge arm and fill available space (~70% view)
        scale = min(w / 340.0, h / 240.0)
        scale = max(1.1, min(scale, 2.3))

        l1 = self.L1 * scale
        l2 = self.L2 * scale
        claw_len = self.CLAW_LEN * scale

        # Centre the arm drawing in the canvas
        bx = w // 2
        by = h - int(56 * scale)

        # Shoulder: - shoulder_deg so UP button rotates arm UP, and DOWN button lowers arm DOWN
        shoulder_deg = (self.state.shown(1) - 90) * 0.8
        elbow_deg = (self.state.shown(2) - 90) * 0.8

        claw_val = self.state.shown(3)   # 0–180, same direction as the slider
        claw_spread = max(3.0 * scale, min(32.0 * scale, (180 - claw_val) * 0.16 * scale))
        base_angle = self.state.get(4)  # 0° = forward, negative = left, positive = right

        # 1. Base Pedestal Platform (scaled)
        pw = 65 * scale
        c.create_rectangle(bx - pw, by + 4 * scale, bx + pw, by + 22 * scale, fill="#151d2d", outline="#25324d", width=max(1, int(2 * scale)))
        c.create_rectangle(bx - pw - 12 * scale, by + 18 * scale, bx + pw + 12 * scale, by + 28 * scale, fill="#0f1624", outline="#1c263a", width=1)

        # 2. Base Turntable Dial (scaled)
        dw = 34 * scale
        dh = 16 * scale
        c.create_oval(bx - dw, by - dh, bx + dw, by + dh, fill="#0c121e", outline="#25324d", width=max(1, int(2 * scale)))
        c.create_oval(bx - dw * 0.8, by - dh * 0.7, bx + dw * 0.8, by + dh * 0.7, fill="#131c2c", outline="#1f2d45", width=1)

        # 3. Base Direction Arrow
        rad_b = math.radians(base_angle)
        arrow_len = 26 * scale
        cx = bx
        cy = by + 2 * scale

        tip_x = cx + arrow_len * math.sin(rad_b)
        tip_y = cy - arrow_len * math.cos(rad_b)

        # Arrow shaft
        c.create_line(cx, cy, tip_x, tip_y, fill=ACCENT_CYAN, width=max(2, int(3.5 * scale)), capstyle="round")

        # Arrowhead polygon
        barb_len = 9 * scale
        barb_w = 6 * scale
        b1_x = cx + (arrow_len - barb_len) * math.sin(rad_b) - barb_w * math.cos(rad_b)
        b1_y = cy - (arrow_len - barb_len) * math.cos(rad_b) - barb_w * math.sin(rad_b)
        b2_x = cx + (arrow_len - barb_len) * math.sin(rad_b) + barb_w * math.cos(rad_b)
        b2_y = cy - (arrow_len - barb_len) * math.cos(rad_b) + barb_w * math.sin(rad_b)
        mid_x = cx + (arrow_len - 6 * scale) * math.sin(rad_b)
        mid_y = cy - (arrow_len - 6 * scale) * math.cos(rad_b)

        c.create_polygon(tip_x, tip_y, b1_x, b1_y, mid_x, mid_y, b2_x, b2_y,
                         fill=ACCENT_CYAN, outline="#ffffff", width=1)

        # Turntable center pivot cap
        cap_r = 5 * scale
        c.create_oval(cx - cap_r, cy - cap_r, cx + cap_r, cy + cap_r, fill="#ffffff", outline=ACCENT_CYAN, width=max(1, int(2 * scale)))

        # Base heading readout text below platform
        norm_ang = ((int(base_angle) + 180) % 360) - 180
        if norm_ang == 0:
            dir_label = "BASE: 0° [CENTER]"
        elif norm_ang < 0:
            dir_label = f"BASE: ◀ {abs(norm_ang)}° LEFT"
        else:
            dir_label = f"BASE: {norm_ang}° RIGHT ▶"
        font_sz = max(9, int(9 * scale * 0.85))
        c.create_text(bx, by + int(38 * scale), text=dir_label, fill=ACCENT_CYAN, font=("Segoe UI", font_sz, "bold"))

        # 4. Upper arm kinematics (Shoulder - fixed direction: UP tilts up, DOWN tilts down)
        rad_s = math.radians(-80 + self.LEAN_DEG - shoulder_deg)
        ex = bx + l1 * math.cos(rad_s)
        ey = by + l1 * math.sin(rad_s)

        # 5. Forearm kinematics (Elbow)
        rad_e = rad_s + math.radians(self.ELBOW_BEND_DEG + elbow_deg)
        wx = ex + l2 * math.cos(rad_e)
        wy = ey + l2 * math.sin(rad_e)

        # Draw arm segments and joint pivots
        w_arm1 = max(4, int(8 * scale))
        w_arm2 = max(3, int(6 * scale))
        w_claw = max(2, int(3.5 * scale))
        piv1_r = max(4, int(7 * scale))
        piv2_r = max(3, int(5.5 * scale))
        piv3_r = max(3, int(4.5 * scale))

        c.create_line(bx, by, ex, ey, fill="#00b0ff", width=w_arm1, capstyle="round")
        c.create_oval(bx - piv1_r, by - piv1_r, bx + piv1_r, by + piv1_r, fill="#ffffff", outline=ACCENT_CYAN, width=max(1, int(2 * scale)))

        c.create_line(ex, ey, wx, wy, fill="#2979ff", width=w_arm2, capstyle="round")
        c.create_oval(ex - piv2_r, ey - piv2_r, ex + piv2_r, ey + piv2_r, fill="#ffffff", outline="#00b0ff", width=max(1, int(2 * scale)))

        c.create_oval(wx - piv3_r, wy - piv3_r, wx + piv3_r, wy + piv3_r, fill=COLOR_YELLOW, outline="#ffab00", width=1)

        # 6. Claw dual-finger pincers
        rad_perp = rad_e + math.pi / 2

        px_l1 = wx + math.cos(rad_perp) * (claw_spread / 2)
        py_l1 = wy + math.sin(rad_perp) * (claw_spread / 2)
        px_l2 = px_l1 + math.cos(rad_e) * claw_len
        py_l2 = py_l1 + math.sin(rad_e) * claw_len

        px_r1 = wx - math.cos(rad_perp) * (claw_spread / 2)
        py_r1 = wy - math.sin(rad_perp) * (claw_spread / 2)
        px_r2 = px_r1 + math.cos(rad_e) * claw_len
        py_r2 = py_r1 + math.sin(rad_e) * claw_len

        c.create_line(wx, wy, px_l1, py_l1, fill=COLOR_YELLOW, width=w_claw)
        c.create_line(px_l1, py_l1, px_l2, py_l2, fill=COLOR_YELLOW, width=w_claw, capstyle="round")
        c.create_line(wx, wy, px_r1, py_r1, fill=COLOR_YELLOW, width=w_claw)
        c.create_line(px_r1, py_r1, px_r2, py_r2, fill=COLOR_YELLOW, width=w_claw, capstyle="round")
