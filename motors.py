"""Beak (jaw) and head control for the parrot.

Two small DC motors on a TB6612 driver (A = beak, B = head), powered by the
prop's own power adapter (5.9V on the reference build):
  - the beak motor opens the beak when driven "forward" (GPIO23 high on the
    reference build) and the beak closes by itself when power is off. Never drive it
    backward: that forces the beak shut hard.
  - the head motor turns the head back and forth (run it while talking).
The beak is never held open for long (JAW_MAX_OPEN_SECONDS), so the motor
doesn't sit stalled against its stop during long loud sounds.

With MOTORS=off (the default) it just logs, so you can test on a Mac.
"""
import logging
import os
import random
import threading
import time

log = logging.getLogger("motors")

ENABLED = os.getenv("MOTORS", "off").lower() == "on"
JAW_FWD = int(os.getenv("JAW_PIN_A", "23"))
JAW_BACK = int(os.getenv("JAW_PIN_B", "24"))
HEAD_FWD = int(os.getenv("HEAD_PIN_A", "5"))
HEAD_BACK = int(os.getenv("HEAD_PIN_B", "6"))
JAW_OPEN_LEVEL = float(os.getenv("JAW_OPEN_LEVEL", "0.06"))   # loudness to open
JAW_CLOSE_LEVEL = float(os.getenv("JAW_CLOSE_LEVEL", "0.03"))  # loudness to close
JAW_POWER = float(os.getenv("JAW_POWER", "0.8"))
HEAD_POWER = float(os.getenv("HEAD_POWER", "0.5"))   # 0 = keep the head still
HEAD_MOVE_S = float(os.getenv("HEAD_MOVE_SECONDS", "0.4"))  # length of one head turn
# His head turns a little farther to his right than to his left in the same time
# (measured on video on the reference build), so right turns are shortened by this factor to stay centred.
HEAD_RIGHT_SCALE = float(os.getenv("HEAD_RIGHT_SCALE", "0.9"))
JAW_MAX_OPEN_S = float(os.getenv("JAW_MAX_OPEN_SECONDS", "0.5"))  # then let it close
JAW_REST_S = float(os.getenv("JAW_REST_SECONDS", "0.12"))  # closed at least this long


class Motors:
    def __init__(self):
        self._jaw_open = False
        self._jaw_since = 0.0
        self._head_left = False  # which way the next gesture starts (alternates)
        self._head_lock = threading.Lock()
        self._head_thread = None
        self._tilted = None  # which way the listening tilt went, until it's undone
        self._talking = False
        self._lock = threading.Lock()
        if ENABLED:
            from gpiozero import Motor
            self.jaw_motor = Motor(forward=JAW_FWD, backward=JAW_BACK)
            self.head_motor = Motor(forward=HEAD_FWD, backward=HEAD_BACK)
            log.info("motors on")
        else:
            self.jaw_motor = self.head_motor = None
            log.info("motors off (MOTORS=off): simulating")

    # Called every 20 ms with the loudness (0..1) of the audio being played.
    def jaw(self, level: float):
        now = time.monotonic()
        with self._lock:
            if not self._jaw_open:
                if level > JAW_OPEN_LEVEL and now - self._jaw_since >= JAW_REST_S:
                    self._jaw_open, self._jaw_since = True, now
                    if self.jaw_motor:
                        self.jaw_motor.forward(JAW_POWER)
            elif level < JAW_CLOSE_LEVEL or now - self._jaw_since >= JAW_MAX_OPEN_S:
                self._jaw_open, self._jaw_since = False, now
                if self.jaw_motor:
                    self.jaw_motor.stop()

    # ---- head ----------------------------------------------------------------
    # There is no position sensor, so every head move is a "there and back"
    # gesture: turn one way, pause, turn back the same amount. That keeps him
    # near the middle all night instead of slowly drifting to one end. Moves
    # are done one at a time (a lock), and a gesture always finishes, so it
    # never stops halfway out.

    def _move(self, left: bool, secs: float):
        if left:
            self.head_motor.forward(HEAD_POWER)   # forward = his left
        else:
            self.head_motor.backward(HEAD_POWER)  # backward = his right
            secs *= HEAD_RIGHT_SCALE
        time.sleep(secs)
        self.head_motor.stop()

    def _gesture_loop(self):
        while self._talking:
            with self._head_lock:
                self._head_left = not self._head_left  # alternate which side first
                self._move(self._head_left, HEAD_MOVE_S)
                time.sleep(0.25)
                self._move(not self._head_left, HEAD_MOVE_S)
            end = time.monotonic() + random.uniform(0.6, 1.5)
            while self._talking and time.monotonic() < end:
                time.sleep(0.05)
        self._head_thread = None

    def talking(self, on: bool):
        self._talking = on
        if not (self.head_motor and HEAD_POWER > 0):
            return
        if on and self._head_thread is None:
            self._head_thread = threading.Thread(target=self._gesture_loop, daemon=True)
            self._head_thread.start()

    # A cue that he's listening: cock the head to one side, then back afterwards.
    def listening(self, on: bool):
        if not (self.head_motor and HEAD_POWER > 0):
            return
        threading.Thread(target=self._tilt, args=(on,), daemon=True).start()

    def _tilt(self, on: bool):
        with self._head_lock:
            if on and self._tilted is None:
                self._head_left = not self._head_left
                self._tilted = self._head_left
                self._move(self._tilted, 0.3)
            elif not on and self._tilted is not None:
                self._move(not self._tilted, 0.3)
                self._tilted = None
