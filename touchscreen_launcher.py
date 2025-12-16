#!/usr/bin/env python3
"""
Film Scanner - Touch Screen Launcher
Main home screen with app icons for launching different applications.

This is the main entry point for the touchscreen interface.
"""

import pygame
import pygame.freetype
import subprocess
import sys
import os
import time
from datetime import datetime
from typing import List, Optional

from touchscreen_config import TouchScreenConfig, get_config
from touchscreen_common import (
    setup_framebuffer_env, 
    BaseTouchApp, 
    AppIcon, 
    Button,
    SystemStatsMonitor,
    PSUTIL_AVAILABLE
)

# Set up framebuffer before pygame init
_using_framebuffer = setup_framebuffer_env()


class AppDefinition:
    """Definition of a launchable app"""
    
    def __init__(self, name: str, icon: str, script: str, 
                 color: tuple = None, description: str = ""):
        self.name = name
        self.icon = icon
        self.script = script  # Python script to run
        self.color = color
        self.description = description


# Define available apps
APPS = [
    AppDefinition(
        name="Scanner",
        icon="📷",
        script="touchscreen_ui.py",
        color=(16, 185, 129),  # Green
        description="Film scanner control"
    ),
    AppDefinition(
        name="Terminal",
        icon="💻",
        script="touchscreen_terminal.py",
        color=(37, 99, 235),  # Blue
        description="View system logs"
    ),
    AppDefinition(
        name="Debug",
        icon="🔧",
        script="touchscreen_debug.py",
        color=(245, 158, 11),  # Amber
        description="Debug & diagnostics"
    ),
    AppDefinition(
        name="Settings",
        icon="⚙️",
        script="touchscreen_settings.py",
        color=(107, 114, 128),  # Gray
        description="System settings"
    ),
]


