"""robotic_arm_app.py - controller: wires the panels, state, visualizer, and connection together."""

import queue
import tkinter as tk

from theme import BG_DARK, setup_styles
from arm_state import ArmState
from connection_manager import ConnectionManager
from header_bar import HeaderBar
from connection_bar import ConnectionBar
from joints_panel import JointsPanel
from side_panel import SidePanel
from status_bar import StatusBar
from servo_easer import ServoEaser


class RoboticArmApp:
    # "RESET ALL JOINTS" moves to this pose (the old fold / rest pose)
    RESET_POSE = (45, 135, 90, 0)        # shoulder, elbow, claw, base (degrees)

    def __init__(self, root):
        self.root = root
        self.root.title("ESP32 Robotic Arm Control Station")
        self.root.geometry("1100x760")
        self.root.minsize(980, 700)
        self.root.configure(bg=BG_DARK)

        # Thread-safe UI event queue
        self.ui_queue = queue.Queue()
        self._suppress = False

        # Base rotation jog state
        self.jog_speed = 200
        self.active_jog_dir = 0
        self.jog_anim_id = None
        self.jog_keepalive_id = None

        self.state = ArmState()
        setup_styles()

        self.comm = ConnectionManager(
            log_callback=self.append_log,
            status_callback=self.update_status,
            disconnect_callback=lambda: self.ui_queue.put(self.conn_bar.show_disconnected),
        )

        # Smooth acceleration / deceleration for shoulder, elbow and claw
        self.easer = ServoEaser(
            root=self.root, state=self.state,
            send_servo=self._send_servo, on_update=self._on_motion_update,
        )

        self._build_ui()

        self.root.after(50, self._drain_ui_queue)
        self.root.after(100, self.side_panel.visualizer.redraw)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ---------- Layout ----------
    def _build_ui(self):
        HeaderBar(self.root).pack(fill="x", padx=18)

        self.conn_bar = ConnectionBar(
            self.root, self.comm, self.ui_queue,
            status_callback=self.update_status,
            on_connected=self.sync_initial_positions,
        )
        self.conn_bar.pack(fill="x", padx=18, pady=(0, 10))

        self.status_bar = StatusBar(self.root)
        self.status_bar.pack(fill="x", side="bottom")

        main_split = tk.Frame(self.root, bg=BG_DARK)
        main_split.pack(fill="both", expand=True, padx=18, pady=(0, 6))

        self.joints_panel = JointsPanel(
            main_split, self.state,
            on_slider=self.on_slider_moved,
            on_step=self.step_joint,
            on_set=self.set_joint_val,
            on_jog_base=self.start_jog_base,
            on_stop_base=self.stop_jog_base,
            on_nudge_base=self.nudge_base,
            on_speed_change=self.set_base_speed,
        )
        self.joints_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.side_panel = SidePanel(
            main_split, self.state,
            on_reset=self.reset_all_controls,
            on_stop_base=self.stop_jog_base,
        )
        self.side_panel.pack(side="right", fill="both")

    # ---------- Thread-Safe Helpers ----------
    def _drain_ui_queue(self):
        try:
            while True:
                self.ui_queue.get_nowait()()
        except queue.Empty:
            pass
        self.root.after(50, self._drain_ui_queue)

    def update_status(self, text, color):
        self.ui_queue.put(lambda: self.status_bar.set(text, color))

    def append_log(self, text):
        self.ui_queue.put(lambda: self.side_panel.log.append(text))

    # ---------- Joint & Servo Control ----------
    def sync_initial_positions(self):
        """Sends current GUI joint values to ESP32 upon connection."""
        self.easer.sync_all()
        self.comm.send("STOP4")
        self.append_log("[SYNC] Initialized positional servos 1-3 & halted Base motor.")

    def _send_servo(self, joint_id, servo_angle, log):
        """Called by the easer for every smoothed step (only the last one is logged)."""
        self.comm.send(f"S{joint_id},{servo_angle}", log=log)

    def _on_motion_update(self):
        """After every easing step: keep the angle badges and the 2D arm in sync."""
        for j in ServoEaser.JOINTS:
            self.joints_panel.update_badge(j, round(self.state.shown(j)))
        self.side_panel.visualizer.redraw()

    def on_slider_moved(self, joint_id, value):
        if self._suppress:
            return
        self.easer.set_target(joint_id, int(float(value)))

    def step_joint(self, joint_id, delta):
        self.set_joint_val(joint_id, self.state.get(joint_id) + delta)

    def set_joint_val(self, joint_id, value):
        value = self.state.clamp(joint_id, value)

        self._suppress = True
        try:
            self.state.set(joint_id, value)
        finally:
            self._suppress = False

        if joint_id in ServoEaser.JOINTS:
            self.easer.set_target(joint_id, value)

    # ---------- Base Continuous Rotation Control (Matches HTML) ----------
    def start_jog_base(self, direction):
        """Hold-to-jog: rotates base continuous motor and smoothly turns visualizer arrow."""
        if self.active_jog_dir == direction:
            return
        self.active_jog_dir = direction
        dir_str = "CW" if direction > 0 else "CCW"
        badge_text = "ROTATING CW ▶" if direction > 0 else "◀ ROTATING CCW"
        self.joints_panel.update_badge(4, badge_text, is_active=True)

        # Send jog command
        self.comm.send(f"J4,{dir_str},{self.jog_speed}")

        # Start visualizer arrow rotation animation
        self._cancel_jog_timers()
        self._jog_step_anim()

        # Send keepalive pulse every 500ms while held
        self._schedule_jog_keepalive(dir_str)

    def _jog_step_anim(self):
        if self.active_jog_dir == 0:
            return
        delta = 3 if self.active_jog_dir > 0 else -3
        new_angle = self.state.get(4) + delta
        self.state.set(4, new_angle)
        self.side_panel.visualizer.redraw()
        self.jog_anim_id = self.root.after(45, self._jog_step_anim)

    def _schedule_jog_keepalive(self, dir_str):
        if self.active_jog_dir == 0:
            return
        self.comm.send(f"J4,{dir_str},{self.jog_speed}")
        self.jog_keepalive_id = self.root.after(500, lambda: self._schedule_jog_keepalive(dir_str))

    def stop_jog_base(self):
        """Halts base continuous rotation."""
        self._cancel_jog_timers()
        self.active_jog_dir = 0
        self.comm.send("STOP4")
        self.joints_panel.update_badge(4, "STOPPED", is_active=False)
        self.side_panel.visualizer.redraw()

    def _cancel_jog_timers(self):
        if self.jog_anim_id:
            self.root.after_cancel(self.jog_anim_id)
            self.jog_anim_id = None
        if self.jog_keepalive_id:
            self.root.after_cancel(self.jog_keepalive_id)
            self.jog_keepalive_id = None

    def nudge_base(self, direction, ms):
        """Timed nudge / step for precision positioning."""
        dir_str = "CW" if direction > 0 else "CCW"
        self.comm.send(f"STEP4,{dir_str},{ms}")

        angle_delta = (14 if ms >= 150 else 6) * (1 if direction > 0 else -1)
        self.state.set(4, self.state.get(4) + angle_delta)
        self.joints_panel.update_badge(4, f"{dir_str} ({ms}ms)", is_active=True)
        self.side_panel.visualizer.redraw()

        self.root.after(ms + 60, lambda: self.joints_panel.update_badge(4, "STOPPED", is_active=False))

    def set_base_speed(self, speed):
        self.jog_speed = speed
        self.joints_panel.set_active_speed(speed)
        self.append_log(f"[BASE] Jog speed offset set to {speed} us.")

    # ---------- Global Pose Controls ----------
    def reset_all_controls(self):
        """RESET ALL JOINTS = glide to the fold / rest pose (RESET_POSE)."""
        s1, s2, s3, s4 = self.RESET_POSE
        self.apply_preset(s1, s2, s3, s4)
        self.append_log(f"[RESET] Fold/rest pose: shoulder {s1}°, elbow {s2}°, "
                        f"claw {s3}°, base heading {s4}°.")

    def apply_preset(self, s1, s2, s3, s4):
        self.stop_jog_base()
        self.state.set(4, s4)
        self.set_joint_val(1, s1)
        self.set_joint_val(2, s2)
        self.set_joint_val(3, s3)
        self.joints_panel.update_badge(4, "STOPPED", is_active=False)
        self.side_panel.visualizer.redraw()

    def on_closing(self):
        try:
            self.stop_jog_base()
            self.comm.disconnect()
        except Exception:
            pass
        self.root.destroy()
