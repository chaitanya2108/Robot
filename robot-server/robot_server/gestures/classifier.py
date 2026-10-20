"""Classifies one hand pose from MediaPipe's 21 landmarks.

Landmarks are (x, y) normalised to the image (x right, y down). Indices:
    0 wrist | thumb 1-4 | index 5-8 | middle 9-12 | ring 13-16 | pinky 17-20

Directions are reported in IMAGE terms: "left" means toward the left edge of
the camera image, which is also the robot's left (the camera faces forward).
When you face the robot and point to YOUR right, your finger points to the
image's left, so the robot goes the way you point.
"""
import math

WRIST = 0
TIPS = (4, 8, 12, 16, 20)
PIPS = (2, 6, 10, 14, 18)
MCPS = (1, 5, 9, 13, 17)

# Gesture names
NONE = "none"
OPEN_PALM = "open_palm"
FIST = "fist"
THUMBS_UP = "thumbs_up"
THUMBS_DOWN = "thumbs_down"
POINT_LEFT = "point_left"
POINT_RIGHT = "point_right"
POINT_UP = "point_up"
TWO_LEFT = "two_left"
TWO_RIGHT = "two_right"
PEACE = "peace"
UNKNOWN = "unknown"


def _d(a, b, aspect):
    return math.hypot((a[0] - b[0]) * aspect, a[1] - b[1])


def palm_size(lm, aspect=1.6):
    """Wrist to middle-finger knuckle, in image-height units. Bigger = closer."""
    return _d(lm[WRIST], lm[9], aspect)


def palm_center(lm):
    pts = [lm[i] for i in (0, 5, 9, 13, 17)]
    return (sum(p[0] for p in pts) / 5.0, sum(p[1] for p in pts) / 5.0)


def fingers_extended(lm, aspect=1.6):
    """[thumb, index, middle, ring, pinky] booleans. Orientation independent."""
    w = lm[WRIST]
    size = palm_size(lm, aspect) or 1e-6
    out = []
    # Thumb: tip far from the index knuckle compared with the hand size
    out.append(_d(lm[4], lm[5], aspect) > 0.55 * size and _d(lm[4], w, aspect) > _d(lm[3], w, aspect))
    for tip, pip in zip(TIPS[1:], PIPS[1:]):
        out.append(_d(lm[tip], w, aspect) > 1.12 * _d(lm[pip], w, aspect))
    return out


def _direction(vec, aspect):
    """Classify a 2D image vector as 'left', 'right', 'up', 'down' or None (diagonal)."""
    dx, dy = vec[0] * aspect, vec[1]
    if abs(dx) > 1.3 * abs(dy):
        return "left" if dx < 0 else "right"
    if abs(dy) > 1.3 * abs(dx):
        return "up" if dy < 0 else "down"
    return None


def classify(lm, aspect=1.6, mirror=False):
    """Return one of the gesture names above."""
    if not lm or len(lm) != 21:
        return NONE
    if mirror:
        lm = [(1.0 - x, y) for x, y in lm]
    thumb, index, middle, ring, pinky = fingers_extended(lm, aspect)
    four = [index, middle, ring, pinky]

    if all(four):
        return OPEN_PALM
    if not any(four):
        if thumb:
            vec = (lm[4][0] - lm[2][0], lm[4][1] - lm[2][1])
            d = _direction(vec, aspect)
            if d == "up":
                return THUMBS_UP
            if d == "down":
                return THUMBS_DOWN
            return UNKNOWN
        return FIST
    if index and not middle and not ring and not pinky:
        d = _direction((lm[8][0] - lm[5][0], lm[8][1] - lm[5][1]), aspect)
        return {"left": POINT_LEFT, "right": POINT_RIGHT, "up": POINT_UP}.get(d, UNKNOWN)
    if index and middle and not ring and not pinky:
        vec = ((lm[8][0] + lm[12][0] - lm[5][0] - lm[9][0]) / 2.0,
               (lm[8][1] + lm[12][1] - lm[5][1] - lm[9][1]) / 2.0)
        d = _direction(vec, aspect)
        return {"left": TWO_LEFT, "right": TWO_RIGHT, "up": PEACE}.get(d, UNKNOWN)
    return UNKNOWN