class LauncherApp(BaseTouchApp):
    """Main launcher/home screen application"""
    
    APP_NAME = "Film Scanner"
    
    def __init__(self, config: TouchScreenConfig = None):
        super().__init__(config)
        self.exit_to_launcher = False  # Launcher exits completely
        
        # Get script directory for launching apps
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Create app icons
        self._create_app_icons()
        
        # Shutdown/power button
        self._create_power_button()
    
    def _create_app_icons(self):
        """Create the app icon grid"""
        self.app_icons: List[AppIcon] = []
        
        w = self.config.display.width
        h = self.config.display.height
        ui = self.config.ui
        colors = self.config.colors
        
        # Calculate grid layout
        margin = ui.button_margin
        header_h = ui.status_bar_height + margin
        
        # 2x2 grid for apps
        num_cols = 2
        num_rows = 2
        
        # Icon size
        available_w = w - margin * (num_cols + 1)
        available_h = h - header_h - margin * (num_rows + 1) - 50  # Reserve space for footer
        
        icon_w = available_w // num_cols
        icon_h = available_h // num_rows
        
        for i, app_def in enumerate(APPS[:4]):  # Max 4 apps on home screen
            row = i // num_cols
            col = i % num_cols
            
            x = margin + col * (icon_w + margin)
            y = header_h + margin + row * (icon_h + margin)
            
            icon = AppIcon(
                rect=pygame.Rect(x, y, icon_w, icon_h),
                name=app_def.name,
                icon=app_def.icon,
                callback=lambda app=app_def: self._launch_app(app),
                color=app_def.color or colors.btn_primary,
                config=self.config
            )
            self.app_icons.append(icon)
    
    def _create_power_button(self):
        """Create fix camera button (replaces exit - use ESC/Q to exit if needed)"""
        ui = self.config.ui
        colors = self.config.colors
        
        btn_w = 100
        btn_h = 36
        margin = ui.button_margin
        
        self.fix_camera_button = Button(
            rect=pygame.Rect(margin, self.config.display.height - btn_h - margin, 
                           btn_w, btn_h),
            text="FIX CAM",
            callback=self._on_fix_camera,
            color=colors.btn_warning,
            hover_color=colors.btn_warning_hover,
            icon="📷",
            font_size=ui.font_size_small,
            config=self.config
        )
    
    def _launch_app(self, app_def: AppDefinition):
        """Launch an app"""
        script_path = os.path.join(self.script_dir, app_def.script)
        
        if not os.path.exists(script_path):
            self._show_toast(f"App not found: {app_def.name}")
            return
        
        self._show_toast(f"Launching {app_def.name}...")
        
        # Close pygame before launching
        pygame.quit()
        
        # Build command
        cmd = [sys.executable, script_path]
        if '--windowed' in sys.argv:
            cmd.append('--windowed')
        
        try:
            # Run the app and wait for it to finish
            result = subprocess.run(cmd, cwd=self.script_dir)
            
            # Re-initialize pygame after app returns
            self._reinit_pygame()
            
            if result.returncode != 0:
                self._show_toast(f"{app_def.name} exited with error")
        except Exception as e:
            self._reinit_pygame()
            self._show_toast(f"Error: {str(e)[:30]}")
    
    def _reinit_pygame(self):
        """Re-initialize pygame after returning from an app"""
        pygame.init()
        pygame.freetype.init()
        
        if not self.config.display.show_cursor:
            pygame.mouse.set_visible(False)
        
        display_flags = pygame.FULLSCREEN if self.config.display.fullscreen else 0
        self.screen = pygame.display.set_mode(
            (self.config.display.width, self.config.display.height),
            display_flags
        )
        pygame.display.set_caption(self.APP_NAME)
        
        # Reload fonts
        self.font = pygame.freetype.SysFont(
            self.config.ui.font_family, 
            self.config.ui.font_size_medium
        )
        self.mono_font = pygame.freetype.SysFont(
            self.config.ui.font_family_mono,
            self.config.ui.font_size_tiny
        )
        
        # Reset clock
        self.clock = pygame.time.Clock()
    
    def _on_fix_camera(self):
        """Fix camera connection by killing gphoto2/gvfs processes"""
        self._show_toast("Fixing camera...")
        
        import subprocess as sp
        import time as t
        
        # Kill processes that can block camera access
        processes_to_kill = [
            "gphoto2", "gvfsd-gphoto2", "gvfs-gphoto2-volume-monitor",
            "gvfsd-mtp", "gvfsd-ptp", "PTPCamera"
        ]
        
        for proc in processes_to_kill:
            try:
                sp.run(["killall", "-9", proc], capture_output=True, timeout=2)
            except:
                pass
        
        # Kill any gvfsd processes
        try:
            sp.run(["pkill", "-9", "-f", "gvfsd"], capture_output=True, timeout=2)
        except:
            pass
        
        # Unmount any auto-mounted camera
        try:
            sp.run(["gio", "mount", "-u", "-f", "gphoto2://"], capture_output=True, timeout=5)
        except:
            pass
        
        t.sleep(1)
        self._show_toast("Camera reset - restart Scanner app")
    
    def handle_events(self):
        """Handle pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                    self.running = False
            
            # Handle app icon touches
            for icon in self.app_icons:
                icon.handle_event(event)
            
            # Handle fix camera button
            self.fix_camera_button.handle_event(event)
    
    def draw(self):
        """Draw the launcher screen"""
        colors = self.config.colors
        ui = self.config.ui
        
        # Clear screen
        self.screen.fill(colors.bg_primary)
        
        # Draw header
        self._draw_header("Film Scanner")
        
        # Draw app icons
        for icon in self.app_icons:
            icon.draw(self.screen, self.font)
        
        # Draw fix camera button
        self.fix_camera_button.draw(self.screen, self.font)
        
        # Draw date in footer area
        date_str = datetime.now().strftime("%A, %B %d")
        self.font.size = ui.font_size_small
        date_surf, date_rect = self.font.render(date_str, colors.text_muted)
        date_rect.midbottom = (self.config.display.width // 2, 
                              self.config.display.height - ui.button_margin)
        self.screen.blit(date_surf, date_rect)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Film Scanner Touch Screen Launcher')
    parser.add_argument('--preset', choices=['3.5_480x320', '3.5_320x240', '5_800x480', '7_1024x600'],
                       help='Screen size preset')
    parser.add_argument('--windowed', action='store_true',
                       help='Run in windowed mode (for testing)')
    
    args = parser.parse_args()
    
    # Load config
    if args.preset:
        from touchscreen_config import PRESETS
        config = PRESETS[args.preset]
    else:
        config = get_config()
    
    if args.windowed:
        config.display.fullscreen = False
        config.display.show_cursor = True
    
    # Run launcher
    launcher = LauncherApp(config)
    
    try:
        launcher.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        launcher.cleanup()


if __name__ == '__main__':
    main()
