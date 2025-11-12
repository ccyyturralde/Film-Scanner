
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Film Scanner Web App (Preview Stream Edition)
---------------------------------------------
- Continuous live preview via MJPEG (/preview.mjpg) using a background worker
  that calls `gphoto2 --capture-preview --stdout`.
- Capture-safe: preview worker respects camera_op_lock and yields last frame
  while captures are in progress, so it never interrupts gphoto2 during capture.
- Status checks are read-only (no kill).
- Minimal dependencies: Flask only.

Tested assumptions:
- Canon R100 supports `--capture-preview`; `--capture-movie` not used by default.
- Writing to camera card (capturetarget=1) for speed; download later if desired.

"""
import os
import re
import time
import json
import shutil
import threading
import subprocess
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, Response

app = Flask(__name__)

class FilmScanner:
    def __init__(self):
        # Camera/device state
        self.camera_connected = False
        self.camera_name = ""
        self.viewfinder_enabled = False

        # Concurrency
        self.lock = threading.Lock()
        self.camera_op_lock = threading.Lock()  # exclusive camera operations

        # Preview worker state
        self.preview_enabled = False
        self._preview_thread = None
        self._preview_stop = threading.Event()
        self._last_frame = None           # bytes (JPEG)
        self._preview_fps = 8             # adjust 6–12 for your Pi
        self._last_status = {}

        # Track last failure to decide when to clean up
        self.last_capture_failed = False

        # Try initial camera detection
        try:
            self.check_camera()
        except Exception as e:
            print("Initial camera check error:", e)

    # ------------------------- Utility -------------------------
    def _kill_gphoto2(self):
        """Kill any gphoto2 processes and give USB a moment to settle."""
        try:
            subprocess.run(["killall", "gphoto2"], capture_output=True, text=True, timeout=1)
        except Exception:
            pass
        # Wait a hair to avoid 'Device busy' right after kill
        time.sleep(0.15)

    # ------------------------- Camera checks (read-only) -------------------------
    def check_camera(self):
        """Passive camera detection—no kill, no interruption of active ops."""
        try:
            if self.camera_op_lock.locked():
                return self.camera_connected

            result = subprocess.run(
                ["gphoto2", "--auto-detect"],
                capture_output=True, timeout=5, text=True
            )
            if result.returncode == 0 and "usb" in result.stdout.lower():
                for line in result.stdout.splitlines():
                    if "usb:" in line.lower():
                        self.camera_connected = True
                        self.camera_name = line.strip()
                        break
            else:
                self.camera_connected = False
        except Exception as e:
            print("check_camera error:", e)
        return self.camera_connected

    def check_viewfinder_state(self):
        """Read viewfinder state (no kill)."""
        try:
            if self.camera_op_lock.locked():
                return self.viewfinder_enabled
            result = subprocess.run(
                ["gphoto2", "--get-config", "viewfinder"],
                capture_output=True, timeout=4, text=True
            )
            if result.returncode == 0 and result.stdout:
                out = result.stdout
                if "Current: 1" in out or "Current: On" in out:
                    self.viewfinder_enabled = True
                elif "Current: 0" in out or "Current: Off" in out:
                    self.viewfinder_enabled = False
        except Exception as e:
            print("check_viewfinder_state error:", e)
        return self.viewfinder_enabled

    # ------------------------- Capture -------------------------
    def capture_image(self, retry=True):
        """Capture a frame to the camera SD card, with exclusive access."""
        try:
            self.camera_op_lock.acquire()

            # Only clean up if the last capture failed to keep fast path snappy
            if self.last_capture_failed:
                self._kill_gphoto2()

            # Ensure writing to card is selected once here (fast path ignores errors)
            subprocess.run(["gphoto2", "--set-config", "capturetarget=1"],
                           capture_output=True, text=True, timeout=3)

            print("\n📷 Capturing image...")
            result = subprocess.run(
                ["gphoto2", "--capture-image"],
                capture_output=True, timeout=10, text=True
            )

            print(f"   Return code: {result.returncode}")
            if result.stdout:
                print("   stdout:", result.stdout.strip())
            if result.stderr:
                print("   stderr:", result.stderr.strip())

            success = (result.returncode == 0)
            if not success and result.stderr:
                low = result.stderr.lower()
                # Consider common transient errors as non-fatal if the shutter fired
                if any(k in low for k in ["ptp i/o error", "device busy", "resource busy", "usb device reset", "i/o in progress"]):
                    success = True

            self.last_capture_failed = not success
            if success:
                print("✓ Capture triggered")
                return True

            if retry:
                print("↻ Retry after resetting gphoto2...")
                self._kill_gphoto2()
                return self.capture_image(retry=False)

            print("✗ Capture failed")
            return False

        except Exception as e:
            print("capture_image error:", e)
            self.last_capture_failed = True
            return False
        finally:
            if self.camera_op_lock.locked():
                try:
                    self.camera_op_lock.release()
                except RuntimeError:
                    pass

    # ------------------------- Preview worker -------------------------
    def _preview_loop(self):
        """Continuously fetch preview JPEGs via stdout; pause during capture."""
        self.preview_enabled = True
        # Turn on viewfinder once on start
        try:
            subprocess.run(["gphoto2", "--set-config", "viewfinder=1"],
                           capture_output=True, text=True, timeout=3)
        except Exception as e:
            print("enable viewfinder error:", e)

        interval = 1.0 / max(1, int(self._preview_fps))
        while not self._preview_stop.is_set():
            if self.camera_op_lock.locked():
                # A capture is happening; don't touch gphoto2
                time.sleep(0.02)
                continue

            t0 = time.time()
            try:
                proc = subprocess.run(
                    ["gphoto2", "--capture-preview", "--stdout"],
                    capture_output=True, timeout=2
                )
                if proc.returncode == 0 and proc.stdout:
                    self._last_frame = proc.stdout
                else:
                    if proc.stderr:
                        try:
                            msg = proc.stderr.decode("utf-8", errors="ignore")
                        except Exception:
                            msg = str(proc.stderr)
                        if msg.strip():
                            print("preview stderr:", msg.strip())
            except subprocess.TimeoutExpired:
                pass
            except Exception as e:
                print("preview loop error:", e)

            # Pace the loop
            elapsed = time.time() - t0
            sleep_for = max(0, interval - elapsed)
            if sleep_for > 0:
                time.sleep(sleep_for)

        # Turn off viewfinder on stop
        try:
            subprocess.run(["gphoto2", "--set-config", "viewfinder=0"],
                           capture_output=True, text=True, timeout=3)
        except Exception as e:
            print("disable viewfinder error:", e)
        self.preview_enabled = False

    def start_preview(self):
        if self._preview_thread and self._preview_thread.is_alive():
            return True
        self._preview_stop.clear()
        self._preview_thread = threading.Thread(target=self._preview_loop, daemon=True)
        self._preview_thread.start()
        return True

    def stop_preview(self):
        self._preview_stop.set()
        if self._preview_thread:
            self._preview_thread.join(timeout=2)
        self._preview_thread = None
        return True

    # ------------------------- Status -------------------------
    def status(self):
        return {
            "camera_connected": bool(self.camera_connected),
            "camera_name": self.camera_name,
            "viewfinder": bool(self.viewfinder_enabled),
            "preview_running": bool(self.preview_enabled),
            "last_capture_failed": bool(self.last_capture_failed),
            "time": datetime.now().isoformat(timespec="seconds")
        }


scanner = FilmScanner()

# ------------------------- Routes -------------------------

@app.route("/api/status")
def api_status():
    scanner.check_camera()
    scanner.check_viewfinder_state()
    return jsonify(scanner.status())

@app.route("/api/test_capture", methods=["POST"])
def api_test_capture():
    ok = scanner.capture_image(retry=True)
    return jsonify({"ok": bool(ok)})

@app.route("/api/preview/start", methods=["POST"])
def api_preview_start():
    ok = scanner.start_preview()
    return jsonify({"ok": bool(ok)})

@app.route("/api/preview/stop", methods=["POST"])
def api_preview_stop():
    ok = scanner.stop_preview()
    return jsonify({"ok": bool(ok)})

@app.route("/preview.mjpg")
def preview_mjpg():
    boundary = "frame"
    def gen():
        # Ensure preview is running
        scanner.start_preview()
        while True:
            frame = scanner._last_frame
            if frame:
                yield (b"--" + boundary.encode() + b"\r\n"
                       b"Content-Type: image/jpeg\r\n"
                       b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n" +
                       frame + b"\r\n")
            else:
                time.sleep(0.03)
    return Response(gen(), mimetype=f"multipart/x-mixed-replace; boundary=%s" % boundary)

# ------------------------- Entrypoint -------------------------

if __name__ == "__main__":
    # Basic run; you can put this behind gunicorn if you prefer.
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    debug = bool(int(os.environ.get("DEBUG", "0")))
    print(f"Starting Film Scanner Preview app on {host}:{port}")
    app.run(host=host, port=port, debug=debug, threaded=True)
