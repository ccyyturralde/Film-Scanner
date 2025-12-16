#!/usr/bin/env python3
"""
Direct Framebuffer Display for TFT screens

Provides a pygame-compatible display interface that writes directly to 
the Linux framebuffer, bypassing SDL. This works on Pi OS with FBTFT 
displays where SDL's fbcon driver doesn't work with vc4-kms-v3d.

Usage:
    from framebuffer_display import FramebufferDisplay
    
    fb = FramebufferDisplay('/dev/fb0', 480, 320)
    
    # Draw with pygame on the surface
    fb.surface.fill((255, 0, 0))
    pygame.draw.rect(fb.surface, (0, 255, 0), (10, 10, 100, 100))
    
    # Push to display
    fb.update()
"""

import os
import numpy as np
import pygame

class FramebufferDisplay:
    """
    Direct framebuffer display that works with FBTFT screens.
    
    Creates a pygame surface for drawing, then converts and writes
    to the framebuffer in RGB565 format.
    """
    
    def __init__(self, device: str = '/dev/fb0', width: int = 480, height: int = 320, 
                 bgr_mode: bool = None):
        """
        Initialize framebuffer display.
        
        Args:
            device: Framebuffer device path (usually /dev/fb0 for FBTFT)
            width: Display width in pixels
            height: Display height in pixels
            bgr_mode: Use BGR565 instead of RGB565 (auto-detect if None)
        """
        self.device = device
        self.width = width
        self.height = height
        
        # Verify framebuffer exists
        if not os.path.exists(device):
            raise RuntimeError(f"Framebuffer device not found: {device}")
        
        # Detect framebuffer properties
        self._bits_per_pixel = self._get_fb_bits_per_pixel()
        
        # BGR mode: some displays (like ILI9486) use BGR565 instead of RGB565
        # Auto-detect based on common display drivers
        if bgr_mode is None:
            self._bgr_mode = self._detect_bgr_mode()
        else:
            self._bgr_mode = bgr_mode
        
        print(f"Framebuffer: {device}, {width}x{height}, {self._bits_per_pixel}bpp, "
              f"{'BGR' if self._bgr_mode else 'RGB'}565")
        
        # Initialize pygame (but not the display subsystem)
        if not pygame.get_init():
            pygame.init()
        
        # Create an in-memory surface for drawing (24-bit RGB)
        self.surface = pygame.Surface((width, height))
        self.surface.fill((0, 0, 0))
        
        # Pre-allocate buffer for RGB565 conversion
        self._fb_buffer = np.zeros((height, width), dtype=np.uint16)
        
        # Track if display needs updating
        self._dirty = True
        
        # Initial clear
        self.clear()
    
    def _get_fb_bits_per_pixel(self) -> int:
        """Read framebuffer bits per pixel from sysfs."""
        try:
            # Extract fb number from device path (e.g., /dev/fb0 -> fb0)
            fb_name = os.path.basename(self.device)
            bpp_path = f"/sys/class/graphics/{fb_name}/bits_per_pixel"
            if os.path.exists(bpp_path):
                with open(bpp_path, 'r') as f:
                    return int(f.read().strip())
        except (IOError, ValueError):
            pass
        return 16  # Default to 16bpp (RGB565)
    
    def _detect_bgr_mode(self) -> bool:
        """
        Detect if display uses BGR565 instead of RGB565.
        
        Many FBTFT displays (ILI9486, ILI9341) use BGR order.
        """
        try:
            # Check driver name from sysfs
            fb_name = os.path.basename(self.device)
            name_path = f"/sys/class/graphics/{fb_name}/name"
            if os.path.exists(name_path):
                with open(name_path, 'r') as f:
                    driver_name = f.read().strip().lower()
                    # These drivers typically use BGR565
                    if any(d in driver_name for d in ['ili9486', 'ili9341', 'piscreen', 'waveshare']):
                        return True
        except (IOError, ValueError):
            pass
        
        # Default: try BGR mode for FBTFT displays (most common)
        # This is because most TFT displays sold for Raspberry Pi use BGR order
        return True
    
    def clear(self, color: tuple = (0, 0, 0)):
        """Clear the display with a solid color."""
        self.surface.fill(color)
        self._dirty = True
    
    def update(self):
        """
        Write the current surface to the framebuffer.
        
        Converts the pygame surface to RGB565/BGR565 and writes to the device.
        """
        # Get pixel data from pygame surface (RGB format)
        # pygame.surfarray gives us (width, height, 3) array
        pixels = pygame.surfarray.pixels3d(self.surface)
        
        # Convert to 16-bit 565 format
        # 565 format: 5 bits for first color, 6 bits for green, 5 bits for last color
        if self._bgr_mode:
            # BGR565: BBBBBGGGGGGRRRRR (blue in high bits, red in low bits)
            b = (pixels[:, :, 2] >> 3).astype(np.uint16)  # 5 bits blue (high)
            g = (pixels[:, :, 1] >> 2).astype(np.uint16)  # 6 bits green (middle)
            r = (pixels[:, :, 0] >> 3).astype(np.uint16)  # 5 bits red (low)
            pixel565 = (b << 11) | (g << 5) | r
        else:
            # RGB565: RRRRRGGGGGGBBBBB (red in high bits, blue in low bits)
            r = (pixels[:, :, 0] >> 3).astype(np.uint16)  # 5 bits red (high)
            g = (pixels[:, :, 1] >> 2).astype(np.uint16)  # 6 bits green (middle)
            b = (pixels[:, :, 2] >> 3).astype(np.uint16)  # 5 bits blue (low)
            pixel565 = (r << 11) | (g << 5) | b
        
        # Transpose because pygame surfarray is (width, height) but fb expects (height, width)
        self._fb_buffer = pixel565.T
        
        # Ensure contiguous array in correct byte order for framebuffer
        # FBTFT displays on Pi expect little-endian 16-bit pixels
        fb_data = np.ascontiguousarray(self._fb_buffer, dtype='<u2')  # '<u2' = little-endian uint16
        
        # Write to framebuffer
        try:
            with open(self.device, 'r+b') as fb:
                fb.write(fb_data.tobytes())
        except IOError as e:
            print(f"Error writing to framebuffer: {e}")
        
        self._dirty = False
    
    def flip(self):
        """Alias for update() - pygame compatibility."""
        self.update()
    
    def get_surface(self) -> pygame.Surface:
        """Get the pygame surface for drawing."""
        return self.surface
    
    def blit(self, source: pygame.Surface, dest: tuple, area=None):
        """Blit a surface onto the display surface."""
        self.surface.blit(source, dest, area)
        self._dirty = True
    
    def fill(self, color: tuple, rect=None):
        """Fill the display (or a rect) with a color."""
        if rect:
            self.surface.fill(color, rect)
        else:
            self.surface.fill(color)
        self._dirty = True
    
    def get_width(self) -> int:
        return self.width
    
    def get_height(self) -> int:
        return self.height
    
    def get_size(self) -> tuple:
        return (self.width, self.height)


