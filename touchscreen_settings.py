#!/usr/bin/env python3
"""
Film Scanner - Touch Screen Settings
System settings and configuration for the touchscreen interface.

Features:
- Display brightness (if supported)
- Screen timeout settings
- Network info
- System info (Pi model, OS, etc.)
- Shutdown/Reboot options
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
    Button,
    PSUTIL_AVAILABLE
)

# Set up framebuffer before pygame init
_using_framebuffer = setup_framebuffer_env()


class SettingsApp(BaseTouchApp):
    """Settings application"""
    
    APP_NAME = "Settings"
    
    def __init__(self, config: TouchScreenConfig = None):
        super().__init__(config)
        
        self.system_info = self._gather_system_info()
        self._create_ui()
    
    def _gather_system_info(self) -> dict:
        """Gather system information"""
        info = {
            "hostname": "Unknown",
            "ip_address": "Unknown",
            "pi_model": "Unknown",
            "os_version": "Unknown",
            "python_version": sys.version.split()[0],
            "uptime": "Unknown",
            "memory_total": "Unknown",
            "disk_free": "Unknown",
        }
        
        # Hostname
        try:
            import socket
            info["hostname"] = socket.gethostname()
            
            # IP Address
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                info["ip_address"] = s.getsockname()[0]
            except:
                pass
            finally:
                s.close()
        except:
            pass
        
        # Pi Model
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read().strip().replace('\x00', '')
                # Shorten the model name
                if 'Raspberry Pi' in model:
                    info["pi_model"] = model.replace('Raspberry Pi ', 'Pi ')
                else:
                    info["pi_model"] = model[:30]
        except:
            pass
        
        # OS Version
        try:
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if line.startswith('PRETTY_NAME='):
                        info["os_version"] = line.split('=')[1].strip().strip('"')[:25]
                        break
        except:
            pass
        
        # Uptime
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.read().split()[0])
                days = int(uptime_seconds // 86400)
                hours = int((uptime_seconds % 86400) // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                if days > 0:
                    info["uptime"] = f"{days}d {hours}h {minutes}m"
                else:
                    info["uptime"] = f"{hours}h {minutes}m"
        except:
            pass
        
        # Memory and disk
        if PSUTIL_AVAILABLE:
            import psutil
            mem = psutil.virtual_memory()
            info["memory_total"] = f"{mem.total / (1024**3):.1f} GB"
            
            disk = psutil.disk_usage('/')
            info["disk_free"] = f"{disk.free / (1024**3):.1f} GB free"
        
        return info
    
    def _create_ui(self):
        """Create UI elements"""
        ui = self.config.ui
        colors = self.config.colors
        w = self.config.display.width
        h = self.config.display.height
        margin = ui.button_margin
        
        header_h = ui.status_bar_height
        
        # Info panel
        self.info_rect = pygame.Rect(
            margin, header_h + margin,
            w - margin * 2, h // 2 - margin
        )
        
        # Action buttons
        btn_w = w // 2 - margin * 2
        btn_h = 40
        btn_y = h // 2 + margin * 2
        
        self.btn_reboot = Button(
            rect=pygame.Rect(margin, btn_y, btn_w, btn_h),
            text="Reboot",
            callback=self._on_reboot,
            color=colors.btn_warning,
            hover_color=colors.btn_warning_hover,
            icon="🔄",
            font_size=ui.font_size_small,
            config=self.config
        )
        
        self.btn_shutdown = Button(
            rect=pygame.Rect(w // 2 + margin, btn_y, btn_w, btn_h),
            text="Shutdown",
            callback=self._on_shutdown,
            color=colors.btn_danger,
            hover_color=colors.btn_danger_hover,
            icon="⏻",
            font_size=ui.font_size_small,
            config=self.config
        )
        
        btn_y += btn_h + margin
        
        self.btn_update = Button(
            rect=pygame.Rect(margin, btn_y, btn_w, btn_h),
            text="Check Updates",
            callback=self._on_check_updates,
            color=colors.btn_primary,
            hover_color=colors.btn_primary_hover,
            icon="📦",
            font_size=ui.font_size_small,
            config=self.config
        )
        
        self.btn_refresh = Button(
            rect=pygame.Rect(w // 2 + margin, btn_y, btn_w, btn_h),
            text="Refresh Info",
            callback=self._on_refresh,
            color=colors.btn_secondary,
            hover_color=colors.btn_secondary_hover,
            icon="🔄",
            font_size=ui.font_size_small,
            config=self.config
        )
        
        # Back button
        self.btn_back = Button(
            rect=pygame.Rect(margin, h - btn_h - margin, btn_w, btn_h),
            text="Back",
            callback=self._on_back,
            color=colors.btn_secondary,
            hover_color=colors.btn_secondary_hover,
            icon="←",
            font_size=ui.font_size_small,
            config=self.config
        )
        
        self.action_buttons = [
            self.btn_reboot, self.btn_shutdown, 
            self.btn_update, self.btn_refresh, self.btn_back
        ]
        
        # Confirmation dialog state
        self.confirm_action = None
        self.confirm_message = ""
    
    def _on_back(self):
        """Return to launcher"""
        self.running = False
    
    def _on_reboot(self):
        """Reboot system"""
        self.confirm_action = "reboot"
        self.confirm_message = "Reboot the system?"
    
    def _on_shutdown(self):
        """Shutdown system"""
        self.confirm_action = "shutdown"
        self.confirm_message = "Shutdown the system?"
    
    def _do_reboot(self):
        """Actually reboot"""
        self._show_toast("Rebooting...")
        time.sleep(1)
        subprocess.run(["sudo", "reboot"])
    
    def _do_shutdown(self):
        """Actually shutdown"""
        self._show_toast("Shutting down...")
        time.sleep(1)
        subprocess.run(["sudo", "shutdown", "-h", "now"])
    
    def _on_check_updates(self):
        """Check for updates"""
        self._show_toast("Checking for updates...")
        # This would typically run git pull or apt update
        # For now just show a message
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            result = subprocess.run(
                ["git", "fetch", "--dry-run"],
                capture_output=True, text=True,
                cwd=script_dir, timeout=10
            )
            if result.stderr:
                self._show_toast("Updates available!")
            else:
                self._show_toast("System is up to date")
        except:
            self._show_toast("Could not check updates")
    
    def _on_refresh(self):
        """Refresh system info"""
        self.system_info = self._gather_system_info()
        self._show_toast("Info refreshed")
    
    def _confirm_yes(self):
        """Handle confirmation yes"""
        action = self.confirm_action
        self.confirm_action = None
        
        if action == "reboot":
            self._do_reboot()
        elif action == "shutdown":
            self._do_shutdown()
    
    def _confirm_no(self):
        """Handle confirmation no"""
        self.confirm_action = None
    
    def handle_events(self):
        """Handle events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                self.exit_to_launcher = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.confirm_action:
                        self.confirm_action = None
                    else:
                        self.running = False
            elif event.type == pygame.MOUSEBUTTONUP:
                if self.confirm_action:
                    # Handle confirmation dialog clicks
                    pos = event.pos
                    w = self.config.display.width
                    h = self.config.display.height
                    
                    # Yes button area
                    yes_rect = pygame.Rect(w // 4 - 40, h // 2 + 20, 80, 36)
                    no_rect = pygame.Rect(3 * w // 4 - 40, h // 2 + 20, 80, 36)
                    
                    if yes_rect.collidepoint(pos):
                        self._confirm_yes()
                    elif no_rect.collidepoint(pos):
                        self._confirm_no()
                    continue
            
            # Handle action buttons (only if no confirmation dialog)
            if not self.confirm_action:
                for btn in self.action_buttons:
                    btn.handle_event(event)
    
    def draw(self):
        """Draw the settings screen"""
        colors = self.config.colors
        ui = self.config.ui
        w = self.config.display.width
        h = self.config.display.height
        
        # Clear screen
        self.screen.fill(colors.bg_primary)
        
        # Draw header
        self._draw_header("Settings")
        
        # Draw info panel
        pygame.draw.rect(self.screen, colors.bg_panel, self.info_rect,
                        border_radius=ui.panel_radius)
        
        # Draw system info
        self.font.size = ui.font_size_small
        padding = ui.panel_padding
        y = self.info_rect.top + padding
        line_height = ui.font_size_small + 6
        
        info_items = [
            ("Device", self.system_info["pi_model"]),
            ("OS", self.system_info["os_version"]),
            ("Hostname", self.system_info["hostname"]),
            ("IP Address", self.system_info["ip_address"]),
            ("Uptime", self.system_info["uptime"]),
            ("Memory", self.system_info["memory_total"]),
            ("Storage", self.system_info["disk_free"]),
            ("Python", self.system_info["python_version"]),
        ]
        
        for label, value in info_items:
            # Label
            label_surf, label_rect = self.font.render(f"{label}:", colors.text_muted)
            label_rect.topleft = (self.info_rect.left + padding, y)
            self.screen.blit(label_surf, label_rect)
            
            # Value
            value_surf, value_rect = self.font.render(value, colors.text_primary)
            value_rect.topleft = (self.info_rect.left + padding + 90, y)
            self.screen.blit(value_surf, value_rect)
            
            y += line_height
        
        # Draw action buttons
        for btn in self.action_buttons:
            btn.draw(self.screen, self.font)
        
        # Draw confirmation dialog if active
        if self.confirm_action:
            self._draw_confirmation_dialog()
    
    def _draw_confirmation_dialog(self):
        """Draw confirmation dialog overlay"""
        colors = self.config.colors
        ui = self.config.ui
        w = self.config.display.width
        h = self.config.display.height
        
        # Semi-transparent overlay
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        
        # Dialog box
        dialog_w = 280
        dialog_h = 120
        dialog_rect = pygame.Rect(
            (w - dialog_w) // 2,
            (h - dialog_h) // 2,
            dialog_w, dialog_h
        )
        pygame.draw.rect(self.screen, colors.bg_secondary, dialog_rect, border_radius=12)
        pygame.draw.rect(self.screen, colors.border, dialog_rect, 2, border_radius=12)
        
        # Message
        self.font.size = ui.font_size_medium
        msg_surf, msg_rect = self.font.render(self.confirm_message, colors.text_primary)
        msg_rect.centerx = dialog_rect.centerx
        msg_rect.centery = dialog_rect.centery - 20
        self.screen.blit(msg_surf, msg_rect)
        
        # Yes/No buttons
        btn_w = 80
        btn_h = 36
        btn_y = dialog_rect.centery + 20
        
        # Yes button
        yes_rect = pygame.Rect(dialog_rect.centerx - btn_w - 10, btn_y, btn_w, btn_h)
        pygame.draw.rect(self.screen, colors.btn_danger, yes_rect, border_radius=6)
        self.font.size = ui.font_size_small
        yes_surf, yes_text_rect = self.font.render("Yes", colors.text_primary)
        yes_text_rect.center = yes_rect.center
        self.screen.blit(yes_surf, yes_text_rect)
        
        # No button
        no_rect = pygame.Rect(dialog_rect.centerx + 10, btn_y, btn_w, btn_h)
        pygame.draw.rect(self.screen, colors.btn_secondary, no_rect, border_radius=6)
        no_surf, no_text_rect = self.font.render("No", colors.text_primary)
        no_text_rect.center = no_rect.center
        self.screen.blit(no_surf, no_text_rect)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Film Scanner Settings')
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
    
    app = SettingsApp(config)
    
    try:
        app.run()
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        app.cleanup()


if __name__ == '__main__':
    main()
