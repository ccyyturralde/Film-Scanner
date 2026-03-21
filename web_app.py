#!/usr/bin/env python3
"""
35mm Film Scanner - Web Application
Mobile-friendly web interface for film scanning

Supports:
- Arduino Uno R3 via USB Serial
- Arduino Uno R4 (Minima/WiFi) via USB Serial
"""
# CRITICAL: Prevent eventlet/gevent from being used even if installed
# This avoids RLock errors when running via subprocess (touchscreen UI)
import sys
if 'eventlet' in sys.modules:
    del sys.modules['eventlet']
if 'gevent' in sys.modules:
    del sys.modules['gevent']

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask import Response
import serial
import serial.tools.list_ports
import socket
import subprocess
import time
import os
from datetime import datetime
from typing import Optional, Tuple, Union
from collections import deque
import json
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import base64
import tempfile
import shutil
import traceback
import re
import glob
import io
from pathlib import Path
from config_manager import ConfigManager
from scanlight_controller import ScanLight
from frame_detector import (
    detect_frame_gap,
    detect_bright_region_roi,
    compute_column_stats,
    compute_vertical_continuity,
    find_gap_candidates_brightness,
    find_gap_regions,
    detect_vertical_edges,
    _to_python_type,
)
from sprocket_detector import (
    detect_sprockets,
    calibrate_from_sprockets,
    detect_frame_edge_sprocket,
    SprocketDetectionResult,
    SPROCKET_PITCH_MM,
    SPROCKETS_PER_FRAME,
)
import cv2
import numpy as np
try:
    from PIL import Image, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠ PIL/Pillow not available - image preview will be limited")


def encode_preview_bytes(preview_bytes: bytes, invert: bool = False) -> str:
    """
    Encode preview bytes to base64 JPEG. Optional pure inversion for visualization.
    Inversion is for UI only and is never fed into alignment.
    """
    if not preview_bytes:
        raise ValueError("Empty preview")
    if invert and PIL_AVAILABLE:
        img = Image.open(io.BytesIO(preview_bytes))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img_inverted = ImageOps.invert(img)
        buf = io.BytesIO()
        img_inverted.save(buf, format='JPEG', quality=85)
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    return base64.b64encode(preview_bytes).decode('utf-8')


CAMERA_USB_BRANDS = ("canon", "fujifilm", "fuji", "nikon", "sony", "olympus", "panasonic")


def _camera_brand_from_lsusb_line(line: str) -> Optional[str]:
    """Return matched camera brand name from an lsusb line, if present."""
    line_lower = (line or "").lower()
    for brand in CAMERA_USB_BRANDS:
        if brand in line_lower:
            return brand
    return None


