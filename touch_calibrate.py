#!/usr/bin/env python3
"""
Touch Screen Calibration Utility

This script helps calibrate and test touch input for TFT screens.
It shows where you're touching and helps determine if axes need
to be swapped or inverted.

Run with: sudo python3 touch_calibrate.py
"""

import os
import sys
import time

# Try to import required modules
try:
    import evdev
    from evdev import InputDevice, ecodes
except ImportError:
    print("evdev not installed. Run: sudo apt install python3-evdev")
    sys.exit(1)

try:
    from framebuffer_display import FramebufferDisplay
    import pygame
    import pygame.freetype
except ImportError as e:
    print(f"Missing module: {e}")
    sys.exit(1)


def find_touch_device():
    """Find the touch input device"""
    print("Searching for touch device...")
    
    for path in evdev.list_devices():
        try:
            dev = InputDevice(path)
            caps = dev.capabilities()
            
            if ecodes.EV_ABS in caps:
                abs_caps = caps[ecodes.EV_ABS]
                has_x = any(c[0] == ecodes.ABS_X for c in abs_caps)
                has_y = any(c[0] == ecodes.ABS_Y for c in abs_caps)
                
                if has_x and has_y:
                    print(f"Found touch device: {dev.name}")
                    print(f"  Path: {path}")
                    
                    # Get axis info
                    x_info = y_info = None
                    for item in abs_caps:
                        code = item[0] if isinstance(item, tuple) else item
                        info = item[1] if isinstance(item, tuple) and len(item) > 1 else None
                        if code == ecodes.ABS_X:
                            x_info = info
                        elif code == ecodes.ABS_Y:
                            y_info = info
                    
                    if x_info:
                        print(f"  X: min={x_info.min}, max={x_info.max}")
                    if y_info:
                        print(f"  Y: min={y_info.min}, max={y_info.max}")
                    
                    return dev, x_info, y_info
        except Exception as e:
            continue
    
    return None, None, None