class FramebufferDisplayManager:
    """
    Singleton manager for framebuffer display.
    
    Provides a pygame.display-like interface for the touchscreen apps.
    """
    
    _instance = None
    _display = None
    
    @classmethod
    def init(cls, device: str = '/dev/fb0', width: int = 480, height: int = 320):
        """Initialize the framebuffer display."""
        if cls._display is None:
            cls._display = FramebufferDisplay(device, width, height)
        return cls._display
    
    @classmethod
    def get_display(cls) -> FramebufferDisplay:
        """Get the current display instance."""
        return cls._display
    
    @classmethod
    def quit(cls):
        """Clean up the display."""
        if cls._display:
            cls._display.clear()
            cls._display.update()
        cls._display = None


def init_display(width: int = 480, height: int = 320, 
                 device: str = None, 
                 use_sdl_fallback: bool = True) -> tuple:
    """
    Initialize display with automatic detection.
    
    Tries framebuffer first, falls back to SDL if in windowed mode.
    
    Args:
        width: Display width
        height: Display height
        device: Framebuffer device (auto-detected if None)
        use_sdl_fallback: Try SDL if framebuffer fails
        
    Returns:
        (surface, update_func, is_framebuffer) tuple
    """
    import sys
    
    # Check for windowed mode
    windowed = '--windowed' in sys.argv
    
    if not windowed:
        # Try to find framebuffer device
        if device is None:
            for fb_path in ['/dev/fb0', '/dev/fb1']:
                if os.path.exists(fb_path):
                    device = fb_path
                    break
        
        if device and os.path.exists(device):
            try:
                fb = FramebufferDisplay(device, width, height)
                print(f"Using direct framebuffer: {device} ({width}x{height})")
                return (fb.surface, fb.update, True)
            except Exception as e:
                print(f"Framebuffer init failed: {e}")
    
    # Fallback to SDL/pygame display
    if use_sdl_fallback:
        pygame.init()
        flags = 0 if windowed else pygame.FULLSCREEN
        screen = pygame.display.set_mode((width, height), flags)
        pygame.display.set_caption("Film Scanner")
        print(f"Using SDL display ({width}x{height}, windowed={windowed})")
        return (screen, pygame.display.flip, False)
    
    raise RuntimeError("Could not initialize any display")


