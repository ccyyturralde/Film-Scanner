#!/usr/bin/env python3
"""
35mm Film Scanner - Calibrated Step Mode
Optimized workflow for strip scanning with precise frame advance
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
        self.frame_advance = None  # Steps between frames (frame 1→2 distance)
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
        
    def find_arduino(self, stdscr=None):
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
                    if stdscr:
                        stdscr.addstr(8, 0, f"✓ Arduino found: {device}")
                        stdscr.refresh()
                        time.sleep(0.5)
                    self.arduino = ser
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
    
    def calibrate(self, stdscr):
        """
        CALIBRATION WORKFLOW:
        
        Strip 1 is special - used to learn frame spacing:
        1. Position frame 1 (first frame position is NOT used for calibration)
        2. Capture frame 1
        3. Manually advance to frame 2
        4. Capture frame 2
        5. Calculate: frame_advance = position_2 - position_1
        
        This frame_advance value is used for all remaining frames in the roll.
        """
        stdscr.clear()
        stdscr.addstr(0, 0, "=== CALIBRATION - STRIP 1 ===", curses.A_BOLD)
        stdscr.addstr(2, 0, "Position the FIRST frame in the scanning window")
        stdscr.addstr(3, 0, "(This position is just for alignment - not used for step calculation)")
        stdscr.addstr(5, 0, "Use arrow keys to align frame 1 perfectly")
        stdscr.addstr(6, 0, "Press SPACE when frame 1 is centered")
        stdscr.addstr(8, 0, "Controls:")
        stdscr.addstr(9, 0, "  ← →     Fine movement")
        stdscr.addstr(10, 0, "  G       Toggle step size")
        stdscr.addstr(11, 0, "  F       Autofocus")
        stdscr.addstr(12, 0, "  Q       Cancel")
        stdscr.addstr(14, 0, f"Position: {self.position}")
        stdscr.refresh()
        
        # Position frame 1
        while True:
            key = stdscr.getch()
            
            if key in [ord('q'), ord('Q')]:
                return False
            
            if key == ord(' '):  # Frame 1 aligned
                frame1_pos = self.position
                stdscr.addstr(16, 0, "Capturing frame 1...")
                stdscr.refresh()
                
                if not self.capture_image():
                    stdscr.addstr(17, 0, "❌ Capture failed! Check camera", curses.A_REVERSE)
                    stdscr.addstr(18, 0, "Press any key...")
                    stdscr.refresh()
                    stdscr.getch()
                    return False
                break
            
            elif key == curses.KEY_LEFT:
                cmd = 'B' if self.is_large_step else 'b'
                self.send(cmd)
                stdscr.addstr(14, 0, f"Position: {self.position}     ")
                stdscr.refresh()
            
            elif key == curses.KEY_RIGHT:
                cmd = 'F' if self.is_large_step else 'f'
                self.send(cmd)
                stdscr.addstr(14, 0, f"Position: {self.position}     ")
                stdscr.refresh()
            
            elif key in [ord('g'), ord('G')]:
                self.is_large_step = not self.is_large_step
                stdscr.addstr(15, 0, f"Step size: {'LARGE' if self.is_large_step else 'small'}     ")
                stdscr.refresh()
            
            elif key in [ord('f'), ord('F')]:
                stdscr.addstr(16, 0, "Focusing...           ")
                stdscr.refresh()
                self.autofocus()
                stdscr.addstr(16, 0, "                      ")
                stdscr.refresh()
        
        # Now position frame 2 - THIS IS THE CRITICAL MEASUREMENT
        stdscr.clear()
        stdscr.addstr(0, 0, "=== CALIBRATION - FRAME 2 ===", curses.A_BOLD)
        stdscr.addstr(2, 0, f"✓ Frame 1 captured at position {frame1_pos}")
        stdscr.addstr(4, 0, "Now manually advance to FRAME 2")
        stdscr.addstr(5, 0, "This distance defines the frame spacing for the entire roll")
        stdscr.addstr(7, 0, "Use arrow keys to align frame 2 perfectly")
        stdscr.addstr(8, 0, "Press SPACE when frame 2 is centered")
        stdscr.addstr(10, 0, "Controls: ← → G F Q")
        stdscr.addstr(12, 0, f"Frame 1 position: {frame1_pos}")
        stdscr.addstr(13, 0, f"Current position: {self.position}")
        stdscr.addstr(14, 0, f"Distance traveled: {self.position - frame1_pos} steps")
        stdscr.refresh()
        
        # Position frame 2
        while True:
            key = stdscr.getch()
            
            if key in [ord('q'), ord('Q')]:
                return False
            
            if key == ord(' '):  # Frame 2 aligned
                frame2_pos = self.position
                self.frame_advance = frame2_pos - frame1_pos
                
                if self.frame_advance <= 0:
                    stdscr.addstr(16, 0, "❌ Frame 2 must be ahead of frame 1!", curses.A_REVERSE)
                    stdscr.refresh()
                    time.sleep(2)
                    return False
                
                stdscr.addstr(16, 0, "Capturing frame 2...")
                stdscr.refresh()
                
                if not self.capture_image():
                    stdscr.addstr(17, 0, "❌ Capture failed!", curses.A_REVERSE)
                    stdscr.refresh()
                    time.sleep(2)
                    return False
                
                # Calibration complete
                self.strip_count = 1
                self.mode = 'calibrated'
                self.save_state()
                
                stdscr.clear()
                stdscr.addstr(0, 0, "✓ CALIBRATION COMPLETE", curses.A_BOLD)
                stdscr.addstr(2, 0, f"Frame advance: {self.frame_advance} steps")
                stdscr.addstr(3, 0, f"Strip 1: {self.frames_in_strip} frames captured")
                stdscr.addstr(5, 0, "This spacing will be used for:")
                stdscr.addstr(6, 0, "  • Remaining frames in this strip")
                stdscr.addstr(7, 0, "  • All frames in subsequent strips")
                stdscr.addstr(8, 0, "  • Fine adjustments still available with arrows")
                stdscr.addstr(10, 0, "Press SPACE to continue scanning this strip...")
                stdscr.refresh()
                stdscr.getch()
                
                self.status_msg = f"Strip 1, Frame {self.frames_in_strip} - Ready for frame 3"
                return True
            
            elif key == curses.KEY_LEFT:
                cmd = 'B' if self.is_large_step else 'b'
                self.send(cmd)
                stdscr.addstr(13, 0, f"Current position: {self.position}     ")
                stdscr.addstr(14, 0, f"Distance traveled: {self.position - frame1_pos} steps     ")
                stdscr.refresh()
            
            elif key == curses.KEY_RIGHT:
                cmd = 'F' if self.is_large_step else 'f'
                self.send(cmd)
                stdscr.addstr(13, 0, f"Current position: {self.position}     ")
                stdscr.addstr(14, 0, f"Distance traveled: {self.position - frame1_pos} steps     ")
                stdscr.refresh()
            
            elif key in [ord('g'), ord('G')]:
                self.is_large_step = not self.is_large_step
                stdscr.addstr(15, 0, f"Step size: {'LARGE' if self.is_large_step else 'small'}     ")
                stdscr.refresh()
            
            elif key in [ord('f'), ord('F')]:
                stdscr.addstr(16, 0, "Focusing...           ")
                stdscr.refresh()
                self.autofocus()
                stdscr.addstr(16, 0, "                      ")
                stdscr.refresh()
    
    def new_strip(self, stdscr):
        """
        START NEW STRIP WORKFLOW:
        
        For strips 2, 3, 4, etc.:
        1. Load new strip
        2. Position first frame (just for alignment)
        3. Use existing frame_advance for all subsequent frames
        4. Manual touch-ups available between any frames
        """
        stdscr.clear()
        stdscr.addstr(0, 0, f"=== NEW STRIP {self.strip_count + 1} ===", curses.A_BOLD)
        stdscr.addstr(2, 0, f"Calibration: {self.frame_advance} steps/frame")
        stdscr.addstr(4, 0, "Load the new film strip")
        stdscr.addstr(5, 0, "Position the FIRST frame in the scanning window")
        stdscr.addstr(6, 0, "(First frame position is for visual alignment only)")
        stdscr.addstr(8, 0, "Use arrow keys to align the first frame")
        stdscr.addstr(9, 0, "Press SPACE when ready to capture")
        stdscr.addstr(11, 0, "Controls: ← → G F Q")
        stdscr.addstr(13, 0, f"Position: {self.position}")
        stdscr.refresh()
        
        # Position first frame of new strip
        while True:
            key = stdscr.getch()
            
            if key in [ord('q'), ord('Q')]:
                return False
            
            if key == ord(' '):
                stdscr.addstr(15, 0, "Capturing first frame of strip...")
                stdscr.refresh()
                
                if not self.capture_image():
                    stdscr.addstr(16, 0, "❌ Capture failed!", curses.A_REVERSE)
                    stdscr.refresh()
                    time.sleep(2)
                    return False
                
                self.strip_count += 1
                self.frames_in_strip = 1
                self.save_state()
                
                stdscr.clear()
                stdscr.addstr(0, 0, f"✓ STRIP {self.strip_count} STARTED", curses.A_BOLD)
                stdscr.addstr(2, 0, f"First frame captured")
                stdscr.addstr(3, 0, f"Using calibrated advance: {self.frame_advance} steps")
                stdscr.addstr(5, 0, "Subsequent frames will auto-advance")
                stdscr.addstr(6, 0, "Fine-tune with arrows as needed")
                stdscr.addstr(8, 0, "Press any key to continue...")
                stdscr.refresh()
                stdscr.getch()
                
                self.status_msg = f"Strip {self.strip_count}, Frame 1 - Ready for frame 2"
                return True
            
            elif key == curses.KEY_LEFT:
                cmd = 'B' if self.is_large_step else 'b'
                self.send(cmd)
                stdscr.addstr(13, 0, f"Position: {self.position}     ")
                stdscr.refresh()
            
            elif key == curses.KEY_RIGHT:
                cmd = 'F' if self.is_large_step else 'f'
                self.send(cmd)
                stdscr.addstr(13, 0, f"Position: {self.position}     ")
                stdscr.refresh()
            
            elif key in [ord('g'), ord('G')]:
                self.is_large_step = not self.is_large_step
                stdscr.addstr(14, 0, f"Step size: {'LARGE' if self.is_large_step else 'small'}     ")
                stdscr.refresh()
            
            elif key in [ord('f'), ord('F')]:
                stdscr.addstr(15, 0, "Focusing...           ")
                stdscr.refresh()
                self.autofocus()
                stdscr.addstr(15, 0, "                      ")
                stdscr.refresh()
    
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
    
    def draw(self, stdscr):
        """Draw main interface"""
        stdscr.clear()
        
        # Header
        stdscr.addstr(0, 0, "=== 35mm FILM SCANNER ===", curses.A_BOLD)
        
        # Status
        row = 2
        stdscr.addstr(row, 0, f"Roll: {self.roll_name if self.roll_name else 'Not set'}")
        row += 1
        stdscr.addstr(row, 0, f"Strip: {self.strip_count}  Frame: {self.frame_count} (Strip: {self.frames_in_strip})")
        row += 1
        stdscr.addstr(row, 0, f"Position: {self.position}")
        row += 1
        stdscr.addstr(row, 0, f"Mode: {self.mode.upper()}")
        row += 1
        
        if self.frame_advance:
            stdscr.addstr(row, 0, f"Frame advance: {self.frame_advance} steps")
            row += 1
        
        self.check_camera()
        camera_status = "✓" if self.camera_connected else "✗"
        stdscr.addstr(row, 0, f"Camera: {camera_status} {self.camera_model}")
        row += 1
        
        if self.mode == 'calibrated':
            auto_status = "ON" if self.auto_advance else "OFF"
            stdscr.addstr(row, 0, f"Auto-advance: {auto_status}")
            row += 1
        
        # Controls
        row += 1
        stdscr.addstr(row, 0, "CONTROLS:", curses.A_BOLD)
        row += 1
        stdscr.addstr(row, 0, "  SPACE       Capture frame")
        row += 1
        stdscr.addstr(row, 0, "  ← →         Fine adjust")
        row += 1
        stdscr.addstr(row, 0, "  Shift+← →   Full frame back/forward")
        row += 1
        stdscr.addstr(row, 0, "  G           Toggle step size")
        row += 1
        stdscr.addstr(row, 0, "  F           Autofocus")
        row += 1
        stdscr.addstr(row, 0, "  C           Calibrate (Strip 1)")
        row += 1
        stdscr.addstr(row, 0, "  S           Start new strip")
        row += 1
        stdscr.addstr(row, 0, "  A           Toggle auto-advance")
        row += 1
        stdscr.addstr(row, 0, "  M           Manual/Calibrated mode")
        row += 1
        stdscr.addstr(row, 0, "  N           New roll")
        row += 1
        stdscr.addstr(row, 0, "  Z           Zero position")
        row += 1
        stdscr.addstr(row, 0, "  Q           Quit")
        row += 2
        
        # Status message
        stdscr.addstr(row, 0, self.status_msg, curses.A_REVERSE)
        
        stdscr.refresh()
    
    def run(self, stdscr):
        """Main event loop"""
        curses.curs_set(0)
        stdscr.nodelay(0)
        stdscr.timeout(100)
        
        # Find Arduino
        stdscr.addstr(0, 0, "Connecting to Arduino...")
        stdscr.refresh()
        
        if not self.find_arduino(stdscr):
            stdscr.addstr(2, 0, "Arduino not found!", curses.A_REVERSE)
            stdscr.addstr(3, 0, "Check connection and press any key...")
            stdscr.refresh()
            stdscr.getch()
            return
        
        self.check_camera()
        
        self.draw(stdscr)
        
        # Main loop
        while True:
            key = stdscr.getch()
            
            if key == -1:
                continue
            
            if key in [ord('q'), ord('Q')]:
                break
            
            elif key in [ord('n'), ord('N')]:
                # New roll
                curses.echo()
                stdscr.addstr(22, 0, "Roll name: " + " " * 50)
                stdscr.refresh()
                stdscr.move(22, 11)
                
                roll_input = stdscr.getstr(22, 11, 40).decode('utf-8').strip()
                curses.noecho()
                
                if roll_input:
                    date_str = datetime.now().strftime("%Y-%m-%d")
                    base_folder = os.path.expanduser("~/scans")
                    self.roll_folder = os.path.join(base_folder, date_str, roll_input)
                    os.makedirs(self.roll_folder, exist_ok=True)
                    
                    self.state_file = os.path.join(self.roll_folder, '.scan_state.json')
                    
                    if os.path.exists(self.state_file):
                        stdscr.addstr(23, 0, "Resume existing roll? (y/n): ")
                        stdscr.refresh()
                        resume = stdscr.getch()
                        
                        if resume in [ord('y'), ord('Y')]:
                            self.load_state(self.roll_folder)
                            self.status_msg = f"Resumed: {roll_input}"
                        else:
                            self.frame_count = 0
                            self.strip_count = 0
                            self.frames_in_strip = 0
                            self.frame_advance = None
                            self.frame_positions = []
                            self.status_msg = f"New roll: {roll_input}"
                    else:
                        self.status_msg = f"New roll: {roll_input}"
                    
                    self.roll_name = roll_input
                    self.save_state()
            
            elif key == curses.KEY_LEFT:
                cmd = 'B' if self.is_large_step else 'b'
                self.send(cmd)
                self.status_msg = f"← {self.coarse_step if self.is_large_step else self.fine_step} steps"
            
            elif key == curses.KEY_RIGHT:
                cmd = 'F' if self.is_large_step else 'f'
                self.send(cmd)
                self.status_msg = f"→ {self.coarse_step if self.is_large_step else self.fine_step} steps"
            
            elif key == curses.KEY_SLEFT:  # Shift+Left
                if self.backup_frame():
                    pass
            
            elif key == curses.KEY_SRIGHT:  # Shift+Right
                if self.advance_frame():
                    pass
            
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
                elif self.strip_count > 0:
                    self.status_msg = "Already calibrated - use S for new strip"
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
                    # Mark strip complete
                    self.frames_in_strip = 0
                    
                    if self.new_strip(stdscr):
                        self.status_msg = f"✓ Strip {self.strip_count} started"
                    else:
                        self.status_msg = "New strip cancelled"
            
            elif key == ord(' '):  # SPACE - Capture
                if not self.roll_name:
                    self.status_msg = "Create roll first (press N)"
                    continue
                
                if not self.check_camera():
                    self.status_msg = "Camera not connected!"
                    continue
                
                # Auto-advance BEFORE capture (for frames 2+)
                if self.mode == 'calibrated' and self.auto_advance and self.frames_in_strip > 0:
                    if self.frame_advance:
                        self.send(f'H{self.frame_advance}')
                        time.sleep(0.5)
                
                # Capture
                self.status_msg = "Capturing..."
                self.draw(stdscr)
                
                if self.capture_image():
                    self.status_msg = f"✓ Frame {self.frame_count} (Strip {self.strip_count})"
                else:
                    self.status_msg = "❌ Capture failed!"
            
            self.draw(stdscr)

def main():
    scanner = FilmScanner()
    curses.wrapper(scanner.run)

if __name__ == "__main__":
    main()
