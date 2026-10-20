"""MediaPipe hand-landmark worker. Runs as its own process because MediaPipe's
GPU build needs an EGL/X display and can crash; the server restarts it if so.

stdin:  [u32 BE length][JPEG] repeated
stdout: [u32 BE json length][json][u32 BE jpeg length][annotated JPEG] repeated
        The first message is {"ready": true} with an empty image.
"""
import json
import struct
import sys
import time


def read_exact(stream, n):
    buf = b""
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def write_msg(out, meta, jpeg):
    payload = json.dumps(meta).encode()
    out.write(struct.pack(">I", len(payload)) + payload + struct.pack(">I", len(jpeg)) + jpeg)
    out.flush()


def main():
    import cv2
    import numpy as np
    import mediapipe as mp

    inp, out = sys.stdin.buffer, sys.stdout.buffer
    hands = mp.solutions.hands.Hands(
        static_image_mode=False, max_num_hands=1,
        min_detection_confidence=0.6, min_tracking_confidence=0.5)
    drawing = mp.solutions.drawing_utils
    connections = mp.solutions.hands.HAND_CONNECTIONS
    landmark_style = drawing.DrawingSpec(color=(252, 169, 61), thickness=2, circle_radius=3)
    line_style = drawing.DrawingSpec(color=(255, 255, 255), thickness=2)
    write_msg(out, {"ready": True}, b"")

    while True:
        header = read_exact(inp, 4)
        if header is None:
            break
        (n,) = struct.unpack(">I", header)
        jpeg = read_exact(inp, n)
        if jpeg is None:
            break
        img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            write_msg(out, {"landmarks": None, "error": "bad frame"}, jpeg)
            continue
        t0 = time.time()
        result = hands.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        landmarks = None
        if result.multi_hand_landmarks:
            hand = result.multi_hand_landmarks[0]
            landmarks = [[round(p.x, 4), round(p.y, 4)] for p in hand.landmark]
            drawing.draw_landmarks(img, hand, connections, landmark_style, line_style)
        ms = (time.time() - t0) * 1000.0
        ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
        write_msg(out, {"landmarks": landmarks, "ms": round(ms, 1),
                        "w": img.shape[1], "h": img.shape[0]}, enc.tobytes() if ok else jpeg)


if __name__ == "__main__":
    main()
