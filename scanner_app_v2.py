#!/usr/bin/env python3
"""
35mm Film Scanner Control - Professional Version 2
Improvements:
- Auto-advance AFTER capture (not before)
- Fine adjustments allowed between frames
- Space bar only for calibration
- RAW files stay on camera SD card (CR3/NEF/ARW/etc)
- Universal camera detection (Canon, Nikon, Sony, etc)
- Autofocus button (F)
- Shift+arrows for frame advance
- Better camera handling and error messages
"""

import curses
import serial
import serial.tools.list_ports
import subprocess
import time
import os
from datetime import datetime
import json

class FilmScanner:
    def __init__(self):
        self.arduino = None
        self.roll_name = ""
        self.roll_folder = ""
        self.frame_count = 0
        self.strip_count = 0  # Track which strip we're on
        self.frames_in_strip = 0  # Frames captured in current strip
        self.status_msg = "Ready"
        self.camera_connected = False
        self.camera_model = "Unknown"
        self.last_camera_check = 0
        
        # Motor configuration (adjust for your hardware)
        self.fine_step = 8       # Fine jog steps
        self.coarse_step = 64    # Coarse jog steps
        self.step_delay = 800    # Microseconds between steps
        
        # Calibration
        self.frame_advance = None  # Steps between frames (will be calibrated)
        self.default_advance = 1200  # Default estimate for 35mm
        
        # Position tracking
        self.position = 0
        self.frame_positions = []  # Store position of each captured frame
        
        # Mode
        self.mode = 'manual'  # 'manual' or 'calibrated'
        self.auto_advance = True  # Auto-advance after capture in calibrated mode
        self.is_large_step = False
        
        # State persistence
        self.state_file = None
        
    def find_arduino(self, stdscr=None):
        """Find Arduino on available ports"""
        ports = list(serial.tools.list_ports.comports())
        
        # Add Raspberry Pi specific ports
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
                time.sleep(2.5)  # Arduino reset time
                
                ser.reset_input_buffer()
                ser.write(b'?\n')
                time.sleep(0.8)
                
                if ser.in_waiting:
                    response = ser.read_all().decode('utf-8', errors='ignore')
                    if any(word in response for word in ['READY', 'STATUS', 'NEMA', 'Position']):
                        return ser
                
                ser.close()
            except:
                continue
        
        return None
    
    def check_camera(self):
        """Check if any camera is connected via USB (rate-limited to avoid spamming)"""
        current_time = time.time()
        if current_time - self.last_camera_check < 5:  # Check every 5 seconds max
            return self.camera_connected
        
        self.last_camera_check = current_time
        
        try:
            result = subprocess.run(
                ["gphoto2", "--auto-detect"],
                capture_output=True,
                timeout=2
            )
            
            output = result.stdout.decode('utf-8', errors='ignore')
            lines = output.strip().split('\n')
            
            # Camera is detected if:
            # 1. Command succeeded
            # 2. Output has more than just the header (more than 2 lines)
            # 3. A USB port is referenced (universal detection)
            self.camera_connected = (
                result.returncode == 0 and 
                len(lines) > 2 and 
                'usb:' in output.lower()
            )
            
            # Extract camera model name for display
            if self.camera_connected and len(lines) > 2:
                # Camera model is typically in the first data line after header
                model_line = lines[2].split()
                if model_line:
                    # Get everything before "usb:" as the model name
                    model_parts = lines[2].split('usb:')[0].strip()
                    self.camera_model = model_parts if model_parts else "Camera"
            else:
                self.camera_model = "Unknown"
            
        except:
            self.camera_connected = False
            self.camera_model = "Unknown"
        
        return self.camera_connected
    
    def send(self, cmd):
        """Send command to Arduino and track position"""
        if not self.arduino or not self.arduino.is_open:
            return False
        
        try:
            self.arduino.write(f"{cmd}\n".encode())
            time.sleep(0.05)
            
            # Track position changes
            if cmd == 'f':
                self.position += self.fine_step
            elif cmd == 'b':
                self.position -= self.fine_step
            elif cmd == 'F':
                self.position += self.coarse_step
            elif cmd == 'B':
                self.position -= self.coarse_step
            elif cmd.startswith('H'):
                steps = int(cmd[1:])
                self.position += steps
            elif cmd.startswith('h'):
                steps = int(cmd[1:])
                self.position -= steps
            elif cmd == 'Z':
                self.position = 0
                self.frame_positions = []
            
            return True
        except Exception as e:
            self.status_msg = f"Command error: {str(e)[:40]}"
            return False
    
    def setup_camera_raw(self):
        """Configure camera to shoot in RAW format"""
        if not self.camera_connected:
            return False
        
        try:
            subprocess.run(["killall", "gphoto2"], capture_output=True, timeout=1)
            time.sleep(0.2)
            
            # Try to set image format to RAW
            # Different cameras use different config names, so try multiple options
            raw_configs = [
                ("imageformat", "RAW"),
                ("imagequality", "RAW"),
                ("capturetarget", "Memory card"),  # Ensure saving to SD card
            ]
            
            for config_name, config_value in raw_configs:
                try:
                    subprocess.run(
                        ["gphoto2", "--set-config", f"{config_name}={config_value}"],
                        capture_output=True,
                        timeout=3
                    )
                except:
                    pass  # Config might not exist on all cameras
            
            return True
        except:
            return False
    
    def autofocus(self):
        """Trigger camera autofocus by doing a capture-preview"""
        if not self.check_camera():
            self.status_msg = "Camera not connected"
            return False
        
        try:
            subprocess.run(["killall", "gphoto2"], capture_output=True, timeout=1)
            time.sleep(0.2)
            
            # Try multiple autofocus methods - different cameras support different ones
            # Method 1: Set autofocus config
            subprocess.run(
                ["gphoto2", "--set-config", "autofocus=1"],
                capture_output=True,
                timeout=3
            )
            
            # Method 2: Capture preview (triggers AF on many cameras)
            result = subprocess.run(
                ["gphoto2", "--capture-preview"],
                capture_output=True,
                timeout=5
            )
            
            # Clean up preview file if created
            subprocess.run(["rm", "-f", "capture_preview.jpg"], capture_output=True)
            
            self.status_msg = "✓ Autofocus complete"
            return True
        except subprocess.TimeoutExpired:
            subprocess.run(["killall", "-9", "gphoto2"], capture_output=True)
            self.status_msg = "Autofocus timeout"
            return False
        except:
            self.status_msg = "Autofocus failed - check camera"
            return False
    
    def capture_image(self):
        """Capture image in RAW format to camera SD card (not downloaded)"""
        if not self.check_camera():
            self.status_msg = "Camera not connected!"
            return False
        
        subprocess.run(["killall", "gphoto2"], capture_output=True, timeout=1)
        time.sleep(0.3)
        
        # Capture to SD card in RAW format (no download)
        try:
            result = subprocess.run(
                ["gphoto2", "--capture-image"],  # Captures in camera's current format
                capture_output=True,
                timeout=15
            )
            
            # Check if capture was successful
            output = result.stdout.decode('utf-8', errors='ignore')
            error_output = result.stderr.decode('utf-8', errors='ignore')
            
            if "New file" in output or result.returncode == 0:
                self.frame_count += 1
                self.frames_in_strip += 1
                self.frame_positions.append(self.position)
                self.save_state()
                
                # Try to detect file format from output
                if any(fmt in output.upper() for fmt in ['CR3', 'CR2', 'NEF', 'ARW', 'RAF', 'DNG', 'RAW']):
                    return True
                elif "New file" in output:
                    # File created but format unknown - still count as success
                    return True
                else:
                    return True  # Successful capture based on return code
            else:
                # Provide more detailed error info
                if "PTP" in error_output:
                    self.status_msg = "Camera busy or locked"
                elif "not found" in error_output.lower():
                    self.status_msg = "Camera disconnected"
                return False
                
        except subprocess.TimeoutExpired:
            subprocess.run(["killall", "-9", "gphoto2"], capture_output=True)
            self.status_msg = "Capture timeout - camera not responding"
            return False
        except Exception as e:
            self.status_msg = f"Capture error: {str(e)[:30]}"
            return False
    
    def advance_frame(self):
        """Advance to next frame using calibrated distance or default"""
        if self.frame_advance is None:
            # Use default if not calibrated
            advance = self.default_advance
            self.status_msg = f"Advancing {advance} steps (default)"
        else:
            advance = self.frame_advance
            self.status_msg = f"Advancing {advance} steps"
        
        return self.send(f'H{advance}')
    
    def backup_frame(self):
        """Backup one frame using calibrated distance or default"""
        if self.frame_advance is None:
            backup = self.default_advance
        else:
            backup = self.frame_advance
        
        self.status_msg = f"Backing up {backup} steps"
        return self.send(f'h{backup}')
    
    def new_strip(self, stdscr):
        """Start a new strip - hand-feed frame 1, then use existing calibration"""
        if not self.roll_name:
            self.status_msg = "Create roll first (press N)"
            return False
        
        if self.frame_advance is None:
            self.status_msg = "Calibrate first (press C)"
            return False
        
        stdscr.clear()
        stdscr.addstr(0, 0, "=== NEW STRIP ===", curses.A_BOLD)
        stdscr.addstr(2, 0, f"Current: Strip {self.strip_count}, Frame {self.frames_in_strip} in strip, {self.frame_count} total")
        stdscr.addstr(4, 0, "Hand-feed the new strip and position frame 1")
        stdscr.addstr(5, 0, "Use arrow keys to align frame 1 perfectly")
        stdscr.addstr(7, 0, "Press SPACE when frame 1 is aligned")
        stdscr.addstr(8, 0, "Press Q to cancel")
        stdscr.addstr(10, 0, f"Position: {self.position}")
        stdscr.addstr(11, 0, f"Calibrated spacing: {self.frame_advance} steps")
        stdscr.refresh()
        
        # Manual positioning loop for frame 1 of new strip
        while True:
            key = stdscr.getch()
            
            if key == ord(' '):  # SPACE - frame aligned, capture it
                stdscr.addstr(13, 0, "Capturing frame 1 of new strip...")
                stdscr.refresh()
                
                if self.capture_image():
                    self.strip_count += 1
                    self.frames_in_strip = 1  # Reset to 1 (just captured frame 1)
                    self.save_state()
                    
                    stdscr.clear()
                    stdscr.addstr(0, 0, "✓ NEW STRIP STARTED", curses.A_BOLD)
                    stdscr.addstr(2, 0, f"Strip {self.strip_count}, Frame 1 captured")
                    stdscr.addstr(3, 0, f"Total frames: {self.frame_count}")
                    stdscr.addstr(5, 0, f"Will use {self.frame_advance} steps between frames")
                    stdscr.addstr(6, 0, "Press SPACE to capture remaining frames")
                    stdscr.addstr(8, 0, "Press any key to continue...")
                    stdscr.refresh()
                    stdscr.getch()
                    
                    self.status_msg = f"Strip {self.strip_count} - Press SPACE for frame 2"
                    return True
                else:
                    stdscr.addstr(14, 0, "Failed to capture frame 1!", curses.A_REVERSE)
                    stdscr.addstr(15, 0, "Press any key...")
                    stdscr.refresh()
                    stdscr.getch()
                    return False
            
            elif key == curses.KEY_LEFT:
                cmd = 'B' if self.is_large_step else 'b'
                self.send(cmd)
                stdscr.addstr(10, 0, f"Position: {self.position}     ")
                stdscr.refresh()
                
            elif key == curses.KEY_RIGHT:
                cmd = 'F' if self.is_large_step else 'f'
                self.send(cmd)
                stdscr.addstr(10, 0, f"Position: {self.position}     ")
                stdscr.refresh()
                
            elif key in [ord('g'), ord('G')]:
                self.is_large_step = not self.is_large_step
                step_size = "LARGE" if self.is_large_step else "small"
                stdscr.addstr(12, 0, f"Step size: {step_size}     ")
                stdscr.refresh()
                
            elif key in [ord('f'), ord('F')]:
                stdscr.addstr(13, 0, "Focusing...           ")
                stdscr.refresh()
                self.autofocus()
                stdscr.addstr(13, 0, "                      ")
                stdscr.refresh()
                
            elif key in [ord('q'), ord('Q')]:
                return False
    
    def calibrate(self, stdscr):
        """
        Calibrate frame advance distance (Frame 1 → Frame 2).
        This is the first strip, so it captures frames 1 and 2 to learn spacing.
        """
        stdscr.clear()
        stdscr.addstr(0, 0, "=== CALIBRATION (STRIP 1) ===", curses.A_BOLD)
        stdscr.addstr(2, 0, "Hand-feed strip 1 and position frame 1")
        stdscr.addstr(3, 0, "Use arrow keys to align perfectly")
        stdscr.addstr(5, 0, "Press SPACE when frame 1 is aligned, or Q to cancel")
        stdscr.addstr(7, 0, "Controls:")
        stdscr.addstr(8, 0, "  ← →     Fine movement")
        stdscr.addstr(9, 0, "  G       Toggle step size")
        stdscr.addstr(10, 0, "  F       Autofocus")
        stdscr.addstr(12, 0, f"Position: {self.position}")
        stdscr.refresh()
        
        # Position and capture frame 1
        while True:
            key = stdscr.getch()
            
            if key == ord(' '):  # SPACE - frame 1 aligned
                break
            elif key == curses.KEY_LEFT:
                cmd = 'B' if self.is_large_step else 'b'
                self.send(cmd)
                stdscr.addstr(12, 0, f"Position: {self.position}     ")
                stdscr.refresh()
            elif key == curses.KEY_RIGHT:
                cmd = 'F' if self.is_large_step else 'f'
                self.send(cmd)
                stdscr.addstr(12, 0, f"Position: {self.position}     ")
                stdscr.refresh()
            elif key in [ord('g'), ord('G')]:
                self.is_large_step = not self.is_large_step
                step_size = "LARGE" if self.is_large_step else "small"
                stdscr.addstr(13, 0, f"Step size: {step_size}     ")
                stdscr.refresh()
            elif key in [ord('f'), ord('F')]:
                stdscr.addstr(14, 0, "Focusing...           ")
                stdscr.refresh()
                self.autofocus()
                stdscr.addstr(14, 0, "                      ")
                stdscr.refresh()
            elif key in [ord('q'), ord('Q')]:
                return False
        
        # Record frame 1 position BEFORE capture
        frame1_pos = self.position
        
        # Capture frame 1
        stdscr.addstr(14, 0, "Capturing frame 1...  ")
        stdscr.refresh()
        
        if not self.capture_image():
            stdscr.addstr(15, 0, "Failed to capture frame 1!", curses.A_REVERSE)
            stdscr.addstr(17, 0, "Press any key...")
            stdscr.refresh()
            stdscr.getch()
            return False
        
        # Now position frame 2
        stdscr.clear()
        stdscr.addstr(0, 0, "=== CALIBRATION (STRIP 1) ===", curses.A_BOLD)
        stdscr.addstr(2, 0, f"✓ Frame 1 captured at position {frame1_pos}")
        stdscr.addstr(4, 0, "Now position frame 2 using arrow keys")
        stdscr.addstr(5, 0, "Press SPACE when frame 2 is perfectly centered")
        stdscr.addstr(7, 0, "Controls:")
        stdscr.addstr(8, 0, "  ← →     Fine movement")
        stdscr.addstr(9, 0, "  G       Toggle step size")
        stdscr.addstr(10, 0, "  F       Autofocus")
        stdscr.addstr(12, 0, f"Frame 1 pos: {frame1_pos}")
        stdscr.addstr(13, 0, f"Current pos: {self.position}")
        stdscr.addstr(14, 0, f"Distance: {self.position - frame1_pos} steps")
        stdscr.refresh()
        
        # Manual positioning loop for frame 2
        while True:
            key = stdscr.getch()
            
            if key == ord(' '):  # SPACE - frame 2 aligned
                frame2_pos = self.position
                self.frame_advance = frame2_pos - frame1_pos
                
                if self.frame_advance <= 0:
                    stdscr.addstr(16, 0, "ERROR: Frame 2 must be ahead of frame 1!", curses.A_REVERSE)
                    stdscr.refresh()
                    time.sleep(2)
                    return False
                
                # Capture frame 2
                stdscr.addstr(16, 0, "Capturing frame 2...                          ")
                stdscr.refresh()
                
                if not self.capture_image():
                    stdscr.addstr(17, 0, "Failed to capture frame 2!", curses.A_REVERSE)
                    stdscr.refresh()
                    time.sleep(2)
                    return False
                
                # Calibration complete - this was strip 1 with 2 frames
                self.strip_count = 1
                self.frames_in_strip = 2
                self.mode = 'calibrated'
                self.save_state()
                
                stdscr.clear()
                stdscr.addstr(0, 0, "✓ CALIBRATION COMPLETE", curses.A_BOLD)
                stdscr.addstr(2, 0, f"Frame spacing: {self.frame_advance} steps")
                stdscr.addstr(3, 0, f"Strip 1: 2 frames captured")
                stdscr.addstr(5, 0, "This spacing will be used for all remaining frames")
                stdscr.addstr(7, 0, "Next steps:")
                stdscr.addstr(8, 0, "  SPACE - Capture remaining frames in this strip")
                stdscr.addstr(9, 0, "  S     - Start new strip (after finishing this one)")
                stdscr.addstr(11, 0, "Press any key to continue...")
                stdscr.refresh()
                stdscr.getch()
                
                self.status_msg = f"Strip 1, Frame 2 - Press SPACE for frame 3"
                return True
                
            elif key == curses.KEY_LEFT:
                cmd = 'B' if self.is_large_step else 'b'
                self.send(cmd)
                stdscr.addstr(13, 0, f"Current pos: {self.position}     ")
                stdscr.addstr(14, 0, f"Distance: {self.position - frame1_pos} steps     ")
                stdscr.refresh()
                
            elif key == curses.KEY_RIGHT:
                cmd = 'F' if self.is_large_step else 'f'
                self.send(cmd)
                stdscr.addstr(13, 0, f"Current pos: {self.position}     ")
                stdscr.addstr(14, 0, f"Distance: {self.position - frame1_pos} steps     ")
                stdscr.refresh()
                
            elif key in [ord('g'), ord('G')]:
                self.is_large_step = not self.is_large_step
                step_size = "LARGE" if self.is_large_step else "small"
                stdscr.addstr(15, 0, f"Step size: {step_size}     ")
                stdscr.refresh()
                
            elif key in [ord('f'), ord('F')]:
                stdscr.addstr(16, 0, "Focusing...                                   ")
                stdscr.refresh()
                self.autofocus()
                stdscr.addstr(16, 0, "                                              ")
                stdscr.refresh()
                
            elif key in [ord('q'), ord('Q')]:
                return False
    
    def capture_frame(self, stdscr):
        """Capture current frame and optionally auto-advance"""
        self.status_msg = "Capturing..."
        self.draw(stdscr)
        
        if self.capture_image():
            # Show strip and frame info
            self.status_msg = f"✓ Strip {self.strip_count}, Frame {self.frames_in_strip} (Total: {self.frame_count})"
            
            # Auto-advance AFTER capture if in calibrated mode
            if self.mode == 'calibrated' and self.auto_advance:
                time.sleep(0.5)  # Brief pause before advancing
                if self.advance_frame():
                    self.status_msg = f"✓ Frame captured, advanced to next"
                else:
                    self.status_msg = f"✓ Frame captured, advance failed"
            
            return True
        else:
            if not self.camera_connected:
                self.status_msg = "✗ Camera not connected!"
            else:
                self.status_msg = "✗ Capture failed"
            return False
    
    def save_state(self):
        """Save current state"""
        if self.state_file:
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
                'last_updated': datetime.now().isoformat()
            }
            try:
                with open(self.state_file, 'w') as f:
                    json.dump(state, f, indent=2)
            except:
                pass
    
    def load_state(self):
        """Load saved state"""
        if self.state_file and os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
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
            except:
                return False
        return False
    
    def new_roll(self, stdscr):
        """Create new roll"""
        stdscr.clear()
        stdscr.addstr(0, 0, "=== NEW ROLL ===", curses.A_BOLD)
        stdscr.addstr(2, 0, "Enter roll name: ")
        stdscr.refresh()
        
        curses.echo()
        curses.curs_set(1)
        
        try:
            roll_input = stdscr.getstr(2, 17, 40).decode('utf-8').strip()
        except:
            roll_input = ""
        finally:
            curses.noecho()
            curses.curs_set(0)
        
        if not roll_input:
            self.status_msg = "Cancelled"
            return False
        
        self.roll_name = roll_input
        
        # Create folder for metadata only
        date_folder = datetime.now().strftime("%Y-%m-%d")
        self.roll_folder = os.path.join(
            os.path.expanduser("~/scans"),
            date_folder,
            self.roll_name
        )
        os.makedirs(self.roll_folder, exist_ok=True)
        self.state_file = os.path.join(self.roll_folder, '.scan_state.json')
        
        # Check for existing state
        if self.load_state():
            stdscr.clear()
            stdscr.addstr(0, 0, "Found existing roll!", curses.A_BOLD)
            stdscr.addstr(2, 0, f"Frames captured: {self.frame_count}")
            stdscr.addstr(3, 0, f"Position: {self.position} steps")
            if self.frame_advance:
                stdscr.addstr(4, 0, f"Frame advance: {self.frame_advance} steps")
            stdscr.addstr(6, 0, "Resume (R) or Start Over (S)?")
            stdscr.refresh()
            
            while True:
                key = stdscr.getch()
                if key in [ord('r'), ord('R')]:
                    self.status_msg = f"Resumed at frame {self.frame_count}"
                    return True
                elif key in [ord('s'), ord('S')]:
                    break
                elif key in [ord('q'), ord('Q')]:
                    return False
        
        # New roll
        self.frame_count = 0
        self.position = 0
        self.frame_positions = []
        self.frame_advance = None
        
        stdscr.clear()
        stdscr.addstr(0, 0, f"Roll: {self.roll_name}", curses.A_BOLD)
        stdscr.addstr(2, 0, "WORKFLOW (Strip-Based Scanning):")
        stdscr.addstr(4, 0, "First Strip (Calibration):")
        stdscr.addstr(5, 0, "  1. Hand-feed strip 1, position frame 1 with arrows")
        stdscr.addstr(6, 0, "  2. Press C to calibrate (captures frames 1 & 2)")
        stdscr.addstr(7, 0, "  3. Press SPACE to capture remaining frames (3-6)")
        stdscr.addstr(9, 0, "Additional Strips:")
        stdscr.addstr(10, 0, "  1. Press S for new strip")
        stdscr.addstr(11, 0, "  2. Hand-feed next strip, align frame 1")
        stdscr.addstr(12, 0, "  3. Press SPACE to capture all frames (uses saved spacing)")
        stdscr.addstr(14, 0, "Each strip: 5-6 frames | Total: ~36-40 frames per roll")
        stdscr.addstr(15, 0, "Files saved to camera SD card in RAW format")
        stdscr.addstr(17, 0, "Press any key to continue...")
        stdscr.refresh()
        stdscr.getch()
        
        self.status_msg = "Hand-feed strip 1, position frame 1, then press C to calibrate"
        self.save_state()
        return True
    
    def draw(self, stdscr):
        """Draw main interface"""
        stdscr.clear()
        
        stdscr.addstr(0, 0, "=== 35MM FILM SCANNER ===", curses.A_BOLD)
        
        # Status
        stdscr.addstr(2, 0, f"Roll: {self.roll_name if self.roll_name else 'None'}")
        stdscr.addstr(3, 0, f"Total frames: {self.frame_count}")
        if self.strip_count > 0:
            stdscr.addstr(4, 0, f"Strip {self.strip_count}, Frame {self.frames_in_strip} in strip")
        stdscr.addstr(5, 0, f"Position: {self.position} steps")
        
        # Mode and calibration
        mode_str = "MANUAL" if self.mode == 'manual' else "CALIBRATED"
        stdscr.addstr(6, 0, f"Mode: {mode_str}")
        
        if self.frame_advance:
            stdscr.addstr(7, 0, f"Frame advance: {self.frame_advance} steps", curses.A_BOLD)
        else:
            stdscr.addstr(7, 0, "Not calibrated (using default)", curses.A_DIM)
        
        # Camera status with model
        if self.camera_connected:
            camera_status = f"✓ {self.camera_model}"
            camera_color = curses.A_BOLD
        else:
            camera_status = "✗ Not connected"
            camera_color = curses.A_REVERSE
        stdscr.addstr(8, 0, f"Camera: {camera_status}", camera_color)
        
        step_str = "LARGE" if self.is_large_step else "small"
        stdscr.addstr(9, 0, f"Step size: {step_str}")
        
        if self.mode == 'calibrated':
            auto_str = "ON" if self.auto_advance else "OFF"
            stdscr.addstr(10, 0, f"Auto-advance: {auto_str}")
        
        # Controls
        stdscr.addstr(12, 0, "Controls:", curses.A_BOLD)
        stdscr.addstr(13, 0, "  ← / →       Fine adjustment")
        stdscr.addstr(14, 0, "  Shift+← / → Full frame forward/back")
        stdscr.addstr(15, 0, "  G           Toggle step size")
        stdscr.addstr(16, 0, "  SPACE       Capture (+ auto-advance)")
        stdscr.addstr(17, 0, "  A           Toggle auto-advance")
        stdscr.addstr(18, 0, "  C           Calibrate (strip 1)")
        stdscr.addstr(19, 0, "  S           Start new strip")
        stdscr.addstr(20, 0, "  F           Autofocus")
        stdscr.addstr(21, 0, "  M           Toggle Manual/Calibrated")
        stdscr.addstr(22, 0, "  N           New roll")
        stdscr.addstr(23, 0, "  Z           Zero position")
        stdscr.addstr(24, 0, "  Q           Quit")
        
        # Status message
        if self.status_msg:
            stdscr.addstr(26, 0, "Status:", curses.A_BOLD)
            stdscr.addstr(27, 0, self.status_msg[:75])
        
        stdscr.refresh()
    
    def run(self, stdscr):
        """Main loop"""
        curses.curs_set(0)
        stdscr.nodelay(False)
        
        # Find Arduino
        stdscr.clear()
        stdscr.addstr(0, 0, "Searching for Arduino...")
        stdscr.refresh()
        
        self.arduino = self.find_arduino(stdscr)
        
        if not self.arduino:
            stdscr.clear()
            stdscr.addstr(0, 0, "ERROR: Arduino not found!", curses.A_BOLD)
            stdscr.addstr(2, 0, "Check:")
            stdscr.addstr(3, 0, "  1. USB cable connection")
            stdscr.addstr(4, 0, "  2. Arduino sketch uploaded")
            stdscr.addstr(5, 0, "  3. Correct serial port permissions")
            stdscr.addstr(7, 0, "Press any key to exit...")
            stdscr.refresh()
            stdscr.getch()
            return
        
        # Initialize Arduino
        time.sleep(1)
        self.send('U')  # Unlock
        self.send('E')  # Enable motor
        self.send(f'v{self.step_delay}')  # Set step delay
        
        # Check camera and configure for RAW
        if self.check_camera():
            self.status_msg = f"Configuring {self.camera_model} for RAW capture..."
            self.draw(stdscr)
            self.setup_camera_raw()
            self.status_msg = f"✓ {self.camera_model} ready - Press N for new roll"
        else:
            self.status_msg = "⚠ No camera detected - Connect camera and press N"
        
        # Main loop
        while True:
            self.draw(stdscr)
            
            key = stdscr.getch()
            
            if key in [ord('q'), ord('Q'), 27]:  # Q or ESC
                break
            
            elif key == curses.KEY_LEFT:
                cmd = 'B' if self.is_large_step else 'b'
                if self.send(cmd):
                    self.status_msg = f"← Backward ({self.coarse_step if self.is_large_step else self.fine_step} steps)"
            
            elif key == curses.KEY_RIGHT:
                cmd = 'F' if self.is_large_step else 'f'
                if self.send(cmd):
                    self.status_msg = f"→ Forward ({self.coarse_step if self.is_large_step else self.fine_step} steps)"
            
            elif key == curses.KEY_SLEFT:  # Shift + Left (full frame back)
                if self.backup_frame():
                    pass  # Status already set
            
            elif key == curses.KEY_SRIGHT:  # Shift + Right (full frame forward)
                if self.advance_frame():
                    pass  # Status already set
            
            elif key in [ord('g'), ord('G')]:
                self.is_large_step = not self.is_large_step
                self.status_msg = f"Step size: {'LARGE' if self.is_large_step else 'small'}"
            
            elif key in [ord('m'), ord('M')]:
                self.mode = 'calibrated' if self.mode == 'manual' else 'manual'
                self.status_msg = f"Mode: {self.mode.upper()}"
                self.save_state()
            
            elif key in [ord('a'), ord('A')]:
                if self.mode == 'calibrated':
                    self.auto_advance = not self.auto_advance
                    self.status_msg = f"Auto-advance: {'ON' if self.auto_advance else 'OFF'}"
                    self.save_state()
                else:
                    self.status_msg = "Auto-advance only in calibrated mode"
            
            elif key in [ord('z'), ord('Z')]:
                self.send('Z')
                self.frame_positions = []
                self.status_msg = "Position zeroed"
            
            elif key in [ord('f'), ord('F')]:
                self.status_msg = "Focusing..."
                self.draw(stdscr)
                self.autofocus()
            
            elif key in [ord('c'), ord('C')]:
                if not self.roll_name:
                    self.status_msg = "Create roll first (press N)"
                else:
                    if self.calibrate(stdscr):
                        self.status_msg = f"✓ Calibrated: {self.frame_advance} steps/frame"
                    else:
                        self.status_msg = "Calibration cancelled"
            
            elif key in [ord('s'), ord('S')]:
                if not self.roll_name:
                    self.status_msg = "Create roll first (press N)"
                elif self.frame_advance is None:
                    self.status_msg = "Calibrate first (press C)"
                else:
                    if self.new_strip(stdscr):
                        self.status_msg = f"✓ Strip {self.strip_count} started"
                    else:
                        self.status_msg = "New strip cancelled"
            
            elif key == ord(' '):  # SPACE
                if not self.roll_name:
                    self.status_msg = "Create roll first (press N)"
                    continue
                
                # Check camera before capture
                if not self.check_camera():
                    self.status_msg = "Camera not connected!"
                    continue
                
                # Capture frame (auto-advance happens AFTER if enabled)
                self.capture_frame(stdscr)
            
            elif key in [ord('n'), ord('N')]:
                self.new_roll(stdscr)
        
        # Cleanup
        if self.arduino:
            self.send('M')  # Disable motor
            time.sleep(0.2)
            self.arduino.close()


def main():
    try:
        scanner = FilmScanner()
        curses.wrapper(scanner.run)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
