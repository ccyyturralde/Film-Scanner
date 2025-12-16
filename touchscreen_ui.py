#!/usr/bin/env python3
"""
Film Scanner Touch Screen UI - Scanner App
A PyGame-based touch screen interface for 3.5" TFT displays.

This is the main scanner control app, launched from touchscreen_launcher.py

Features:
- Launch/Stop/Restart the web application
- View real-time logs with friendly error messages
- Display connection status (Arduino, Camera)
- System status and uptime (CPU, RAM, temperature)
- Touch-friendly large buttons
"""

import pygame
import pygame.freetype
import sys
import os
import time
import threading
from datetime import datetime
from typing import List, Tuple, Optional, Callable
from enum import Enum, auto

# Optional psutil for system stats (graceful fallback if not available)
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Optional evdev for direct touch input (when using framebuffer mode)
try:
    import evdev
    from evdev import InputDevice, ecodes
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False

# Import our modules
from app_manager import AppManager, AppState, LogEntry, get_app_manager
from touchscreen_config import TouchScreenConfig, get_config, ColorTheme

# Try to import framebuffer display module
try:
    from framebuffer_display import FramebufferDisplay, init_display
    FRAMEBUFFER_AVAILABLE = True
except ImportError:
    FRAMEBUFFER_AVAILABLE = False

def is_windowed_mode():
    """Check if running in windowed/desktop mode"""
    return '--windowed' in sys.argv


class TouchInputHandler:
    """
    Handles touch input via evdev for direct framebuffer mode.
    
    When using direct framebuffer rendering (bypassing SDL), pygame events
    don't work. This class reads touch events directly from the input device.
    """
    
    def __init__(self, device_path: str = None, width: int = 480, height: int = 320):
        self.width = width
        self.height = height
        self.device = None
        self.current_x = 0
        self.current_y = 0
        self.is_touching = False
        self._pending_touch = None  # (x, y) of pending touch release
        self._x_min = 0
        self._x_max = width
        self._y_min = 0
        self._y_max = height
        
        if not EVDEV_AVAILABLE:
            print("evdev not available - touch input disabled")
            print("Install with: sudo apt install python3-evdev")
            return
        
        print(f"Looking for touch device...")
        print(f"Available input devices:")
        for path in evdev.list_devices():
            try:
                dev = InputDevice(path)
                print(f"  {path}: {dev.name}")
            except:
                pass
        
        # Try specified device first
        if device_path and os.path.exists(device_path):
            try:
                self.device = InputDevice(device_path)
                self._setup_device(self.device)
                return
            except Exception as e:
                print(f"Failed to open {device_path}: {e}")
        
        # Auto-detect touch device
        for path in evdev.list_devices():
            try:
                dev = InputDevice(path)
                caps = dev.capabilities()
                # Look for absolute positioning (touch screens)
                if ecodes.EV_ABS in caps:
                    abs_caps = caps[ecodes.EV_ABS]
                    has_x = any(c[0] == ecodes.ABS_X for c in abs_caps)
                    has_y = any(c[0] == ecodes.ABS_Y for c in abs_caps)
                    if has_x and has_y:
                        self.device = dev
                        self._setup_device(dev)
                        return
            except Exception as e:
                print(f"  Error checking {path}: {e}")
                continue
        
        print("No touch device found!")
        print("Touch input will not work.")
    
    def _setup_device(self, dev):
        """Setup device and get calibration info"""
        caps = dev.capabilities()
        if ecodes.EV_ABS in caps:
            abs_caps = caps[ecodes.EV_ABS]
            for item in abs_caps:
                code = item[0] if isinstance(item, tuple) else item
                info = item[1] if isinstance(item, tuple) and len(item) > 1 else None
                if code == ecodes.ABS_X and info:
                    self._x_min = info.min
                    self._x_max = info.max
                elif code == ecodes.ABS_Y and info:
                    self._y_min = info.min
                    self._y_max = info.max
        
        # Set non-blocking mode
        dev.grab()  # Exclusive access
        
        print(f"Touch device initialized: {dev.name}")
        print(f"  Path: {dev.path}")
        print(f"  X range: {self._x_min}-{self._x_max} -> 0-{self.width}")
        print(f"  Y range: {self._y_min}-{self._y_max} -> 0-{self.height}")
    
    def _scale_x(self, raw_x: int) -> int:
        """Scale raw X coordinate to screen width"""
        if not hasattr(self, '_x_max'):
            return raw_x
        return int((raw_x - self._x_min) * self.width / (self._x_max - self._x_min))
    
    def _scale_y(self, raw_y: int) -> int:
        """Scale raw Y coordinate to screen height"""
        if not hasattr(self, '_y_max'):
            return raw_y
        return int((raw_y - self._y_min) * self.height / (self._y_max - self._y_min))
    
    def poll(self) -> Optional[Tuple[str, int, int]]:
        """
        Poll for touch events.
        
        Returns:
            ('touch', x, y) for touch press
            ('release', x, y) for touch release
            None if no event
        """
        if not self.device:
            return None
        
        # Return pending touch release
        if self._pending_touch:
            result = ('release', self._pending_touch[0], self._pending_touch[1])
            self._pending_touch = None
            return result
        
        try:
            # Non-blocking read
            while True:
                event = self.device.read_one()
                if event is None:
                    break
                
                if event.type == ecodes.EV_ABS:
                    if event.code == ecodes.ABS_X:
                        self.current_x = self._scale_x(event.value)
                    elif event.code == ecodes.ABS_Y:
                        self.current_y = self._scale_y(event.value)
                
                elif event.type == ecodes.EV_KEY:
                    if event.code == ecodes.BTN_TOUCH:
                        if event.value == 1:  # Touch press
                            self.is_touching = True
                            return ('touch', self.current_x, self.current_y)
                        else:  # Touch release
                            self.is_touching = False
                            return ('release', self.current_x, self.current_y)
                
                elif event.type == ecodes.EV_SYN:
                    # Sync event - if touching, this might be a touch event
                    pass
        
        except BlockingIOError:
            pass
        except Exception as e:
            print(f"Touch read error: {e}")
        
        return None
    
    def close(self):
        """Close the touch device"""
        if self.device:
            self.device.close()


