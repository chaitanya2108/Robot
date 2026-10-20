"""Configuration loading.

Config lives in ~/robot_app/config.yaml on the robot. Missing keys fall back to
DEFAULTS. The access token is generated on first run if it is empty.
"""
import copy
import os
import secrets

import yaml

DEFAULT_PATH = os.path.expanduser("~/robot_app/config.yaml")

DEFAULTS = {
    "server": {
        "host": "0.0.0.0",
        "port": 8765,
        "name": "ROSOrin",
    },
    "auth": {
        # Shared secret the phone app must present. Generated on first run.
        "token": "",
    },
    "board": {
        "device": "/dev/rrc",
        "baudrate": 1000000,
    },
    "chassis": {
        # Geometry from the original Hiwonder controller (metres)
        "wheelbase": 0.17706,
        "track_width": 0.17165,
        "wheel_diameter": 0.08,
        "linear_correction": 1.0,
        "angular_correction": 1.02,
        # Hard limits enforced on the robot, whatever the app sends
        "max_linear": 0.35,   # m/s
        "max_angular": 1.5,   # rad/s
        "max_linear_accel": 1.2,   # m/s^2
        "max_angular_accel": 5.0,  # rad/s^2
        # Flip these if a direction is reversed on your robot
        "invert_x": False,
        "invert_y": False,
        "invert_rotation": False,
    },
    "safety": {
        # Stop the motors if no drive command arrives for this long (seconds)
        "command_timeout": 0.4,
        "control_rate_hz": 50,
    },
    "camera": {
        "enabled": True,
        "bridge": os.path.expanduser("~/robot_app/server/camera_bridge/build/camera_bridge"),
        "mode": 2,        # 0=320x200, 1=480x300, 2=640x400
        "quality": 70,    # JPEG quality
        "fps": 15,
        "width": 0,       # 0 = native width
        "idle_stop_seconds": 15,  # stop the camera when nobody watches
    },
    "audio": {
        "enabled": True,
        "sounds_dir": os.path.expanduser("~/robot_app/vendor/audio/sounds/english"),
        "fallback_sounds_dir": os.path.expanduser("~/robot_app/vendor/audio/sounds"),
        "player": "aplay",
    },
    "buttons": {
        # Physical buttons on the expansion board (Jetson GPIO, BCM numbering)
        "enabled": True,
        "wifi_reset_pin": 25,   # short press: go back to hotspot mode
        "shutdown_pin": 4,      # hold ~1.5 s: shut the robot down
    },
    "gestures": {
        "enabled": True,
        "speed": 0.5,            # fraction of chassis max speed in command mode
        "follow_speed": 0.5,     # fraction of chassis max speed in follow mode
        "confirm_frames": 3,     # a moving pose must be seen this many frames in a row
        "hold_seconds": 1.0,     # peace sign / fist hold time to enter / leave follow mode
        "follow_lost_timeout": 5.0,  # leave follow mode if the hand is gone this long
        "follow_turn_gain": 1.2,
        "follow_distance_gain": 2.5,
        "follow_center_deadband": 0.06,
        "follow_distance_deadband": 0.12,
        "mirror": False,         # set true if the camera image is mirrored
        # MediaPipe's GPU build needs the robot's desktop (X) session
        "display": ":0",
        "xauthority": "~/.Xauthority",
    },
    "battery": {
        # 3S pack: used for the percentage estimate only
        "empty_mv": 10000,
        "full_mv": 12400,
        "low_warn_mv": 10500,
    },
}


def _merge(base, override):
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load(path=None):
    path = path or os.environ.get("ROBOT_CONFIG", DEFAULT_PATH)
    user = {}
    if os.path.exists(path):
        with open(path) as fh:
            user = yaml.safe_load(fh) or {}
    cfg = _merge(DEFAULTS, user)
    if not cfg["auth"]["token"]:
        cfg["auth"]["token"] = secrets.token_urlsafe(24)
        user.setdefault("auth", {})["token"] = cfg["auth"]["token"]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            yaml.safe_dump(user, fh, default_flow_style=False)
        os.chmod(path, 0o600)
    cfg["_path"] = path
    return cfg
