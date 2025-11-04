#!/bin/bash
# Film Scanner - Quick Update Script
# Pulls latest code from Git and optionally flashes Arduino

set -e

echo "========================================"
echo "Film Scanner - Update"
echo "========================================"
echo ""

# Change to script directory
cd "$(dirname "$0")"

# Check if git repo
if [ ! -d ".git" ]; then
    echo "ERROR: Not a git repository"
    echo "Run this script from the film-scanner directory"
    exit 1
fi

# Pull latest code
echo "Pulling latest code from GitHub..."
git pull

echo ""
echo "✓ Code updated successfully"
echo ""

# Ask about Arduino update
read -p "Flash Arduino with latest firmware? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Flashing Arduino..."
    
    # Find Arduino port
    ARDUINO_PORT=$(ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null | head -n1)
    
    if [ -z "$ARDUINO_PORT" ]; then
        echo "ERROR: No Arduino detected on /dev/ttyACM* or /dev/ttyUSB*"
        echo "Please check USB connection"
        exit 1
    fi
    
    echo "Using port: $ARDUINO_PORT"
    
    # Check if arduino-cli is available
    if command -v arduino-cli &> /dev/null; then
        arduino-cli compile --fqbn arduino:avr:uno arduino/film_scanner/
        arduino-cli upload -p "$ARDUINO_PORT" --fqbn arduino:avr:uno arduino/film_scanner/
        echo "✓ Arduino updated successfully"
    else
        echo "ERROR: arduino-cli not found"
        echo "Install it or use Arduino IDE to flash: arduino/film_scanner/film_scanner.ino"
        exit 1
    fi
fi

echo ""
echo "========================================"
echo "✓ Update Complete!"
echo "========================================"
echo ""
echo "To run the scanner:"
echo "  python3 scanner_app_v3\ test.py"
echo ""
