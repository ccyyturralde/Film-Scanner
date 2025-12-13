#!/bin/bash
# Film Scanner - Setup Script for Raspberry Pi
# Supports Arduino Uno R3 and R4 (Minima/WiFi)

set -e

echo "========================================="
echo "35mm Film Scanner - Setup"
echo "========================================="
echo ""

# Check if running on Raspberry Pi
if [ -f /proc/device-tree/model ]; then
    echo "Detected: $(cat /proc/device-tree/model)"
else
    echo "Warning: Not running on Raspberry Pi"
    read -p "Continue anyway? (y/n): " response
    if [ "$response" != "y" ]; then
        exit 1
    fi
fi

echo ""
echo "Installing system packages..."
sudo apt update
sudo apt install -y python3-pip python3-serial git gphoto2 screen curl

echo ""
echo "Installing Python packages..."
pip3 install --break-system-packages pyserial flask flask-socketio pillow

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

echo ""
echo "Setting up serial permissions..."
if ! groups | grep -q dialout; then
    sudo usermod -a -G dialout $USER
    echo "Added user to dialout group (logout required)"
else
    echo "Already in dialout group"
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

