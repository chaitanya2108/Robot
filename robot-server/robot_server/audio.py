"""Plays short sound clips on the robot's USB speaker (ALSA default = card 2)."""
import logging
import os
import subprocess

log = logging.getLogger("audio")


class Audio(object):
    def __init__(self, cfg):
        self.cfg = cfg
        self.dir = cfg["sounds_dir"] if os.path.isdir(cfg["sounds_dir"]) else cfg["fallback_sounds_dir"]
        self._proc = None

    def sounds(self):
        if not self.cfg["enabled"] or not os.path.isdir(self.dir):
            return []
        return sorted(f[:-4] for f in os.listdir(self.dir) if f.endswith(".wav"))

    def play(self, name):
        if not self.cfg["enabled"] or name not in self.sounds():
            return False
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        path = os.path.join(self.dir, name + ".wav")
        self._proc = subprocess.Popen([self.cfg["player"], "-q", path],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
