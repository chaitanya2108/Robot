"""Mecanum wheel inverse kinematics.

Conventions (same as ROS / the original Hiwonder controller):
    vx  forward  (m/s)
    vy  left     (m/s)
    wz  counter-clockwise (rad/s)

Wheel layout, seen from above, front at the top:

        motor1 |  ^  | motor3
               |     |
        motor2 |     | motor4

The sign pattern matches Hiwonder's MecanumChassis.set_velocity so the motor
board receives exactly what it received before.
"""
import math


class Mecanum(object):
    def __init__(self, wheelbase, track_width, wheel_diameter,
                 linear_correction=1.0, angular_correction=1.0):
        self.half_sum = (wheelbase + track_width) / 2.0
        self.wheel_circumference = math.pi * wheel_diameter
        self.linear_correction = linear_correction
        self.angular_correction = angular_correction

    def wheel_rps(self, vx, vy, wz):
        """Return [(motor_id, rps), ...] for motors 1-4."""
        vx *= self.linear_correction
        vy *= self.linear_correction
        vp = wz * self.angular_correction * self.half_sum
        v1 = vx - vy - vp
        v2 = vx + vy - vp
        v3 = -vx - vy - vp
        v4 = -vx + vy - vp
        return [(i + 1, v / self.wheel_circumference) for i, v in enumerate((v1, v2, v3, v4))]


def clamp(value, low, high):
    return max(low, min(high, value))


def approach(current, target, max_step):
    """Move current toward target by at most max_step."""
    if target > current:
        return min(target, current + max_step)
    return max(target, current - max_step)
