"""joints_panel.py - left column holding the four JointCards."""

import tkinter as tk
from theme import BG_DARK
from joint_card import JointCard


class JointsPanel(tk.Frame):
    # Display order: Base, Shoulder, Elbow, Claw
    CARD_SPECS = [
        dict(joint_id=4, title="BASE ROTATION (MG90S Continuous)",
             subtitle="Timed Position Tracking & Continuous Yaw Rotation",
             left_text="↺ ◀ CCW", right_text="CW ▶ ↻", has_stop_base=True),
        dict(joint_id=1, title="SHOULDER JOINT (SG90 180°)",
             subtitle="Main Arm Pitch Elevation",
             left_text="▼ LOWER", right_text="RAISE ▲", show_angle=False),
        dict(joint_id=2, title="ELBOW JOINT (SG90 180°)",
             subtitle="Forearm Extension & Pitch Angle",
             left_text="↶ RETRACT", right_text="EXTEND ↷", show_angle=False),
        dict(joint_id=3, title="CLAW / GRIPPER (SG90 180°)",
             subtitle="Pincer End-Effector Mechanism",
             left_text="◄ OPEN 🔓", right_text="GRIP 🔒 ►", has_claw_actions=True),
    ]

    def __init__(self, parent, state, on_slider, on_step, on_set, on_stop_base):
        super().__init__(parent, bg=BG_DARK)
        self.cards = {}
        for spec in self.CARD_SPECS:
            card = JointCard(
                self, variable=state.vars[spec["joint_id"]],
                on_slider=on_slider, on_step=on_step, on_set=on_set,
                on_stop_base=on_stop_base, **spec,
            )
            card.pack(fill="x", pady=3)
            self.cards[spec["joint_id"]] = card

    def update_badge(self, joint_id, value):
        self.cards[joint_id].update_badge(value)
