"""Physical buttons on the expansion board (replaces Hiwonder's button_scan.py).

KEY1 (short press): forget the home WiFi and go back to hotspot mode.
KEY2 (hold ~1.5 s): shut the robot down safely.
"""
import logging
import os
import threading
import time

log = logging.getLogger("buttons")


class Buttons(object):
    def __init__(self, cfg, board, on_shutdown=None):
        self.cfg = cfg
        self.board = board
        self.on_shutdown = on_shutdown
        self._thread = None

    def start(self):
        if not self.cfg["enabled"]:
            return
        try:
            import Jetson.GPIO as GPIO  # noqa: N814
        except Exception as exc:
            log.warning("GPIO unavailable, buttons disabled: %s", exc)
            return
        self._thread = threading.Thread(target=self._run, args=(GPIO,), name="buttons", daemon=True)
        self._thread.start()

    def _run(self, GPIO):
        k1, k2 = self.cfg["wifi_reset_pin"], self.cfg["shutdown_pin"]
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(k1, GPIO.IN)
        GPIO.setup(k2, GPIO.IN)
        k1_count = k2_count = 0
        k1_done = k2_done = False
        while True:
            if GPIO.input(k1) == GPIO.LOW:
                k1_count += 1
                if k1_count >= 2 and not k1_done:
                    k1_done = True
                    log.warning("KEY1: resetting WiFi to hotspot mode")
                    self.board.beep(1900, 0.2, 0.01, 1)
                    os.system("sudo rm -rf /etc/wifi/* > /dev/null 2>&1")
                    os.system("sudo systemctl restart wifi.service > /dev/null 2>&1")
            else:
                k1_count, k1_done = 0, False
            if GPIO.input(k2) == GPIO.LOW:
                k2_count += 1
                if k2_count >= 30 and not k2_done:
                    k2_done = True
                    log.warning("KEY2: shutting down")
                    self.board.beep(2500, 0.5, 0.01, 1)
                    if self.on_shutdown:
                        self.on_shutdown()
                    time.sleep(0.6)
                    os.system("sudo halt")
            else:
                k2_count, k2_done = 0, False
            time.sleep(0.05)
