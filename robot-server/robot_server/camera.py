"""Camera service.

Runs the C++ `camera_bridge` (Deptrum SDK) as a child process, reads the
length-prefixed JPEG frames it writes to stdout, and fans the latest frame out
to any number of viewers. The camera only runs while someone is watching.
"""
import asyncio
import logging
import os
import struct
import subprocess
import sys
import threading
import time

log = logging.getLogger("camera")


def _event(loop):
    # Python < 3.8 binds Events to a loop at creation; newer versions bind lazily.
    return asyncio.Event(loop=loop) if sys.version_info < (3, 8) else asyncio.Event()


class CameraService(object):
    def __init__(self, cfg, loop):
        self.cfg = cfg
        self.loop = loop
        self.frame = None
        self.frame_id = 0
        self.frame_time = 0.0
        self.fps = 0.0
        self.error = None
        self.viewers = 0
        self._proc = None
        self._reader = None
        self._new_frame = _event(loop)
        self._idle_handle = None
        self._lock = threading.Lock()
        self._backoff = 1.0
        # Gesture mode hooks: raw frames go to listeners; when override is on,
        # viewers get frames from publish_processed() instead of the raw feed.
        self.raw_listeners = []
        self.override = False

    # ---- lifecycle --------------------------------------------------------
    @property
    def running(self):
        return self._proc is not None and self._proc.poll() is None

    def _start(self):
        with self._lock:
            if self.running:
                return
            path = self.cfg["bridge"]
            if not os.path.exists(path):
                self.error = "camera_bridge not built: %s" % path
                log.error(self.error)
                return
            args = [path, "--mode", str(self.cfg["mode"]), "--quality", str(self.cfg["quality"]),
                    "--fps", str(self.cfg["fps"]), "--width", str(self.cfg["width"])]
            log.info("starting camera: %s", " ".join(args))
            self._proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
            self.error = None
            self._reader = threading.Thread(target=self._read_frames, args=(self._proc,), daemon=True)
            self._reader.start()
            threading.Thread(target=self._drain_stderr, args=(self._proc,), daemon=True).start()

    def _stop(self):
        with self._lock:
            proc, self._proc = self._proc, None
        if proc and proc.poll() is None:
            log.info("stopping camera")
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        self.fps = 0.0

    def _read_frames(self, proc):
        stream = proc.stdout
        count, window_start = 0, time.time()
        try:
            while True:
                header = stream.read(4)
                if len(header) < 4:
                    break
                (length,) = struct.unpack(">I", header)
                data = b""
                while len(data) < length:
                    chunk = stream.read(length - len(data))
                    if not chunk:
                        break
                    data += chunk
                if len(data) < length:
                    break
                count += 1
                now = time.time()
                if now - window_start >= 1.0:
                    self.fps = count / (now - window_start)
                    count, window_start = 0, now
                self._backoff = 1.0
                self.loop.call_soon_threadsafe(self._publish, data)
        except Exception:
            log.exception("camera reader error")
        code = proc.wait()
        if self._proc is proc:  # died on its own, not stopped by us
            self.error = "camera_bridge exited (code %s)" % code
            log.warning(self.error)
            self.loop.call_soon_threadsafe(self._restart_later)

    def _drain_stderr(self, proc):
        for line in iter(proc.stderr.readline, b""):
            text = line.decode("utf-8", "replace").rstrip()
            if "[camera_bridge]" in text:
                log.info(text)

    def _restart_later(self):
        with self._lock:
            self._proc = None
        if self.viewers > 0:
            delay, self._backoff = self._backoff, min(self._backoff * 2, 30.0)
            log.info("restarting camera in %.0fs", delay)
            self.loop.call_later(delay, self._maybe_start)

    def _maybe_start(self):
        if self.viewers > 0:
            self._start()

    def _publish(self, data):
        for listener in list(self.raw_listeners):
            try:
                listener(data)
            except Exception:
                log.exception("raw frame listener failed")
        if not self.override:
            self._emit(data)

    def publish_processed(self, data):
        if self.override:
            self._emit(data)

    def _emit(self, data):
        self.frame = data
        self.frame_id += 1
        self.frame_time = time.time()
        self._new_frame.set()
        self._new_frame = _event(self.loop)

    # ---- viewers ----------------------------------------------------------
    def add_viewer(self):
        self.viewers += 1
        if self._idle_handle:
            self._idle_handle.cancel()
            self._idle_handle = None
        if self.cfg["enabled"]:
            self._start()

    def remove_viewer(self):
        self.viewers = max(0, self.viewers - 1)
        if self.viewers == 0 and self._idle_handle is None:
            self._idle_handle = self.loop.call_later(self.cfg["idle_stop_seconds"], self._idle_stop)

    def _idle_stop(self):
        self._idle_handle = None
        if self.viewers == 0:
            self._stop()

    async def next_frame(self, last_id, timeout=5.0):
        """Wait for a frame newer than last_id. Returns (frame_id, jpeg) or None."""
        if self.frame is not None and self.frame_id != last_id and time.time() - self.frame_time < 1.0:
            return self.frame_id, self.frame
        event = self._new_frame
        try:
            await asyncio.wait_for(event.wait(), timeout)
        except asyncio.TimeoutError:
            return None
        return self.frame_id, self.frame

    def status(self):
        return {"running": self.running, "fps": round(self.fps, 1), "viewers": self.viewers, "error": self.error}

    def shutdown(self):
        self._stop()
