#!/usr/bin/env bash
# ============================================================================
# Film Scanner - Installation Verification Script
# ============================================================================
# Run this after setup to verify everything is working correctly
# ============================================================================

set -euo pipefail

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}=========================================${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}=========================================${NC}"
}

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Detect install location
if [[ -d "/opt/film-scanner" ]]; then
    APP_DIR="/opt/film-scanner"
elif [[ -d "$HOME/Film-Scanner" ]]; then
    APP_DIR="$HOME/Film-Scanner"
else
    APP_DIR="$(pwd)"
fi

print_header "Film Scanner - Installation Verification"
echo ""
echo "Testing directory: $APP_DIR"
echo ""

# Test 1: Python virtual environment
print_header "Python Environment"
if [[ -f "$APP_DIR/.venv/bin/python" ]]; then
    check_pass "Virtual environment exists"
    PYTHON="$APP_DIR/.venv/bin/python"
else
    check_fail "Virtual environment not found"
    PYTHON=$(which python3)
    check_warn "Using system Python: $PYTHON"
fi

echo ""
"$PYTHON" --version || check_fail "Python not working"

# Test 2: Python dependencies
print_header "Python Dependencies"
"$PYTHON" << 'EOF'
import sys

deps = [
    ("Flask", "flask"),
    ("Flask-SocketIO", "flask_socketio"),
    ("pyserial", "serial"),
    ("NumPy", "numpy"),
    ("OpenCV", "cv2"),
    ("Pillow", "PIL"),
    ("pygame", "pygame"),
    ("evdev", "evdev"),
    ("psutil", "psutil"),
]

failed = []
for name, module in deps:
    try:
        __import__(module)
        print(f"✓ {name}")
    except ImportError as e:
        print(f"✗ {name}: {e}")
        failed.append(name)

if failed:
    print(f"\n✗ Failed imports: {', '.join(failed)}")
    sys.exit(1)
else:
    print("\n✓ All dependencies OK")
EOF

if [[ $? -ne 0 ]]; then
    check_fail "Dependency check failed"
    exit 1
fi

# Test 3: System packages
print_header "System Packages"

if command -v gphoto2 &> /dev/null; then
    check_pass "gphoto2 installed"
    gphoto2 --version | head -1
else
    check_fail "gphoto2 not found"
fi

if command -v ffmpeg &> /dev/null; then
    check_pass "ffmpeg installed"
else
    check_warn "ffmpeg not found (optional)"
fi

# Test 4: Hardware permissions
print_header "Hardware Permissions"

if groups | grep -q dialout; then
    check_pass "User in dialout group (Arduino access)"
else
    check_fail "User NOT in dialout group - run: sudo usermod -a -G dialout $USER"
fi

if groups | grep -q video; then
    check_pass "User in video group (framebuffer access)"
else
    check_warn "User NOT in video group (needed for touchscreen)"
fi

if groups | grep -q input; then
    check_pass "User in input group (touch input)"
else
    check_warn "User NOT in input group (needed for touchscreen)"
fi

# Test 5: Serial ports
print_header "Serial Ports (Arduino)"
echo "Available serial ports:"
if ls /dev/ttyACM* &> /dev/null; then
    ls -l /dev/ttyACM* | while read line; do
        echo "  $line"
    done
    check_pass "Found /dev/ttyACM* ports"
elif ls /dev/ttyUSB* &> /dev/null; then
    ls -l /dev/ttyUSB* | while read line; do
        echo "  $line"
    done
    check_pass "Found /dev/ttyUSB* ports"
else
    check_warn "No Arduino detected (connect Arduino and check connection)"
fi

# Test 6: Camera detection
print_header "Camera Detection"
if command -v gphoto2 &> /dev/null; then
    echo "Detecting camera..."
    if timeout 5 gphoto2 --auto-detect 2>&1 | grep -q "usb"; then
        check_pass "Camera detected"
        timeout 5 gphoto2 --auto-detect | grep "usb"
    else
        check_warn "No camera detected (make sure camera is ON and in PTP mode)"
    fi
else
    check_fail "gphoto2 not installed - cannot detect camera"
fi

# Test 7: Network
print_header "Network Configuration"
if command -v hostname &> /dev/null; then
    HOSTNAME=$(hostname)
    check_pass "Hostname: $HOSTNAME"
fi

if command -v hostname &> /dev/null; then
    IPS=$(hostname -I 2>/dev/null || echo "")
    if [[ -n "$IPS" ]]; then
        check_pass "IP addresses: $IPS"
        echo ""
        echo "Web interface should be accessible at:"
        for IP in $IPS; do
            echo "  http://${IP}:5000"
        done
        echo "  http://${HOSTNAME}.local:5000"
    else
        check_warn "No IP address found (not connected to network?)"
    fi
fi

# Test 8: Services
print_header "Systemd Services"
if systemctl list-unit-files | grep -q film-scanner.service; then
    check_pass "Web app service installed"
    
    if systemctl is-enabled film-scanner.service &> /dev/null; then
        check_pass "Web app enabled (starts on boot)"
    else
        check_warn "Web app not enabled for auto-start"
    fi
    
    if systemctl is-active film-scanner.service &> /dev/null; then
        check_pass "Web app currently running"
    else
        check_warn "Web app not currently running (use: start-scanner)"
    fi
else
    check_warn "Web app service not installed (manual mode)"
fi

if systemctl list-unit-files | grep -q film-scanner-touchscreen.service; then
    check_pass "Touchscreen service installed"
else
    check_warn "Touchscreen service not installed (optional)"
fi

# Test 9: Directories
print_header "Data Directories"
if [[ -d "$HOME/scans" ]]; then
    check_pass "Scans directory: $HOME/scans"
else
    check_warn "Scans directory not found - will be created on first scan"
fi

if [[ -d "$HOME/.film_scanner" ]]; then
    check_pass "Config directory: $HOME/.film_scanner"
else
    check_warn "Config directory not found - will be created on first run"
fi

# Test 10: Alignment detector
print_header "Alignment System"
echo "Testing frame detection module..."
"$PYTHON" << 'EOF'
try:
    from frame_detector import detect_frame_gap, jpeg_bytes_to_color
    print("✓ Frame detector module loaded")
    print("✓ Automatic alignment improvements available")
    
    # Test detection functions exist
    import cv2
    import numpy as np
    print("✓ OpenCV and NumPy integration OK")
    
except ImportError as e:
    print(f"✗ Frame detector import failed: {e}")
    exit(1)
EOF

if [[ $? -eq 0 ]]; then
    check_pass "Alignment system verified"
else
    check_fail "Alignment system test failed"
fi

# Summary
print_header "Verification Summary"
echo ""
echo "System ready for film scanning!"
echo ""
echo "Next steps:"
echo "  1. Connect Arduino: Plug in via USB"
echo "  2. Connect Camera: Turn ON, set to PTP mode"
echo "  3. Start scanner: start-scanner (or python3 web_app.py)"
echo "  4. Access web UI: http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "Helper commands:"
echo "  start-scanner          - Start web interface"
echo "  stop-scanner           - Stop web interface"
echo "  film-scanner status    - Check service status"
echo "  film-scanner web       - Run web app directly"
echo ""
echo "Logs:"
echo "  journalctl -u film-scanner -f"
echo ""