# Simple test
if __name__ == '__main__':
    import time
    import argparse
    
    parser = argparse.ArgumentParser(description='Test framebuffer display')
    parser.add_argument('--bgr', action='store_true', help='Force BGR565 mode')
    parser.add_argument('--rgb', action='store_true', help='Force RGB565 mode')
    parser.add_argument('--device', default='/dev/fb0', help='Framebuffer device')
    parser.add_argument('--width', type=int, default=480, help='Display width')
    parser.add_argument('--height', type=int, default=320, help='Display height')
    args = parser.parse_args()
    
    # Determine BGR mode
    bgr_mode = None  # Auto-detect
    if args.bgr:
        bgr_mode = True
    elif args.rgb:
        bgr_mode = False
    
    print("Testing direct framebuffer display...")
    print(f"Device: {args.device}, Size: {args.width}x{args.height}")
    if bgr_mode is not None:
        print(f"Mode: {'BGR565 (forced)' if bgr_mode else 'RGB565 (forced)'}")
    else:
        print("Mode: Auto-detect")
    
    # Try to init display
    try:
        fb = FramebufferDisplay(args.device, args.width, args.height, bgr_mode=bgr_mode)
        
        # Test 1: Red screen (should appear RED if color order is correct)
        print("Test 1: Red screen (should be RED)")
        fb.surface.fill((255, 0, 0))
        fb.update()
        time.sleep(2)
        
        # Test 2: Green screen
        print("Test 2: Green screen (should be GREEN)")
        fb.surface.fill((0, 255, 0))
        fb.update()
        time.sleep(2)
        
        # Test 3: Blue screen
        print("Test 3: Blue screen (should be BLUE)")
        fb.surface.fill((0, 0, 255))
        fb.update()
        time.sleep(2)
        
        # Test 4: Draw colored boxes - left to right: RED, GREEN, BLUE
        print("Test 4: Color boxes (R, G, B from left to right)")
        fb.surface.fill((20, 20, 40))
        pygame.draw.rect(fb.surface, (255, 0, 0), (10, 10, 100, 80))    # RED
        pygame.draw.rect(fb.surface, (0, 255, 0), (120, 10, 100, 80))   # GREEN
        pygame.draw.rect(fb.surface, (0, 0, 255), (230, 10, 100, 80))   # BLUE
        pygame.draw.circle(fb.surface, (255, 255, 0), (240, 200), 60)   # YELLOW
        fb.update()
        time.sleep(3)
        
        # Test 5: Text (if freetype available)
        print("Test 5: Text")
        try:
            pygame.freetype.init()
            font = pygame.freetype.SysFont('DejaVu Sans', 32)
            fb.surface.fill((17, 24, 39))
            font.render_to(fb.surface, (20, 100), "Film Scanner", (249, 250, 251))
            font.render_to(fb.surface, (20, 150), "TFT Display OK!", (16, 185, 129))
            mode_text = f"Mode: {'BGR565' if fb._bgr_mode else 'RGB565'}"
            font.render_to(fb.surface, (20, 200), mode_text, (100, 149, 237))
            fb.update()
            time.sleep(3)
        except Exception as e:
            print(f"Text test skipped: {e}")
        
        # Clear
        fb.clear()
        fb.update()
        
        print("\nAll tests passed!")
        print("\nIf colors appeared wrong (e.g., red showed as blue):")
        print("  - If using auto-detect, try: python framebuffer_display.py --rgb")
        print("  - Or try: python framebuffer_display.py --bgr")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
