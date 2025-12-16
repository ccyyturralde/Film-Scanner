#!/usr/bin/env python3
"""
35mm Film Scanner - Web Application
Mobile-friendly web interface for film scanning

Supports:
- Arduino Uno R3 (ATmega328P with ATmega16U2 USB bridge)
- Arduino Uno R4 Minima (Renesas RA4M1 with native USB)
- Arduino Uno R4 WiFi (Renesas RA4M1 with ESP32-S3)
"""
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import serial
import serial.tools.list_ports
import subprocess
import time
import os
import sys
from datetime import datetime
import json
import threading
import base64
import tempfile
import shutil
import traceback
import re
from config_manager import ConfigManager
from frame_detector import detect_frame_gap
try:
    from PIL import Image, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠ PIL/Pillow not available - image preview will be limited")

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
socketio = SocketIO(app, cors_allowed_origins="*")
class FilmScanner:
    def __init__(self):
        self.arduino = None
        self.arduino_port = None
        self.arduino_board = "Unknown"  # Track board type (R3/R4)
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
        
        # Motor configuration
        self.fine_step = 8
        self.coarse_step = 192  # 3x larger for better coarse control
        self.step_delay = 800
        
        # Calibration data
        self.frame_advance = None
        self.default_advance = 1200
        self.px_per_step = 3.0  # adaptive estimate for auto-align
        self.alignment_confidence = 0.0
        self.last_gap_px = None
        
        # Position tracking
        self.position = 0
        self.frame_positions = []
        
        # Mode control
        self.mode = 'manual'
        self.auto_advance = True
        
        # State persistence
        self.state_file = None
        
        # Lock for thread safety
        self.lock = threading.Lock()
    
        # RLock to prevent gphoto2 conflicts across routes (reentrant for recursive calls)
        self.camera_op_lock = threading.RLock()
    
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
        """Find Arduino on available ports (supports R3 and R4)"""
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
            # Try to read any available data without blocking
            self.arduino.timeout = 0.1
            self.arduino.reset_input_buffer()
            self.arduino.write(b'?\n')
            time.sleep(0.2)
            response = self.arduino.read(100).decode('ascii', errors='ignore')
            
            # Check if we got a valid response
            if response and ('Position' in response or 'READY' in response or 'Film' in response):
                return True
            
            # No valid response, connection may be dead
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
        """Send command to Arduino with error handling and retry - optimized for responsiveness"""
        # Quick check - don't verify connection on every command (causes disconnects)
        if not self.arduino:
            print(f"✗ Cannot send command '{cmd}': No Arduino connection")
            self.broadcast_status()
            return False
        
        try:
            # Clear buffer and send command
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
            
        except serial.SerialException as e:
            print(f"✗ Serial error sending '{cmd}': {e}")
            
            # Mark connection as bad
            try:
                self.arduino.close()
            except:
                pass
            self.arduino = None
            
            # Try to reconnect and retry command once
            if retry:
                print("🔄 Retrying command after reconnection...")
                time.sleep(0.5)  # Give port time to release
                if self.find_arduino():
                    print("✓ Reconnected, retrying command...")
                    return self.send(cmd, retry=False, update_position=update_position)
            
            self.broadcast_status()
            return False
            
        except Exception as e:
            print(f"✗ Unexpected error sending '{cmd}': {e}")
            self.broadcast_status()
            return False
    
    def check_camera(self):
        """Check if camera is connected without killing gphoto2 or interrupting ops"""
        try:
            # If another camera operation is in progress (preview/capture), don't interrupt it.
            if self.camera_op_lock.locked():
                return self.camera_connected
            # Passive detect; no kill here.
            result = subprocess.run(
                ["gphoto2", "--auto-detect"],
                capture_output=True, timeout=10, text=True
            )
            if result.returncode == 0 and "usb" in result.stdout.lower():
                lines = result.stdout.strip().splitlines()
                for line in lines:
                    if "usb:" in line.lower():
                        self.camera_connected = True
                        self.camera_name = line.strip()
                        print(f"✓ Camera detected: {self.camera_name}")
                        break
            else:
                self.camera_connected = False
        except Exception as e:
            print(f"✗ Error checking camera: {e}")
            # Don't change state on exception
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
            # Also kill gvfs which can interfere
            subprocess.run(["killall", "gvfs-gphoto2-volume-monitor"], 
                         capture_output=True, timeout=1)
            time.sleep(0.3)
            # Kill any PTP processes that might be hanging
            subprocess.run(["killall", "-9", "PTPCamera"], 
                         capture_output=True, timeout=1)
            time.sleep(0.3)
            # Total wait: 1 second for USB to fully release
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
    
    def check_viewfinder_state(self):
        """Query viewfinder state without killing other gphoto2 ops"""
        try:
            result = subprocess.run(
                ["gphoto2", "--get-config", "viewfinder"],
                capture_output=True, timeout=10, text=True
            )
            if result.returncode == 0 and result.stdout:
                if "Current: 1" in result.stdout or "Current: On" in result.stdout:
                    self.viewfinder_enabled = True
                elif "Current: 0" in result.stdout or "Current: Off" in result.stdout:
                    self.viewfinder_enabled = False
            elif result.stderr:
                print(f"viewfinder query stderr: {result.stderr.strip()}")
        except Exception as e:
            print(f"✗ Error checking viewfinder: {e}")
        return self.viewfinder_enabled
    def enable_viewfinder(self):
        """Enable camera viewfinder - REQUIRED for live preview on Canon R100"""
        try:
            print("📷 Checking viewfinder state...")
            
            # First check if already enabled
            if self.check_viewfinder_state():
                print("✓ Viewfinder already enabled")
                return True
            
            # Not enabled, so enable it
            print("   Enabling viewfinder...")
            self._kill_gphoto2()
            
            result = subprocess.run(
                ["gphoto2", "--set-config", "viewfinder=1"],
                capture_output=True, timeout=10, text=True
            )
            
            if result.returncode == 0:
                self.viewfinder_enabled = True
                print("✓ Viewfinder enabled")
                time.sleep(0.5)  # Give camera time to enter live view
                return True
            else:
                print(f"✗ Failed to enable viewfinder (return code: {result.returncode})")
                if result.stderr:
                    print(f"   Error: {result.stderr.strip()}")
                return False
                
        except subprocess.TimeoutExpired:
            print("✗ Viewfinder enable timeout")
            self._kill_gphoto2()
            return False
        except Exception as e:
            print(f"✗ Viewfinder enable error: {e}")
            return False
    
    def disable_viewfinder(self):
        """Disable camera viewfinder to save battery"""
        try:
            print("📷 Disabling viewfinder...")
            self._kill_gphoto2()
            
            result = subprocess.run(
                ["gphoto2", "--set-config", "viewfinder=0"],
                capture_output=True, timeout=10, text=True
            )
            
            if result.returncode == 0:
                self.viewfinder_enabled = False
                print("✓ Viewfinder disabled")
                return True
            else:
                print(f"✗ Failed to disable viewfinder (return code: {result.returncode})")
                return False
                
        except subprocess.TimeoutExpired:
            print("✗ Viewfinder disable timeout")
            self._kill_gphoto2()
            return False
        except Exception as e:
            print(f"✗ Viewfinder disable error: {e}")
            return False
    
    def capture_image(self, retry=True):
        """Capture image to camera SD card with exclusive access"""
        # Ensure exclusive access - RLock allows recursive acquisition by same thread
        with self.camera_op_lock:
            try:
                # Clean any stray gphoto2 from previous ops
                self._kill_gphoto2()
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
        """Capture a preview image and return raw JPEG bytes (no inversion)."""
        if not self.check_camera():
            raise RuntimeError("Camera not connected")

        temp_dir = None
        original_dir = os.getcwd()
        try:
            temp_dir = tempfile.mkdtemp()
            with self.camera_op_lock:
                self._kill_gphoto2()
                time.sleep(0.5)

                if not self.enable_viewfinder():
                    raise RuntimeError("Failed to enable viewfinder")

                os.chdir(temp_dir)
                try:
                    result = subprocess.run(
                        ["gphoto2", "--capture-preview", "--force-overwrite"],
                        capture_output=True,
                        timeout=10,
                        text=True
                    )
                finally:
                    try:
                        os.chdir(original_dir)
                    except Exception:
                        pass  # Don't mask subprocess errors; outer finally handles cleanup

                if result.returncode != 0:
                    raise RuntimeError(f"Preview capture failed: {result.stderr.strip() if result.stderr else result.returncode}")

                files = os.listdir(temp_dir)
                preview_path = os.path.join(temp_dir, "preview.jpg")
                if not os.path.exists(preview_path):
                    jpgs = [f for f in files if f.lower().endswith(('.jpg', '.jpeg'))]
                    if not jpgs:
                        raise RuntimeError("No preview file created")
                    preview_path = os.path.join(temp_dir, jpgs[0])

                with open(preview_path, "rb") as f:
                    data = f.read()

                if len(data) < 1000:
                    raise RuntimeError("Preview image too small/corrupt")

                return data
        finally:
            # Ensure we're back in original directory
            try:
                os.chdir(original_dir)
            except Exception:
                pass
            # Clean up temp directory
            if temp_dir:
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass

    def auto_align(self, max_iters=5, stop_px=6, max_step=600, min_step=8, prefer_forward=True):
        """
        Closed-loop auto alignment using preview edge detection.
        Returns (success, message, result_dict).
        """
        prev_offset = None
        last_move_steps = None
        offset = 0  # Initialize to handle max_iters=0 edge case

        for iteration in range(max_iters):
            preview_bytes = self.capture_preview_bytes()
            detection = detect_frame_gap(preview_bytes)

            # Update shared state under lock for thread safety
            with self.lock:
                self.last_gap_px = detection.gap_x
                self.alignment_confidence = detection.confidence

            if detection.confidence < 0.15:
                return False, "Low confidence in frame edge detection", {
                    "confidence": detection.confidence,
                    "offset_px": detection.offset_px,
                }

            offset = detection.offset_px
            if abs(offset) <= stop_px:
                with self.lock:
                    self.status_msg = "✓ Auto-aligned"
                return True, "Aligned", {
                    "confidence": detection.confidence,
                    "offset_px": offset,
                    "gap_x": detection.gap_x,
                }

            # Bias first move forward to avoid pulling film back on first frame
            commanded_offset = offset
            if iteration == 0 and prefer_forward and offset < 0:
                commanded_offset = abs(offset)

            with self.lock:
                px_per_step = max(0.5, float(self.px_per_step))
            step_float = commanded_offset / px_per_step
            steps = int(round(step_float))
            if abs(steps) < min_step:
                steps = min_step if commanded_offset >= 0 else -min_step
            if abs(steps) > max_step:
                steps = max_step if steps > 0 else -max_step

            direction_cmd = 'H' if steps >= 0 else 'h'
            success = self.send(f"{direction_cmd}{abs(steps)}")
            if not success:
                return False, "Motor move failed during auto-align", {
                    "confidence": detection.confidence,
                    "offset_px": offset,
                }

            # Update px_per_step estimate from observed change once we have two offsets
            if prev_offset is not None and last_move_steps is not None and last_move_steps != 0:
                delta_px = prev_offset - offset
                if delta_px != 0:
                    est = abs(delta_px) / abs(last_move_steps)
                    if 0.1 < est < 50:  # sanity bounds
                        with self.lock:
                            self.px_per_step = 0.7 * self.px_per_step + 0.3 * est

            prev_offset = offset
            last_move_steps = steps

        with self.lock:
            self.status_msg = "✗ Auto-align failed to converge"
            alignment_conf = self.alignment_confidence
        return False, "Failed to converge", {
            "confidence": alignment_conf,
            "offset_px": offset,
        }
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
            'frame_positions': self.frame_positions,
            'mode': self.mode,
            'auto_advance': self.auto_advance,
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
                self.frame_positions = state.get('frame_positions', [])
                self.mode = state.get('mode', 'manual')
                self.auto_advance = state.get('auto_advance', True)
                return True
        return False
    
    def advance_frame(self):
        """Advance one full frame forward using calibrated distance"""
        if self.frame_advance:
            success = self.send(f'H{self.frame_advance}')
            if success:
                self.status_msg = f"Advanced {self.frame_advance} steps"
                return True
            else:
                self.status_msg = "❌ Advance failed - Check Arduino"
                return False
        return False
    
    def backup_frame(self):
        """Backup one full frame using calibrated distance"""
        if self.frame_advance:
            # Use 'h' command for backward movement (lowercase = reverse direction)
            # Note: 'H' only accepts positive values; 'h' moves backward with positive value
            success = self.send(f'h{self.frame_advance}')
            if success:
                self.status_msg = f"Backed up {self.frame_advance} steps"
                return True
            else:
                self.status_msg = "❌ Backup failed - Check Arduino"
                return False
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
                'auto_advance': self.auto_advance,
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
                'last_gap_px': self.last_gap_px
            }
        
        return status
    
    def broadcast_status(self):
        """Broadcast status to all connected clients"""
        socketio.emit('status_update', self.get_status())
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
    """Create new roll"""
    data = request.json
    roll_name = data.get('roll_name', '')
    
    if not roll_name:
        return jsonify({'success': False, 'message': 'Roll name required'})
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    base_folder = os.path.expanduser("~/scans")
    scanner.roll_folder = os.path.join(base_folder, date_str, roll_name)
    os.makedirs(scanner.roll_folder, exist_ok=True)
    
    scanner.state_file = os.path.join(scanner.roll_folder, '.scan_state.json')
    
    resume = data.get('resume', False)
    if os.path.exists(scanner.state_file) and resume:
        scanner.load_state(scanner.roll_folder)
        scanner.status_msg = f"Resumed: {roll_name}"
    else:
        scanner.frame_count = 0
        scanner.strip_count = 0
        scanner.frames_in_strip = 0
        scanner.frame_advance = None
        scanner.frame_positions = []
        scanner.status_msg = f"New roll: {roll_name}"
    
    scanner.roll_name = roll_name
    scanner.save_state()
    scanner.broadcast_status()
    
    return jsonify({'success': True})
