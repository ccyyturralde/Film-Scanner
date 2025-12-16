#!/bin/bash
# Film Scanner - Setup Script for Raspberry Pi
# Supports Arduino Uno R3 and R4 (Minima/WiFi)
# Includes optional touch screen UI setup

set -e

echo "========================================="
echo "35mm Film Scanner - Setup"
echo "========================================="
echo ""

# Check if running on Raspberry Pi
if [ -f /proc/device-tree/model ]; then
    echo "Detected: $(cat /proc/device-tree/model)"
    IS_PI=true
else
    echo "Warning: Not running on Raspberry Pi"
    read -p "Continue anyway? (y/n): " response
    if [ "$response" != "y" ]; then
        exit 1
    fi
    IS_PI=false
fi

echo ""
echo "Installing system packages..."
sudo apt update
sudo apt install -y \
    python3-pip \
    python3-serial \
    python3-pygame \
    git \
    gphoto2 \
    screen \
    curl \
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-ttf-dev \
    libfreetype6-dev

echo ""
echo "Installing Python packages..."
pip3 install --break-system-packages \
    pyserial \
    flask \
    flask-socketio \
    python-socketio \
    pillow \
    opencv-python-headless \
    numpy \
    pygame

echo ""
echo "Installing Arduino CLI..."
if ! command -v arduino-cli &> /dev/null; then
    curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh
    sudo mv bin/arduino-cli /usr/local/bin/
    arduino-cli core update-index
    arduino-cli core install arduino:avr
    arduino-cli core install arduino:renesas_uno
    echo "Arduino CLI installed with R3 and R4 support"
else
    echo "Arduino CLI already installed"
fi

echo ""
echo "Setting up directories..."
mkdir -p ~/scans
mkdir -p ~/.film_scanner

echo ""
echo "Setting up serial permissions..."
if ! groups | grep -q dialout; then
    sudo usermod -a -G dialout $USER
    echo "Added user to dialout group (logout required)"
else
    echo "Already in dialout group"
fi

# Ask about touch screen setup
echo ""
echo "========================================="
echo "Touch Screen Setup (Optional)"
echo "========================================="
echo ""
echo "Do you have a 3.5\" TFT touch screen connected?"
echo "This will set up the touch screen control interface."
echo ""
read -p "Set up touch screen? (y/n): " touchscreen_choice

if [ "$touchscreen_choice" = "y" ] || [ "$touchscreen_choice" = "Y" ]; then
    echo ""
    echo "Running touch screen setup..."
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    if [ -f "$SCRIPT_DIR/setup_touchscreen.sh" ]; then
        sudo bash "$SCRIPT_DIR/setup_touchscreen.sh"
    else
        echo "Touch screen setup script not found at: $SCRIPT_DIR/setup_touchscreen.sh"
        echo "You can run it later with: sudo ./scripts/setup_touchscreen.sh"
    fi
else
    echo "Skipping touch screen setup."
    echo "You can set it up later with: sudo ./scripts/setup_touchscreen.sh"
fi

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Flash Arduino: ./scripts/flash_arduino.sh"
echo "  2. Run scanner: python3 web_app.py"
echo ""
echo "Touch screen options:"
echo "  • Run touch screen UI: python3 touchscreen_ui.py"
echo "  • Test in windowed mode: python3 touchscreen_ui.py --windowed"
echo "  • Full touch screen setup: sudo ./scripts/setup_touchscreen.sh"
echo ""

