#!/usr/bin/env python3
"""
Film Scanner App Manager
Manages the web application lifecycle and captures logs for the touch screen UI.

Features:
- Start/Stop/Restart the web application
- Capture stdout/stderr logs in a circular buffer
- Parse and format error messages for friendly display
- Health monitoring with auto-restart capability
"""

import subprocess
import threading
import time
import os
import sys
import signal
import re
from collections import deque
from datetime import datetime
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Callable

class AppState(Enum):
    """Application states"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"
    CRASHED = "crashed"

@dataclass
class LogEntry:
    """A single log entry with metadata"""
    timestamp: datetime
    level: str  # INFO, WARNING, ERROR, DEBUG
    message: str
    source: str  # stdout, stderr
    raw: str  # Original line
    
    def __str__(self):
        return f"[{self.timestamp.strftime('%H:%M:%S')}] {self.level}: {self.message}"

@dataclass
class AppStatus:
    """Current application status"""
    state: AppState = AppState.STOPPED
    pid: Optional[int] = None
    uptime_seconds: float = 0
    last_error: Optional[str] = None
    error_count: int = 0
    restart_count: int = 0
    web_url: Optional[str] = None
    arduino_connected: bool = False
    camera_connected: bool = False

class AppManager:
    """
    Manages the Film Scanner web application process.
    
    Provides:
    - Process lifecycle management (start, stop, restart)
    - Log capture and parsing
    - Status monitoring
    - Error detection and friendly formatting
    """
    
    def __init__(self, 
                 app_path: str = None,
                 log_buffer_size: int = 500,
                 auto_restart: bool = False,
                 auto_restart_delay: float = 5.0):
        """
        Initialize the App Manager.
        
        Args:
            app_path: Path to web_app.py (auto-detected if None)
            log_buffer_size: Number of log entries to keep in memory
            auto_restart: Whether to auto-restart on crash
            auto_restart_delay: Seconds to wait before auto-restart
        """
        # Find app path
        if app_path is None:
            self.app_path = self._find_app_path()
        else:
            self.app_path = Path(app_path)
        
        # Process management
        self.process: Optional[subprocess.Popen] = None
        self.state = AppState.STOPPED
        self.status = AppStatus()
        
        # Logging
        self.log_buffer: deque = deque(maxlen=log_buffer_size)
        self.error_buffer: deque = deque(maxlen=100)  # Recent errors only
        
        # Configuration
        self.auto_restart = auto_restart
        self.auto_restart_delay = auto_restart_delay
        
        # Threading
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._log_thread: Optional[threading.Thread] = None
        self._monitor_thread: Optional[threading.Thread] = None
        
        # Log file (output from web app goes here instead of pipes)
        self._log_file = None
        self._log_file_path: Optional[Path] = None
        
        # Callbacks
        self._state_callbacks: List[Callable[[AppState], None]] = []
        self._log_callbacks: List[Callable[[LogEntry], None]] = []
        self._error_callbacks: List[Callable[[str], None]] = []
        
        # Startup time tracking
        self._start_time: Optional[datetime] = None
        
    def _find_app_path(self) -> Path:
        """Find the web_app.py file"""
        # Check common locations
        candidates = [
            Path(__file__).parent / "web_app.py",
            Path.cwd() / "web_app.py",
            Path.home() / "Film-Scanner" / "web_app.py",
            Path("/home/pi/Film-Scanner/web_app.py"),
        ]
        
        for path in candidates:
            if path.exists():
                return path
        
        raise FileNotFoundError("Could not find web_app.py")
    
    def add_state_callback(self, callback: Callable[[AppState], None]):
        """Register a callback for state changes"""
        self._state_callbacks.append(callback)
    
    def add_log_callback(self, callback: Callable[[LogEntry], None]):
        """Register a callback for new log entries"""
        self._log_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable[[str], None]):
        """Register a callback for errors"""
        self._error_callbacks.append(callback)
    
    def _set_state(self, new_state: AppState):
        """Update state and notify callbacks"""
        with self._lock:
            old_state = self.state
            self.state = new_state
            self.status.state = new_state
        
        if old_state != new_state:
            for callback in self._state_callbacks:
                try:
                    callback(new_state)
                except Exception as e:
                    print(f"State callback error: {e}")
    
    def _parse_log_line(self, line: str, source: str) -> LogEntry:
        """Parse a log line and extract metadata"""
        timestamp = datetime.now()
        level = "INFO"
        message = line.strip()
        
        # Detect log level from common patterns
        line_lower = line.lower()
        
        if any(x in line_lower for x in ['error', '✗', '❌', 'failed', 'exception', 'traceback']):
            level = "ERROR"
        elif any(x in line_lower for x in ['warning', '⚠', 'warn']):
            level = "WARNING"
        elif any(x in line_lower for x in ['debug']):
            level = "DEBUG"
        elif any(x in line_lower for x in ['✓', '✔', 'success', 'connected', 'ready']):
            level = "SUCCESS"
        
        # Clean up message for display
        # Remove ANSI escape codes
        message = re.sub(r'\x1b\[[0-9;]*m', '', message)
        
        # Parse Arduino/Camera connection status (protected by lock for thread safety)
        # Note: Check negative cases FIRST since 'disconnected' contains 'connected'
        with self._lock:
            if 'arduino' in line_lower:
                if 'not found' in line_lower or 'disconnected' in line_lower or 'not connected' in line_lower:
                    self.status.arduino_connected = False
                elif 'connected' in line_lower or '✓' in line:
                    self.status.arduino_connected = True
            
            if 'camera' in line_lower:
                if 'not connected' in line_lower or 'not found' in line_lower or 'disconnected' in line_lower:
                    self.status.camera_connected = False
                elif 'detected' in line_lower or 'connected' in line_lower:
                    self.status.camera_connected = True
            
            # Extract web URL
            url_match = re.search(r'http://[\d\.]+:\d+', line)
            if url_match:
                self.status.web_url = url_match.group(0)
        
        return LogEntry(
            timestamp=timestamp,
            level=level,
            message=message,
            source=source,
            raw=line
        )
    
    def _log_file_reader_thread(self):
        """Thread to read logs from log file (simpler than pipe threading)"""
        if not hasattr(self, '_log_file_path') or not self._log_file_path:
            return
        
        # Wait for log file to be created
        log_path = self._log_file_path
        for _ in range(10):
            if os.path.exists(log_path):
                break
            time.sleep(0.5)
        
        if not os.path.exists(log_path):
            return
        
        try:
            with open(log_path, 'r') as f:
                # Start at beginning of file
                while not self._stop_event.is_set():
                    line = f.readline()
                    if line:
                        entry = self._parse_log_line(line, 'logfile')
                        
                        with self._lock:
                            self.log_buffer.append(entry)
                            
                            if entry.level == "ERROR":
                                self.error_buffer.append(entry)
                                self.status.error_count += 1
                                self.status.last_error = entry.message
                        
                        # Notify callbacks
                        for callback in self._log_callbacks:
                            try:
                                callback(entry)
                            except:
                                pass
                        
                        if entry.level == "ERROR":
                            for callback in self._error_callbacks:
                                try:
                                    callback(entry.message)
                                except:
                                    pass
                    else:
                        # No new content, wait a bit
                        time.sleep(0.5)
        except Exception as e:
            print(f"Log file reader error: {e}")
    
    def _monitor_thread_func(self):
        """Thread to monitor process health"""
        while not self._stop_event.is_set():
            if self.process:
                # Check if process is still running
                poll = self.process.poll()
                
                if poll is not None:
                    # Process has exited
                    exit_code = poll
                    
                    if self.state == AppState.RUNNING:
                        # Unexpected exit
                        self._set_state(AppState.CRASHED)
                        self.status.last_error = f"Process exited with code {exit_code}"
                        
                        if self.auto_restart:
                            time.sleep(self.auto_restart_delay)
                            if self.state == AppState.CRASHED:
                                self.start()
                    else:
                        self._set_state(AppState.STOPPED)
                
                # Update uptime
                if self._start_time and self.state == AppState.RUNNING:
                    self.status.uptime_seconds = (datetime.now() - self._start_time).total_seconds()
            
            time.sleep(1)
    
    def start(self) -> bool:
        """
        Start the web application.
        
        Returns:
            True if started successfully, False otherwise
        """
        with self._lock:
            if self.state in [AppState.RUNNING, AppState.STARTING]:
                return True
            
            self._set_state(AppState.STARTING)
        
        try:
            # Clear stop event
            self._stop_event.clear()
            
            # Reset status
            self.status.error_count = 0
            self.status.arduino_connected = False
            self.status.camera_connected = False
            
            # Set up log file for web app output
            log_dir = Path.home() / ".film_scanner"
            log_dir.mkdir(parents=True, exist_ok=True)
            self._log_file_path = log_dir / "web_app.log"
            
            # Open log file for writing (truncate on start)
            self._log_file = open(self._log_file_path, 'w')
            
            # Start the process in its own process group
            # Output goes to log file instead of pipes (avoids threading issues)
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'  # Force unbuffered output
            
            self.process = subprocess.Popen(
                [sys.executable, str(self.app_path)],
                stdout=self._log_file,
                stderr=subprocess.STDOUT,  # Combine stderr with stdout
                env=env,
                cwd=str(self.app_path.parent),
                start_new_session=True  # Create new process group for clean shutdown
            )
            
            self.status.pid = self.process.pid
            self._start_time = datetime.now()
            
            # Start simple monitor thread (no pipe reading)
            self._monitor_thread = threading.Thread(
                target=self._monitor_thread_func,
                daemon=True
            )
            self._monitor_thread.start()
            
            # Start log file reader thread
            self._log_thread = threading.Thread(
                target=self._log_file_reader_thread,
                daemon=True
            )
            self._log_thread.start()
            
            # Wait a moment and check if it started
            time.sleep(2)
            
            if self.process.poll() is None:
                self._set_state(AppState.RUNNING)
                self.status.restart_count += 1
                return True
            else:
                self._set_state(AppState.ERROR)
                return False
                
        except Exception as e:
            self.status.last_error = str(e)
            self._set_state(AppState.ERROR)
            return False
    
    def stop(self, timeout: float = 10.0) -> bool:
        """
        Stop the web application gracefully.
        
        Args:
            timeout: Seconds to wait before force killing
            
        Returns:
            True if stopped successfully
        """
        with self._lock:
            if self.state == AppState.STOPPED:
                return True
            
            self._set_state(AppState.STOPPING)
        
        self._stop_event.set()
        
        if self.process:
            try:
                pid = self.process.pid
                
                # Kill the entire process group/tree (Flask spawns child processes)
                try:
                    # On Unix, kill the process group
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                except (OSError, ProcessLookupError):
                    # Fallback: just terminate the main process
                    self.process.terminate()
                
                try:
                    self.process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # Force kill the process group
                    try:
                        os.killpg(os.getpgid(pid), signal.SIGKILL)
                    except (OSError, ProcessLookupError):
                        self.process.kill()
                    self.process.wait(timeout=5)
                
                # Also kill any remaining processes on port 5000
                self._kill_port_processes(5000)
                
                self.process = None
                self.status.pid = None
                
            except Exception as e:
                self.status.last_error = f"Stop error: {e}"
                # Try to kill by port as last resort
                self._kill_port_processes(5000)
                return False
        
        # Close log file if open
        if self._log_file:
            try:
                self._log_file.close()
            except:
                pass
            self._log_file = None
        
        self._set_state(AppState.STOPPED)
        return True
    
    def _kill_port_processes(self, port: int):
        """Kill any processes using the specified port"""
        try:
            # Use fuser to find and kill processes on the port
            subprocess.run(
                ["fuser", "-k", f"{port}/tcp"],
                capture_output=True,
                timeout=5
            )
        except Exception:
            pass
        
        try:
            # Also try pkill for any remaining web_app processes
            subprocess.run(
                ["pkill", "-f", "web_app.py"],
                capture_output=True,
                timeout=5
            )
        except Exception:
            pass
    
    def restart(self) -> bool:
        """Restart the web application"""
        self.stop()
        time.sleep(1)
        return self.start()
    
    def get_logs(self, count: int = 50, level: str = None) -> List[LogEntry]:
        """
        Get recent log entries.
        
        Args:
            count: Maximum number of entries to return
            level: Filter by level (INFO, WARNING, ERROR, etc.)
            
        Returns:
            List of LogEntry objects
        """
        with self._lock:
            logs = list(self.log_buffer)
        
        if level:
            logs = [l for l in logs if l.level == level]
        
        return logs[-count:]
    
    def get_errors(self, count: int = 20) -> List[LogEntry]:
        """Get recent error entries"""
        with self._lock:
            return list(self.error_buffer)[-count:]
    
    def get_status(self) -> AppStatus:
        """Get current application status"""
        return self.status
    
    def get_friendly_status(self) -> dict:
        """Get status formatted for display"""
        # Use ASCII-compatible status messages (no emoji for TFT font compatibility)
        state_messages = {
            AppState.STOPPED: ("STOPPED", "App is not running"),
            AppState.STARTING: ("STARTING", "App is starting up"),
            AppState.RUNNING: ("RUNNING", "App is running normally"),
            AppState.STOPPING: ("STOPPING", "App is shutting down"),
            AppState.ERROR: ("ERROR", "App failed to start"),
            AppState.CRASHED: ("CRASHED", "App stopped unexpectedly"),
        }
        
        # Read all shared state under lock for thread safety
        with self._lock:
            current_state = self.state
            uptime_seconds = self.status.uptime_seconds
            pid = self.status.pid
            error_count = self.status.error_count
            last_error = self.status.last_error
            web_url = self.status.web_url
            arduino_connected = self.status.arduino_connected
            camera_connected = self.status.camera_connected
        
        icon, desc = state_messages.get(current_state, ("UNKNOWN", "Unknown state"))
        
        # Format uptime
        uptime = ""
        if uptime_seconds > 0:
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            seconds = int(uptime_seconds % 60)
            if hours > 0:
                uptime = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                uptime = f"{minutes}m {seconds}s"
            else:
                uptime = f"{seconds}s"
        
        return {
            'state': current_state.value,
            'icon': icon,
            'description': desc,
            'uptime': uptime,
            'pid': pid,
            'error_count': error_count,
            'last_error': last_error,
            'web_url': web_url or "http://localhost:5000",
            'arduino_connected': arduino_connected,
            'camera_connected': camera_connected,
        }
    
    def format_error_for_display(self, error: str) -> str:
        """
        Format an error message for friendly display on small screen.
        
        Simplifies technical errors into user-friendly messages.
        """
        error_lower = error.lower()
        
        # Arduino errors
        if 'arduino' in error_lower:
            if 'not found' in error_lower:
                return "Arduino not connected\nCheck USB cable"
            if 'permission' in error_lower:
                return "Arduino permission error\nAdd user to dialout group"
            if 'serial' in error_lower:
                return "Arduino communication error\nTry reconnecting USB"
        
        # Camera errors
        if 'camera' in error_lower or 'gphoto' in error_lower:
            if 'not connected' in error_lower or 'not found' in error_lower:
                return "Camera not connected\nCheck USB cable"
            if 'busy' in error_lower:
                return "Camera busy\nClose other camera apps"
            if 'ptp' in error_lower:
                return "Camera PTP error\nSet camera to PTP mode"
            if 'timeout' in error_lower:
                return "Camera timeout\nTry again or reconnect"
        
        # Network errors
        if 'network' in error_lower or 'socket' in error_lower:
            return "Network error\nCheck WiFi connection"
        
        # File errors
        if 'permission denied' in error_lower:
            return "Permission denied\nCheck file permissions"
        if 'no such file' in error_lower or 'not found' in error_lower:
            return "File not found\nCheck installation"
        
        # Memory errors
        if 'memory' in error_lower:
            return "Low memory\nRestart the Pi"
        
        # Generic - truncate long messages
        if len(error) > 50:
            return error[:47] + "..."
        
        return error
    
    def cleanup(self):
        """Clean up resources"""
        self.stop()
        self._stop_event.set()


# Singleton instance for global access
_manager_instance: Optional[AppManager] = None

def get_app_manager() -> AppManager:
    """Get or create the global AppManager instance"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = AppManager()
    return _manager_instance