@app.route('/api/move', methods=['POST'])
def move():
    """Move motor - optimized for quick response"""
    data = request.json
    direction = data.get('direction', 'forward')
    size = data.get('size', 'fine')
    
    if direction == 'forward':
        cmd = 'F' if size == 'coarse' else 'f'
    else:
        cmd = 'B' if size == 'coarse' else 'b'
    
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
    if not scanner.check_camera():
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
    """Capture image"""
    data = request.json or {}
    auto_align_before = data.get('auto_align', False)

    if not scanner.roll_name:
        return jsonify({'success': False, 'message': 'Create roll first'})
    
    if not scanner.check_camera():
        return jsonify({'success': False, 'message': 'Camera not connected'})
    
    if auto_align_before:
        try:
            success, msg, info = scanner.auto_align()
            scanner.broadcast_status()
            if not success:
                return jsonify({'success': False, 'message': f'Auto-align failed: {msg}', 'info': info})
        except Exception as e:
            scanner.status_msg = "✗ Auto-align error"
            scanner.broadcast_status()
            return jsonify({'success': False, 'message': f'Auto-align error: {str(e)}'})

    scanner.status_msg = "Capturing..."
    scanner.broadcast_status()
    
    success = scanner.capture_image()
    
    if success:
        scanner.status_msg = f"✓ Frame {scanner.frame_count} (Strip {scanner.strip_count})"
        
        # Auto-advance AFTER capture (for calibrated mode)
        # Advances to next frame position so user is ready for next capture
        if scanner.mode == 'calibrated' and scanner.auto_advance and scanner.frame_advance:
            time.sleep(0.3)  # Brief pause before advancing
            if scanner.send(f'H{scanner.frame_advance}'):
                scanner.status_msg = f"✓ Frame {scanner.frame_count} → Ready for next"
            else:
                scanner.status_msg = f"✓ Frame {scanner.frame_count} (advance failed)"
    else:
        scanner.status_msg = "❌ Capture failed!"
    
    scanner.broadcast_status()
    return jsonify({'success': success})


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
        })
    except Exception as e:
        with scanner.lock:
            scanner.status_msg = "✗ Auto-align error"
        scanner.broadcast_status()
        return jsonify({'success': False, 'message': str(e)})
