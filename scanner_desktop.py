#!/usr/bin/env python3
"""
35mm Film Scanner - Desktop Application
Modern Qt-based GUI for Windows/Mac/Linux

Features:
- Responsive GUI with Qt6
- Fast Arduino serial communication
- Integrated live view with color inversion for film positives
- Direct camera control (autofocus, capture)
- Keyboard shortcuts for rapid operation
- Session management and state persistence
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
import numpy as np
import cv2

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QGroupBox, QSpinBox,
    QCheckBox, QFileDialog, QStatusBar, QGridLayout, QMessageBox, QSplitter
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread
from PySide6.QtGui import QKeySequence, QShortcut, QFont, QAction, QImage, QPixmap

import serial
import serial.tools.list_ports
import subprocess
import time

try:
    import gphoto2 as gp
    GPHOTO2_AVAILABLE = True
except ImportError:
    GPHOTO2_AVAILABLE = False
    print("Warning: gphoto2 not available. Camera control will be limited.")


class ArduinoController(QThread):
    """
    Background thread for Arduino communication to prevent GUI blocking
    """
    position_updated = Signal(int)
    status_message = Signal(str)
    connection_status = Signal(bool)
    
    def __init__(self):
        super().__init__()
        self.arduino: Optional[serial.Serial] = None
        self.position = 0
        self.running = True
        
    def find_and_connect(self):
        """Find and connect to Arduino"""
        ports = list(serial.tools.list_ports.comports())
        
        for port in ports:
            try:
                ser = serial.Serial(port.device, 115200, timeout=2)
                time.sleep(2.5)  # Arduino reset time
                
                ser.reset_input_buffer()
                ser.write(b'?\n')
                time.sleep(0.5)
                
                if ser.in_waiting:
                    response = ser.read_all().decode('utf-8', errors='ignore')
                    if any(word in response for word in ['READY', 'STATUS', 'NEMA', 'Position']):
                        self.arduino = ser
                        self.connection_status.emit(True)
                        self.status_message.emit(f"Connected to {port.device}")
                        self.initialize_arduino()
                        return True
                
                ser.close()
            except Exception as e:
                continue
        
        self.connection_status.emit(False)
        self.status_message.emit("Arduino not found")
        return False
    
    def initialize_arduino(self):
        """Initialize Arduino settings"""
        if not self.arduino:
            return
        
        try:
            self.arduino.write(b'U\n')  # Unlock
            time.sleep(0.05)
            self.arduino.write(b'E\n')  # Enable motor
            time.sleep(0.05)
            self.arduino.write(b'v800\n')  # Set step delay
            time.sleep(0.05)
        except Exception as e:
            self.status_message.emit(f"Init error: {str(e)}")
    
    def send_command(self, cmd: str) -> bool:
        """Send command to Arduino"""
        if not self.arduino or not self.arduino.is_open:
            self.status_message.emit("Arduino not connected")
            return False
        
        try:
            self.arduino.write(f"{cmd}\n".encode())
            time.sleep(0.05)
            
            # Update position tracking
            if cmd == 'f':
                self.position += 8  # fine_step
            elif cmd == 'b':
                self.position -= 8
            elif cmd == 'F':
                self.position += 64  # coarse_step
            elif cmd == 'B':
                self.position -= 64
            elif cmd.startswith('H'):
                steps = int(cmd[1:])
                self.position += steps
            elif cmd.startswith('h'):
                steps = int(cmd[1:])
                self.position -= steps
            elif cmd == 'Z':
                self.position = 0
            
            self.position_updated.emit(self.position)
            return True
        except Exception as e:
            self.status_message.emit(f"Command error: {str(e)}")
            return False
    
    def disconnect(self):
        """Clean disconnect"""
        self.running = False
        if self.arduino and self.arduino.is_open:
            try:
                self.arduino.write(b'M\n')  # Disable motor
                time.sleep(0.2)
                self.arduino.close()
            except:
                pass
        self.connection_status.emit(False)


class CameraController(QThread):
    """
    Direct camera control with live view support
    """
    frame_ready = Signal(np.ndarray)
    status_message = Signal(str)
    camera_connected = Signal(bool)
    
    def __init__(self):
        super().__init__()
        self.camera = None
        self.context = None
        self.running = False
        self.capturing_live_view = False
        
        if GPHOTO2_AVAILABLE:
            self.init_gphoto2()
    
    def init_gphoto2(self):
        """Initialize gphoto2 camera"""
        try:
            self.context = gp.Context()
            self.camera = gp.Camera()
            self.camera.init(self.context)
            self.camera_connected.emit(True)
            self.status_message.emit("Camera connected via gphoto2")
            return True
        except Exception as e:
            self.status_message.emit(f"Camera connection failed: {str(e)}")
            self.camera_connected.emit(False)
            return False
    
    def start_live_view(self):
        """Start live view capture"""
        if not self.camera:
            self.status_message.emit("No camera connected")
            return False
        
        self.capturing_live_view = True
        self.running = True
        self.start()
        return True
    
    def stop_live_view(self):
        """Stop live view capture"""
        self.capturing_live_view = False
        self.running = False
    
    def run(self):
        """Background thread for live view"""
        while self.running and self.capturing_live_view:
            try:
                if GPHOTO2_AVAILABLE and self.camera:
                    # Capture preview frame
                    camera_file = self.camera.capture_preview(self.context)
                    file_data = camera_file.get_data_and_size()
                    
                    # Convert to numpy array
                    image = np.frombuffer(file_data, dtype=np.uint8)
                    frame = cv2.imdecode(image, cv2.IMREAD_COLOR)
                    
                    if frame is not None:
                        self.frame_ready.emit(frame)
                
                time.sleep(0.033)  # ~30 fps
            except Exception as e:
                print(f"Live view error: {e}")
                time.sleep(0.1)
    
    def autofocus(self) -> bool:
        """Trigger camera autofocus"""
        if not self.camera:
            return False
        
        try:
            if GPHOTO2_AVAILABLE:
                # Set autofocus
                config = self.camera.get_config(self.context)
                af_widget = config.get_child_by_name('autofocusdrive')
                af_widget.set_value(1)
                self.camera.set_config(config, self.context)
                time.sleep(1)  # Wait for AF to complete
                self.status_message.emit("Autofocus complete")
                return True
        except Exception as e:
            self.status_message.emit(f"Autofocus error: {str(e)}")
            # Try alternative method
            try:
                # Some cameras use different config names
                config = self.camera.get_config(self.context)
                af_widget = config.get_child_by_name('manualfocusdrive')
                # Trigger AF by setting to 0 (neutral position)
                af_widget.set_value(0)
                self.camera.set_config(config, self.context)
                return True
            except:
                pass
        
        return False
    
    def capture_image(self, save_path: str) -> bool:
        """Capture and save image"""
        if not self.camera:
            self.status_message.emit("No camera connected")
            return False
        
        try:
            if GPHOTO2_AVAILABLE:
                # Pause live view during capture
                was_capturing = self.capturing_live_view
                if was_capturing:
                    self.capturing_live_view = False
                    time.sleep(0.1)
                
                # Capture image
                file_path = self.camera.capture(gp.GP_CAPTURE_IMAGE, self.context)
                
                # Download image
                camera_file = self.camera.file_get(
                    file_path.folder, file_path.name, gp.GP_FILE_TYPE_NORMAL, self.context
                )
                camera_file.save(save_path)
                
                # Resume live view
                if was_capturing:
                    self.capturing_live_view = True
                
                self.status_message.emit(f"Image captured: {save_path}")
                return True
        except Exception as e:
            self.status_message.emit(f"Capture error: {str(e)}")
            return False
    
    def disconnect(self):
        """Disconnect camera"""
        self.running = False
        self.capturing_live_view = False
        
        if self.camera:
            try:
                self.camera.exit(self.context)
            except:
                pass
        
        self.camera_connected.emit(False)


class LiveViewWidget(QLabel):
    """
    Widget for displaying camera live view with color inversion option
    """
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(640, 480)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: black; border: 2px solid #555;")
        self.setText("Live View\n(Camera will appear here)")
        self.invert_colors = False
    
    def update_frame(self, frame: np.ndarray):
        """Update display with new frame"""
        try:
            # Apply color inversion if enabled
            if self.invert_colors:
                frame = cv2.bitwise_not(frame)
            
            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Convert to QImage
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            # Scale to fit widget while maintaining aspect ratio
            pixmap = QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            
            self.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"Frame update error: {e}")
    
    def toggle_invert(self, enabled: bool):
        """Toggle color inversion"""
        self.invert_colors = enabled


class FilmScannerApp(QMainWindow):
    """
    Main application window
    """
    
    def __init__(self):
        super().__init__()
        
        # Controllers
        self.arduino = ArduinoController()
        self.camera = CameraController()
        
        # State
        self.roll_name = ""
        self.frame_count = 0
        self.strip_count = 0
        self.frames_in_strip = 0
        self.position = 0
        self.frame_advance = None
        self.state_file = None
        self.calibration_complete = False
        self.roll_folder = None
        self.is_capturing = False  # Flag to prevent multiple simultaneous captures
        
        # Settings
        self.fine_step = 8
        self.coarse_step = 64
        self.auto_advance = True
        self.frames_per_strip = 6  # Default, user can change
        self.total_strips = 0  # Track completed strips
        
        # Setup UI
        self.init_ui()
        self.setup_shortcuts()
        
        # Connect Arduino signals
        self.arduino.position_updated.connect(self.on_position_updated)
        self.arduino.status_message.connect(self.show_status)
        self.arduino.connection_status.connect(self.on_arduino_connection)
        
        # Connect Camera signals
        self.camera.frame_ready.connect(self.on_frame_ready)
        self.camera.status_message.connect(self.show_status)
        self.camera.camera_connected.connect(self.on_camera_connection)
        
        # Auto-connect to Arduino
        QTimer.singleShot(500, self.connect_arduino)
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Film Scanner - Desktop Edition")
        self.setMinimumSize(1200, 800)
        
        # Central widget with splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Create splitter for live view and controls
        splitter = QSplitter(Qt.Horizontal)
        
        # Left side: Live View
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        self.live_view = LiveViewWidget()
        left_layout.addWidget(self.live_view)
        
        # Live view controls
        lv_controls = QHBoxLayout()
        
        self.btn_toggle_liveview = QPushButton("Start Live View")
        self.btn_toggle_liveview.setCheckable(True)
        self.btn_toggle_liveview.clicked.connect(self.toggle_live_view)
        lv_controls.addWidget(self.btn_toggle_liveview)
        
        self.chk_invert_colors = QCheckBox("Invert Colors (Show Positive)")
        self.chk_invert_colors.stateChanged.connect(self.toggle_invert_colors)
        lv_controls.addWidget(self.chk_invert_colors)
        
        left_layout.addLayout(lv_controls)
        
        splitter.addWidget(left_panel)
        
        # Right side: Controls
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Top: Status Display
        status_group = QGroupBox("Status")
        status_layout = QGridLayout()
        
        self.lbl_connection = QLabel("Arduino: Disconnected")
        self.lbl_connection.setStyleSheet("color: red; font-weight: bold;")
        status_layout.addWidget(QLabel("Arduino:"), 0, 0)
        status_layout.addWidget(self.lbl_connection, 0, 1)
        
        self.lbl_camera_status = QLabel("Camera: Disconnected")
        self.lbl_camera_status.setStyleSheet("color: red; font-weight: bold;")
        status_layout.addWidget(QLabel("Camera:"), 1, 0)
        status_layout.addWidget(self.lbl_camera_status, 1, 1)
        
        self.lbl_roll = QLabel("None")
        status_layout.addWidget(QLabel("Roll:"), 2, 0)
        status_layout.addWidget(self.lbl_roll, 2, 1)
        
        self.lbl_frame_count = QLabel("0")
        status_layout.addWidget(QLabel("Total Frames:"), 3, 0)
        status_layout.addWidget(self.lbl_frame_count, 3, 1)
        
        self.lbl_strip_info = QLabel("Strip 0, Frame 0")
        status_layout.addWidget(QLabel("Current:"), 4, 0)
        status_layout.addWidget(self.lbl_strip_info, 4, 1)
        
        self.lbl_position = QLabel("0 steps")
        status_layout.addWidget(QLabel("Position:"), 5, 0)
        status_layout.addWidget(self.lbl_position, 5, 1)
        
        self.lbl_frame_advance = QLabel("Not calibrated")
        status_layout.addWidget(QLabel("Frame Spacing:"), 6, 0)
        status_layout.addWidget(self.lbl_frame_advance, 6, 1)
        
        # Strip configuration
        strip_config_layout = QHBoxLayout()
        strip_config_layout.addWidget(QLabel("Frames/Strip:"))
        self.spin_frames_per_strip = QSpinBox()
        self.spin_frames_per_strip.setMinimum(4)
        self.spin_frames_per_strip.setMaximum(8)
        self.spin_frames_per_strip.setValue(6)
        self.spin_frames_per_strip.valueChanged.connect(self.update_frames_per_strip)
        strip_config_layout.addWidget(self.spin_frames_per_strip)
        strip_config_layout.addStretch()
        status_layout.addLayout(strip_config_layout, 7, 0, 1, 2)
        
        status_group.setLayout(status_layout)
        right_layout.addWidget(status_group)
        
        # Middle: Motor Controls
        motor_group = QGroupBox("Motor Control")
        motor_layout = QVBoxLayout()
        
        # Movement buttons
        movement_layout = QHBoxLayout()
        
        self.btn_backward_coarse = QPushButton("◄◄ Coarse Back")
        self.btn_backward_coarse.clicked.connect(lambda: self.send_arduino('B'))
        movement_layout.addWidget(self.btn_backward_coarse)
        
        self.btn_backward_fine = QPushButton("◄ Fine Back")
        self.btn_backward_fine.clicked.connect(lambda: self.send_arduino('b'))
        movement_layout.addWidget(self.btn_backward_fine)
        
        self.btn_forward_fine = QPushButton("Fine Forward ►")
        self.btn_forward_fine.clicked.connect(lambda: self.send_arduino('f'))
        movement_layout.addWidget(self.btn_forward_fine)
        
        self.btn_forward_coarse = QPushButton("Coarse Forward ►►")
        self.btn_forward_coarse.clicked.connect(lambda: self.send_arduino('F'))
        movement_layout.addWidget(self.btn_forward_coarse)
        
        motor_layout.addLayout(movement_layout)
        
        # Frame advance buttons
        frame_layout = QHBoxLayout()
        
        self.btn_frame_back = QPushButton("⏪ Previous Frame")
        self.btn_frame_back.clicked.connect(self.backup_frame)
        frame_layout.addWidget(self.btn_frame_back)
        
        self.btn_frame_forward = QPushButton("Next Frame ⏩")
        self.btn_frame_forward.clicked.connect(self.advance_frame)
        frame_layout.addWidget(self.btn_frame_forward)
        
        motor_layout.addLayout(frame_layout)
        
        # Zero and lock
        control_layout = QHBoxLayout()
        
        self.btn_zero = QPushButton("Zero Position")
        self.btn_zero.clicked.connect(lambda: self.send_arduino('Z'))
        control_layout.addWidget(self.btn_zero)
        
        self.btn_motor_toggle = QPushButton("Motor: ON")
        self.btn_motor_toggle.setCheckable(True)
        self.btn_motor_toggle.setChecked(True)
        self.btn_motor_toggle.clicked.connect(self.toggle_motor)
        control_layout.addWidget(self.btn_motor_toggle)
        
        motor_layout.addLayout(control_layout)
        
        motor_group.setLayout(motor_layout)
        right_layout.addWidget(motor_group)
        
        # Bottom: Session Controls
        session_group = QGroupBox("Session Control")
        session_layout = QVBoxLayout()
        
        # Roll management
        roll_layout = QHBoxLayout()
        roll_layout.addWidget(QLabel("Roll Name:"))
        self.txt_roll_name = QLineEdit()
        self.txt_roll_name.setPlaceholderText("e.g., Kodak-Portra400-001")
        roll_layout.addWidget(self.txt_roll_name)
        
        self.btn_new_roll = QPushButton("New Roll")
        self.btn_new_roll.clicked.connect(self.new_roll)
        roll_layout.addWidget(self.btn_new_roll)
        
        session_layout.addLayout(roll_layout)
        
        # Calibration and capture
        action_layout = QHBoxLayout()
        
        self.btn_calibrate = QPushButton("📏 Calibrate (C)")
        self.btn_calibrate.clicked.connect(self.start_calibration)
        action_layout.addWidget(self.btn_calibrate)
        
        self.btn_new_strip = QPushButton("🎞️ New Strip (S)")
        self.btn_new_strip.clicked.connect(self.new_strip)
        action_layout.addWidget(self.btn_new_strip)
        
        self.btn_capture = QPushButton("📷 CAPTURE (Space)")
        self.btn_capture.clicked.connect(self.capture_frame)
        self.btn_capture.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; font-size: 14px;")
        action_layout.addWidget(self.btn_capture)
        
        session_layout.addLayout(action_layout)
        
        # Auto-advance control
        advance_layout = QHBoxLayout()
        
        self.chk_auto_advance = QCheckBox("Auto-advance after capture")
        self.chk_auto_advance.setChecked(True)
        self.chk_auto_advance.stateChanged.connect(self.toggle_auto_advance)
        advance_layout.addWidget(self.chk_auto_advance)
        
        session_layout.addLayout(advance_layout)
        
        session_group.setLayout(session_layout)
        right_layout.addWidget(session_group)
        
        # Log area
        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout()
        
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumHeight(150)
        log_layout.addWidget(self.txt_log)
        
        log_group.setLayout(log_layout)
        right_layout.addWidget(log_group)
        
        # Add right panel to splitter
        splitter.addWidget(right_panel)
        
        # Set splitter proportions (60% live view, 40% controls)
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)
        
        # Add splitter to main layout
        main_layout.addWidget(splitter)
        
        # Status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready")
        
        # Menu bar
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("File")
        
        new_action = QAction("New Roll", self)
        new_action.triggered.connect(self.new_roll)
        file_menu.addAction(new_action)
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        help_menu = menubar.addMenu("Help")
        
        shortcuts_action = QAction("Keyboard Shortcuts", self)
        shortcuts_action.triggered.connect(self.show_shortcuts)
        help_menu.addAction(shortcuts_action)
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Arrow keys for movement
        QShortcut(QKeySequence(Qt.Key_Left), self).activated.connect(lambda: self.send_arduino('b'))
        QShortcut(QKeySequence(Qt.Key_Right), self).activated.connect(lambda: self.send_arduino('f'))
        QShortcut(QKeySequence(Qt.Key_Left | Qt.SHIFT), self).activated.connect(self.backup_frame)
        QShortcut(QKeySequence(Qt.Key_Right | Qt.SHIFT), self).activated.connect(self.advance_frame)
        
        # Capture
        QShortcut(QKeySequence(Qt.Key_Space), self).activated.connect(self.capture_frame)
        
        # Session controls
        QShortcut(QKeySequence("C"), self).activated.connect(self.start_calibration)
        QShortcut(QKeySequence("S"), self).activated.connect(self.new_strip)
        QShortcut(QKeySequence("N"), self).activated.connect(self.new_roll)
        QShortcut(QKeySequence("Z"), self).activated.connect(lambda: self.send_arduino('Z'))
    
    def connect_arduino(self):
        """Connect to Arduino"""
        self.log("Searching for Arduino...")
        if self.arduino.find_and_connect():
            self.log("Arduino connected successfully")
        else:
            self.log("Arduino not found - check USB connection")
            QMessageBox.warning(self, "Connection Error", 
                              "Arduino not found. Please check USB connection and try again.")
    
    def send_arduino(self, cmd: str):
        """Send command to Arduino"""
        self.arduino.send_command(cmd)
    
    @Slot(int)
    def on_position_updated(self, position: int):
        """Update position display"""
        self.position = position
        self.lbl_position.setText(f"{position} steps")
    
    @Slot(str)
    def show_status(self, message: str):
        """Show status message"""
        self.statusBar.showMessage(message, 5000)
        self.log(message)
    
    @Slot(bool)
    def on_arduino_connection(self, connected: bool):
        """Update connection status"""
        if connected:
            self.lbl_connection.setText("Connected ✓")
            self.lbl_connection.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.lbl_connection.setText("Disconnected ✗")
            self.lbl_connection.setStyleSheet("color: red; font-weight: bold;")
    
    @Slot(bool)
    def on_camera_connection(self, connected: bool):
        """Update camera connection status"""
        if connected:
            self.lbl_camera_status.setText("Connected ✓")
            self.lbl_camera_status.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.lbl_camera_status.setText("Disconnected ✗")
            self.lbl_camera_status.setStyleSheet("color: red; font-weight: bold;")
    
    @Slot(np.ndarray)
    def on_frame_ready(self, frame: np.ndarray):
        """Update live view with new frame"""
        self.live_view.update_frame(frame)
    
    def toggle_live_view(self):
        """Toggle live view on/off"""
        if self.btn_toggle_liveview.isChecked():
            if self.camera.start_live_view():
                self.btn_toggle_liveview.setText("Stop Live View")
                self.log("Live view started")
            else:
                self.btn_toggle_liveview.setChecked(False)
                self.log("Failed to start live view")
        else:
            self.camera.stop_live_view()
            self.btn_toggle_liveview.setText("Start Live View")
            self.log("Live view stopped")
    
    def toggle_invert_colors(self, state):
        """Toggle color inversion for film positive preview"""
        enabled = (state == Qt.Checked)
        self.live_view.toggle_invert(enabled)
        self.log(f"Color inversion: {'ON' if enabled else 'OFF'}")
    
    def log(self, message: str):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.txt_log.append(f"[{timestamp}] {message}")
    
    def toggle_motor(self):
        """Toggle motor on/off"""
        if self.btn_motor_toggle.isChecked():
            self.send_arduino('E')
            self.btn_motor_toggle.setText("Motor: ON")
        else:
            self.send_arduino('M')
            self.btn_motor_toggle.setText("Motor: OFF")
    
    def advance_frame(self):
        """Advance to next frame"""
        if self.frame_advance:
            self.send_arduino(f'H{self.frame_advance}')
            self.log(f"Advanced {self.frame_advance} steps")
        else:
            self.send_arduino(f'H1200')  # Default
            self.log("Advanced 1200 steps (default - not calibrated)")
    
    def backup_frame(self):
        """Go back one frame"""
        if self.frame_advance:
            self.send_arduino(f'h{self.frame_advance}')
            self.log(f"Backed up {self.frame_advance} steps")
        else:
            self.send_arduino(f'h1200')  # Default
            self.log("Backed up 1200 steps (default - not calibrated)")
    
    def toggle_auto_advance(self, state):
        """Toggle auto-advance"""
        self.auto_advance = (state == Qt.Checked)
        self.log(f"Auto-advance: {'ON' if self.auto_advance else 'OFF'}")
    
    def new_roll(self):
        """Create new roll"""
        roll_name = self.txt_roll_name.text().strip()
        
        if not roll_name:
            QMessageBox.warning(self, "Invalid Input", "Please enter a roll name")
            return
        
        self.roll_name = roll_name
        self.lbl_roll.setText(roll_name)
        
        # Create folder
        date_folder = datetime.now().strftime("%Y-%m-%d")
        self.roll_folder = Path.home() / "scans" / date_folder / roll_name
        self.roll_folder.mkdir(parents=True, exist_ok=True)
        
        self.state_file = self.roll_folder / ".scan_state.json"
        
        # Check for existing state
        if self.state_file.exists():
            reply = QMessageBox.question(self, "Existing Roll Found",
                                        "Found existing roll data. Resume scanning?",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.load_state()
                self.log(f"Resumed roll: {roll_name}")
                return
        
        # New roll
        self.frame_count = 0
        self.strip_count = 0
        self.frames_in_strip = 0
        self.total_strips = 0
        self.frame_advance = None
        self.calibration_complete = False
        
        self.update_display()
        self.save_state()
        
        self.log(f"📼 New roll created: {roll_name}")
        self.log(f"   Expected: ~{36 // self.frames_per_strip} strips × {self.frames_per_strip} frames")
        self.log("Next steps:")
        self.log("   1. Hand-feed strip 1 (frame 1 will be halfway across mask)")
        self.log("   2. Press C to calibrate (captures frames 1 & 2)")
        self.log(f"   3. Press SPACE to capture frames 3-{self.frames_per_strip}")
    
    def start_calibration(self):
        """Start calibration wizard - Captures frames 1 and 2 to learn spacing"""
        if not self.roll_name:
            QMessageBox.warning(self, "No Roll", "Please create a new roll first (N key)")
            return
        
        # Show calibration dialog
        msg = QMessageBox(self)
        msg.setWindowTitle("Calibration - Strip 1")
        msg.setText("📏 CALIBRATION MODE\n\n"
                   "This will capture frames 1 and 2 to learn frame spacing.\n\n"
                   "Workflow:\n"
                   "1. Align frame 1 perfectly with arrow keys\n"
                   "2. Capture frame 1\n"
                   "3. Move to frame 2 with arrow keys\n"
                   "4. Capture frame 2\n"
                   "5. System calculates frame spacing\n"
                   f"6. Continue with frames 3-{self.frames_per_strip} using SPACE\n\n"
                   "Ready to begin?")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        
        if msg.exec() != QMessageBox.Ok:
            return
        
        # Start strip 1
        self.strip_count = 1
        self.frames_in_strip = 0
        
        # Position and capture frame 1
        msg1 = QMessageBox(self)
        msg1.setWindowTitle("Calibration - Frame 1")
        msg1.setText("STEP 1: Capture Frame 1\n\n"
                    "Use arrow keys to align frame 1 perfectly.\n\n"
                    "Note: Frame 1 started halfway across the mask - normal!\n"
                    "The motor engages in the middle of the scanning area.\n\n"
                    f"Current position: {self.position} steps\n\n"
                    "Click OK to CAPTURE frame 1")
        msg1.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        
        if msg1.exec() != QMessageBox.Ok:
            return
        
        # Capture frame 1
        frame1_pos = self.position
        self.frame_count += 1
        self.frames_in_strip += 1
        self.save_state()
        
        self.log(f"📷 Frame 1 captured at position: {frame1_pos}")
        
        # Position and capture frame 2
        msg2 = QMessageBox(self)
        msg2.setWindowTitle("Calibration - Frame 2")
        msg2.setIcon(QMessageBox.Information)
        msg2.setText(f"STEP 2: Capture Frame 2\n\n"
                    f"Frame 1 position: {frame1_pos}\n"
                    f"Current position: {self.position}\n"
                    f"Distance so far: {self.position - frame1_pos} steps\n\n"
                    "Use arrow keys to align frame 2 perfectly.\n\n"
                    "Click OK to CAPTURE frame 2")
        msg2.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        
        result = msg2.exec()
        
        if result != QMessageBox.Ok:
            return
        
        # Calculate frame spacing and capture frame 2
        frame2_pos = self.position
        self.frame_advance = frame2_pos - frame1_pos
        
        if self.frame_advance <= 0:
            QMessageBox.critical(self, "Calibration Error",
                               "Frame 2 must be ahead of frame 1!\n\n"
                               "Please try calibration again.")
            return
        
        # Capture frame 2
        self.frame_count += 1
        self.frames_in_strip += 1
        self.calibration_complete = True
        
        self.lbl_frame_advance.setText(f"{self.frame_advance} steps")
        self.lbl_frame_advance.setStyleSheet("color: green; font-weight: bold;")
        
        self.update_display()
        self.save_state()
        
        self.log(f"📷 Frame 2 captured at position: {frame2_pos}")
        self.log(f"✓ Calibration complete! Frame spacing: {self.frame_advance} steps")
        
        # Show next steps
        remaining = self.frames_per_strip - self.frames_in_strip
        next_msg = QMessageBox(self)
        next_msg.setWindowTitle("Calibration Complete ✓")
        next_msg.setIcon(QMessageBox.Information)
        next_msg.setText(f"✓ Frames 1 and 2 captured!\n"
                        f"✓ Frame spacing learned: {self.frame_advance} steps\n\n"
                        "NEXT STEPS:\n\n"
                        f"Press SPACE to capture frames 3-{self.frames_per_strip}\n"
                        f"({remaining} frames remaining in this strip)\n\n"
                        "Motor will auto-advance using the calibrated spacing.\n"
                        "You can always fine-tune position with arrow keys\n"
                        "before each capture!\n\n"
                        "When strip complete, press S for next strip.")
        next_msg.exec()
        
        self.update_display()
    
    def new_strip(self):
        """Start new strip"""
        if not self.roll_name:
            QMessageBox.warning(self, "No Roll", "Please create a new roll first")
            return
        
        if not self.calibration_complete:
            QMessageBox.warning(self, "Not Calibrated", 
                              "Please calibrate frame spacing first (C key)\n\n"
                              "Calibration measures the distance between frames.")
            return
        
        # Increment strip counter if this isn't the first strip
        if self.strip_count > 0:
            self.total_strips += 1
        
        self.strip_count += 1
        self.frames_in_strip = 0
        
        msg = QMessageBox(self)
        msg.setWindowTitle("New Strip")
        msg.setIcon(QMessageBox.Information)
        msg.setText(f"Starting Strip {self.strip_count}\n\n"
                   f"Expected frames: {self.frames_per_strip}\n"
                   f"Total frames so far: {self.frame_count}\n\n"
                   "Instructions:\n"
                   "1. Hand-feed the new strip\n"
                   "2. Position frame 1 using arrow keys\n"
                   "3. Press SPACE to capture frame 1\n"
                   f"4. Continue for frames 2-{self.frames_per_strip}\n\n"
                   "💡 Motor will auto-advance using calibrated spacing\n"
                   "   Fine-tune with arrow keys as needed before each capture")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        
        if msg.exec() != QMessageBox.Ok:
            return
        
        self.update_display()
        self.save_state()
        
        self.log(f"🎞️ Strip {self.strip_count} ready - Position frame 1 and press SPACE")
    
    def capture_frame(self):
        """Capture current frame: Autofocus -> Capture -> Advance (all in one!)"""
        if self.is_capturing:
            self.log("Capture already in progress...")
            return
        
        if not self.roll_name:
            QMessageBox.warning(self, "No Roll", "Please create a new roll first (N key)")
            return
        
        if not self.calibration_complete:
            reply = QMessageBox.question(self, "Not Calibrated",
                                        "You haven't calibrated frame spacing yet.\n\n"
                                        "Do you want to capture anyway?",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
        
        # If starting a new strip, increment strip count
        if self.frames_in_strip == 0 and self.strip_count == 0:
            self.strip_count = 1
        
        self.is_capturing = True
        
        # Step 1: Autofocus
        self.log("🎯 Autofocusing...")
        self.statusBar.showMessage("Autofocusing...", 3000)
        
        if self.camera.camera:
            if not self.camera.autofocus():
                self.log("⚠️ Autofocus failed (continuing anyway)")
        
        # Step 2: Capture image
        self.log("📷 Capturing image...")
        self.statusBar.showMessage("Capturing...", 3000)
        
        # Generate filename
        frame_filename = f"{self.roll_name}_frame_{self.frame_count + 1:04d}.jpg"
        save_path = str(self.roll_folder / frame_filename)
        
        capture_success = False
        if self.camera.camera:
            capture_success = self.camera.capture_image(save_path)
        
        if not capture_success:
            self.log("⚠️ Capture failed - no camera or capture error")
            self.is_capturing = False
            return
        
        # Update counts
        self.frame_count += 1
        self.frames_in_strip += 1
        
        self.update_display()
        self.save_state()
        
        # Check if strip is complete
        strip_complete = (self.frames_in_strip >= self.frames_per_strip)
        
        if strip_complete:
            self.log(f"✓ Frame {self.frames_in_strip} captured - STRIP {self.strip_count} COMPLETE ({self.frames_per_strip} frames)")
            self.log(f"   Total frames: {self.frame_count}")
            self.statusBar.showMessage(f"Strip {self.strip_count} complete! Press S for next strip", 10000)
        else:
            remaining = self.frames_per_strip - self.frames_in_strip
            self.log(f"✓ Frame {self.frames_in_strip} captured (Strip {self.strip_count}, {remaining} remaining)")
        
        # Step 3: Auto-advance if enabled AND not at end of strip
        if self.auto_advance and self.frame_advance and not strip_complete:
            self.log(f"⏩ Auto-advancing {self.frame_advance} steps...")
            self.statusBar.showMessage("Advancing to next frame...", 3000)
            QTimer.singleShot(500, self.advance_frame)
        
        self.is_capturing = False
    
    
    def update_display(self):
        """Update all display elements"""
        self.lbl_frame_count.setText(str(self.frame_count))
        
        # Show progress within current strip
        if self.strip_count > 0:
            self.lbl_strip_info.setText(
                f"Strip {self.strip_count}, Frame {self.frames_in_strip}/{self.frames_per_strip}"
            )
        else:
            self.lbl_strip_info.setText("No strip started")
        
        if self.frame_advance:
            self.lbl_frame_advance.setText(f"{self.frame_advance} steps")
            self.lbl_frame_advance.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.lbl_frame_advance.setText("Not calibrated")
            self.lbl_frame_advance.setStyleSheet("color: orange;")
    
    def update_frames_per_strip(self, value):
        """Update frames per strip setting"""
        self.frames_per_strip = value
        self.log(f"Frames per strip set to: {value}")
        self.update_display()
        self.save_state()
    
    def save_state(self):
        """Save current state to JSON"""
        if not self.state_file:
            return
        
        state = {
            'roll_name': self.roll_name,
            'frame_count': self.frame_count,
            'strip_count': self.strip_count,
            'frames_in_strip': self.frames_in_strip,
            'total_strips': self.total_strips,
            'position': self.position,
            'frame_advance': self.frame_advance,
            'calibration_complete': self.calibration_complete,
            'frames_per_strip': self.frames_per_strip,
            'auto_advance': self.auto_advance,
            'last_updated': datetime.now().isoformat()
        }
        
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            self.log(f"Error saving state: {e}")
    
    def load_state(self):
        """Load state from JSON"""
        if not self.state_file or not self.state_file.exists():
            return
        
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            self.frame_count = state.get('frame_count', 0)
            self.strip_count = state.get('strip_count', 0)
            self.frames_in_strip = state.get('frames_in_strip', 0)
            self.total_strips = state.get('total_strips', 0)
            self.position = state.get('position', 0)
            self.frame_advance = state.get('frame_advance')
            self.calibration_complete = state.get('calibration_complete', False)
            self.frames_per_strip = state.get('frames_per_strip', 6)
            self.auto_advance = state.get('auto_advance', True)
            
            self.chk_auto_advance.setChecked(self.auto_advance)
            self.spin_frames_per_strip.setValue(self.frames_per_strip)
            self.update_display()
            
        except Exception as e:
            self.log(f"Error loading state: {e}")
    
    def show_shortcuts(self):
        """Show keyboard shortcuts dialog"""
        shortcuts_text = """
        Keyboard Shortcuts:
        
        Movement:
        ← / →           Fine adjustment (left/right)
        Shift+← / →     Full frame back/forward
        
        Session Control:
        Space           Capture frame
        C               Calibrate frame spacing
        S               Start new strip
        N               New roll
        Z               Zero position
        
        Motor Control:
        Arrow keys for fine positioning
        """
        
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts_text)
    
    def closeEvent(self, event):
        """Handle window close"""
        self.arduino.disconnect()
        self.camera.disconnect()
        event.accept()


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Set application-wide font
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    # Create and show main window
    window = FilmScannerApp()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

