"""Gesture classifier + controller tests using synthetic hands."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from robot_server.config import DEFAULTS  # noqa: E402
from robot_server.gestures import classifier as g  # noqa: E402
from robot_server.gestures.controller import GestureController  # noqa: E402

ASPECT = 1.6
MCP = {1: (-0.25, 0.9), 2: (0.0, 1.0), 3: (0.22, 0.95), 4: (0.4, 0.82)}  # index..pinky knuckles


def make_hand(fingers, angle_deg=0.0, thumb=False, cx=0.5, cy=0.55, scale=0.15):
    """Upright hand (fingers up) in local units, rotated counter-clockwise by angle_deg
    as seen in the image. fingers = [index, middle, ring, pinky] extended flags."""
    pts = {0: (0.0, 0.0)}
    # thumb 1-4
    pts[1] = (-0.3, 0.25)
    pts[2] = (-0.5, 0.45)
    if thumb:
        pts[3], pts[4] = (-0.8, 0.55), (-1.05, 0.62)
    else:
        pts[3], pts[4] = (-0.4, 0.6), (-0.2, 0.7)
    for f, ext in enumerate(fingers, start=1):
        mx, my = MCP[f]
        base = 1 + 4 * f  # 5, 9, 13, 17
        pts[base] = (mx, my)
        if ext:
            pts[base + 1], pts[base + 2], pts[base + 3] = (mx, my + 0.35), (mx, my + 0.6), (mx, my + 0.8)
        else:
            pts[base + 1], pts[base + 2], pts[base + 3] = (mx, my + 0.28), (mx, my + 0.12), (mx, my - 0.05)
    a = math.radians(angle_deg)
    out = []
    for i in range(21):
        x, y = pts[i]
        rx, ry = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
        out.append((cx + rx * scale / ASPECT, cy - ry * scale))  # image y grows downward
    return out


def test_basic_poses():
    assert g.classify(make_hand([1, 1, 1, 1], thumb=True)) == g.OPEN_PALM
    assert g.classify(make_hand([0, 0, 0, 0])) == g.FIST
    assert g.classify(make_hand([1, 1, 0, 0])) == g.PEACE
    assert g.classify(make_hand([1, 0, 0, 0])) == g.POINT_UP


def test_directions_follow_the_image():
    # rotate 90 deg counter-clockwise: fingers point to the image's left
    assert g.classify(make_hand([1, 0, 0, 0], angle_deg=90)) == g.POINT_LEFT
    assert g.classify(make_hand([1, 0, 0, 0], angle_deg=-90)) == g.POINT_RIGHT
    assert g.classify(make_hand([1, 1, 0, 0], angle_deg=90)) == g.TWO_LEFT
    assert g.classify(make_hand([1, 1, 0, 0], angle_deg=-90)) == g.TWO_RIGHT
    # mirror flag swaps left/right
    assert g.classify(make_hand([1, 0, 0, 0], angle_deg=90), mirror=True) == g.POINT_RIGHT


def test_thumbs():
    # thumb points left in the local frame; rotate -90 (clockwise) -> up, +90 -> down
    assert g.classify(make_hand([0, 0, 0, 0], angle_deg=-90, thumb=True)) == g.THUMBS_UP
    assert g.classify(make_hand([0, 0, 0, 0], angle_deg=90, thumb=True)) == g.THUMBS_DOWN


def cfg():
    return dict(DEFAULTS["gestures"])


def run(ctrl, hand, frames, t0, dt=0.1):
    out = None
    for i in range(frames):
        out = ctrl.update(hand, now=t0 + i * dt)
    return out, t0 + frames * dt


def test_command_needs_confirmation_but_stop_is_instant():
    c = GestureController(cfg())
    up = make_hand([0, 0, 0, 0], angle_deg=-90, thumb=True)
    assert c.update(up, now=0.0) == (0.0, 0.0, 0.0)          # 1st frame: confirming
    out, t = run(c, up, 3, 0.1)
    assert out == (1.0, 0.0, 0.0) and c.action == "forward"
    assert c.update(make_hand([1, 1, 1, 1], thumb=True), now=t) == (0.0, 0.0, 0.0)  # palm: instant stop
    out, t = run(c, up, 3, t + 0.1)
    assert out[0] == 1.0
    assert c.update(None, now=t) == (0.0, 0.0, 0.0) and c.action == "no_hand"  # lost: instant stop


def test_turn_and_strafe_signs():
    c = GestureController(cfg())
    out, _ = run(c, make_hand([1, 0, 0, 0], angle_deg=90), 4, 0.0)
    assert out == (0.0, 0.0, 1.0)      # point to image-left -> turn left (ccw)
    c = GestureController(cfg())
    out, _ = run(c, make_hand([1, 1, 0, 0], angle_deg=-90), 4, 0.0)
    assert out == (0.0, -1.0, 0.0)     # two fingers to image-right -> strafe right


def test_follow_mode_enter_track_exit():
    c = GestureController(cfg())
    peace = make_hand([1, 1, 0, 0])
    _, t = run(c, peace, 12, 0.0)     # 1.2 s hold
    assert c.mode == "follow" and "follow_on" in c.events
    palm = make_hand([1, 1, 1, 1], thumb=True, scale=0.15)
    _, t = run(c, palm, 6, t)         # locks target size
    assert c.action in ("holding", "following")
    # hand moves to the image's right -> turn clockwise
    vx, vy, wz = c.update(make_hand([1, 1, 1, 1], thumb=True, cx=0.8), now=t)
    assert wz < 0 and vy == 0
    # hand gets smaller (farther away) -> drive forward
    vx, _, _ = c.update(make_hand([1, 1, 1, 1], thumb=True, scale=0.10), now=t + 0.1)
    assert vx > 0
    # hand gets bigger (too close) -> back up
    vx, _, _ = c.update(make_hand([1, 1, 1, 1], thumb=True, scale=0.22), now=t + 0.2)
    assert vx < 0
    # fist held 1 s -> back to command mode
    _, t = run(c, make_hand([0, 0, 0, 0]), 12, t + 0.3)
    assert c.mode == "command" and "follow_off" in c.events


def test_follow_mode_times_out_without_hand():
    c = GestureController(cfg())
    run(c, make_hand([1, 1, 0, 0]), 12, 0.0)
    assert c.mode == "follow"
    run(c, None, 60, 2.0)  # 6 s without a hand
    assert c.mode == "command"
