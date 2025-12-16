#!/bin/bash
# Film Scanner - Touch Screen Setup Script
# Sets up a 3.5" TFT touch screen for the control interface
#
# Supports common 3.5" TFT screens:
# - Waveshare 3.5" LCD (A/B/C)
# - Raspberry Pi compatible 3.5" TFT
# - Elegoo 3.5" TFT
# - Generic ILI9486/ILI9341 based screens

set -e

echo "========================================="
echo "Film Scanner Touch Screen Setup"
echo "========================================="
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "Warning: This script is designed for Raspberry Pi"
    read -p "Continue anyway? (y/n): " response
    if [ "$response" != "y" ]; then
        exit 1
    fi
fi

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER=${SUDO_USER:-$USER}
ACTUAL_HOME=$(eval echo ~$ACTUAL_USER)

echo ""
echo "Installing dependencies..."
echo "-----------------------------------------"

# Update package list
apt update

# Install required system packages (works on Pi OS Lite without desktop)
apt install -y \
    python3-pygame \
    python3-pip \
    python3-numpy \
    python3-pil \
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-ttf-dev \
    libsdl2-mixer-dev \
    libfreetype6-dev \
    libportmidi-dev \
    libjpeg-dev \
    libpng-dev \
    fonts-dejavu \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    libts-bin \
    tslib \
    evtest

# Install X11 packages only if user wants windowed mode testing (optional)
echo ""
read -p "Install X11 packages for windowed mode testing? (y/n, default: n): " install_x11
if [ "$install_x11" = "y" ] || [ "$install_x11" = "Y" ]; then
    apt install -y xserver-xorg xinit x11-xserver-utils
    echo "✓ X11 packages installed"
else
    echo "✓ Skipping X11 (not needed for framebuffer/TFT display)"
fi

# Install Python packages for the user
echo ""
echo "Installing Python packages..."
sudo -u $ACTUAL_USER pip3 install --break-system-packages --user \
    pygame>=2.5.0 \
    numpy>=1.24.0 \
    pillow>=10.0.0

echo ""
echo "Touch screen driver selection"
echo "-----------------------------------------"
echo ""
echo "Select your touch screen type:"
echo ""
echo "1. Waveshare 3.5\" LCD (A) - SPI"
echo "2. Waveshare 3.5\" LCD (B/C) - SPI"
echo "3. Generic ILI9486 - SPI"
echo "4. Generic ILI9341 - SPI"
echo "5. HDMI touch screen (no driver needed)"
echo "6. Skip driver installation (manual setup)"
echo ""

read -p "Enter your choice (1-6): " screen_choice

case $screen_choice in
    1|2|3|4)
        echo ""
        echo "Installing LCD drivers..."
        
        # Enable SPI
        if ! grep -q "^dtparam=spi=on" /boot/config.txt; then
            echo "dtparam=spi=on" >> /boot/config.txt
        fi
        
        # Add framebuffer driver overlay
        if [ "$screen_choice" = "1" ] || [ "$screen_choice" = "2" ]; then
            # Waveshare LCD
            if ! grep -q "waveshare35a" /boot/config.txt; then
                cat >> /boot/config.txt << 'EOF'

# Waveshare 3.5" LCD
dtoverlay=waveshare35a
dtoverlay=ads7846,cs=1,penirq=25,penirq_pull=2,speed=50000,keep_vref_on=0,swapxy=0,pmax=255,xohms=150,xmin=200,xmax=3900,ymin=200,ymax=3900
EOF
            fi
        else
            # Generic ILI9486/ILI9341
            if ! grep -q "ili9486" /boot/config.txt && ! grep -q "ili9341" /boot/config.txt; then
                if [ "$screen_choice" = "3" ]; then
                    echo "dtoverlay=piscreen,speed=16000000,rotate=270" >> /boot/config.txt
                else
                    echo "dtoverlay=piscreen2r,speed=16000000,rotate=270" >> /boot/config.txt
                fi
            fi
        fi
        
        # Configure fbturbo
        echo "Configuring framebuffer..."
        if [ ! -f /usr/share/X11/xorg.conf.d/99-fbturbo.conf ]; then
            cat > /usr/share/X11/xorg.conf.d/99-fbturbo.conf << 'EOF'
Section "Device"
    Identifier "FBDEV"
    Driver "fbturbo"
    Option "fbdev" "/dev/fb1"
    Option "SwapbuffersWait" "true"
EndSection
EOF
        fi
        
        echo "✓ LCD driver configured"
        ;;
        
    5)
        echo "HDMI touch screen selected - no driver installation needed"
        ;;
        
    6)
        echo "Skipping driver installation"
        ;;
        
    *)
        echo "Invalid choice, skipping driver installation"
        ;;
esac

