import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from robot_server.board import FakeBoard  # noqa: E402
from robot_server.config import DEFAULTS  # noqa: E402
from robot_server.drive import DriveController  # noqa: E402
from robot_server.kinematics import Mecanum  # noqa: E402


def hiwonder_reference(vx, vy, wz, wheelbase, track, diameter):
    """Straight port of Hiwonder's MecanumChassis.set_velocity + cmd_vel_callback."""
    speed = math.sqrt(vx ** 2 + vy ** 2)
    direction = math.atan2(vx, vy)
    direction = math.pi * 2 + direction if direction < 0 else direction
    x = speed * math.sin(direction)
    y = speed * math.cos(direction)
    vp = wz * (wheelbase + track) / 2
    v = [x - y - vp, x + y - vp, -x - y - vp, -x + y - vp]
    return [s / (math.pi * diameter) for s in v]


def test_matches_hiwonder_formula():
    c = DEFAULTS["chassis"]
    kin = Mecanum(c["wheelbase"], c["track_width"], c["wheel_diameter"])
    for vx, vy, wz in [(0.2, 0, 0), (0, 0.2, 0), (0, 0, 1.0), (0.1, -0.15, 0.5), (-0.3, 0.1, -0.8)]:
        ours = [rps for _, rps in kin.wheel_rps(vx, vy, wz)]
        ref = hiwonder_reference(vx, vy, wz, c["wheelbase"], c["track_width"], c["wheel_diameter"])
        assert all(abs(a - b) < 1e-9 for a, b in zip(ours, ref)), (ours, ref)


def make_drive():
    board = FakeBoard()
    return board, DriveController(board, dict(DEFAULTS["chassis"]), DEFAULTS["safety"])


def test_only_driver_can_drive_and_limits_apply():
    board, d = make_drive()
    assert d.claim(1)
    assert not d.claim(2)
    assert not d.command(2, 1, 0, 0)
    assert d.command(1, 5, 0, 0, speed=0.5)  # clamps to 1.0 * max * 0.5
    assert abs(d.target[0] - DEFAULTS["chassis"]["max_linear"] * 0.5) < 1e-9


def test_ramp_and_watchdog():
    board, d = make_drive()
    d.claim(1)
    d.command(1, 1, 0, 0)
    t0 = d.last_command
    lin_step, ang_step = 0.02, 0.1
    d.tick(lin_step, ang_step, now=t0 + 0.01)
    assert abs(d.current[0] - 0.02) < 1e-9  # ramped, not jumped
    assert any(abs(r) > 0 for _, r in board.last_wheels)
    # no new command for longer than the timeout -> target zero, ramps down to a stop
    for i in range(100):
        d.tick(lin_step, ang_step, now=t0 + 1.0 + i * 0.02)
    assert d.current == (0.0, 0.0, 0.0)
    assert all(r == 0 for _, r in board.last_wheels)


def test_estop_latches():
    board, d = make_drive()
    d.claim(1)
    d.set_estop(True)
    assert not d.command(1, 1, 0, 0)
    d.set_estop(False)
    assert d.command(1, 1, 0, 0)


def test_release_on_disconnect_frees_control():
    board, d = make_drive()
    d.claim(1)
    d.release(1)
    assert d.claim(2)
