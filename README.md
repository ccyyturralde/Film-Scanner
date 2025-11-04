# 35mm Film Scanner

Professional-grade 35mm film scanner using Raspberry Pi, Arduino, and DSLR camera. Features precise motor control, automated frame advance, and direct capture to camera SD card.

## Features

- **Precise Motor Control**: Fine and coarse positioning with arrow keys
- **Automated Scanning**: Calibrated frame advance for entire roll
- **Professional Workflow**: Capture directly to camera SD card (.CR3 format)
- **Frame-Perfect Alignment**: Manual control with visual confirmation
- **Smart Calibration**: Learn frame spacing once, apply to entire roll
- **Resume Capability**: Continue scanning after interruption
- **Unlimited Frames**: No maximum frame count limitation
- **🆕 Smart Startup**: Auto-discover Pi IP on first launch with persistent configuration

## Hardware Requirements

### Essential Components
- Raspberry Pi 4 (2GB+ RAM recommended)
- Arduino Uno/Nano
- NEMA 17 Stepper Motor (e.g., BJ42D22-23V01)
- A4988 Stepper Driver
- Canon DSLR with USB support (or compatible camera)
- 12V Power Supply (2A minimum)
- USB cables for Arduino and camera

### Film Transport
- 3D printed or mechanical film transport mechanism
- Film holders/reels
- Smooth film path guides

## Software Requirements

- Raspberry Pi OS (Bullseye or Bookworm)
- Python 3.7+
- gphoto2 (camera control)
- Arduino IDE or arduino-cli

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/film-scanner.git
cd film-scanner/Film-Scanner
```

### 2. Install Dependencies

```bash
# Install requirements
pip3 install -r requirements.txt

# Or run the automated setup script
bash setup.sh
```

### 3. Flash Arduino

Upload the Arduino sketch using Arduino IDE or CLI:

```bash
# Using arduino-cli
arduino-cli compile --fqbn arduino:avr:uno arduino/film_scanner/
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:avr:uno arduino/film_scanner/

# Or open arduino/film_scanner/film_scanner.ino in Arduino IDE and upload
```

### 4. Run Scanner

**Option A: Using the launcher (recommended)**
```bash
# On Linux/Mac/Pi
./launch_scanner.sh

# On Windows
launch_scanner.bat
```

**Option B: Direct launch**
```bash
# Web Application (browser interface)
python3 web_app.py

# CLI Application (terminal interface)
python3 "scanner_app_v3 test.py"
```

On first launch, the **Smart Startup wizard** will guide you through configuration:
- Auto-discover your Raspberry Pi on the network
- Or manually enter the Pi's IP address
- Configuration is saved for future launches

See [SMART_STARTUP_README.md](SMART_STARTUP_README.md) for detailed setup instructions.

## Usage Guide

### Standard Workflow

1. **Start Application**
   ```bash
   python3 "scanner_app_v3 test.py"
   ```

2. **Create New Roll**
   - Press `N` and enter roll name
   - Metadata saved to `~/scans/YYYY-MM-DD/roll_name/`

3. **Load Film**
   - Insert film leader into transport
   - Ensure film is properly tensioned

4. **Position First Frame**
   - Use arrow keys for precise alignment
   - `G` toggles between small/large steps

5. **Calibrate Frame Spacing**
   - Press `C` to start calibration
   - Press `SPACE` to capture frame 1
   - Advance to frame 2 using arrows
   - Press `SPACE` to capture frame 2
   - System learns frame-to-frame distance

6. **Scan Remaining Frames**
   - Press `SPACE` for each frame
   - System captures then auto-advances
   - Make fine adjustments with arrows if needed

### Control Reference

| Key | Action | Description |
|-----|--------|-------------|
| **← →** | Fine adjust | Small movements (8/64 steps) |
| **Shift+← →** | Frame jump | Full frame forward/backward |
| **G** | Step size | Toggle small/LARGE steps |
| **SPACE** | Capture | Capture frame + auto-advance |
| **F** | Focus | Trigger autofocus |
| **C** | Calibrate | Learn frame spacing |
| **A** | Auto-advance | Toggle ON/OFF |
| **M** | Mode | Manual/Calibrated |
| **N** | New roll | Start new roll |
| **Z** | Zero | Reset position |
| **Q** | Quit | Exit application |

## Operating Modes

### Manual Mode
Complete manual control for challenging frames or initial setup.

### Calibrated Mode
Automated frame advance based on learned spacing. Still allows fine adjustments.

### Mixed Operation
- Calibrated mode with auto-advance OFF
- Use Shift+arrows for frame jumps
- Fine-tune before each capture

## Arduino Wiring

### Connections

```
Arduino → A4988 Driver
Pin D2 → STEP
Pin D3 → DIR
Pin D4 → ENABLE
GND → GND

A4988 → Motor
1A, 1B → Coil 1
2A, 2B → Coil 2

