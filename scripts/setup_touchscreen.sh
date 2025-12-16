#!/bin/bash
# ============================================================================
# Film Scanner - TFT Touchscreen Setup Script
# ============================================================================
# Sets up 3.5" TFT touch screens for the Film Scanner control interface
#
# Supports:
# - Generic ILI9486/ILI9341 based screens
# - Waveshare 3.5" LCD (A/B/C)
# - Elegoo 3.5" TFT
# - Other SPI-based TFT displays
#
# This script:
# - Enables SPI and installs display overlays
# - Installs pygame, evdev, and display dependencies
# - Creates udev rules for touch input
# - Sets up systemd service for auto-start
#
# Works with Pi OS Bookworm/Trixie (Debian 12/13)
# Uses direct framebuffer rendering (not SDL fbcon)
# Uses evdev for touch input (not tslib)
#
# Run with: sudo bash scripts/setup_touchscreen.sh
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    print_warning "Raspberry Pi not detected"
    read -p "Continue anyway? (y/n): " response
    if [ "$response" != "y" ]; then
        exit 1
    fi
fi

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root (use sudo)"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER=${SUDO_USER:-$USER}
ACTUAL_HOME=$(eval echo ~$ACTUAL_USER)

# Determine script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Determine boot config path
if [ -f /boot/firmware/config.txt ]; then
    BOOT_CONFIG="/boot/firmware/config.txt"
elif [ -f /boot/config.txt ]; then
    BOOT_CONFIG="/boot/config.txt"
else
    BOOT_CONFIG=""
fi

print_header "Film Scanner - TFT Touchscreen Setup"
echo ""
echo "User: $ACTUAL_USER"
echo "Home: $ACTUAL_HOME"
echo "Boot config: ${BOOT_CONFIG:-Not found}"
echo ""

# ============================================================================
# Install Dependencies
# ============================================================================
print_header "Installing Dependencies"

apt-get update

# Core packages for touchscreen UI
print_step "Installing display and input packages..."
apt-get install -y \
    python3-pygame \
    python3-pip \
    python3-numpy \
    python3-pil \
    python3-evdev \
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-ttf-dev \
    libsdl2-mixer-dev \
    libfreetype-dev \
    libportmidi-dev \
    libjpeg-dev \
    libpng-dev \
    fonts-dejavu \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    evtest

# Note: We do NOT install tslib - it's not available on modern Debian
# and we use evdev for touch input instead

# Install Python packages
print_step "Installing Python packages..."
sudo -u $ACTUAL_USER pip3 install --break-system-packages --user \
    pygame>=2.5.0 \
    numpy>=1.24.0 \
    pillow>=10.0.0 \
    evdev>=1.6.0 \
    psutil>=5.9.0 || true

# ============================================================================
# TFT Screen Driver Selection
# ============================================================================
print_header "TFT Screen Driver Setup"

echo ""
echo "Select your TFT screen type:"
echo ""
echo "  1) Generic ILI9486 - Most common 3.5\" screens (recommended)"
echo "  2) Generic ILI9341 - Some 2.8\" and 3.2\" screens"
echo "  3) Waveshare 3.5\" LCD (A)"
echo "  4) Waveshare 3.5\" LCD (B/C)"
echo "  5) HDMI touchscreen (no driver needed)"
echo "  6) Skip driver installation (manual/already configured)"
echo ""
read -p "Enter your choice (1-6): " screen_choice

if [ -n "$BOOT_CONFIG" ]; then
    case $screen_choice in
        1|2|3|4)
            print_step "Configuring display driver..."
            
            # Enable SPI if not already enabled
            if grep -q "^#dtparam=spi=on" "$BOOT_CONFIG"; then
                sed -i 's/^#dtparam=spi=on/dtparam=spi=on/' "$BOOT_CONFIG"
                print_step "Enabled SPI (uncommented)"
            elif ! grep -q "^dtparam=spi=on" "$BOOT_CONFIG"; then
                echo "dtparam=spi=on" >> "$BOOT_CONFIG"
                print_step "Enabled SPI (added)"
            else
                print_step "SPI already enabled"
            fi
            
            # Add display overlay based on selection
            case $screen_choice in
                1)
                    if ! grep -q "piscreen" "$BOOT_CONFIG"; then
                        echo "" >> "$BOOT_CONFIG"
                        echo "# TFT Display - ILI9486" >> "$BOOT_CONFIG"
                        echo "dtoverlay=piscreen,speed=16000000,rotate=270" >> "$BOOT_CONFIG"
                        print_step "Added ILI9486 (piscreen) overlay"
                    else
                        print_step "ILI9486 overlay already configured"
                    fi
                    ;;
                2)
                    if ! grep -q "piscreen2r" "$BOOT_CONFIG"; then
                        echo "" >> "$BOOT_CONFIG"
                        echo "# TFT Display - ILI9341" >> "$BOOT_CONFIG"
                        echo "dtoverlay=piscreen2r,speed=16000000,rotate=270" >> "$BOOT_CONFIG"
                        print_step "Added ILI9341 overlay"
                    else
                        print_step "ILI9341 overlay already configured"
                    fi
                    ;;
                3)
                    if ! grep -q "waveshare35a" "$BOOT_CONFIG"; then
                        echo "" >> "$BOOT_CONFIG"
                        echo "# TFT Display - Waveshare 3.5\" (A)" >> "$BOOT_CONFIG"
                        echo "dtoverlay=waveshare35a" >> "$BOOT_CONFIG"
                        echo "dtoverlay=ads7846,cs=1,penirq=25,penirq_pull=2,speed=50000,keep_vref_on=0,swapxy=0,pmax=255,xohms=150,xmin=200,xmax=3900,ymin=200,ymax=3900" >> "$BOOT_CONFIG"
                        print_step "Added Waveshare 3.5A overlay"
                    else
                        print_step "Waveshare overlay already configured"
                    fi
                    ;;
                4)
                    if ! grep -q "waveshare35b" "$BOOT_CONFIG"; then
                        echo "" >> "$BOOT_CONFIG"
                        echo "# TFT Display - Waveshare 3.5\" (B/C)" >> "$BOOT_CONFIG"
                        echo "dtoverlay=waveshare35b" >> "$BOOT_CONFIG"
                        print_step "Added Waveshare 3.5B overlay"
                    else
                        print_step "Waveshare overlay already configured"
                    fi
                    ;;
            esac
            ;;
        5)
            print_step "HDMI touchscreen - no driver configuration needed"
            ;;
        6)
            print_step "Skipping driver installation"
            ;;
        *)
            print_warning "Invalid choice, skipping driver installation"
            ;;
    esac
