"""Gesture mode: camera frames -> MediaPipe worker -> GestureController -> drive.

While gesture mode is on:
  * the gesture service is the robot's driver (the phone's sticks are disabled),
  * the camera stays on and viewers see the video with the hand skeleton drawn,
  * losing the hand, a stop pose, the phone's E-STOP, or the phone taking
    control all stop the robot.
"""
import logging
import os
import queue
import struct
import subprocess
import sys
import threading
import time

from .controller import GestureController

log = logging.getLogger("gestures")
CLIENT_ID = "gesture"
SERVER_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class GestureService(object):
    def __init__(self, cfg, camera, drive, board, loop):
        self.cfg = cfg
        self.camera = camera
        self.drive = drive
        self.board = board
        self.loop = loop
        self.controller = GestureController(cfg)
        self.enabled = False
        self.ready = False
        self.error = None
        self.fps = 0.0
        self.infer_ms = None
        self._proc = None
        self._busy = False
        self._pending = None
        self._outbox = queue.Queue(maxsize=1)
        self._frames = 0
        self._window = time.time()
        self._restarts = 0
        self._started_at = 0.0

    # ---- public ---------------------------------------------------------------
    def enable(self):
        if self.enabled:
            return True
        if not self.cfg["enabled"]:
            self.error = "gestures disabled in config"
            return False
        log.info("gesture mode ON")
        self.enabled = True
        self.error = None
        self._restarts = 0
        self.controller.reset()
        if self.drive.driver_id not in (None, CLIENT_ID):
            self.drive.release(self.drive.driver_id)
        self.drive.claim(CLIENT_ID)
        self.camera.raw_listeners.append(self._on_raw)
        self.camera.override = True
        self.camera.add_viewer()
        self._start_worker()
        return True

    def disable(self, reason="off"):
        if not self.enabled:
            return
        log.info("gesture mode OFF (%s)", reason)
        self.enabled = False
        self.ready = False
        self.fps = 0.0
        if self.drive.driver_id == CLIENT_ID:
            self.drive.release(CLIENT_ID)
        self.board.stop_motors()
        if self._on_raw in self.camera.raw_listeners:
            self.camera.raw_listeners.remove(self._on_raw)
        self.camera.override = False
        self.camera.remove_viewer()
        self._stop_worker()
        self.controller.reset()
        if reason != "worker failed":
            self.error = None  # only failures stay visible to the app
        self.board.beep(1200, 0.15, 0.05, 1)

    def status(self):
        s = self.controller.status() if self.enabled else {"mode": None, "gesture": None, "action": None}
        s.update({"enabled": self.enabled, "ready": self.ready, "fps": round(self.fps, 1),
                  "infer_ms": self.infer_ms, "error": self.error})
        return s

    def shutdown(self):
        self.disable("shutdown")

    # ---- worker process -------------------------------------------------------
    def _start_worker(self):
        env = dict(os.environ)
        env.setdefault("DISPLAY", self.cfg["display"])
        env.setdefault("XAUTHORITY", os.path.expanduser(self.cfg["xauthority"]))
        env["PYTHONUNBUFFERED"] = "1"
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "robot_server.gestures.worker"], cwd=SERVER_DIR, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        self._started_at = time.time()
        self._busy = False
        self._pending = None
        self._outbox = queue.Queue(maxsize=1)
        proc = self._proc
        threading.Thread(target=self._reader, args=(proc,), daemon=True).start()
        threading.Thread(target=self._writer, args=(proc, self._outbox), daemon=True).start()
        threading.Thread(target=self._stderr, args=(proc,), daemon=True).start()

    def _stop_worker(self):
        proc, self._proc = self._proc, None
        if proc and proc.poll() is None:
            try:
                proc.stdin.close()
            except Exception:
                pass
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()

    def _writer(self, proc, outbox):
        while proc.poll() is None:
            try:
                jpeg = outbox.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                proc.stdin.write(struct.pack(">I", len(jpeg)) + jpeg)
                proc.stdin.flush()
            except Exception:
                return

    def _reader(self, proc):
        out = proc.stdout
        try:
            while True:
                meta = self._read_block(out)
                if meta is None:
                    break
                jpeg = self._read_block(out)
                if jpeg is None:
                    break
                self.loop.call_soon_threadsafe(self._on_result, proc, meta, jpeg)
        except Exception:
            log.exception("worker reader error")
        code = proc.wait()
        self.loop.call_soon_threadsafe(self._on_worker_exit, proc, code)

    @staticmethod
    def _read_block(stream):
        header = stream.read(4)
        if len(header) < 4:
            return None
        (n,) = struct.unpack(">I", header)
        data = b""
        while len(data) < n:
            chunk = stream.read(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def _stderr(self, proc):
        for line in iter(proc.stderr.readline, b""):
            text = line.decode("utf-8", "replace").rstrip()
            if "Error" in text or "error" in text or "Traceback" in text:
                log.warning("worker: %s", text[:300])
                if "EGL" in text or "display" in text.lower():
                    self.error = "GPU display unavailable (is the robot's desktop session running?)"

    def _on_worker_exit(self, proc, code):
        if proc is not self._proc or not self.enabled:
            return
        self.ready = False
        self.board.stop_motors()
        quick_fail = time.time() - self._started_at < 10
        self._restarts += 1
        if self._restarts > 3 or (quick_fail and self._restarts > 1):
            self.error = self.error or "gesture worker keeps crashing (exit %s)" % code
            log.error(self.error)
            self.disable("worker failed")
            return
        log.warning("gesture worker exited (%s), restarting", code)
        self.loop.call_later(1.0, self._restart_if_enabled)

    def _restart_if_enabled(self):
        if self.enabled:
            self._start_worker()

    # ---- frames ---------------------------------------------------------------
    def _on_raw(self, jpeg):
        if not self.ready or self._busy:
            self._pending = jpeg
            return
        self._send(jpeg)

    def _send(self, jpeg):
        self._busy = True
        try:
            self._outbox.put_nowait(jpeg)
        except queue.Full:
            self._busy = False

    def _on_result(self, proc, meta_raw, jpeg):
        if proc is not self._proc or not self.enabled:
            return
        import json
        meta = json.loads(meta_raw.decode())
        if meta.get("ready"):
            self.ready = True
            self.error = None
            log.info("gesture worker ready")
            self.board.beep(2200, 0.05, 0.05, 2)
        else:
            self._busy = False
            self.infer_ms = meta.get("ms")
            self._frames += 1
            now = time.time()
            if now - self._window >= 1.0:
                self.fps = self._frames / (now - self._window)
                self._frames, self._window = 0, now
            self._apply(meta.get("landmarks"))
            if jpeg:
                self.camera.publish_processed(jpeg)
        if self._pending is not None and self.ready and not self._busy:
            pending, self._pending = self._pending, None
            self._send(pending)

    def _apply(self, landmarks):
        if self.drive.driver_id != CLIENT_ID:
            self.disable("control taken")
            return
        vx, vy, wz = self.controller.update(landmarks)
        for event in self.controller.events:
            if event == "follow_on":
                self.board.beep(2600, 0.08, 0.06, 3)
            elif event == "follow_off":
                self.board.beep(1500, 0.3, 0.05, 1)
        del self.controller.events[:]
        speed = self.cfg["follow_speed"] if self.controller.mode == "follow" else self.cfg["speed"]
        self.drive.command(CLIENT_ID, vx, vy, wz, speed)
