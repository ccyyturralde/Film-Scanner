#!/usr/bin/env bash
# ============================================================================
# Film Scanner - Comprehensive Raspberry Pi Setup
# ============================================================================
# One-touch installation for Film Scanner on Raspberry Pi
# Supports Pi OS Bookworm/Trixie (Debian 12/13)
#
# This script installs:
# - All system dependencies
# - Python packages (Flask, pygame, evdev, etc.)
# - TFT touchscreen support (optional)
# - Systemd services for auto-start
#
# Run with: sudo bash scripts/setup_pi.sh
# ============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}=========================================${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}=========================================${NC}"
}

print_step() {
    echo -e "${GREEN}[+]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check for root
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    print_error "Please run with sudo: sudo bash $0"
    exit 1
fi

# Get actual user (not root)
APP_USER=${SUDO_USER:-pi}
if ! id -u "$APP_USER" >/dev/null 2>&1; then
    APP_USER="$(logname 2>/dev/null || echo pi)"
fi
APP_HOME=$(eval echo ~$APP_USER)

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="/opt/film-scanner"
SERVICE_WEB="film-scanner.service"
SERVICE_TOUCH="film-scanner-touchscreen.service"
CONFIG_DIR="$APP_HOME/.film_scanner"

print_header "Film Scanner - Raspberry Pi Installer"
echo ""
echo "User:        $APP_USER"
echo "Home:        $APP_HOME"
echo "Source:      $REPO_ROOT"
echo "Install to:  $APP_DIR"
echo ""

# Detect Raspberry Pi
if [[ -f /proc/device-tree/model ]]; then
    PI_MODEL=$(cat /proc/device-tree/model | tr -d '\0')
    print_step "Detected: $PI_MODEL"
else
    print_warning "Raspberry Pi not detected - continuing anyway"
fi

# Detect OS version
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    print_step "OS: $PRETTY_NAME"
fi

# Determine boot config path (differs between Pi OS versions)
if [[ -f /boot/firmware/config.txt ]]; then
    BOOT_CONFIG="/boot/firmware/config.txt"
elif [[ -f /boot/config.txt ]]; then
    BOOT_CONFIG="/boot/config.txt"
else
    BOOT_CONFIG=""
    print_warning "Boot config not found - TFT setup may need manual configuration"
fi

print_header "Installing System Packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y

# Core system packages
print_step "Installing core packages..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    rsync \
    avahi-daemon

# Camera support
print_step "Installing camera support (gphoto2)..."
apt-get install -y \
    gphoto2 \
    libgphoto2-dev \
    ffmpeg

# Image processing libraries
print_step "Installing image processing libraries..."
apt-get install -y \
    libjpeg-dev \
    libtiff-dev \
    libopenjp2-7 \
    libpng-dev \
    libfreetype-dev \
    || true

# Try alternative package names for different Debian versions
apt-get install -y libatlas-base-dev 2>/dev/null \
    || apt-get install -y libatlas3-base 2>/dev/null \
    || apt-get install -y libopenblas-dev 2>/dev/null \
    || true

# SDL2 and pygame dependencies
print_step "Installing SDL2 and display libraries..."
apt-get install -y \
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-ttf-dev \
    libsdl2-mixer-dev \
    libportmidi-dev

# Fonts
print_step "Installing fonts..."
apt-get install -y \
    fonts-dejavu \
    fonts-dejavu-core \
    fonts-dejavu-extra

# Python packages (system packages where available - faster than pip)
print_step "Installing Python system packages..."
apt-get install -y \
    python3-flask \
    python3-pygame \
    python3-numpy \
    python3-pil \
    python3-serial \
    python3-psutil \
    python3-evdev \
    python3-opencv || true  # opencv may not be in all repos

# Input/touch tools
print_step "Installing input tools..."
apt-get install -y \
    evtest \
    input-utils || true

print_header "Installing Application"

# Copy application to /opt
print_step "Copying application to $APP_DIR..."
mkdir -p "$APP_DIR"
rsync -a --delete \
    --exclude ".git" \
    --exclude ".github" \
    --exclude "__pycache__" \
    --exclude "*.pyc" \
    --exclude ".venv" \
    "$REPO_ROOT"/ "$APP_DIR"/

# Create virtual environment
print_step "Creating Python virtual environment..."
if [[ ! -f "$APP_DIR/.venv/bin/python" ]]; then
    python3 -m venv "$APP_DIR/.venv" --system-site-packages
fi

# Install Python packages via pip (ones not in system repos or need newer versions)
print_step "Installing Python packages..."
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install \
    Flask>=2.3.0 \
    Flask-SocketIO>=5.3.0 \
    python-socketio>=5.9.0 \
    simple-websocket>=0.10.0 \
    eventlet>=0.33.0 \
    pyserial>=3.5 \
    Pillow>=10.0.0 \
    numpy>=1.24.0 \
    pygame>=2.5.0 \
    evdev>=1.6.0 \
    psutil>=5.9.0

# Try to install opencv-python-headless (may fail on some systems)
"$APP_DIR/.venv/bin/pip" install opencv-python-headless>=4.8.0 || {
    print_warning "opencv-python-headless installation failed - using system opencv"
}

# Set ownership
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# Add user to required groups for hardware access
print_step "Adding $APP_USER to hardware access groups..."
usermod -a -G video "$APP_USER" 2>/dev/null || true    # Framebuffer access
usermod -a -G input "$APP_USER" 2>/dev/null || true    # Touch/input device access
usermod -a -G dialout "$APP_USER" 2>/dev/null || true  # Serial port access (Arduino)
usermod -a -G gpio "$APP_USER" 2>/dev/null || true     # GPIO access
usermod -a -G spi "$APP_USER" 2>/dev/null || true      # SPI access
usermod -a -G i2c "$APP_USER" 2>/dev/null || true      # I2C access

print_header "Creating Directories"

# Create data directories
print_step "Creating data directories..."
install -d -o "$APP_USER" -g "$APP_USER" "$APP_HOME/scans"
install -d -o "$APP_USER" -g "$APP_USER" "$CONFIG_DIR"

# Create default config
print_step "Creating default configuration..."
cat > "$CONFIG_DIR/touchscreen_config.json" << 'CONFIGEOF'
{
  "config_version": 1,
  "display": {
    "width": 480,
    "height": 320,
    "framebuffer": "/dev/fb0",
    "touch_device": "/dev/input/touchscreen",
    "rotation": 0,
    "touch_swap_xy": false,
    "touch_invert_x": false,
    "touch_invert_y": true,
    "fullscreen": true,
    "show_cursor": false,
    "backlight_pin": 18,
    "screen_timeout": 300
  },
  "colors": {
    "bg_primary": [17, 24, 39],
    "bg_secondary": [31, 41, 55],
    "bg_panel": [55, 65, 81],
    "text_primary": [249, 250, 251],
    "text_secondary": [156, 163, 175],
    "text_muted": [107, 114, 128],
    "success": [16, 185, 129],
    "warning": [245, 158, 11],
    "error": [239, 68, 68],
    "info": [37, 99, 235],
    "btn_primary": [37, 99, 235],
    "btn_primary_hover": [30, 64, 175],
    "btn_secondary": [107, 114, 128],
    "btn_secondary_hover": [55, 65, 81],
    "btn_danger": [239, 68, 68],
    "btn_danger_hover": [220, 38, 38],
    "btn_success": [16, 185, 129],
    "btn_success_hover": [5, 150, 105],
    "btn_warning": [245, 158, 11],
    "btn_warning_hover": [217, 119, 6],
    "border": [75, 85, 99],
    "border_active": [37, 99, 235]
  },
  "ui": {
    "font_size_large": 28,
    "font_size_medium": 20,
    "font_size_small": 16,
    "font_size_tiny": 12,
    "font_family": "DejaVu Sans",
    "font_family_mono": "DejaVu Sans Mono",
    "button_height": 50,
    "button_width": 140,
    "button_margin": 8,
    "button_radius": 8,
    "panel_padding": 12,
    "panel_radius": 10,
    "status_bar_height": 36,
    "log_lines_visible": 8,
    "log_line_height": 20
  },
  "app": {
    "auto_start_app": false,
    "auto_restart": true,
    "auto_restart_delay": 5.0,
    "status_refresh_interval": 2.0,
    "log_refresh_interval": 1.0,
    "web_app_port": 5000,
    "web_app_path": "",
    "max_log_entries": 500,
    "max_error_entries": 100
  }
}
CONFIGEOF
chown "$APP_USER:$APP_USER" "$CONFIG_DIR/touchscreen_config.json"

print_header "Setting Up Systemd Services"

# Web app service
print_step "Creating web app service..."
cat > /etc/systemd/system/$SERVICE_WEB << EOF
[Unit]
Description=Film Scanner Web Application
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/web_app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Touchscreen UI service (uses direct framebuffer, not SDL)
print_step "Creating touchscreen UI service..."
cat > /etc/systemd/system/$SERVICE_TOUCH << EOF
[Unit]
Description=Film Scanner Touch Screen UI
After=multi-user.target
Wants=systemd-udev-settle.service

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment=PYTHONUNBUFFERED=1

# Direct framebuffer mode (no SDL/X11 required)
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/touchscreen_ui.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

print_header "Creating Helper Commands"

# start-scanner command
cat > /usr/local/bin/start-scanner << 'EOF'
#!/usr/bin/env bash
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    exec sudo "$0" "$@"
fi
systemctl start film-scanner.service
sleep 1
systemctl status film-scanner.service --no-pager --lines=10
EOF
chmod +x /usr/local/bin/start-scanner

# stop-scanner command
cat > /usr/local/bin/stop-scanner << 'EOF'
#!/usr/bin/env bash
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    exec sudo "$0" "$@"
fi
systemctl stop film-scanner.service
systemctl status film-scanner.service --no-pager --lines=5
EOF
chmod +x /usr/local/bin/stop-scanner

# Touch UI commands
cat > /usr/local/bin/start-touchscreen << 'EOF'
#!/usr/bin/env bash
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    exec sudo "$0" "$@"
fi
systemctl start film-scanner-touchscreen.service
sleep 1
systemctl status film-scanner-touchscreen.service --no-pager --lines=10
EOF
chmod +x /usr/local/bin/start-touchscreen

cat > /usr/local/bin/stop-touchscreen << 'EOF'
#!/usr/bin/env bash
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    exec sudo "$0" "$@"
fi
systemctl stop film-scanner-touchscreen.service
systemctl status film-scanner-touchscreen.service --no-pager --lines=5
EOF
chmod +x /usr/local/bin/stop-touchscreen

# Create scanner-run command to run any script with the venv
cat > /usr/local/bin/scanner-run << EOF
#!/usr/bin/env bash
# Run a Python script using the Film Scanner virtual environment
exec $APP_DIR/.venv/bin/python "\$@"
EOF
chmod +x /usr/local/bin/scanner-run

# Create film-scanner command for direct access
cat > /usr/local/bin/film-scanner << EOF
#!/usr/bin/env bash
# Film Scanner command-line interface
APP_DIR="$APP_DIR"
VENV_PYTHON="\$APP_DIR/.venv/bin/python"

case "\$1" in
    web)
        echo "Starting web app..."
        exec "\$VENV_PYTHON" "\$APP_DIR/web_app.py"
        ;;
    touch|touchscreen)
        echo "Starting touchscreen UI..."
        exec sudo "\$VENV_PYTHON" "\$APP_DIR/touchscreen_ui.py"
        ;;
    calibrate)
        echo "Starting touch calibration..."
        exec sudo "\$VENV_PYTHON" "\$APP_DIR/touch_calibrate.py" "\${@:2}"
        ;;
    status)
        echo "=== Web App ==="
        systemctl status film-scanner.service --no-pager --lines=3 2>/dev/null || echo "Not installed as service"
        echo ""
        echo "=== Touchscreen UI ==="
        systemctl status film-scanner-touchscreen.service --no-pager --lines=3 2>/dev/null || echo "Not installed as service"
        ;;
    *)
        echo "Film Scanner CLI"
        echo ""
        echo "Usage: film-scanner <command>"
        echo ""
        echo "Commands:"
        echo "  web          Start the web application"
        echo "  touch        Start the touchscreen UI (requires sudo)"
        echo "  calibrate    Run touch calibration tool"
        echo "  status       Show service status"
        echo ""
        echo "Service commands:"
        echo "  start-scanner       Start web app service"
        echo "  stop-scanner        Stop web app service"
        echo "  start-touchscreen   Start touchscreen service"
        echo "  stop-touchscreen    Stop touchscreen service"
        ;;