echo ""
echo "Configuring touch input..."
echo "-----------------------------------------"

# Create udev rules for touch screen
cat > /etc/udev/rules.d/95-touchscreen.rules << 'EOF'
# Touch screen rules
SUBSYSTEM=="input", ATTRS{name}=="*Touch*", SYMLINK+="input/touchscreen"
SUBSYSTEM=="input", ATTRS{name}=="*touch*", SYMLINK+="input/touchscreen"
SUBSYSTEM=="input", ATTRS{name}=="ADS7846*", SYMLINK+="input/touchscreen"
EOF

# Reload udev rules
udevadm control --reload-rules
udevadm trigger

echo "✓ Touch input configured"

echo ""
echo "Creating configuration directory..."
echo "-----------------------------------------"

# Create config directory
CONFIG_DIR="$ACTUAL_HOME/.film_scanner"
mkdir -p "$CONFIG_DIR"
chown $ACTUAL_USER:$ACTUAL_USER "$CONFIG_DIR"

# Create default touchscreen config (matches web UI dark theme)
cat > "$CONFIG_DIR/touchscreen_config.json" << 'EOF'
{
  "config_version": 1,
  "display": {
    "width": 480,
    "height": 320,
    "framebuffer": "/dev/fb1",
    "touch_device": "/dev/input/touchscreen",
    "rotation": 0,
    "touch_swap_xy": false,
    "touch_invert_x": false,
    "touch_invert_y": false,
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

echo "✓ Configuration created at $CONFIG_DIR"

echo ""
echo "Setting up auto-start services..."
echo "-----------------------------------------"

# Determine script directory
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Create systemd service for touch screen UI
# Configured for Pi OS Lite (framebuffer mode, no X11 required)
cat > /etc/systemd/system/film-scanner-touchscreen.service << EOF
[Unit]
Description=Film Scanner Touch Screen UI
After=multi-user.target
Wants=systemd-udev-settle.service

[Service]
Type=simple
User=$ACTUAL_USER
Group=$ACTUAL_USER

# Framebuffer and SDL configuration for Pi OS Lite
Environment=SDL_FBDEV=/dev/fb1
Environment=SDL_VIDEODRIVER=fbcon
Environment=SDL_MOUSEDRV=TSLIB
Environment=SDL_MOUSEDEV=/dev/input/touchscreen
Environment=TSLIB_FBDEVICE=/dev/fb1
Environment=TSLIB_TSDEVICE=/dev/input/touchscreen
Environment=TSLIB_CALIBFILE=/etc/pointercal
Environment=TSLIB_CONFFILE=/etc/ts.conf
Environment=TSLIB_PLUGINDIR=/usr/lib/ts
Environment=PYTHONUNBUFFERED=1

WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/python3 $SCRIPT_DIR/touchscreen_ui.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Create systemd service for web app (managed by touch screen UI, but also standalone)
cat > /etc/systemd/system/film-scanner-web.service << EOF
[Unit]
Description=Film Scanner Web Application
After=network.target

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/python3 $SCRIPT_DIR/web_app.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

echo "✓ Systemd services created"

echo ""
echo "Do you want to enable auto-start on boot?"
echo ""
echo "1. Enable touch screen UI auto-start (recommended)"
echo "2. Enable web app auto-start only (no touch screen)"
echo "3. Don't enable auto-start"
echo ""

read -p "Enter your choice (1-3): " autostart_choice

case $autostart_choice in
    1)
        systemctl enable film-scanner-touchscreen.service
        echo "✓ Touch screen UI will start automatically on boot"
        ;;
    2)
        systemctl enable film-scanner-web.service
        echo "✓ Web app will start automatically on boot"
        ;;
    3)
        echo "Auto-start not enabled"
        ;;
esac

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo ""
echo "  1. Reboot to apply display driver changes:"
echo "     sudo reboot"
echo ""
echo "  2. After reboot, the touch screen UI should start automatically"
echo "     (if auto-start was enabled)"
echo ""
echo "  3. To manually start the touch screen UI:"
echo "     python3 $SCRIPT_DIR/touchscreen_ui.py"
echo ""
echo "  4. To test in windowed mode (on desktop):"
echo "     python3 $SCRIPT_DIR/touchscreen_ui.py --windowed"
echo ""
echo "Service commands:"
echo "  sudo systemctl start film-scanner-touchscreen"
echo "  sudo systemctl stop film-scanner-touchscreen"
echo "  sudo systemctl status film-scanner-touchscreen"
echo ""
echo "Configuration file:"
echo "  $CONFIG_DIR/touchscreen_config.json"
echo ""
echo "========================================="
echo ""

read -p "Reboot now? (y/n): " reboot_choice
if [ "$reboot_choice" = "y" ]; then
    echo "Rebooting..."
    reboot
fi
