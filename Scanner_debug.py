#!/usr/bin/env python3
"""
Film Scanner - Clean Implementation
Goal: Minimize gap visibility, center frame content
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
    print("ERROR: OpenCV required for smart alignment")
    exit(1)

LOG = "/tmp/scanner_debug.log"

def log(msg):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    with open(LOG, 'a') as f:
        f.write(f"[{ts}] {msg}\n")

def detect_frame_state(img_path):
    """
    Detect frame alignment state.
    Returns: status, action, distance
    
    GOAL: Frame content fills view, gaps < 50px at edges
    """
    img = cv2.imread(img_path)
    if img is None:
        return 'ERROR', 'NONE', 0
    
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Analyze middle section
    roi = gray[int(h*0.3):int(h*0.7), :]
    brightness = np.mean(roi, axis=0)
    
    # Smooth to reduce noise
    kernel_size = max(5, int(w * 0.01))
    kernel = np.ones(kernel_size) / kernel_size
    smoothed = np.convolve(brightness, kernel, mode='same')
    
    # Detect bright regions (potential gaps)
    threshold = np.percentile(smoothed, 80)
    is_bright = smoothed > threshold
    
    # Find contiguous bright regions
    gaps = []
    in_gap = False
    gap_start = 0
    
    for i in range(len(is_bright)):
        if is_bright[i] and not in_gap:
            gap_start = i
            in_gap = True
        elif not is_bright[i] and in_gap:
            gap_width = i - gap_start
            if gap_width > 15:  # Minimum gap width
                gap_center = (gap_start + i) // 2
                gaps.append({
                    'start': gap_start,
                    'end': i,
                    'center': gap_center,
                    'width': gap_width,
                    'percent': (gap_center / w) * 100
                })
            in_gap = False
    
    log(f"Image width: {w}px, found {len(gaps)} gaps")
    for g in gaps:
        log(f"  Gap: {g['width']}px at {g['percent']:.1f}%")
    
    # Analyze alignment state
    if len(gaps) == 0:
        # No gaps - either perfect or between frames
        log("No gaps visible")
        return 'NO_GAPS', 'ADVANCE_SMALL', 10
    
    # Find largest gap (most problematic)
    largest = max(gaps, key=lambda g: g['width'])
    w_gap = largest['width']
    p_gap = largest['percent']
    
    # CRITICAL LOGIC: A VISIBLE GAP MEANS NOT ALIGNED
    # Only acceptable: small gap (<40px) at extreme edge
    
    if w_gap < 40 and (p_gap < 15 or p_gap > 85):
        # Small gap at edge - acceptable
        log(f"ALIGNED: {w_gap}px gap at {p_gap:.1f}%")
        return 'ALIGNED', 'CAPTURE', 0
    
    if w_gap > 150:
        # Huge gap - way off
        log(f"Large gap: {w_gap}px at {p_gap:.1f}%")
        return 'LARGE_GAP', 'ADVANCE_LARGE', 50
    
    if p_gap < 30:
        # Gap on left - advance
        dist = int(p_gap * w / 100) + 30  # Advance past it
        log(f"Gap left at {p_gap:.1f}%, advancing {dist}px")
        return 'GAP_LEFT', 'ADVANCE_MEDIUM', dist
    
    if p_gap > 70:
        # Gap on right - almost there, small advance
        dist = 20
        log(f"Gap right at {p_gap:.1f}%, advancing {dist}px")
        return 'GAP_RIGHT', 'ADVANCE_SMALL', dist
    
    # Gap centered (30-70%) - advance more
    dist = int((50 - p_gap) * w / 100) + 40 if p_gap < 50 else 30
    log(f"Gap centered at {p_gap:.1f}%, advancing {dist}px")
    return 'GAP_CENTERED', 'ADVANCE_MEDIUM', dist


class FilmScanner:
    def __init__(self):
        self.arduino = None
        self.roll_name = ""
        self.roll_folder = ""
        self.frame_count = 0
        self.status_msg = "Ready"
        
        # Motor config
        # NOTE: If A4988 is in 1/16 microstepping mode,
        # each step command = 1 microstep
        self.fine_step = 8      # pulses (microsteps if driver in microstep mode)
        self.coarse_step = 64
        
        # Calibration
        self.pixels_per_step = None  # Will be calibrated
        self.frame_advance_steps = None  # Steps between frames
        
        self.position = 0
        self.state_file = None
        
        # Create log
        open(LOG, 'w').write(f"=== Film Scanner Started ===\n{datetime.now()}\n\n")
        log("Scanner initialized")
        log("NOTE: Step commands are pulses - driver interprets as microsteps if wired that way")
    
    def find_arduino(self, stdscr=None):
        """Find Arduino"""
        ports = list(serial.tools.list_ports.comports())
        
        # Add common Pi ports
        for p in ['/dev/ttyACM0', '/dev/ttyUSB0', '/dev/serial0', '/dev/ttyAMA0']:
            if os.path.exists(p):
                class Port:
                    def __init__(self, d):
                        self.device = d
                ports.append(Port(p))
        
        for port in ports:
            device = port.device if hasattr(port, 'device') else str(port)
            try:
                ser = serial.Serial(device, 115200, timeout=3)
                time.sleep(2.5)
                ser.reset_input_buffer()
                ser.write(b'?\n')
                time.sleep(0.8)
                
                if ser.in_waiting:
                    resp = ser.read_all().decode('utf-8', errors='ignore')
                    if any(x in resp for x in ['READY', 'STATUS', 'NEMA', 'Position']):
                        log(f"Arduino found: {device}")
                        return ser
                ser.close()
            except:
                continue
        
        return None
    
    def send(self, cmd):
        """Send command to Arduino"""
        if not self.arduino:
            return
        
        try:
            self.arduino.write(f"{cmd}\n".encode())
            log(f">>> {cmd}")
            time.sleep(0.05)
            
            # Track position
            if cmd == 'f':
                self.position += self.fine_step
            elif cmd == 'b':
                self.position -= self.fine_step
            elif cmd == 'F':
                self.position += self.coarse_step
            elif cmd == 'B':
                self.position -= self.coarse_step
            elif cmd.startswith('H'):
                self.position += int(cmd[1:])
            elif cmd.startswith('h'):
                self.position -= int(cmd[1:])
            elif cmd == 'Z':
                self.position = 0
        
        except Exception as e:
            log(f"Command error: {e}")
    
    def preview(self):
        """Capture preview image"""
        try:
            path = "/tmp/preview.jpg"
            if os.path.exists(path):
                os.remove(path)
            
            subprocess.run(["killall", "gphoto2"], capture_output=True, timeout=1)
            time.sleep(0.3)
            
            result = subprocess.run(
                ["gphoto2", "--capture-preview", f"--filename={path}"],
                capture_output=True,
                timeout=10
            )
            
            # Handle Canon thumb_ prefix
            if not os.path.exists(path):
                thumb = os.path.join(os.path.dirname(path), "thumb_" + os.path.basename(path))
                if os.path.exists(thumb):
                    os.rename(thumb, path)
            
            time.sleep(0.3)
            success = os.path.exists(path)
            if not success:
                log("Preview failed")
            return success
        
        except Exception as e:
            log(f"Preview error: {e}")
            return False
    
    def calibrate(self, stdscr):
        """
        Calibrate pixels per step and frame spacing.
        Assumes frame 1 is manually aligned by user.
        """
        log("\n=== CALIBRATION START ===")
        
        stdscr.clear()
        stdscr.addstr(0, 0, "=== CALIBRATION ===", curses.A_BOLD)
        stdscr.addstr(2, 0, "Frame 1 should be aligned")
        stdscr.addstr(3, 0, "Capturing initial position...")
        stdscr.refresh()
        
        if not self.preview():
            stdscr.addstr(5, 0, "Preview failed!")
            stdscr.refresh()
            time.sleep(2)
            return False
        
        # Detect initial state
        status1, action1, dist1 = detect_frame_state("/tmp/preview.jpg")
        
        if status1 != 'ALIGNED':
            stdscr.addstr(5, 0, "Frame 1 not aligned! Use arrows to align first")
            stdscr.addstr(6, 0, "Press any key...")
            stdscr.refresh()
            stdscr.getch()
            return False
        
        log("Frame 1 confirmed aligned")
        pos_start = self.position
        
        stdscr.addstr(5, 0, "Frame 1 OK, advancing to frame 2...")
        stdscr.refresh()
        
        # Advance conservatively
        # Start with ~80-100 steps, iterate to find frame
        test_advance = 100
        log(f"Initial advance: {test_advance} steps")
        self.send(f'H{test_advance}')
        time.sleep(1.5)
        
        # Iteratively find frame 2
        for attempt in range(10):
            if not self.preview():
                continue
            
            status, action, dist = detect_frame_state("/tmp/preview.jpg")
            log(f"Attempt {attempt+1}: {status}, action={action}")
            
            if status == 'ALIGNED':
                # Found frame 2!
                break
            
            if status == 'NO_GAPS' or status == 'LARGE_GAP':
                # Need more advance
                self.send('H30')
                time.sleep(0.8)
            elif status in ['GAP_LEFT', 'GAP_CENTERED', 'GAP_RIGHT']:
                # Close - fine tune
                steps = max(5, dist // 4)  # Conservative
                self.send(f'H{steps}')
                time.sleep(0.5)
        else:
            stdscr.addstr(7, 0, "Could not find frame 2!")
            stdscr.addstr(8, 0, "Press any key...")
            stdscr.refresh()
            stdscr.getch()
            return False
        
        # Calculate frame spacing
        pos_end = self.position
        self.frame_advance_steps = pos_end - pos_start
        
        log(f"Calibration complete:")
        log(f"  Frame 1 position: {pos_start}")
        log(f"  Frame 2 position: {pos_end}")
        log(f"  Frame spacing: {self.frame_advance_steps} steps")
        
        # Rough pixels per step (for movement calculations)
        # Assume ~800px between frame centers for 35mm
        self.pixels_per_step = 800.0 / self.frame_advance_steps if self.frame_advance_steps > 0 else 8.0
        log(f"  Approx: {self.pixels_per_step:.2f} px/step")
        
        stdscr.addstr(7, 0, f"Calibration complete!")
        stdscr.addstr(8, 0, f"Frame spacing: {self.frame_advance_steps} steps")
        stdscr.addstr(9, 0, f"Ratio: {self.pixels_per_step:.2f} px/step")
        stdscr.addstr(11, 0, "Press any key...")
        stdscr.refresh()
        stdscr.getch()
        
        self.save_state()
        return True
    
    def align_and_capture(self, stdscr):
        """
        Align frame and capture.
        Uses learned frame spacing for initial positioning.
        """
        log("\n=== ALIGN AND CAPTURE ===")
        
        if self.frame_advance_steps is None:
            self.status_msg = "Must calibrate first! Press C"
            log("ERROR: Not calibrated")
            return False
        
        # If this is not frame 1, advance to next frame
        if self.frame_count > 0:
            # Undershoot by 15% to avoid overshooting
            advance = int(self.frame_advance_steps * 0.85)
            log(f"Auto-advance {advance} steps (85% of {self.frame_advance_steps})")
            self.send(f'H{advance}')
            time.sleep(1.0)
        
        # Align
        for attempt in range(15):
            self.status_msg = f"Aligning... {attempt+1}/15"
            self.draw(stdscr)
            
            if not self.preview():
                log(f"Attempt {attempt+1}: preview failed")
                continue
            
            status, action, distance = detect_frame_state("/tmp/preview.jpg")
            log(f"Attempt {attempt+1}: {status}")
            
            if status == 'ALIGNED':
                log("ALIGNED!")
                break
            
            # Calculate steps from pixels
            steps = int(distance / self.pixels_per_step) if self.pixels_per_step else int(distance / 8)
            steps = max(5, min(steps, 100))  # Clamp to reasonable range
            
            log(f"  Action: {action}, distance={distance}px, steps={steps}")
            self.send(f'H{steps}')
            time.sleep(0.5)
        
        else:
            log("Alignment failed - timeout")
            self.status_msg = "Alignment failed"
            return False
        
        # Capture
        self.status_msg = "Capturing..."
        self.draw(stdscr)
        
        if self.capture_image():
            self.status_msg = f"✓ Frame {self.frame_count} captured"
            return True
        else:
            self.status_msg = "Capture failed"
            return False
    
    def capture_image(self):
        """Capture final image"""
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
        except:
            pass
        
        # Capture
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{ts}.cr3"
        filepath = os.path.join(self.roll_folder, filename)
        
        try:
            subprocess.run(
                ["gphoto2", "--capture-image-and-download", f"--filename={filepath}"],
                capture_output=True,
                timeout=20
            )
        except:
            subprocess.run(["killall", "-9", "gphoto2"], capture_output=True)
            return False
        
        if os.path.exists(filepath):
            self.frame_count += 1
            log(f"Captured: {filename}")
            self.save_state()
            return True
        
        return False
    
    def save_state(self):
        """Save state"""
        if self.state_file:
            state = {
                'frame_count': self.frame_count,
                'position': self.position,
                'pixels_per_step': self.pixels_per_step,
                'frame_advance_steps': self.frame_advance_steps
            }
            try:
                with open(self.state_file, 'w') as f:
                    json.dump(state, f, indent=2)
            except:
                pass
    
    def load_state(self):
        """Load state"""
        if self.state_file and os.path.exists(self.state_file):
            try:
                with open(self.state_file) as f:
                    state = json.load(f)
                self.frame_count = state.get('frame_count', 0)
                self.position = state.get('position', 0)
                self.pixels_per_step = state.get('pixels_per_step')
                self.frame_advance_steps = state.get('frame_advance_steps')
                log(f"State loaded: frame {self.frame_count}")
                return True
            except:
                return False
        return False
    
    def new_roll(self, stdscr):
        """Create new roll"""
        stdscr.clear()
        stdscr.addstr(0, 0, "=== NEW ROLL ===", curses.A_BOLD)
        stdscr.addstr(2, 0, "Roll name: ")
        stdscr.refresh()
        
        curses.echo()
        curses.curs_set(1)
        try:
            name = stdscr.getstr(2, 11, 40).decode('utf-8').strip()
        except:
            name = ""
        finally:
            curses.noecho()
            curses.curs_set(0)
        
        if not name:
            self.status_msg = "Cancelled"
            return False
        
        self.roll_name = name
        date_folder = datetime.now().strftime("%Y-%m-%d")
        self.roll_folder = os.path.join(os.path.expanduser("~/scans"), date_folder, self.roll_name)
        os.makedirs(self.roll_folder, exist_ok=True)
        self.state_file = os.path.join(self.roll_folder, '.scan_state.json')
        
        # Check existing
        if self.load_state():
            stdscr.clear()
            stdscr.addstr(0, 0, "Existing roll found", curses.A_BOLD)
            stdscr.addstr(2, 0, f"Frames captured: {self.frame_count}")
            stdscr.addstr(4, 0, "Resume (r) or Start Over (s)?")
            stdscr.refresh()
            
            while True:
                key = stdscr.getch()
                if key in [ord('r'), ord('R')]:
                    log(f"Resumed roll: {self.roll_name}")
                    return True
                elif key in [ord('s'), ord('S')]:
                    break
                elif key in [ord('q'), ord('Q')]:
                    return False
        
        # New roll
        self.frame_count = 0
        self.position = 0
        self.pixels_per_step = None
        self.frame_advance_steps = None
        
        stdscr.clear()
        stdscr.addstr(0, 0, f"Roll: {self.roll_name}", curses.A_BOLD)
        stdscr.addstr(2, 0, "Workflow:")
        stdscr.addstr(3, 0, "  1. Use arrows to align frame 1")
        stdscr.addstr(4, 0, "  2. Press C to calibrate")
        stdscr.addstr(5, 0, "  3. Press SPACE to capture each frame")
        stdscr.addstr(7, 0, "Press any key to continue...")
        stdscr.refresh()
        stdscr.getch()
        
        log(f"New roll: {self.roll_name}")
        self.status_msg = "Align frame 1, then press C"
        self.save_state()
        return True
    
    def draw(self, stdscr):
        """Draw UI"""
        stdscr.clear()
        stdscr.addstr(0, 0, "=== FILM SCANNER ===", curses.A_BOLD)
        
        stdscr.addstr(2, 0, f"Roll: {self.roll_name or 'None'}")
        stdscr.addstr(3, 0, f"Frames: {self.frame_count}")
        stdscr.addstr(4, 0, f"Position: {self.position} steps")
        
        # Calibration status
        if self.frame_advance_steps:
            stdscr.addstr(6, 0, f"✓ Calibrated: {self.frame_advance_steps} steps/frame", curses.A_BOLD)
        else:
            stdscr.addstr(6, 0, "⚠ NOT CALIBRATED - Press C", curses.A_REVERSE)
        
        stdscr.addstr(8, 0, "Controls:", curses.A_BOLD)
        stdscr.addstr(9, 0, "  ← →     Manual jog (fine)")
        stdscr.addstr(10, 0, "  Shift+← →   Manual jog (coarse)")
        stdscr.addstr(11, 0, "  C       Calibrate (after aligning frame 1)")
        stdscr.addstr(12, 0, "  SPACE   Align + Capture frame")
        stdscr.addstr(13, 0, "  P       Preview only")
        stdscr.addstr(14, 0, "  N       New roll")
        stdscr.addstr(15, 0, "  Q       Quit")
        
        stdscr.addstr(17, 0, f"Log: {LOG}")
        
        if self.status_msg:
            stdscr.addstr(19, 0, "Status:", curses.A_BOLD)
            stdscr.addstr(20, 0, self.status_msg[:75])
        
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
            stdscr.addstr(2, 0, "Check USB connection")
            stdscr.addstr(4, 0, "Press any key to exit...")
            stdscr.refresh()
            stdscr.getch()
            return
        
        # Initialize Arduino
        time.sleep(1)
        self.send('U')  # Unlock
        self.send('E')  # Enable motor
        time.sleep(0.3)
        
        self.status_msg = "Ready - Press N for new roll"
        
        # Main loop
        while True:
            self.draw(stdscr)
            key = stdscr.getch()
            
            if key in [ord('q'), ord('Q'), 27]:  # Q or ESC
                break
            
            elif key == curses.KEY_LEFT:
                self.send('b')
                self.status_msg = "Moved backward (fine)"
            
            elif key == curses.KEY_RIGHT:
                self.send('f')
                self.status_msg = "Moved forward (fine)"
            
            elif key == curses.KEY_SLEFT:  # Shift + Left
                self.send('B')
                self.status_msg = "Moved backward (coarse)"
            
            elif key == curses.KEY_SRIGHT:  # Shift + Right
                self.send('F')
                self.status_msg = "Moved forward (coarse)"
            
            elif key in [ord('c'), ord('C')]:
                if not self.roll_name:
                    self.status_msg = "Create roll first (N)"
                else:
                    self.calibrate(stdscr)
            
            elif key in [ord('p'), ord('P')]:
                if self.preview():
                    status, action, dist = detect_frame_state("/tmp/preview.jpg")
                    self.status_msg = f"Preview: {status}"
                else:
                    self.status_msg = "Preview failed"
            
            elif key == ord(' '):  # SPACE
                if not self.roll_name:
                    self.status_msg = "Create roll first (N)"
                elif not self.frame_advance_steps:
                    self.status_msg = "Calibrate first (C)"
                else:
                    self.align_and_capture(stdscr)
            
            elif key in [ord('n'), ord('N')]:
                self.new_roll(stdscr)
        
        # Cleanup
        if self.arduino:
            self.send('M')  # Disable motor
            self.arduino.close()
        
        log("Scanner stopped")


def main():
    try:
        scanner = FilmScanner()
        curses.wrapper(scanner.run)
    except KeyboardInterrupt:
        log("Interrupted by user")
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