esac
EOF
chmod +x /usr/local/bin/film-scanner

print_header "TFT Touchscreen Setup"

echo ""
echo "Do you have a TFT touchscreen connected?"
echo ""
echo "  1) Yes - Set up TFT touchscreen (GPIO/SPI connected)"
echo "  2) No  - Skip touchscreen setup (web interface only)"
echo ""
read -p "Enter choice [1/2]: " tft_choice

if [[ "$tft_choice" == "1" ]]; then
    print_step "Setting up TFT touchscreen..."
    
    # Create udev rules for touch input and framebuffer
    cat > /etc/udev/rules.d/95-touchscreen.rules << 'EOF'
# Touch screen rules - create symlink for touch devices
SUBSYSTEM=="input", ATTRS{name}=="*Touch*", SYMLINK+="input/touchscreen", MODE="0666"
SUBSYSTEM=="input", ATTRS{name}=="*touch*", SYMLINK+="input/touchscreen", MODE="0666"
SUBSYSTEM=="input", ATTRS{name}=="ADS7846*", SYMLINK+="input/touchscreen", MODE="0666"

# Framebuffer access for video group
SUBSYSTEM=="graphics", KERNEL=="fb*", MODE="0660", GROUP="video"
EOF
    udevadm control --reload-rules
    udevadm trigger
    
    # TFT driver selection
    echo ""
    echo "Select your TFT screen type:"
    echo ""
    echo "  1) Generic ILI9486 (most common 3.5\" screens)"
    echo "  2) Waveshare 3.5\" LCD (A)"
    echo "  3) Waveshare 3.5\" LCD (B/C)"
    echo "  4) HDMI touchscreen (no driver needed)"
    echo "  5) Skip driver setup (already configured)"
    echo ""
    read -p "Enter choice [1-5]: " screen_choice
    
    if [[ -n "$BOOT_CONFIG" ]] && [[ "$screen_choice" != "4" ]] && [[ "$screen_choice" != "5" ]]; then
        # Enable SPI
        if ! grep -q "^dtparam=spi=on" "$BOOT_CONFIG"; then
            echo "dtparam=spi=on" >> "$BOOT_CONFIG"
            print_step "Enabled SPI"
        fi
        
        case $screen_choice in
            1)
                if ! grep -q "piscreen" "$BOOT_CONFIG"; then
                    echo "dtoverlay=piscreen,speed=16000000,rotate=270" >> "$BOOT_CONFIG"
                    print_step "Added ILI9486 overlay"
                fi
                ;;
            2)
                if ! grep -q "waveshare35a" "$BOOT_CONFIG"; then
                    echo "dtoverlay=waveshare35a" >> "$BOOT_CONFIG"
                    print_step "Added Waveshare 3.5A overlay"
                fi
                ;;
            3)
                if ! grep -q "waveshare35b" "$BOOT_CONFIG"; then
                    echo "dtoverlay=waveshare35b" >> "$BOOT_CONFIG"
                    print_step "Added Waveshare 3.5B overlay"
                fi
                ;;
        esac
    fi
    
    # Enable touchscreen service
    echo ""
    echo "Enable touchscreen UI to start on boot?"
    read -p "[y/N]: " enable_touch
    if [[ "$enable_touch" == "y" ]] || [[ "$enable_touch" == "Y" ]]; then
        systemctl enable $SERVICE_TOUCH
        print_step "Touchscreen UI will start on boot"
    fi
fi

print_header "Enabling Web App Service"
systemctl enable $SERVICE_WEB
systemctl start $SERVICE_WEB || true

print_header "Installation Complete!"
echo ""
echo "Services:"
echo "  - Web app:      $SERVICE_WEB"
echo "  - Touchscreen:  $SERVICE_TOUCH"
echo ""
echo "Commands:"
echo "  start-scanner       - Start web app"
echo "  stop-scanner        - Stop web app"
echo "  start-touchscreen   - Start touchscreen UI"
echo "  stop-touchscreen    - Stop touchscreen UI"
echo ""
echo "Web interface: http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "Logs:"
echo "  journalctl -u $SERVICE_WEB -f"
echo "  journalctl -u $SERVICE_TOUCH -f"
echo ""

if [[ "$tft_choice" == "1" ]]; then
    print_warning "REBOOT REQUIRED for TFT display driver to load!"
    echo ""
    read -p "Reboot now? [y/N]: " reboot_choice
    if [[ "$reboot_choice" == "y" ]] || [[ "$reboot_choice" == "Y" ]]; then
        echo "Rebooting..."
        reboot
    fi
fi

echo ""
print_step "Setup complete!"
