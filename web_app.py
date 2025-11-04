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
from datetime import datetime
import json
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = 'film-scanner-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

class FilmScanner:
    def __init__(self):
        self.arduino = None
        self.roll_name = ""
        self.roll_folder = ""
        self.frame_count = 0
        self.strip_count = 0
        self.frames_in_strip = 0
        self.status_msg = "Ready"
        self.camera_connected = False
        self.camera_model = "Unknown"
        self.last_camera_check = 0
        
        # Motor configuration
        self.fine_step = 8
        self.coarse_step = 64
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
        self.is_large_step = False
        
        # State persistence
        self.state_file = None
        
        # Lock for thread safety
        self.lock = threading.Lock()
    
    def find_arduino(self):
        """Find Arduino on available ports"""
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
                time.sleep(2)
                
                ser.write(b'?\n')
                time.sleep(0.2)
                response = ser.read(100).decode('ascii', errors='ignore')
                
                if 'Film' in response or 'READY' in response:
                    self.arduino = ser
                    self.broadcast_status()
                    return True
                
                ser.close()
            except:
                continue
        
        return False
    
    def send(self, cmd):
        """Send command to Arduino"""
        if self.arduino:
            self.arduino.write(f"{cmd}\n".encode())
            time.sleep(0.1)
            
            # Update position for movement commands
            if cmd in ['f', 'F', 'b', 'B'] or cmd.startswith('H'):
                time.sleep(0.2)
                self.arduino.write(b'?\n')
                time.sleep(0.1)
                response = self.arduino.read(100).decode('ascii', errors='ignore')
                
                for line in response.split('\n'):
                    if 'Position' in line:
                        try:
                            self.position = int(line.split(':')[1].strip())
                        except:
                            pass
    
    def check_camera(self):
        """Check camera connection"""
        current_time = time.time()
        if current_time - self.last_camera_check < 5:
            return self.camera_connected
        
        self.last_camera_check = current_time
        
        try:
            subprocess.run(["killall", "gphoto2"], capture_output=True, timeout=1)
            time.sleep(0.3)
            
            result = subprocess.run(
                ["gphoto2", "--auto-detect"],
                capture_output=True, timeout=5, text=True
            )
            
            if result.returncode == 0 and "usb" in result.stdout.lower():
                lines = result.stdout.strip().split('\n')
                for line in lines[2:]:
                    if 'usb' in line.lower():
                        self.camera_model = line.split('usb')[0].strip()
                        self.camera_connected = True
                        return True
            
            self.camera_connected = False
            self.camera_model = "Not detected"
            return False
        except:
            self.camera_connected = False
            self.camera_model = "Check failed"
            return False
    
    def autofocus(self):
        """Trigger camera autofocus"""
        try:
            subprocess.run(["killall", "gphoto2"], capture_output=True, timeout=1)
            time.sleep(0.3)
            subprocess.run(
                ["gphoto2", "--set-config", "autofocus=1"],
                capture_output=True, timeout=5
            )
            time.sleep(1.5)
            return True
        except:
            return False
    
    def capture_image(self):
        """Capture image to camera SD card"""
        try:
            subprocess.run(["killall", "gphoto2"], capture_output=True, timeout=1)
            time.sleep(0.3)
            
            # Autofocus
            subprocess.run(
                ["gphoto2", "--set-config", "autofocus=1"],
                capture_output=True, timeout=5
            )
            time.sleep(1.5)
            
            # Capture to camera SD card only
            result = subprocess.run(
                ["gphoto2", "--capture-image"],
                capture_output=True, timeout=20
            )
            
            if result.returncode == 0:
                self.frame_count += 1
                self.frames_in_strip += 1
                self.frame_positions.append(self.position)
                self.save_state()
                return True
            
            return False
        except:
            subprocess.run(["killall", "-9", "gphoto2"], capture_output=True)
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
            self.send(f'H{self.frame_advance}')
            self.status_msg = f"Advanced {self.frame_advance} steps"
            return True
        return False
    
    def backup_frame(self):
        """Backup one full frame using calibrated distance"""
        if self.frame_advance:
            self.send(f'H-{self.frame_advance}')
            self.status_msg = f"Backed up {self.frame_advance} steps"
            return True
        return False
    
    def get_status(self):
        """Get current status as dictionary"""
        return {
            'roll_name': self.roll_name,
            'frame_count': self.frame_count,
            'strip_count': self.strip_count,
            'frames_in_strip': self.frames_in_strip,
            'position': self.position,
            'mode': self.mode,
            'frame_advance': self.frame_advance,
            'auto_advance': self.auto_advance,
            'is_large_step': self.is_large_step,
            'camera_connected': self.camera_connected,
            'camera_model': self.camera_model,
            'status_msg': self.status_msg,
            'arduino_connected': self.arduino is not None
        }
    
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
    
    scanner.send(cmd)
    scanner.status_msg = f"{'→' if direction == 'forward' else '←'} {scanner.coarse_step if size == 'coarse' else scanner.fine_step} steps"
    scanner.broadcast_status()
    
    return jsonify({'success': True})

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

@app.route('/api/toggle_step_size', methods=['POST'])
def toggle_step_size():
    """Toggle step size"""
    scanner.is_large_step = not scanner.is_large_step
    scanner.status_msg = f"Step size: {'LARGE' if scanner.is_large_step else 'small'}"
    scanner.broadcast_status()
    return jsonify({'success': True})

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
    scanner.send('Z')
    scanner.frame_positions = []
    scanner.status_msg = "Position zeroed"
    scanner.broadcast_status()
    return jsonify({'success': True})

@app.route('/api/autofocus', methods=['POST'])
def autofocus():
    """Trigger autofocus"""
    scanner.status_msg = "Focusing..."
    scanner.broadcast_status()
    
    success = scanner.autofocus()
    scanner.status_msg = "Focused" if success else "Focus failed"
    scanner.broadcast_status()
    
    return jsonify({'success': success})

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
            scanner.send(f'H{scanner.frame_advance}')
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
    # Auto-connect to Arduino on startup
    print("Starting Film Scanner Web App...")
    print("Searching for Arduino...")
    if scanner.find_arduino():
        print("✓ Arduino connected")
    else:
        print("✗ Arduino not found (you can connect later via the web interface)")
    
    print("\nStarting web server...")
    print("Access the scanner at: http://localhost:5000")
    print("Or from your phone: http://<your-computer-ip>:5000")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)

