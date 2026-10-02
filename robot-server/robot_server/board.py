"""Thread-safe wrapper around the Hiwonder STM32 motor board.

The board talks over /dev/rrc (USB serial, 1 Mbaud). Only one process may own
the port, so everything that needs the board goes through this class.
"""
import logging
import threading
import time

log = logging.getLogger("board")


class BoardUnavailable(Exception):
    pass


class MotorBoard(object):
    def __init__(self, device="/dev/rrc", baudrate=1000000):
        from .vendor.ros_robot_controller_sdk import Board

        try:
            self._board = Board(device=device, baudrate=baudrate, timeout=1)
        except Exception as exc:  # serial.SerialException and friends
            raise BoardUnavailable("cannot open %s: %s" % (device, exc))
        self._board.enable_reception()
        self._lock = threading.Lock()
        self.battery_mv = None
        self.imu = None  # (ax, ay, az, gx, gy, gz)
        self.last_battery_time = 0.0
        self._key_events = []
        self._running = True
        self._poller = threading.Thread(target=self._poll, name="board-poll", daemon=True)
        self._poller.start()
        self.stop_motors()

    # ---- outputs ---------------------------------------------------------
    def set_wheels(self, wheel_rps):
        with self._lock:
            self._board.set_motor_speed([[mid, float(rps)] for mid, rps in wheel_rps])

    def stop_motors(self):
        self.set_wheels([(1, 0.0), (2, 0.0), (3, 0.0), (4, 0.0)])

    def beep(self, freq=1900, on_time=0.1, off_time=0.05, repeat=1):
        with self._lock:
            self._board.set_buzzer(int(freq), on_time, off_time, int(repeat))

    def led(self, on_time=0.1, off_time=0.1, repeat=1, led_id=1):
        with self._lock:
            self._board.set_led(on_time, off_time, repeat, led_id)

    # ---- inputs ----------------------------------------------------------
    def _poll(self):
        while self._running:
            try:
                mv = self._board.get_battery()
                if mv:
                    self.battery_mv = mv
                    self.last_battery_time = time.time()
                imu = self._board.get_imu()
                if imu:
                    self.imu = imu
                key = self._board.get_button()
                if key:
                    self._key_events.append(key)
                    del self._key_events[:-10]
            except Exception:  # never let the poller die
                log.exception("board poll error")
            time.sleep(0.02)

    def close(self):
        self._running = False
        try:
            self.stop_motors()
        finally:
            self._board.enable_recv = False


class FakeBoard(object):
    """Stand-in used when the board is missing (development / tests)."""

    def __init__(self):
        self.battery_mv = None
        self.imu = None
        self.last_wheels = [(1, 0.0), (2, 0.0), (3, 0.0), (4, 0.0)]

    def set_wheels(self, wheel_rps):
        self.last_wheels = list(wheel_rps)

    def stop_motors(self):
        self.set_wheels([(1, 0.0), (2, 0.0), (3, 0.0), (4, 0.0)])

    def beep(self, *args, **kwargs):
        pass

    def led(self, *args, **kwargs):
        pass

    def close(self):
        pass