def clear_usb_for_camera():
    """
    Thoroughly clear USB to make room for the camera connection.
    This addresses issues where touchscreen or other USB devices
    cause gphoto2 to fail to detect the camera.
    
    Kills:
    - gphoto2 processes
    - gvfsd-gphoto2 (GNOME/GVFS auto-mount daemon)
    - gvfs-gphoto2-volume-monitor
    - gvfsd-mtp (MTP daemon that can interfere)
    - PTPCamera (macOS)
    - Any other processes that might claim the camera
    
    Also:
    - Resets USB device if possible (Linux only)
    """
    print("\n🔌 Clearing USB for camera connection...")
    
    # List of processes to kill that can interfere with gphoto2 camera access
    processes_to_kill = [
        "gphoto2",
        "gvfsd-gphoto2",
        "gvfs-gphoto2-volume-monitor", 
        "gvfsd-mtp",
        "gvfs-mtp-volume-monitor",
        "gvfsd-ptp",
        "PTPCamera",  # macOS
        "gvfs-ptp-volume-monitor",
    ]
    
    killed_any = False
    
    for proc in processes_to_kill:
        try:
            # First try graceful kill
            result = subprocess.run(
                ["killall", proc],
                capture_output=True,
                timeout=2
            )
            if result.returncode == 0:
                print(f"   ✓ Killed {proc}")
                killed_any = True
        except Exception:
            pass
    
    # Brief pause to let processes die
    if killed_any:
        time.sleep(0.3)
    
    # Force kill any remaining processes
    for proc in processes_to_kill:
        try:
            subprocess.run(
                ["killall", "-9", proc],
                capture_output=True,
                timeout=1
            )
        except Exception:
            pass
    
    # Kill any gvfsd processes that might be holding USB devices
    try:
        result = subprocess.run(
            ["pkill", "-f", "gvfsd"],
            capture_output=True,
            timeout=2
        )
        if result.returncode == 0:
            print("   ✓ Killed gvfsd processes")
    except Exception:
        pass
    
    # Wait for processes to fully release USB
    time.sleep(0.5)
    
    # Try to reset USB devices for known camera brands (Linux only)
    try:
        # Find camera USB devices
        lsusb_result = subprocess.run(
            ["lsusb"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if lsusb_result.returncode == 0:
            for line in lsusb_result.stdout.split('\n'):
                brand = _camera_brand_from_lsusb_line(line)
                if brand:
                    print(f"   📷 Found {brand.title()} device: {line.strip()}")
                    
                    # Extract bus and device numbers for potential USB reset
                    # Format: Bus 001 Device 005: ID 04a9:32da Vendor Name ...
                    parts = line.split()
                    if len(parts) >= 6:
                        bus = parts[1]
                        device = parts[3].rstrip(':')
                        
                        # Try USB reset using usb_reset if available
                        usb_dev_path = f"/dev/bus/usb/{bus}/{device}"
                        if os.path.exists(usb_dev_path):
                            try:
                                # Use usbreset tool if available
                                subprocess.run(
                                    ["usbreset", usb_dev_path],
                                    capture_output=True,
                                    timeout=3
                                )
                                print(f"   ✓ Reset USB device {usb_dev_path}")
                            except FileNotFoundError:
                                # usbreset not installed, try alternative
                                try:
                                    # Alternative: unbind and rebind the USB device
                                    # This is a more aggressive reset
                                    pass  # Skip if usbreset not available
                                except Exception:
                                    pass
                            except Exception as e:
                                # USB reset failed, but continue anyway
                                pass
    except Exception as e:
        # lsusb not available (non-Linux), skip USB reset
        pass
    
    # Final cleanup - unmount any auto-mounted camera
    try:
        # Get list of gvfs mounts
        result = subprocess.run(
            ["gio", "mount", "-l"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and 'gphoto2' in result.stdout.lower():
            # Unmount gphoto2 devices
            subprocess.run(
                ["gio", "mount", "-u", "-f", "gphoto2://"],
                capture_output=True,
                timeout=5
            )
            print("   ✓ Unmounted gphoto2 auto-mount")
            time.sleep(0.3)
    except Exception:
        pass
    
    # Wait for USB to stabilize after all cleanup
    time.sleep(0.5)
    
    print("   ✓ USB cleanup complete")
    return True

def find_capture_card_device():
    """
    Find the first available video capture device (e.g. USB capture card on Raspberry Pi).
    - Prefer /dev/video0 through /dev/video9 (V4L2 on Linux).
    - Fallback: try integer indices 0..9 in case device is available by index only.
    Returns device path (str), device index (int), or None if none found.
    """
    # 1) Prefer /dev/video* (V4L2 on Raspberry Pi / Linux)
    for i in range(10):
        device = f"/dev/video{i}"
        if os.path.exists(device):
            try:
                cap = cv2.VideoCapture(device)
                if cap.isOpened():
                    cap.release()
                    return device
            except Exception:
                pass
    # 2) Fallback: integer indices
    for i in range(10):
        try:
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                cap.release()
                return i
        except Exception:
            pass
    return None


class CaptureCardStream:
    """
    Live preview stream from capture card using OpenCV VideoCapture.
    Always 1080p (1920x1080). Reads from /dev/video* and exposes the latest frame.
    """
    # Fixed 1080p stream
    CAPTURE_WIDTH = 1920
    CAPTURE_HEIGHT = 1080

    # MJPEG stream is downscaled to 960px in the capture thread for performance.
    # A raw full-res numpy frame is kept alongside for alignment/sprocket detection.
    STREAM_OUTPUT_WIDTH = 960

    def __init__(self, scanner, device: Optional[Union[str, int]] = None, max_age: float = 2.0):
        self.scanner = scanner
        self.device = device if device is not None else find_capture_card_device()
        self.output_width = self.STREAM_OUTPUT_WIDTH  # MJPEG stream at 960px
        self.capture_width = self.CAPTURE_WIDTH
        self.capture_height = self.CAPTURE_HEIGHT
        self.jpeg_quality = 80
        self.max_age = max_age
        self.latest_frame: Optional[bytes] = None      # 960px JPEG for MJPEG stream
        self.latest_raw_frame: Optional[np.ndarray] = None  # Full-res numpy for alignment
        self.last_frame_ts: float = 0.0
        
        # Thread control
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.restart_event = threading.Event()  # Signal to restart with new settings
        self.cap: Optional[cv2.VideoCapture] = None
        self.lock = threading.Lock()
        self.last_error: Optional[str] = None
        
        # Stats
        self.actual_width = 0
        self.actual_height = 0
        self.fps = 0.0

    def is_running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def start(self) -> bool:
        """Start stream if not already running. Re-searches for device if not found (e.g. plugged in later)."""
        # Re-search for capture card when device is missing (e.g. first use or after disconnect)
        if self.device is None:
            self.device = find_capture_card_device()
        if self.device is None:
            self.last_error = "No capture card found (check USB /dev/video* or camera index)"
            self.scanner.log("✗ Capture card not found - check USB connection and /dev/video* or camera index")
            return False

        with self.lock:
            if self.is_running():
                return True
            self.stop_event.clear()
            self.restart_event.clear()
            self.thread = threading.Thread(target=self._run_stream, daemon=True)
            self.thread.start()
        return True

    def pause_for_capture(self) -> bool:
        """Stop stream before a still capture, returning whether it was running."""
        was_running = self.is_running()
        if was_running:
            self.stop()
            time.sleep(0.1)  # Brief pause for capture
        return was_running

    def stop(self):
        """Stop stream and clean up capture device."""
        with self.lock:
            self.stop_event.set()
            cap = self.cap
            self.cap = None
        if cap:
            try:
                cap.release()
            except Exception:
                pass
        # Allow thread to exit
        if self.thread:
            self.thread.join(timeout=1.0)
        self.thread = None

    def get_frame(self, timeout: float = 0.8) -> Optional[bytes]:
        """Return latest fresh 960px JPEG for the MJPEG stream, or None."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.lock:
                frame = self.latest_frame
                ts = self.last_frame_ts
            if frame and (time.time() - ts) <= self.max_age:
                return frame
            time.sleep(0.05)
        return None

    def get_full_frame(self, timeout: float = 0.8) -> Optional[bytes]:
        """Return latest full-resolution JPEG for alignment/sprocket detection."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.lock:
                raw = self.latest_raw_frame
                ts = self.last_frame_ts
            if raw is not None and (time.time() - ts) <= self.max_age:
                ret, jpeg = cv2.imencode('.jpg', raw, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if ret:
                    return jpeg.tobytes()
            time.sleep(0.05)
        return None

    def restart_if_stale(self, max_age_sec: float = 2.5) -> bool:
        """
        If no new frame for max_age_sec (stream dead or stuck), stop, wait for device
        release, then start again. Works even when the capture thread has already exited.
        Returns True if a restart was performed.
        """
        with self.lock:
            ts = self.last_frame_ts
        if time.time() - ts <= max_age_sec:
            return False
        try:
            self.scanner.log("⚠ Video stream stuck or dead, restarting (release + 2.5s delay)...")
            self.stop()
            # Force device fully released before reopen (only fix for USB/V4L2 freeze)
            time.sleep(2.5)
            self.start()
            return True
        except Exception as e:
            self.scanner.log(f"✗ Stream restart failed: {e}")
            return False

    def get_resolution_info(self) -> dict:
        """Return fixed 1080p stream info."""
        return {
            "capture_width": self.capture_width,
            "capture_height": self.capture_height,
            "output_width": self.output_width,
            "actual_width": self.actual_width,
            "actual_height": self.actual_height,
            "fps": self.fps,
            "jpeg_quality": self.jpeg_quality,
        }
    
    def restart_stream(self):
        """Restart stream to apply new settings."""
        was_running = self.is_running()
        if was_running:
            self.stop()
            time.sleep(0.2)
            self.start()
    
    def _run_stream(self):
        """Background thread that continuously reads frames from capture card."""
        frame_count = 0
        fps_start_time = time.time()
        
        try:
            if not self.device:
                self.last_error = "No capture card device specified"
                return

            self.scanner.log(f"▶ Starting capture card stream from {self.device}")
            self.scanner.log(f"   Requested resolution: {self.capture_width}x{self.capture_height}")
            self.scanner.log(f"   Output width: {self.output_width}px")
            
            cap = cv2.VideoCapture(self.device)

            if not cap.isOpened():
                self.last_error = f"Failed to open capture card {self.device}"
                self.scanner.log(f"✗ Failed to open capture card {self.device}")
                with self.lock:
                    self.device = None  # Force re-search on next start()
                return

            # Set capture resolution
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.capture_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.capture_height)
            
            # Set capture properties for lower latency
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_FPS, 30)
            
            # Read actual resolution achieved
            self.actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.scanner.log(f"   Actual resolution: {self.actual_width}x{self.actual_height}")

            # Flush stale V4L2 buffers so first frames are fresh
            for _ in range(5):
                cap.grab()
            with self.lock:
                self.cap = cap

            consecutive_failures = 0
            max_failures_before_exit = 200  # ~2s of no frames then exit for restart (was 100)
            read_timeout_sec = 3.0  # cap.read() can block on USB stall; timeout and restart (was 2.0)
            read_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cap_read")

            while not self.stop_event.is_set():
                try:
                    future = read_executor.submit(cap.read)
                    ret, frame = future.result(timeout=read_timeout_sec)
                except FuturesTimeoutError:
                    self.last_error = "Capture card read timed out (USB stall?)"
                    self.scanner.log("✗ Video stream read timeout, thread exiting for restart")
                    break
                except Exception as e:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures_before_exit:
                        self.last_error = str(e)
                        self.scanner.log(f"✗ Video stream error, thread exiting: {e}")
                        break
                    time.sleep(0.01)
                    continue

                if not ret or frame is None:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures_before_exit:
                        self.last_error = "Capture card stopped returning frames"
                        self.scanner.log("✗ Video stream stuck (no frames), thread exiting for restart")
                        break
                    if consecutive_failures % 30 == 1:
                        try:
                            cap.grab()
                        except Exception:
                            pass
                    time.sleep(0.01)
                    continue
                consecutive_failures = 0

                # Keep full-res frame for alignment/sprocket detection
                raw_frame = frame

                # Resize for MJPEG stream output
                if self.output_width and frame.shape[1] != self.output_width:
                    height = int(frame.shape[0] * (self.output_width / frame.shape[1]))
                    frame = cv2.resize(frame, (self.output_width, height), interpolation=cv2.INTER_AREA)

                # Convert to JPEG (960px for stream)
                ret, jpeg_bytes = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
                if ret:
                    with self.lock:
                        self.latest_frame = jpeg_bytes.tobytes()
                        self.latest_raw_frame = raw_frame
                        self.last_frame_ts = time.time()
                
                # Calculate FPS
                frame_count += 1
                elapsed = time.time() - fps_start_time
                if elapsed >= 2.0:
                    self.fps = frame_count / elapsed
                    frame_count = 0
                    fps_start_time = time.time()

                # Small delay to avoid 100% CPU usage
                time.sleep(0.01)

        except Exception as e:
            self.last_error = str(e)
            try:
                self.scanner.log(f"✗ Capture card stream error: {e}")
            except Exception:
                pass
        finally:
            try:
                read_executor.shutdown(wait=False)
            except NameError:
                pass
            with self.lock:
                cap = self.cap
                self.cap = None
            if cap:
                try:
                    cap.release()
                except Exception:
                    pass
                # Let kernel/USB release the device before anything reopens it
                time.sleep(2.0)


class GPhotoPreviewStream:
    """
    USB live preview via gphoto2 --capture-preview.
    Useful when no HDMI capture card is connected.
    """

    STREAM_OUTPUT_WIDTH = 960

    def __init__(self, scanner, max_age: float = 3.0):
        self.scanner = scanner
        self.device = "gphoto2"
        self.output_width = self.STREAM_OUTPUT_WIDTH
        self.capture_width = 0
        self.capture_height = 0
        self.jpeg_quality = 80
        self.max_age = max_age

        self.latest_frame: Optional[bytes] = None
        self.latest_raw_frame: Optional[np.ndarray] = None
        self.last_frame_ts: float = 0.0

        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.last_error: Optional[str] = None

        self.actual_width = 0
        self.actual_height = 0
        self.fps = 0.0

    def is_running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def start(self) -> bool:
        if shutil.which("gphoto2") is None:
            self.last_error = "gphoto2 not found in PATH"
            self.scanner.log("✗ gphoto2 not found - cannot start USB live preview")
            return False

        with self.lock:
            if self.is_running():
                return True
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._run_stream, daemon=True)
            self.thread.start()
        return True

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1.2)
        self.thread = None

    def get_frame(self, timeout: float = 0.8) -> Optional[bytes]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.lock:
                frame = self.latest_frame
                ts = self.last_frame_ts
            if frame and (time.time() - ts) <= self.max_age:
                return frame
            time.sleep(0.05)
        return None

    def get_full_frame(self, timeout: float = 0.8) -> Optional[bytes]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.lock:
                raw = self.latest_raw_frame
                ts = self.last_frame_ts
            if raw is not None and (time.time() - ts) <= self.max_age:
                ret, jpeg = cv2.imencode('.jpg', raw, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if ret:
                    return jpeg.tobytes()
            time.sleep(0.05)
        return None

    def get_resolution_info(self) -> dict:
        return {
            "capture_width": self.capture_width,
            "capture_height": self.capture_height,
            "output_width": self.output_width,
            "actual_width": self.actual_width,
            "actual_height": self.actual_height,
            "fps": self.fps,
            "jpeg_quality": self.jpeg_quality,
        }

    def restart_stream(self):
        was_running = self.is_running()
        if was_running:
            self.stop()
            time.sleep(0.2)
            self.start()

    def _run_stream(self):
        frame_count = 0
        fps_start_time = time.time()
        consecutive_failures = 0
        max_failures_before_log = 10

        self.scanner.log("▶ Starting USB live preview stream via gphoto2")
        while not self.stop_event.is_set():
            lock_acquired = False
            try:
                lock_acquired = self.scanner.camera_op_lock.acquire(timeout=0.8)
                if not lock_acquired:
                    time.sleep(0.05)
                    continue

                result = subprocess.run(
                    ["gphoto2", "--capture-preview", "--stdout"],
                    capture_output=True,
                    timeout=3,
                )
                preview_bytes = result.stdout or b""

                if result.returncode != 0 and not preview_bytes:
                    consecutive_failures += 1
                    err = (result.stderr or b"").decode("utf-8", errors="ignore").strip()
                    if err:
                        self.last_error = err
                    if consecutive_failures >= max_failures_before_log and consecutive_failures % max_failures_before_log == 0:
                        self.scanner.log(f"⚠ USB preview retries: {consecutive_failures} ({self.last_error or 'unknown gphoto2 error'})")
                    time.sleep(0.1)
                    continue

                arr = np.frombuffer(preview_bytes, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is None:
                    consecutive_failures += 1
                    self.last_error = "gphoto2 returned non-image preview bytes"
                    time.sleep(0.08)
                    continue

                consecutive_failures = 0
                self.actual_width = int(img.shape[1])
                self.actual_height = int(img.shape[0])
                self.capture_width = self.actual_width
                self.capture_height = self.actual_height

                stream_img = img
                if self.output_width and img.shape[1] != self.output_width:
                    out_h = int(img.shape[0] * (self.output_width / img.shape[1]))
                    stream_img = cv2.resize(img, (self.output_width, out_h), interpolation=cv2.INTER_AREA)

                ok, jpeg = cv2.imencode('.jpg', stream_img, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
                if ok:
                    with self.lock:
                        self.latest_frame = jpeg.tobytes()
                        self.latest_raw_frame = img
                        self.last_frame_ts = time.time()

                frame_count += 1
                elapsed = time.time() - fps_start_time
                if elapsed >= 2.0:
                    self.fps = frame_count / elapsed
                    frame_count = 0
                    fps_start_time = time.time()

                time.sleep(0.03)
            except subprocess.TimeoutExpired:
                self.last_error = "gphoto2 preview timed out"
                time.sleep(0.1)
            except Exception as e:
                self.last_error = str(e)
                time.sleep(0.1)
            finally:
                if lock_acquired:
                    try:
                        self.scanner.camera_op_lock.release()
                    except Exception:
                        pass


class HybridPreviewStream:
    """Preview abstraction that can use capture card or gphoto2 live preview."""

    def __init__(self, scanner):
        self.scanner = scanner
        self.capture_card_stream = CaptureCardStream(scanner)
        self.gphoto_stream = GPhotoPreviewStream(scanner)
        self.active_backend: Optional[str] = None  # capture_card | gphoto
        self._last_error: Optional[str] = None

    @property
    def device(self):
        if self.active_backend == "gphoto":
            return self.gphoto_stream.device
        return self.capture_card_stream.device

    @property
    def last_error(self):
        if self.active_backend == "gphoto":
            return self.gphoto_stream.last_error or self._last_error
        if self.active_backend == "capture_card":
            return self.capture_card_stream.last_error or self._last_error
        return self._last_error

    @property
    def capture_width(self):
        stream = self._active_stream() or self.capture_card_stream
        return stream.capture_width

    @property
    def capture_height(self):
        stream = self._active_stream() or self.capture_card_stream
        return stream.capture_height

    @property
    def output_width(self):
        stream = self._active_stream() or self.capture_card_stream
        return stream.output_width

    @property
    def fps(self):
        stream = self._active_stream()
        return stream.fps if stream else 0.0

    def _active_stream(self):
        if self.active_backend == "capture_card":
            return self.capture_card_stream
        if self.active_backend == "gphoto":
            return self.gphoto_stream
        return None

    def is_running(self) -> bool:
        stream = self._active_stream()
        return bool(stream and stream.is_running())

    def _build_backend_order(self):
        pref = getattr(self.scanner, "preview_source_preference", "auto")
        if pref == "capture_card":
            return ["capture_card"]
        if pref == "gphoto":
            return ["gphoto"]
        return ["capture_card", "gphoto"]

    def _start_backend(self, backend: str) -> bool:
        if backend == "capture_card":
            if self.capture_card_stream.start():
                self.active_backend = "capture_card"
                self._last_error = None
                self.scanner.log("✓ Preview source: capture card")
                return True
            self._last_error = self.capture_card_stream.last_error
            return False

        if backend == "gphoto":
            if not self.scanner.check_camera(force=False):
                self._last_error = "Camera not connected for gphoto preview"
                return False
            if self.gphoto_stream.start():
                self.active_backend = "gphoto"
                self._last_error = None
                self.scanner.log("✓ Preview source: USB live preview (gphoto2)")
                return True
            self._last_error = self.gphoto_stream.last_error
            return False

        self._last_error = f"Unknown preview backend: {backend}"
        return False

    def start(self) -> bool:
        if self.is_running():
            return True

        errors = []
        for backend in self._build_backend_order():
            if self._start_backend(backend):
                return True
            errors.append(f"{backend}: {self._last_error or 'failed'}")

        self.active_backend = None
        self._last_error = "; ".join(errors) if errors else "No preview backend available"
        self.scanner.log(f"✗ Unable to start preview stream ({self._last_error})")
        return False

    def stop(self):
        self.capture_card_stream.stop()
        self.gphoto_stream.stop()
        self.active_backend = None

    def get_frame(self, timeout: float = 0.8) -> Optional[bytes]:
        if not self.is_running() and not self.start():
            return None

        stream = self._active_stream()
        if not stream:
            return None

        frame = stream.get_frame(timeout=timeout)
        if frame is not None:
            return frame

        # Auto mode failover: if capture card stalls, try gphoto preview.
        if self.scanner.preview_source_preference == "auto" and self.active_backend == "capture_card":
            self.capture_card_stream.stop()
            if self._start_backend("gphoto"):
                return self.gphoto_stream.get_frame(timeout=timeout)
        return None

    def get_full_frame(self, timeout: float = 0.8) -> Optional[bytes]:
        if not self.is_running() and not self.start():
            return None

        stream = self._active_stream()
        if not stream:
            return None

        frame = stream.get_full_frame(timeout=timeout)
        if frame is not None:
            return frame

        if self.scanner.preview_source_preference == "auto" and self.active_backend == "capture_card":
            self.capture_card_stream.stop()
            if self._start_backend("gphoto"):
                return self.gphoto_stream.get_full_frame(timeout=timeout)
        return None

    def get_resolution_info(self) -> dict:
        stream = self._active_stream() or self.capture_card_stream
        info = stream.get_resolution_info()
        info["backend"] = self.active_backend or "none"
        return info

    def restart_stream(self):
        stream = self._active_stream()
        if stream:
            stream.restart_stream()
        else:
            self.start()

# Arduino USB Vendor/Product IDs for automatic detection
ARDUINO_USB_IDS = {
    # Arduino Uno R3 and compatible
    (0x2341, 0x0043): "Arduino Uno R3",
    (0x2341, 0x0001): "Arduino Uno R3",
    (0x2A03, 0x0043): "Arduino Uno R3 (Clone)",
    # Arduino Uno R4 Minima
    (0x2341, 0x0069): "Arduino Uno R4 Minima",
    (0x2341, 0x0369): "Arduino Uno R4 Minima (Bootloader)",
    # Arduino Uno R4 WiFi
    (0x2341, 0x1002): "Arduino Uno R4 WiFi",
    (0x2341, 0x006D): "Arduino Uno R4 WiFi",
    # Generic CH340 (common clone chip)
    (0x1A86, 0x7523): "Arduino Clone (CH340)",
    # FTDI (used in some boards)
    (0x0403, 0x6001): "Arduino Compatible (FTDI)",
}
app = Flask(__name__)
app.config['SECRET_KEY'] = 'film-scanner-secret-key'
# Use threading mode (not eventlet/gevent) for compatibility when launched via subprocess
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
class FilmScanner:
    def __init__(self):
        # Arduino connection (USB Serial)
        self.arduino = None  # Serial connection
        self.arduino_port = None  # USB port
        self.arduino_board = "Unknown"
        
        # Scanner state
        self.roll_name = ""
        self.roll_folder = ""
        self.frame_count = 0
        self.strip_count = 0
        self.frames_in_strip = 0
        self.status_msg = "Ready"
        self.camera_connected = False
        self.camera_model = "Unknown"
        self.camera_error = None
        self.last_camera_check = 0
        self.viewfinder_enabled = False
        self.log_buffer = deque(maxlen=400)
        
        # Motor configuration
        self.fine_step = 8
        self.coarse_step = 192  # 3x larger for better coarse control
        self.step_delay = 800
        
        # Calibration data
        self.frame_advance = None  # Full frame advance (steps)
        self.half_frame_advance = None  # Half frame advance (2 half-frames, similar to 1 full)
        self.default_advance = 1200
        self.px_per_step = 3.0  # adaptive estimate for auto-align
        self.alignment_confidence = 0.0
        self.last_gap_px = None
        self.alignment_roi = None  # normalized ROI (fractions 0-1)
        self.alignment_min_confidence = 0.03
        
        # Position tracking
        self.position = 0
        self.frame_positions = []
        
        # Mode control
        self.mode = 'manual'
        self.auto_advance = True
        self.alignment_mode = "stream"  # stream or sprocket
        self.frame_mode = "full"  # full or half
        
        # Sprocket-based alignment (new hardware with visible sprocket holes)
        self.sprocket_detection_enabled = True  # Enable sprocket hole detection
        self.sprocket_pitch_px = None  # Measured pixels per sprocket pitch
        self.sprocket_pitch_px_smoothed = None  # Running average for stable advance (reduces overshoot/undershoot)
        self.px_per_mm = None  # Pixels per millimeter (from sprocket calibration)
        self.last_sprocket_result = None  # Last sprocket detection result
        
        # Scanner mode: "35mm" (Arduino motor control) or "120" (hand feed, no Arduino)
        self.scanner_mode = "35mm"
        # Auto-alignment toggle: when False, skip all auto alignment
        self.auto_alignment_enabled = True
        
        # Auto-capture mode: continuous scanning with automatic capture after alignment
        self.auto_capture_enabled = False  # Toggle for automatic continuous capture
        self.auto_capture_delay = 3.0  # Delay after capture before advancing (exposure time)
        
        # ScanLight RGB backlight control
        self.scanlight = ScanLight()
        self.scanlight_connected = False
        self.scanlight_profiles = {
            "Color": {"r": 255, "g": 255, "b": 255, "description": "Full spectrum white for color film"},
            "B&W": {"r": 255, "g": 255, "b": 255, "description": "Balanced white for black & white film"}
        }
        self.scanlight_current_profile = "Color"
        self.scanlight_rgb = {"r": 255, "g": 255, "b": 255}  # Current RGB values
        
        # State persistence
        self.state_file = None
        self.settings_dir = Path.home() / ".film_scanner"
        self._initialize_default_session()

        # Motor direction: SINGLE SOURCE OF TRUTH for advance/backup (frame advance, alignment).
        # advance_reversed=False → advance='h', backup='H'. If your motor goes the wrong way, set True or use UI toggle.
        self.motor_advance_reversed = False
        self._load_motor_config()

        # Lock for thread safety
        self.lock = threading.Lock()
    
        # RLock to prevent gphoto2 conflicts across routes (reentrant for recursive calls)
        self.camera_op_lock = threading.RLock()
        # Lock for entire capture+advance flow so we never run two at once (avoids double capture / partial advance)
        self.capture_workflow_lock = threading.Lock()

        # Stream control:
        # - capture card when available
        # - optional gphoto2 USB live preview (e.g. Fujifilm X-T5 without capture card)
        self.stream_enabled = True
        preview_pref = os.environ.get("FS_PREVIEW_SOURCE", "auto").strip().lower()
        if preview_pref not in ("auto", "capture_card", "gphoto"):
            preview_pref = "auto"
        self.preview_source_preference = preview_pref

        # Capture card device placeholder (legacy field retained for compatibility)
        self.capture_card_device = None

        # Live preview stream abstraction (capture card and/or gphoto2)
        self.preview_stream = HybridPreviewStream(self)

        # Load persisted alignment settings (best-effort)
        try:
            self._load_alignment_config()
        except Exception as e:
            print(f"⚠ Failed to load alignment config: {e}")

    # Lightweight in-memory log for UI consumption
    def log(self, msg: str):
        try:
            ts = datetime.now().strftime("%H:%M:%S")
            line = f"{ts} | {msg}"
        except Exception:
            line = msg
        print(line)
        try:
            self.log_buffer.append(line)
        except Exception:
            pass

    def get_logs(self, limit: int = 200):
        try:
            limit = max(1, min(int(limit), 400))
        except Exception:
            limit = 200
        return list(self.log_buffer)[-limit:]

    def _initialize_default_session(self):
        """Create/resume the default scan session without requiring user input."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        base_folder = os.path.expanduser("~/scans")
        session_name = "current-session"

        self.roll_name = session_name
        self.roll_folder = os.path.join(base_folder, date_str, session_name)
        os.makedirs(self.roll_folder, exist_ok=True)
        self.state_file = os.path.join(self.roll_folder, ".scan_state.json")

        if os.path.exists(self.state_file):
            self.load_state(self.roll_folder)
            self.status_msg = "Resumed current session"
        else:
            self.save_state()
            self.status_msg = "Ready"

    def ensure_preview_stream(self) -> bool:
        """
        Ensure preview stream is running (capture card or gphoto2).
        Returns True if stream is running or successfully started, False otherwise.
        """
        try:
            return self.preview_stream.start()
        except Exception as e:
            self.log(f"✗ Failed to start preview stream: {e}")
            return False

    def stop_preview_stream(self):
        """Stop preview stream (safe to call even if not running)."""
        try:
            self.preview_stream.stop()
        except Exception as e:
            self.log(f"✗ Failed to stop preview stream: {e}")

    def get_alignment_frame(self, timeout: float = 1.0) -> Tuple[Optional[bytes], bool]:
        """
        Get full-resolution frame from active preview backend for alignment.
        Returns (frame_bytes, used_stream_flag).
        
        NOTE: This always returns the original, non-inverted frame.
        The 'invert' setting in the UI is for viewing only and does
        NOT affect alignment detection.
        """
        # Get full-res frame from live stream (not the 960px MJPEG version)
        if self.ensure_preview_stream():
            frame = self.preview_stream.get_full_frame(timeout=timeout)
            if frame:
                return frame, True

        # Fallback: grab a fresh frame directly
        try:
            frame = self.capture_preview_bytes()
            if frame:
                return frame, False
        except Exception as e:
            self.log(f"✗ Fallback capture failed: {e}")

            return None, False
    
    def identify_arduino_board(self, port_info):
        """Identify Arduino board type from USB port info"""
        try:
            vid = port_info.vid
            pid = port_info.pid
            
            if vid and pid:
                board_name = ARDUINO_USB_IDS.get((vid, pid))
                if board_name:
                    return board_name
                
                # Check for Arduino vendor ID
                if vid == 0x2341:
                    return "Arduino (Unknown Model)"
            
            # Fallback to description parsing
            desc = getattr(port_info, 'description', '') or ''
            if 'R4' in desc.upper():
                return "Arduino Uno R4"
            elif 'UNO' in desc.upper():
                return "Arduino Uno"
            
            return None
        except Exception:
            return None
    
    def find_arduino(self):
        """Find Arduino on available USB Serial ports"""
        # Close existing connection if any
        if self.arduino:
            try:
                self.arduino.close()
            except:
                pass
            self.arduino = None
            self.arduino_board = "Unknown"
        
        ports = list(serial.tools.list_ports.comports())
        
        # Add Raspberry Pi serial ports if they exist
        pi_ports = ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0', '/dev/ttyUSB1', 
                    '/dev/serial0', '/dev/ttyAMA0']
        for port_path in pi_ports:
            if os.path.exists(port_path):
                # Check if this port is already in the list
                existing = [p for p in ports if hasattr(p, 'device') and p.device == port_path]
                if not existing:
                    class SimplePort:
                        def __init__(self, device):
                            self.device = device
                            self.vid = None
                            self.pid = None
                            self.description = "Serial Port"
                    ports.append(SimplePort(port_path))
        
        # Sort ports to prioritize known Arduino ports
        def port_priority(p):
            board = self.identify_arduino_board(p) if hasattr(p, 'vid') else None
            if board:
                return 0  # Known Arduino boards first
            device = getattr(p, 'device', str(p))
            if 'ACM' in device or 'USB' in device:
                return 1  # Common Arduino ports
            return 2  # Other ports
        
        ports = sorted(ports, key=port_priority)
        
        print("🔍 Scanning for Arduino boards...")
        
        for port in ports:
            device = port.device if hasattr(port, 'device') else str(port)
            board_id = self.identify_arduino_board(port) if hasattr(port, 'vid') else None
            
            if board_id:
                print(f"   Found: {board_id} on {device}")
            
            try:
                # Open serial connection
                ser = serial.Serial(device, 115200, timeout=3)
                
                # Wait for Arduino to reset after connection
                # R4 native USB may need longer initialization
                is_r4 = board_id and 'R4' in board_id
                reset_delay = 3.0 if is_r4 else 2.5
                time.sleep(reset_delay)
                
                # Clear any startup messages
                ser.reset_input_buffer()
                time.sleep(0.1)
                
                # Send status query
                ser.write(b'?\n')
                time.sleep(0.5)  # R4 may need slightly longer response time
                response = ser.read(500).decode('ascii', errors='ignore')
                
                # Check for valid Film Scanner firmware response
                if 'Film' in response or 'READY' in response or 'Position' in response:
                    self.arduino = ser
                    self.arduino_port = device
                    
                    # Determine board type from response
                    if 'UNO R4' in response or 'R4' in response:
                        self.arduino_board = "Arduino Uno R4"
                    elif 'UNO R3' in response or 'R3' in response:
                        self.arduino_board = "Arduino Uno R3"
                    elif board_id:
                        self.arduino_board = board_id
                    else:
                        self.arduino_board = "Arduino Compatible"
                    
                    # Configure coarse step size
                    time.sleep(0.1)
                    self.arduino.write(f'l{self.coarse_step}\n'.encode())
                    time.sleep(0.1)
                    
                    print(f"✓ Connected: {self.arduino_board} on {device}")
                    self.broadcast_status()
                    return True
                
                ser.close()
            except serial.SerialException as e:
                # Port busy or access denied
                if 'PermissionError' in str(e) or 'Access' in str(e):
                    print(f"   ⚠ Port {device} in use by another application")
                else:
                    print(f"   ✗ {device}: {e}")
                continue
            except Exception as e:
                print(f"   ✗ {device}: {e}")
                continue
        
        print("✗ No Arduino found with Film Scanner firmware")
        self.arduino = None
        self.arduino_port = None
        self.arduino_board = "Unknown"
        return False
    
    def verify_connection(self):
        """Verify Arduino connection is alive"""
        if not self.arduino:
            return False
        
        try:
            self.arduino.timeout = 0.1
            self.arduino.reset_input_buffer()
            self.arduino.write(b'?\n')
            time.sleep(0.2)
            response = self.arduino.read(100).decode('ascii', errors='ignore')
            
            # Check if we got a valid response
            if response and ('Position' in response or 'READY' in response or 'Film' in response):
                return True
            return False
                
        except Exception as e:
            print(f"✗ Connection verification failed: {e}")
            return False
    
    def ensure_connection(self):
        """Ensure Arduino is connected, reconnect if needed"""
        if not self.arduino or not self.verify_connection():
            print("🔌 Attempting to reconnect to Arduino...")
            if self.find_arduino():
                print("✓ Reconnected to Arduino")
                return True
            else:
                print("✗ Failed to reconnect to Arduino")
                self.arduino = None
                self.arduino_port = None
                return False
        return True
    
    def send(self, cmd, retry=True, update_position=True):
        """Send command to Arduino with error handling and retry"""
        # Quick check - don't verify connection on every command (causes disconnects)
        if not self.arduino:
            print(f"✗ Cannot send command '{cmd}': No Arduino connection")
            self.broadcast_status()
            return False
        
        try:
            self.arduino.reset_input_buffer()
            self.arduino.write(f"{cmd}\n".encode())
            
            # Minimal delay for command processing
            time.sleep(0.05)
            
            # Only update position for movement commands if requested
            if update_position and (cmd in ['f', 'F', 'b', 'B'] or cmd.startswith('H') or cmd.startswith('Z')):
                # Reduced wait time for better responsiveness
                time.sleep(0.15)  # Shorter wait for motor to start moving
                
                # Query position without blocking
                self.arduino.write(b'?\n')
                time.sleep(0.1)
                response = self.arduino.read(200).decode('ascii', errors='ignore')
                
                for line in response.split('\n'):
                    if 'Position' in line:
                        try:
                            pos_str = line.split(':')[1].strip().split()[0]
                            self.position = int(pos_str)
                        except Exception as e:
                            # Silently ignore parsing errors for responsiveness
                            pass
            
            return True
            
        except (serial.SerialException, OSError) as e:
            print(f"✗ Serial error sending '{cmd}': {e}")
            
            # Mark connection as bad
            try:
                if self.arduino:
                    self.arduino.close()
            except:
                pass
            self.arduino = None
            
            # Try to reconnect and retry command once
            if retry:
                print("🔄 Retrying command after reconnection...")
                time.sleep(0.5)
                if self.find_arduino():
                    print("✓ Reconnected, retrying command...")
                    return self.send(cmd, retry=False, update_position=update_position)
            
            self.broadcast_status()
            return False
            
        except Exception as e:
            print(f"✗ Unexpected error sending '{cmd}': {e}")
            self.broadcast_status()
            return False
    
    def send_and_wait(self, cmd, timeout: float = 10.0) -> bool:
        """
        Send a motor command and block until the Arduino confirms completion.
        
        The Arduino sends 'POS:<number>' after every move_steps() call.
        Waiting for this prevents command stacking: if we send the next move
        before the first finishes, commands pile up in the serial buffer and
        the motor runs much longer than intended.
        
        Returns True if the command completed, False on error/timeout.
        """
        if not self.arduino:
            return False
        
        try:
            # Drain any stale data so we only see the response to THIS command
            self.arduino.reset_input_buffer()
            self.arduino.write(f"{cmd}\n".encode())
            
            # Wait for POS: response (motor move complete) or timeout
            deadline = time.time() + timeout
            buf = ""
            while time.time() < deadline:
                if self.arduino.in_waiting:
                    chunk = self.arduino.read(self.arduino.in_waiting).decode('ascii', errors='ignore')
                    buf += chunk
                    # Check for POS: line which signals move is done
                    for line in buf.split('\n'):
                        line = line.strip()
                        if line.startswith('POS:'):
                            try:
                                self.position = int(line.split(':')[1].strip())
                            except (ValueError, IndexError):
                                pass
                            return True
                        elif line == 'LOCKED':
                            self.log("⚠ Motor is locked")
                            return False
                else:
                    time.sleep(0.01)
            
            # Timeout - motor may still be moving
            self.log(f"⚠ Timed out waiting for motor completion ({cmd})")
            return False
            
        except (serial.SerialException, OSError) as e:
            print(f"✗ Serial error in send_and_wait '{cmd}': {e}")
            try:
                if self.arduino:
                    self.arduino.close()
            except Exception:
                pass
            self.arduino = None
            return False

    def check_camera(self, retry_with_usb_clear=True, max_retries=3, force=False):
        """Check if camera is connected with detailed logging

        Args:
            retry_with_usb_clear: If camera not found, clear USB and retry
            max_retries: Number of retry attempts (some cameras need multiple tries)
            force: If True, bypass rate limiting and check immediately
            
        IMPORTANT: Running gphoto2 commands too frequently can destabilize some
        cameras (including occasional date/time resets). This is rate-limited.
        """
        # Rate limiting: Don't check camera more than once every 60 seconds
        # unless forced. Frequent gphoto2 calls can disturb camera state.
        CAMERA_CHECK_INTERVAL = 60  # seconds
        
        current_time = time.time()
        if not force and self.camera_connected:
            # If camera was already connected and we checked recently, skip
            if (current_time - self.last_camera_check) < CAMERA_CHECK_INTERVAL:
                return self.camera_connected
        
        self.last_camera_check = current_time
        
        try:
            # If another camera operation is in progress (preview/capture), don't interrupt it.
            # Use non-blocking acquire to check if lock is held
            if not self.camera_op_lock.acquire(blocking=False):
                # Lock is held by another operation, return cached state
                return self.camera_connected
            # We got the lock, release it immediately - we just wanted to check
            self.camera_op_lock.release()
            
            print("\n📷 Checking camera connection...")
            
            # First, check if a known camera brand is visible on USB
            try:
                lsusb_result = subprocess.run(
                    ["lsusb"],
                    capture_output=True, text=True, timeout=5
                )
                camera_on_usb = False
                if lsusb_result.returncode == 0:
                    for line in lsusb_result.stdout.split('\n'):
                        if _camera_brand_from_lsusb_line(line):
                            print(f"   USB: {line.strip()}")
                            camera_on_usb = True
                    if not camera_on_usb:
                        print("   USB: No known camera device found on USB bus")
            except Exception as e:
                print(f"   USB check error: {e}")
            
            # Try detection with retries (some camera USB/PTP stacks are finicky)
            for attempt in range(max_retries):
                if attempt > 0:
                    print(f"   Retry {attempt}/{max_retries-1}...")
                    time.sleep(1.5)  # Camera often needs a pause between attempts
                
                # Run gphoto2 --auto-detect
                result = subprocess.run(
                    ["gphoto2", "--auto-detect"],
                    capture_output=True, timeout=15, text=True
                )
                
                # Log the full output for debugging
                print(f"   gphoto2 --auto-detect (attempt {attempt+1}):")
                for line in result.stdout.strip().split('\n'):
                    print(f"      {line}")
                if result.stderr:
                    print(f"   stderr: {result.stderr.strip()}")
                
                if result.returncode == 0 and "usb" in result.stdout.lower():
                    lines = result.stdout.strip().splitlines()
                    for line in lines:
                        if "usb:" in line.lower():
                            self.camera_connected = True
                            self.camera_model = line.strip()
                            self.camera_error = None
                            print(f"✓ Camera detected: {self.camera_model}")
                            return True
                
                # If first attempt failed and retry enabled, clear USB
                if attempt == 0 and retry_with_usb_clear:
                    print("   Camera not detected, clearing USB...")
                    clear_usb_for_camera()
            
            # All retries failed
            self.camera_connected = False
            self.camera_error = "Camera not detected after multiple attempts. Check USB and PTP mode."
            print("✗ Camera not detected after all attempts")
            print("   Troubleshooting:")
            print("   - Ensure camera is ON and in PTP mode")
            print("   - Try unplugging and replugging USB cable")
            print("   - Press FIX CAM on touchscreen")
                
        except subprocess.TimeoutExpired:
            print("✗ Camera detection timeout - USB may be blocked")
            self.camera_error = "Detection timeout"
            self.camera_connected = False
        except Exception as e:
            print(f"✗ Error checking camera: {e}")
            self.camera_error = str(e)
            
        return self.camera_connected
    def _kill_gphoto2(self):
        """Thoroughly kill any gphoto2 processes and wait for USB release"""
        try:
            # Kill gracefully first
            subprocess.run(["killall", "gphoto2"], 
                         capture_output=True, timeout=1)
            time.sleep(0.2)
            # Force kill any remaining
            subprocess.run(["killall", "-9", "gphoto2"], 
                         capture_output=True, timeout=1)
            time.sleep(0.2)
            
            # Kill all gvfs processes that can interfere with camera USB access
            gvfs_processes = [
                "gvfs-gphoto2-volume-monitor",
                "gvfsd-gphoto2",
                "gvfsd-mtp",
                "gvfs-mtp-volume-monitor",
                "gvfsd-ptp",
                "gvfs-ptp-volume-monitor",
            ]
            for proc in gvfs_processes:
                try:
                    subprocess.run(["killall", proc], 
                                 capture_output=True, timeout=1)
                except:
                    pass
            time.sleep(0.3)
            
            # Kill any PTP processes that might be hanging (macOS)
            subprocess.run(["killall", "-9", "PTPCamera"], 
                         capture_output=True, timeout=1)
            time.sleep(0.3)
            
            # Total wait: ~1 second for USB to fully release
        except:
            pass
    
    def autofocus(self):
        """Trigger camera autofocus
        
        NOTE: Not currently used. Cameras with Continuous AF (like R100 in CAF mode)
        handle focus automatically. This method is kept for compatibility with cameras
        that might need explicit AF triggering.
        """
        try:
            print("📷 Triggering autofocus...")
            self._kill_gphoto2()
            
            result = subprocess.run(
                ["gphoto2", "--set-config", "autofocus=1"],
                capture_output=True, timeout=10, text=True
            )
            
            if result.returncode == 0:
                print("✓ Autofocus triggered successfully")
                time.sleep(2.0)  # Give camera time to focus
                return True
            else:
                print(f"✗ Autofocus failed (return code: {result.returncode})")
                if result.stderr:
                    error_msg = result.stderr.strip()
                    print(f"   Error: {error_msg}")
                    
                    # Provide specific guidance based on error
                    if "not found" in error_msg.lower():
                        print("   → Camera doesn't have 'autofocus' config option")
                        print("   → Use manual focus or camera's AF button")
                    elif "read-only" in error_msg.lower():
                        print("   → Autofocus setting is read-only on this camera")
                    elif "PTP" in error_msg or "claim" in error_msg.lower():
                        print("   → Camera connection issue - check USB mode is PTP")
                
                return False
                
        except subprocess.TimeoutExpired:
            print("✗ Autofocus timeout - camera not responding")
            self._kill_gphoto2()
            return False
        except Exception as e:
            print(f"✗ Autofocus error: {e}")
            return False
    
    def get_camera_settings(self):
        """Fetch basic exposure settings (best-effort; keys may vary by camera)."""
        key_candidates = {
            "aperture": ("aperture", "f-number", "fnumber"),
            "iso": ("iso", "isoauto", "autoiso"),
            "shutterspeed": ("shutterspeed", "shutter-speed", "shutterspeed2"),
        }
        values = {}

        def read_config(cfg_key):
            try:
                result = subprocess.run(
                    ["gphoto2", "--get-config", cfg_key],
                    capture_output=True,
                    text=True,
                    timeout=8,
                )
                if result.returncode == 0 and result.stdout:
                    for line in result.stdout.splitlines():
                        if "Current:" in line:
                            return line.split("Current:", 1)[1].strip()
            except Exception:
                return None
            return None

        for name, candidates in key_candidates.items():
            value = None
            for key in candidates:
                value = read_config(key)
                if value is not None:
                    break
            values[name] = value

        return values
    
    def check_viewfinder_state(self):
        """
        Viewfinder state.
        Returns True when preview streaming is enabled.
        """
        self.viewfinder_enabled = self.stream_enabled
        return True

    def enable_viewfinder(self):
        """
        Legacy compatibility method.
        Preview stream is managed separately and remains always-on when enabled.
        """
        return self.stream_enabled
    
    def disable_viewfinder(self):
        """
        Legacy compatibility method.
        Preview stream is managed separately and remains always-on when enabled.
        """
        return self.stream_enabled
    
    def capture_image(self, retry=True):
        """Capture image to camera SD card with exclusive access"""
        # Preview stream runs independently from still capture.

        # Ensure exclusive access - RLock allows recursive acquisition by same thread
        with self.camera_op_lock:
            try:
                # Clean any stray gphoto2 from previous ops
                self._kill_gphoto2()
                
                # Best-effort: ensure capture goes to camera SD card (capturetarget=1)
                try:
                    subprocess.run(
                        ["gphoto2", "--set-config", "capturetarget=1"],
                        capture_output=True, timeout=5, text=True
                    )
                except Exception as e:
                    print(f"⚠ capturetarget set failed (continuing): {e}")
                
                print("\n📷 Capturing image...")
                result = subprocess.run(
                    ["gphoto2", "--capture-image"],
                    capture_output=True, timeout=30, text=True
                )
                print(f"   Return code: {result.returncode}")
                if result.stdout:
                    print(f"   stdout: {result.stdout.strip()}")
                if result.stderr:
                    print(f"   stderr: {result.stderr.strip()}")
                # Success detection: allow some transient non-zero errors if shutter likely fired
                success_code = (result.returncode == 0)
                non_fatal = False
                if not success_code and result.stderr:
                    low = result.stderr.lower()
                    non_fatal = any(k in low for k in ["ptp i/o error", "device busy", "resource busy", "usb device reset", "i/o in progress"])
                if success_code or non_fatal:
                    print("✓ Capture triggered")
                    return True
                # If failed and retry is allowed, try once more after a short reset
                if retry:
                    print("↻ Retry capture after resetting gphoto2...")
                    self._kill_gphoto2()
                    time.sleep(0.5)
                    return self.capture_image(retry=False)
                print("✗ Capture failed")
                return False
            except Exception as e:
                print(f"✗ Capture error: {e}")
                self._kill_gphoto2()
                return False

    def capture_preview_bytes(self):
        """
        Get preview frame from active preview backend.
        """
        if not self.ensure_preview_stream():
            raise RuntimeError("Unable to start preview stream")
        frame = self.preview_stream.get_frame(timeout=2.0)
        if not frame:
            raise RuntimeError("No frame available from preview backend")
        return frame

    def sample_preview_rgb(self, norm_x: float, norm_y: float, sample_radius: int = 2):
        """
        Sample RGB from the active preview stream at normalized coordinates.
        Returns dict with rgb values in 0-255 range and sampling metadata.
        """
        frame = self.preview_stream.get_frame(timeout=1.5)
        if not frame:
            raise RuntimeError("No frame available from preview stream")

        arr = np.frombuffer(frame, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise RuntimeError("Failed to decode preview frame")

        h, w = img.shape[:2]
        if w <= 0 or h <= 0:
            raise RuntimeError("Invalid preview frame dimensions")

        x = int(round(max(0.0, min(1.0, norm_x)) * (w - 1)))
        y = int(round(max(0.0, min(1.0, norm_y)) * (h - 1)))
        radius = max(0, min(int(sample_radius), 25))

        x0 = max(0, x - radius)
        x1 = min(w - 1, x + radius)
        y0 = max(0, y - radius)
        y1 = min(h - 1, y + radius)

        roi = img[y0:y1 + 1, x0:x1 + 1]
        if roi.size == 0:
            raise RuntimeError("Sampling region was empty")

        # OpenCV uses BGR ordering; convert to RGB-like output expected by users.
        b_mean = float(np.mean(roi[:, :, 0]))
        g_mean = float(np.mean(roi[:, :, 1]))
        r_mean = float(np.mean(roi[:, :, 2]))

        return {
            "rgb": {
                "r": int(round(r_mean)),
                "g": int(round(g_mean)),
                "b": int(round(b_mean)),
            },
            "pixel": {"x": x, "y": y},
            "sample_box": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
            "frame_size": {"width": w, "height": h},
        }

    def auto_align(self, max_step=600, min_step=50, margin_px=60):
        """
        Auto alignment - SINGLE PASS approach.
        
        Film moves LEFT to RIGHT (forward = right).
        
        FULL FRAME MODE (test align button):
        1. Detect where the gap is
        2. Calculate ONE move to push it out of frame
        3. Execute the move
        4. Done (no iterative chasing)
        
        HALF FRAME MODE:
        - Centers the gap in the frame (single calculation)
        """
        self.log(f"▶ Auto-align [{self.frame_mode}] starting...")
        
        # Get frame
        frame_bytes, stream_used = self.get_alignment_frame(timeout=1.0)
        if not frame_bytes:
            self.log("✗ No frame from preview stream")
            return False, "No frame", {"mode": "error", "total_steps": 0, "confidence": 0}
        
        self.log(f"   Got frame: {len(frame_bytes)} bytes (stream={stream_used})")

        try:
            result = detect_frame_gap(
                frame_bytes,
                roi={"x0": 0.05, "x1": 0.95, "y0": 0.15, "y1": 0.85},
                expected_gap_fraction=None,
                gap_window_fraction=1.0,
                mean_threshold=0.70,  # Higher - gaps must be clearly bright (white)
                std_threshold=0.25,   # Tighter - gaps must be uniform
                min_gap_width=6,      # Wider minimum to avoid noise
                max_gap_width=400,
                use_edge_detection=True,
            )
        except Exception as e:
            self.log(f"✗ Detection error: {e}")
            return False, f"Detection error: {e}", {"mode": "error", "total_steps": 0, "confidence": 0}

        debug = result.debug_info or {}
        gap_count = int(debug.get("gap_count", 0))
        confidence = float(result.confidence) if result.confidence else 0.0
        
        self.alignment_confidence = confidence
        self.last_gap_px = int(result.gap_x) if result.gap_x else None

        # Get frame dimensions
        lit_x0 = debug.get("lit_region", {}).get("x0", 0)
        lit_x1 = debug.get("lit_region", {}).get("x1", 640)
        frame_width = max(lit_x1 - lit_x0, 100)
        center_x = frame_width / 2

        # === FULL FRAME MODE - STRICT SINGLE-GAP DETECTION ===
        if self.frame_mode == "full":
            # Scan entire frame but be VERY strict about what qualifies as a gap:
            # - Must be in the TOP 20% of brightness (gaps are the brightest thing)
            # - Must have very low std (< 0.08) - gaps are perfectly uniform
            # - Must be at least 8 pixels wide (consecutive)
            # Find the SINGLE best gap and move based on its position
            
            total_steps = 0
            max_attempts = 5
            
            for attempt in range(max_attempts):
                # Get fresh frame (use initial frame_bytes on first attempt)
                if attempt > 0:
                    time.sleep(0.3)
                    frame_bytes, _ = self.get_alignment_frame(timeout=0.8)
                    if not frame_bytes:
                        continue
                # else: use frame_bytes from line 1075
                
                # Decode frame
                try:
                    import numpy as np
                    import cv2
                    nparr = np.frombuffer(frame_bytes, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if img is None:
                        continue
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    h, w = gray.shape
                    
                    # Crop to middle 70% vertically (avoid camera overlays)
                    y_start = int(h * 0.15)
                    y_end = int(h * 0.85)
                    cropped = gray[y_start:y_end, :]
                    
                    # Compute per-column stats
                    col_mean = cropped.mean(axis=0) / 255.0  # 0-1 scale
                    col_std = cropped.std(axis=0) / 255.0   # 0-1 scale
                    
                    # STRICT gap criteria:
                    # 1. Brightness must be in TOP 20% of all column brightnesses
                    brightness_threshold = np.percentile(col_mean, 80)
                    # 2. But also must be at least 60% absolute brightness
                    brightness_threshold = max(brightness_threshold, 0.60)
                    # 3. Std must be very low (uniform from top to bottom)
                    std_threshold = 0.08
                    
                    # Find gap candidates
                    gap_mask = (col_mean >= brightness_threshold) & (col_std <= std_threshold)
                    
                    # Find consecutive runs of gap columns
                    gap_regions = []
                    in_gap = False
                    gap_start = 0
                    
                    for i in range(len(gap_mask)):
                        if gap_mask[i] and not in_gap:
                            gap_start = i
                            in_gap = True
                        elif not gap_mask[i] and in_gap:
                            gap_end = i
                            gap_width = gap_end - gap_start
                            if gap_width >= 8:  # Minimum 8 pixels wide
                                gap_center = (gap_start + gap_end) / 2
                                gap_brightness = col_mean[gap_start:gap_end].mean()
                                gap_uniformity = 1.0 - col_std[gap_start:gap_end].mean()  # Higher = more uniform
                                gap_score = gap_brightness * gap_uniformity
                                gap_regions.append({
                                    "start": gap_start,
                                    "end": gap_end,
                                    "center": gap_center,
                                    "width": gap_width,
                                    "brightness": gap_brightness,
                                    "score": gap_score,
                                })
                            in_gap = False
                    
                    # Handle gap at end of frame
                    if in_gap:
                        gap_end = len(gap_mask)
                        gap_width = gap_end - gap_start
                        if gap_width >= 8:
                            gap_center = (gap_start + gap_end) / 2
                            gap_brightness = col_mean[gap_start:gap_end].mean()
                            gap_uniformity = 1.0 - col_std[gap_start:gap_end].mean()
                            gap_score = gap_brightness * gap_uniformity
                            gap_regions.append({
                                "start": gap_start,
                                "end": gap_end,
                                "center": gap_center,
                                "width": gap_width,
                                "brightness": gap_brightness,
                                "score": gap_score,
                            })
                    
                    self.log(f"   [{attempt+1}] Found {len(gap_regions)} gap regions (thresh: bright>{brightness_threshold:.2f}, std<{std_threshold})")
                    
                    # No gaps found = ALIGNED!
                    if not gap_regions:
                        self.status_msg = "✓ Aligned"
                        self.log(f"   ✓ Aligned! No gaps detected. Total: {total_steps} steps")
                        self.alignment_confidence = 1.0
                        return True, "Aligned", {
                            "mode": "aligned",
                            "total_steps": total_steps,
                            "attempts": attempt + 1,
                            "confidence": 1.0,
                        }
                    
                    # Pick the SINGLE BEST gap (highest score)
                    best_gap = max(gap_regions, key=lambda g: g["score"])
                    gap_center = best_gap["center"]
                    gap_width = best_gap["width"]
                    gap_fraction = gap_center / w  # 0 = left edge, 1 = right edge
                    
                    self.log(f"   Best gap at {gap_fraction:.1%} (x={gap_center:.0f}, width={gap_width}, score={best_gap['score']:.3f})")
                    
                    # FULL FRAME: ALWAYS move FORWARD to push gap out left
                    # Bigger steps when gap is far from left edge
                    gap_start_x = best_gap["start"]
                    if gap_start_x < w * 0.08:
                        steps = 25   # Almost out
                    elif gap_start_x < w * 0.20:
                        steps = 60   # Near left
                    elif gap_start_x < w * 0.40:
                        steps = 100  # Getting there
                    else:
                        steps = 150  # Far from left - big push
                    
                    self.log(f"   Gap at {gap_fraction:.0%} -> FORWARD {steps}")
                    moved = self.send_and_wait(self.cmd_advance(steps))
                    if not moved:
                        return False, "Motor failed", {"mode": "error", "total_steps": total_steps, "confidence": 0}
                    total_steps += steps
                    time.sleep(0.1)  # Brief settle after motor confirmed done
                    
                except Exception as e:
                    self.log(f"   Error: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            # === FINAL EDGE FINE-TUNE (BOTH SIDES) - ENHANCED ===
            # After main alignment, check BOTH left and right edges
            # and push out any remaining gaps with adaptive thresholds
            # IMPORTANT: Check edges of the FILM area, not the total image (which has black borders)
            self.log(f"   Final edge fine-tune (both sides)...")
            
            # Use multi-pass approach with progressively stricter detection
            for fine_attempt in range(8):  # Increased attempts for better coverage
                time.sleep(0.15)  # Brief settle (send_and_wait confirmed motor done)
                fine_frame, _ = self.get_alignment_frame(timeout=0.8)
                if not fine_frame:
                    continue
                
                try:
                    import numpy as np
                    import cv2
                    nparr = np.frombuffer(fine_frame, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if img is None:
                        continue
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    h, w = gray.shape
                    
                    # Use the alignment ROI to find the FILM area (not the black borders)
                    roi = self.alignment_roi or {"x0": 0.1, "x1": 0.9, "y0": 0.1, "y1": 0.9}
                    film_x0 = int(w * roi.get("x0", 0.1))
                    film_x1 = int(w * roi.get("x1", 0.9))
                    film_y0 = int(h * roi.get("y0", 0.1))
                    film_y1 = int(h * roi.get("y1", 0.9))
                    
                    # Crop to just the film area
                    film_region = gray[film_y0:film_y1, film_x0:film_x1]
                    film_h, film_w = film_region.shape
                    
                    # Apply light median blur to reduce noise
                    film_region = cv2.medianBlur(film_region, 3)
                    
                    # === ADAPTIVE THRESHOLDS ===
                    # Start strict, relax if no gaps found (prevents over-correction)
                    if fine_attempt < 3:
                        # First passes: strict detection (catch obvious gaps)
                        brightness_thresh = 0.55
                        std_thresh = 0.10
                        min_gap_px = 5
                    elif fine_attempt < 6:
                        # Middle passes: moderate detection (catch smaller gaps)
                        brightness_thresh = 0.50
                        std_thresh = 0.12
                        min_gap_px = 3
                    else:
                        # Final passes: sensitive detection (catch tiny gaps)
                        brightness_thresh = 0.45
                        std_thresh = 0.15
                        min_gap_px = 2
                    
                    # Compute overall brightness stats for adaptive thresholding
                    film_brightness = film_region.mean() / 255.0
                    film_std = film_region.std() / 255.0
                    
                    # If film is generally bright, increase thresholds
                    if film_brightness > 0.6:
                        brightness_thresh = max(brightness_thresh, film_brightness * 0.85)
                    
                    # === LEFT EDGE CHECK (first 12%) ===
                    left_edge_width = max(int(film_w * 0.12), 60)  # At least 60px
                    left_region = film_region[:, 0:left_edge_width]
                    left_col_mean = left_region.mean(axis=0) / 255.0
                    left_col_std = left_region.std(axis=0) / 255.0
                    
                    # Compute column uniformity (key for gap detection)
                    left_col_uniformity = 1.0 - np.clip(left_col_std / 0.3, 0, 1)
                    
                    # Gap detection: bright + uniform OR very uniform + brighter than average
                    left_gap_mask = (
                        ((left_col_mean > brightness_thresh) & (left_col_std < std_thresh)) |
                        ((left_col_uniformity > 0.80) & (left_col_mean > film_brightness * 1.1))
                    )
                    
                    # Find contiguous gap regions
                    left_gap_regions = []
                    in_gap = False
                    gap_start = 0
                    for i in range(len(left_gap_mask)):
                        if left_gap_mask[i] and not in_gap:
                            gap_start = i
                            in_gap = True
                        elif not left_gap_mask[i] and in_gap:
                            if i - gap_start >= min_gap_px:
                                left_gap_regions.append((gap_start, i))
                            in_gap = False
                    if in_gap and len(left_gap_mask) - gap_start >= min_gap_px:
                        left_gap_regions.append((gap_start, len(left_gap_mask)))
                    
                    left_gap_width = sum(end - start for start, end in left_gap_regions)
                    
                    # === RIGHT EDGE CHECK (last 12%) ===
                    right_edge_start = max(int(film_w * 0.88), film_w - 60)
                    right_region = film_region[:, right_edge_start:]
                    right_col_mean = right_region.mean(axis=0) / 255.0
                    right_col_std = right_region.std(axis=0) / 255.0
                    
                    right_col_uniformity = 1.0 - np.clip(right_col_std / 0.3, 0, 1)
                    
                    right_gap_mask = (
                        ((right_col_mean > brightness_thresh) & (right_col_std < std_thresh)) |
                        ((right_col_uniformity > 0.80) & (right_col_mean > film_brightness * 1.1))
                    )
                    
                    # Find contiguous gap regions
                    right_gap_regions = []
                    in_gap = False
                    gap_start = 0
                    for i in range(len(right_gap_mask)):
                        if right_gap_mask[i] and not in_gap:
                            gap_start = i
                            in_gap = True
                        elif not right_gap_mask[i] and in_gap:
                            if i - gap_start >= min_gap_px:
                                right_gap_regions.append((gap_start, i))
                            in_gap = False
                    if in_gap and len(right_gap_mask) - gap_start >= min_gap_px:
                        right_gap_regions.append((gap_start, len(right_gap_mask)))
                    
                    right_gap_width = sum(end - start for start, end in right_gap_regions)
                    
                    self.log(f"   [Fine {fine_attempt+1}] Left: {left_gap_width}px ({len(left_gap_regions)} regions), Right: {right_gap_width}px ({len(right_gap_regions)} regions)")
                    
                    # === SUCCESS CHECK ===
                    # Both edges clear = ALIGNED!
                    # Use adaptive threshold based on pass number
                    clear_threshold = 2 if fine_attempt >= 6 else 3
                    if left_gap_width <= clear_threshold and right_gap_width <= clear_threshold:
                        # Calculate final confidence based on edge cleanliness
                        edge_cleanliness = 1.0 - (left_gap_width + right_gap_width) / (left_edge_width * 0.05)
                        final_confidence = max(0.95, min(1.0, edge_cleanliness))
                        
                        self.status_msg = "✓ Aligned"
                        self.log(f"   ✓ Both edges clear! Total: {total_steps} steps")
                        self.alignment_confidence = final_confidence
                        return True, "Aligned", {
                            "mode": "aligned",
                            "total_steps": total_steps,
                            "attempts": max_attempts,
                            "fine_tune_attempts": fine_attempt + 1,
                            "confidence": final_confidence,
                            "left_gap_width": left_gap_width,
                            "right_gap_width": right_gap_width,
                        }
                    
                    # === CORRECTION MOVES ===
                    # Prioritize larger gap first
                    if left_gap_width > right_gap_width and left_gap_width > clear_threshold:
                        # Gap on LEFT edge - push it out by moving BACKWARD
                        if left_gap_regions:
                            # Find rightmost gap pixel
                            rightmost_gap = max(end for start, end in left_gap_regions)
                            
                            # Calculate steps based on gap extent and iteration
                            # More aggressive in early passes, more precise in later passes
                            if fine_attempt < 3:
                                step_multiplier = 2.0
                            elif fine_attempt < 6:
                                step_multiplier = 1.5
                            else:
                                step_multiplier = 1.2
                            
                            fine_steps = int(rightmost_gap * step_multiplier)
                            fine_steps = max(10, min(100, fine_steps))
                            
                            self.log(f"   Left edge gap (rightmost: {rightmost_gap}px) -> BACKWARD {fine_steps}")
                            
                            self.send_and_wait(self.cmd_backup(fine_steps))
                            total_steps -= fine_steps
                            time.sleep(0.1)
                            continue
                    
                    elif right_gap_width > clear_threshold:
                        # Gap on RIGHT edge - push it out by moving FORWARD
                        if right_gap_regions:
                            # Find leftmost gap pixel (relative to right_region start)
                            leftmost_gap = min(start for start, end in right_gap_regions)
                            gap_extent = len(right_col_mean) - leftmost_gap
                            
                            # Calculate steps
                            if fine_attempt < 3:
                                step_multiplier = 2.0
                            elif fine_attempt < 6:
                                step_multiplier = 1.5
                            else:
                                step_multiplier = 1.2
                            
                            fine_steps = int(gap_extent * step_multiplier)
                            fine_steps = max(10, min(100, fine_steps))
                            
                            self.log(f"   Right edge gap (leftmost: {leftmost_gap}px, extent: {gap_extent}px) -> FORWARD {fine_steps}")
                            
                            self.send_and_wait(self.cmd_advance(fine_steps))
                            total_steps += fine_steps
                            time.sleep(0.1)
                            continue
                        
                except Exception as e:
                    self.log(f"   Fine-tune error: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            # If we get here, calculate confidence based on remaining gaps
            # Better scoring than flat 0.8
            final_left = left_gap_width if 'left_gap_width' in locals() else 0
            final_right = right_gap_width if 'right_gap_width' in locals() else 0
            total_gap = final_left + final_right
            
            if total_gap <= 8:
                # Very close - 90-95% confidence
                confidence = 0.90 + (1.0 - total_gap / 16) * 0.05
            elif total_gap <= 15:
                # Good - 85-90% confidence
                confidence = 0.85 + (1.0 - (total_gap - 8) / 14) * 0.05
            else:
                # Needs work - 75-85% confidence
                confidence = max(0.75, 0.85 - (total_gap - 15) / 100)
            
            self.alignment_confidence = confidence
            self.status_msg = "⚠ May need adjustment" if confidence < 0.90 else "✓ Mostly aligned"
            self.log(f"   Alignment complete: {total_steps} total steps, {confidence:.0%} confidence (left:{final_left}px, right:{final_right}px)")
            return True, "Aligned (check edges)", {
                "mode": "moved",
                "total_steps": total_steps,
                "attempts": max_attempts,
                "fine_tune_attempts": 8,
                "confidence": confidence,
                "left_gap_width": final_left,
                "right_gap_width": final_right,
            }

        # === HALF FRAME MODE - CENTER THE GAP ===
        else:
            # Half frame: need gap in the MIDDLE, no gaps on edges
            # Use same strict detection as full frame mode
            
            total_steps = 0
            max_attempts = 5
            
            for attempt in range(max_attempts):
                # Get fresh frame (send_and_wait confirmed motor done, brief settle only)
                if attempt > 0:
                    time.sleep(0.15)
                    frame_bytes, _ = self.get_alignment_frame(timeout=0.8)
                    if not frame_bytes:
                        continue
                
                try:
                    import numpy as np
                    import cv2
                    nparr = np.frombuffer(frame_bytes, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if img is None:
                        continue
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    h, w = gray.shape
                    
                    # Crop to middle 70% vertically (avoid camera overlays)
                    y_start = int(h * 0.15)
                    y_end = int(h * 0.85)
                    cropped = gray[y_start:y_end, :]
                    
                    # Compute per-column stats (same as full frame mode)
                    col_mean = cropped.mean(axis=0) / 255.0
                    col_std = cropped.std(axis=0) / 255.0
                    
                    # STRICT gap criteria
                    brightness_threshold = max(np.percentile(col_mean, 80), 0.60)
                    std_threshold = 0.08
                    
                    gap_mask = (col_mean >= brightness_threshold) & (col_std <= std_threshold)
                    
                    # Find gap regions
                    gap_regions = []
                    in_gap = False
                    gap_start = 0
                    
                    for i in range(len(gap_mask)):
                        if gap_mask[i] and not in_gap:
                            gap_start = i
                            in_gap = True
                        elif not gap_mask[i] and in_gap:
                            gap_end = i
                            gap_width = gap_end - gap_start
                            if gap_width >= 8:
                                gap_center = (gap_start + gap_end) / 2
                                gap_brightness = col_mean[gap_start:gap_end].mean()
                                gap_uniformity = 1.0 - col_std[gap_start:gap_end].mean()
                                gap_score = gap_brightness * gap_uniformity
                                gap_regions.append({
                                    "start": gap_start,
                                    "end": gap_end,
                                    "center": gap_center,
                                    "width": gap_width,
                                    "score": gap_score,
                                })
                            in_gap = False
                    
                    if in_gap:
                        gap_end = len(gap_mask)
                        gap_width = gap_end - gap_start
                        if gap_width >= 8:
                            gap_center = (gap_start + gap_end) / 2
                            gap_brightness = col_mean[gap_start:gap_end].mean()
                            gap_uniformity = 1.0 - col_std[gap_start:gap_end].mean()
                            gap_score = gap_brightness * gap_uniformity
                            gap_regions.append({
                                "start": gap_start,
                                "end": gap_end,
                                "center": gap_center,
                                "width": gap_width,
                                "score": gap_score,
                            })
                    
                    self.log(f"   [{attempt+1}] Found {len(gap_regions)} gap regions")
                    
                    # No gap found - search forward
                    if not gap_regions:
                        self.log(f"   No gap detected, searching forward...")
                        self.send_and_wait(self.cmd_advance(100))
                        total_steps += 100
                        time.sleep(0.15)
                        continue
                    
                    # Pick the best gap
                    best_gap = max(gap_regions, key=lambda g: g["score"])
                    gap_center = best_gap["center"]
                    gap_fraction = gap_center / w  # 0 = left, 1 = right
                    frame_center = w / 2
                    
                    self.log(f"   Best gap at {gap_fraction:.1%} (center_x={gap_center:.0f}, frame_center={frame_center:.0f})")
                    
                    # Check if gap is centered (within 40-60% of frame)
                    if 0.40 <= gap_fraction <= 0.60:
                        # Check edges are clear (no gaps in left/right 15%)
                        left_edge = int(w * 0.15)
                        right_edge = int(w * 0.85)
                        
                        has_left_gap = any(g["center"] < left_edge for g in gap_regions)
                        has_right_gap = any(g["center"] > right_edge for g in gap_regions)
                        
                        if not has_left_gap and not has_right_gap:
                            self.status_msg = "✓ Centered"
                            self.log(f"   ✓ Gap centered! No edge gaps. Total: {total_steps} steps")
                            self.alignment_confidence = 1.0
                            return True, "Centered", {
                                "mode": "aligned",
                                "total_steps": total_steps,
                                "attempts": attempt + 1,
                                "confidence": 1.0,
                            }
                    
                    # Gap not centered - calculate move to center it
                    offset_px = gap_center - frame_center  # Positive = gap is right of center
                    
                    if offset_px > 0:
                        # Gap is RIGHT of center - move BACKWARD to shift gap left
                        steps = max(20, min(150, int(abs(offset_px) / 2)))
                        direction = "BACKWARD"
                        cmd = self.cmd_backup(steps)
                        self.log(f"   Gap right of center -> moving BACKWARD {steps} steps")
                    else:
                        # Gap is LEFT of center - move FORWARD to shift gap right
                        steps = max(20, min(150, int(abs(offset_px) / 2)))
                        direction = "FORWARD"
                        cmd = self.cmd_advance(steps)
                        self.log(f"   Gap left of center -> moving FORWARD {steps} steps")
                    
                    # Execute move — wait for completion
                    moved = self.send_and_wait(cmd)
                    if not moved:
                        return False, "Motor failed", {"mode": "error", "total_steps": total_steps, "confidence": 0}
                    
                    total_steps += steps if direction == "FORWARD" else -steps
                    time.sleep(0.15)
                    
                except Exception as e:
                    self.log(f"   Error: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            # Max attempts
            self.status_msg = "⚠ May need adjustment"
            self.log(f"   Max attempts reached, {total_steps} total steps")
            return True, "Moved - check centering", {
                "mode": "moved",
                "total_steps": total_steps,
                "attempts": max_attempts,
                "confidence": 0.5,
            }
    
    def advance_and_align(self, max_iters=20):
        """
        Advance to next frame after capture.
        
        Uses the same strict gap detection as auto_align.
        
        FULL FRAME MODE:
        1. Move FORWARD to push current frame out
        2. Gap appears on left, keep moving until gap exits left
        3. Stop when no gap visible (next frame aligned)
        
        HALF FRAME MODE:
        1. Move FORWARD until gap appears
        2. Center the gap in the middle of the frame
        """
        import numpy as np
        import cv2
        
        total_steps_moved = 0
        saw_gap = False
        
        self.log(f"▶ Advancing to next frame [{self.frame_mode}]...")
        
        for iteration in range(max_iters):
            if iteration > 0:
                time.sleep(0.15)  # Brief settle after motor (send_and_wait confirmed completion)
            
            frame_bytes, _ = self.get_alignment_frame(timeout=0.8)
            if not frame_bytes:
                continue
            
            try:
                nparr = np.frombuffer(frame_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is None:
                    continue
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                h, w = gray.shape
                
                # Crop to middle 70% vertically
                y_start = int(h * 0.15)
                y_end = int(h * 0.85)
                cropped = gray[y_start:y_end, :]
                
                # Column stats
                col_mean = cropped.mean(axis=0) / 255.0
                col_std = cropped.std(axis=0) / 255.0
                
                # Check for end of roll (entire frame is uniformly bright)
                if col_mean.min() > 0.85 and col_std.max() < 0.10:
                    self.log("⚠ End of roll detected (uniform maximum brightness)")
                    self.status_msg = "End of roll"
                    return True, "End of roll", {"mode": "end_of_roll", "total_steps": total_steps_moved}
                
                # STRICT gap detection
                brightness_threshold = max(np.percentile(col_mean, 80), 0.60)
                std_threshold = 0.08
                gap_mask = (col_mean >= brightness_threshold) & (col_std <= std_threshold)
                
                # Find gap regions
                gap_regions = []
                in_gap = False
                gap_start = 0
                
                for i in range(len(gap_mask)):
                    if gap_mask[i] and not in_gap:
                        gap_start = i
                        in_gap = True
                    elif not gap_mask[i] and in_gap:
                        gap_end = i
                        gap_width = gap_end - gap_start
                        if gap_width >= 8:
                            gap_center = (gap_start + gap_end) / 2
                            gap_regions.append({
                                "start": gap_start,
                                "end": gap_end,
                                "center": gap_center,
                                "width": gap_width,
                            })
                        in_gap = False
                
                if in_gap:
                    gap_end = len(gap_mask)
                    gap_width = gap_end - gap_start
                    if gap_width >= 8:
                        gap_center = (gap_start + gap_end) / 2
                        gap_regions.append({
                            "start": gap_start,
                            "end": gap_end,
                            "center": gap_center,
                            "width": gap_width,
                        })
                
                has_gap = len(gap_regions) > 0
                
                if has_gap:
                    saw_gap = True
                    best_gap = max(gap_regions, key=lambda g: g["width"])
                    gap_fraction = best_gap["center"] / w
                    
                    self.log(f"   [{iteration+1}] Gap at {gap_fraction:.1%} (width={best_gap['width']})")
                    
                    if self.frame_mode == "full":
                        # FULL FRAME: push gap out left edge
                        gap_x_fraction = best_gap["start"] / w
                        if gap_x_fraction < 0.05:
                            steps = 20   # Almost out
                        elif gap_x_fraction < 0.15:
                            steps = 50   # Near left
                        elif gap_x_fraction < 0.30:
                            steps = 80   # Getting there
                        else:
                            steps = 120  # Far from left
                        self.log(f"   Moving FORWARD {steps} steps")
                        self.send_and_wait(self.cmd_advance(steps))
                        total_steps_moved += steps
                    else:
                        # HALF FRAME: center the gap in the middle
                        # Prioritize FORWARD movement, only go backward for fine adjustment
                        frame_center = w / 2
                        offset = best_gap["center"] - frame_center
                        
                        if abs(offset) <= w * 0.08:  # Within 8% of center = good enough
                            # Check no gaps on edges
                            left_edge = int(w * 0.12)
                            right_edge = int(w * 0.88)
                            has_left = any(g["center"] < left_edge for g in gap_regions)
                            has_right = any(g["center"] > right_edge for g in gap_regions)
                            
                            if not has_left and not has_right:
                                self.status_msg = "✓ Next frame ready (centered)"
                                self.log(f"✓ Gap centered! Total: {total_steps_moved} steps")
                                return True, "Next frame centered", {
                                    "mode": "aligned",
                                    "total_steps": total_steps_moved,
                                    "iterations": iteration + 1,
                                }
                        
                        # Move to center gap
                        if offset > 0:
                            steps = max(10, min(40, int(abs(offset) / 4)))
                            self.log(f"   Gap right of center -> FORWARD {steps}")
                            self.send_and_wait(self.cmd_advance(steps))
                            total_steps_moved += steps
                        else:
                            steps = max(8, min(25, int(abs(offset) / 4)))
                            self.log(f"   Gap left of center (overshot) -> BACKWARD {steps}")
                            self.send_and_wait(self.cmd_backup(steps))
                            total_steps_moved -= steps
                
                elif saw_gap and not has_gap:
                    # FULL FRAME: We saw a gap and now it's gone = aligned!
                    if self.frame_mode == "full":
                        self.status_msg = "✓ Next frame ready"
                        self.log(f"✓ Advanced to next frame! {total_steps_moved} steps")
                        return True, "Next frame aligned", {
                            "mode": "aligned",
                            "total_steps": total_steps_moved,
                            "iterations": iteration + 1,
                        }
                    else:
                        # HALF FRAME: gap disappeared but we need it centered - keep searching
                        self.log(f"   [{iteration+1}] Gap lost, searching forward...")
                        self.send_and_wait(self.cmd_advance(80))
                        total_steps_moved += 80
                else:
                    # No gap yet - keep moving forward
                    self.log(f"   [{iteration+1}] No gap yet, advancing...")
                    self.send_and_wait(self.cmd_advance(100))
                    total_steps_moved += 100
                    
            except Exception as e:
                self.log(f"   Error: {e}")
                continue
        
        self.log(f"⚠ Advance incomplete after {max_iters} iterations")
        return False, "Max iterations", {"mode": "max_iterations", "total_steps": total_steps_moved}

    # ========================================================================
    # SPROCKET-BASED ALIGNMENT (New hardware with visible sprocket holes)
    # ========================================================================
    
    def detect_sprocket_holes(self) -> Optional[dict]:
        """
        Detect sprocket holes in current frame.
        
        Returns detection result dict or None if detection failed.
        """
        frame_bytes, _ = self.get_alignment_frame(timeout=1.0)
        if not frame_bytes:
            self.log("✗ No frame for sprocket detection")
            return None
        
        try:
            result = detect_sprockets(
                frame_bytes,
                sprocket_region_fraction=0.18,  # Look at top/bottom 18% of image
                min_sprocket_area=50,
                max_sprocket_area=15000,
                brightness_threshold=0.45,
            )
            
            # Store result and update calibration
            self.last_sprocket_result = result
            
            if result.sprocket_pitch_px:
                self.sprocket_pitch_px = result.sprocket_pitch_px
                self.px_per_mm = result.px_per_mm
                
            return result.to_dict()
            
        except Exception as e:
            self.log(f"✗ Sprocket detection error: {e}")
            return None
    
    def auto_align_sprocket(self, max_iterations=15, tolerance_px=15):
        """
        Align frame using sprocket hole detection.
        
        This is more reliable than gap detection because sprocket holes are:
        - Precisely spaced (standard 35mm pitch: 4.75mm)
        - High contrast (bright holes against dark film)
        - Consistent regardless of image content
        
        Args:
            max_iterations: Maximum alignment iterations
            tolerance_px: Alignment tolerance in pixels
            
        Returns:
            (success, message, debug_info)
        """
        import numpy as np
        
        self.log("▶ Sprocket-based alignment starting...")
        total_steps = 0
        
        for iteration in range(max_iterations):
            if iteration > 0:
                # Brief settle after previous move completed (send_and_wait already
                # confirmed the motor stopped, this is just for physical vibration)
                time.sleep(0.15)
            
            # Get frame and detect sprockets
            frame_bytes, _ = self.get_alignment_frame(timeout=0.8)
            if not frame_bytes:
                self.log(f"   [{iteration+1}] No frame")
                continue
            
            try:
                result = detect_sprockets(
                    frame_bytes,
                    sprocket_region_fraction=0.18,
                    alignment_tolerance_px=tolerance_px,
                )
                
                # Store result for UI
                self.last_sprocket_result = result
                
                # Update calibration if we got good data — with validation
                if result.sprocket_pitch_px:
                    new_p = result.sprocket_pitch_px
                    # Reject wild outliers that would corrupt the smoothed pitch
                    accept = True
                    if self.sprocket_pitch_px_smoothed is not None:
                        ratio = new_p / self.sprocket_pitch_px_smoothed
                        if ratio < 0.65 or ratio > 1.35:
                            accept = False
                    if accept:
                        self.sprocket_pitch_px = new_p
                        if self.sprocket_pitch_px_smoothed is None:
                            self.sprocket_pitch_px_smoothed = new_p
                        else:
                            self.sprocket_pitch_px_smoothed = 0.8 * self.sprocket_pitch_px_smoothed + 0.2 * new_p
                        self.px_per_mm = result.px_per_mm
                
                sprocket_count = len(result.sprocket_holes)
                offset = result.offset_px
                confidence = result.confidence
                
                self.log(f"   [{iteration+1}] Sprockets: {sprocket_count}, Offset: {offset}px, Confidence: {confidence:.0%}")
                
                # Check if we need sprockets to align
                if sprocket_count < 2:
                    self.log(f"   ⚠ Not enough sprocket holes detected ({sprocket_count})")
                    # Move a bit to find sprockets — wait for completion
                    self.send_and_wait(self.cmd_advance(50))
                    total_steps += 50
                    continue
                
                # Check if aligned
                if result.aligned:
                    self.status_msg = "✓ Aligned (sprockets)"
                    self.log(f"   ✓ Aligned! {total_steps} total steps")
                    self.alignment_confidence = confidence
                    return True, "Aligned", {
                        "mode": "sprocket_aligned",
                        "total_steps": total_steps,
                        "iterations": iteration + 1,
                        "sprocket_count": sprocket_count,
                        "confidence": confidence,
                        "sprocket_pitch_px": result.sprocket_pitch_px,
                    }
                
                # Calculate steps to move
                if not self.sprocket_pitch_px:
                    # No calibration - use rough estimate
                    # Assuming ~640px width and ~2 frames visible, each frame ~320px
                    # 8 sprockets per frame, so ~40px per sprocket
                    px_per_step = 3.0
                else:
                    # Use calibrated px_per_mm and motor calibration
                    # This can be refined based on your motor setup
                    px_per_step = self.px_per_step if hasattr(self, 'px_per_step') else 3.0
                
                steps_needed = int(abs(offset) / px_per_step)
                steps_needed = max(8, min(steps_needed, 200))  # Clamp between 8-200
                
                # Determine direction: detector says positive = move film right.
                if offset > 0:
                    direction = "RIGHT"
                    cmd = self.cmd_backup(steps_needed)
                else:
                    direction = "LEFT"
                    cmd = self.cmd_advance(steps_needed)
                
                self.log(f"   → Moving {direction} {steps_needed} steps (offset={offset}px)")
                self.send_and_wait(cmd)
                
                if direction == "RIGHT":
                    total_steps += steps_needed
                else:
                    total_steps -= steps_needed
                
            except Exception as e:
                self.log(f"   Error: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # Max iterations reached
        self.status_msg = "⚠ Sprocket alignment incomplete"
        self.log(f"   Max iterations, {total_steps} total steps")
        return True, "Moved", {
            "mode": "sprocket_incomplete",
            "total_steps": total_steps,
            "iterations": max_iterations,
        }
    
    def advance_and_align_sprocket(self, max_iters=20):
        """
        Advance to next frame using sprocket hole detection.
        
        This is the sprocket-based version of advance_and_align.
        Uses sprocket spacing to precisely advance one frame (8 sprocket pitches).
        
        Returns:
            (success, message, debug_info)
        """
        self.log("▶ Advancing to next frame (sprocket mode)...")
        
        # Get current sprocket positions
        frame_bytes, _ = self.get_alignment_frame(timeout=1.0)
        if not frame_bytes:
            self.log("✗ No frame for sprocket advance")
            return False, "No frame", {}
        
        try:
            result = detect_sprockets(frame_bytes)
            
            if not result.sprocket_pitch_px:
                self.log("⚠ No sprocket calibration, falling back to gap detection")
                return self.advance_and_align(max_iters)
            
            new_pitch = result.sprocket_pitch_px
            
            # --- Validate detected pitch ---
            # Reject obviously wrong detections (e.g. clear base merging holes).
            # If we have a smoothed reference, new pitch must be within ±35%.
            if self.sprocket_pitch_px_smoothed is not None:
                ratio = new_pitch / self.sprocket_pitch_px_smoothed
                if ratio < 0.65 or ratio > 1.35:
                    self.log(f"   ⚠ Detected pitch {new_pitch:.1f}px rejected "
                             f"(smoothed={self.sprocket_pitch_px_smoothed:.1f}px, "
                             f"ratio={ratio:.2f}). Using smoothed value.")
                    new_pitch = self.sprocket_pitch_px_smoothed  # Keep old value
            
            # Update smoothed pitch (EMA)
            if self.sprocket_pitch_px_smoothed is None:
                self.sprocket_pitch_px_smoothed = new_pitch
            else:
                self.sprocket_pitch_px_smoothed = 0.8 * self.sprocket_pitch_px_smoothed + 0.2 * new_pitch
            pitch_for_advance = self.sprocket_pitch_px_smoothed
            self.sprocket_pitch_px = new_pitch
            
            # Calculate steps for one frame advance (8 sprocket pitches)
            frame_pitch_px = pitch_for_advance * SPROCKETS_PER_FRAME
            
            # Round steps to avoid systematic undershoot from int() truncation
            px_per_step = self.px_per_step if hasattr(self, 'px_per_step') else 3.0
            steps_per_frame = round(frame_pitch_px / px_per_step)
            steps_per_frame = max(1, steps_per_frame)
            
            self.log(f"   Frame pitch: {frame_pitch_px:.1f}px (smoothed), Steps: {steps_per_frame}, "
                     f"confidence: {result.confidence:.0%}, sprockets: {len(result.sprocket_holes)}")
            
            # Move forward one frame — wait for Arduino to confirm completion
            # so we don't stack another command while the motor is still running.
            self.send_and_wait(self.cmd_advance(steps_per_frame), timeout=15.0)
            # Brief settle so film physically stops before we grab the next frame
            time.sleep(0.3)
            
            # Fine-tune alignment: more iterations and tighter tolerance to correct 1–2 sprocket errors
            success, msg, info = self.auto_align_sprocket(max_iterations=12, tolerance_px=15)
            
            info["advance_steps"] = steps_per_frame
            # Refine px_per_step from observed movement — but ONLY when confident.
            # Bad detections on clear base can produce garbage ratios that drift
            # px_per_step to unusable values.
            align_steps = info.get("total_steps", 0)
            total_steps_used = steps_per_frame + align_steps
            align_confidence = info.get("confidence", 0)
            if (total_steps_used > 50 and frame_pitch_px > 0
                    and align_confidence >= 0.5
                    and abs(align_steps) < steps_per_frame * 0.25):
                # Only refine when alignment was good and correction was small
                observed_px_per_step = frame_pitch_px / total_steps_used
                old_pps = self.px_per_step if hasattr(self, 'px_per_step') and self.px_per_step else 3.0
                # Clamp to ±30% of current value to prevent runaway drift
                if 0.7 * old_pps <= observed_px_per_step <= 1.3 * old_pps:
                    self.px_per_step = 0.9 * old_pps + 0.1 * observed_px_per_step
                    info["px_per_step_refined"] = self.px_per_step
            return success, msg, info
            
        except Exception as e:
            self.log(f"✗ Sprocket advance error: {e}")
            return False, str(e), {}
    
    def calibrate_from_visible_sprockets(self):
        """
        Calibrate scanner using visible sprocket holes.
        
        Call this when you can see multiple sprocket holes to establish
        the pixel-to-mm ratio and frame pitch.
        
        Returns calibration dict or None.
        """
        frame_bytes, _ = self.get_alignment_frame(timeout=2.0)
        if not frame_bytes:
            self.log("✗ No frame for sprocket calibration")
            return None
        
        try:
            calibration = calibrate_from_sprockets(frame_bytes)
            
            if calibration:
                self.sprocket_pitch_px = calibration["sprocket_pitch_px"]
                self.sprocket_pitch_px_smoothed = self.sprocket_pitch_px
                self.px_per_mm = calibration["px_per_mm"]
                
                # Update px_per_step estimate based on motor calibration
                if self.frame_advance:
                    frame_pitch_px = self.sprocket_pitch_px * SPROCKETS_PER_FRAME
                    self.px_per_step = frame_pitch_px / self.frame_advance
                    calibration["px_per_step"] = self.px_per_step
                
                self.log(f"✓ Sprocket calibration: {self.sprocket_pitch_px:.1f}px/sprocket, {self.px_per_mm:.2f}px/mm")
                return calibration
            else:
                self.log("✗ Sprocket calibration failed - not enough sprockets detected")
                return None
                
        except Exception as e:
            self.log(f"✗ Calibration error: {e}")
            return None

    def detect_alignment_roi(self, padding: float = 0.0, min_area_ratio: float = 0.05):
        """
        Detect alignment ROI from preview stream frame.
        gphoto2 is only used for autofocus and capture (not preview).
        """
        # Get frame from active preview stream
        frame_bytes, _ = self.get_alignment_frame(timeout=2.0)
        if not frame_bytes:
            return None
        
        try:
            roi = detect_bright_region_roi(frame_bytes, padding=padding, min_area_ratio=min_area_ratio)
            if roi:
                self.alignment_roi = self._normalize_alignment_roi(roi)
            return self.alignment_roi
        except Exception as e:
            self.log(f"✗ ROI detection error: {e}")
            return None
    def _normalize_alignment_roi(self, roi):
        """
        Normalize ROI dict to 0-1 fractions with sanity checks.
        Allows 0-1 or 0-100 inputs. Ensures minimum usable width/height.
        """
        if roi is None:
            return None

        if not isinstance(roi, dict):
            raise ValueError("ROI must be an object with x0/x1/y0/y1")

        try:
            x0 = float(roi.get("x0", 0.0))
            x1 = float(roi.get("x1", 1.0))
            y0 = float(roi.get("y0", 0.0))
            y1 = float(roi.get("y1", 1.0))
        except Exception:
            raise ValueError("ROI values must be numbers")

        if max(x0, x1, y0, y1) > 1.5:
            x0, x1, y0, y1 = x0 / 100.0, x1 / 100.0, y0 / 100.0, y1 / 100.0

        x0 = max(0.0, min(1.0, x0))
        x1 = max(0.0, min(1.0, x1))
        y0 = max(0.0, min(1.0, y0))
        y1 = max(0.0, min(1.0, y1))

        if x1 <= x0 or y1 <= y0:
            raise ValueError("ROI end must be greater than start for both axes")
        if (x1 - x0) < 0.02:
            raise ValueError("ROI width too small (needs at least 2% of frame)")
        if (y1 - y0) < 0.05:
            raise ValueError("ROI height too small (needs at least 5% of frame)")

        return {
            "x0": round(x0, 4),
            "x1": round(x1, 4),
            "y0": round(y0, 4),
            "y1": round(y1, 4),
        }

    def _alignment_config_path(self):
        return self.settings_dir / "alignment_config.json"

    def _motor_config_path(self):
        return self.settings_dir / "motor_config.json"

    def _load_motor_config(self):
        """Load motor direction. advance_reversed=True means swap H/h for advance vs backup."""
        p = self._motor_config_path()
        if not p.exists():
            return
        try:
            with p.open("r") as f:
                data = json.load(f)
            self.motor_advance_reversed = bool(data.get("advance_reversed", False))
        except Exception:
            pass

    def _save_motor_config(self):
        try:
            self.settings_dir.mkdir(parents=True, exist_ok=True)
            with self._motor_config_path().open("w") as f:
                json.dump({"advance_reversed": self.motor_advance_reversed}, f, indent=2)
        except Exception as e:
            print(f"⚠ Failed to save motor config: {e}")

    @property
    def motor_cmd_advance(self):
        """Arduino command letter for 'advance to next frame'. Single source of truth."""
        return "H" if self.motor_advance_reversed else "h"

    @property
    def motor_cmd_backup(self):
        """Arduino command letter for 'backup'. Single source of truth."""
        return "h" if self.motor_advance_reversed else "H"

    def cmd_advance(self, steps):
        """Return Arduino command string for advancing steps (e.g. 'h1200' or 'H1200')."""
        return f"{self.motor_cmd_advance}{steps}"

    def cmd_backup(self, steps):
        """Return Arduino command string for backing up steps."""
        return f"{self.motor_cmd_backup}{steps}"

    def _load_alignment_config(self):
        cfg_path = self._alignment_config_path()
        if not cfg_path.exists():
            return False
        with cfg_path.open("r") as f:
            data = json.load(f)

        roi = data.get("roi")
        min_conf = data.get("min_confidence", self.alignment_min_confidence)

        with self.lock:
            if roi:
                try:
                    self.alignment_roi = self._normalize_alignment_roi(roi)
                except ValueError as e:
                    print(f"⚠ Ignoring saved ROI: {e}")
                    self.alignment_roi = None

            try:
                self.alignment_min_confidence = float(min_conf)
                self.alignment_min_confidence = max(0.01, min(0.9, self.alignment_min_confidence))
            except Exception:
                pass
        return True

    def _save_alignment_config(self):
        try:
            self.settings_dir.mkdir(parents=True, exist_ok=True)
            data = {
                "roi": self.alignment_roi,
                "min_confidence": self.alignment_min_confidence,
            }
            with self._alignment_config_path().open("w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠ Failed to save alignment config: {e}")

    def set_alignment_config(self, roi=None, min_confidence=None, clear=False):
        """Update ROI/min confidence and persist to disk."""
        with self.lock:
            if clear:
                self.alignment_roi = None
            if roi is not None:
                self.alignment_roi = self._normalize_alignment_roi(roi)
            if min_confidence is not None:
                try:
                    conf = float(min_confidence)
                except Exception:
                    raise ValueError("min_confidence must be a number")
                self.alignment_min_confidence = max(0.01, min(0.9, conf))
        self._save_alignment_config()

    def set_alignment_mode(self, mode: str):
        """
        Set alignment mode:
        - "stream": live auto-detect using preview stream (gap detection)
        - "sprocket": use sprocket hole detection (new hardware with visible sprockets)
        """
        if not isinstance(mode, str):
            raise ValueError("mode must be a string")
        normalized = mode.strip().lower()
        if normalized not in ("stream", "sprocket"):
            raise ValueError("mode must be 'stream' or 'sprocket'")
        with self.lock:
            self.alignment_mode = normalized
        self.save_state()
    
    def save_state(self):
        """Save scanning state"""
        if not self.state_file:
            return
        
        state = {
            'roll_name': self.roll_name,
            'frame_count': self.frame_count,
            'strip_count': self.strip_count,
            'frames_in_strip': self.frames_in_strip,
            'position': self.position,
            'frame_advance': self.frame_advance,
            'half_frame_advance': self.half_frame_advance,
            'frame_positions': self.frame_positions,
            'mode': self.mode,
            'auto_advance': self.auto_advance,
            'alignment_mode': self.alignment_mode,
            'scanner_mode': self.scanner_mode,
            'auto_alignment_enabled': self.auto_alignment_enabled,
            'auto_capture_enabled': self.auto_capture_enabled,
            'auto_capture_delay': self.auto_capture_delay,
            'scanlight_profiles': self.scanlight_profiles,
            'scanlight_current_profile': self.scanlight_current_profile,
            'scanlight_rgb': self.scanlight_rgb,
            'updated': datetime.now().isoformat()
        }
        
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def load_state(self, roll_folder):
        """Load scanning state"""
        state_path = os.path.join(roll_folder, '.scan_state.json')
        
        if os.path.exists(state_path):
            with open(state_path, 'r') as f:
                state = json.load(f)
                self.frame_count = state.get('frame_count', 0)
                self.strip_count = state.get('strip_count', 0)
                self.frames_in_strip = state.get('frames_in_strip', 0)
                self.position = state.get('position', 0)
                self.frame_advance = state.get('frame_advance')
                self.half_frame_advance = state.get('half_frame_advance')
                self.frame_positions = state.get('frame_positions', [])
                self.mode = state.get('mode', 'manual')
                self.auto_advance = state.get('auto_advance', True)
                self.alignment_mode = state.get('alignment_mode', self.alignment_mode)
                self.scanner_mode = state.get('scanner_mode', self.scanner_mode)
                self.auto_alignment_enabled = state.get('auto_alignment_enabled', self.auto_alignment_enabled)
                self.auto_capture_enabled = state.get('auto_capture_enabled', self.auto_capture_enabled)
                self.auto_capture_delay = state.get('auto_capture_delay', self.auto_capture_delay)
                
                # Load ScanLight profiles and settings
                self.scanlight_profiles = state.get('scanlight_profiles', self.scanlight_profiles)
                self.scanlight_current_profile = state.get('scanlight_current_profile', self.scanlight_current_profile)
                self.scanlight_rgb = state.get('scanlight_rgb', self.scanlight_rgb)
                
                return True
        return False
    
    def advance_frame(self):
        """
        Advance film forward using calibrated distance.
        
        Full frame mode: Advances by frame_advance (1 full 35mm frame)
        Half frame mode: Advances by half_frame_advance (2 half-frames ≈ 1 full frame)
        
        Half frame cameras expose 2 smaller frames per standard 35mm frame area.
        Each capture gets both half-frames (with gap centered), then we advance
        by 2 half-frames to the next pair.
        """
        # Determine advance distance based on frame mode
        if self.frame_mode == "half":
            # Use half_frame_advance if calibrated, else fallback to frame_advance
            advance = self.half_frame_advance or self.frame_advance
            mode_label = "half-frame"
        else:
            advance = self.frame_advance
            mode_label = "full-frame"
        
        if advance:
            success = self.send(self.cmd_advance(advance))
            if success:
                self.status_msg = f"Advanced {advance} steps ({mode_label})"
                return True
            else:
                self.status_msg = "❌ Advance failed - Check Arduino"
                return False
        return False
    
    def backup_frame(self):
        """
        Backup film using calibrated distance.
        Uses appropriate advance value based on frame mode (full or half).
        """
        # Determine advance distance based on frame mode
        if self.frame_mode == "half":
            advance = self.half_frame_advance or self.frame_advance
            mode_label = "half-frame"
        else:
            advance = self.frame_advance
            mode_label = "full-frame"
        
        if advance:
            success = self.send(self.cmd_backup(advance))
            if success:
                self.status_msg = f"Backed up {advance} steps ({mode_label})"
                return True
            else:
                self.status_msg = "❌ Backup failed - Check Arduino"
                return False
        return False
    
    # ========================================================================
    # ScanLight RGB Backlight Control
    # ========================================================================
    
    def connect_scanlight(self):
        """Auto-connect to ScanLight if present"""
        if not self.scanlight_connected:
            try:
                # Auto-discover and connect
                if self.scanlight.connect():
                    self.scanlight_connected = True
                    # Set to current RGB values
                    self.scanlight.set_rgb(
                        self.scanlight_rgb['r'],
                        self.scanlight_rgb['g'],
                        self.scanlight_rgb['b']
                    )
                    self.log(f"✓ ScanLight connected on {self.scanlight.port}")
                    return True
            except Exception as e:
                self.log(f"⚠ ScanLight not detected: {e}")
        return self.scanlight_connected
    
    def set_scanlight_rgb(self, r: int, g: int, b: int):
        """Set ScanLight RGB values"""
        try:
            r = max(0, min(255, int(r)))
            g = max(0, min(255, int(g)))
            b = max(0, min(255, int(b)))
            
            self.scanlight_rgb = {"r": r, "g": g, "b": b}
            
            if self.scanlight_connected:
                self.scanlight.set_rgb(r, g, b)
                return True
            else:
                # Try to connect first
                if self.connect_scanlight():
                    self.scanlight.set_rgb(r, g, b)
                    return True
            return False
        except Exception as e:
            self.log(f"✗ ScanLight RGB error: {e}")
            return False
    
    def save_scanlight_profile(self, name: str, description: str = ""):
        """Save current RGB values as a named profile"""
        try:
            self.scanlight_profiles[name] = {
                "r": self.scanlight_rgb['r'],
                "g": self.scanlight_rgb['g'],
                "b": self.scanlight_rgb['b'],
                "description": description
            }
            # Persist to state file
            if self.state_file:
                self.save_state()
            return True
        except Exception as e:
            self.log(f"✗ Failed to save profile: {e}")
            return False
    
    def load_scanlight_profile(self, name: str):
        """Load a saved RGB profile"""
        try:
            if name in self.scanlight_profiles:
                profile = self.scanlight_profiles[name]
                self.scanlight_current_profile = name
                self.set_scanlight_rgb(profile['r'], profile['g'], profile['b'])
                self.log(f"✓ Loaded profile: {name}")
                return True
            else:
                self.log(f"⚠ Profile not found: {name}")
                return False
        except Exception as e:
            self.log(f"✗ Failed to load profile: {e}")
            return False
    
    def delete_scanlight_profile(self, name: str):
        """Delete a saved profile"""
        try:
            # Prevent deletion of default profiles
            if name in ["Color", "B&W"]:
                return False
            
            if name in self.scanlight_profiles:
                del self.scanlight_profiles[name]
                # Persist to state file
                if self.state_file:
                    self.save_state()
                self.log(f"✓ Deleted profile: {name}")
                return True
            return False
        except Exception as e:
            self.log(f"✗ Failed to delete profile: {e}")
            return False
    
    def get_status(self):
        """Get current status as dictionary"""
        # Acquire lock to safely read shared state
        with self.lock:
            status = {
                'roll_name': self.roll_name,
                'frame_count': self.frame_count,
                'strip_count': self.strip_count,
                'frames_in_strip': self.frames_in_strip,
                'position': self.position,
                'mode': self.mode,
                'frame_advance': self.frame_advance,
                'half_frame_advance': self.half_frame_advance,
                'auto_advance': self.auto_advance,
                'alignment_mode': self.alignment_mode,
                'frame_mode': self.frame_mode,
                'scanner_mode': self.scanner_mode,
                'auto_alignment_enabled': self.auto_alignment_enabled,
                'auto_capture_enabled': self.auto_capture_enabled,
                'auto_capture_delay': self.auto_capture_delay,
                'camera_connected': self.camera_connected,
                'camera_model': self.camera_model,
                'camera_error': self.camera_error,
                'viewfinder_enabled': self.viewfinder_enabled,
                'status_msg': self.status_msg,
                'arduino_connected': self.arduino is not None,
                'arduino_port': self.arduino_port,
                'arduino_board': self.arduino_board,
                'px_per_step': self.px_per_step,
                'alignment_confidence': self.alignment_confidence,
                'last_gap_px': self.last_gap_px,
                'alignment_roi': self.alignment_roi,
                'alignment_min_confidence': self.alignment_min_confidence,
                # Sprocket detection info
                'sprocket_detection_enabled': self.sprocket_detection_enabled,
                'sprocket_pitch_px': self.sprocket_pitch_px,
                'px_per_mm': self.px_per_mm,
                # Stream info
                'stream_resolution': f"{self.preview_stream.capture_width}x{self.preview_stream.capture_height}",
                'stream_output_width': self.preview_stream.output_width,
                'stream_fps': round(self.preview_stream.fps, 1),
                'preview_source_preference': self.preview_source_preference,
                'preview_source_active': self.preview_stream.get_resolution_info().get('backend', 'none'),
                'motor_advance_reversed': self.motor_advance_reversed,
            }
        
        return status
    
    def broadcast_status(self, throttle=True):
        """
        Broadcast status to all connected clients.
        
        Args:
            throttle: If True, rate-limit broadcasts to reduce network overhead (default: True)
        """
        try:
            # Throttle broadcasts to max 2 per second to reduce network/CPU overhead
            if throttle:
                current_time = time.time()
                if not hasattr(self, '_last_broadcast_time'):
                    self._last_broadcast_time = 0
                
                # Only broadcast if 0.5 seconds have passed since last broadcast
                if current_time - self._last_broadcast_time < 0.5:
                    return
                
                self._last_broadcast_time = current_time
            
            socketio.emit('status_update', self.get_status())
        except Exception:
            pass
# Global scanner instance
scanner = FilmScanner()
# Routes
@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')
@app.route('/api/status')
def get_status():
    """Get current status"""
    return jsonify(scanner.get_status())
@app.route('/api/connect_arduino', methods=['POST'])
def connect_arduino():
    """Connect to Arduino"""
    success = scanner.find_arduino()
    scanner.broadcast_status()
    return jsonify({'success': success})
@app.route('/api/new_roll', methods=['POST'])
def new_roll():
    """Create or reset scan session (legacy endpoint)."""
    data = request.json or {}
    roll_name = (data.get('roll_name') or '').strip() or "current-session"
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    base_folder = os.path.expanduser("~/scans")
    scanner.roll_folder = os.path.join(base_folder, date_str, roll_name)
    os.makedirs(scanner.roll_folder, exist_ok=True)
    
    scanner.state_file = os.path.join(scanner.roll_folder, '.scan_state.json')
    
    resume = data.get('resume', False)
    if os.path.exists(scanner.state_file) and resume:
        scanner.load_state(scanner.roll_folder)
        scanner.status_msg = "Resumed current session"
    else:
        scanner.frame_count = 0
        scanner.strip_count = 0
        scanner.frames_in_strip = 0
        scanner.frame_advance = None
        scanner.frame_positions = []
        scanner.status_msg = "New session started"
    
    scanner.roll_name = roll_name
    scanner.save_state()
    scanner.broadcast_status()
    
    return jsonify({'success': True})
@app.route('/api/motor_direction', methods=['GET', 'POST'])
def motor_direction():
    """
    Get or set motor advance direction. Single source of truth for auto-advance/alignment.
    POST body: { "reversed": true } or { "reversed": false }.
    If auto-advance goes the wrong way, set reversed to true (saved permanently).
    """
    if request.method == 'GET':
        return jsonify({
            'motor_advance_reversed': scanner.motor_advance_reversed,
            'message': 'Reverse motor direction if auto-advance goes the wrong way',
        })
    data = request.json or {}
    if 'reversed' in data:
        scanner.motor_advance_reversed = bool(data['reversed'])
        scanner._save_motor_config()
        scanner.status_msg = f"Motor direction: {'reversed' if scanner.motor_advance_reversed else 'normal'}"
        scanner.broadcast_status()
        return jsonify({
            'success': True,
            'motor_advance_reversed': scanner.motor_advance_reversed,
            'message': scanner.status_msg,
        })
    return jsonify({'success': False, 'message': 'Send {"reversed": true/false}'})


@app.route('/api/move', methods=['POST'])
def move():
    """Move motor - optimized for quick response"""
    data = request.json
    direction = data.get('direction', 'forward')
    size = data.get('size', 'fine')
    
    # Motor direction reversed for new pancake motor
    if direction == 'forward':
        cmd = 'B' if size == 'coarse' else 'b'
    else:
        cmd = 'F' if size == 'coarse' else 'f'
    
    # Send command without waiting for position update (for speed)
    success = scanner.send(cmd, update_position=False)
    
    if success:
        # Update position estimate locally for immediate feedback
        step = scanner.coarse_step if size == 'coarse' else scanner.fine_step
        if direction == 'forward':
            scanner.position += step
        else:
            scanner.position -= step
        
        scanner.status_msg = f"{'→' if direction == 'forward' else '←'} {step} steps"
    else:
        scanner.status_msg = "❌ Motor move failed - Check Arduino connection"
    
    # Don't broadcast status on every move to reduce lag
    # Status will be updated by periodic polling
    
    return jsonify({'success': success, 'position': scanner.position})
@app.route('/api/advance_frame', methods=['POST'])
def advance_frame():
    """Advance one frame"""
    success = scanner.advance_frame()
    scanner.broadcast_status()
    return jsonify({'success': success})
@app.route('/api/backup_frame', methods=['POST'])
def backup_frame():
    """Backup one frame"""
    success = scanner.backup_frame()
    scanner.broadcast_status()
    return jsonify({'success': success})
@app.route('/api/toggle_mode', methods=['POST'])
def toggle_mode():
    """Toggle mode"""
    scanner.mode = 'calibrated' if scanner.mode == 'manual' else 'manual'
    scanner.status_msg = f"Mode: {scanner.mode.upper()}"
    scanner.save_state()
    scanner.broadcast_status()
    return jsonify({'success': True})
@app.route('/api/toggle_auto_advance', methods=['POST'])
def toggle_auto_advance():
    """Toggle auto advance"""
    if scanner.mode == 'calibrated':
        scanner.auto_advance = not scanner.auto_advance
        scanner.status_msg = f"Auto-advance: {'ON' if scanner.auto_advance else 'OFF'}"
        scanner.save_state()
    else:
        scanner.status_msg = "Auto-advance only in calibrated mode"
    scanner.broadcast_status()
    return jsonify({'success': True})
@app.route('/api/zero_position', methods=['POST'])
def zero_position():
    """Zero position"""
    success = scanner.send('Z')
    if success:
        scanner.frame_positions = []
        scanner.position = 0
        scanner.status_msg = "Position zeroed"
    else:
        scanner.status_msg = "❌ Zero failed - Check Arduino"
    scanner.broadcast_status()
    return jsonify({'success': success})
# Autofocus button removed - autofocus is now only used internally during capture
# The autofocus() method is kept for internal use in capture_image()
@app.route('/api/test_capture', methods=['POST'])
def test_capture():
    """Test camera capture without saving to roll (for debugging)"""
    # Force camera check for user-initiated capture
    if not scanner.check_camera(force=True):
        return jsonify({
            'success': False, 
            'message': 'Camera not connected',
            'error': scanner.camera_error
        })
    
    scanner.status_msg = "Testing capture..."
    scanner.broadcast_status()
    
    print("\n" + "="*60)
    print("TEST CAPTURE (frame count will NOT be incremented)")
    print("="*60)
    
    # Temporarily save frame count
    saved_count = scanner.frame_count
    saved_strip = scanner.frames_in_strip
    saved_positions = scanner.frame_positions.copy()
    
    try:
        # Try to capture
        success = scanner.capture_image(retry=False)
        
        # Restore frame counts (test doesn't count)
        scanner.frame_count = saved_count
        scanner.frames_in_strip = saved_strip
        scanner.frame_positions = saved_positions
        
        if success:
            scanner.status_msg = "✓ Test capture successful! Camera is working."
            message = "Camera capture works! Check camera SD card for test image."
        else:
            scanner.status_msg = "✗ Test capture failed (check console for details)"
            message = "Capture failed. Check console output above for specific error."
        
        print("="*60)
        print(f"TEST RESULT: {'SUCCESS' if success else 'FAILED'}")
        print("="*60 + "\n")
        
        scanner.broadcast_status()
        return jsonify({'success': success, 'message': message})
        
    except Exception as e:
        scanner.frame_count = saved_count
        scanner.frames_in_strip = saved_strip
        scanner.frame_positions = saved_positions
        scanner.status_msg = f"✗ Test error: {str(e)}"
        scanner.broadcast_status()
        return jsonify({'success': False, 'message': str(e)})
@app.route('/api/capture', methods=['POST'])
def capture():
    """
    Capture image and auto-advance to next frame.
    
    In STREAM (auto-align) mode:
    - Captures the current frame
    - Automatically advances and aligns to next frame using advance_and_align
    - ONLY moves FORWARD (right), with backward only for fine overshoot correction
    - If auto_capture_enabled, continues to capture next frame automatically
    
    In CALIBRATION mode:
    - Uses fixed frame_advance distance
    """
    # Prevent overlapping capture+advance (double capture, partial advance on Pi)
    if not scanner.capture_workflow_lock.acquire(blocking=False):
        return jsonify({
            'success': False,
            'message': 'Capture already in progress. Wait for the current capture and advance to finish.',
            'frame_count': scanner.frame_count,
        }), 409

    try:
        data = request.json or {}
        auto_align_before = data.get('auto_align', False)
        
        # Force camera check for user-initiated capture
        if not scanner.check_camera(force=True):
            return jsonify({'success': False, 'message': 'Camera not connected'})
        
        # Optional pre-capture fine-tune (only does minor adjustments if gap visible on edge)
        # Respects both the checkbox AND the global auto_alignment_enabled setting
        if auto_align_before and scanner.alignment_mode in ("stream", "sprocket") and scanner.auto_alignment_enabled:
            try:
                # Only do edge fine-tune, not full realignment
                scanner.log("Pre-capture edge check...")
                if scanner.alignment_mode == "sprocket":
                    success, msg, info = scanner.auto_align_sprocket(max_iterations=5, tolerance_px=20)
                else:
                    success, msg, info = scanner.auto_align()
                scanner.broadcast_status()
                if not success:
                    scanner.log(f"Pre-capture align note: {msg}")
                    # Don't fail capture if pre-align has issues - just log it
            except Exception as e:
                scanner.log(f"Pre-capture align error: {e}")

        scanner.status_msg = "Capturing..."
        scanner.broadcast_status()
        
        success = scanner.capture_image()
        
        if success:
            scanner.status_msg = f"✓ Frame {scanner.frame_count}"
            scanner.broadcast_status()
            
            # Wait for exposure to complete if auto-capture is enabled
            if scanner.auto_capture_enabled:
                scanner.log(f"⏱️ Waiting {scanner.auto_capture_delay}s for exposure...")
                scanner.status_msg = f"⏱️ Frame {scanner.frame_count} - Waiting for exposure..."
                scanner.broadcast_status()
                time.sleep(scanner.auto_capture_delay)
            
            # Auto-advance AFTER capture (only in 35mm mode with Arduino)
            # In 120 mode (hand feed), skip all motor operations
            if scanner.scanner_mode == "120":
                # 120 mode: No auto-advance, user manually feeds film
                scanner.status_msg = f"✓ Frame {scanner.frame_count} (hand feed next)"
            elif scanner.alignment_mode == "sprocket" and scanner.auto_alignment_enabled:
                # SPROCKET MODE: Use sprocket hole detection for precise frame advance
                time.sleep(0.3)  # Brief pause before advancing
                try:
                    adv_success, adv_msg, adv_info = scanner.advance_and_align_sprocket()
                    if adv_success:
                        scanner.status_msg = f"✓ Frame {scanner.frame_count} → Ready for next"
                    else:
                        scanner.status_msg = f"✓ Frame {scanner.frame_count} (advance: {adv_msg})"
                except Exception as e:
                    scanner.log(f"Sprocket advance error: {e}")
                    scanner.status_msg = f"✓ Frame {scanner.frame_count} (advance error)"
            elif scanner.alignment_mode == "stream" and scanner.auto_alignment_enabled:
                # STREAM MODE with auto-alignment: Use advance_and_align (always moves FORWARD/right)
                time.sleep(0.3)  # Brief pause before advancing
                try:
                    adv_success, adv_msg, adv_info = scanner.advance_and_align()
                    if adv_success:
                        scanner.status_msg = f"✓ Frame {scanner.frame_count} → Ready for next"
                    else:
                        scanner.status_msg = f"✓ Frame {scanner.frame_count} (advance: {adv_msg})"
                except Exception as e:
                    scanner.log(f"Advance error: {e}")
                    scanner.status_msg = f"✓ Frame {scanner.frame_count} (advance failed)"
            elif scanner.mode == 'calibrated' and scanner.auto_advance:
                # CALIBRATION MODE: Use fixed frame_advance distance (h = advance on this hardware)
                if scanner.frame_mode == "half":
                    advance = scanner.half_frame_advance or scanner.frame_advance
                else:
                    advance = scanner.frame_advance
                
                if advance:
                    time.sleep(0.3)
                    if scanner.send(scanner.cmd_advance(advance)):
                        scanner.status_msg = f"✓ Frame {scanner.frame_count} → Ready for next"
                    else:
                        scanner.status_msg = f"✓ Frame {scanner.frame_count} (advance failed)"
            else:
                # No advance path matched (e.g. auto-alignment off and not calibrated)
                scanner.status_msg = f"✓ Frame {scanner.frame_count} (no advance - enable Auto-Alignment or calibrated mode)"
                scanner.log("Capture OK but no advance: auto_alignment_enabled or calibrated mode required for auto-advance")
        else:
            scanner.status_msg = "❌ Capture failed!"
        
        scanner.broadcast_status()
        return jsonify({
            'success': success,
            'auto_capture_enabled': scanner.auto_capture_enabled,
            'frame_count': scanner.frame_count
        })
    finally:
        scanner.capture_workflow_lock.release()


@app.route('/api/auto_align', methods=['POST'])
def auto_align_route():
    """Automatically align to nearest frame gap using preview edge detection."""
    try:
        success, msg, info = scanner.auto_align()
        scanner.broadcast_status()
        # Read shared state under lock for thread safety
        with scanner.lock:
            px_per_step = scanner.px_per_step
            confidence = scanner.alignment_confidence
        return jsonify({
            'success': success,
            'message': msg,
            'info': info,
            'px_per_step': px_per_step,
            'confidence': confidence,
            'alignment_roi': scanner.alignment_roi,
            'min_confidence': scanner.alignment_min_confidence,
        })
    except Exception as e:
        with scanner.lock:
            scanner.status_msg = "✗ Auto-align error"
        scanner.broadcast_status()
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/advance_and_align', methods=['POST'])
def advance_and_align_route():
    """
    Advance to next frame after capture.
    Always moves FORWARD, pushing current frame out right, 
    until gap appears on left and then exits, revealing next frame.
    """
    try:
        success, msg, info = scanner.advance_and_align()
        scanner.broadcast_status()
        return jsonify({
            'success': success,
            'message': msg,
            'info': info,
        })
    except Exception as e:
        scanner.status_msg = "✗ Advance error"
        scanner.broadcast_status()
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/get_alignment_config', methods=['POST'])
def get_alignment_config_route():
    """Return current alignment ROI and confidence threshold."""
    with scanner.lock:
        return jsonify({
            'success': True,
            'roi': scanner.alignment_roi,
            'min_confidence': scanner.alignment_min_confidence,
            'alignment_mode': scanner.alignment_mode,
            'frame_mode': scanner.frame_mode,
        })


@app.route('/api/set_alignment_config', methods=['POST'])
def set_alignment_config_route():
    """
    Update alignment ROI and/or minimum confidence.
    Accepts either a nested roi object or flat x0/x1/y0/y1 keys.
    Values may be 0-1 fractions or 0-100 percentages.
    """
    data = request.json or {}
    clear = bool(data.get('clear'))

    roi = data.get('roi')
    if roi is None:
        flat_roi = {k: data.get(k) for k in ("x0", "x1", "y0", "y1") if data.get(k) is not None}
        if flat_roi:
            roi = flat_roi

    min_conf = data.get('min_confidence')

    try:
        scanner.set_alignment_config(roi=roi, min_confidence=min_conf, clear=clear)
        with scanner.lock:
            return jsonify({
                'success': True,
                'roi': scanner.alignment_roi,
                'min_confidence': scanner.alignment_min_confidence,
            })
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/set_alignment_mode', methods=['POST'])
def set_alignment_mode_route():
    """Set alignment mode: stream or sprocket."""
    data = request.json or {}
    mode = data.get('mode')
    try:
        scanner.set_alignment_mode(mode)
        scanner.status_msg = f"Alignment mode: {scanner.alignment_mode}"
        scanner.broadcast_status()
        with scanner.lock:
            return jsonify({
                'success': True,
                'alignment_mode': scanner.alignment_mode,
            })
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)})


# ============================================================================
# SPROCKET DETECTION API ENDPOINTS
# ============================================================================

@app.route('/api/detect_sprockets', methods=['POST'])
def detect_sprockets_route():
    """Detect sprocket holes in current frame for alignment."""
    result = scanner.detect_sprocket_holes()
    if result:
        return jsonify({
            'success': True,
            'result': result,
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Sprocket detection failed',
        })


@app.route('/api/calibrate_sprockets', methods=['POST'])
def calibrate_sprockets_route():
    """Calibrate scanner using visible sprocket holes."""
    calibration = scanner.calibrate_from_visible_sprockets()
    if calibration:
        return jsonify({
            'success': True,
            'calibration': calibration,
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Sprocket calibration failed - not enough sprockets visible',
        })


@app.route('/api/align_sprocket', methods=['POST'])
def align_sprocket_route():
    """Align frame using sprocket hole detection."""
    success, message, info = scanner.auto_align_sprocket()
    return jsonify({
        'success': success,
        'message': message,
        'info': info,
    })


@app.route('/api/set_scanner_mode', methods=['POST'])
def set_scanner_mode_route():
    """
    Set scanner mode: 35mm (Arduino motor control) or 120 (hand feed, no Arduino).
    
    120 mode is for medium format film scanning with manual film advancement.
    In this mode, Arduino/motor controls are hidden and only preview/capture is available.
    """
    data = request.json or {}
    mode = (data.get('mode') or '').strip().lower()
    
    # Normalize mode names
    if mode in ('35mm', '35'):
        mode = '35mm'
    elif mode in ('120', 'medium', 'medium format'):
        mode = '120'
    else:
        return jsonify({'success': False, 'message': "mode must be '35mm' or '120'"})
    
    with scanner.lock:
        scanner.scanner_mode = mode
    scanner.status_msg = f"Scanner mode: {scanner.scanner_mode}"
    scanner.save_state()
    scanner.broadcast_status()
    
    return jsonify({
        'success': True,
        'scanner_mode': scanner.scanner_mode,
    })


@app.route('/api/set_auto_alignment', methods=['POST'])
def set_auto_alignment_route():
    """
    Toggle auto-alignment on or off.
    
    When disabled, no automatic frame alignment is performed - useful for manual control
    or when the auto-alignment detection isn't working well for a particular film type.
    """
    data = request.json or {}
    enabled = data.get('enabled')
    
    if enabled is None:
        # Toggle if not specified
        with scanner.lock:
            scanner.auto_alignment_enabled = not scanner.auto_alignment_enabled
    else:
        with scanner.lock:
            scanner.auto_alignment_enabled = bool(enabled)
    
    state = "enabled" if scanner.auto_alignment_enabled else "disabled"
    scanner.status_msg = f"Auto-alignment: {state}"
    scanner.save_state()
    scanner.broadcast_status()
    
    return jsonify({
        'success': True,
        'auto_alignment_enabled': scanner.auto_alignment_enabled,
    })


@app.route('/api/set_auto_capture', methods=['POST'])
def set_auto_capture_route():
    """
    Toggle auto-capture on or off.
    
    When enabled, the scanner will automatically capture the next frame after
    advancing and aligning. This creates a continuous scanning workflow:
    1. Capture frame
    2. Wait for exposure (auto_capture_delay seconds)
    3. Auto-advance to next frame
    4. Auto-capture next frame
    5. Repeat
    
    Useful for scanning entire rolls without manual intervention.
    """
    data = request.json or {}
    enabled = data.get('enabled')
    
    if enabled is None:
        # Toggle if not specified
        with scanner.lock:
            scanner.auto_capture_enabled = not scanner.auto_capture_enabled
    else:
        with scanner.lock:
            scanner.auto_capture_enabled = bool(enabled)
    
    state = "enabled" if scanner.auto_capture_enabled else "disabled"
    scanner.status_msg = f"Auto-capture: {state}"
    scanner.save_state()
    scanner.broadcast_status()
    
    return jsonify({
        'success': True,
        'auto_capture_enabled': scanner.auto_capture_enabled,
    })


@app.route('/api/set_auto_capture_delay', methods=['POST'])
def set_auto_capture_delay_route():
    """
    Set the delay between capture and advance (exposure time).
    
    This delay allows the camera exposure to complete before advancing
    to the next frame. Adjust based on your camera's exposure time:
    - Fast exposures (1/60s - 1/125s): 1-2 seconds
    - Medium exposures (1/30s - 1/15s): 2-3 seconds  
    - Slow exposures (1/8s - 1s): 3-5 seconds
    - Very slow exposures (>1s): Match your exposure time + 1-2 seconds buffer
    
    Range: 1.0 - 30.0 seconds
    """
    data = request.json or {}
    delay = data.get('delay')
    
    if delay is None:
        return jsonify({
            'success': False,
            'message': 'delay parameter required'
        })
    
    try:
        delay = float(delay)
        if delay < 1.0 or delay > 30.0:
            return jsonify({
                'success': False,
                'message': 'delay must be between 1.0 and 30.0 seconds'
            })
        
        with scanner.lock:
            scanner.auto_capture_delay = delay
        
        scanner.status_msg = f"Auto-capture delay: {delay}s"
        scanner.save_state()
        scanner.broadcast_status()
        
        return jsonify({
            'success': True,
            'auto_capture_delay': scanner.auto_capture_delay,
        })
    except (ValueError, TypeError):
        return jsonify({
            'success': False,
            'message': 'Invalid delay value'
        })


# ============================================================================
# ScanLight RGB Backlight Control API
# ============================================================================

@app.route('/api/scanlight/status')
def scanlight_status():
    """Get ScanLight connection status and current RGB values"""
    try:
        # Try to connect if not already connected
        if not scanner.scanlight_connected:
            scanner.connect_scanlight()
        
        status = {
            'connected': scanner.scanlight_connected,
            'rgb': scanner.scanlight_rgb,
            'profiles': scanner.scanlight_profiles,
            'current_profile': scanner.scanlight_current_profile
        }
        
        if scanner.scanlight_connected:
            status['port'] = scanner.scanlight.port
        
        return jsonify({'success': True, **status})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e), 'connected': False})


@app.route('/api/scanlight/set_rgb', methods=['POST'])
def scanlight_set_rgb():
    """Set ScanLight RGB values"""
    try:
        data = request.get_json()
        r = int(data.get('r', 255))
        g = int(data.get('g', 255))
        b = int(data.get('b', 255))
        
        success = scanner.set_scanlight_rgb(r, g, b)
        
        # Save to state if state file exists
        if scanner.state_file:
            scanner.save_state()
        
        return jsonify({
            'success': success,
            'rgb': scanner.scanlight_rgb,
            'connected': scanner.scanlight_connected
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/scanlight/profiles')
def scanlight_get_profiles():
    """Get all saved ScanLight profiles"""
    try:
        return jsonify({
            'success': True,
            'profiles': scanner.scanlight_profiles,
            'current_profile': scanner.scanlight_current_profile
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/scanlight/save_profile', methods=['POST'])
def scanlight_save_profile():
    """Save current RGB values as a named profile"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        
        if not name:
            return jsonify({'success': False, 'message': 'Profile name required'})
        
        # Limit name length
        if len(name) > 50:
            return jsonify({'success': False, 'message': 'Profile name too long (max 50 chars)'})
        
        success = scanner.save_scanlight_profile(name, description)
        
        return jsonify({
            'success': success,
            'profiles': scanner.scanlight_profiles
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/scanlight/load_profile', methods=['POST'])
def scanlight_load_profile():
    """Load a saved RGB profile"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        
        if not name:
            return jsonify({'success': False, 'message': 'Profile name required'})
        
        success = scanner.load_scanlight_profile(name)
        
        return jsonify({
            'success': success,
            'rgb': scanner.scanlight_rgb,
            'current_profile': scanner.scanlight_current_profile
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/scanlight/delete_profile', methods=['POST'])
def scanlight_delete_profile():
    """Delete a saved profile"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        
        if not name:
            return jsonify({'success': False, 'message': 'Profile name required'})
        
        success = scanner.delete_scanlight_profile(name)
        
        if not success and name in ["Color", "B&W"]:
            return jsonify({
                'success': False,
                'message': 'Cannot delete default profiles'
            })
        
        return jsonify({
            'success': success,
            'profiles': scanner.scanlight_profiles
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/set_frame_mode', methods=['POST'])
def set_frame_mode_route():
    """Set frame mode: full or half (affects gap hint for alignment)."""
    data = request.json or {}
    mode = (data.get('mode') or '').strip().lower()
    if mode not in ("full", "half"):
        return jsonify({'success': False, 'message': "mode must be 'full' or 'half'"})
    scanner.frame_mode = mode
    scanner.status_msg = f"Frame mode: {scanner.frame_mode}"
    scanner.broadcast_status()
    with scanner.lock:
        return jsonify({'success': True, 'frame_mode': scanner.frame_mode})


@app.route('/api/set_half_frame_advance', methods=['POST'])
def set_half_frame_advance_route():
    """
    Set the half-frame advance distance (steps to move 2 half-frames).
    
    Half-frame cameras expose 2 smaller frames per standard 35mm frame area.
    When scanning half-frame film:
    - Each capture gets both half-frames (with gap centered)
    - Advance moves 2 half-frames to the next pair
    
    If not set, defaults to frame_advance (full frame distance).
    Can be set to a percentage of frame_advance (e.g., 95% if half-frames
    are slightly smaller than full frames).
    """
    data = request.json or {}
    
    # Accept either absolute steps or percentage of frame_advance
    steps = data.get('steps')
    percentage = data.get('percentage')
    
    if steps is not None:
        try:
            steps = int(steps)
            if steps <= 0:
                return jsonify({'success': False, 'message': 'steps must be positive'})
            scanner.half_frame_advance = steps
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Invalid steps value'})
    elif percentage is not None:
        try:
            percentage = float(percentage)
            if not scanner.frame_advance:
                return jsonify({'success': False, 'message': 'Calibrate full frame first'})
            scanner.half_frame_advance = int(scanner.frame_advance * percentage / 100)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Invalid percentage value'})
    else:
        # Clear half_frame_advance (will fallback to frame_advance)
        scanner.half_frame_advance = None
    
    scanner.save_state()
    scanner.status_msg = f"Half-frame advance: {scanner.half_frame_advance or 'using full frame'}"
    scanner.broadcast_status()
    
    return jsonify({
        'success': True,
        'half_frame_advance': scanner.half_frame_advance,
        'frame_advance': scanner.frame_advance,
    })


@app.route('/api/preview_roi', methods=['POST'])
def preview_roi_route():
    """
    Detect ROI from preview stream frame and optionally return an overlay.
    Request JSON: {apply_roi: bool, overlay: bool}
    """
    data = request.json or {}
    apply_roi = bool(data.get('apply_roi'))
    overlay = bool(data.get('overlay'))

    try:
        frame_bytes = scanner.capture_preview_bytes()
    except Exception as e:
        return jsonify({'success': False, 'message': f'Preview error: {e}'})

    detected_roi = detect_bright_region_roi(frame_bytes, padding=0.0)

    # Optionally persist detected ROI
    if apply_roi and detected_roi:
        try:
            with scanner.lock:
                scanner.alignment_roi = detected_roi
            scanner._save_alignment_config()
        except Exception:
            pass  # best-effort

    image_data = None
    if overlay:
        try:
            arr = np.frombuffer(frame_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Failed to decode preview for ROI overlay")

            if detected_roi:
                h, w = img.shape[:2]
                x0 = int(detected_roi['x0'] * w)
                x1 = int(detected_roi['x1'] * w)
                y0 = int(detected_roi['y0'] * h)
                y1 = int(detected_roi['y1'] * h)
                cv2.rectangle(img, (x0, y0), (x1, y1), (0, 0, 255), thickness=3)

            success, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if success:
                image_data = base64.b64encode(buf.tobytes()).decode('utf-8')
        except Exception:
            image_data = None

    return jsonify({
        'success': True,
        'roi': detected_roi,
        'applied': apply_roi and bool(detected_roi),
        'image': image_data
    })


@app.route('/api/capture_card_diagnostic', methods=['POST'])
def capture_card_diagnostic_route():
    """
    Diagnostic endpoint to test preview stream and gap detection.
    Returns detailed info about what the detector sees.
    """
    active_backend = scanner.preview_stream.get_resolution_info().get('backend', 'none')
    result = {
        'success': False,
        'preview': {
            'backend': active_backend,
            'device': scanner.preview_stream.device,
            'is_running': scanner.preview_stream.is_running(),
            'last_error': scanner.preview_stream.last_error,
        },
        # Backward compatibility for existing clients.
        'capture_card': {
            'device': scanner.preview_stream.device,
            'is_running': scanner.preview_stream.is_running(),
            'last_error': scanner.preview_stream.last_error,
        },
        'frame': None,
        'detection': None,
    }
    
    # Try to get a frame
    try:
        frame_bytes, used_stream = scanner.get_alignment_frame(timeout=2.0)
        if frame_bytes:
            result['frame'] = {
                'size_bytes': len(frame_bytes),
                'used_stream': used_stream,
            }
            
            # Decode and analyze
            arr = np.frombuffer(frame_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                result['frame']['width'] = int(img.shape[1])
                result['frame']['height'] = int(img.shape[0])
                
                # Convert to grayscale and compute stats
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                gray_blurred = cv2.medianBlur(gray, 5)
                stats = compute_column_stats(gray_blurred)
                
                # Compute edge strength
                edge_strength = detect_vertical_edges(gray)
                
                result['detection'] = {
                    'brightness_min': float(stats['col_mean'].min()),
                    'brightness_max': float(stats['col_mean'].max()),
                    'brightness_mean': float(stats['col_mean'].mean()),
                    'std_min': float(stats['col_std'].min()),
                    'std_max': float(stats['col_std'].max()),
                    'uniformity_max': float(stats['col_uniformity'].max()),
                    'edge_strength_max': float(edge_strength.max()),
                    'edge_strength_mean': float(edge_strength.mean()),
                }
                
                # Test gap detection with various thresholds
                for thresh in [0.60, 0.70, 0.80]:
                    gap_mask = find_gap_candidates_brightness(stats, mean_threshold=thresh, std_threshold=0.12)
                    regions = find_gap_regions(gap_mask, min_width=8, max_width=250, stats=stats, edge_strength=edge_strength)
                    result['detection'][f'gaps_at_{thresh}'] = len(regions)
                    if regions:
                        result['detection'][f'gap_widths_at_{thresh}'] = [int(r.width) for r in regions[:5]]
                
                # Use default detection for visualization
                gap_mask = find_gap_candidates_brightness(stats, mean_threshold=0.70, std_threshold=0.12)
                regions = find_gap_regions(gap_mask, min_width=8, max_width=250, stats=stats, edge_strength=edge_strength)
                
                # Draw gap regions on image
                for region in regions:
                    cv2.rectangle(img, (region.start_x, 0), (region.end_x, img.shape[0]), (0, 255, 0), 3)
                    # Draw center of gap
                    cx = (region.start_x + region.end_x) // 2
                    cv2.line(img, (cx, 0), (cx, img.shape[0]), (0, 255, 255), 1)
                
                # Draw center line
                center = img.shape[1] // 2
                cv2.line(img, (center, 0), (center, img.shape[0]), (255, 0, 0), 2)
                
                # Add text info
                cv2.putText(img, f"Gaps: {len(regions)}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                
                success, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                if success:
                    result['image'] = base64.b64encode(buf.tobytes()).decode('utf-8')
                
                result['success'] = True
        else:
            result['frame'] = {'error': 'No frame received'}
    except Exception as e:
        result['frame'] = {'error': str(e)}
        import traceback
        result['traceback'] = traceback.format_exc()
    
    return jsonify(result)


@app.route('/api/logs', methods=['POST'])
def logs_route():
    """Return recent application log lines (lightweight in-memory buffer)."""
    data = request.json or {}
    limit = data.get('limit', 200)
    return jsonify({'success': True, 'logs': scanner.get_logs(limit=limit)})
@app.route('/api/detect_alignment_roi', methods=['POST'])
def detect_alignment_roi_route():
    """Detect alignment ROI from preview stream frame."""
    if not scanner.stream_enabled:
        return jsonify({'success': False, 'message': 'Preview stream disabled'})
    
    roi = scanner.detect_alignment_roi()
    if roi:
        scanner.status_msg = "✓ ROI detected from preview stream"
        scanner.broadcast_status()
        return jsonify({'success': True, 'roi': roi})
    else:
        scanner.status_msg = "✗ ROI detection failed"
        scanner.broadcast_status()
        return jsonify({'success': False, 'message': 'ROI detection failed - check preview stream'})
@app.route('/api/calibrate', methods=['POST'])
def calibrate():
    """Start or continue calibration"""
    data = request.json
    action = data.get('action', 'start')  # start, capture_frame1, capture_frame2
    
    if scanner.strip_count > 0:
        return jsonify({'success': False, 'message': 'Already calibrated'})
    
    if action == 'capture_frame1':
        frame1_pos = scanner.position
        if not scanner.capture_image():
            return jsonify({'success': False, 'message': 'Capture failed'})
        return jsonify({'success': True, 'frame1_pos': frame1_pos})
    
    elif action == 'capture_frame2':
        frame1_pos = data.get('frame1_pos')
        frame2_pos = scanner.position
        scanner.frame_advance = frame2_pos - frame1_pos
        
        if scanner.frame_advance <= 0:
            return jsonify({'success': False, 'message': 'Frame 2 must be ahead of frame 1'})
        
        if not scanner.capture_image():
            return jsonify({'success': False, 'message': 'Capture failed'})
        
        scanner.strip_count = 1
        scanner.mode = 'calibrated'
        scanner.save_state()
        scanner.status_msg = f"✓ Calibrated: {scanner.frame_advance} steps/frame"
        scanner.broadcast_status()
        
        return jsonify({'success': True, 'frame_advance': scanner.frame_advance})
    
    return jsonify({'success': True})
@app.route('/api/new_strip', methods=['POST'])
def new_strip():
    """Start new strip"""
    if scanner.frame_advance is None:
        return jsonify({'success': False, 'message': 'Calibrate first'})
    
    data = request.json
    action = data.get('action', 'start')  # start, capture_first
    
    if action == 'capture_first':
        if not scanner.capture_image():
            return jsonify({'success': False, 'message': 'Capture failed'})
        
        scanner.strip_count += 1
        scanner.frames_in_strip = 1
        scanner.save_state()
        scanner.status_msg = f"✓ Strip {scanner.strip_count} started"
        scanner.broadcast_status()
        
        return jsonify({'success': True})
    
    # Reset strip frame count
    scanner.frames_in_strip = 0
    return jsonify({'success': True})
@app.route('/api/get_preview', methods=['POST'])
def get_preview():
    """Get a single frame from the active preview stream."""
    data = request.json or {}
    invert = bool(data.get('invert')) if isinstance(data, dict) else False

    if not scanner.stream_enabled:
        return jsonify({'success': False, 'message': 'Preview stream disabled'})

    if not scanner.ensure_preview_stream():
        return jsonify({'success': False, 'message': 'Unable to start preview stream'})

    frame = scanner.preview_stream.get_frame(timeout=1.5)
    if not frame:
        return jsonify({'success': False, 'message': 'No frame available from preview stream'})

    try:
        image_data = encode_preview_bytes(frame, invert=invert)
        backend = scanner.preview_stream.get_resolution_info().get('backend', 'unknown')
        scanner.status_msg = f"✓ Preview frame ({backend})"
        scanner.broadcast_status()
        return jsonify({'success': True, 'image': image_data, 'source': backend})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/get_preview_video', methods=['POST'])
def get_preview_video():
    """
    Get a single frame from the active preview video stream for testing.
    Optional invert (UI-only) via JSON {invert: true}.
    """
    data = request.json or {}
    invert = bool(data.get('invert')) if isinstance(data, dict) else False

    if not scanner.stream_enabled:
        return jsonify({'success': False, 'message': 'Preview stream disabled'})

    if not scanner.ensure_preview_stream():
        return jsonify({'success': False, 'message': 'Unable to start preview stream'})

    frame = scanner.preview_stream.get_frame(timeout=1.5)
    if not frame:
        return jsonify({'success': False, 'message': 'No frame available from preview stream'})

    try:
        image_data = encode_preview_bytes(frame, invert=invert)
        backend = scanner.preview_stream.get_resolution_info().get('backend', 'unknown')
        scanner.status_msg = f"✓ Preview video frame ({backend})"
        scanner.broadcast_status()
        return jsonify({'success': True, 'image': image_data, 'source': backend})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/preview_rgb', methods=['POST'])
def preview_rgb_route():
    """
    Sample RGB values from a user-selected point in the live preview.
    Request JSON:
      - x_norm: float in [0,1]
      - y_norm: float in [0,1]
      - radius: optional int sample radius in pixels (default 2)
    """
    data = request.json or {}
    try:
        x_norm = float(data.get('x_norm', 0.5))
        y_norm = float(data.get('y_norm', 0.5))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'x_norm and y_norm must be numeric'}), 400

    if not (0.0 <= x_norm <= 1.0 and 0.0 <= y_norm <= 1.0):
        return jsonify({'success': False, 'message': 'x_norm and y_norm must be between 0.0 and 1.0'}), 400

    radius_raw = data.get('radius', 2)
    try:
        radius = int(radius_raw)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'radius must be an integer'}), 400

    if not scanner.stream_enabled:
        return jsonify({'success': False, 'message': 'Preview stream disabled'}), 400

    if not scanner.ensure_preview_stream():
        return jsonify({'success': False, 'message': scanner.preview_stream.last_error or 'Unable to start preview stream'}), 503

    try:
        sampled = scanner.sample_preview_rgb(norm_x=x_norm, norm_y=y_norm, sample_radius=radius)
        backend = scanner.preview_stream.get_resolution_info().get('backend', 'unknown')
        return jsonify({
            'success': True,
            'source': backend,
            **sampled,
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/preview_video_stream')
def preview_video_stream():
    """
    MJPEG stream of live preview frames from active backend.
    Optional query param ?invert=1 for UI-only inversion.
    Returns 503 if preview stream cannot be started (client can show error and retry).
    """
    if not scanner.stream_enabled:
        return jsonify({'success': False, 'message': 'Preview stream disabled'}), 503

    if not scanner.ensure_preview_stream():
        msg = scanner.preview_stream.last_error or 'Unable to start preview stream'
        return jsonify({'success': False, 'message': msg}), 503

    invert = request.args.get('invert', '0') in ('1', 'true', 'True', 'yes')

    def generate():
        last_frame_time = time.time()
        last_yield_time = 0.0
        min_frame_interval = 1.0 / 15  # Cap at ~15 fps to reduce Pi CPU / WiFi load
        no_frame_duration_before_recover = 4.0

        while True:
            try:
                frame = scanner.preview_stream.get_frame(timeout=1.2)
                if frame is None:
                    if time.time() - last_frame_time >= no_frame_duration_before_recover:
                        scanner.ensure_preview_stream()
                        last_frame_time = time.time()
                    time.sleep(0.05)
                    continue
                last_frame_time = time.time()

                # Frame-rate limiting: skip this frame if we yielded too recently
                now = time.time()
                if now - last_yield_time < min_frame_interval:
                    time.sleep(0.005)
                    continue

                out = frame
                if invert:
                    arr = np.frombuffer(out, dtype=np.uint8)
                    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if img is None:
                        continue
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(img)
                    pil_img = ImageOps.invert(pil_img)
                    buf = io.BytesIO()
                    pil_img.save(buf, format='JPEG', quality=75)
                    out = buf.getvalue()

                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + out + b'\r\n')
                last_yield_time = time.time()
            except GeneratorExit:
                break
            except Exception:
                continue

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/autofocus', methods=['POST'])
def autofocus_route():
    """Trigger autofocus (best-effort)."""
    # Force camera check for user-initiated action
    if not scanner.check_camera(force=True):
        return jsonify({'success': False, 'message': 'Camera not connected'})
    success = scanner.autofocus()
    if success:
        return jsonify({'success': True, 'message': 'Autofocus triggered'})
    return jsonify({'success': False, 'message': 'Autofocus failed (see logs)'})


@app.route('/api/camera_settings', methods=['POST'])
def camera_settings_route():
    """Return basic exposure settings (aperture/iso/shutter) if available.
    
    NOTE: Uses rate-limited camera check to avoid repeated gphoto2 perturbing camera state.
    """
    # Use rate-limited check - settings request is less critical
    if not scanner.check_camera(force=False):
        return jsonify({'success': False, 'message': 'Camera not connected'})
    settings = scanner.get_camera_settings()
    return jsonify({'success': True, 'settings': settings})


@app.route('/api/refresh_camera', methods=['POST'])
def refresh_camera_route():
    """Force a camera connection check.
    
    Use this to reconnect to the camera after power cycling or USB reconnect.
    This bypasses the rate limiting that prevents frequent checks.
    
    NOTE: Frequent gphoto2 commands can disturb some camera settings/state.
    Only use this when you need to verify camera connection.
    """
    # Force an immediate camera check
    connected = scanner.check_camera(force=True, retry_with_usb_clear=True)
    scanner.broadcast_status()
    
    if connected:
        return jsonify({
            'success': True,
            'message': f'Camera connected: {scanner.camera_model}',
            'camera_model': scanner.camera_model,
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Camera not detected',
            'error': scanner.camera_error,
        })
@app.route('/api/update_step_sizes', methods=['POST'])
def update_step_sizes():
    """Update motor step sizes"""
    data = request.json
    fine_step = data.get('fine_step')
    coarse_step = data.get('coarse_step')
    
    if not fine_step or not coarse_step:
        return jsonify({'success': False, 'message': 'Both step sizes required'})
    
    try:
        scanner.fine_step = int(fine_step)
        scanner.coarse_step = int(coarse_step)
        
        # Update coarse step size on Arduino
        if scanner.arduino:
            scanner.arduino.write(f'l{scanner.coarse_step}\n'.encode())
            time.sleep(0.1)
        
        scanner.status_msg = f"Step sizes: Fine={scanner.fine_step}, Coarse={scanner.coarse_step}"
        scanner.broadcast_status()
        
        print(f"✓ Step sizes updated: Fine={scanner.fine_step}, Coarse={scanner.coarse_step}")
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"✗ Failed to update step sizes: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/stream/info', methods=['GET'])
def stream_info():
    """Get stream status for active preview backend."""
    info = scanner.preview_stream.get_resolution_info()
    return jsonify({
        'success': True,
        'stream_enabled': scanner.stream_enabled,
        'stream_running': scanner.preview_stream.is_running(),
        'resolution': info,
        'preview_source_preference': scanner.preview_source_preference,
        'preview_source_active': info.get('backend', 'none'),
        'device': scanner.preview_stream.device,
        'last_error': scanner.preview_stream.last_error,
    })


@app.route('/api/preview_source', methods=['GET', 'POST'])
def preview_source():
    """Get or update preview source preference: auto, capture_card, or gphoto."""
    valid = {'auto', 'capture_card', 'gphoto'}

    if request.method == 'GET':
        info = scanner.preview_stream.get_resolution_info()
        return jsonify({
            'success': True,
            'preference': scanner.preview_source_preference,
            'active': info.get('backend', 'none'),
        })

    data = request.json or {}
    preference = str(data.get('source', '')).strip().lower()
    if preference not in valid:
        return jsonify({
            'success': False,
            'message': "Invalid source. Use 'auto', 'capture_card', or 'gphoto'.",
        }), 400

    scanner.preview_source_preference = preference
    scanner.stop_preview_stream()
    started = scanner.ensure_preview_stream()
    info = scanner.preview_stream.get_resolution_info()
    scanner.broadcast_status()
    return jsonify({
        'success': started,
        'preference': scanner.preview_source_preference,
        'active': info.get('backend', 'none'),
        'message': 'Preview source updated' if started else (scanner.preview_stream.last_error or 'Failed to start preview source'),
    })


def _do_full_stream_restart():
    """Background: stop stream, wait for device release, start again. Avoids blocking HTTP."""
    try:
        scanner.log("↻ Full stream restart (release + 2.5s delay)...")
        scanner.preview_stream.stop()
        time.sleep(2.5)
        scanner.preview_stream.start()
        scanner.log("↻ Stream restart complete")
    except Exception as e:
        scanner.log(f"✗ Stream restart failed: {e}")


@app.route('/api/stream/restart', methods=['POST'])
def stream_restart():
    """
    Restart the preview stream.
    POST body: { "full": true } to do a full recovery (stop + 2.5s delay + start).
    Returns immediately so the client does not hit a timeout; full restart runs in background.
    """
    try:
        data = request.json or {}
        full_recovery = data.get('full', False)
        if full_recovery:
            threading.Thread(target=_do_full_stream_restart, daemon=True).start()
            msg = 'Restarting stream... (reload in a few seconds if needed)'
        else:
            scanner.preview_stream.restart_stream()
            msg = 'Stream restarted'
        return jsonify({
            'success': True,
            'message': msg,
            'resolution': scanner.preview_stream.get_resolution_info(),
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    emit('status_update', scanner.get_status())
@socketio.on('request_status')
def handle_status_request():
    """Handle status request
    
    NOTE: Camera check is rate-limited to avoid disturbing camera state via
    repeated gphoto2 probing.
    """
    # Use rate-limited camera check (won't actually check if checked recently)
    scanner.check_camera(force=False)
    emit('status_update', scanner.get_status())
if __name__ == '__main__':
    try:
        # Handle command line arguments
        import argparse
        parser = argparse.ArgumentParser(description='Film Scanner Web Application')
        parser.add_argument('--reset', action='store_true', help='Reset configuration and run setup')
        parser.add_argument('--config', action='store_true', help='Show current configuration')
        args = parser.parse_args()
        
        # Initialize configuration manager
        config_mgr = ConfigManager()
        
        # Handle special commands
        if args.reset:
            config_mgr.delete_config()
            print("\n✓ Configuration reset. Restart the application to run setup.\n")
            sys.exit(0)
        
        if args.config:
            config_mgr.print_config()
            sys.exit(0)
        
        # Get or create configuration
        print("\n" + "="*60)
        print("   FILM SCANNER WEB APPLICATION")
        print("="*60 + "\n")
        
        config = config_mgr.get_config()
        if not config:
            print("\n❌ Setup failed or cancelled\n")
            sys.exit(1)
        
        # Display configuration
        print(f"\n📍 Mode: {config.get('mode', 'unknown')}")
        print(f"📍 Pi IP: {config.get('pi_ip', 'unknown')}")
        print(f"📍 Port: {config.get('port', 5000)}")
        
        # USB cleanup: non-fatal so app still starts if this hangs/fails at boot
        try:
            clear_usb_for_camera()
        except Exception as e:
            print(f"⚠ USB cleanup skipped: {e}")
        
        # Auto-connect to Arduino on startup (non-fatal)
        print("\n🔌 Searching for Arduino (R3/R4 supported)...")
        try:
            if scanner.find_arduino():
                print(f"✓ Arduino connected: {scanner.arduino_board}")
                print(f"   Port: {scanner.arduino_port}")
            else:
                print("✗ Arduino not found (you can connect later via the web interface)")
        except Exception as e:
            print(f"⚠ Arduino check skipped: {e}")
        
        # Camera check (non-fatal)
        print("\n📷 Camera Detection")
        try:
            if scanner.check_camera(retry_with_usb_clear=True, max_retries=3):
                print(f"✓ Camera ready: {scanner.camera_model}")
            else:
                print("⚠ Camera not detected at startup")
        except Exception as e:
            print(f"⚠ Camera check skipped: {e}")
        
        # Start web server
        host = '0.0.0.0'
        port = config.get('port', 5000)
        pi_ip = config.get('pi_ip', 'localhost')
        
        print("\n" + "="*60)
        print("   WEB SERVER STARTING")
        print("="*60)
        print(f"\n🌐 Access the scanner from your device:")
        print(f"   • http://{pi_ip}:{port}")
        print("\n💡 Tip: To reset configuration, run:")
        print("   python3 web_app.py --reset")
        print("="*60 + "\n")
        
        # Safety check: if another instance is already on this port (e.g. spawned
        # by the touchscreen service), exit cleanly so systemd won't restart-loop.
        import socket as _sock
        _probe = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
        try:
            _probe.bind((host, port))
            _probe.close()
        except OSError:
            print(f"\n⚠ Port {port} is already in use (another web_app.py instance may be running via touchscreen service).")
            print("Exiting cleanly to avoid conflict.")
            sys.exit(0)  # clean exit → Restart=on-failure won't restart
        
        socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
    except SystemExit:
        raise
    except Exception as e:
        print("\n❌ Film Scanner failed to start:")
        traceback.print_exc()
        sys.exit(1)
