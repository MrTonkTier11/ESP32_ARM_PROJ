"""arm_visualizer.py - live 2D drawing of the arm (inclined pose)."""

import math
import tkinter as tk
from theme import ACCENT_CYAN, CARD_BORDER, COLOR_YELLOW


class ArmVisualizer(tk.Canvas):
    LEAN_DEG = 35         # extra tilt of the whole arm
    ELBOW_BEND_DEG = 20   # natural forearm bend
    L1 = 60               # upper-arm length (px)
    L2 = 50               # forearm length (px)
    CLAW_LEN = 16

    def __init__(self, parent, state):
        super().__init__(parent, bg="#090d15", highlightthickness=1,
                         highlightbackground=CARD_BORDER, height=210)
        self.state = state
        self.bind("<Configure>", lambda e: self.redraw())

    def redraw(self):
        """Draws a 2D vector graphic of the arm (inclined pose, no text labels)."""
        c = self
        c.delete("all")

        w = c.winfo_width()
        h = c.winfo_height()
        if w < 10:
            w = 350
        if h < 10:
            h = 210

        # Centre the whole drawing (base + inclined arm) in the canvas.
        bx = w // 2 - 16
        by = h - 35

        shoulder_deg = (self.state.get(1) - 90) * 0.8
        elbow_deg = (self.state.get(2) - 90) * 0.8
        claw_servo =self.state.to_servo(3, self.state.get(3))
        claw_spread = max(3, min(24, (180 - claw_servo) * 0.13))

        # Base platform
        c.create_rectangle(bx - 55, by, bx + 55, by + 16, fill="#1c2538", outline="#2b3b59", width=2)
        c.create_oval(bx - 18, by - 6, bx + 18, by + 12, fill="#0f1624", outline=ACCENT_CYAN, width=2)

        rad_s = math.radians(-90 + self.LEAN_DEG + shoulder_deg)
        ex = bx + self.L1 * math.cos(rad_s)
        ey = by + self.L1 * math.sin(rad_s)

        rad_e = rad_s + math.radians(self.ELBOW_BEND_DEG + elbow_deg)
        wx = ex + self.L2 * math.cos(rad_e)
        wy = ey + self.L2 * math.sin(rad_e)

        c.create_line(bx, by, ex, ey, fill="#00b0ff", width=7, capstyle="round")
        c.create_oval(bx - 6, by - 6, bx + 6, by + 6, fill="#ffffff", outline=ACCENT_CYAN, width=2)

        c.create_line(ex, ey, wx, wy, fill="#2979ff", width=5, capstyle="round")
        c.create_oval(ex - 5, ey - 5, ex + 5, ey + 5, fill="#ffffff", outline="#00b0ff", width=2)

        c.create_oval(wx - 4, wy - 4, wx + 4, wy + 4, fill=COLOR_YELLOW, outline="#ffab00", width=1)

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
