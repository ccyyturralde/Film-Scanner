#!/bin/bash
# Film Scanner Deployment Script
# Run this on your Raspberry Pi to update everything

set -e  # Exit on error

REPO_URL="https://github.com/ccyyturralde/Film-Scanner.git"
INSTALL_DIR="$HOME/film-scanner"
ARDUINO_PORT="/dev/ttyACM0"  # Change if needed

echo "=================================="
echo "Film Scanner Deployment"
echo "=================================="

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "Installing git..."
    sudo apt update
    sudo apt install -y git
fi

# Clone or update repository
if [ -d "$INSTALL_DIR" ]; then
    echo "Updating repository..."
    cd "$INSTALL_DIR"
    git pull
else
    echo "Cloning repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install --break-system-packages -r requirements.txt 2>/dev/null || true

# Check if arduino-cli is installed
if ! command -v arduino-cli &> /dev/null; then
    echo ""
    echo "Arduino CLI not found. Install? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo "Installing Arduino CLI..."
        curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh
        export PATH=$PATH:$HOME/bin
        echo 'export PATH=$PATH:$HOME/bin' >> ~/.bashrc
        
        # Initialize and install board support
        arduino-cli core update-index
        arduino-cli core install arduino:avr
    else
        echo "Skipping Arduino flash. You'll need to upload manually."
        exit 0
    fi
fi

# Find Arduino port
echo ""
echo "Detecting Arduino..."
PORTS=$(arduino-cli board list | grep -E "tty(ACM|USB)" | awk '{print $1}')

if [ -z "$PORTS" ]; then
    echo "No Arduino detected. Connect it and try again."
    exit 1
fi

# If multiple ports, let user choose
PORT_COUNT=$(echo "$PORTS" | wc -l)
if [ "$PORT_COUNT" -gt 1 ]; then
    echo "Multiple Arduinos detected:"
    echo "$PORTS"
    echo "Enter port to use (e.g., /dev/ttyACM0):"
    read -r ARDUINO_PORT
else
    ARDUINO_PORT=$PORTS
    echo "Found Arduino on: $ARDUINO_PORT"
fi

# Flash Arduino
echo ""
echo "Flashing Arduino..."
arduino-cli compile --fqbn arduino:avr:uno Arduino_Film_Scanner/Arduino_Film_Scanner.ino
arduino-cli upload -p "$ARDUINO_PORT" --fqbn arduino:avr:uno Arduino_Film_Scanner/Arduino_Film_Scanner.ino

echo ""
echo "=================================="
echo "✓ Deployment Complete!"
echo "=================================="
echo ""
echo "To run the scanner:"
echo "  cd $INSTALL_DIR"
echo "  python3 scanner_app.py"
echo ""