@app.route('/api/calibrate', methods=['POST'])
def calibrate():
    """Start or continue calibration"""
    data = request.json
    action = data.get('action', 'start')  # start, capture_frame1, capture_frame2
    
    if not scanner.roll_name:
        return jsonify({'success': False, 'message': 'Create roll first'})
    
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
    if not scanner.roll_name:
        return jsonify({'success': False, 'message': 'Create roll first'})
    
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
    """Get live preview from camera - Canon R100 requires viewfinder enabled first"""
    if not scanner.check_camera():
        return jsonify({
            'success': False,
            'message': 'Camera not connected',
            'error': scanner.camera_error
        })
    
    scanner.status_msg = "Getting live preview..."
    scanner.broadcast_status()
    
    # Create temp directory
    temp_dir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    
    try:
        # Ensure exclusive access to gphoto2 during preview
        scanner.camera_op_lock.acquire()
        print("\n📷 Capturing live preview from camera...")
        scanner._kill_gphoto2()
        time.sleep(0.5)
        
        # CRITICAL: Enable viewfinder first (Canon R100 requirement)
        # Per r100-liveview-testing.md: viewfinder MUST be enabled for --capture-preview to work
        print("   Step 1: Checking/enabling viewfinder...")
        if not scanner.enable_viewfinder():
            print("✗ Failed to enable viewfinder")
            scanner.status_msg = "✗ Cannot enable viewfinder"
            scanner.broadcast_status()
            return jsonify({
                'success': False,
                'message': 'Failed to enable viewfinder. Required for live preview.'
            })
        
        # Change to temp directory
        os.chdir(temp_dir)
        print(f"   Working directory: {temp_dir}")
        
        # Step 2: Capture preview with viewfinder enabled
        print("   Step 2: Capturing preview (viewfinder enabled)...")
        print("   Running: gphoto2 --capture-preview --force-overwrite")
        result = subprocess.run(
            ["gphoto2", "--capture-preview", "--force-overwrite"],
            capture_output=True,
            timeout=10,
            text=True
        )
        
        # Restore directory
        os.chdir(original_dir)
        
        print(f"   Return code: {result.returncode}")
        if result.stdout:
            print(f"   stdout: {result.stdout.strip()}")
        if result.stderr:
            print(f"   stderr: {result.stderr.strip()}")
        
        time.sleep(0.2)
        
        # Check what files were created
        files = os.listdir(temp_dir)
        print(f"   Files in directory: {files}")
        
        # Look for preview.jpg (default name for --capture-preview)
        preview_path = os.path.join(temp_dir, "preview.jpg")
        
        if not os.path.exists(preview_path):
            # Look for any JPG files
            preview_files = [f for f in files if f.lower().endswith(('.jpg', '.jpeg'))]
            
            if not preview_files:
                print("✗ No preview file created")
                print("   → This shouldn't happen if viewfinder was enabled")
                print("   → Check camera is in PTP mode")
                scanner.status_msg = "✗ No preview file"
                scanner.broadcast_status()
                return jsonify({
                    'success': False,
                    'message': 'No preview file created despite viewfinder being enabled.'
                })
            
            preview_path = os.path.join(temp_dir, preview_files[0])
            print(f"   Using: {preview_files[0]}")
        else:
            print(f"   Found: preview.jpg")
        
        # Read the image
        file_size = os.path.getsize(preview_path)
        print(f"   Image size: {file_size} bytes")
        
        # Check minimum size
        if file_size < 1000:
            print("✗ Image too small (corrupt)")
            scanner.status_msg = "✗ Preview corrupt"
            scanner.broadcast_status()
            return jsonify({'success': False, 'message': 'Preview image corrupt or too small'})
        
        # Convert negative to positive if PIL is available
        if PIL_AVAILABLE:
            try:
                print("   Converting negative to positive...")
                img = Image.open(preview_path)
                
                # Convert to RGB if needed
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Invert the image (negative to positive)
                img_inverted = ImageOps.invert(img)
                
                # Save as JPG to buffer
                from io import BytesIO
                buffer = BytesIO()
                img_inverted.save(buffer, format='JPEG', quality=85)
                image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                print("   ✓ Converted to positive")
                
            except Exception as e:
                print(f"   ⚠ Conversion failed: {e}, using original")
                with open(preview_path, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
        else:
            # No PIL, just encode original
            print("   (PIL not available, showing as negative)")
            with open(preview_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
        
        scanner.status_msg = "✓ Live preview ready"
        scanner.broadcast_status()
        
        print(f"✓ Live preview successful")
        
        # Clean up any lingering gphoto2 processes after preview
        scanner._kill_gphoto2()
        
        return jsonify({'success': True, 'image': image_data})
        
    except subprocess.TimeoutExpired:
        scanner._kill_gphoto2()  # Clean up on timeout
        try:
            os.chdir(original_dir)
        except:
            pass
        print("✗ Preview timeout")
        scanner.status_msg = "✗ Preview timeout"
        scanner.broadcast_status()
        return jsonify({'success': False, 'message': 'Preview capture timeout'})
        
    except Exception as e:
        try:
            os.chdir(original_dir)
        except:
            pass
        scanner._kill_gphoto2()  # Clean up on error
        print(f"✗ Preview error: {e}")
        traceback.print_exc()
        scanner.status_msg = f"✗ Error"
        scanner.broadcast_status()
        return jsonify({'success': False, 'message': str(e)})
        
    finally:
        if scanner.camera_op_lock.locked():
            try:
                scanner.camera_op_lock.release()
            except RuntimeError:
                pass
        try:
            os.chdir(original_dir)
        except:
            pass
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass
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
# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    emit('status_update', scanner.get_status())
@socketio.on('request_status')
def handle_status_request():
    """Handle status request"""
    scanner.check_camera()
    emit('status_update', scanner.get_status())
if __name__ == '__main__':
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
    
    # Clean up any existing gphoto2 processes from previous runs
    print("\n🧹 Cleaning up any existing gphoto2 processes...")
    scanner._kill_gphoto2()
    print("✓ Process cleanup complete")
    
    # Auto-connect to Arduino on startup
    print("\n🔌 Searching for Arduino (R3/R4 supported)...")
    if scanner.find_arduino():
        print(f"✓ Arduino connected: {scanner.arduino_board}")
        print(f"   Port: {scanner.arduino_port}")
    else:
        print("✗ Arduino not found (you can connect later via the web interface)")
        print("   Supported boards: Arduino Uno R3, R4 Minima, R4 WiFi")
    
    # Check for camera
    print("\n📷 Camera Setup")
    print("  • USB Camera: gphoto2 for capture and preview")
    print("  • Autofocus: Automatic during capture")
    print("  • Preview: On-demand via web interface")
    
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
    
    # Run without debug mode to prevent reloads that disrupt Arduino connection
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
