#!/usr/bin/env python3
"""
35mm Film Scanner Control Application - Production Version
Uses proper two-gap detection to center frames correctly
"""

import curses
import serial
import serial.tools.list_ports
import subprocess
import time
import os
from datetime import datetime
import json

try:
    import cv2
    import numpy as np
    from optimized_edge_detect import detect_frame_gaps, get_motor_command
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    print("Warning: OpenCV not available. Auto-align disabled.")

class FilmScanner:
    def __init__(self):
        self.arduino = None
        self.roll_name = ""
        self.roll_folder = ""
        self.frame_count = 0
        self.status_msg = "Ready"
        
        # Motor configuration
        self.fine_step = 8
        self.coarse_step = 64
        self.steps_per_frame = 1200  # Will be calibrated
        
        # Position tracking
        self.position_steps = 0
        self.is_large_step = False
        
        # Mode
        self.mode = 'smart'  # 'manual' or 'smart'
        
        # Calibration (learned during use)
        self.pixels_per_step = 2.0  # Initial estimate, will be refined
        self.last_frame_advance = None  # Steps to advance between frames
        
        # State file
        self.state_file = None
        
    def find_arduino(self, stdscr=None):
        """Find Arduino on any available port"""
        
        ports = list(serial.tools.list_ports.comports())
        
        # Add Raspberry Pi specific ports
        pi_ports = ['/dev/ttyS0', '/dev/ttyAMA0', '/dev/serial0', '/dev/ttyUSB0', '/dev/ttyACM0']
        for pi_port in pi_ports:
            if os.path.exists(pi_port):
                class SimplePort:
                    def __init__(self, device):
                        self.device = device
                ports.append(SimplePort(pi_port))
        
        if stdscr:
            stdscr.clear()
            stdscr.addstr(0, 0, "Searching for Arduino...", curses.A_BOLD)
            stdscr.addstr(2, 0, f"Checking {len(ports)} ports")
            stdscr.refresh()
        
        for idx, port in enumerate(ports):
            device = port.device if hasattr(port, 'device') else str(port)
            
            if stdscr:
                stdscr.addstr(3 + idx, 0, f"Trying {device}...")
                stdscr.refresh()
            
            try:
                ser = serial.Serial(device, 115200, timeout=3, exclusive=False)
                time.sleep(2.5)
                
                ser.reset_input_buffer()
                ser.write(b'?\n')
                time.sleep(0.8)
                
                if ser.in_waiting:
                    response = ser.read_all().decode('utf-8', errors='ignore')
                    if any(word in response for word in ['READY', 'STATUS', 'NEMA', 'Position']):
                        if stdscr:
                            stdscr.addstr(3 + idx, 0, f"✓ Found Arduino on {device}!", curses.A_BOLD)
                            stdscr.refresh()
                            time.sleep(1)
                        return ser
                
                ser.close()
                
            except (OSError, serial.SerialException):
                continue
            except Exception:
                continue
        
        return None
    
    def send_command(self, cmd):
        """Send command to Arduino and track position"""
        if not self.arduino or not self.arduino.is_open:
            return
        
        try:
            self.arduino.write(f"{cmd}\n".encode())
            time.sleep(0.05)
            
            # Track position changes
            if cmd == 'f':
                self.position_steps += self.fine_step
            elif cmd == 'b':
                self.position_steps -= self.fine_step
            elif cmd == 'F':
                self.position_steps += self.coarse_step
            elif cmd == 'B':
                self.position_steps -= self.coarse_step
            elif cmd == 'N':
                self.position_steps += self.steps_per_frame
            elif cmd == 'R':
                self.position_steps -= self.steps_per_frame
            elif cmd.startswith('H'):
                steps = int(cmd[1:])
                self.position_steps += steps
            elif cmd.startswith('h'):
                steps = int(cmd[1:])
                self.position_steps -= steps
            elif cmd == 'Z':
                self.position_steps = 0
                
        except Exception as e:
            self.status_msg = f"Command error: {str(e)[:40]}"
    
    def capture_preview(self, output_path="/tmp/preview.jpg"):
        """Capture camera preview"""
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
            
            subprocess.run(["killall", "gphoto2"], capture_output=True, timeout=1)
            time.sleep(0.3)
            
            result = subprocess.run(
                ["gphoto2", "--capture-preview", f"--filename={output_path}"],
                capture_output=True,
                timeout=10
            )
            
            # Handle Canon thumb_ prefix
            if not os.path.exists(output_path):
                thumb_path = os.path.join(
                    os.path.dirname(output_path),
                    "thumb_" + os.path.basename(output_path)
                )
                if os.path.exists(thumb_path):
                    os.rename(thumb_path, output_path)
            
            time.sleep(0.4)
            return os.path.exists(output_path)
            
        except subprocess.TimeoutExpired:
            subprocess.run(["killall", "-9", "gphoto2"], capture_output=True)
            return False
        except Exception:
            return False
    
    def smart_align_step(self, stdscr):
        """
        Single step of intelligent frame alignment.
        Uses two-gap detection to properly center frames.
        """
        if not HAS_CV2:
            self.status_msg = "OpenCV not available"
            return False
        
        # Capture preview
        self.status_msg = "Capturing preview..."
        self.draw_screen(stdscr)
        
        if not self.capture_preview():
            self.status_msg = "Preview failed"
            return False
        
        # Detect frame gaps
        self.status_msg = "Analyzing frame position..."
        self.draw_screen(stdscr)
        
        result = detect_frame_gaps("/tmp/preview.jpg", debug=False)
        
        # Update status message
        self.status_msg = result.get('message', result.get('action', 'Processing...'))
        self.draw_screen(stdscr)
        
        # Check if aligned
        if result['action'] in ['CAPTURE', 'CAPTURE_OK']:
            self.status_msg = f"✓ ALIGNED! {result['message']}"
            self.draw_screen(stdscr)
            time.sleep(1)
            return True
        
        # Get motor command
        motor_cmd = get_motor_command(result, self.pixels_per_step)
        
        if motor_cmd['command']:
            self.status_msg = f"{result['status']}: {motor_cmd['description']}"
            self.draw_screen(stdscr)
            
            # Send command to Arduino
            self.send_command(motor_cmd['command'])
            time.sleep(0.4)  # Wait for movement
            
            return False
        else:
            # No movement needed - aligned
            return True
    
    def calibrate_frame_spacing(self, stdscr):
        """
        Calibrate pixels-per-step and frame spacing.
        Call this on the first frame after manual positioning.
        """
        if not HAS_CV2:
            return False
        
        stdscr.clear()
        stdscr.addstr(0, 0, "=== CALIBRATION ===", curses.A_BOLD)
        stdscr.addstr(2, 0, "Capturing initial position...")
        stdscr.refresh()
        
        # Capture first position
        if not self.capture_preview():
            stdscr.addstr(4, 0, "Preview failed!")
            stdscr.refresh()
            time.sleep(2)
            return False
        
        result1 = detect_frame_gaps("/tmp/preview.jpg")
        
        if not result1.get('frame_center'):
            stdscr.addstr(4, 0, "Could not detect frame - adjust position manually")
            stdscr.refresh()
            time.sleep(2)
            return False
        
        initial_center = result1['frame_center']
        initial_steps = self.position_steps
        
        stdscr.addstr(4, 0, f"Initial frame center: {initial_center}px")
        stdscr.addstr(5, 0, "")
        stdscr.addstr(6, 0, "Advancing to next frame...")
        stdscr.refresh()
        
        # Advance approximately one frame
        advance_steps = int(self.steps_per_frame * 0.8)  # Conservative estimate
        self.send_command(f'H{advance_steps}')
        time.sleep(1.5)
        
        # Capture new position
        if not self.capture_preview():
            stdscr.addstr(8, 0, "Second preview failed!")
            stdscr.refresh()
            time.sleep(2)
            return False
        
        result2 = detect_frame_gaps("/tmp/preview.jpg")
        
        if not result2.get('frame_center'):
            stdscr.addstr(8, 0, "Could not detect second frame")
            stdscr.refresh()
            time.sleep(2)
            return False
        
        new_center = result2['frame_center']
        steps_moved = self.position_steps - initial_steps
        pixels_moved = abs(new_center - initial_center)
        
        # Calculate pixels per step
        if steps_moved > 0 and pixels_moved > 0:
            self.pixels_per_step = pixels_moved / steps_moved
            
            # Also estimate frame spacing in steps
            # If we moved ~1 frame, this is our frame spacing
            if result2['action'] in ['CAPTURE', 'CAPTURE_OK', 'NEEDS_FINE_TUNE']:
                self.last_frame_advance = steps_moved
        
        stdscr.addstr(8, 0, f"New frame center: {new_center}px")
        stdscr.addstr(9, 0, f"Moved: {pixels_moved}px in {steps_moved} steps")
        stdscr.addstr(10, 0, f"Calculated: {self.pixels_per_step:.2f} pixels/step")
        stdscr.addstr(11, 0, "")
        stdscr.addstr(12, 0, "✓ Calibration complete!")
        stdscr.addstr(14, 0, "Press any key to continue...")
        stdscr.refresh()
        stdscr.getch()
        
        self.save_state()
        return True
    
    def capture_image(self, stdscr):
        """Capture RAW image"""
        self.status_msg = "Focusing and capturing..."
        self.draw_screen(stdscr)
        
        subprocess.run(["killall", "gphoto2"], capture_output=True, timeout=1)
        time.sleep(0.3)
        
        # Autofocus
        try:
            subprocess.run(
                ["gphoto2", "--set-config", "autofocus=1"],
                capture_output=True,
                timeout=5
            )
            time.sleep(1.5)
        except subprocess.TimeoutExpired:
            subprocess.run(["killall", "-9", "gphoto2"], capture_output=True)
        
        # Capture
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{timestamp}.cr3"
        filepath = os.path.join(self.roll_folder, filename)
        
        try:
            subprocess.run(
                ["gphoto2", "--capture-image-and-download", f"--filename={filepath}"],
                capture_output=True,
                timeout=20
            )
        except subprocess.TimeoutExpired:
            subprocess.run(["killall", "-9", "gphoto2"], capture_output=True)
            self.status_msg = "Capture timeout"
            return False
        
        if os.path.exists(filepath):
            self.frame_count += 1
            self.save_state()
            self.status_msg = f"✓ Frame {self.frame_count}: {filename}"
            time.sleep(1.2)
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
                'position_steps': self.position_steps,
                'mode': self.mode,
                'pixels_per_step': self.pixels_per_step,
                'last_frame_advance': self.last_frame_advance,
                'last_updated': datetime.now().isoformat()
            }
            try:
                with open(self.state_file, 'w') as f:
                    json.dump(state, f, indent=2)
            except Exception:
                pass
    
    def load_state(self):
        """Load saved state"""
        if self.state_file and os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                self.frame_count = state.get('frame_count', 0)
                self.position_steps = state.get('position_steps', 0)
                self.mode = state.get('mode', 'smart')
                self.pixels_per_step = state.get('pixels_per_step', 2.0)
                self.last_frame_advance = state.get('last_frame_advance')
                return True
            except Exception:
                return False
        return False
    
    def draw_screen(self, stdscr):
        """Draw interface"""
        stdscr.clear()
        
        try:
            stdscr.addstr(0, 0, "=== 35MM FILM SCANNER ===", curses.A_BOLD)
        except:
            pass
        
        # Status
        stdscr.addstr(2, 0, f"Roll: {self.roll_name if self.roll_name else 'None'}")
        stdscr.addstr(3, 0, f"Frames: {self.frame_count}")
        stdscr.addstr(4, 0, f"Position: {self.position_steps} steps")
        
        step_str = 'LARGE' if self.is_large_step else 'small'
        mode_str = self.mode.upper()
        stdscr.addstr(5, 0, f"Step: {step_str} | Mode: {mode_str}")
        
        if self.pixels_per_step != 2.0:
            stdscr.addstr(6, 0, f"Calibrated: {self.pixels_per_step:.2f} px/step")
        
        # Controls
        stdscr.addstr(8, 0, "Controls:", curses.A_BOLD)
        stdscr.addstr(9, 0, "  ← / →   Jog film (G toggles size)")
        stdscr.addstr(10, 0, "  SPACE   Auto-align + Capture")
        stdscr.addstr(11, 0, "  A       Auto-align only")
        stdscr.addstr(12, 0, "  C       Calibrate (first frame)")
        stdscr.addstr(13, 0, "  M       Toggle Manual/Smart mode")
        stdscr.addstr(14, 0, "  N       New roll")
        stdscr.addstr(15, 0, "  P       Preview")
        stdscr.addstr(16, 0, "  Z       Zero position")
        stdscr.addstr(17, 0, "  Q       Quit")
        
        # Status message
        if self.status_msg:
            stdscr.addstr(19, 0, "Status:", curses.A_BOLD)
            stdscr.addstr(20, 0, self.status_msg[:75])
        
        stdscr.refresh()
    
    def new_roll(self, stdscr):
        """Initialize new roll"""
        stdscr.clear()
        stdscr.addstr(0, 0, "=== NEW ROLL ===", curses.A_BOLD)
        stdscr.addstr(2, 0, "Enter roll name: ")
        stdscr.refresh()
        
        curses.echo()
        curses.curs_set(1)
        
        try:
            roll_input = stdscr.getstr(2, 17, 40).decode('utf-8', errors='ignore').strip()
        except Exception:
            roll_input = ""
        
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
            stdscr.addstr(2, 0, f"Frames: {self.frame_count}")
            stdscr.addstr(3, 0, f"Position: {self.position_steps} steps")
            stdscr.addstr(4, 0, f"Mode: {self.mode}")
            if self.pixels_per_step != 2.0:
                stdscr.addstr(5, 0, f"Calibrated: {self.pixels_per_step:.2f} px/step")
            stdscr.addstr(7, 0, "Continue (C) or Start Over (S)?")
            stdscr.refresh()
            
            while True:
                key = stdscr.getch()
                if key in [ord('c'), ord('C')]:
                    self.status_msg = f"Resumed at frame {self.frame_count}"
                    return True
                elif key in [ord('s'), ord('S')]:
                    self.frame_count = 0
                    self.position_steps = 0
                    self.pixels_per_step = 2.0
                    self.last_frame_advance = None
                    break
                elif key in [ord('q'), ord('Q')]:
                    return False
        
        # New roll setup
        self.frame_count = 0
        self.mode = 'smart'
        self.pixels_per_step = 2.0
        self.last_frame_advance = None
        
        stdscr.clear()
        stdscr.addstr(0, 0, f"Roll: {self.roll_name}", curses.A_BOLD)
        stdscr.addstr(2, 0, "Smart mode enabled")
        stdscr.addstr(4, 0, "Workflow:")
        stdscr.addstr(5, 0, "  1. Position first frame roughly (arrow keys)")
        stdscr.addstr(6, 0, "  2. Press C to calibrate")
        stdscr.addstr(7, 0, "  3. Press SPACE to auto-align + capture")
        stdscr.addstr(8, 0, "  4. Repeat for each frame")
        stdscr.addstr(10, 0, "Press any key to start...")
        stdscr.refresh()
        stdscr.getch()
        
        self.status_msg = "Position first frame, then press C to calibrate"
        self.save_state()
        return True
    
    def run(self, stdscr):
        """Main loop"""
        curses.curs_set(0)
        stdscr.nodelay(False)
        stdscr.clear()
        
        # Connect to Arduino
        self.arduino = self.find_arduino(stdscr)
        
        if not self.arduino:
            stdscr.clear()
            stdscr.addstr(0, 0, "ERROR: Arduino not found!", curses.A_BOLD)
            stdscr.addstr(2, 0, "Check USB connection and sketch upload")
            stdscr.addstr(4, 0, "Press any key to exit...")
            stdscr.refresh()
            stdscr.getch()
            return
        
        time.sleep(1)
        
        # Initialize Arduino
        stdscr.clear()
        stdscr.addstr(0, 0, f"✓ Arduino: {self.arduino.port}", curses.A_BOLD)
        stdscr.addstr(2, 0, "Initializing...")
        stdscr.refresh()
        
        self.send_command(f'S{self.steps_per_frame}')
        self.send_command(f'm{self.fine_step}')
        self.send_command(f'l{self.coarse_step}')
        self.send_command('U')
        self.send_command('E')
        time.sleep(0.5)
        
        stdscr.addstr(3, 0, "✓ Ready")
        stdscr.addstr(5, 0, "Press any key to start...")
        stdscr.refresh()
        stdscr.getch()
        
        self.status_msg = "Ready - Press N for new roll"
        
        # Main loop
        while True:
            self.draw_screen(stdscr)
            
            key = stdscr.getch()
            
            if key in [ord('q'), ord('Q'), 27]:
                break
            
            elif key == curses.KEY_LEFT:
                cmd = 'B' if self.is_large_step else 'b'
                self.send_command(cmd)
                self.status_msg = f"Moved backward ({cmd})"
            
            elif key == curses.KEY_RIGHT:
                cmd = 'F' if self.is_large_step else 'f'
                self.send_command(cmd)
                self.status_msg = f"Moved forward ({cmd})"
            
            elif key in [ord('g'), ord('G')]:
                self.is_large_step = not self.is_large_step
                self.status_msg = f"Step: {'LARGE' if self.is_large_step else 'small'}"
            
            elif key in [ord('m'), ord('M')]:
                self.mode = 'smart' if self.mode == 'manual' else 'manual'
                self.status_msg = f"Mode: {self.mode.upper()}"
                self.save_state()
            
            elif key in [ord('z'), ord('Z')]:
                self.send_command('Z')
                self.status_msg = "Position zeroed"
            
            elif key in [ord('p'), ord('P')]:
                if self.capture_preview():
                    self.status_msg = "✓ Preview: /tmp/preview.jpg"
                else:
                    self.status_msg = "✗ Preview failed"
            
            elif key in [ord('c'), ord('C')]:
                if self.roll_name:
                    self.calibrate_frame_spacing(stdscr)
                else:
                    self.status_msg = "Create roll first (press N)"
            
            elif key in [ord('a'), ord('A')]:
                if not self.roll_name:
                    self.status_msg = "Create roll first (press N)"
                    continue
                
                if not HAS_CV2:
                    self.status_msg = "OpenCV not available"
                    continue
                
                self.status_msg = "Auto-aligning..."
                self.draw_screen(stdscr)
                
                for attempt in range(20):
                    if self.smart_align_step(stdscr):
                        break
                    time.sleep(0.2)
                else:
                    self.status_msg = "Alignment timeout - try manual positioning"
            
            elif key == ord(' '):
                if not self.roll_name:
                    self.status_msg = "Create roll first (press N)"
                    continue
                
                if not HAS_CV2:
                    self.status_msg = "OpenCV not available - use manual mode"
                    continue
                
                # Smart capture: align then shoot
                self.status_msg = "Smart capture: aligning..."
                self.draw_screen(stdscr)
                
                aligned = False
                for attempt in range(20):
                    if self.smart_align_step(stdscr):
                        aligned = True
                        break
                    time.sleep(0.2)
                
                if aligned:
                    if self.capture_image(stdscr):
                        self.status_msg = f"✓ Frame {self.frame_count} complete!"
                        
                        # Auto-advance to next frame using learned spacing
                        if self.last_frame_advance:
                            self.status_msg = "Advancing to next frame..."
                            self.draw_screen(stdscr)
                            
                            # Use 85% of last advance (conservative)
                            advance = int(self.last_frame_advance * 0.85)
                            self.send_command(f'H{advance}')
                            time.sleep(0.8)
                            
                            self.status_msg = f"✓ Frame {self.frame_count} - ready for next"
                    else:
                        self.status_msg = "Capture failed"
                else:
                    self.status_msg = "Could not align - adjust manually and try again"
            
            elif key in [ord('n'), ord('N')]:
                self.new_roll(stdscr)
        
        # Cleanup
        if self.arduino:
            self.send_command('M')
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