class SystemStatsMonitor:
    """
    Efficient system stats monitor with caching.
    Reads CPU usage, RAM usage, and CPU temperature without poll spam.
    """
    
    # Path to CPU temperature on Raspberry Pi
    CPU_TEMP_PATH = "/sys/class/thermal/thermal_zone0/temp"
    
    def __init__(self, update_interval: float = 3.0):
        """
        Args:
            update_interval: How often to refresh stats (seconds). Default 3s.
        """
        self.update_interval = update_interval
        self._last_update = 0
        
        # Cached values
        self._cpu_percent = 0.0
        self._ram_percent = 0.0
        self._cpu_temp = 0.0
        
        # Track if we can read temperature
        self._temp_available = os.path.exists(self.CPU_TEMP_PATH)
        
        # Initialize CPU percent measurement (first call returns 0)
        if PSUTIL_AVAILABLE:
            psutil.cpu_percent(interval=None)
    
    def _read_cpu_temp(self) -> float:
        """Read CPU temperature from thermal zone (Raspberry Pi)."""
        if not self._temp_available:
            return 0.0
        
        try:
            with open(self.CPU_TEMP_PATH, 'r') as f:
                # Temperature is in millidegrees Celsius
                temp_milli = int(f.read().strip())
                return temp_milli / 1000.0
        except (IOError, ValueError):
            return 0.0
    
    def update(self) -> bool:
        """
        Update stats if enough time has passed.
        Returns True if stats were refreshed, False if cached values used.
        """
        now = time.time()
        if now - self._last_update < self.update_interval:
            return False
        
        self._last_update = now
        
        if PSUTIL_AVAILABLE:
            # Non-blocking CPU percent (uses delta from last call)
            self._cpu_percent = psutil.cpu_percent(interval=None)
            
            # RAM usage
            mem = psutil.virtual_memory()
            self._ram_percent = mem.percent
        
        # CPU temperature (works on Pi even without psutil)
        self._cpu_temp = self._read_cpu_temp()
        
        return True
    
    @property
    def cpu_percent(self) -> float:
        """CPU usage percentage (0-100)."""
        return self._cpu_percent
    
    @property
    def ram_percent(self) -> float:
        """RAM usage percentage (0-100)."""
        return self._ram_percent
    
    @property
    def cpu_temp(self) -> float:
        """CPU temperature in Celsius."""
        return self._cpu_temp
    
    @property
    def temp_available(self) -> bool:
        """Whether CPU temperature reading is available."""
        return self._temp_available
    
    @property
    def is_available(self) -> bool:
        """Whether system stats are available at all."""
        return PSUTIL_AVAILABLE or self._temp_available


