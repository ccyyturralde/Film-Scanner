#!/usr/bin/env python3
"""
35mm Film Scanner Control - Professional Version
Focus: Manual control and calibrated advance without problematic CV
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
        self.status_msg = "Ready"
        
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
    
    def capture_preview(self):
        """Capture camera preview for positioning"""
        try:
            subprocess.run(["killall", "gphoto2"], capture_output=True, timeout=1)
            time.sleep(0.3)
            
            result = subprocess.run(
                ["gphoto2", "--capture-preview", "--filename=/tmp/preview.jpg"],
                capture_output=True,
                timeout=10
            )
            
            # Handle Canon thumb_ prefix
            if not os.path.exists("/tmp/preview.jpg") and os.path.exists("/tmp/thumb_preview.jpg"):
                os.rename("/tmp/thumb_preview.jpg", "/tmp/preview.jpg")
            
            return os.path.exists("/tmp/preview.jpg")
        except:
            return False
    
    def capture_image(self):
        """Capture final image"""
        subprocess.run(["killall", "gphoto2"], capture_output=True, timeout=1)
        time.sleep(0.3)
        
        # Autofocus (optional, comment out if not needed)
        try:
            subprocess.run(
                ["gphoto2", "--set-config", "autofocus=1"],
                capture_output=True,
                timeout=5
            )
            time.sleep(1.5)
        except:
            pass
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{timestamp}.cr3"  # Adjust extension for your camera
        filepath = os.path.join(self.roll_folder, filename)
        
        # Capture
        try:
            result = subprocess.run(
                ["gphoto2", "--capture-image-and-download", f"--filename={filepath}"],
                capture_output=True,
                timeout=20
            )
            
            if os.path.exists(filepath):
                self.frame_count += 1
                self.frame_positions.append(self.position)
                self.save_state()
                return True
        except subprocess.TimeoutExpired:
            subprocess.run(["killall", "-9", "gphoto2"], capture_output=True)
        
        return False
    
    def calibrate(self, stdscr):
        """
        Calibrate frame advance distance.
        Assumes frame 1 is already manually positioned.
        """
        stdscr.clear()
        stdscr.addstr(0, 0, "=== CALIBRATION ===", curses.A_BOLD)
        stdscr.addstr(2, 0, "Frame 1 should be properly positioned")
        stdscr.addstr(3, 0, "Press ENTER when ready, or Q to cancel")
        stdscr.refresh()
        
        while True:
            key = stdscr.getch()
            if key == 10:  # Enter
                break
            elif key in [ord('q'), ord('Q')]:
                return False
        
        # Record frame 1 position
        frame1_pos = self.position
        
        stdscr.clear()
        stdscr.addstr(0, 0, "=== CALIBRATION ===", curses.A_BOLD)
        stdscr.addstr(2, 0, f"Frame 1 position: {frame1_pos}")
        stdscr.addstr(4, 0, "Now advance to frame 2 using arrow keys")
        stdscr.addstr(5, 0, "Press ENTER when frame 2 is centered")
        stdscr.addstr(7, 0, "Controls:")
        stdscr.addstr(8, 0, "  ← →     Fine movement")
        stdscr.addstr(9, 0, "  Shift+← →   Coarse movement")
        stdscr.addstr(10, 0, "  P       Preview")
        stdscr.addstr(12, 0, f"Position: {self.position}")
        stdscr.refresh()
        
        # Manual positioning loop
        while True:
            key = stdscr.getch()
            
            if key == 10:  # Enter - done positioning
                frame2_pos = self.position
                self.frame_advance = frame2_pos - frame1_pos
                
                if self.frame_advance <= 0:
                    stdscr.addstr(14, 0, "ERROR: Frame 2 must be ahead of frame 1!", curses.A_REVERSE)
                    stdscr.refresh()
                    time.sleep(2)
                    return False
                
                stdscr.clear()
                stdscr.addstr(0, 0, "✓ CALIBRATION COMPLETE", curses.A_BOLD)
                stdscr.addstr(2, 0, f"Frame spacing: {self.frame_advance} steps")
                stdscr.addstr(4, 0, "This will be used for all frames")
                stdscr.addstr(6, 0, "Press any key to continue...")
                stdscr.refresh()
                stdscr.getch()
                
                self.save_state()
                return True
                
            elif key == curses.KEY_LEFT:
                self.send('b')
                stdscr.addstr(12, 0, f"Position: {self.position}     ")
                stdscr.refresh()
                
            elif key == curses.KEY_RIGHT:
                self.send('f')
                stdscr.addstr(12, 0, f"Position: {self.position}     ")
                stdscr.refresh()
                
            elif key == curses.KEY_SLEFT:
                self.send('B')
                stdscr.addstr(12, 0, f"Position: {self.position}     ")
                stdscr.refresh()
                
            elif key == curses.KEY_SRIGHT:
                self.send('F')
                stdscr.addstr(12, 0, f"Position: {self.position}     ")
                stdscr.refresh()
                
            elif key in [ord('p'), ord('P')]:
                stdscr.addstr(14, 0, "Capturing preview...")
                stdscr.refresh()
                if self.capture_preview():
                    stdscr.addstr(14, 0, "Preview saved to /tmp/preview.jpg     ")
                else:
                    stdscr.addstr(14, 0, "Preview failed                        ")
                stdscr.refresh()
                
            elif key in [ord('q'), ord('Q')]:
                return False
    
    def advance_frame(self):
        """Advance to next frame using calibrated distance"""
        if self.frame_advance is None:
            # Use default if not calibrated
            advance = self.default_advance
            self.status_msg = f"Advancing {advance} steps (default)"
        else:
            advance = self.frame_advance
            self.status_msg = f"Advancing {advance} steps (calibrated)"
        
        return self.send(f'H{advance}')
    
    def capture_frame(self, stdscr):
        """Capture current frame"""
        self.status_msg = "Capturing..."
        self.draw(stdscr)
        
        if self.capture_image():
            self.status_msg = f"✓ Frame {self.frame_count} captured"
            
            # Calculate actual advance if we have previous frames
            if len(self.frame_positions) >= 2:
                actual_advance = self.frame_positions[-1] - self.frame_positions[-2]
                self.status_msg += f" (advanced {actual_advance} steps)"
            
            return True
        else:
            self.status_msg = "✗ Capture failed"
            return False
    
    def save_state(self):
        """Save current state"""
        if self.state_file:
            state = {
                'roll_name': self.roll_name,
                'frame_count': self.frame_count,
                'position': self.position,
                'frame_advance': self.frame_advance,
                'frame_positions': self.frame_positions,
                'mode': self.mode,
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
                self.position = state.get('position', 0)
                self.frame_advance = state.get('frame_advance')
                self.frame_positions = state.get('frame_positions', [])
                self.mode = state.get('mode', 'manual')
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
        
        # Create folder
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
        stdscr.addstr(2, 0, "WORKFLOW:")
        stdscr.addstr(4, 0, "Manual Mode:")
        stdscr.addstr(5, 0, "  1. Use arrows to position each frame")
        stdscr.addstr(6, 0, "  2. Press SPACE to capture")
        stdscr.addstr(8, 0, "Calibrated Mode:")
        stdscr.addstr(9, 0, "  1. Position frame 1 manually")
        stdscr.addstr(10, 0, "  2. Press C to calibrate advance")
        stdscr.addstr(11, 0, "  3. Press SPACE to auto-advance and capture")
        stdscr.addstr(13, 0, "Press any key to continue...")
        stdscr.refresh()
        stdscr.getch()
        
        self.status_msg = "Position frame 1"
        self.save_state()
        return True
    
    def draw(self, stdscr):
        """Draw main interface"""
        stdscr.clear()
        
        stdscr.addstr(0, 0, "=== 35MM FILM SCANNER ===", curses.A_BOLD)
        
        # Status
        stdscr.addstr(2, 0, f"Roll: {self.roll_name if self.roll_name else 'None'}")
        stdscr.addstr(3, 0, f"Frames: {self.frame_count}")
        stdscr.addstr(4, 0, f"Position: {self.position} steps")
        
        # Mode and calibration
        mode_str = "MANUAL" if self.mode == 'manual' else "CALIBRATED"
        stdscr.addstr(5, 0, f"Mode: {mode_str}")
        
        if self.frame_advance:
            stdscr.addstr(6, 0, f"Frame advance: {self.frame_advance} steps", curses.A_BOLD)
        else:
            stdscr.addstr(6, 0, "Not calibrated (using default)", curses.A_DIM)
        
        step_str = "LARGE" if self.is_large_step else "small"
        stdscr.addstr(7, 0, f"Step size: {step_str}")
        
        # Controls
        stdscr.addstr(9, 0, "Controls:", curses.A_BOLD)
        stdscr.addstr(10, 0, "  ← / →       Manual jog")
        stdscr.addstr(11, 0, "  G           Toggle step size")
        stdscr.addstr(12, 0, "  SPACE       Capture (advance if calibrated)")
        stdscr.addstr(13, 0, "  A           Advance one frame")
        stdscr.addstr(14, 0, "  C           Calibrate frame spacing")
        stdscr.addstr(15, 0, "  M           Toggle Manual/Calibrated mode")
        stdscr.addstr(16, 0, "  N           New roll")
        stdscr.addstr(17, 0, "  P           Preview")
        stdscr.addstr(18, 0, "  Z           Zero position")
        stdscr.addstr(19, 0, "  Q           Quit")
        
        # Status message
        if self.status_msg:
            stdscr.addstr(21, 0, "Status:", curses.A_BOLD)
            stdscr.addstr(22, 0, self.status_msg[:75])
        
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
        
        self.status_msg = "Ready - Press N for new roll"
        
        # Main loop
        while True:
            self.draw(stdscr)
            
            key = stdscr.getch()
            
            if key in [ord('q'), ord('Q'), 27]:  # Q or ESC
                break
            
            elif key == curses.KEY_LEFT:
                cmd = 'B' if self.is_large_step else 'b'
                if self.send(cmd):
                    self.status_msg = f"← Moved backward ({self.coarse_step if self.is_large_step else self.fine_step} steps)"
            
            elif key == curses.KEY_RIGHT:
                cmd = 'F' if self.is_large_step else 'f'
                if self.send(cmd):
                    self.status_msg = f"→ Moved forward ({self.coarse_step if self.is_large_step else self.fine_step} steps)"
            
            elif key in [ord('g'), ord('G')]:
                self.is_large_step = not self.is_large_step
                self.status_msg = f"Step size: {'LARGE' if self.is_large_step else 'small'}"
            
            elif key in [ord('m'), ord('M')]:
                self.mode = 'calibrated' if self.mode == 'manual' else 'manual'
                self.status_msg = f"Mode: {self.mode.upper()}"
                self.save_state()
            
            elif key in [ord('z'), ord('Z')]:
                self.send('Z')
                self.frame_positions = []
                self.status_msg = "Position zeroed"
            
            elif key in [ord('p'), ord('P')]:
                self.status_msg = "Capturing preview..."
                self.draw(stdscr)
                if self.capture_preview():
                    self.status_msg = "✓ Preview: /tmp/preview.jpg"
                else:
                    self.status_msg = "✗ Preview failed"
            
            elif key in [ord('c'), ord('C')]:
                if not self.roll_name:
                    self.status_msg = "Create roll first (press N)"
                else:
                    if self.calibrate(stdscr):
                        self.status_msg = f"✓ Calibrated: {self.frame_advance} steps/frame"
                        self.mode = 'calibrated'
                    else:
                        self.status_msg = "Calibration cancelled"
            
            elif key in [ord('a'), ord('A')]:
                if self.advance_frame():
                    self.status_msg = f"Advanced to next frame"
                else:
                    self.status_msg = "Advance failed"
            
            elif key == ord(' '):  # SPACE
                if not self.roll_name:
                    self.status_msg = "Create roll first (press N)"
                    continue
                
                # In calibrated mode, advance first (except for first frame)
                if self.mode == 'calibrated' and self.frame_count > 0:
                    if not self.advance_frame():
                        self.status_msg = "Advance failed"
                        continue
                    time.sleep(1)  # Wait for movement to complete
                
                # Capture
                if self.capture_frame(stdscr):
                    pass  # Status already set by capture_frame
                else:
                    self.status_msg = "Capture failed"
            
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
