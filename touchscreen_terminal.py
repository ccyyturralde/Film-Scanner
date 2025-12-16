#!/usr/bin/env python3
"""
Film Scanner - Touch Screen Terminal Viewer
A simple terminal/log viewer for the touchscreen interface.

Shows system logs, dmesg, and app logs in a scrollable view.
"""

import pygame
import pygame.freetype
import subprocess
import sys
import os
import time
from datetime import datetime
from typing import List, Tuple
from enum import Enum, auto

from touchscreen_config import TouchScreenConfig, get_config
from touchscreen_common import (
    setup_framebuffer_env,
    BaseTouchApp,
    Button,
    PSUTIL_AVAILABLE
)

# Set up framebuffer before pygame init
_using_framebuffer = setup_framebuffer_env()


class LogSource(Enum):
    """Available log sources"""
    SYSLOG = auto()
    DMESG = auto()
    APP_LOG = auto()
    JOURNALCTL = auto()


class TerminalApp(BaseTouchApp):
    """Terminal/log viewer application"""
    
    APP_NAME = "Terminal"
    
    # Log source configurations
    LOG_SOURCES = {
        LogSource.SYSLOG: {
            "name": "System",
            "cmd": ["tail", "-n", "100", "/var/log/syslog"],
            "icon": "📋"
        },
        LogSource.DMESG: {
            "name": "Kernel",
            "cmd": ["dmesg", "--time-format=short", "-T"],
            "icon": "🐧"
        },
        LogSource.JOURNALCTL: {
            "name": "Journal",
            "cmd": ["journalctl", "-n", "100", "--no-pager"],
            "icon": "📜"
        },
        LogSource.APP_LOG: {
            "name": "Scanner",
            "file": os.path.expanduser("~/.film_scanner/scanner.log"),
            "icon": "📷"
        },
    }
    
    def __init__(self, config: TouchScreenConfig = None):
        super().__init__(config)
        
        self.current_source = LogSource.JOURNALCTL
        self.log_lines: List[str] = []
        self.scroll_offset = 0
        self.auto_scroll = True
        self.last_refresh = 0
        self.refresh_interval = 5.0  # Refresh logs every 5 seconds
        
        self._create_ui()
        self._refresh_logs()
    
    def _create_ui(self):
        """Create UI elements"""
        ui = self.config.ui
        colors = self.config.colors
        w = self.config.display.width
        h = self.config.display.height
        margin = ui.button_margin
        
        # Header area
        header_h = ui.status_bar_height
        
        # Footer buttons area
        btn_h = 40
        footer_y = h - btn_h - margin
        
        # Log view area
        self.log_rect = pygame.Rect(
            margin, 
            header_h + margin,
            w - margin * 2,
            footer_y - header_h - margin * 2
        )
        
        # Calculate visible lines
        self.line_height = ui.font_size_tiny + 2
        self.visible_lines = (self.log_rect.height - ui.panel_padding * 2) // self.line_height
        
        # Source selector buttons (top row of footer)
        btn_w = (w - margin * 5) // 4
        
        self.source_buttons: List[Tuple[Button, LogSource]] = []
        
        x = margin
        for source in [LogSource.JOURNALCTL, LogSource.SYSLOG, LogSource.DMESG, LogSource.APP_LOG]:
            src_config = self.LOG_SOURCES[source]
            btn = Button(
                rect=pygame.Rect(x, footer_y - btn_h - margin, btn_w, btn_h),
                text=src_config["name"],
                callback=lambda s=source: self._set_source(s),
                color=colors.btn_primary if source == self.current_source else colors.btn_secondary,
                hover_color=colors.btn_primary_hover,
                icon=src_config["icon"],
                font_size=ui.font_size_tiny,
                config=self.config
            )
            self.source_buttons.append((btn, source))
            x += btn_w + margin
        
        # Navigation buttons (bottom row)
        nav_btn_w = (w - margin * 5) // 4
        
        self.btn_back = Button(
            rect=pygame.Rect(margin, footer_y, nav_btn_w, btn_h),
            text="Back",
            callback=self._on_back,
            color=colors.btn_secondary,
            hover_color=colors.btn_secondary_hover,
            icon="←",
            font_size=ui.font_size_small,
            config=self.config
        )
        
        self.btn_scroll_up = Button(
            rect=pygame.Rect(margin + nav_btn_w + margin, footer_y, nav_btn_w, btn_h),
            text="▲ Up",
            callback=self._scroll_up,
            color=colors.btn_secondary,
            hover_color=colors.btn_secondary_hover,
            font_size=ui.font_size_small,
            config=self.config
        )
        
        self.btn_scroll_down = Button(
            rect=pygame.Rect(margin + (nav_btn_w + margin) * 2, footer_y, nav_btn_w, btn_h),
            text="▼ Down",
            callback=self._scroll_down,
            color=colors.btn_secondary,
            hover_color=colors.btn_secondary_hover,
            font_size=ui.font_size_small,
            config=self.config
        )
        
        self.btn_refresh = Button(
            rect=pygame.Rect(margin + (nav_btn_w + margin) * 3, footer_y, nav_btn_w, btn_h),
            text="Refresh",
            callback=self._refresh_logs,
            color=colors.btn_primary,
            hover_color=colors.btn_primary_hover,
            icon="🔄",
            font_size=ui.font_size_small,
            config=self.config
        )
    
    def _set_source(self, source: LogSource):
        """Change log source"""
        self.current_source = source
        self.scroll_offset = 0
        self.auto_scroll = True
        self._refresh_logs()
        
        # Update button colors
        colors = self.config.colors
        for btn, src in self.source_buttons:
            if src == source:
                btn.color = colors.btn_primary
            else:
                btn.color = colors.btn_secondary
    
    def _refresh_logs(self):
        """Refresh log content from current source"""
        self.last_refresh = time.time()
        source_config = self.LOG_SOURCES[self.current_source]
        
        try:
            if "cmd" in source_config:
                # Run command to get logs
                result = subprocess.run(
                    source_config["cmd"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    self.log_lines = result.stdout.strip().split('\n')
                else:
                    self.log_lines = [f"Error: {result.stderr[:100]}"]
            
            elif "file" in source_config:
                # Read from file
                filepath = source_config["file"]
                if os.path.exists(filepath):
                    with open(filepath, 'r') as f:
                        # Read last 100 lines
                        lines = f.readlines()
                        self.log_lines = [l.rstrip() for l in lines[-100:]]
                else:
                    self.log_lines = ["Log file not found:", filepath]
        
        except subprocess.TimeoutExpired:
            self.log_lines = ["Timeout reading logs"]
        except Exception as e:
            self.log_lines = [f"Error: {str(e)}"]
        
        # Auto-scroll to bottom
        if self.auto_scroll:
            self.scroll_offset = max(0, len(self.log_lines) - self.visible_lines)
    
    def _scroll_up(self):
        """Scroll up"""
        self.scroll_offset = max(0, self.scroll_offset - 5)
        self.auto_scroll = False
    
    def _scroll_down(self):
        """Scroll down"""
        max_offset = max(0, len(self.log_lines) - self.visible_lines)
        self.scroll_offset = min(max_offset, self.scroll_offset + 5)
        if self.scroll_offset >= max_offset:
            self.auto_scroll = True
    
    def _on_back(self):
        """Return to launcher"""
        self.running = False
    
    def handle_events(self):
        """Handle events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                self.exit_to_launcher = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_UP:
                    self._scroll_up()
                elif event.key == pygame.K_DOWN:
                    self._scroll_down()
                elif event.key == pygame.K_r:
                    self._refresh_logs()
            
            # Handle button events
            for btn, _ in self.source_buttons:
                btn.handle_event(event)
            
            self.btn_back.handle_event(event)
            self.btn_scroll_up.handle_event(event)
            self.btn_scroll_down.handle_event(event)
            self.btn_refresh.handle_event(event)
    
    def update(self):
        """Update - auto-refresh logs periodically"""
        if time.time() - self.last_refresh > self.refresh_interval:
            self._refresh_logs()
    
    def draw(self):
        """Draw the terminal view"""
        colors = self.config.colors
        ui = self.config.ui
        
        # Clear screen
        self.screen.fill(colors.bg_primary)
        
        # Draw header
        source_name = self.LOG_SOURCES[self.current_source]["name"]
        self._draw_header(f"Terminal - {source_name}")
        
        # Draw log panel background
        pygame.draw.rect(self.screen, colors.bg_panel, self.log_rect, 
                        border_radius=ui.panel_radius)
        
        # Draw log lines
        self.mono_font.size = ui.font_size_tiny
        padding = ui.panel_padding
        y = self.log_rect.top + padding
        
        max_chars = (self.log_rect.width - padding * 2) // 7
        
        for i, line in enumerate(self.log_lines[self.scroll_offset:self.scroll_offset + self.visible_lines]):
            # Color based on content
            line_lower = line.lower()
            if 'error' in line_lower or 'fail' in line_lower:
                text_color = colors.error
            elif 'warn' in line_lower:
                text_color = colors.warning
            elif 'success' in line_lower or 'ok' in line_lower:
                text_color = colors.success
            else:
                text_color = colors.text_secondary
            
            # Truncate line if too long
            display_line = line[:max_chars] if len(line) > max_chars else line
            
            surf, rect = self.mono_font.render(display_line, text_color)
            rect.topleft = (self.log_rect.left + padding, y)
            self.screen.blit(surf, rect)
            
            y += self.line_height
        
        # Draw scroll indicators
        if self.scroll_offset > 0:
            pygame.draw.polygon(self.screen, colors.text_muted, [
                (self.log_rect.right - 20, self.log_rect.top + 10),
                (self.log_rect.right - 10, self.log_rect.top + 20),
                (self.log_rect.right - 30, self.log_rect.top + 20)
            ])
        
        if self.scroll_offset < len(self.log_lines) - self.visible_lines:
            pygame.draw.polygon(self.screen, colors.text_muted, [
                (self.log_rect.right - 20, self.log_rect.bottom - 10),
                (self.log_rect.right - 10, self.log_rect.bottom - 20),
                (self.log_rect.right - 30, self.log_rect.bottom - 20)
            ])
        
        # Draw line count indicator
        self.font.size = ui.font_size_tiny
        count_text = f"Lines: {len(self.log_lines)} | Showing: {self.scroll_offset+1}-{min(self.scroll_offset + self.visible_lines, len(self.log_lines))}"
        count_surf, count_rect = self.font.render(count_text, colors.text_muted)
        count_rect.bottomright = (self.log_rect.right - padding, self.log_rect.top - 2)
        self.screen.blit(count_surf, count_rect)
        
        # Draw source selector buttons
        for btn, _ in self.source_buttons:
            btn.draw(self.screen, self.font)
        
        # Draw navigation buttons
        self.btn_back.draw(self.screen, self.font)
        self.btn_scroll_up.draw(self.screen, self.font)
        self.btn_scroll_down.draw(self.screen, self.font)
        self.btn_refresh.draw(self.screen, self.font)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Film Scanner Terminal Viewer')
    parser.add_argument('--preset', choices=['3.5_480x320', '3.5_320x240', '5_800x480', '7_1024x600'],
                       help='Screen size preset')
    parser.add_argument('--windowed', action='store_true',
                       help='Run in windowed mode (for testing)')
    
    args = parser.parse_args()
    
    if args.preset:
        from touchscreen_config import PRESETS
        config = PRESETS[args.preset]
    else:
        config = get_config()
    
    if args.windowed:
        config.display.fullscreen = False
        config.display.show_cursor = True
    
    app = TerminalApp(config)
    
    try:
        app.run()
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        app.cleanup()


if __name__ == '__main__':
    main()
