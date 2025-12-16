#!/usr/bin/env python3
"""
Touch Screen Configuration for Film Scanner
Configuration settings for 3.5" TFT touch screen displays.

Supports common 3.5" TFT screens:
- 480x320 resolution (most common)
- 320x240 resolution (older screens)
- Various drivers (ILI9486, ILI9341, etc.)
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Tuple, Optional

@dataclass
class ColorTheme:
    """
    Color scheme for the UI - matches web UI dark theme (style.css)
    
    Web UI CSS variables reference:
    --background: #111827, --surface: #1f2937, --surface-light: #374151
    --text: #f9fafb, --text-secondary: #9ca3af, --border: #4b5563
    --primary: #2563eb, --success: #10b981, --warning: #f59e0b, --danger: #ef4444
    """
    # Background colors (matching web UI)
    bg_primary: Tuple[int, int, int] = (17, 24, 39)       # #111827 - main background
    bg_secondary: Tuple[int, int, int] = (31, 41, 55)     # #1f2937 - surface/panel
    bg_panel: Tuple[int, int, int] = (55, 65, 81)         # #374151 - surface-light
    
    # Text colors (matching web UI)
    text_primary: Tuple[int, int, int] = (249, 250, 251)  # #f9fafb - main text
    text_secondary: Tuple[int, int, int] = (156, 163, 175) # #9ca3af - secondary text
    text_muted: Tuple[int, int, int] = (107, 114, 128)    # #6b7280 - muted/disabled
    
    # Status colors (matching web UI)
    success: Tuple[int, int, int] = (16, 185, 129)        # #10b981 - green
    warning: Tuple[int, int, int] = (245, 158, 11)        # #f59e0b - amber
    error: Tuple[int, int, int] = (239, 68, 68)           # #ef4444 - red
    info: Tuple[int, int, int] = (37, 99, 235)            # #2563eb - blue
    
    # Button colors (matching web UI)
    btn_primary: Tuple[int, int, int] = (37, 99, 235)     # #2563eb - primary blue
    btn_primary_hover: Tuple[int, int, int] = (30, 64, 175)  # #1e40af - primary-dark
    btn_secondary: Tuple[int, int, int] = (107, 114, 128) # #6b7280 - secondary gray
    btn_secondary_hover: Tuple[int, int, int] = (55, 65, 81)  # #374151 - surface-light
    btn_danger: Tuple[int, int, int] = (239, 68, 68)      # #ef4444 - red
    btn_danger_hover: Tuple[int, int, int] = (220, 38, 38)  # darker red
    btn_success: Tuple[int, int, int] = (16, 185, 129)    # #10b981 - green
    btn_success_hover: Tuple[int, int, int] = (5, 150, 105)  # #059669 - success-dark
    btn_warning: Tuple[int, int, int] = (245, 158, 11)    # #f59e0b - warning
    btn_warning_hover: Tuple[int, int, int] = (217, 119, 6)  # #d97706 - warning-dark
    
    # Border colors (matching web UI)
    border: Tuple[int, int, int] = (75, 85, 99)           # #4b5563 - border
    border_active: Tuple[int, int, int] = (37, 99, 235)   # #2563eb - primary (focus)


@dataclass
class DisplayConfig:
    """Display configuration"""
    # Screen dimensions (common 3.5" TFT sizes)
    width: int = 480
    height: int = 320
    
    # Framebuffer device (for direct rendering)
    framebuffer: str = "/dev/fb1"  # Usually fb1 for SPI displays
    
    # Touch input device
    touch_device: str = "/dev/input/touchscreen"
    
    # Display rotation (0, 90, 180, 270)
    rotation: int = 0
    
    # Swap X/Y touch coordinates (some screens need this)
    touch_swap_xy: bool = False
    
    # Invert touch coordinates
    touch_invert_x: bool = False
    touch_invert_y: bool = False
    
    # Use fullscreen mode
    fullscreen: bool = True
    
    # Show mouse cursor (usually off for touch screens)
    show_cursor: bool = False
    
    # Backlight GPIO pin (if controllable)
    backlight_pin: Optional[int] = 18
    
    # Screen timeout in seconds (0 = disabled)
    screen_timeout: int = 300  # 5 minutes


@dataclass
class UIConfig:
    """UI element configuration"""
    # Font sizes (optimized for 480x320)
    font_size_large: int = 28
    font_size_medium: int = 20
    font_size_small: int = 16
    font_size_tiny: int = 12
    
    # Font family
    font_family: str = "DejaVu Sans"  # Good Unicode support
    font_family_mono: str = "DejaVu Sans Mono"  # For logs
    
    # Button dimensions
    button_height: int = 50
    button_width: int = 140
    button_margin: int = 8
    button_radius: int = 8
    
    # Panel configuration
    panel_padding: int = 12
    panel_radius: int = 10
    
    # Status bar height
    status_bar_height: int = 36
    
    # Log viewer
    log_lines_visible: int = 8
    log_line_height: int = 20
    
    # Animation
    animation_speed: float = 0.15
    touch_feedback_duration: float = 0.1


@dataclass 
class AppConfig:
    """Application behavior configuration"""
    # Auto-start web app on boot
    auto_start_app: bool = True
    
    # Auto-restart crashed app
    auto_restart: bool = True
    auto_restart_delay: float = 5.0
    
    # Refresh intervals (seconds)
    status_refresh_interval: float = 2.0
    log_refresh_interval: float = 1.0
    
    # Web app settings
    web_app_port: int = 5000
    web_app_path: str = ""  # Auto-detected if empty
    
    # Log buffer size
    max_log_entries: int = 500
    max_error_entries: int = 100


@dataclass
class TouchScreenConfig:
    """Main configuration container"""
    display: DisplayConfig = field(default_factory=DisplayConfig)
    colors: ColorTheme = field(default_factory=ColorTheme)
    ui: UIConfig = field(default_factory=UIConfig)
    app: AppConfig = field(default_factory=AppConfig)
    
    # Metadata
    config_version: int = 1
    
    def save(self, path: str = None):
        """Save configuration to JSON file"""
        if path is None:
            path = self._get_default_path()
        
        config_dict = {
            'config_version': self.config_version,
            'display': asdict(self.display),
            'colors': asdict(self.colors),
            'ui': asdict(self.ui),
            'app': asdict(self.app),
        }
        
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with open(path, 'w') as f:
            json.dump(config_dict, f, indent=2)
    
    @classmethod
    def load(cls, path: str = None) -> 'TouchScreenConfig':
        """Load configuration from JSON file"""
        if path is None:
            path = cls._get_default_path()
        
        if not os.path.exists(path):
            return cls()  # Return defaults
        
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            config = cls()
            
            if 'display' in data:
                for k, v in data['display'].items():
                    if hasattr(config.display, k):
                        setattr(config.display, k, v)
            
            if 'colors' in data:
                for k, v in data['colors'].items():
                    if hasattr(config.colors, k):
                        setattr(config.colors, k, tuple(v) if isinstance(v, list) else v)
            
            if 'ui' in data:
                for k, v in data['ui'].items():
                    if hasattr(config.ui, k):
                        setattr(config.ui, k, v)
            
            if 'app' in data:
                for k, v in data['app'].items():
                    if hasattr(config.app, k):
                        setattr(config.app, k, v)
            
            return config
            
        except Exception as e:
            print(f"Error loading config: {e}")
            return cls()
    
    @staticmethod
    def _get_default_path() -> str:
        """Get default config file path"""
        config_dir = Path.home() / ".film_scanner"
        return str(config_dir / "touchscreen_config.json")


# Preset configurations for common screens
PRESETS = {
    '3.5_480x320': TouchScreenConfig(
        display=DisplayConfig(width=480, height=320),
        ui=UIConfig(font_size_large=28, font_size_medium=20),
    ),
    
    '3.5_320x240': TouchScreenConfig(
        display=DisplayConfig(width=320, height=240),
        ui=UIConfig(
            font_size_large=20,
            font_size_medium=16,
            font_size_small=12,
            font_size_tiny=10,
            button_height=40,
            button_width=100,
            log_lines_visible=6,
        ),
    ),
    
    '5_800x480': TouchScreenConfig(
        display=DisplayConfig(width=800, height=480),
        ui=UIConfig(
            font_size_large=36,
            font_size_medium=24,
            font_size_small=18,
            font_size_tiny=14,
            button_height=60,
            button_width=180,
            log_lines_visible=12,
        ),
    ),
    
    '7_1024x600': TouchScreenConfig(
        display=DisplayConfig(width=1024, height=600),
        ui=UIConfig(
            font_size_large=42,
            font_size_medium=28,
            font_size_small=20,
            font_size_tiny=16,
            button_height=70,
            button_width=200,
            log_lines_visible=15,
        ),
    ),
}


def get_config(preset: str = None) -> TouchScreenConfig:
    """
    Get configuration, optionally from a preset.
    
    Args:
        preset: Name of preset ('3.5_480x320', '3.5_320x240', etc.)
        
    Returns:
        TouchScreenConfig instance
    """
    if preset and preset in PRESETS:
        return PRESETS[preset]
    
    # Try to load saved config
    return TouchScreenConfig.load()


def detect_screen_size() -> Tuple[int, int]:
    """
    Attempt to detect the screen size.
    
    Returns:
        (width, height) tuple
    """
    try:
        import pygame
        pygame.init()
        info = pygame.display.Info()
        size = (info.current_w, info.current_h)
        pygame.quit()
        return size
    except:
        pass
    
    # Try reading from framebuffer
    try:
        with open('/sys/class/graphics/fb1/virtual_size', 'r') as f:
            w, h = f.read().strip().split(',')
            return (int(w), int(h))
    except:
        pass
    
    # Default to common 3.5" size
    return (480, 320)


if __name__ == '__main__':
    # Print current configuration
    config = get_config()
    print("Current Touch Screen Configuration:")
    print(f"  Display: {config.display.width}x{config.display.height}")
    print(f"  Framebuffer: {config.display.framebuffer}")
    print(f"  Auto-start: {config.app.auto_start_app}")
    print(f"  Auto-restart: {config.app.auto_restart}")
    
    # Detect screen
    detected = detect_screen_size()
    print(f"\nDetected screen size: {detected[0]}x{detected[1]}")
    
    # Save default config
    config.save()
    print(f"\nConfig saved to: {TouchScreenConfig._get_default_path()}")