def main():
    # Screen dimensions
    WIDTH = 480
    HEIGHT = 320
    
    # Calibration settings (adjust these!)
    SWAP_XY = False      # Swap X and Y axes
    INVERT_X = False     # Invert X axis
    INVERT_Y = False     # Invert Y axis
    
    # Parse command line args
    for arg in sys.argv[1:]:
        if arg == '--swap':
            SWAP_XY = True
        elif arg == '--invertx':
            INVERT_X = True
        elif arg == '--inverty':
            INVERT_Y = True
    
    print(f"\nCalibration settings:")
    print(f"  Swap X/Y: {SWAP_XY}")
    print(f"  Invert X: {INVERT_X}")
    print(f"  Invert Y: {INVERT_Y}")
    print(f"\nRun with --swap, --invertx, --inverty to adjust")
    print()
    
    # Find touch device
    device, x_info, y_info = find_touch_device()
    if not device:
        print("No touch device found!")
        return
    
    # Get calibration values
    x_min = x_info.min if x_info else 0
    x_max = x_info.max if x_info else WIDTH
    y_min = y_info.min if y_info else 0
    y_max = y_info.max if y_info else HEIGHT
    
    # Initialize framebuffer display
    print(f"\nInitializing display ({WIDTH}x{HEIGHT})...")
    fb = FramebufferDisplay('/dev/fb0', WIDTH, HEIGHT)
    
    pygame.freetype.init()
    font = pygame.freetype.SysFont('DejaVu Sans', 16)
    font_large = pygame.freetype.SysFont('DejaVu Sans', 24)
    
    # Colors
    BG = (17, 24, 39)
    WHITE = (255, 255, 255)
    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLUE = (0, 100, 255)
    YELLOW = (255, 255, 0)
    
    # Touch state
    raw_x = raw_y = 0
    screen_x = screen_y = 0
    is_touching = False
    touch_history = []  # List of recent touch points
    
    print("\nTouch Calibration Test")
    print("======================")
    print("Touch the screen to see coordinates")
    print("Touch the corners to check alignment")
    print("Press Ctrl+C to exit")
    print()
    
    try:
        device.grab()  # Exclusive access
        
        running = True
        while running:
            # Read touch events (non-blocking)
            try:
                for event in device.read():
                    if event.type == ecodes.EV_ABS:
                        if event.code == ecodes.ABS_X:
                            raw_x = event.value
                        elif event.code == ecodes.ABS_Y:
                            raw_y = event.value
                    
                    elif event.type == ecodes.EV_KEY:
                        if event.code == ecodes.BTN_TOUCH:
                            is_touching = event.value == 1
                            if is_touching:
                                # Calculate screen coordinates
                                tx = raw_x
                                ty = raw_y
                                
                                if SWAP_XY:
                                    tx, ty = ty, tx
                                    # Also swap the ranges
                                    tx_min, tx_max = y_min, y_max
                                    ty_min, ty_max = x_min, x_max
                                else:
                                    tx_min, tx_max = x_min, x_max
                                    ty_min, ty_max = y_min, y_max
                                
                                # Scale to screen
                                screen_x = int((tx - tx_min) * WIDTH / (tx_max - tx_min))
                                screen_y = int((ty - ty_min) * HEIGHT / (ty_max - ty_min))
                                
                                if INVERT_X:
                                    screen_x = WIDTH - screen_x
                                if INVERT_Y:
                                    screen_y = HEIGHT - screen_y
                                
                                # Clamp to screen bounds
                                screen_x = max(0, min(WIDTH - 1, screen_x))
                                screen_y = max(0, min(HEIGHT - 1, screen_y))
                                
                                # Add to history
                                touch_history.append((screen_x, screen_y, time.time()))
                                # Keep only recent touches
                                touch_history = [(x, y, t) for x, y, t in touch_history 
                                               if time.time() - t < 3.0]
                                
                                print(f"Touch: raw=({raw_x}, {raw_y}) -> screen=({screen_x}, {screen_y})")
            
            except BlockingIOError:
                pass
            
            # Draw
            fb.surface.fill(BG)
            
            # Draw corner targets
            target_size = 30
            corners = [
                (target_size, target_size, "TL"),
                (WIDTH - target_size, target_size, "TR"),
                (target_size, HEIGHT - target_size, "BL"),
                (WIDTH - target_size, HEIGHT - target_size, "BR"),
            ]
            
            for cx, cy, label in corners:
                # Draw crosshair
                pygame.draw.line(fb.surface, GREEN, (cx - 15, cy), (cx + 15, cy), 2)
                pygame.draw.line(fb.surface, GREEN, (cx, cy - 15), (cx, cy + 15), 2)
                # Label
                surf, rect = font.render(label, GREEN)
                fb.surface.blit(surf, (cx - rect.width//2, cy + 20))
            
            # Draw center target
            cx, cy = WIDTH // 2, HEIGHT // 2
            pygame.draw.circle(fb.surface, BLUE, (cx, cy), 20, 2)
            pygame.draw.line(fb.surface, BLUE, (cx - 25, cy), (cx + 25, cy), 2)
            pygame.draw.line(fb.surface, BLUE, (cx, cy - 25), (cx, cy + 25), 2)
            
            # Draw title
            surf, rect = font_large.render("Touch Calibration", WHITE)
            fb.surface.blit(surf, (WIDTH//2 - rect.width//2, 5))
            
            # Draw current touch info
            if is_touching:
                # Draw touch point
                pygame.draw.circle(fb.surface, RED, (screen_x, screen_y), 10)
                pygame.draw.circle(fb.surface, YELLOW, (screen_x, screen_y), 10, 2)
            
            # Draw touch history (fading trail)
            for tx, ty, t in touch_history:
                age = time.time() - t
                alpha = max(0, 1 - age / 3.0)
                color = (int(255 * alpha), int(100 * alpha), int(100 * alpha))
                pygame.draw.circle(fb.surface, color, (tx, ty), 5)
            
            # Draw coordinate info at bottom
            info_y = HEIGHT - 50
            surf, rect = font.render(f"Raw: ({raw_x}, {raw_y})", WHITE)
            fb.surface.blit(surf, (10, info_y))
            surf, rect = font.render(f"Screen: ({screen_x}, {screen_y})", WHITE)
            fb.surface.blit(surf, (10, info_y + 20))
            
            # Draw calibration hints
            surf, rect = font.render(f"swap={SWAP_XY} invX={INVERT_X} invY={INVERT_Y}", YELLOW)
            fb.surface.blit(surf, (WIDTH - rect.width - 10, info_y + 20))
            
            fb.update()
            time.sleep(0.033)  # ~30 FPS
    
    except KeyboardInterrupt:
        print("\nExiting...")
    
    finally:
        device.ungrab()
        fb.clear()
        fb.update()
        
    # Print calibration recommendation
    print("\n" + "="*50)
    print("CALIBRATION RESULTS")
    print("="*50)
    print("\nIf touch points don't match the targets, try:")
    print("  sudo python3 touch_calibrate.py --swap        (if X/Y are swapped)")
    print("  sudo python3 touch_calibrate.py --invertx     (if X is reversed)")
    print("  sudo python3 touch_calibrate.py --inverty     (if Y is reversed)")
    print("  Or combine: sudo python3 touch_calibrate.py --swap --inverty")
    print()


if __name__ == '__main__':
    main()
