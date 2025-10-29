#!/bin/bash
# Quick update script - pulls latest code and flashes Arduino

cd ~/film-scanner || exit

echo "Pulling latest code..."
git pull

echo "Flashing Arduino..."
ARDUINO_PORT=$(arduino-cli board list | grep -E "tty(ACM|USB)" | awk '{print $1}' | head -n1)

if [ -z "$ARDUINO_PORT" ]; then
    echo "No Arduino detected!"
    exit 1
fi

arduino-cli compile --fqbn arduino:avr:uno Arduino_Film_Scanner/Arduino_Film_Scanner.ino
arduino-cli upload -p "$ARDUINO_PORT" --fqbn arduino:avr:uno Arduino_Film_Scanner/Arduino_Film_Scanner.ino

echo "✓ Update complete!"