Power
12V → VMOT (A4988)
5V → VDD (A4988)
GND → Common ground
```

### Current Setting
Adjust A4988 potentiometer for ~1A motor current:
- Vref = 0.4-0.5V (measure pot to GND)

## Camera Configuration

### Supported Cameras
- Canon DSLRs with gphoto2 support
- Files saved as .CR3 to camera SD card
- USB tethering required

### Camera Settings
- Manual mode recommended
- Fixed ISO (100-400)
- Consistent exposure
- Manual focus or single-shot AF

## File Management

### Image Storage
- **Location**: Camera SD card
- **Format**: .CR3 (Canon RAW)
- **Naming**: Set by camera

### Metadata Storage
- **Location**: `~/scans/YYYY-MM-DD/roll_name/.scan_state.json`
- **Contents**: Frame count, positions, calibration data

## Configuration

Edit `scanner_app_v2.py` to adjust:

```python
# Motor steps
self.fine_step = 8       # Fine movement
self.coarse_step = 64    # Coarse movement

# Frame advance
self.default_advance = 1200  # Default spacing

# Step timing
self.step_delay = 800    # Microseconds
```

## Troubleshooting

### Arduino Not Found
```bash
# Check connection
ls -l /dev/tty*

# Test with screen
screen /dev/ttyACM0 115200
```

### Camera Not Detected
```bash
# Check camera
gphoto2 --auto-detect

# Test capture
gphoto2 --capture-image
```

### Motor Not Moving
- Check 12V power supply
- Verify common ground
- Test motor coils (2-4Ω)
- Check A4988 current setting

### Inconsistent Frame Spacing
- Check mechanical coupling
- Verify no slippage
- Recalibrate if needed

## Advanced Features

### Resume Scanning
Automatically resume interrupted rolls:
1. Start app
2. Press N → Enter same roll name
3. Choose "Resume"

### Different Film Formats
Adjust default frame spacing:
- 35mm full frame: ~1200 steps
- 35mm half frame: ~600 steps
- Custom: Calibrate for each format

### Batch Processing
```bash
# Create simple batch script
for i in {1..36}; do
    echo "Frame $i"
    python3 -c "import serial; s=serial.Serial('/dev/ttyACM0', 115200); s.write(b'N\n')"
    sleep 5
done
```

## Development

### Project Structure
```
film-scanner/
├── scanner_app_v3 test.py    # Main application
├── arduino/
│   └── film_scanner/
│       └── film_scanner.ino  # Arduino firmware
├── docs/                      # Documentation
│   ├── hardware-setup.md
│   ├── api-reference.md
│   ├── quick-reference.md
│   ├── calibration-workflow.md
│   └── github-deploy.md
├── setup.sh                   # Automated setup script
├── update.sh                  # Update and flash script
├── requirements.txt
├── .gitignore
├── LICENSE
└── README.md
```

### Testing
```bash
# Manual test with Arduino
screen /dev/ttyACM0 115200
# Commands: f, b, F, B, ?, Z

# Full documentation in docs/api-reference.md
```

### Contributing
1. Fork the repository
2. Create feature branch
3. Test thoroughly
4. Submit pull request

## Version History

### v3.0 (Current - Testing Branch)
- Strip-based scanning workflow
- Multi-strip calibration
- Per-strip frame tracking
- Enhanced state persistence
- Improved camera handling
- All v2.0 features maintained

### v2.0
- Auto-advance after capture (not before)
- Calibration captures both frames
- Fine adjustments always available
- Shift+arrows for frame jumps
- Autofocus button
- Direct SD card capture
- Camera status indicator

### v1.0
- Initial release
- Basic motor control
- Manual scanning

## License

MIT License - See [LICENSE](LICENSE) file for details

## Acknowledgments

- Built for reliability and professional results
- Inspired by commercial film scanners
- Community contributions welcome

## Documentation

Detailed documentation is available in the repository:

### Core Documentation
- **[Hardware Setup Guide](docs/hardware-setup.md)** - Complete assembly instructions, wiring diagrams, and calibration
- **[Arduino API Reference](docs/api-reference.md)** - Command documentation and serial protocol
- **[Quick Reference](docs/quick-reference.md)** - Keyboard shortcuts and workflow cheat sheet
- **[Calibration Workflow](docs/calibration-workflow.md)** - Detailed calibration process and strip scanning
- **[GitHub Deploy Guide](docs/github-deploy.md)** - Repository setup and deployment instructions

### 🆕 Smart Startup System
- **[Smart Startup README](SMART_STARTUP_README.md)** - Feature overview and quick start
- **[Startup Guide](STARTUP_GUIDE.md)** - Detailed setup and configuration instructions
- **[Implementation Summary](IMPLEMENTATION_SUMMARY.md)** - Technical details and design decisions

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review the [documentation](docs/)
3. Check closed issues on GitHub
4. Open a new issue with details

## Future Enhancements

- [ ] Web interface for remote control
- [ ] Multi-format support (120, 110 film)
- [ ] Automatic exposure detection
- [ ] Batch processing modes
- [ ] Image preview on Pi display
- [ ] Cloud backup integration

---

**Note**: This project is under active development. For production use, thoroughly test with your specific hardware configuration.
