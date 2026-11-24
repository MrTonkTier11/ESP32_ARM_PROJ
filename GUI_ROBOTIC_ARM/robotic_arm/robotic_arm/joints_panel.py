"""joints_panel.py - left column holding the four JointCards (Base, Shoulder, Elbow, Claw)."""

import tkinter as tk
from theme import BG_DARK
from joint_card import JointCard


class JointsPanel(tk.Frame):
    # Display order: Base, Shoulder, Elbow, Claw
    CARD_SPECS = [
        dict(
            joint_id=4,
            card_type="base",
            title="↺ BASE ROTATION (MG90S 360°)",
            subtitle="Smooth Eased Continuous Jog · GPIO 21",
            left_text="ROTATE LEFT",
            right_text="ROTATE RIGHT",
            left_sub="HOLD CCW",
            right_sub="HOLD CW",
        ),
        dict(
            joint_id=1,
            card_type="two_button",
            title="▲ SHOULDER JOINT (SG90)",
            subtitle="Main Arm Pitch Elevation · GPIO 4",
            left_text="LOWER ARM",
            right_text="RAISE ARM",
            left_sub="DOWN",
            right_sub="UP",
        ),
        dict(
            joint_id=2,
            card_type="two_button",
            title="↶ ELBOW JOINT (SG90)",
            subtitle="Forearm Extension Pitch · GPIO 18",
            left_text="RETRACT",
            right_text="EXTEND",
            left_sub="BACK",
            right_sub="FWD",
        ),
        dict(
            joint_id=3,
            card_type="slider",
            title="🤏 CLAW / GRIPPER (SG90)",
            subtitle="Pincer End-Effector Grip · GPIO 19",
            left_text="◄ OPEN",
            right_text="GRIP ►",
            has_claw_actions=True,
        ),
    ]

    def __init__(self, parent, state, on_slider, on_step, on_set,
                 on_jog_base, on_stop_base):
        super().__init__(parent, bg=BG_DARK, width=340)
        self.pack_propagate(False)
        self.cards = {}

        for spec in self.CARD_SPECS:
            jid = spec["joint_id"]
            lo, hi = state.limits(jid)
            extra = {}
            if spec.get("has_claw_actions"):
                # Pass raw display values (not servo-inverted).
                # set_joint_val → state.set() stores these directly;
                # inversion only happens in to_servo() when sending the command.
                extra = dict(
                    open_value=30,   # slider value = claw fully open
                    grip_value=150   # slider value = claw fully gripped
                )

            card = JointCard(
                self,
                variable=state.vars[jid],
                min_val=lo,
                max_val=hi,
                on_slider=on_slider,
                on_step=on_step,
                on_set=on_set,
                on_jog_base=on_jog_base,
                on_stop_base=on_stop_base,
                **extra,
                **spec,
            )
            card.pack(fill="x", pady=2)
            self.cards[jid] = card

    def update_badge(self, joint_id, value, is_active=False):
        if joint_id in self.cards:
            self.cards[joint_id].update_badge(value, is_active=is_active)