else
    print_warning "Boot config not found - please configure display driver manually"
fi

# ============================================================================
# Touch Input Configuration
# ============================================================================
print_header "Configuring Touch Input"

# Create udev rules for touch screen
print_step "Creating udev rules for touch input..."
cat > /etc/udev/rules.d/95-touchscreen.rules << 'EOF'
# Touch screen rules - create symlink for easy access
SUBSYSTEM=="input", ATTRS{name}=="*Touch*", SYMLINK+="input/touchscreen"
SUBSYSTEM=="input", ATTRS{name}=="*touch*", SYMLINK+="input/touchscreen"
SUBSYSTEM=="input", ATTRS{name}=="ADS7846*", SYMLINK+="input/touchscreen"
SUBSYSTEM=="input", ATTRS{name}=="*ADS7846*", SYMLINK+="input/touchscreen"
EOF

# Reload udev rules
udevadm control --reload-rules
udevadm trigger
print_step "Udev rules created and loaded"

# ============================================================================
# Configuration Directory
# ============================================================================
print_header "Creating Configuration"

CONFIG_DIR="$ACTUAL_HOME/.film_scanner"
mkdir -p "$CONFIG_DIR"
chown $ACTUAL_USER:$ACTUAL_USER "$CONFIG_DIR"

# Create touchscreen config with correct defaults
# Note: Uses fb0 (not fb1) for FBTFT with vc4-kms-v3d
# Note: touch_invert_y=true is common for most TFT screens
cat > "$CONFIG_DIR/touchscreen_config.json" << 'EOF'
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
    "auto_start_app": true,
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
EOF
chown $ACTUAL_USER:$ACTUAL_USER "$CONFIG_DIR/touchscreen_config.json"
print_step "Configuration created at $CONFIG_DIR"

# ============================================================================
# Systemd Services
# ============================================================================
print_header "Setting Up Services"

# Create systemd service for touchscreen UI
# Uses direct framebuffer rendering (no SDL/X11 required)
cat > /etc/systemd/system/film-scanner-touchscreen.service << EOF
[Unit]
Description=Film Scanner Touch Screen UI
After=multi-user.target
Wants=systemd-udev-settle.service

[Service]
Type=simple
User=$ACTUAL_USER
Group=$ACTUAL_USER
WorkingDirectory=$REPO_ROOT
Environment=PYTHONUNBUFFERED=1

# Direct framebuffer mode - no SDL environment needed
ExecStart=/usr/bin/python3 $REPO_ROOT/touchscreen_ui.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload
print_step "Systemd service created"

# ============================================================================
# Auto-start Selection
# ============================================================================
print_header "Auto-start Configuration"

echo ""
echo "Enable touchscreen UI to start automatically on boot?"
echo ""
echo "  1) Yes - Enable auto-start (recommended)"
echo "  2) No  - Start manually when needed"
echo ""
read -p "Enter choice [1/2]: " autostart_choice

case $autostart_choice in
    1)
        systemctl enable film-scanner-touchscreen.service
        print_step "Touchscreen UI will start automatically on boot"
        ;;
    *)
        print_step "Auto-start not enabled"
        print_step "Start manually with: sudo systemctl start film-scanner-touchscreen"
        ;;
esac

# ============================================================================
# Complete
# ============================================================================
print_header "Setup Complete!"

echo ""
echo "Configuration:"
echo "  Config file: $CONFIG_DIR/touchscreen_config.json"
echo "  Framebuffer: /dev/fb0 (auto-detected)"
echo "  Touch calibration: invert_y=true (default)"
echo ""
echo "Commands:"
echo "  sudo systemctl start film-scanner-touchscreen   - Start UI"
echo "  sudo systemctl stop film-scanner-touchscreen    - Stop UI"
echo "  sudo systemctl status film-scanner-touchscreen  - Check status"
echo "  journalctl -u film-scanner-touchscreen -f       - View logs"
echo ""
echo "Manual testing:"
echo "  sudo python3 $REPO_ROOT/touchscreen_ui.py"
echo "  sudo python3 $REPO_ROOT/touch_calibrate.py     - Calibration tool"
echo ""

if [[ "$screen_choice" != "5" ]] && [[ "$screen_choice" != "6" ]]; then
    print_warning "REBOOT REQUIRED for display driver to load!"
    echo ""
    read -p "Reboot now? (y/n): " reboot_choice
    if [ "$reboot_choice" = "y" ]; then
        echo "Rebooting..."
        reboot
    else
        echo ""
        echo "Remember to reboot before testing the touchscreen!"
    fi
fi
