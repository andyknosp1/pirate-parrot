"""Camera for the parrot: lets him see (and compliment) costumes.

The camera runs continuously in the background so exposure is always settled,
and snapshot() just grabs the latest frame. Frames are never saved to disk;
each snapshot is shrunk, sent to Claude with the question, then discarded.

Setup check (saves one test photo per camera it finds so you can pick the
right CAMERA_DEVICE; delete the files afterwards):
    python camera.py
"""
import base64
import logging
import os
import shutil
import subprocess
import sys
import threading
import time

log = logging.getLogger("camera")

ENABLED = os.getenv("CAMERA", "off").lower() == "on"
_dev = os.getenv("CAMERA_DEVICE", "0")
DEVICE = int(_dev) if _dev.isdigit() else _dev   # index, or a path like /dev/video0
CAPTURE_W = int(os.getenv("CAMERA_WIDTH", "1280"))
CAPTURE_H = int(os.getenv("CAMERA_HEIGHT", "720"))
SEND_W = int(os.getenv("CAMERA_SEND_WIDTH", "1024"))   # size sent to Claude
MIN_BRIGHTNESS = float(os.getenv("CAMERA_MIN_BRIGHTNESS", "25"))  # 0-255; darker = skip
# Extra camera settings applied on Linux with v4l2-ctl, e.g. for the Arducam low-light
# board: "power_line_frequency=2,exposure_dynamic_framerate=1" (60 Hz lighting, and let
# it use longer exposures when it's dark). See `v4l2-ctl -d /dev/video0 -l` for the list.
CONTROLS = os.getenv("CAMERA_CONTROLS", "")


class Camera:
    def __init__(self):
        self.enabled = ENABLED
        self._frame = None
        self._lock = threading.Lock()
        if not self.enabled:
            log.info("camera off (CAMERA=off)")
            return
        import cv2  # noqa: F401  (fail fast if OpenCV is missing)
        threading.Thread(target=self._run, daemon=True).start()

    def _open(self):
        import cv2
        cap = cv2.VideoCapture(DEVICE)
        # Ask for the compressed (MJPG) stream: many USB cameras only offer full
        # resolution that way, and it is lighter on the Pi's USB bus.
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_H)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._apply_controls()
        return cap

    def _apply_controls(self):
        if not (CONTROLS and sys.platform.startswith("linux") and shutil.which("v4l2-ctl")):
            return
        dev = f"/dev/video{DEVICE}" if isinstance(DEVICE, int) else DEVICE
        r = subprocess.run(["v4l2-ctl", "-d", dev, "-c", CONTROLS],
                           capture_output=True, text=True)
        if r.returncode:
            log.warning("camera settings not applied: %s", r.stderr.strip())

    def _run(self):
        cap = None
        while True:
            if cap is None or not cap.isOpened():
                cap = self._open()
                if not cap.isOpened():
                    log.warning("camera %s not available; retrying", DEVICE)
                    time.sleep(3)
                    continue
                log.info("camera %s running", DEVICE)
            ok, frame = cap.read()
            if not ok:
                log.warning("camera read failed; reopening")
                cap.release()
                cap = None
                time.sleep(1)
                continue
            with self._lock:
                self._frame = frame

    def snapshot(self):
        """Latest frame as base64 JPEG for Claude, or None if off, missing or too dark."""
        if not self.enabled:
            return None
        import cv2
        with self._lock:
            frame = None if self._frame is None else self._frame.copy()
        if frame is None:
            return None
        if float(frame.mean()) < MIN_BRIGHTNESS:
            log.info("too dark for a useful photo; skipping")
            return None
        h, w = frame.shape[:2]
        if w > SEND_W:
            frame = cv2.resize(frame, (SEND_W, int(h * SEND_W / w)), interpolation=cv2.INTER_AREA)
        ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return base64.b64encode(jpg.tobytes()).decode() if ok else None


if __name__ == "__main__":
    import cv2
    found = False
    for i in range(6):
        cap = cv2.VideoCapture(i)
        if not cap.isOpened():
            continue
        for _ in range(20):          # let auto-exposure settle
            ok, frame = cap.read()
        cap.release()
        if ok:
            found = True
            name = f"camera_test_{i}.jpg"
            cv2.imwrite(name, frame)
            h, w = frame.shape[:2]
            print(f"CAMERA_DEVICE={i}: {w}x{h}, brightness {frame.mean():.0f} -> saved {name}")
    if not found:
        print("No cameras found. On a Mac, allow Terminal to use the camera in "
              "System Settings > Privacy & Security > Camera.")
