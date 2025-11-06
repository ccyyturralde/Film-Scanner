#!/usr/bin/env python3
"""
35mm Film Scanner - Web Application
Mobile-friendly web interface for film scanning
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
import requests
from config_manager import ConfigManager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'film-scanner-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

class FilmScanner:
    def __init__(self):
        self.arduino = None
        self.arduino_port = None
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
        
        # Remote camera server configuration
        self.camera_server_url = None
        self.use_remote_camera = False
        self.remote_camera_available = False
        
        # Motor configuration
        self.fine_step = 8
        self.coarse_step = 192  # 3x larger for better coarse control
        self.step_delay = 800
        
        # Calibration data
        self.frame_advance = None
        self.default_advance = 1200
        
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
    
    def find_arduino(self):
        """Find Arduino on available ports"""
        # Close existing connection if any
        if self.arduino:
            try:
                self.arduino.close()
            except:
                pass
            self.arduino = None
        
        ports = list(serial.tools.list_ports.comports())
        
        pi_ports = ['/dev/ttyACM0', '/dev/ttyUSB0', '/dev/serial0', '/dev/ttyAMA0']
        for port_path in pi_ports:
            if os.path.exists(port_path):
                class SimplePort:
                    def __init__(self, device):
                        self.device = device
                ports.append(SimplePort(port_path))
        
        for port in ports:
            device = port.device if hasattr(port, 'device') else str(port)
            
            try:
                ser = serial.Serial(device, 115200, timeout=3)
                time.sleep(2.5)  # Give Arduino time to reset after connection
                
                # Clear any startup messages
                ser.reset_input_buffer()
                time.sleep(0.1)
                
                ser.write(b'?\n')
                time.sleep(0.3)
                response = ser.read(200).decode('ascii', errors='ignore')
                
                if 'Film' in response or 'READY' in response or 'Position' in response:
                    self.arduino = ser
                    self.arduino_port = device
                    
                    # Configure coarse step size
                    time.sleep(0.1)
                    self.arduino.write(f'l{self.coarse_step}\n'.encode())
                    time.sleep(0.1)
                    
                    print(f"✓ Arduino connected on {device}")
                    self.broadcast_status()
                    return True
                
                ser.close()
            except Exception as e:
                print(f"✗ Failed to connect to {device}: {e}")
                continue
        
        self.arduino = None
        self.arduino_port = None
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
    
    def send(self, cmd, retry=True):
        """Send command to Arduino with error handling and retry"""
        if not self.ensure_connection():
            print(f"✗ Cannot send command '{cmd}': No Arduino connection")
            self.broadcast_status()
            return False
        
        try:
            # Send command
            self.arduino.reset_input_buffer()
            self.arduino.write(f"{cmd}\n".encode())
            time.sleep(0.1)
            
            # Update position for movement commands
            if cmd in ['f', 'F', 'b', 'B'] or cmd.startswith('H') or cmd.startswith('Z'):
                time.sleep(0.3)  # Give motor time to move
                
                # Query position
                self.arduino.write(b'?\n')
                time.sleep(0.2)
                response = self.arduino.read(200).decode('ascii', errors='ignore')
                
                for line in response.split('\n'):
                    if 'Position' in line:
                        try:
                            pos_str = line.split(':')[1].strip().split()[0]
                            self.position = int(pos_str)
                        except Exception as e:
                            print(f"✗ Failed to parse position: {e}")
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
                if self.ensure_connection():
                    return self.send(cmd, retry=False)
            
            self.broadcast_status()
            return False
            
        except Exception as e:
            print(f"✗ Unexpected error sending '{cmd}': {e}")
            self.broadcast_status()
            return False
    
    def setup_remote_camera(self, server_url):
        """Setup connection to remote camera server"""
        if not server_url:
            return False
        
        # Normalize URL
        if not server_url.startswith('http'):
            server_url = f'http://{server_url}'
        if server_url.endswith('/'):
            server_url = server_url[:-1]
        
        self.camera_server_url = server_url
        
        # Test connection
        try:
            response = requests.get(f'{server_url}/api/status', timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.use_remote_camera = True
                self.remote_camera_available = True
                self.camera_connected = data.get('camera_connected', False)
                self.camera_model = data.get('camera_model', 'Remote Camera')
                print(f"✓ Connected to remote camera server: {server_url}")
                return True
        except Exception as e:
            print(f"✗ Failed to connect to remote camera server: {e}")
            self.remote_camera_available = False
            return False
    
    def check_remote_camera(self):
        """Check remote camera server status"""
        if not self.camera_server_url:
            return False
        
        try:
            response = requests.get(f'{self.camera_server_url}/api/check-camera', timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.camera_connected = data.get('connected', False)
                self.camera_model = data.get('model', 'Unknown')
                return self.camera_connected
        except Exception as e:
            print(f"✗ Remote camera check failed: {e}")
            self.camera_connected = False
            return False
    
    def check_camera(self):
        """Check camera connection (local or remote)"""
        # If using remote camera server, check that instead
        if self.use_remote_camera and self.camera_server_url:
            return self.check_remote_camera()
        
        # Otherwise check for local gphoto2 USB camera
        current_time = time.time()
        if current_time - self.last_camera_check < 5:
            return self.camera_connected
        
        self.last_camera_check = current_time
        self.camera_error = None
        
        try:
            self._kill_gphoto2()
            
            result = subprocess.run(
                ["gphoto2", "--auto-detect"],
                capture_output=True, timeout=10, text=True
            )
            
            if result.returncode == 0 and "usb" in result.stdout.lower():
                lines = result.stdout.strip().split('\n')
                for line in lines[2:]:
                    if 'usb' in line.lower():
                        self.camera_model = line.split('usb')[0].strip()
                        self.camera_connected = True
                        print(f"✓ Camera detected: {self.camera_model}")
                        return True
            
            self.camera_connected = False
            self.camera_model = "Not detected"
            self.camera_error = "No camera found on USB. Check connection and USB mode (PTP)."
            print(f"✗ {self.camera_error}")
            if result.stderr:
                print(f"   Details: {result.stderr.strip()}")
            return False
            
        except subprocess.TimeoutExpired:
            self.camera_connected = False
            self.camera_model = "Check timeout"
            self.camera_error = "Camera detection timed out"
            print(f"✗ {self.camera_error}")
            return False
            
        except Exception as e:
            self.camera_connected = False
            self.camera_model = "Check failed"
            self.camera_error = str(e)
            print(f"✗ Camera check failed: {e}")
            return False
    
    def _kill_gphoto2(self):
        """Thoroughly kill any gphoto2 processes"""
        try:
            # Kill gracefully first
            subprocess.run(["killall", "gphoto2"], 
                         capture_output=True, timeout=1)
            time.sleep(0.1)
            # Force kill any remaining
            subprocess.run(["killall", "-9", "gphoto2"], 
                         capture_output=True, timeout=1)
            # Also kill gvfs which can interfere
            subprocess.run(["killall", "gvfs-gphoto2-volume-monitor"], 
                         capture_output=True, timeout=1)
            time.sleep(0.5)  # Give system time to release USB
        except:
            pass
    
    def autofocus(self):
        """Trigger camera autofocus (local or remote)"""
        # Use remote camera server if configured
        if self.use_remote_camera and self.camera_server_url:
            try:
                print("📷 Triggering remote autofocus...")
                response = requests.post(
                    f'{self.camera_server_url}/api/autofocus',
                    timeout=15
                )
                if response.status_code == 200:
                    print("✓ Remote autofocus triggered successfully")
                    time.sleep(2.0)
                    return True
                else:
                    print(f"✗ Remote autofocus failed: {response.json().get('error')}")
                    return False
            except Exception as e:
                print(f"✗ Remote autofocus error: {e}")
                return False
        
        # Otherwise use local gphoto2
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
    
    def capture_image(self, retry=True):
        """Capture image to camera SD card with autofocus (local or remote)"""
        # Use remote camera server if configured
        if self.use_remote_camera and self.camera_server_url:
            try:
                print("📷 Starting remote capture sequence...")
                
                # Step 1: Try autofocus
                print("   [1/2] Attempting autofocus...")
                try:
                    af_response = requests.post(
                        f'{self.camera_server_url}/api/autofocus',
                        timeout=15
                    )
                    if af_response.status_code == 200:
                        print("   ✓ Autofocus successful")
                        time.sleep(2.0)
                    else:
                        print("   ⚠ Autofocus not available (continuing)")
                        time.sleep(0.5)
                except:
                    print("   ⚠ Autofocus not available (continuing)")
                    time.sleep(0.5)
                
                # Step 2: Capture
                print("   [2/2] Capturing image...")
                capture_response = requests.post(
                    f'{self.camera_server_url}/api/capture',
                    json={'download': False},
                    timeout=35
                )
                
                if capture_response.status_code == 200:
                    # Success!
                    self.frame_count += 1
                    self.frames_in_strip += 1
                    self.frame_positions.append(self.position)
                    self.save_state()
                    print(f"✓ Successfully captured frame #{self.frame_count}")
                    print(f"   (Strip {self.strip_count}, Frame {self.frames_in_strip} in strip)")
                    return True
                else:
                    error_data = capture_response.json()
                    print(f"✗ Remote capture failed: {error_data.get('error')}")
                    return False
            
            except Exception as e:
                print(f"✗ Remote capture error: {e}")
                return False
        
        # Otherwise use local gphoto2
        try:
            print("📷 Starting capture sequence...")
            self._kill_gphoto2()
            
            # Step 1: Try autofocus (non-blocking if fails)
            print("   [1/2] Attempting autofocus...")
            af_result = subprocess.run(
                ["gphoto2", "--set-config", "autofocus=1"],
                capture_output=True, timeout=10, text=True
            )
            
            if af_result.returncode == 0:
                print("   ✓ Autofocus successful")
                time.sleep(2.0)  # Give camera time to focus
            else:
                print("   ⚠ Autofocus not available (continuing with current focus)")
                time.sleep(0.5)
            
            # Step 2: Capture image
            print("   [2/2] Capturing image...")
            result = subprocess.run(
                ["gphoto2", "--capture-image"],
                capture_output=True, timeout=30, text=True
            )
            
            # Check result
            if result.returncode == 0:
                # Success!
                self.frame_count += 1
                self.frames_in_strip += 1
                self.frame_positions.append(self.position)
                self.save_state()
                print(f"✓ Successfully captured frame #{self.frame_count}")
                print(f"   (Strip {self.strip_count}, Frame {self.frames_in_strip} in strip)")
                return True
                
            else:
                # Capture failed - analyze error
                print(f"✗ Capture failed (return code: {result.returncode})")
                
                if result.stderr:
                    error_msg = result.stderr.strip()
                    print(f"   Error: {error_msg}")
                    
                    # Provide specific guidance
                    if "PTP" in error_msg:
                        print("   → Fix: Set camera USB mode to PTP (not Mass Storage)")
                        print("   → Check camera menu: Settings → USB → PTP")
                    elif "claim" in error_msg.lower() or "busy" in error_msg.lower():
                        print("   → Fix: Camera is locked by another process")
                        print("   → Run: sudo killall gphoto2 gvfs-gphoto2-volume-monitor")
                    elif "not found" in error_msg.lower() or "detect" in error_msg.lower():
                        print("   → Fix: Camera not detected - check connection")
                        print("   → Check USB cable and camera is powered on")
                    elif "timeout" in error_msg.lower():
                        print("   → Camera took too long to respond")
                        print("   → Check camera is not in sleep mode")
                    elif "card" in error_msg.lower() or "full" in error_msg.lower():
                        print("   → Check camera has SD card with free space")
                    
                    # Retry once on transient errors
                    if retry and ("busy" in error_msg.lower() or "claim" in error_msg.lower()):
                        print("   ↻ Retrying after cleaning up processes...")
                        time.sleep(1)
                        return self.capture_image(retry=False)
                
                return False
            
        except subprocess.TimeoutExpired:
            print("✗ Capture timeout - camera not responding (30s)")
            print("   → Camera may be in sleep mode or disconnected")
            print("   → Check camera screen is on")
            self._kill_gphoto2()
            return False
            
        except Exception as e:
            print(f"✗ Unexpected capture error: {e}")
            self._kill_gphoto2()
            return False
    
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
            success = self.send(f'H-{self.frame_advance}')
            if success:
                self.status_msg = f"Backed up {self.frame_advance} steps"
                return True
            else:
                self.status_msg = "❌ Backup failed - Check Arduino"
                return False
        return False
    
    def get_status(self):
        """Get current status as dictionary"""
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
            'status_msg': self.status_msg,
            'arduino_connected': self.arduino is not None,
            'use_remote_camera': self.use_remote_camera,
            'remote_camera_available': self.remote_camera_available,
            'camera_server_url': self.camera_server_url
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
    """Move motor"""
    data = request.json
    direction = data.get('direction', 'forward')
    size = data.get('size', 'fine')
    
    if direction == 'forward':
        cmd = 'F' if size == 'coarse' else 'f'
    else:
        cmd = 'B' if size == 'coarse' else 'b'
    
    success = scanner.send(cmd)
    
    if success:
        scanner.status_msg = f"{'→' if direction == 'forward' else '←'} {scanner.coarse_step if size == 'coarse' else scanner.fine_step} steps"
    else:
        scanner.status_msg = "❌ Motor move failed - Check Arduino connection"
    
    scanner.broadcast_status()
    
    return jsonify({'success': success})

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

@app.route('/api/autofocus', methods=['POST'])
def autofocus():
    """Trigger autofocus"""
    scanner.status_msg = "Focusing..."
    scanner.broadcast_status()
    
    success = scanner.autofocus()
    scanner.status_msg = "✓ Focused" if success else "⚠ Focus failed (check console)"
    scanner.broadcast_status()
    
    return jsonify({'success': success})

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
    if not scanner.roll_name:
        return jsonify({'success': False, 'message': 'Create roll first'})
    
    if not scanner.check_camera():
        return jsonify({'success': False, 'message': 'Camera not connected'})
    
    # Auto-advance before capture (for frames 2+)
    if scanner.mode == 'calibrated' and scanner.auto_advance and scanner.frames_in_strip > 0:
        if scanner.frame_advance:
            if not scanner.send(f'H{scanner.frame_advance}'):
                return jsonify({'success': False, 'message': 'Auto-advance failed - Check Arduino'})
            time.sleep(0.5)
    
    scanner.status_msg = "Capturing..."
    scanner.broadcast_status()
    
    success = scanner.capture_image()
    
    if success:
        scanner.status_msg = f"✓ Frame {scanner.frame_count} (Strip {scanner.strip_count})"
    else:
        scanner.status_msg = "❌ Capture failed!"
    
    scanner.broadcast_status()
    return jsonify({'success': success})

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

@app.route('/api/setup_remote_camera', methods=['POST'])
def setup_remote_camera():
    """Setup connection to remote camera server"""
    data = request.json
    server_url = data.get('server_url')
    
    if not server_url:
        return jsonify({'success': False, 'error': 'No server URL provided'})
    
    success = scanner.setup_remote_camera(server_url)
    
    return jsonify({
        'success': success,
        'camera_connected': scanner.camera_connected,
        'camera_model': scanner.camera_model,
        'server_url': scanner.camera_server_url
    })

@app.route('/api/disconnect_remote_camera', methods=['POST'])
def disconnect_remote_camera():
    """Disconnect from remote camera server"""
    scanner.use_remote_camera = False
    scanner.camera_server_url = None
    scanner.remote_camera_available = False
    scanner.camera_connected = False
    scanner.status_msg = "Remote camera disconnected"
    scanner.broadcast_status()
    
    return jsonify({'success': True})

@app.route('/api/live_view')
def live_view():
    """Proxy live view from remote camera server"""
    if not scanner.use_remote_camera or not scanner.camera_server_url:
        return jsonify({'error': 'Remote camera not configured'}), 503
    
    try:
        # Proxy the live view from camera server
        response = requests.get(
            f'{scanner.camera_server_url}/api/live-view',
            timeout=10,
            stream=True
        )
        
        if response.status_code == 200:
            return response.content, 200, {
                'Content-Type': 'image/jpeg',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        else:
            return jsonify({'error': 'Failed to get live view'}), response.status_code
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
    
    # Auto-connect to Arduino on startup
    print("\n🔌 Searching for Arduino...")
    if scanner.find_arduino():
        print("✓ Arduino connected")
    else:
        print("✗ Arduino not found (you can connect later via the web interface)")
    
    # Check for camera
    print("\n📷 Camera Setup")
    print("  • USB Camera: gphoto2 will be used for autofocus and capture")
    print("  • Live view: Not available (Canon WiFi support removed)")
    
    # Start web server
    host = '0.0.0.0'
    port = config.get('port', 5000)
    pi_ip = config.get('pi_ip', 'localhost')
    
    print("\n" + "="*60)
    print("   WEB SERVER STARTING")
    print("="*60)
    print(f"\n🌐 Access the scanner at:")
    print(f"   • Local:  http://localhost:{port}")
    print(f"   • Network: http://{pi_ip}:{port}")
    print(f"\n📱 From your phone/tablet:")
    print(f"   • http://{pi_ip}:{port}")
    print("\n💡 Tip: To reset configuration, run:")
    print("   python3 web_app.py --reset")
    print("="*60 + "\n")
    
    # Run without debug mode to prevent reloads that disrupt Arduino connection
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)

