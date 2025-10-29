# 35mm Film Scanner

Open source film scanner for digitizing 35mm film using a Raspberry Pi, Arduino, stepper motor, and DSLR camera.

## Features

- **Manual Mode**: Direct control with arrow keys for precise positioning
- **Smart Mode**: Automatic frame detection and alignment
- **Position Tracking**: Always knows where the motor is
- **State Persistence**: Resume scanning if interrupted
- **RAW Capture**: Supports Canon .CR3 and other formats via gphoto2

## Hardware Requirements

- Raspberry Pi 4 (4GB recommended)
- Arduino Uno or Nano
- NEMA 17 Stepper Motor (BJ42D22-23V01 or similar)
- A4988 Stepper Driver
- Canon DSLR with USB tethering support
- 12V Power Supply
- 3D printed film holder (STL files coming soon)

## Software Requirements

- Raspberry Pi OS (Bullseye or later)
- Python 3.7+
- gphoto2
- Arduino CLI (auto-installed by deploy script)

## Quick Start

### One-Command Deploy

On your Raspberry Pi, run:

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/film-scanner/main/deploy.sh | bash
```

This will:
1. Clone the repository
2. Install dependencies
3. Flash the Arduino
4. Set up everything

### Manual Installation

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/film-scanner.git
cd film-scanner

# Install dependencies
sudo apt install -y python3-opencv gphoto2
pip3 install --break-system-packages -r requirements.txt

# Flash Arduino (if arduino-cli installed)
arduino-cli compile --fqbn arduino:avr:uno Arduino_Film_Scanner/Arduino_Film_Scanner.ino
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:avr:uno Arduino_Film_Scanner/Arduino_Film_Scanner.ino

# Or use Arduino IDE to upload Arduino_Film_Scanner/Arduino_Film_Scanner.ino
```

## Usage

```bash
cd ~/film-scanner
python3 scanner_app.py
```

### Controls

| Key | Action |
|-----|--------|
| `N` | New roll |
| `←` `→` | Jog film backward/forward |
| `G` | Toggle small/large step size |
| `SPACE` | Capture frame |
| `M` | Toggle Manual/Smart mode |
| `A` | Auto-align (Smart mode only) |
| `P` | Preview only |
| `Z` | Zero position counter |
| `Q` | Quit |

### Workflow - Manual Mode (Recommended)

1. Press `N` to create new roll
2. Enter roll name
3. Choose option 1 (Manual mode)
4. Use arrow keys to position first frame
5. Press `G` to toggle between small/large steps
6. Press `SPACE` to capture
7. Move to next frame and repeat

### Workflow - Smart Mode

1. Press `N` to create new roll
2. Enter roll name
3. Choose option 2 (Smart mode)
4. Position roughly near first frame
5. Press `A` to auto-align
6. Press `SPACE` to capture (auto-aligns then shoots)

## Updating

To pull the latest code and flash Arduino:

```bash
cd ~/film-scanner
./update.sh
```

Or manually:
```bash
git pull
# Then flash Arduino with Arduino IDE or arduino-cli
```

## Hardware Setup

### Arduino Connections

```
Arduino -> A4988 Driver
D2      -> STEP
D3      -> DIR
D4      -> ENABLE
GND     -> GND

A4988 Driver -> Motor
1B, 1A, 2A, 2B -> Motor coils (see motor datasheet)

Power:
12V -> A4988 VMOT
12V GND -> A4988 GND (connect to Arduino GND too!)
5V -> A4988 VDD
```

### Motor Wiring

For NEMA 17 BJ42D22-23V01:
- Coil A: Black + Blue (2-4 ohms)
- Coil B: Red + Green (2-4 ohms)

Document your working configuration in the Arduino sketch.

### Current Setting

Adjust A4988 potentiometer:
- Vref = 0.45-0.50V (measure pot to GND)
- This gives ~1.1-1.25A motor current

## File Structure

```
film-scanner/
├── scanner_app.py              # Main application
├── optimized_edge_detect.py    # Gap detection
├── Arduino_Film_Scanner/
│   └── Arduino_Film_Scanner.ino
├── deploy.sh                   # One-command deploy
├── update.sh                   # Quick update script
├── requirements.txt            # Python dependencies
└── README.md
```

## Output Files

Scanned frames are saved to:
```
~/scans/YYYY-MM-DD/roll_name/
├── .scan_state.json       # Resume state
├── 20241027-120000.cr3
├── 20241027-120030.cr3
└── ...
```

## Troubleshooting

### Arduino Not Found
- Check USB cable
- Verify sketch uploaded: `ls -l /dev/tty*`
- Try different USB port

### Camera Not Detected
- Check USB cable
- Camera powered on
- Test: `gphoto2 --auto-detect`

### Smart Align Not Working
- Ensure OpenCV installed: `python3 -c "import cv2"`
- Check lighting is even
- Try manual mode instead

### Position Tracking Off
- Press `Z` to zero position
- Verify step sizes in Arduino match Python
- Check for motor slippage

## Future Enhancements

- [ ] IR sprocket hole sensor for precise counting
- [ ] Rotation/skew detection
- [ ] Batch processing mode
- [ ] Web interface
- [ ] Support for different film formats

## Contributing

Contributions welcome! Please open an issue or pull request.

## License

MIT License - See LICENSE file

## Credits

Built for scanning 35mm film with precision and reliability.

## Support

For issues or questions, open a GitHub issue or check the documentation in `/docs`.
