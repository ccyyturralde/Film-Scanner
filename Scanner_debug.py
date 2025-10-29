#!/usr/bin/env python3
"""
Film Scanner - DEBUG VERSION
Logs all detection decisions to /tmp/scanner_debug.log
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

DEBUG_LOG = "/tmp/scanner_debug.log"

def log_debug(msg):
    """Write to debug log with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    with open(DEBUG_LOG, 'a') as f:
        f.write(f"[{timestamp}] {msg}\n")
    print(msg)  # Also print to console

def detect_frame_gaps_debug(img_path):
    """
    Detection with extensive debug logging.
    Goal: MINIMIZE gap visibility, not center gaps!
    """
    log_debug(f"\n{'='*70}")
    log_debug(f"ANALYZING: {os.path.basename(img_path)}")
    
    img = cv2.imread(img_path)
    if img is None:
        log_debug("ERROR: Cannot read image")
        return {'status': 'ERROR', 'action': 'NONE', 'confidence': 0.0}
    
    h, w = img.shape[:2]
    log_debug(f"Image size: {w}x{h}")
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    y1, y2 = int(h * 0.3), int(h * 0.7)
    roi = gray[y1:y2, :]
    
    # Brightness profile
    brightness = np.mean(roi, axis=0)
    kernel_size = max(5, int(w * 0.005))
    kernel = np.ones(kernel_size) / kernel_size
    smoothed = np.convolve(brightness, kernel, mode='same')
    
    # Variance profile (gaps are uniform, content is textured)
    variance_profile = np.array([np.var(roi[:, max(0, i-2):min(w, i+3)]) 
                                  for i in range(w)])
    smoothed_variance = np.convolve(variance_profile, kernel, mode='same')
    
    # Detect bright AND uniform regions (true gaps)
    median_bright = np.median(smoothed)
    std_bright = np.std(smoothed)
    brightness_threshold = median_bright + 0.7 * std_bright
    variance_threshold = np.percentile(smoothed_variance, 25)
    
    log_debug(f"Brightness threshold: {brightness_threshold:.1f}")
    log_debug(f"Variance threshold: {variance_threshold:.1f}")
    
    gap_mask = (smoothed > brightness_threshold) & (smoothed_variance < variance_threshold)
    
    # Find gaps
    gaps = []
    in_gap = False
    gap_start = 0
    
    for i in range(len(gap_mask)):
        if gap_mask[i] and not in_gap:
            gap_start = i
            in_gap = True
        elif not gap_mask[i] and in_gap:
            gap_width = i - gap_start
            if 10 < gap_width < 250:
                gap_center = (gap_start + i) // 2
                gaps.append({
                    'center': gap_center,
                    'start': gap_start,
                    'end': i,
                    'width': gap_width,
                    'percent': (gap_center / w) * 100
                })
            in_gap = False
    
    log_debug(f"Found {len(gaps)} total gaps")
    for i, g in enumerate(gaps):
        log_debug(f"  Gap {i+1}: {g['center']}px ({g['percent']:.1f}%), width={g['width']}px")
    
    # Classify gaps
    left_gaps = [g for g in gaps if g['percent'] < 50]
    right_gaps = [g for g in gaps if g['percent'] >= 50]
    
    left_gap = max(left_gaps, key=lambda g: g['width']) if left_gaps else None
    right_gap = max(right_gaps, key=lambda g: g['width']) if right_gaps else None
    
    if left_gap:
        log_debug(f"LEFT gap: {left_gap['center']}px ({left_gap['percent']:.1f}%), {left_gap['width']}px wide")
    else:
        log_debug("LEFT gap: None")
    
    if right_gap:
        log_debug(f"RIGHT gap: {right_gap['center']}px ({right_gap['percent']:.1f}%), {right_gap['width']}px wide")
    else:
        log_debug("RIGHT gap: None")
    
    # CRITICAL: Alignment logic
    # Goal: Both gaps should be small (<40px) and at edges (<15% or >85%)
    # If gaps are large or centered = NOT ALIGNED
    
    result = {}
    
    # Case 1: Both gaps visible
    if left_gap and right_gap:
        frame_width = right_gap['center'] - left_gap['center']
        frame_center_percent = ((left_gap['center'] + right_gap['center']) / 2) / w * 100
        
        log_debug(f"Frame width: {frame_width}px, center at {frame_center_percent:.1f}%")
        
        # Check if gaps are small and at edges
        left_at_edge = left_gap['percent'] < 15
        right_at_edge = right_gap['percent'] > 85
        gaps_small = left_gap['width'] < 40 and right_gap['width'] < 40
        
        log_debug(f"Left at edge: {left_at_edge}, Right at edge: {right_at_edge}, Gaps small: {gaps_small}")
        
        if left_at_edge and right_at_edge and gaps_small:
            result = {
                'status': 'ALIGNED',
                'action': 'CAPTURE',
                'movement': 0,
                'message': 'Perfect alignment - gaps minimal'
            }
        elif frame_center_percent < 40:
            # Frame too far left - advance
            distance = int((50 - frame_center_percent) / 100 * w)
            result = {
                'status': 'FRAME_LEFT',
                'action': 'ADVANCE_MEDIUM',
                'movement': distance,
                'message': f'Frame left, advance {distance}px'
            }
        elif frame_center_percent > 60:
            # Frame too far right - backup
            distance = int((frame_center_percent - 50) / 100 * w)
            result = {
                'status': 'FRAME_RIGHT',
                'action': 'BACKUP_MEDIUM',
                'movement': distance,
                'message': f'Frame right, backup {distance}px'
            }
        else:
            # Gaps too large - fine tune toward smaller gap
            if left_gap['width'] > right_gap['width']:
                result = {
                    'status': 'GAPS_LARGE',
                    'action': 'ADVANCE_FINE',
                    'movement': 30,
                    'message': f'Left gap {left_gap["width"]}px too large'
                }
            else:
                result = {
                    'status': 'GAPS_LARGE',
                    'action': 'BACKUP_FINE',
                    'movement': 30,
                    'message': f'Right gap {right_gap["width"]}px too large'
                }
    
    # Case 2: Only right gap (frame entering from left)
    elif right_gap and not left_gap:
        log_debug(f"Only right gap at {right_gap['percent']:.1f}%")
        
        if right_gap['percent'] > 70:
            # Gap far right - frame mostly off-screen left
            distance = int((right_gap['percent'] - 50) / 100 * w)
            result = {
                'status': 'ENTERING_LEFT',
                'action': 'BACKUP_MEDIUM',
                'movement': distance,
                'message': f'Frame entering left, backup {distance}px'
            }
        else:
            # Gap in middle - multiple frames or transitioning
            result = {
                'status': 'TRANSITION',
                'action': 'ADVANCE_COARSE',
                'movement': int(w * 0.4),
                'message': 'Advance to next frame'
            }
    
    # Case 3: Only left gap (frame exiting right)
    elif left_gap and not right_gap:
        log_debug(f"Only left gap at {left_gap['percent']:.1f}%")
        
        if left_gap['percent'] < 30:
            # Gap far left - advance to next frame
            distance = int(w * 0.5)
            result = {
                'status': 'EXITING_RIGHT',
                'action': 'ADVANCE_COARSE',
                'movement': distance,
                'message': f'Frame exiting, advance {distance}px to next'
            }
        else:
            result = {
                'status': 'UNCERTAIN',
                'action': 'ADVANCE_MEDIUM',
                'movement': int(w * 0.3),
                'message': 'Uncertain position, advance'
            }
    
    # Case 4: No gaps detected
    else:
        log_debug("No gaps detected - advance to find frame")
        result = {
            'status': 'NO_GAPS',
            'action': 'ADVANCE_COARSE',
            'movement': int(w * 0.4),
            'message': 'No gaps found, advance'
        }
    
    result['confidence'] = 0.7 if (left_gap or right_gap) else 0.3
    result['left_gap'] = left_gap
    result['right_gap'] = right_gap
    
    log_debug(f"DECISION: {result['status']} -> {result['action']}")
    log_debug(f"MESSAGE: {result['message']}")
    log_debug(f"Confidence: {result['confidence']:.2f}")
    
    return result


