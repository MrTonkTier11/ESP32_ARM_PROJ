"""servo_easer.py - smooth acceleration / deceleration (servo easing) for the arm joints."""

import math
import time


class ServoEaser:
    """Moves the shoulder, elbow and claw toward their targets gently.

    Sliders and buttons only set a TARGET. Every tick this class moves the real
    position a little closer: it speeds up gradually, cruises at a capped speed,
    and slows down before the target, so the arm never starts or stops with a jerk.
    Each new servo angle is sent to the ESP32 as it is reached.
    """

    JOINTS = (1, 2, 3)            # shoulder, elbow, claw (the base is speed-controlled)
    TICK_MS = 20                  # 50 updates per second

    # ---- tune the feel here ---------------------------------------------------
    MAX_SPEED = {1: 40.0, 2: 40.0, 3: 90.0}    # degrees / second   (lower = slower arm)
    ACCEL = {1: 80.0, 2: 80.0, 3: 240.0}       # degrees / second^2 (lower = softer start/stop)
    # ---------------------------------------------------------------------------

    def __init__(self, root, state, send_servo, on_update):
        self.root = root
        self.state = state
        self.send_servo = send_servo      # (joint_id, servo_angle, log)
        self.on_update = on_update        # called after every step (redraw, badges)

        self.targets = {j: float(state.current[j]) for j in self.JOINTS}
        self.velocity = {j: 0.0 for j in self.JOINTS}
        self._last_sent = {j: None for j in self.JOINTS}
        self._resend = set()          # joints that must be sent once, even if already there
        self._job = None
        self._last_time = 0.0

    # ---------- public ----------
    def set_target(self, joint_id, value):
        """Ask a joint to move (smoothly) to `value` (slider units)."""
        self.targets[joint_id] = float(value)
        self._resend.add(joint_id)    # always tell the ESP32 the final angle (it may have
        self._start()                 # been moved by the phone page or restarted)

    def sync_all(self):
        """Send every joint's current position (used right after connecting)."""
        for j in self.JOINTS:
            self._send(j, force=True)

    # ---------- internals ----------
    def _start(self):
        if self._job is None:
            self._last_time = time.monotonic()
            self._job = self.root.after(self.TICK_MS, self._tick)

    def _tick(self):
        now = time.monotonic()
        dt = min(now - self._last_time, 0.1)      # never take a giant step after a stall
        self._last_time = now

        busy = False
        for j in self.JOINTS:
            if self._step_joint(j, dt):
                busy = True
        self.on_update()

        self._job = self.root.after(self.TICK_MS, self._tick) if busy else None

    def _step_joint(self, j, dt):
        """Advance one joint. Returns True while it is still moving."""
        cur = self.state.current[j]
        tgt = self.targets[j]
        vel = self.velocity[j]
        dist = tgt - cur
        if dist == 0 and vel == 0:
            if j in self._resend:         # asked to move but already there
                self._resend.discard(j)
                self._send(j, final=True)
            return False

        accel = self.ACCEL[j]
        direction = 1.0 if dist > 0 else -1.0

        # Fastest speed from which we can still stop exactly at the target.
        brake_speed = math.sqrt(2.0 * accel * abs(dist))
        wanted = direction * min(self.MAX_SPEED[j], brake_speed)

        # Change speed gradually (this is the smooth acceleration).
        max_dv = accel * dt
        vel += max(-max_dv, min(max_dv, wanted - vel))
        new_cur = cur + vel * dt

        # Reached (or about to pass) the target: land exactly on it.
        arrived = (tgt - new_cur) * direction <= 0 or (abs(tgt - new_cur) < 0.05 and abs(vel) < 2.0)
        if arrived:
            new_cur, vel = tgt, 0.0
            self._resend.discard(j)

        self.velocity[j] = vel
        self.state.current[j] = new_cur
        self._send(j, final=arrived)
        return not arrived

    def _send(self, j, final=False, force=False):
        angle = self.state.to_servo(j, self.state.current[j])
        if final or force or angle != self._last_sent[j]:
            self._last_sent[j] = angle
            self.send_servo(j, angle, final or force)    # only the last step is logged
