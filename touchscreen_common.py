#!/usr/bin/env python3
"""
Film Scanner - Touch Screen Common Components
Shared UI components and utilities for all touchscreen apps.

Updated for Pi OS Bookworm/Trixie:
- Uses direct framebuffer rendering (not SDL fbcon)
- Uses evdev for touch input (not tslib)
- Compatible with vc4-kms-v3d DRM driver
"""

import pygame
import pygame.freetype
import sys
import os
import time
from typing import Tuple, Callable, Optional
from dataclasses import dataclass

# Optional psutil for system stats
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Optional evdev for direct touch input
try:
    import evdev
    from evdev import InputDevice, ecodes
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False

# Import framebuffer display for direct rendering
try:
    from framebuffer_display import FramebufferDisplay
    FRAMEBUFFER_AVAILABLE = True
except ImportError:
    FRAMEBUFFER_AVAILABLE = False

from touchscreen_config import TouchScreenConfig, get_config, ColorTheme


# ============================================================================
# Helper Functions
# ============================================================================

def is_windowed_mode() -> bool:
    """Check if running in windowed/desktop mode"""
    return '--windowed' in sys.argv


def find_framebuffer() -> str:
    """Find the framebuffer device (fb0 or fb1)"""
    for fb in ['/dev/fb0', '/dev/fb1']:
        if os.path.exists(fb):
            return fb
    return '/dev/fb0'  # Default


# ============================================================================
# System Stats Monitor
# ============================================================================

class SystemStatsMonitor:
    """
    Efficient system stats monitor with caching.
    Reads CPU usage, RAM usage, and CPU temperature without poll spam.
    """
    
    CPU_TEMP_PATH = "/sys/class/thermal/thermal_zone0/temp"
    
    def __init__(self, update_interval: float = 3.0):
        self.update_interval = update_interval
        self._last_update = 0
        self._cpu_percent = 0.0
        self._ram_percent = 0.0
        self._cpu_temp = 0.0
        self._temp_available = os.path.exists(self.CPU_TEMP_PATH)
        
        if PSUTIL_AVAILABLE:
            psutil.cpu_percent(interval=None)
    
    def _read_cpu_temp(self) -> float:
        if not self._temp_available:
            return 0.0
        try:
            with open(self.CPU_TEMP_PATH, 'r') as f:
                temp_milli = int(f.read().strip())
                return temp_milli / 1000.0
        except (IOError, ValueError):
            return 0.0
    
    def update(self) -> bool:
        now = time.time()
        if now - self._last_update < self.update_interval:
            return False
        
        self._last_update = now
        
        if PSUTIL_AVAILABLE:
            self._cpu_percent = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            self._ram_percent = mem.percent
        
        self._cpu_temp = self._read_cpu_temp()
        return True
    
    @property
    def cpu_percent(self) -> float:
        return self._cpu_percent
    
    @property
    def ram_percent(self) -> float:
        return self._ram_percent
    
    @property
    def cpu_temp(self) -> float:
        return self._cpu_temp
    
    @property
    def temp_available(self) -> bool:
        return self._temp_available
    
    @property
    def is_available(self) -> bool:
        return PSUTIL_AVAILABLE or self._temp_available


# ============================================================================
# UI Components
# ============================================================================

