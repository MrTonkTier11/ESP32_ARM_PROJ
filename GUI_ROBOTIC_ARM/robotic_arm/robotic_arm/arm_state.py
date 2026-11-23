"""arm_state.py - single source of truth for the joint angles."""

import tkinter as tk


class ArmState:
    """Holds the 4 joint angles. No drawing, no networking."""

    JOINTS = (1, 2, 3, 4)          # 1 Shoulder, 2 Elbow, 3 Claw, 4 Base
    NAMES = {1: "Shoulder", 2: "Elbow", 3: "Claw", 4: "Base"}
    DEFAULTS = {1: 90, 2: 90, 3: 90, 4: 0}
    INVERTED = {3: True}

    RANGES = {
        1: (0, 180),
        2: (0, 180),
        3: (0, 180),
        4: (-180, 180),
    }

    def __init__(self):
        self.vars = {j: tk.IntVar(value=self.DEFAULTS[j]) for j in self.JOINTS}
        # Where each joint REALLY is right now. It glides toward the slider value
        # (the target) - see servo_easer.py. Same units as the slider.
        self.current = {j: float(self.DEFAULTS[j]) for j in self.JOINTS}

    def shown(self, joint_id):
        """Position to draw: eased position for joints 1-3, heading for the base."""
        if joint_id == 4:
            return self.get(4)
        return self.current[joint_id]

    def to_servo(self, joint_id, value):
        val = int(round(float(value)))
        if self.INVERTED.get(joint_id):
            lo, hi = self.RANGES[joint_id]
            return lo + hi - val
        return val

    def limits(self, joint_id):
        return self.RANGES[joint_id]

    def clamp(self, joint_id, value):
        val = int(round(float(value)))
        if joint_id == 4:
            # Wrap around 360° continuously (-180° to +180°)
            return ((val + 180) % 360) - 180
        lo, hi = self.RANGES[joint_id]
        return max(lo, min(hi, val))

    def get(self, joint_id):
        return self.vars[joint_id].get()

    def set(self, joint_id, value):
        value = self.clamp(joint_id, value)
        self.vars[joint_id].set(value)
        return value
