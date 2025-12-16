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
    
    def __init__(self, device: str = '/dev/fb0', width: int = 480, height: int = 320):
        """
        Initialize framebuffer display.
        
        Args:
            device: Framebuffer device path (usually /dev/fb0 for FBTFT)
            width: Display width in pixels
            height: Display height in pixels
        """
        self.device = device
        self.width = width
        self.height = height
        
        # Verify framebuffer exists
        if not os.path.exists(device):
            raise RuntimeError(f"Framebuffer device not found: {device}")
        
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
    
    def clear(self, color: tuple = (0, 0, 0)):
        """Clear the display with a solid color."""
        self.surface.fill(color)
        self._dirty = True
    
    def update(self):
        """
        Write the current surface to the framebuffer.
        
        Converts the pygame surface to RGB565 and writes to the device.
        """
        # Get pixel data from pygame surface (RGB format)
        # pygame.surfarray gives us (width, height, 3) array
        pixels = pygame.surfarray.pixels3d(self.surface)
        
        # Convert RGB888 to RGB565
        # RGB565: RRRRRGGGGGGBBBBB (5 bits red, 6 bits green, 5 bits blue)
        r = (pixels[:, :, 0] >> 3).astype(np.uint16)  # 5 bits
        g = (pixels[:, :, 1] >> 2).astype(np.uint16)  # 6 bits
        b = (pixels[:, :, 2] >> 3).astype(np.uint16)  # 5 bits
        
        # Combine into RGB565 (note: need to transpose for correct orientation)
        rgb565 = (r << 11) | (g << 5) | b
        
        # Transpose because pygame surfarray is (width, height) but fb expects (height, width)
        self._fb_buffer = rgb565.T
        
        # Write to framebuffer
        try:
            with open(self.device, 'r+b') as fb:
                fb.write(self._fb_buffer.tobytes())
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
    
    print("Testing direct framebuffer display...")
    
    # Try to init display
    try:
        fb = FramebufferDisplay('/dev/fb0', 480, 320)
        
        # Test 1: Red screen
        print("Test 1: Red screen")
        fb.surface.fill((255, 0, 0))
        fb.update()
        time.sleep(1)
        
        # Test 2: Green screen
        print("Test 2: Green screen")
        fb.surface.fill((0, 255, 0))
        fb.update()
        time.sleep(1)
        
        # Test 3: Blue screen
        print("Test 3: Blue screen")
        fb.surface.fill((0, 0, 255))
        fb.update()
        time.sleep(1)
        
        # Test 4: Draw some shapes
        print("Test 4: Shapes")
        fb.surface.fill((20, 20, 40))
        pygame.draw.rect(fb.surface, (255, 0, 0), (10, 10, 100, 80))
        pygame.draw.rect(fb.surface, (0, 255, 0), (120, 10, 100, 80))
        pygame.draw.rect(fb.surface, (0, 0, 255), (230, 10, 100, 80))
        pygame.draw.circle(fb.surface, (255, 255, 0), (240, 200), 60)
        fb.update()
        time.sleep(2)
        
        # Test 5: Text (if freetype available)
        print("Test 5: Text")
        try:
            pygame.freetype.init()
            font = pygame.freetype.SysFont('DejaVu Sans', 32)
            fb.surface.fill((17, 24, 39))
            font.render_to(fb.surface, (20, 140), "Film Scanner", (249, 250, 251))
            font.render_to(fb.surface, (20, 180), "TFT Display OK!", (16, 185, 129))
            fb.update()
            time.sleep(2)
        except Exception as e:
            print(f"Text test skipped: {e}")
        
        # Clear
        fb.clear()
        fb.update()
        
        print("All tests passed!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
