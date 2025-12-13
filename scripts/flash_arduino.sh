#!/bin/bash
# Flash Arduino with Film Scanner firmware
# Supports Arduino Uno R3, R4 Minima, and R4 WiFi

set -e

echo "========================================="
echo "Arduino Film Scanner - Flash Utility"
echo "========================================="
echo ""

# Find sketch directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKETCH_DIR="$SCRIPT_DIR/../arduino/film_scanner"

if [ ! -f "$SKETCH_DIR/film_scanner.ino" ]; then
    echo "Error: Could not find film_scanner.ino"
    exit 1
fi

echo "Sketch: $SKETCH_DIR"
echo ""

# Detect board
echo "Detecting Arduino..."
arduino-cli board list

# Find port
PORT=$(arduino-cli board list | grep -E "ttyACM|ttyUSB|COM" | head -1 | awk '{print $1}')

if [ -z "$PORT" ]; then
    echo ""
    echo "No Arduino detected. Please connect your board."
    exit 1
fi

echo ""
echo "Found Arduino on: $PORT"
echo ""

# Select board type
echo "Select your board:"
echo "  1) Arduino Uno R3"
echo "  2) Arduino Uno R4 Minima"
echo "  3) Arduino Uno R4 WiFi"
echo ""
read -p "Choice [1-3]: " choice

case $choice in
    1) FQBN="arduino:avr:uno"; BOARD="Arduino Uno R3";;
    2) FQBN="arduino:renesas_uno:unor4minima"; BOARD="Arduino Uno R4 Minima";;
    3) FQBN="arduino:renesas_uno:unor4wifi"; BOARD="Arduino Uno R4 WiFi";;
    *) echo "Invalid choice"; exit 1;;
esac

echo ""
echo "Compiling for $BOARD..."
arduino-cli compile --fqbn "$FQBN" "$SKETCH_DIR"

echo ""
echo "Uploading to $PORT..."
arduino-cli upload -p "$PORT" --fqbn "$FQBN" "$SKETCH_DIR"

echo ""
echo "========================================="
echo "Firmware installed on $BOARD"
echo "========================================="