if __name__ == '__main__':
    # Test the app manager
    import argparse
    
    parser = argparse.ArgumentParser(description='Film Scanner App Manager')
    parser.add_argument('command', choices=['start', 'stop', 'restart', 'status', 'logs'],
                       help='Command to execute')
    parser.add_argument('--follow', '-f', action='store_true',
                       help='Follow logs (for logs command)')
    
    args = parser.parse_args()
    
    manager = get_app_manager()
    
    if args.command == 'start':
        print("Starting Film Scanner...")
        if manager.start():
            print("✓ Started successfully")
            print(f"  PID: {manager.status.pid}")
        else:
            print("✗ Failed to start")
            print(f"  Error: {manager.status.last_error}")
    
    elif args.command == 'stop':
        print("Stopping Film Scanner...")
        if manager.stop():
            print("✓ Stopped successfully")
        else:
            print("✗ Failed to stop")
    
    elif args.command == 'restart':
        print("Restarting Film Scanner...")
        if manager.restart():
            print("✓ Restarted successfully")
        else:
            print("✗ Failed to restart")
    
    elif args.command == 'status':
        status = manager.get_friendly_status()
        print(f"\n{status['icon']} {status['description']}")
        if status['pid']:
            print(f"  PID: {status['pid']}")
        if status['uptime']:
            print(f"  Uptime: {status['uptime']}")
        print(f"  Arduino: {'Connected' if status['arduino_connected'] else 'Disconnected'}")
        print(f"  Camera: {'Connected' if status['camera_connected'] else 'Disconnected'}")
        if status['last_error']:
            print(f"  Last Error: {status['last_error']}")
        print(f"  Web UI: {status['web_url']}")
    
    elif args.command == 'logs':
        if args.follow:
            # Follow mode - print new logs as they arrive
            def print_log(entry):
                print(entry)
            
            manager.add_log_callback(print_log)
            manager.start()
            
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                manager.stop()
        else:
            # Print recent logs
            logs = manager.get_logs(50)
            for entry in logs:
                print(entry)
