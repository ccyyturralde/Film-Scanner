#!/usr/bin/env python3
"""
Film Scanner - HYBRID APPROACH
Fixed mechanical advance + CV verification

Philosophy:
- 35mm film frames are consistent distances apart
- Use FIXED advance distance (user-tunable)
- Computer vision only VERIFIES we hit a frame (not FINDS it)
- Simple, reliable, professional approach
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

LOG = "/tmp/scanner.log"

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    with open(LOG, 'a') as f:
        f.write(f"[{ts}] {msg}\n")

def check_has_content(img_path):
    """
    Simple check: Is there FRAME CONTENT visible?
    Returns: True if we see texture/detail (frame present)
             False if mostly uniform (in gap between frames)
    """
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return False
    
    h, w = img.shape
    
    # Look at center region
    roi = img[int(h*0.3):int(h*0.7), int(w*0.3):int(w*0.7)]
    
    # Calculate texture (variance and edge strength)
    variance = np.var(roi)
    edges = cv2.Canny(roi, 50, 150)
    edge_density = np.sum(edges > 0) / edges.size
    
    log(f"Content check: variance={variance:.1f}, edges={edge_density:.3f}")
    
    # If we see texture and edges, there's content
    has_content = variance > 200 and edge_density > 0.01
    
    log(f"Has content: {has_content}")
    return has_content


class FilmScanner:
    def __init__(self):
        self.arduino = None
        self.roll_name = ""
        self.roll_folder = ""
        self.frame_count = 0
        self.status = "Ready"
        
        # SIMPLE: Fixed advance distance (user-tunable)
        # For 35mm film, frame spacing is consistent
        # User will calibrate this once
        self.frame_advance = 120  # steps (adjust with +/- keys)
        
        self.fine_step = 8
        self.coarse_step = 64
        
        self.position = 0
        self.state_file = None
        
        open(LOG, 'w').write(f"=== Scanner Started ===\n{datetime.now()}\n\n")
        log(f"Frame advance: {self.frame_advance} steps")
    
    def find_arduino(self):
        """Find Arduino"""
        ports = list(serial.tools.list_ports.comports())
        for p in ['/dev/ttyACM0', '/dev/ttyUSB0', '/dev/serial0']:
            if os.path.exists(p):
                class Port:
                    def __init__(self, d): self.device = d
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
                    if any(x in resp for x in ['READY', 'STATUS', 'Position']):
                        log(f"Arduino: {device}")
                        return ser
                ser.close()
            except:
                continue
        return None
    
    def send(self, cmd):
        """Send command"""
        if not self.arduino:
            return
        try:
            self.arduino.write(f"{cmd}\n".encode())
            log(f">>> {cmd}")
            time.sleep(0.05)
            
            if cmd == 'f': self.position += self.fine_step
            elif cmd == 'b': self.position -= self.fine_step
            elif cmd == 'F': self.position += self.coarse_step
            elif cmd == 'B': self.position -= self.coarse_step
            elif cmd.startswith('H'): self.position += int(cmd[1:])
            elif cmd.startswith('h'): self.position -= int(cmd[1:])
            elif cmd == 'Z': self.position = 0
        except Exception as e:
            log(f"Error: {e}")
    
    def preview(self):
        """Capture preview"""
        try:
            path = "/tmp/preview.jpg"
            if os.path.exists(path):
                os.remove(path)
            
            subprocess.run(["killall", "gphoto2"], capture_output=True, timeout=1)
            time.sleep(0.2)
            
            subprocess.run(
                ["gphoto2", "--capture-preview", f"--filename={path}"],
                capture_output=True, timeout=10
            )
            
            # Handle thumb_ prefix
            if not os.path.exists(path):
                thumb = f"/tmp/thumb_{os.path.basename(path)}"
                if os.path.exists(thumb):
                    os.rename(thumb, path)
            
            time.sleep(0.2)
            return os.path.exists(path)
        except:
            return False
    
    def capture_frame(self, stdscr):
        """
        Capture current frame.
        Simple workflow:
        1. If not first frame, advance fixed distance
        2. Verify we see content (not in gap)
        3. Small adjustments if needed
        4. Capture
        """
        log(f"\n=== CAPTURE FRAME {self.frame_count + 1} ===")
        
        # Advance to next frame (except first frame)
        if self.frame_count > 0:
            log(f"Advancing {self.frame_advance} steps")
            self.status = f"Advancing {self.frame_advance} steps..."
            self.draw(stdscr)
            
            self.send(f'H{self.frame_advance}')
            time.sleep(1.0)
        
        # Verify we're on a frame (not in gap)
        for attempt in range(5):
            self.status = f"Verifying position... {attempt+1}/5"
            self.draw(stdscr)
            
            if not self.preview():
                log(f"Attempt {attempt+1}: preview failed")
                continue
            
            if HAS_CV2:
                has_content = check_has_content("/tmp/preview.jpg")
            else:
                # Without CV, assume good
                has_content = True
            
            if has_content:
                log(f"Attempt {attempt+1}: Content detected, capturing")
                break
            else:
                # In gap - advance a bit more
                log(f"Attempt {attempt+1}: In gap, advancing 10 steps")
                self.send('H10')
                time.sleep(0.4)
        else:
            log("Verification failed - no content found")
            self.status = "No frame found - adjust manually"
            return False
        
        # Capture final image
        self.status = "Capturing..."
        self.draw(stdscr)
        
        if self.capture_image():
            self.status = f"✓ Frame {self.frame_count} captured"
            return True
        else:
            self.status = "Capture failed"
            return False
    
    def capture_image(self):
        """Capture final image"""
        subprocess.run(["killall", "gphoto2"], capture_output=True, timeout=1)
        time.sleep(0.3)
        
        # Autofocus
        try:
            subprocess.run(
                ["gphoto2", "--set-config", "autofocus=1"],
                capture_output=True, timeout=5
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
                capture_output=True, timeout=20
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
    
    def calibrate(self, stdscr):
        """
        Simple calibration:
        1. User positions frame 1 manually
        2. System advances to frame 2
        3. User confirms it's good
        4. System records the distance
        """
        log("\n=== CALIBRATION ===")
        
        stdscr.clear()
        stdscr.addstr(0, 0, "=== CALIBRATION ===", curses.A_BOLD)
        stdscr.addstr(2, 0, "Frame 1 should be positioned (press any key)")
        stdscr.refresh()
        stdscr.getch()
        
        # Mark starting position
        start_pos = self.position
        log(f"Frame 1 position: {start_pos}")
        
        stdscr.clear()
        stdscr.addstr(0, 0, "Advancing to frame 2...", curses.A_BOLD)
        stdscr.addstr(2, 0, f"Current advance: {self.frame_advance} steps")
        stdscr.addstr(3, 0, "Advancing...")
        stdscr.refresh()
        
        # Advance
        self.send(f'H{self.frame_advance}')
        time.sleep(1.2)
        
        stdscr.addstr(5, 0, "Is frame 2 visible?")
        stdscr.addstr(6, 0, "  y - Yes, good")
        stdscr.addstr(7, 0, "  + - Need more advance")
        stdscr.addstr(8, 0, "  - - Need less advance")
        stdscr.refresh()
        
        # Interactive adjustment
        while True:
            key = stdscr.getch()
            
            if key in [ord('y'), ord('Y')]:
                # Good - save this distance
                end_pos = self.position
                self.frame_advance = end_pos - start_pos
                log(f"Calibrated: {self.frame_advance} steps per frame")
                
                stdscr.clear()
                stdscr.addstr(0, 0, "✓ Calibration complete!", curses.A_BOLD)
                stdscr.addstr(2, 0, f"Frame spacing: {self.frame_advance} steps")
                stdscr.addstr(4, 0, "Press any key...")
                stdscr.refresh()
                stdscr.getch()
                
                self.save_state()
                return True
            
            elif key in [ord('+'), ord('=')]:
                # Need more
                stdscr.addstr(10, 0, "Advancing 10 steps...")
                stdscr.refresh()
                self.send('H10')
                time.sleep(0.5)
                stdscr.addstr(10, 0, "                      ")
                stdscr.refresh()
            
            elif key in [ord('-'), ord('_')]:
                # Need less - back up and try again
                stdscr.clear()
                stdscr.addstr(0, 0, "Reduce advance by 10 steps?")
                stdscr.addstr(1, 0, "(Note: Will need to recalibrate)")
                stdscr.addstr(2, 0, "y/n?")
                stdscr.refresh()
                
                k2 = stdscr.getch()
                if k2 in [ord('y'), ord('Y')]:
                    self.frame_advance -= 10
                    stdscr.clear()
                    stdscr.addstr(0, 0, "Start calibration over with new advance")
                    stdscr.addstr(1, 0, "Press any key...")
                    stdscr.refresh()
                    stdscr.getch()
                    return False
            
            elif key in [ord('q'), ord('Q')]:
                return False
    
    def save_state(self):
        if self.state_file:
            state = {
                'frame_count': self.frame_count,
                'position': self.position,
                'frame_advance': self.frame_advance
            }
            try:
                with open(self.state_file, 'w') as f:
                    json.dump(state, f, indent=2)
            except:
                pass
    
    def load_state(self):
        if self.state_file and os.path.exists(self.state_file):
            try:
                with open(self.state_file) as f:
                    state = json.load(f)
                self.frame_count = state.get('frame_count', 0)
                self.position = state.get('position', 0)
                self.frame_advance = state.get('frame_advance', 120)
                return True
            except:
                return False
        return False
    
    def new_roll(self, stdscr):
        """Create new roll"""
        stdscr.clear()
        stdscr.addstr(0, 0, "Roll name: ")
        stdscr.refresh()
        
        curses.echo()
        curses.curs_set(1)
        try:
            name = stdscr.getstr(0, 11, 40).decode('utf-8').strip()
        except:
            name = ""
        finally:
            curses.noecho()
            curses.curs_set(0)
        
        if not name:
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
            stdscr.addstr(2, 0, f"Frames: {self.frame_count}")
            stdscr.addstr(3, 0, f"Frame advance: {self.frame_advance} steps")
            stdscr.addstr(5, 0, "Resume (r) or Start Over (s)?")
            stdscr.refresh()
            
            while True:
                key = stdscr.getch()
                if key in [ord('r'), ord('R')]:
                    log(f"Resumed: {self.roll_name}")
                    return True
                elif key in [ord('s'), ord('S')]:
                    break
                elif key in [ord('q'), ord('Q')]:
                    return False
        
        # New roll
        self.frame_count = 0
        self.position = 0
        
        stdscr.clear()
        stdscr.addstr(0, 0, f"Roll: {self.roll_name}", curses.A_BOLD)
        stdscr.addstr(2, 0, "SIMPLE WORKFLOW:")
        stdscr.addstr(3, 0, "  1. Insert film, position frame 1 with arrows")
        stdscr.addstr(4, 0, "  2. Press C to calibrate advance distance")
        stdscr.addstr(5, 0, "  3. Press SPACE to capture each frame")
        stdscr.addstr(6, 0, "  4. Use +/- to adjust frame_advance if needed")
        stdscr.addstr(8, 0, "Press any key...")
        stdscr.refresh()
        stdscr.getch()
        
        log(f"New roll: {self.roll_name}")
        self.status = "Position frame 1, then press C"
        self.save_state()
        return True
    
    def draw(self, stdscr):
        """Draw UI"""
        stdscr.clear()
        stdscr.addstr(0, 0, "=== FILM SCANNER (HYBRID) ===", curses.A_BOLD)
        
        stdscr.addstr(2, 0, f"Roll: {self.roll_name or 'None'}")
        stdscr.addstr(3, 0, f"Frames captured: {self.frame_count}")
        stdscr.addstr(4, 0, f"Position: {self.position} steps")
        stdscr.addstr(5, 0, f"Frame advance: {self.frame_advance} steps")
        
        stdscr.addstr(7, 0, "Controls:", curses.A_BOLD)
        stdscr.addstr(8, 0, "  ← →     Manual jog (fine)")
        stdscr.addstr(9, 0, "  Shift+← →   Coarse jog")
        stdscr.addstr(10, 0, "  + -     Adjust frame_advance")
        stdscr.addstr(11, 0, "  C       Calibrate (position frame 1 first)")
        stdscr.addstr(12, 0, "  SPACE   Capture frame (auto-advance)")
        stdscr.addstr(13, 0, "  P       Preview")
        stdscr.addstr(14, 0, "  N       New roll")
        stdscr.addstr(15, 0, "  Q       Quit")
        
        stdscr.addstr(17, 0, f"Log: {LOG}")
        
        if self.status:
            stdscr.addstr(19, 0, "Status:", curses.A_BOLD)
            stdscr.addstr(20, 0, self.status[:75])
        
        stdscr.refresh()
    
    def run(self, stdscr):
        """Main loop"""
        curses.curs_set(0)
        stdscr.nodelay(False)
        
        # Find Arduino
        self.arduino = self.find_arduino()
        if not self.arduino:
            stdscr.clear()
            stdscr.addstr(0, 0, "ERROR: Arduino not found!")
            stdscr.addstr(2, 0, "Press any key...")
            stdscr.refresh()
            stdscr.getch()
            return
        
        # Init
        time.sleep(1)
        self.send('U')
        self.send('E')
        time.sleep(0.3)
        
        self.status = "Ready - Press N for new roll"
        
        # Main loop
        while True:
            self.draw(stdscr)
            key = stdscr.getch()
            
            if key in [ord('q'), ord('Q'), 27]:
                break
            
            elif key == curses.KEY_LEFT:
                self.send('b')
                self.status = "← backward"
            
            elif key == curses.KEY_RIGHT:
                self.send('f')
                self.status = "→ forward"
            
            elif key == curses.KEY_SLEFT:
                self.send('B')
                self.status = "← BACKWARD"
            
            elif key == curses.KEY_SRIGHT:
                self.send('F')
                self.status = "→ FORWARD"
            
            elif key in [ord('+'), ord('=')]:
                self.frame_advance += 5
                self.status = f"Frame advance: {self.frame_advance}"
                self.save_state()
            
            elif key in [ord('-'), ord('_')]:
                self.frame_advance = max(10, self.frame_advance - 5)
                self.status = f"Frame advance: {self.frame_advance}"
                self.save_state()
            
            elif key in [ord('c'), ord('C')]:
                if not self.roll_name:
                    self.status = "Create roll first (N)"
                else:
                    self.calibrate(stdscr)
            
            elif key in [ord('p'), ord('P')]:
                if self.preview():
                    if HAS_CV2:
                        has_content = check_has_content("/tmp/preview.jpg")
                        self.status = f"Preview: {'Content detected' if has_content else 'In gap'}"
                    else:
                        self.status = "Preview OK"
                else:
                    self.status = "Preview failed"
            
            elif key == ord(' '):
                if not self.roll_name:
                    self.status = "Create roll first (N)"
                else:
                    self.capture_frame(stdscr)
            
            elif key in [ord('n'), ord('N')]:
                self.new_roll(stdscr)
        
        # Cleanup
        if self.arduino:
            self.send('M')
            self.arduino.close()


def main():
    try:
        scanner = FilmScanner()
        curses.wrapper(scanner.run)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
