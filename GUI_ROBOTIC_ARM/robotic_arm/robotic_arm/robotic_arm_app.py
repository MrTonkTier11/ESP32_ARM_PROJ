"""robotic_arm_app.py - controller: wires the panels, state and connection together."""

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


class RoboticArmApp:
    REST_POSE = (45, 135, 90, 90)      # shoulder, elbow, claw, base
    CENTER_POSE = (90, 90, 90, 90)
    SEND_DEBOUNCE_MS = 35

    def __init__(self, root):
        self.root = root
        self.root.title("ESP32 Robotic Arm Control Station")
        self.root.geometry("1100x740")
        self.root.minsize(980, 680)
        self.root.configure(bg=BG_DARK)

        # Thread-safe UI event queue (background threads post, main thread runs)
        self.ui_queue = queue.Queue()
        self._suppress = False
        self.pending_timers = {}

        self.state = ArmState()
        setup_styles()

        self.comm = ConnectionManager(
            log_callback=self.append_log,
            status_callback=self.update_status,
            disconnect_callback=lambda: self.ui_queue.put(self.conn_bar.show_disconnected),
        )

        self._build_ui()

        self.root.after(50, self._drain_ui_queue)
        self.root.after(100, self.side_panel.visualizer.redraw)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ---------- layout ----------
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
            on_slider=self.on_slider_moved, on_step=self.step_joint,
            on_set=self.set_joint_val, on_stop_base=self.stop_base,
        )
        self.joints_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.side_panel = SidePanel(
            main_split, self.state,
            on_rest=lambda: self.apply_preset(*self.REST_POSE),
            on_reset=self.reset_all_controls,
            on_stop_base=self.stop_base,
        )
        self.side_panel.pack(side="right", fill="both")

    # ---------- thread-safe helpers ----------
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

    # ---------- joint control ----------
    def sync_initial_positions(self):
        """Sends current GUI slider values to ESP32 upon connection."""
        for j in ArmState.JOINTS:
            self.comm.send(f"S{j},{self.state.get(j)}")

    def on_slider_moved(self, joint_id, value):
        if self._suppress:
            return
        val = int(float(value))
        self.joints_panel.update_badge(joint_id, val)
        self.side_panel.visualizer.redraw()

        # Debounce transmissions
        if joint_id in self.pending_timers:
            self.root.after_cancel(self.pending_timers[joint_id])
        self.pending_timers[joint_id] = self.root.after(
            self.SEND_DEBOUNCE_MS, lambda j=joint_id, v=val: self.send_joint_command(j, v)
        )

    def step_joint(self, joint_id, delta):
        self.set_joint_val(joint_id, self.state.get(joint_id) + delta)

    def set_joint_val(self, joint_id, value):
        value = self.state.clamp(value)

        # Cancel any pending debounced send so the command is not sent twice
        if joint_id in self.pending_timers:
            self.root.after_cancel(self.pending_timers.pop(joint_id))

        self._suppress = True
        try:
            self.state.set(joint_id, value)
        finally:
            self._suppress = False

        self.joints_panel.update_badge(joint_id, value)
        self.side_panel.visualizer.redraw()
        self.send_joint_command(joint_id, value)

    def send_joint_command(self, joint_id, value):
        self.pending_timers.pop(joint_id, None)
        self.comm.send(f"S{joint_id},{value}")

    def stop_base(self):
        self.comm.send("STOP4")
        self.append_log("[ACTION] STOP BASE triggered.")

    def reset_all_controls(self):
        self.apply_preset(*self.CENTER_POSE)
        self.comm.send("RESET")

    def apply_preset(self, s1, s2, s3, s4):
        self.set_joint_val(1, s1)
        self.set_joint_val(2, s2)
        self.set_joint_val(3, s3)
        self.set_joint_val(4, s4)

    def on_closing(self):
        try:
            self.comm.send("STOP4")
            self.comm.disconnect()
        except Exception:
            pass
        self.root.destroy()
