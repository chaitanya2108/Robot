"""Turns a stream of hand landmarks into robot commands.

Two modes:
  command  Fixed poses map to motions (see ACTIONS). A pose must be seen for
           `confirm_frames` frames in a row before it moves the robot; stop
           poses and losing the hand act immediately.
  follow   The robot turns to keep your hand centred and drives to keep the
           hand the same size it was when follow mode started (= same distance).
           Hold a fist for `hold_seconds` to leave follow mode.

Peace sign held for `hold_seconds` enters follow mode.
Output commands are normalised (-1..1): vx forward, vy left, wz counter-clockwise.
"""
import time

from . import classifier as g

ACTIONS = {
    g.OPEN_PALM: ("stop", (0.0, 0.0, 0.0)),
    g.FIST: ("stop", (0.0, 0.0, 0.0)),
    g.THUMBS_UP: ("forward", (1.0, 0.0, 0.0)),
    g.THUMBS_DOWN: ("backward", (-1.0, 0.0, 0.0)),
    g.POINT_LEFT: ("turn_left", (0.0, 0.0, 1.0)),
    g.POINT_RIGHT: ("turn_right", (0.0, 0.0, -1.0)),
    g.TWO_LEFT: ("strafe_left", (0.0, 1.0, 0.0)),
    g.TWO_RIGHT: ("strafe_right", (0.0, -1.0, 0.0)),
}
STOP = (0.0, 0.0, 0.0)


def _clamp(v, lim=1.0):
    return max(-lim, min(lim, v))


class GestureController(object):
    def __init__(self, cfg, aspect=1.6):
        self.cfg = cfg
        self.aspect = aspect
        self.mode = "command"
        self.gesture = g.NONE
        self.action = "idle"
        self._streak_gesture = None
        self._streak = 0
        self._hold_gesture = None
        self._hold_since = None
        self._lost_since = None
        self._target_size = None
        self._size_samples = []
        self.events = []  # e.g. "follow_on", "follow_off" (consumed by the service)

    def reset(self):
        self.__init__(self.cfg, self.aspect)

    # ---- helpers --------------------------------------------------------------
    def _held(self, gesture, now):
        """True once `gesture` has been continuously visible for hold_seconds."""
        if self._hold_gesture != gesture:
            self._hold_gesture, self._hold_since = gesture, now
            return False
        return now - self._hold_since >= self.cfg["hold_seconds"]

    def _enter_follow(self):
        self.mode = "follow"
        self._target_size = None
        self._size_samples = []
        self._hold_gesture = None
        self.events.append("follow_on")

    def _exit_follow(self):
        self.mode = "command"
        self._hold_gesture = None
        self.events.append("follow_off")

    # ---- main -----------------------------------------------------------------
    def update(self, landmarks, now=None):
        """Feed one frame's landmarks (or None). Returns (vx, vy, wz)."""
        now = time.monotonic() if now is None else now
        if not landmarks:
            self.gesture = g.NONE
            self._streak_gesture, self._streak = None, 0
            self._hold_gesture = None
            if self._lost_since is None:
                self._lost_since = now
            if self.mode == "follow" and now - self._lost_since > self.cfg["follow_lost_timeout"]:
                self._exit_follow()
            self.action = "no_hand"
            return STOP
        self._lost_since = None

        gesture = g.classify(landmarks, self.aspect, self.cfg.get("mirror", False))
        self.gesture = gesture
        if gesture == self._streak_gesture:
            self._streak += 1
        else:
            self._streak_gesture, self._streak = gesture, 1

        if self.mode == "follow":
            return self._follow(landmarks, gesture, now)
        return self._command(gesture, now)

    def _command(self, gesture, now):
        if gesture == g.PEACE:
            if self._held(g.PEACE, now):
                self._enter_follow()
                self.action = "follow"
            else:
                self.action = "hold_for_follow"
            return STOP
        self._hold_gesture = None
        action = ACTIONS.get(gesture)
        if action is None:
            self.action = "stop"
            return STOP
        name, cmd = action
        if name == "stop":  # safety: act on the first frame
            self.action = "stop"
            return STOP
        if self._streak < self.cfg["confirm_frames"]:
            self.action = "confirming"
            return STOP
        self.action = name
        return cmd

    def _follow(self, lm, gesture, now):
        if gesture == g.FIST:
            if self._held(g.FIST, now):
                self._exit_follow()
            self.action = "stop"
            return STOP
        self._hold_gesture = None
        size = g.palm_size(lm, self.aspect)
        cx, _ = g.palm_center(lm)
        if self.cfg.get("mirror"):
            cx = 1.0 - cx
        if self._target_size is None:
            self._size_samples.append(size)
            if len(self._size_samples) < 5:
                self.action = "locking_distance"
                return STOP
            self._target_size = sorted(self._size_samples)[2]
        # Turn toward the hand: hand on the image's right (cx > 0.5) -> turn clockwise (wz < 0)
        err_x = cx - 0.5
        wz = 0.0 if abs(err_x) < self.cfg["follow_center_deadband"] else -self.cfg["follow_turn_gain"] * err_x * 2.0
        # Keep distance: hand smaller than target -> it's farther -> drive forward
        err_d = (self._target_size - size) / self._target_size
        vx = 0.0 if abs(err_d) < self.cfg["follow_distance_deadband"] else self.cfg["follow_distance_gain"] * err_d
        vx, wz = _clamp(vx), _clamp(wz)
        self.action = "following" if (vx or wz) else "holding"
        return (vx, 0.0, wz)

    def status(self):
        return {"mode": self.mode, "gesture": self.gesture, "action": self.action}
