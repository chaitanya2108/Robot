"""Drive controller: turns joystick commands into wheel speeds, safely.

Safety rules, all enforced on the robot:
  * Commands are normalised (-1..1) and scaled by the configured max speeds.
  * Acceleration is ramped so the robot never jerks.
  * If no command arrives within `command_timeout`, the target drops to zero.
  * Emergency stop latches until explicitly released.
  * Only one client (the "driver") may send drive commands at a time.
"""
import asyncio
import logging
import time

from .kinematics import Mecanum, approach, clamp

log = logging.getLogger("drive")


class DriveController(object):
    def __init__(self, board, chassis_cfg, safety_cfg):
        self.board = board
        self.cfg = chassis_cfg
        self.timeout = float(safety_cfg["command_timeout"])
        self.period = 1.0 / float(safety_cfg["control_rate_hz"])
        self.kin = Mecanum(
            chassis_cfg["wheelbase"], chassis_cfg["track_width"], chassis_cfg["wheel_diameter"],
            chassis_cfg["linear_correction"], chassis_cfg["angular_correction"],
        )
        self.target = (0.0, 0.0, 0.0)
        self.current = (0.0, 0.0, 0.0)
        self.last_command = 0.0
        self.estop = False
        self.driver_id = None
        self._task = None
        self._was_moving = False

    # ---- driver ownership -------------------------------------------------
    def claim(self, client_id):
        if self.driver_id is None or self.driver_id == client_id:
            self.driver_id = client_id
            return True
        return False

    def release(self, client_id):
        if self.driver_id == client_id:
            self.driver_id = None
            self.target = (0.0, 0.0, 0.0)

    # ---- commands ---------------------------------------------------------
    def command(self, client_id, vx, vy, wz, speed=1.0):
        """Normalised command from the joystick. Returns False if refused."""
        if client_id != self.driver_id or self.estop:
            return False
        speed = clamp(float(speed), 0.0, 1.0)
        c = self.cfg
        vx = clamp(float(vx), -1.0, 1.0) * c["max_linear"] * speed
        vy = clamp(float(vy), -1.0, 1.0) * c["max_linear"] * speed
        wz = clamp(float(wz), -1.0, 1.0) * c["max_angular"] * speed
        if c.get("invert_x"):
            vx = -vx
        if c.get("invert_y"):
            vy = -vy
        if c.get("invert_rotation"):
            wz = -wz
        self.target = (vx, vy, wz)
        self.last_command = time.monotonic()
        return True

    def stop(self):
        self.target = (0.0, 0.0, 0.0)

    def set_estop(self, on):
        self.estop = bool(on)
        if self.estop:
            self.target = (0.0, 0.0, 0.0)
            self.current = (0.0, 0.0, 0.0)
            self.board.stop_motors()
        log.warning("E-STOP %s", "ENGAGED" if self.estop else "released")

    # ---- control loop -----------------------------------------------------
    def start(self, loop):
        self._task = loop.create_task(self._run())

    async def _run(self):
        c = self.cfg
        lin_step = c["max_linear_accel"] * self.period
        ang_step = c["max_angular_accel"] * self.period
        while True:
            try:
                self.tick(lin_step, ang_step)
            except Exception:
                log.exception("control loop error")
                self.board.stop_motors()
            await asyncio.sleep(self.period)

    def tick(self, lin_step, ang_step, now=None):
        now = time.monotonic() if now is None else now
        if self.estop or (now - self.last_command) > self.timeout:
            self.target = (0.0, 0.0, 0.0)
        tx, ty, tw = self.target
        cx, cy, cw = self.current
        self.current = (approach(cx, tx, lin_step), approach(cy, ty, lin_step), approach(cw, tw, ang_step))
        moving = any(abs(v) > 1e-4 for v in self.current)
        if moving:
            self.board.set_wheels(self.kin.wheel_rps(*self.current))
        elif self._was_moving:
            self.current = (0.0, 0.0, 0.0)
            self.board.stop_motors()
        self._was_moving = moving

    def status(self):
        vx, vy, wz = self.current
        return {
            "vx": round(vx, 3), "vy": round(vy, 3), "wz": round(wz, 3),
            "moving": self._was_moving, "estop": self.estop,
            "has_driver": self.driver_id is not None,
        }

    async def shutdown(self):
        if self._task:
            self._task.cancel()
        self.board.stop_motors()