class Button:
    """Touch-friendly button widget"""
    
    def __init__(self, 
                 rect: pygame.Rect,
                 text: str,
                 callback: Callable,
                 color: Tuple[int, int, int] = None,
                 hover_color: Tuple[int, int, int] = None,
                 text_color: Tuple[int, int, int] = None,
                 icon: str = None,
                 font_size: int = None,
                 enabled: bool = True,
                 config: TouchScreenConfig = None):
        
        self.rect = rect
        self.text = text
        self.callback = callback
        self.icon = icon
        self.enabled = enabled
        self.config = config or get_config()
        
        colors = self.config.colors
        self.color = color or colors.btn_primary
        self.hover_color = hover_color or colors.btn_primary_hover
        self.text_color = text_color or colors.text_primary
        self.font_size = font_size or self.config.ui.font_size_medium
        
        self.pressed = False
        self.press_time = 0
        
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle touch/mouse events. Returns True if button was activated."""
        if not self.enabled:
            return False
            
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.pressed = True
                self.press_time = time.time()
                return False
                
        elif event.type == pygame.MOUSEBUTTONUP:
            if self.pressed and self.rect.collidepoint(event.pos):
                self.pressed = False
                if self.callback:
                    self.callback()
                return True
            self.pressed = False
            
        return False
    
    def draw(self, surface: pygame.Surface, font: pygame.freetype.Font):
        """Draw the button"""
        colors = self.config.colors
        
        # Determine button color
        if not self.enabled:
            # Use darker background for disabled buttons so text is visible
            color = colors.bg_panel
            text_color = colors.text_muted
        elif self.pressed:
            color = self.hover_color
            text_color = self.text_color
        else:
            color = self.color
            text_color = self.text_color
        
        radius = self.config.ui.button_radius
        pygame.draw.rect(surface, color, self.rect, border_radius=radius)
        
        if self.pressed:
            pygame.draw.rect(surface, colors.border_active, self.rect, 2, border_radius=radius)
        
        # Draw text (icon support removed - use plain text for font compatibility)
        display_text = self.text
        
        font.size = self.font_size
        text_surface, text_rect = font.render(display_text, text_color)
        text_rect.center = self.rect.center
        surface.blit(text_surface, text_rect)


class AppIcon:
    """Large touchable app icon for launcher"""
    
    def __init__(self,
                 rect: pygame.Rect,
                 name: str,
                 icon: str,
                 callback: Callable,
                 color: Tuple[int, int, int] = None,
                 config: TouchScreenConfig = None):
        
        self.rect = rect
        self.name = name
        self.icon = icon
        self.callback = callback
        self.config = config or get_config()
        self.color = color or self.config.colors.btn_primary
        self.pressed = False
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.pressed = True
                return False
        elif event.type == pygame.MOUSEBUTTONUP:
            if self.pressed and self.rect.collidepoint(event.pos):
                self.pressed = False
                if self.callback:
                    self.callback()
                return True
            self.pressed = False
        return False
    
    def draw(self, surface: pygame.Surface, font: pygame.freetype.Font):
        colors = self.config.colors
        ui = self.config.ui
        
        # Background
        bg_color = self.color if not self.pressed else colors.btn_primary_hover
        pygame.draw.rect(surface, bg_color, self.rect, border_radius=12)
        
        if self.pressed:
            pygame.draw.rect(surface, colors.border_active, self.rect, 3, border_radius=12)
        
        # Name (centered - no icon to avoid font compatibility issues)
        font.size = ui.font_size_medium
        name_surf, name_rect = font.render(self.name, colors.text_primary)
        name_rect.center = self.rect.center
        surface.blit(name_surf, name_rect)


# ============================================================================
# Base App Class
# ============================================================================

class BaseTouchApp:
    """
    Base class for touchscreen applications.
    
    Uses direct framebuffer rendering on TFT displays (when not in windowed mode).
    Falls back to SDL/pygame display for windowed/desktop testing.
    """
    
    APP_NAME = "Base App"
    
    def __init__(self, config: TouchScreenConfig = None):
        self.config = config or get_config()
        self.running = False
        self.exit_to_launcher = True  # If True, return to launcher on exit
        
        # Initialize pygame (core modules)
        pygame.init()
        pygame.freetype.init()
        
        # Determine display mode
        windowed = is_windowed_mode()
        self._using_framebuffer = False
        self._fb_display = None
        
        if not windowed and FRAMEBUFFER_AVAILABLE:
            # Try direct framebuffer for TFT displays
            fb_device = find_framebuffer()
            try:
                self._fb_display = FramebufferDisplay(
                    fb_device,
                    self.config.display.width,
                    self.config.display.height
                )
                self.screen = self._fb_display.surface
                self._using_framebuffer = True
                print(f"Using direct framebuffer: {fb_device}")
            except Exception as e:
                print(f"Framebuffer init failed: {e}, falling back to SDL")
        
        if not self._using_framebuffer:
            # Fallback to SDL/pygame display
            if not self.config.display.show_cursor:
                try:
                    pygame.mouse.set_visible(False)
                except pygame.error:
                    pass
            
            display_flags = pygame.FULLSCREEN if self.config.display.fullscreen and not windowed else 0
            self.screen = pygame.display.set_mode(
                (self.config.display.width, self.config.display.height),
                display_flags
            )
            pygame.display.set_caption(self.APP_NAME)
            print("Using SDL display")
        
        # Load fonts
        self.font = pygame.freetype.SysFont(
            self.config.ui.font_family, 
            self.config.ui.font_size_medium
        )
        self.mono_font = pygame.freetype.SysFont(
            self.config.ui.font_family_mono,
            self.config.ui.font_size_tiny
        )
        
        # System stats
        self.system_stats = SystemStatsMonitor(
            update_interval=self.config.app.system_stats_interval
        )
        
        # Clock for frame rate
        self.clock = pygame.time.Clock()
        
        # Toast notification
        self.toast_message = ""
        self.toast_time = 0
        self.toast_duration = 3.0
    
    def _show_toast(self, message: str):
        """Show a toast notification"""
        self.toast_message = message
        self.toast_time = time.time()
    
    def _draw_toast(self):
        """Draw toast notification if active"""
        if not self.toast_message:
            return
            
        elapsed = time.time() - self.toast_time
        if elapsed > self.toast_duration:
            self.toast_message = ""
            return
        
        colors = self.config.colors
        ui = self.config.ui
        
        alpha = 255
        if elapsed > self.toast_duration - 0.5:
            alpha = int(255 * (self.toast_duration - elapsed) / 0.5)
        
        self.font.size = ui.font_size_small
        text_surf, text_rect = self.font.render(self.toast_message, colors.text_primary)
        
        padding = 16
        toast_rect = pygame.Rect(
            0, 0,
            text_rect.width + padding * 2,
            text_rect.height + padding * 2
        )
        toast_rect.centerx = self.config.display.width // 2
        toast_rect.bottom = self.config.display.height - 80
        
        toast_surf = pygame.Surface(toast_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(toast_surf, (*colors.bg_secondary, alpha), 
                        toast_surf.get_rect(), border_radius=8)
        self.screen.blit(toast_surf, toast_rect)
        
        text_rect.center = toast_rect.center
        self.screen.blit(text_surf, text_rect)
    
    def _draw_system_stats(self):
        """Draw system stats in bottom-right corner"""
        if not self.system_stats.is_available:
            return
        
        colors = self.config.colors
        ui = self.config.ui
        
        self.system_stats.update()
        
        stats_lines = []
        
        if PSUTIL_AVAILABLE:
            cpu = self.system_stats.cpu_percent
            ram = self.system_stats.ram_percent
            stats_lines.append(f"CPU: {cpu:4.1f}%")
            stats_lines.append(f"RAM: {ram:4.1f}%")
        
        if self.system_stats.temp_available:
            temp = self.system_stats.cpu_temp
            stats_lines.append(f"TMP: {temp:4.1f}°C")
        
        if not stats_lines:
            return
        
        self.font.size = ui.font_size_tiny
        line_height = ui.font_size_tiny + 2
        padding = 6
        
        max_width = 0
        for line in stats_lines:
            surf, rect = self.font.render(line, colors.text_secondary)
            max_width = max(max_width, rect.width)
        
        box_width = max_width + padding * 2
        box_height = len(stats_lines) * line_height + padding * 2
        
        box_x = self.config.display.width - box_width - ui.button_margin
        box_y = self.config.display.height - box_height - ui.button_margin
        
        box_rect = pygame.Rect(box_x, box_y, box_width, box_height)
        box_surf = pygame.Surface((box_width, box_height), pygame.SRCALPHA)
        pygame.draw.rect(box_surf, (*colors.bg_secondary, 200), 
                        box_surf.get_rect(), border_radius=4)
        self.screen.blit(box_surf, box_rect)
        
        y = box_y + padding
        for line in stats_lines:
            if line.startswith("TMP:"):
                temp = self.system_stats.cpu_temp
                if temp > 80:
                    text_color = colors.error
                elif temp > 70:
                    text_color = colors.warning
                else:
                    text_color = colors.text_secondary
            elif line.startswith("CPU:"):
                cpu = self.system_stats.cpu_percent
                if cpu > 90:
                    text_color = colors.error
                elif cpu > 75:
                    text_color = colors.warning
                else:
                    text_color = colors.text_secondary
            elif line.startswith("RAM:"):
                ram = self.system_stats.ram_percent
                if ram > 90:
                    text_color = colors.error
                elif ram > 80:
                    text_color = colors.warning
                else:
                    text_color = colors.text_secondary
            else:
                text_color = colors.text_secondary
            
            surf, rect = self.font.render(line, text_color)
            rect.topleft = (box_x + padding, y)
            self.screen.blit(surf, rect)
            y += line_height
    
    def _draw_header(self, title: str):
        """Draw app header bar"""
        colors = self.config.colors
        ui = self.config.ui
        
        # Header background
        header_rect = pygame.Rect(0, 0, self.config.display.width, ui.status_bar_height)
        pygame.draw.rect(self.screen, colors.bg_secondary, header_rect)
        pygame.draw.line(self.screen, colors.border, 
                        (0, ui.status_bar_height - 1), 
                        (self.config.display.width, ui.status_bar_height - 1))
        
        # Title
        self.font.size = ui.font_size_medium
        title_surf, title_rect = self.font.render(title, colors.text_primary)
        title_rect.center = (self.config.display.width // 2, ui.status_bar_height // 2)
        self.screen.blit(title_surf, title_rect)
        
        # Time (right side)
        from datetime import datetime
        time_str = datetime.now().strftime("%H:%M")
        self.font.size = ui.font_size_small
        time_surf, time_rect = self.font.render(time_str, colors.text_secondary)
        time_rect.midright = (self.config.display.width - 10, ui.status_bar_height // 2)
        self.screen.blit(time_surf, time_rect)
    
    def handle_events(self):
        """Handle pygame events - override in subclass"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                    self.running = False
    
    def update(self):
        """Update app state - override in subclass"""
        pass
    
    def draw(self):
        """Draw app - override in subclass"""
        self.screen.fill(self.config.colors.bg_primary)
    
    def run(self) -> bool:
        """
        Main app loop.
        Returns True if should return to launcher, False to exit completely.
        """
        self.running = True
        
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self._draw_system_stats()
            self._draw_toast()
            
            # Update display
            if self._using_framebuffer and self._fb_display:
                self._fb_display.update()
            else:
                pygame.display.flip()
            
            self.clock.tick(30)
        
        # Cleanup
        if self._using_framebuffer and self._fb_display:
            self._fb_display.clear()
            self._fb_display.update()
        
        pygame.quit()
        return self.exit_to_launcher
    
    def cleanup(self):
        """Clean up resources - override in subclass"""
        pass
