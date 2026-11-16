"""arm_state.py - single source of truth for the joint angles."""

import tkinter as tk


class ArmState:
    """Holds the 4 joint angles (0-180). No drawing, no networking."""

    JOINTS = (1, 2, 3, 4)          # 1 Shoulder, 2 Elbow, 3 Claw, 4 Base
    NAMES = {1: "Shoulder", 2: "Elbow", 3: "Claw", 4: "Base"}
    MIN_ANGLE = 30
    MAX_ANGLE = 150
    DEFAULT = 90

    def __init__(self):
        self.vars = {j: tk.IntVar(value=self.DEFAULT) for j in self.JOINTS}

    def clamp(self, value):
        return max(self.MIN_ANGLE, min(self.MAX_ANGLE, int(value)))

    def get(self, joint_id):
        return self.vars[joint_id].get()

    def set(self, joint_id, value):
        value = self.clamp(value)
        self.vars[joint_id].set(value)
        return value