class FilmScanner:
    def __init__(self):
        self.arduino = None
        self.roll_name = ""
        self.roll_folder = ""
        self.frame_count = 0
        self.status_msg = "Ready"
        
        # IMPORTANT: Arduino commands are in FULL STEPS
        # A4988 driver handles microstepping internally
        self.fine_step = 8      # Full steps
        self.coarse_step = 64   # Full steps
        self.steps_per_frame = 1200  # Full steps (will calibrate)
        
        self.position_steps = 0  # Track in full steps
        self.is_large_step = False
        self.mode = 'smart'
        
        # Calibration (in full steps)
        self.pixels_per_step = 2.0  # Pixels per FULL STEP (will calibrate)
        self.last_frame_advance = None  # Full steps between frames
        
        self.state_file = None
        
        log_debug("Scanner initialized - Arduino uses FULL STEPS")
        log_debug(f"Scanner initialized with {self.microsteps}x microstepping")
        log_debug(f"Total microsteps/rev: {self.total_microsteps_per_rev}")
    
    def find_arduino(self, stdscr=None):
        """Find Arduino"""
        ports = list(serial.tools.list_ports.comports())
        
        pi_ports = ['/dev/ttyS0', '/dev/ttyAMA0', '/dev/serial0', '/dev/ttyUSB0', '/dev/ttyACM0']
        for pi_port in pi_ports:
            if os.path.exists(pi_port):
                class SimplePort:
                    def __init__(self, device):
                        self.device = device
                ports.append(SimplePort(pi_port))
        
        for port in ports:
            device = port.device if hasattr(port, 'device') else str(port)
            try:
                ser = serial.Serial(device, 115200, timeout=3, exclusive=False)
                time.sleep(2.5)
                ser.reset_input_buffer()
                ser.write(b'?\n')
                time.sleep(0.8)
                
                if ser.in_waiting:
                    response = ser.read_all().decode('utf-8', errors='ignore')
                    if any(word in response for word in ['READY', 'STATUS', 'NEMA', 'Position']):
                        log_debug(f"Arduino found on {device}")
                        return ser
                ser.close()
            except:
                continue
        
        return None
    
    def send_command(self, cmd):
        """Send command with logging"""
        if not self.arduino or not self.arduino.is_open:
            return
        
        try:
            log_debug(f"CMD: {cmd}")
            self.arduino.write(f"{cmd}\n".encode())
            time.sleep(0.05)
            
            # Track position
            if cmd == 'f':
                self.position_steps += self.fine_step
            elif cmd == 'b':
                self.position_steps -= self.fine_step
            elif cmd == 'F':
                self.position_steps += self.coarse_step
            elif cmd == 'B':
                self.position_steps -= self.coarse_step
            elif cmd.startswith('H'):
                steps = int(cmd[1:])
                self.position_steps += steps
                log_debug(f"Advanced {steps} microsteps")
            elif cmd.startswith('h'):
                steps = int(cmd[1:])
                self.position_steps -= steps
                log_debug(f"Backed up {steps} microsteps")
            elif cmd == 'Z':
                self.position_steps = 0
        except Exception as e:
            log_debug(f"CMD ERROR: {e}")
    
    def capture_preview(self, output_path="/tmp/preview.jpg"):
        """Capture preview"""
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
            
            # Handle thumb_ prefix
            if not os.path.exists(output_path):
                thumb_path = os.path.join(os.path.dirname(output_path), 
                                         "thumb_" + os.path.basename(output_path))
                if os.path.exists(thumb_path):
                    os.rename(thumb_path, output_path)
            
            success = os.path.exists(output_path)
            log_debug(f"Preview captured: {success}")
            return success
        except Exception as e:
            log_debug(f"Preview error: {e}")
            return False
    
    def smart_align_step(self, stdscr):
        """Single alignment step with debug logging"""
        if not HAS_CV2:
            return False
        
        if not self.capture_preview():
            log_debug("Preview capture failed")
            return False
        
        result = detect_frame_gaps_debug("/tmp/preview.jpg")
        
        self.status_msg = result.get('message', result.get('action'))
        self.draw_screen(stdscr)
        
        if result['action'] in ['CAPTURE']:
            log_debug("ALIGNED - ready to capture")
            return True
        
        # Convert pixels to full steps
        if result.get('movement'):
            steps = int(result['movement'] / self.pixels_per_step)
            
            # SAFETY: Limit movement before calibration
            if self.last_frame_advance is None:  # Not calibrated
                log_debug(f"WARNING: Not calibrated, limiting movement")
                steps = min(steps, 100)  # Max 100 steps (~1/2 rotation)
            
            # SAFETY: Absolute maximum
            steps = min(steps, 300)  # Never more than 300 steps (~1.5 rotations)
            
            if result['action'] in ['ADVANCE_COARSE', 'ADVANCE_MEDIUM', 'ADVANCE_FINE']:
                cmd = f'H{steps}'
            elif result['action'] in ['BACKUP_MEDIUM', 'BACKUP_FINE']:
                cmd = f'h{steps}'
            else:
                cmd = 'F'  # Default
            
            log_debug(f"Executing: {cmd} ({result['movement']}px -> {steps} steps)")
            self.send_command(cmd)
            time.sleep(0.5)
        
        return False
    
    def calibrate_frame_spacing(self, stdscr):
        """Calibrate pixels per step"""
        if not HAS_CV2:
            return False
        
        log_debug("\n" + "="*70)
        log_debug("STARTING CALIBRATION")
        
        stdscr.clear()
        stdscr.addstr(0, 0, "=== CALIBRATION ===", curses.A_BOLD)
        stdscr.addstr(2, 0, "Capturing initial position...")
        stdscr.refresh()
        
        if not self.capture_preview():
            log_debug("Calibration failed: no preview")
            return False
        
        result1 = detect_frame_gaps_debug("/tmp/preview.jpg")
        
        if not result1.get('right_gap'):
            log_debug("Calibration failed: no gaps detected")
            stdscr.addstr(4, 0, "Could not detect frame - adjust position")
            stdscr.refresh()
            time.sleep(2)
            return False
        
        initial_center = result1['right_gap']['center']
        initial_steps = self.position_steps
        
        stdscr.addstr(4, 0, f"Initial gap at: {initial_center}px")
        stdscr.addstr(6, 0, "Advancing one frame...")
        stdscr.refresh()
        
        # Advance approximately 1 frame
        # Start conservative - about 100 steps
        advance_steps = 100
        log_debug(f"Calibration advance: {advance_steps} steps")
        
        self.send_command(f'H{advance_steps}')
        time.sleep(1.5)
        
        if not self.capture_preview():
            return False
        
        result2 = detect_frame_gaps_debug("/tmp/preview.jpg")
        
        if not result2.get('right_gap'):
            log_debug("Calibration: advancing more...")
            # Try advancing more
            self.send_command('H50')
            time.sleep(1)
            if not self.capture_preview():
                return False
            result2 = detect_frame_gaps_debug("/tmp/preview.jpg")
        
        if not result2.get('right_gap'):
            log_debug("Calibration failed: second gap not found")
            return False
        
        new_center = result2['right_gap']['center']
        steps_moved = self.position_steps - initial_steps
        pixels_moved = abs(new_center - initial_center)
        
        if steps_moved > 0 and pixels_moved > 0:
            self.pixels_per_step = pixels_moved / steps_moved
            self.last_frame_advance = steps_moved
            
            log_debug(f"Calibration complete:")
            log_debug(f"  Moved {pixels_moved}px in {steps_moved} steps")
            log_debug(f"  Ratio: {self.pixels_per_step:.3f} px/step")
            log_debug(f"  Frame advance: {steps_moved} steps")
        
        stdscr.addstr(8, 0, f"Moved: {pixels_moved}px in {steps_moved} steps")
        stdscr.addstr(9, 0, f"Ratio: {self.pixels_per_step:.3f} px/step")
        stdscr.addstr(11, 0, "✓ Calibration complete!")
        stdscr.addstr(13, 0, "Press any key...")
        stdscr.refresh()
        stdscr.getch()
        
        self.save_state()
        return True
    
    def capture_image(self, stdscr):
        """Capture RAW image"""
        subprocess.run(["killall", "gphoto2"], capture_output=True, timeout=1)
        time.sleep(0.3)
        
        try:
            subprocess.run(["gphoto2", "--set-config", "autofocus=1"], 
                         capture_output=True, timeout=5)
            time.sleep(1.5)
        except:
            pass
        
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{timestamp}.cr3"
        filepath = os.path.join(self.roll_folder, filename)
        
        try:
            subprocess.run(
                ["gphoto2", "--capture-image-and-download", f"--filename={filepath}"],
                capture_output=True, timeout=20
            )
        except:
            subprocess.run(["killall", "-9", "gphoto2"], capture_output=True)
            return False
        
        if os.path.exists(filepath):
            self.frame_count += 1
            log_debug(f"Captured frame {self.frame_count}: {filename}")
            self.save_state()
            return True
        return False
    
    def save_state(self):
        """Save state"""
        if self.state_file:
            state = {
                'roll_name': self.roll_name,
                'frame_count': self.frame_count,
                'position_steps': self.position_steps,
                'pixels_per_step': self.pixels_per_step,
                'last_frame_advance': self.last_frame_advance
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
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                self.frame_count = state.get('frame_count', 0)
                self.position_steps = state.get('position_steps', 0)
                self.pixels_per_step = state.get('pixels_per_step', 2.0)
                self.last_frame_advance = state.get('last_frame_advance')
                log_debug(f"Loaded state: frame {self.frame_count}, pos {self.position_steps} steps")
                return True
            except:
                return False
        return False
    
    def draw_screen(self, stdscr):
        """Draw UI"""
        stdscr.clear()
        stdscr.addstr(0, 0, "=== FILM SCANNER DEBUG ===", curses.A_BOLD)
        stdscr.addstr(2, 0, f"Roll: {self.roll_name if self.roll_name else 'None'}")
        stdscr.addstr(3, 0, f"Frames: {self.frame_count}")
        stdscr.addstr(4, 0, f"Position: {self.position_steps} steps")
        
        # Calibration status
        if self.last_frame_advance is not None:
            stdscr.addstr(5, 0, f"Calibrated: YES ({self.pixels_per_step:.3f} px/step)", curses.A_BOLD)
            stdscr.addstr(6, 0, f"Frame spacing: {self.last_frame_advance} steps")
        else:
            stdscr.addstr(5, 0, "Calibrated: NO - PRESS C TO CALIBRATE", curses.A_REVERSE)
        
        stdscr.addstr(8, 0, "Controls:", curses.A_BOLD)
        stdscr.addstr(9, 0, "  ← / →   Manual jog (G = toggle size)")
        stdscr.addstr(10, 0, "  C       Calibrate (REQUIRED FIRST)")
        stdscr.addstr(11, 0, "  A       Auto-align only")
        stdscr.addstr(12, 0, "  SPACE   Align + Capture + Advance")
        stdscr.addstr(13, 0, "  N       New roll")
        stdscr.addstr(14, 0, "  Q       Quit")
        stdscr.addstr(15, 0, f"  Debug:  {DEBUG_LOG}")
        
        if self.status_msg:
            stdscr.addstr(17, 0, "Status:", curses.A_BOLD)
            stdscr.addstr(18, 0, self.status_msg[:75])
        
        stdscr.refresh()
    
    def new_roll(self, stdscr):
        """Create new roll"""
        stdscr.clear()
        stdscr.addstr(0, 0, "=== NEW ROLL ===", curses.A_BOLD)
        stdscr.addstr(2, 0, "Roll name: ")
        stdscr.refresh()
        
        curses.echo()
        curses.curs_set(1)
        
        try:
            roll_input = stdscr.getstr(2, 11, 40).decode('utf-8').strip()
        except:
            roll_input = ""
        finally:
            curses.noecho()
            curses.curs_set(0)
        
        if not roll_input:
            self.status_msg = "Cancelled"
            return False
        
        self.roll_name = roll_input
        date_folder = datetime.now().strftime("%Y-%m-%d")
        self.roll_folder = os.path.join(os.path.expanduser("~/scans"), 
                                       date_folder, self.roll_name)
        os.makedirs(self.roll_folder, exist_ok=True)
        self.state_file = os.path.join(self.roll_folder, '.scan_state.json')
        
        # Check for existing
        if self.load_state():
            stdscr.clear()
            stdscr.addstr(0, 0, "Found existing roll!", curses.A_BOLD)
            stdscr.addstr(2, 0, f"Frames: {self.frame_count}")
            stdscr.addstr(3, 0, f"Position: {self.position_steps}")
            stdscr.addstr(5, 0, "Continue? (c) or Start Over (s) or Cancel (q)")
            stdscr.refresh()
            
            while True:
                key = stdscr.getch()
                if key in [ord('c'), ord('C')]:
                    log_debug(f"Resumed roll: {self.roll_name} at frame {self.frame_count}")
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
        self.position_steps = 0
        self.pixels_per_step = 2.0
        self.last_frame_advance = None
        
        stdscr.clear()
        stdscr.addstr(0, 0, f"Roll: {self.roll_name}", curses.A_BOLD)
        stdscr.addstr(2, 0, "Workflow:")
        stdscr.addstr(3, 0, "  1. Use arrow keys to position first frame")
        stdscr.addstr(4, 0, "  2. Press C to calibrate (REQUIRED)")
        stdscr.addstr(5, 0, "  3. Press SPACE to align + capture")
        stdscr.addstr(6, 0, "  4. Repeat for each frame")
        stdscr.addstr(8, 0, "Press any key to continue...")
        stdscr.refresh()
        stdscr.getch()
        
        log_debug(f"New roll created: {self.roll_name}")
        self.status_msg = "Position first frame, then press C to calibrate"
        self.save_state()
        return True
    
    def run(self, stdscr):
        """Main loop"""
        curses.curs_set(0)
        stdscr.nodelay(False)
        
        # Clear debug log
        open(DEBUG_LOG, 'w').write(f"=== Scanner Debug Log ===\n{datetime.now()}\n\n")
        log_debug("Scanner starting...")
        
        self.arduino = self.find_arduino(stdscr)
        if not self.arduino:
            stdscr.clear()
            stdscr.addstr(0, 0, "ERROR: Arduino not found!")
            stdscr.refresh()
            stdscr.getch()
            return
        
        # Initialize
        self.send_command(f'S{self.steps_per_frame}')
        self.send_command(f'm{self.fine_step}')
        self.send_command(f'l{self.coarse_step}')
        self.send_command('U')
        self.send_command('E')
        time.sleep(0.5)
        
        self.status_msg = "Ready - Press N for new roll"
        
        # Main loop
        while True:
            self.draw_screen(stdscr)
            key = stdscr.getch()
            
            if key in [ord('q'), ord('Q'), 27]:
                break
            
            elif key == curses.KEY_LEFT:
                self.send_command('B' if self.is_large_step else 'b')
            
            elif key == curses.KEY_RIGHT:
                self.send_command('F' if self.is_large_step else 'f')
            
            elif key in [ord('g'), ord('G')]:
                self.is_large_step = not self.is_large_step
            
            elif key in [ord('c'), ord('C')]:
                if self.roll_name:
                    self.calibrate_frame_spacing(stdscr)
                else:
                    self.status_msg = "Create roll first (N)"
            
            elif key in [ord('a'), ord('A')]:
                if not self.roll_name:
                    self.status_msg = "Create roll first (N)"
                    continue
                
                if not HAS_CV2:
                    self.status_msg = "OpenCV not available"
                    continue
                
                # CHECK: Should calibrate first (but allow without for testing)
                if self.last_frame_advance is None:
                    log_debug("WARNING: Aligning without calibration - movements may be wrong")
                    self.status_msg = "WARNING: Not calibrated!"
                    stdscr.addstr(18, 0, ">>> NOT CALIBRATED - movements may be incorrect <<<", curses.A_BOLD)
                    stdscr.refresh()
                    time.sleep(1)
                
                log_debug("\n=== ALIGNMENT START ===")
                for attempt in range(15):
                    log_debug(f"Attempt {attempt + 1}/15")
                    if self.smart_align_step(stdscr):
                        log_debug("ALIGNED!")
                        break
                    time.sleep(0.3)
                else:
                    log_debug("Alignment timeout")
                    self.status_msg = "Alignment failed"
            
            elif key == ord(' '):
                if not self.roll_name:
                    self.status_msg = "Create roll first (N)"
                    continue
                
                if not HAS_CV2:
                    self.status_msg = "OpenCV not available"
                    continue
                
                # CHECK: Must calibrate first
                if self.last_frame_advance is None:
                    self.status_msg = "CALIBRATE FIRST! Press C to calibrate"
                    log_debug("Attempted capture without calibration")
                    stdscr.addstr(18, 0, ">>> PRESS C TO CALIBRATE FIRST <<<", curses.A_BOLD | curses.A_REVERSE)
                    stdscr.refresh()
                    time.sleep(1.5)
                    continue
                
                log_debug("\n=== SMART CAPTURE START ===")
                
                # Align
                aligned = False
                for attempt in range(15):
                    log_debug(f"Align attempt {attempt + 1}/15")
                    if self.smart_align_step(stdscr):
                        aligned = True
                        break
                    time.sleep(0.3)
                
                if aligned:
                    # Capture
                    if self.capture_image(stdscr):
                        self.status_msg = f"✓ Frame {self.frame_count}"
                        
                        # Auto-advance to next frame
                        log_debug("Auto-advancing to next frame")
                        advance = int(self.last_frame_advance * 0.80)
                        log_debug(f"Advancing {advance} steps (80% of {self.last_frame_advance})")
                        self.send_command(f'H{advance}')
                        time.sleep(0.8)
                        log_debug(f"Ready for frame {self.frame_count + 1}")
                else:
                    log_debug("Capture aborted - alignment failed")
                    self.status_msg = "Alignment failed"
            
            elif key in [ord('n'), ord('N')]:
                self.new_roll(stdscr)
        
        # Cleanup
        if self.arduino:
            self.send_command('M')
            self.arduino.close()
        
        log_debug("Scanner stopped")


def main():
    try:
        scanner = FilmScanner()
        curses.wrapper(scanner.run)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
