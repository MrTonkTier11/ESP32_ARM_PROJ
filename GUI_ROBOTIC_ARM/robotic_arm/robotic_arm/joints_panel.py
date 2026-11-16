"""joints_panel.py - left column holding the four JointCards."""

import tkinter as tk
from theme import BG_DARK
from joint_card import JointCard


class JointsPanel(tk.Frame):
    # Display order: Base, Shoulder, Elbow, Claw
    CARD_SPECS = [
        dict(joint_id=4, title="BASE ROTATION (MG90S 360° Continuous)",
             subtitle="Directional Jog & Rotation Control",
             left_text="↺ ◀ CCW", right_text="CW ▶ ↻", has_stop_base=True),
        dict(joint_id=1, title="SHOULDER JOINT (SG90)",
             subtitle="Main Arm Pitch Elevation",
             left_text="▼ LOWER", right_text="RAISE ▲", show_angle=False),
        dict(joint_id=2, title="ELBOW JOINT (SG90)",
             subtitle="Forearm Extension & Pitch Angle",
             left_text="↶ RETRACT", right_text="EXTEND ↷", show_angle=False),
        dict(joint_id=3, title="CLAW / GRIPPER (SG90)",
             subtitle="Pincer End-Effector Mechanism",
             left_text="◄ GRIP 🔓", right_text="OPEN 🔒 ►", has_claw_actions=True),
    ]

    def __init__(self, parent, state, on_slider, on_step, on_set, on_stop_base):
        super().__init__(parent, bg=BG_DARK)
        self.cards = {}
        for spec in self.CARD_SPECS:
            lo, hi = state.limits(spec["joint_id"])
            extra = {}
            if spec.get("has_claw_actions"):
                extra = dict(open_value=state.to_servo(3,30), grip_value=state.to_servo(3, 150))
            card = JointCard(
                self, variable=state.vars[spec["joint_id"]], min_val=lo, max_val=hi,
                on_slider=on_slider, on_step=on_step, on_set=on_set,
                on_stop_base=on_stop_base, **extra, **spec,
            )
            card.pack(fill="x", pady=3)
            self.cards[spec["joint_id"]] = card

    def update_badge(self, joint_id, value):
        self.cards[joint_id].update_badge(value)
