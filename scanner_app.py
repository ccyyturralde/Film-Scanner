#!/usr/bin/env python3
"""
35mm Film Scanner Control Application
Raspberry Pi 4 - Production Version
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
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

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
        self.steps_per_frame = 1200
        
        # Position tracking
        self.position_steps = 0
        self.is_large_step = False
        
        # Mode flags
        self.mode = 'manual'  # 'manual' or 'smart'
        
        # Smart mode parameters
        self.pixels_per_step = None  # Calibrated during use
        self.target_gap_percent = 82  # Ideal gap position (75-90% range)
        
        # State file
        self.state_file = None
        
    def find_arduino(self, stdscr=None):
        """Find Arduino on any available port (Raspberry Pi compatible)"""
        
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
    
    def detect_gap(self, img_path):
        """Detect frame gap using local edge detection"""
        if not HAS_CV2:
            return None, 0.0
        
        try:
            img = cv2.imread(img_path)
            if img is None:
                return None, 0.0
            
            h, w = img.shape[:2]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Focus on middle 40% vertically
            y1, y2 = int(h * 0.3), int(h * 0.7)
            roi = gray[y1:y2, :]
            
            # Brightness profile
            brightness = np.mean(roi, axis=0)
            
            # Smooth
            kernel_size = max(5, int(w * 0.005))
            kernel = np.ones(kernel_size) / kernel_size
            smoothed = np.convolve(brightness, kernel, mode='same')
            
            # Find bright peaks
            median_bright = np.median(smoothed)
            std_bright = np.std(smoothed)
            threshold = median_bright + 0.8 * std_bright
            bright_mask = smoothed > threshold
            
            # Find gaps
            gaps = []
            in_gap = False
            gap_start = 0
            
            for i in range(len(bright_mask)):
                if bright_mask[i] and not in_gap:
                    gap_start = i
                    in_gap = True
                elif not bright_mask[i] and in_gap:
                    gap_end = i
                    gap_width = gap_end - gap_start
                    
                    if 7 < gap_width < 100:
                        gap_center = (gap_start + gap_end) // 2
                        gap_brightness = np.mean(smoothed[gap_start:gap_end])
                        gaps.append({
                            'center': gap_center,
                            'width': gap_width,
                            'brightness': gap_brightness,
                            'percent': (gap_center / w) * 100
                        })
                    in_gap = False
            
            if not gaps:
                return None, 0.0
            
            # Find rightmost gap
            target_min_pct = 55
            right_gaps = [g for g in gaps if g['percent'] > target_min_pct]
            
            if not right_gaps:
                selected = max(gaps, key=lambda g: g['center'])
            else:
                selected = max(right_gaps, key=lambda g: g['center'])
            
            # Calculate confidence
            max_bright = np.max(smoothed)
            brightness_ratio = selected['brightness'] / max_bright
            width_score = min(selected['width'] / 40, 1.0)
            confidence = (brightness_ratio * 0.7 + width_score * 0.3)
            
            return selected['center'], confidence
            
        except Exception:
            return None, 0.0
    
    def smart_align_step(self, stdscr):
        """
        Single step of smart alignment.
        Makes intelligent decisions about how far to move based on distance to target.
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
        
        # Detect gap
        self.status_msg = "Detecting gap..."
        self.draw_screen(stdscr)
        
        gap_col, confidence = self.detect_gap("/tmp/preview.jpg")
        
        if gap_col is None:
            # No gap visible - advance forward to find next frame
            self.status_msg = "No gap - advancing"
            self.draw_screen(stdscr)
            self.send_command('F')
            time.sleep(0.5)
            return False
        
        # Get image width
        img = cv2.imread("/tmp/preview.jpg")
        img_width = img.shape[1]
        
        # Target: 75-90% of width, ideal at 82%
        target_min = int(img_width * 0.75)
        target_max = int(img_width * 0.90)
        target_ideal = int(img_width * 0.82)
        
        # Calculate offset
        offset = gap_col - target_ideal
        gap_percent = (gap_col / img_width) * 100
        
        # Check if aligned
        if target_min <= gap_col <= target_max and abs(offset) <= 8:
            self.status_msg = f"✓ ALIGNED at {gap_percent:.1f}%"
            self.draw_screen(stdscr)
            time.sleep(1)
            return True
        
        # Calculate movement needed
        # Key insight: pixels to steps conversion
        # Estimate: ~2 pixels per step (calibrate during use)
        if self.pixels_per_step is None:
            self.pixels_per_step = 2.0  # Initial estimate
        
        steps_needed = int(abs(offset) / self.pixels_per_step)
        
        # Determine movement strategy based on distance
        if abs(offset) > 200:
            # Large distance - use coarse movement
            self.status_msg = f"Gap at {gap_percent:.1f}%, advancing ~{steps_needed} steps"
            self.draw_screen(stdscr)
            
            # Make multiple coarse movements if needed
            num_coarse = max(1, steps_needed // self.coarse_step)
            for _ in range(min(num_coarse, 5)):  # Limit to 5 moves per iteration
                if offset > 0:
                    self.send_command('B')
                else:
                    self.send_command('F')
                time.sleep(0.3)
            
        elif abs(offset) > 50:
            # Medium distance - use fine movement
            self.status_msg = f"Gap at {gap_percent:.1f}%, fine adjustment"
            self.draw_screen(stdscr)
            
            num_fine = max(1, steps_needed // self.fine_step)
            for _ in range(min(num_fine, 3)):
                if offset > 0:
                    self.send_command('b')
                else:
                    self.send_command('f')
                time.sleep(0.2)
        
        else:
            # Small distance - single fine movement
            self.status_msg = f"Almost aligned, {abs(offset)}px offset"
            self.draw_screen(stdscr)
            
            if offset > 0:
                self.send_command('b')
            else:
                self.send_command('f')
            time.sleep(0.2)
        
        return False
    
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
                self.mode = state.get('mode', 'manual')
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
        
        # Controls
        stdscr.addstr(7, 0, "Controls:", curses.A_BOLD)
        stdscr.addstr(8, 0, "  ← / →   Jog film (G toggles size)")
        stdscr.addstr(9, 0, "  SPACE   Capture frame")
        stdscr.addstr(10, 0, "  M       Toggle Manual/Smart mode")
        stdscr.addstr(11, 0, "  A       Auto-align (smart mode)")
        stdscr.addstr(12, 0, "  N       New roll")
        stdscr.addstr(13, 0, "  P       Preview")
        stdscr.addstr(14, 0, "  Z       Zero position")
        stdscr.addstr(15, 0, "  Q       Quit")
        
        # Status message
        if self.status_msg:
            stdscr.addstr(17, 0, "Status:", curses.A_BOLD)
            stdscr.addstr(18, 0, self.status_msg[:75])
        
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
            stdscr.addstr(6, 0, "Continue (C) or Start Over (S)?")
            stdscr.refresh()
            
            while True:
                key = stdscr.getch()
                if key in [ord('c'), ord('C')]:
                    self.status_msg = f"Resumed at frame {self.frame_count}"
                    return True
                elif key in [ord('s'), ord('S')]:
                    self.frame_count = 0
                    self.position_steps = 0
                    break
                elif key in [ord('q'), ord('Q')]:
                    return False
        
        # Choose mode
        stdscr.clear()
        stdscr.addstr(0, 0, f"Roll: {self.roll_name}", curses.A_BOLD)
        stdscr.addstr(2, 0, "Choose mode:")
        stdscr.addstr(3, 0, "  1 = Manual (arrow keys + space)")
        stdscr.addstr(4, 0, "  2 = Smart (auto-align frames)")
        stdscr.addstr(6, 0, "Press 1 or 2...")
        stdscr.refresh()
        
        while True:
            key = stdscr.getch()
            if key == ord('1'):
                self.mode = 'manual'
                self.frame_count = 0
                self.status_msg = "Manual mode - use arrows to position, space to capture"
                self.save_state()
                return True
            elif key == ord('2'):
                self.mode = 'smart'
                self.frame_count = 0
                self.status_msg = "Smart mode - press A to align, space to capture"
                self.save_state()
                return True
            elif key in [ord('q'), ord('Q')]:
                return False
    
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
            
            elif key in [ord('a'), ord('A')]:
                if self.roll_name and self.mode == 'smart':
                    self.status_msg = "Auto-aligning..."
                    self.draw_screen(stdscr)
                    
                    for attempt in range(20):
                        if self.smart_align_step(stdscr):
                            break
                        time.sleep(0.2)
                    else:
                        self.status_msg = "Alignment timeout"
                else:
                    self.status_msg = "Auto-align only in smart mode"
            
            elif key == ord(' '):
                if not self.roll_name:
                    self.status_msg = "Press N to create roll first"
                    continue
                
                if self.mode == 'smart':
                    # Smart mode: align then capture
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
                            self.status_msg = f"✓ Frame {self.frame_count} captured"
                        else:
                            self.status_msg = "Capture failed"
                    else:
                        self.status_msg = "Could not align - try manual positioning"
                
                else:
                    # Manual mode: just capture
                    if self.capture_image(stdscr):
                        self.status_msg = f"✓ Frame {self.frame_count} captured"
                    else:
                        self.status_msg = "Capture failed"
            
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
