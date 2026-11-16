"""arm_state.py - single source of truth for the joint angles."""

import tkinter as tk


class ArmState:
    """Holds the 4 joint angles (0-180). No drawing, no networking."""

    JOINTS = (1, 2, 3, 4)          # 1 Shoulder, 2 Elbow, 3 Claw, 4 Base
    NAMES = {1: "Shoulder", 2: "Elbow", 3: "Claw", 4: "Base"}
    DEFAULTS = {1: 90, 2:90, 3:90, 4:180}
    INVERTED = {3: True}



    RANGES = {
        1: (30, 150),
        2: (0, 180),
        3: (0, 180),
        4: (0,360),
    }

    def __init__(self):
        self.vars = {j: tk.IntVar(value=self.DEFAULTS[j]) for j in self.JOINTS}

    def to_servo(self, joint_id, value):
        if self.INVERTED.get(joint_id):
            lo, hi =self.RANGES[joint_id]
            return lo+hi - int(value)
        return int(value)

    def limits(self, joint_id):
        return self.RANGES[joint_id]

    def clamp(self, jont_id, value):
        lo, hi = self.RANGES[jont_id]
        return max(lo, min(hi, int(float(value))))

    def get(self, joint_id):
        return self.vars[joint_id].get()

    def set(self, joint_id, value):
        value = self.clamp(joint_id,value)
        self.vars[joint_id].set(value)
        return value
