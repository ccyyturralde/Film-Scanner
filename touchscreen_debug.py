#!/usr/bin/env python3
"""
Film Scanner - Touch Screen Debug & Diagnostics
Debug tools and diagnostic functions for troubleshooting.

Features:
- Camera connection test
- Arduino connection test
- GPIO test
- Network info
- Storage info
- Run dependency check
"""

import pygame
import pygame.freetype
import subprocess
import sys
import os
import time
import threading
from datetime import datetime
from typing import List, Tuple, Optional, Dict
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


class TestResult:
    """Result of a diagnostic test"""
    def __init__(self, name: str, passed: bool, message: str = "", details: str = ""):
        self.name = name
        self.passed = passed
        self.message = message
        self.details = details
        self.timestamp = datetime.now()


class DebugApp(BaseTouchApp):
    """Debug and diagnostics application"""
    
    APP_NAME = "Debug"
    
    def __init__(self, config: TouchScreenConfig = None):
        super().__init__(config)
        
        self.test_results: List[TestResult] = []
        self.current_test = ""
        self.testing = False
        self.scroll_offset = 0
        
        self._create_ui()
    
    def _create_ui(self):
        """Create UI elements"""
        ui = self.config.ui
        colors = self.config.colors
        w = self.config.display.width
        h = self.config.display.height
        margin = ui.button_margin
        
        header_h = ui.status_bar_height
        
        # Test buttons (left column)
        btn_w = w // 2 - margin * 2
        btn_h = 36
        btn_x = margin
        btn_y = header_h + margin
        
        self.test_buttons: List[Button] = []
        
        tests = [
            ("📷 Camera", self._test_camera),
            ("🔌 Arduino", self._test_arduino),
            ("🌐 Network", self._test_network),
            ("💾 Storage", self._test_storage),
            ("📦 Dependencies", self._test_dependencies),
            ("🔄 Run All", self._run_all_tests),
        ]
        
        for label, callback in tests:
            btn = Button(
                rect=pygame.Rect(btn_x, btn_y, btn_w, btn_h),
                text=label,
                callback=callback,
                color=colors.btn_secondary,
                hover_color=colors.btn_secondary_hover,
                font_size=ui.font_size_small,
                config=self.config
            )
            self.test_buttons.append(btn)
            btn_y += btn_h + margin // 2
        
        # Results panel (right side + bottom)
        results_x = w // 2 + margin // 2
        results_y = header_h + margin
        results_w = w // 2 - margin * 1.5
        results_h = h - header_h - margin * 3 - btn_h
        
        self.results_rect = pygame.Rect(results_x, results_y, results_w, results_h)
        
        # Also show results on left side below buttons
        left_results_y = btn_y + margin
        left_results_h = h - left_results_y - margin * 2 - btn_h
        self.left_results_rect = pygame.Rect(margin, left_results_y, btn_w, left_results_h)
        
        # Combined results area for drawing
        self.full_results_rect = pygame.Rect(
            margin, results_y,
            w - margin * 2, h - results_y - margin * 2 - btn_h
        )
        
        # Back button
        self.btn_back = Button(
            rect=pygame.Rect(margin, h - btn_h - margin, btn_w // 2, btn_h),
            text="Back",
            callback=self._on_back,
            color=colors.btn_secondary,
            hover_color=colors.btn_secondary_hover,
            icon="←",
            font_size=ui.font_size_small,
            config=self.config
        )
        
        # Clear results button
        self.btn_clear = Button(
            rect=pygame.Rect(w - margin - btn_w // 2, h - btn_h - margin, btn_w // 2, btn_h),
            text="Clear",
            callback=self._clear_results,
            color=colors.btn_secondary,
            hover_color=colors.btn_secondary_hover,
            icon="🗑️",
            font_size=ui.font_size_small,
            config=self.config
        )
    
    def _add_result(self, result: TestResult):
        """Add a test result"""
        self.test_results.append(result)
        # Auto-scroll to bottom
        self.scroll_offset = max(0, len(self.test_results) - 5)
    
    def _clear_results(self):
        """Clear all test results"""
        self.test_results = []
        self.scroll_offset = 0
    
    def _on_back(self):
        """Return to launcher"""
        self.running = False
    
    def _run_test_async(self, test_func, test_name: str):
        """Run a test in a background thread"""
        if self.testing:
            self._show_toast("Test already running...")
            return
        
        self.testing = True
        self.current_test = test_name
        
        def run():
            try:
                test_func()
            finally:
                self.testing = False
                self.current_test = ""
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
    
    def _test_camera(self):
        """Test camera connection"""
        self._run_test_async(self._do_camera_test, "Camera")
    
    def _do_camera_test(self):
        """Perform camera test"""
        try:
            # Check if gphoto2 is available
            result = subprocess.run(
                ["gphoto2", "--auto-detect"],
                capture_output=True, text=True, timeout=15
            )
            
            if result.returncode == 0:
                output = result.stdout
                # Check if camera found
                lines = output.strip().split('\n')
                cameras = [l for l in lines[2:] if l.strip()]  # Skip header
                
                if cameras:
                    self._add_result(TestResult(
                        "Camera", True,
                        f"Found {len(cameras)} camera(s)",
                        cameras[0][:40] if cameras else ""
                    ))
                else:
                    self._add_result(TestResult(
                        "Camera", False,
                        "No camera detected",
                        "Connect USB camera and try again"
                    ))
            else:
                self._add_result(TestResult(
                    "Camera", False,
                    "gphoto2 error",
                    result.stderr[:50] if result.stderr else "Unknown error"
                ))
        except FileNotFoundError:
            self._add_result(TestResult(
                "Camera", False,
                "gphoto2 not installed",
                "Run: sudo apt install gphoto2"
            ))
        except subprocess.TimeoutExpired:
            self._add_result(TestResult(
                "Camera", False,
                "Timeout",
                "Camera detection timed out"
            ))
        except Exception as e:
            self._add_result(TestResult(
                "Camera", False,
                "Error",
                str(e)[:50]
            ))
    
    def _test_arduino(self):
        """Test Arduino connection"""
        self._run_test_async(self._do_arduino_test, "Arduino")
    
    def _do_arduino_test(self):
        """Perform Arduino test"""
        try:
            import serial.tools.list_ports
            
            ports = list(serial.tools.list_ports.comports())
            arduino_ports = [p for p in ports if 'Arduino' in p.description or 
                           'USB' in p.description or 'ACM' in p.device or 
                           'USB' in p.device]
            
            if arduino_ports:
                port = arduino_ports[0]
                self._add_result(TestResult(
                    "Arduino", True,
                    f"Found on {port.device}",
                    port.description[:40]
                ))
            else:
                # List all ports for debugging
                if ports:
                    self._add_result(TestResult(
                        "Arduino", False,
                        "No Arduino found",
                        f"Available: {', '.join(p.device for p in ports[:3])}"
                    ))
                else:
                    self._add_result(TestResult(
                        "Arduino", False,
                        "No serial ports found",
                        "Check USB connection"
                    ))
        except ImportError:
            self._add_result(TestResult(
                "Arduino", False,
                "pyserial not installed",
                "Run: pip install pyserial"
            ))
        except Exception as e:
            self._add_result(TestResult(
                "Arduino", False,
                "Error",
                str(e)[:50]
            ))
    
    def _test_network(self):
        """Test network connectivity"""
        self._run_test_async(self._do_network_test, "Network")
    
    def _do_network_test(self):
        """Perform network test"""
        try:
            import socket
            
            # Get hostname and IP
            hostname = socket.gethostname()
            
            # Try to get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
            except:
                local_ip = "No network"
            finally:
                s.close()
            
            if local_ip != "No network":
                self._add_result(TestResult(
                    "Network", True,
                    f"IP: {local_ip}",
                    f"Hostname: {hostname}"
                ))
            else:
                self._add_result(TestResult(
                    "Network", False,
                    "No network connection",
                    f"Hostname: {hostname}"
                ))
            
            # Test internet connectivity
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=3)
                self._add_result(TestResult(
                    "Internet", True,
                    "Internet connected",
                    ""
                ))
            except:
                self._add_result(TestResult(
                    "Internet", False,
                    "No internet access",
                    "Check router/firewall"
                ))
                
        except Exception as e:
            self._add_result(TestResult(
                "Network", False,
                "Error",
                str(e)[:50]
            ))
    
    def _test_storage(self):
        """Test storage space"""
        self._run_test_async(self._do_storage_test, "Storage")
    
    def _do_storage_test(self):
        """Perform storage test"""
        try:
            if PSUTIL_AVAILABLE:
                import psutil
                
                disk = psutil.disk_usage('/')
                free_gb = disk.free / (1024**3)
                total_gb = disk.total / (1024**3)
                percent = disk.percent
                
                passed = free_gb > 1.0  # At least 1GB free
                
                self._add_result(TestResult(
                    "Storage", passed,
                    f"{free_gb:.1f}GB free ({100-percent:.0f}%)",
                    f"Total: {total_gb:.1f}GB"
                ))
                
                # Check scans directory
                scans_dir = os.path.expanduser("~/scans")
                if os.path.exists(scans_dir):
                    num_files = len([f for f in os.listdir(scans_dir) if f.endswith(('.jpg', '.jpeg', '.png'))])
                    self._add_result(TestResult(
                        "Scans Dir", True,
                        f"{num_files} images in ~/scans",
                        scans_dir
                    ))
                else:
                    self._add_result(TestResult(
                        "Scans Dir", False,
                        "~/scans not found",
                        "Will be created on first scan"
                    ))
            else:
                # Fallback without psutil
                result = subprocess.run(
                    ["df", "-h", "/"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        parts = lines[1].split()
                        self._add_result(TestResult(
                            "Storage", True,
                            f"Available: {parts[3]}",
                            f"Used: {parts[4]}"
                        ))
                        
        except Exception as e:
            self._add_result(TestResult(
                "Storage", False,
                "Error",
                str(e)[:50]
            ))
    
    def _test_dependencies(self):
        """Test Python dependencies"""
        self._run_test_async(self._do_dependencies_test, "Dependencies")
    
    def _do_dependencies_test(self):
        """Perform dependencies test"""
        deps_to_check = [
            ("flask", "Flask"),
            ("flask_socketio", "Flask-SocketIO"),
            ("serial", "pyserial"),
            ("PIL", "Pillow"),
            ("cv2", "OpenCV"),
            ("numpy", "NumPy"),
            ("pygame", "Pygame"),
            ("psutil", "psutil"),
        ]
        
        passed = 0
        failed = 0
        
        for module, name in deps_to_check:
            try:
                __import__(module)
                passed += 1
            except ImportError:
                failed += 1
                self._add_result(TestResult(
                    f"Dep: {name}", False,
                    "Not installed",
                    f"pip install {name.lower()}"
                ))
        
        if failed == 0:
            self._add_result(TestResult(
                "Dependencies", True,
                f"All {passed} packages OK",
                ""
            ))
        else:
            self._add_result(TestResult(
                "Dependencies", False,
                f"{failed} missing, {passed} OK",
                "Run dependency_check.py"
            ))
    
    def _run_all_tests(self):
        """Run all tests sequentially"""
        if self.testing:
            self._show_toast("Tests already running...")
            return
        
        def run_all():
            self._do_camera_test()
            time.sleep(0.5)
            self._do_arduino_test()
            time.sleep(0.5)
            self._do_network_test()
            time.sleep(0.5)
            self._do_storage_test()
            time.sleep(0.5)
            self._do_dependencies_test()
        
        self.testing = True
        self.current_test = "All Tests"
        
        def run():
            try:
                run_all()
            finally:
                self.testing = False
                self.current_test = ""
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
    
    def handle_events(self):
        """Handle events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                self.exit_to_launcher = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
            
            # Handle buttons
            for btn in self.test_buttons:
                btn.handle_event(event)
            
            self.btn_back.handle_event(event)
            self.btn_clear.handle_event(event)
    
    def draw(self):
        """Draw the debug screen"""
        colors = self.config.colors
        ui = self.config.ui
        w = self.config.display.width
        
        # Clear screen
        self.screen.fill(colors.bg_primary)
        
        # Draw header
        header_text = "Debug & Diagnostics"
        if self.testing:
            header_text = f"Testing: {self.current_test}..."
        self._draw_header(header_text)
        
        # Draw test buttons
        for btn in self.test_buttons:
            btn.draw(self.screen, self.font)
        
        # Draw results panel
        pygame.draw.rect(self.screen, colors.bg_panel, self.results_rect,
                        border_radius=ui.panel_radius)
        
        # Draw results
        if self.test_results:
            self.font.size = ui.font_size_tiny
            padding = ui.panel_padding
            line_height = ui.font_size_tiny + 8
            y = self.results_rect.top + padding
            
            for result in self.test_results[self.scroll_offset:]:
                if y + line_height > self.results_rect.bottom - padding:
                    break
                
                # Status icon
                icon = "✓" if result.passed else "✗"
                icon_color = colors.success if result.passed else colors.error
                
                # Draw icon
                icon_surf, icon_rect = self.font.render(icon, icon_color)
                icon_rect.topleft = (self.results_rect.left + padding, y)
                self.screen.blit(icon_surf, icon_rect)
                
                # Draw name and message
                text = f"{result.name}: {result.message}"
                max_chars = (self.results_rect.width - padding * 3) // 6
                text = text[:max_chars]
                
                text_color = colors.text_primary if result.passed else colors.text_secondary
                text_surf, text_rect = self.font.render(text, text_color)
                text_rect.topleft = (self.results_rect.left + padding + 20, y)
                self.screen.blit(text_surf, text_rect)
                
                # Draw details on next line if present
                if result.details:
                    y += line_height - 4
                    detail_text = result.details[:max_chars]
                    detail_surf, detail_rect = self.font.render(detail_text, colors.text_muted)
                    detail_rect.topleft = (self.results_rect.left + padding + 20, y)
                    self.screen.blit(detail_surf, detail_rect)
                
                y += line_height
        else:
            # No results yet
            self.font.size = ui.font_size_small
            text_surf, text_rect = self.font.render("Run a test to see results", colors.text_muted)
            text_rect.center = self.results_rect.center
            self.screen.blit(text_surf, text_rect)
        
        # Draw navigation buttons
        self.btn_back.draw(self.screen, self.font)
        self.btn_clear.draw(self.screen, self.font)
        
        # Draw testing indicator
        if self.testing:
            self.font.size = ui.font_size_small
            test_surf, test_rect = self.font.render("⏳ Testing...", colors.warning)
            test_rect.center = (w // 2, self.config.display.height - ui.button_margin - 18)
            self.screen.blit(test_surf, test_rect)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Film Scanner Debug & Diagnostics')
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
    
    app = DebugApp(config)
    
    try:
        app.run()
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        app.cleanup()


if __name__ == '__main__':
    main()