class Screen(Enum):
    """Available screens/views"""
    HOME = auto()
    LOGS = auto()
    ERRORS = auto()
    SETTINGS = auto()

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
            color = colors.btn_secondary
            text_color = colors.text_muted
        elif self.pressed:
            color = self.hover_color
            text_color = self.text_color
        else:
            color = self.color
            text_color = self.text_color
        
        # Draw button background with rounded corners
        radius = self.config.ui.button_radius
        pygame.draw.rect(surface, color, self.rect, border_radius=radius)
        
        # Draw border
        if self.pressed:
            pygame.draw.rect(surface, colors.border_active, self.rect, 2, border_radius=radius)
        
        # Draw text (and icon if present)
        display_text = f"{self.icon} {self.text}" if self.icon else self.text
        
        font.size = self.font_size
        text_surface, text_rect = font.render(display_text, text_color)
        text_rect.center = self.rect.center
        surface.blit(text_surface, text_rect)


class StatusBar:
    """Top status bar showing app state and connections"""
    
    def __init__(self, width: int, height: int, config: TouchScreenConfig = None):
        self.config = config or get_config()
        self.rect = pygame.Rect(0, 0, width, height)
        self.status_text = "Starting..."
        self.arduino_connected = False
        self.camera_connected = False
        self.time_str = ""
        
    def update(self, status: dict):
        """Update status from app manager"""
        # Status icon is now plain text like "STOPPED", "RUNNING", etc.
        icon = status.get('icon', 'UNKNOWN')
        self.status_text = icon
        self.arduino_connected = status.get('arduino_connected', False)
        self.camera_connected = status.get('camera_connected', False)
        self.time_str = datetime.now().strftime("%H:%M")
    
    def draw(self, surface: pygame.Surface, font: pygame.freetype.Font):
        """Draw the status bar"""
        colors = self.config.colors
        
        # Background
        pygame.draw.rect(surface, colors.bg_secondary, self.rect)
        pygame.draw.line(surface, colors.border, 
                        (0, self.rect.height - 1), 
                        (self.rect.width, self.rect.height - 1))
        
        # Status text (left side)
        font.size = self.config.ui.font_size_small
        text_surface, text_rect = font.render(self.status_text, colors.text_primary)
        text_rect.midleft = (10, self.rect.height // 2)
        surface.blit(text_surface, text_rect)
        
        # Connection indicators (right side)
        indicator_y = self.rect.height // 2
        x_pos = self.rect.width - 10
        
        # Time
        time_surface, time_rect = font.render(self.time_str, colors.text_secondary)
        time_rect.midright = (x_pos, indicator_y)
        surface.blit(time_surface, time_rect)
        x_pos -= time_rect.width + 15
        
        # Camera indicator (CAM label with color)
        cam_color = colors.success if self.camera_connected else colors.error
        cam_text = "CAM"
        cam_surface, cam_rect = font.render(cam_text, cam_color)
        cam_rect.midright = (x_pos, indicator_y)
        surface.blit(cam_surface, cam_rect)
        x_pos -= cam_rect.width + 10
        
        # Arduino indicator (ARD label with color)
        ard_color = colors.success if self.arduino_connected else colors.error
        ard_text = "ARD"
        ard_surface, ard_rect = font.render(ard_text, ard_color)
        ard_rect.midright = (x_pos, indicator_y)
        surface.blit(ard_surface, ard_rect)


class LogViewer:
    """Scrollable log viewer widget"""
    
    def __init__(self, rect: pygame.Rect, config: TouchScreenConfig = None):
        self.rect = rect
        self.config = config or get_config()
        self.logs: List[LogEntry] = []
        self.scroll_offset = 0
        self.auto_scroll = True
        self.show_errors_only = False
        
    def set_logs(self, logs: List[LogEntry]):
        """Update the log entries"""
        self.logs = logs
        if self.auto_scroll:
            # Scroll to bottom
            visible_lines = self.config.ui.log_lines_visible
            self.scroll_offset = max(0, len(self.logs) - visible_lines)
    
    def scroll_up(self):
        """Scroll up"""
        self.scroll_offset = max(0, self.scroll_offset - 3)
        self.auto_scroll = False
    
    def scroll_down(self):
        """Scroll down"""
        visible = self.config.ui.log_lines_visible
        max_offset = max(0, len(self.logs) - visible)
        self.scroll_offset = min(max_offset, self.scroll_offset + 3)
        if self.scroll_offset >= max_offset:
            self.auto_scroll = True
    
    def draw(self, surface: pygame.Surface, font: pygame.freetype.Font):
        """Draw the log viewer"""
        colors = self.config.colors
        ui = self.config.ui
        
        # Background
        pygame.draw.rect(surface, colors.bg_panel, self.rect, border_radius=ui.panel_radius)
        
        if not self.logs:
            # No logs message
            font.size = ui.font_size_small
            text_surface, text_rect = font.render("No logs yet...", colors.text_muted)
            text_rect.center = self.rect.center
            surface.blit(text_surface, text_rect)
            return
        
        # Draw log entries
        font.size = ui.font_size_tiny
        line_height = ui.log_line_height
        padding = ui.panel_padding
        
        y = self.rect.top + padding
        visible_lines = ui.log_lines_visible
        
        for i, log in enumerate(self.logs[self.scroll_offset:self.scroll_offset + visible_lines]):
            # Color based on log level
            if log.level == "ERROR":
                text_color = colors.error
            elif log.level == "WARNING":
                text_color = colors.warning
            elif log.level == "SUCCESS":
                text_color = colors.success
            else:
                text_color = colors.text_secondary
            
            # Format: [HH:MM:SS] message
            time_str = log.timestamp.strftime("%H:%M:%S")
            
            # Truncate message if too long
            max_chars = (self.rect.width - padding * 2) // 7  # Approximate char width
            message = log.message[:max_chars] if len(log.message) > max_chars else log.message
            
            line = f"[{time_str}] {message}"
            
            text_surface, text_rect = font.render(line, text_color)
            text_rect.topleft = (self.rect.left + padding, y)
            surface.blit(text_surface, text_rect)
            
            y += line_height
        
        # Scroll indicators
        if self.scroll_offset > 0:
            pygame.draw.polygon(surface, colors.text_muted, [
                (self.rect.right - 20, self.rect.top + 10),
                (self.rect.right - 10, self.rect.top + 20),
                (self.rect.right - 30, self.rect.top + 20)
            ])
        
        if self.scroll_offset < len(self.logs) - visible_lines:
            pygame.draw.polygon(surface, colors.text_muted, [
                (self.rect.right - 20, self.rect.bottom - 10),
                (self.rect.right - 10, self.rect.bottom - 20),
                (self.rect.right - 30, self.rect.bottom - 20)
            ])


class TouchScreenUI:
    """Main touch screen application"""
    
    def __init__(self, config: TouchScreenConfig = None):
        self.config = config or get_config()
        self.running = False
        self.current_screen = Screen.HOME
        
        # Initialize pygame (core modules, not display yet)
        pygame.init()
        pygame.freetype.init()
        
        # Determine display mode
        windowed = is_windowed_mode()
        self._using_framebuffer = False
        self._fb_display = None
        
        if not windowed and FRAMEBUFFER_AVAILABLE:
            # Try direct framebuffer for TFT displays
            fb_device = self.config.display.framebuffer
            # Check for fb0 first (FBTFT uses fb0 with vc4-kms-v3d)
            if not os.path.exists(fb_device):
                for fb_path in ['/dev/fb0', '/dev/fb1']:
                    if os.path.exists(fb_path):
                        fb_device = fb_path
                        break
            
            if os.path.exists(fb_device):
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
            # Fallback to SDL/pygame display (windowed mode or framebuffer failed)
            # Hide mouse cursor for touch screen
            if not self.config.display.show_cursor:
                try:
                    pygame.mouse.set_visible(False)
                except pygame.error:
                    pass  # May fail if no display
            
            display_flags = pygame.FULLSCREEN if self.config.display.fullscreen and not windowed else 0
            self.screen = pygame.display.set_mode(
                (self.config.display.width, self.config.display.height),
                display_flags
            )
            pygame.display.set_caption("Scanner Control")
            print("Using SDL display")
        
        # Initialize touch input (for framebuffer mode)
        self._touch_handler = None
        if self._using_framebuffer and EVDEV_AVAILABLE:
            touch_device = self.config.display.touch_device
            self._touch_handler = TouchInputHandler(
                touch_device,
                self.config.display.width,
                self.config.display.height
            )
        
        # Load fonts
        self.font = pygame.freetype.SysFont(
            self.config.ui.font_family, 
            self.config.ui.font_size_medium
        )
        self.mono_font = pygame.freetype.SysFont(
            self.config.ui.font_family_mono,
            self.config.ui.font_size_tiny
        )
        
        # Initialize app manager
        self.app_manager = get_app_manager()
        self.app_manager.add_state_callback(self._on_state_change)
        self.app_manager.add_error_callback(self._on_error)
        
        # Create UI components
        self._create_widgets()
        
        # Status update thread
        self._status_lock = threading.Lock()
        self._last_status = {}
        self._last_logs = []
        
        # Clock for frame rate control
        self.clock = pygame.time.Clock()
        
        # Toast notification
        self.toast_message = ""
        self.toast_time = 0
        self.toast_duration = 3.0
        
        # System stats monitor (CPU, RAM, temp) - uses configurable interval
        self.system_stats = SystemStatsMonitor(
            update_interval=self.config.app.system_stats_interval
        )
        
    def _create_widgets(self):
        """Create all UI widgets"""
        w = self.config.display.width
        h = self.config.display.height
        colors = self.config.colors
        ui = self.config.ui
        
        # Status bar
        self.status_bar = StatusBar(w, ui.status_bar_height, self.config)
        
        # Calculate button layout
        btn_w = ui.button_width
        btn_h = ui.button_height
        margin = ui.button_margin
        
        # Content area starts below status bar
        content_y = ui.status_bar_height + margin
        
        # Home screen buttons
        self.home_buttons = []
        
        # Main action buttons - 2 columns
        col1_x = margin
        col2_x = w // 2 + margin // 2
        btn_full_w = w // 2 - margin * 1.5
        
        # Row 1: Start / Stop
        self.btn_start = Button(
            pygame.Rect(col1_x, content_y, btn_full_w, btn_h),
            "START",
            self._on_start,
            color=colors.btn_success,
            hover_color=colors.btn_success_hover,
            config=self.config
        )
        self.home_buttons.append(self.btn_start)
        
        self.btn_stop = Button(
            pygame.Rect(col2_x, content_y, btn_full_w, btn_h),
            "STOP",
            self._on_stop,
            color=colors.btn_danger,
            hover_color=colors.btn_danger_hover,
            config=self.config
        )
        self.home_buttons.append(self.btn_stop)
        
        # Row 2: Restart / Logs
        row2_y = content_y + btn_h + margin
        
        self.btn_restart = Button(
            pygame.Rect(col1_x, row2_y, btn_full_w, btn_h),
            "RESTART",
            self._on_restart,
            color=colors.btn_primary,
            hover_color=colors.btn_primary_hover,
            config=self.config
        )
        self.home_buttons.append(self.btn_restart)
        
        self.btn_logs = Button(
            pygame.Rect(col2_x, row2_y, btn_full_w, btn_h),
            "LOGS",
            self._show_logs,
            color=colors.btn_secondary,
            hover_color=colors.btn_secondary_hover,
            config=self.config
        )
        self.home_buttons.append(self.btn_logs)
        
        # Row 3: Errors / Exit
        row3_y = row2_y + btn_h + margin
        
        self.btn_errors = Button(
            pygame.Rect(col1_x, row3_y, btn_full_w, btn_h),
            "ERRORS",
            self._show_errors,
            color=colors.btn_secondary,
            hover_color=colors.btn_secondary_hover,
            config=self.config
        )
        self.home_buttons.append(self.btn_errors)
        
        self.btn_back_home = Button(
            pygame.Rect(col2_x, row3_y, btn_full_w, btn_h),
            "EXIT",
            self._on_exit,
            color=colors.btn_secondary,
            hover_color=colors.btn_secondary_hover,
            config=self.config
        )
        self.home_buttons.append(self.btn_back_home)
        
        # Info panel area
        info_y = row3_y + btn_h + margin
        info_h = h - info_y - margin
        self.info_rect = pygame.Rect(margin, info_y, w - margin * 2, info_h)
        
        # Log viewer (for logs screen)
        log_viewer_y = content_y
        log_viewer_h = h - content_y - btn_h - margin * 3
        self.log_viewer = LogViewer(
            pygame.Rect(margin, log_viewer_y, w - margin * 2, log_viewer_h),
            self.config
        )
        
        # Back button for sub-screens
        back_btn_y = h - btn_h - margin
        self.btn_back = Button(
            pygame.Rect(margin, back_btn_y, btn_full_w, btn_h),
            "BACK",
            self._show_home,
            color=colors.btn_secondary,
            hover_color=colors.btn_secondary_hover,
            config=self.config
        )
        
        # Scroll buttons for log viewer
        scroll_btn_w = btn_full_w // 2 - margin // 2
        self.btn_scroll_up = Button(
            pygame.Rect(col2_x, back_btn_y, scroll_btn_w, btn_h),
            "UP",
            self.log_viewer.scroll_up,
            color=colors.btn_secondary,
            hover_color=colors.btn_secondary_hover,
            config=self.config
        )
        
        self.btn_scroll_down = Button(
            pygame.Rect(col2_x + scroll_btn_w + margin, back_btn_y, scroll_btn_w, btn_h),
            "DOWN",
            self.log_viewer.scroll_down,
            color=colors.btn_secondary,
            hover_color=colors.btn_secondary_hover,
            config=self.config
        )
    
    def _on_state_change(self, state: AppState):
        """Callback when app state changes"""
        # Update button states
        if state == AppState.RUNNING:
            self.btn_start.enabled = False
            self.btn_stop.enabled = True
            self.btn_restart.enabled = True
        elif state == AppState.STOPPED:
            self.btn_start.enabled = True
            self.btn_stop.enabled = False
            self.btn_restart.enabled = False
        elif state in [AppState.STARTING, AppState.STOPPING]:
            self.btn_start.enabled = False
            self.btn_stop.enabled = False
            self.btn_restart.enabled = False
        else:
            self.btn_start.enabled = True
            self.btn_stop.enabled = True
            self.btn_restart.enabled = True
    
    def _on_error(self, error: str):
        """Callback when an error occurs"""
        friendly = self.app_manager.format_error_for_display(error)
        self._show_toast(f"Error: {friendly}")
    
    def _on_start(self):
        """Start button handler"""
        self._show_toast("Starting app...")
        threading.Thread(target=self.app_manager.start, daemon=True).start()
    
    def _on_stop(self):
        """Stop button handler"""
        self._show_toast("Stopping app...")
        threading.Thread(target=self.app_manager.stop, daemon=True).start()
    
    def _on_restart(self):
        """Restart button handler"""
        self._show_toast("Restarting app...")
        threading.Thread(target=self.app_manager.restart, daemon=True).start()
    
    def _on_exit(self):
        """Exit button handler"""
        self.running = False
    
    def _show_logs(self):
        """Show logs screen"""
        self.current_screen = Screen.LOGS
        self.log_viewer.show_errors_only = False
        self.log_viewer.auto_scroll = True
    
    def _show_errors(self):
        """Show errors screen"""
        self.current_screen = Screen.ERRORS
        self.log_viewer.show_errors_only = True
        self.log_viewer.auto_scroll = True
    
    def _show_home(self):
        """Return to home screen"""
        self.current_screen = Screen.HOME
    
    def _show_toast(self, message: str):
        """Show a toast notification"""
        self.toast_message = message
        self.toast_time = time.time()
    
    def _update_status(self):
        """Update status from app manager"""
        with self._status_lock:
            self._last_status = self.app_manager.get_friendly_status()
            
            if self.log_viewer.show_errors_only:
                self._last_logs = self.app_manager.get_errors(50)
            else:
                self._last_logs = self.app_manager.get_logs(100)
    
    def _handle_events(self):
        """Handle pygame and touch events"""
        # Handle pygame events (works in SDL mode)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.current_screen != Screen.HOME:
                        self._show_home()
                    else:
                        self.running = False
                elif event.key == pygame.K_q:
                    self.running = False
            
            # Handle button events based on current screen
            if self.current_screen == Screen.HOME:
                for btn in self.home_buttons:
                    btn.handle_event(event)
            else:
                self.btn_back.handle_event(event)
                self.btn_scroll_up.handle_event(event)
                self.btn_scroll_down.handle_event(event)
        
        # Handle evdev touch events (for framebuffer mode)
        if self._touch_handler:
            touch_event = self._touch_handler.poll()
            if touch_event:
                event_type, x, y = touch_event
                
                if event_type == 'touch':
                    # Touch press - mark buttons as pressed
                    if self.current_screen == Screen.HOME:
                        for btn in self.home_buttons:
                            if btn.enabled and btn.rect.collidepoint(x, y):
                                btn.pressed = True
                                btn.press_time = time.time()
                    else:
                        for btn in [self.btn_back, self.btn_scroll_up, self.btn_scroll_down]:
                            if btn.enabled and btn.rect.collidepoint(x, y):
                                btn.pressed = True
                                btn.press_time = time.time()
                
                elif event_type == 'release':
                    # Touch release - trigger callbacks
                    if self.current_screen == Screen.HOME:
                        for btn in self.home_buttons:
                            if btn.pressed and btn.rect.collidepoint(x, y):
                                btn.pressed = False
                                if btn.callback:
                                    btn.callback()
                            btn.pressed = False
                    else:
                        for btn in [self.btn_back, self.btn_scroll_up, self.btn_scroll_down]:
                            if btn.pressed and btn.rect.collidepoint(x, y):
                                btn.pressed = False
                                if btn.callback:
                                    btn.callback()
                            btn.pressed = False
    
    def _draw_home_screen(self):
        """Draw the home screen"""
        colors = self.config.colors
        ui = self.config.ui
        
        # Draw buttons
        for btn in self.home_buttons:
            btn.draw(self.screen, self.font)
        
        # Draw info panel
        pygame.draw.rect(self.screen, colors.bg_panel, self.info_rect, 
                        border_radius=ui.panel_radius)
        
        # Draw status info (copy under lock to avoid race condition)
        with self._status_lock:
            status = self._last_status.copy() if self._last_status else {}
        if status:
            y = self.info_rect.top + ui.panel_padding
            x = self.info_rect.left + ui.panel_padding
            
            self.font.size = ui.font_size_small
            
            # Web URL
            if status.get('web_url'):
                url_text = f"Web: {status['web_url']}"
                surf, rect = self.font.render(url_text, colors.text_secondary)
                self.screen.blit(surf, (x, y))
                y += rect.height + 8
            
            # Uptime
            if status.get('uptime'):
                uptime_text = f"Uptime: {status['uptime']}"
                surf, rect = self.font.render(uptime_text, colors.text_secondary)
                self.screen.blit(surf, (x, y))
                y += rect.height + 8
            
            # Error count
            if status.get('error_count', 0) > 0:
                err_text = f"Errors: {status['error_count']}"
                surf, rect = self.font.render(err_text, colors.warning)
                self.screen.blit(surf, (x, y))
                y += rect.height + 8
            
            # Last error (truncated to fit panel)
            if status.get('last_error'):
                # Calculate max chars that fit in panel width
                max_chars = 35  # Conservative for small screens
                err = status['last_error'][:max_chars]
                if len(status['last_error']) > max_chars:
                    err += "..."
                self.font.size = ui.font_size_tiny
                # Only draw if there's room in the panel
                if y + ui.font_size_tiny < self.info_rect.bottom - ui.panel_padding:
                    surf, rect = self.font.render(err, colors.error)
                    self.screen.blit(surf, (x, y))
    
    def _draw_system_stats(self):
        """Draw system stats (CPU, RAM, temp) in the bottom-right corner."""
        if not self.system_stats.is_available:
            return
        
        colors = self.config.colors
        ui = self.config.ui
        
        # Update stats (uses internal caching, won't spam)
        self.system_stats.update()
        
        # Build stats text lines
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
        
        # Calculate position (bottom-right corner)
        self.font.size = ui.font_size_tiny
        line_height = ui.font_size_tiny + 2
        padding = 6
        
        # Measure text width for background
        max_width = 0
        for line in stats_lines:
            surf, rect = self.font.render(line, colors.text_secondary)
            max_width = max(max_width, rect.width)
        
        # Background box dimensions
        box_width = max_width + padding * 2
        box_height = len(stats_lines) * line_height + padding * 2
        
        # Position in bottom-right
        box_x = self.config.display.width - box_width - ui.button_margin
        box_y = self.config.display.height - box_height - ui.button_margin
        
        # Draw semi-transparent background
        box_rect = pygame.Rect(box_x, box_y, box_width, box_height)
        box_surf = pygame.Surface((box_width, box_height), pygame.SRCALPHA)
        pygame.draw.rect(box_surf, (*colors.bg_secondary, 200), 
                        box_surf.get_rect(), border_radius=4)
        self.screen.blit(box_surf, box_rect)
        
        # Draw stats text
        y = box_y + padding
        for line in stats_lines:
            # Color-code temperature if hot
            if line.startswith("TMP:"):
                temp = self.system_stats.cpu_temp
                if temp > 80:
                    text_color = colors.error
                elif temp > 70:
                    text_color = colors.warning
                else:
                    text_color = colors.text_secondary
            # Color-code CPU if high
            elif line.startswith("CPU:"):
                cpu = self.system_stats.cpu_percent
                if cpu > 90:
                    text_color = colors.error
                elif cpu > 75:
                    text_color = colors.warning
                else:
                    text_color = colors.text_secondary
            # Color-code RAM if high
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
    
    def _draw_logs_screen(self):
        """Draw the logs/errors screen"""
        colors = self.config.colors
        
        # Title
        title = "Error Log" if self.log_viewer.show_errors_only else "Application Log"
        self.font.size = self.config.ui.font_size_medium
        surf, rect = self.font.render(title, colors.text_primary)
        rect.topleft = (self.config.ui.button_margin, 
                       self.config.ui.status_bar_height + 5)
        self.screen.blit(surf, rect)
        
        # Update logs (copy under lock to avoid race condition)
        with self._status_lock:
            logs_copy = list(self._last_logs)
        self.log_viewer.set_logs(logs_copy)
        
        # Draw log viewer (offset for title)
        original_rect = self.log_viewer.rect
        self.log_viewer.rect = pygame.Rect(
            original_rect.x,
            original_rect.y + 30,
            original_rect.width,
            original_rect.height - 30
        )
        self.log_viewer.draw(self.screen, self.mono_font)
        self.log_viewer.rect = original_rect
        
        # Draw navigation buttons
        self.btn_back.draw(self.screen, self.font)
        self.btn_scroll_up.draw(self.screen, self.font)
        self.btn_scroll_down.draw(self.screen, self.font)
    
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
        
        # Fade out
        alpha = 255
        if elapsed > self.toast_duration - 0.5:
            alpha = int(255 * (self.toast_duration - elapsed) / 0.5)
        
        # Create toast surface
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
        
        # Draw toast background
        toast_surf = pygame.Surface(toast_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(toast_surf, (*colors.bg_secondary, alpha), 
                        toast_surf.get_rect(), border_radius=8)
        self.screen.blit(toast_surf, toast_rect)
        
        # Draw text
        text_rect.center = toast_rect.center
        self.screen.blit(text_surf, text_rect)
    
    def _draw(self):
        """Draw the current screen"""
        colors = self.config.colors
        
        # Clear screen
        self.screen.fill(colors.bg_primary)
        
        # Draw status bar
        self.status_bar.update(self._last_status)
        self.status_bar.draw(self.screen, self.font)
        
        # Draw current screen content
        if self.current_screen == Screen.HOME:
            self._draw_home_screen()
        elif self.current_screen in [Screen.LOGS, Screen.ERRORS]:
            self._draw_logs_screen()
        
        # Draw system stats overlay (bottom-right corner, all screens)
        self._draw_system_stats()
        
        # Draw toast notification
        self._draw_toast()
        
        # Update display
        if self._using_framebuffer and self._fb_display:
            self._fb_display.update()
        else:
            pygame.display.flip()
    
    def run(self):
        """Main application loop"""
        self.running = True
        
        # Auto-start app if configured
        if self.config.app.auto_start_app:
            self._show_toast("Auto-starting app...")
            threading.Thread(target=self.app_manager.start, daemon=True).start()
        
        # Start status update thread
        last_update = 0
        update_interval = self.config.app.status_refresh_interval
        
        while self.running:
            # Handle events
            self._handle_events()
            
            # Update status periodically
            now = time.time()
            if now - last_update > update_interval:
                self._update_status()
                last_update = now
            
            # Draw
            self._draw()
            
            # Control frame rate
            self.clock.tick(30)
        
        # Cleanup
        if self._using_framebuffer and self._fb_display:
            self._fb_display.clear()
            self._fb_display.update()
        pygame.quit()
    
    def cleanup(self):
        """Clean up resources"""
        self.app_manager.cleanup()


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Film Scanner Touch Screen UI')
    parser.add_argument('--preset', choices=['3.5_480x320', '3.5_320x240', '5_800x480', '7_1024x600'],
                       help='Screen size preset')
    parser.add_argument('--windowed', action='store_true',
                       help='Run in windowed mode (for testing)')
    parser.add_argument('--no-auto-start', action='store_true',
                       help="Don't auto-start the web app")
    
    args = parser.parse_args()
    
    # Load config
    if args.preset:
        from touchscreen_config import PRESETS
        config = PRESETS[args.preset]
    else:
        config = get_config()
    
    # Apply command line options
    if args.windowed:
        config.display.fullscreen = False
        config.display.show_cursor = True
    
    if args.no_auto_start:
        config.app.auto_start_app = False
    
    # Create and run UI
    ui = TouchScreenUI(config)
    
    try:
        ui.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        ui.cleanup()


if __name__ == '__main__':
    main()
