# 35mm Film Scanner

Professional-grade 35mm film scanner using Raspberry Pi, Arduino, and DSLR camera. Features precise motor control, automated frame advance, and direct capture to camera SD card.

## Features

- **Precise Motor Control**: Fine and coarse positioning via web interface
- **Automated Scanning**: Calibrated frame advance for entire rolls
- **Professional Workflow**: Capture directly to camera SD card (.CR3/.CR2)
- **Smart Calibration**: Learn frame spacing once, apply to entire roll
- **Resume Capability**: Continue scanning after interruption
- **Live Preview**: On-demand camera preview with negative inversion
- **Web Interface**: Mobile-friendly browser control
- **Arduino R3/R4 Support**: Compatible with Uno R3 and R4 (Minima/WiFi)

## Hardware Requirements

| Component | Details |
|-----------|---------|
| Raspberry Pi | Pi 4 (2GB+ RAM recommended) |
| Arduino | Uno R3, R4 Minima, or R4 WiFi |
| Motor | NEMA 17 stepper (e.g., Creality 42-40) |
| Driver | A4988 stepper driver |
| Camera | Canon DSLR with USB/PTP support |
| Power | 12V 2A for motor driver |

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/Film-Scanner.git
cd Film-Scanner
```

### 2. Install Dependencies

```bash
# On Raspberry Pi
bash scripts/setup.sh

# Or manually
pip3 install -r requirements.txt
sudo apt install gphoto2
```

### 3. Flash Arduino

```bash
# Using the flash utility
bash scripts/flash_arduino.sh

# Or manually with arduino-cli:

# Arduino Uno R3:
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:avr:uno arduino/film_scanner/

# Arduino Uno R4 Minima:
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:renesas_uno:unor4minima arduino/film_scanner/

# Arduino Uno R4 WiFi:
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:renesas_uno:unor4wifi arduino/film_scanner/
```

### 4. Run Scanner

```bash
python3 web_app.py
```

Access the interface at `http://<raspberry-pi-ip>:5000`

## Wiring

```
Arduino (R3 or R4) → A4988 Driver
Pin D2 → STEP
Pin D3 → DIR
Pin D4 → ENABLE
GND → GND (common with 12V supply)

Power
12V → VMOT (A4988)
5V → VDD (A4988)
```

## Project Structure

```
Film-Scanner/
├── arduino/              # Arduino firmware
│   └── film_scanner/
│       └── film_scanner.ino
├── docs/                 # Documentation
│   ├── api-reference.md
│   ├── calibration-workflow.md
│   ├── hardware-setup.md
│   └── quick-reference.md
├── pcb/                  # PCB design files (KiCad)
├── scripts/              # Setup utilities
│   ├── setup.sh
│   └── flash_arduino.sh
├── static/               # Web assets
│   ├── css/style.css
│   └── js/app.js
├── templates/            # HTML templates
│   └── index.html
├── web_app.py            # Main application
├── config_manager.py     # Configuration handling
├── requirements.txt      # Python dependencies
└── README.md
```

## Usage

### Workflow

1. **Create Roll**: Enter a name for your film roll
2. **Calibrate**: Position and capture first two frames to learn spacing
3. **Scan**: Capture frames with automatic advance
4. **New Strip**: Load next strip and continue

### Controls

| Action | Description |
|--------|-------------|
| ← → | Fine position adjustment |
| Shift + ← → | Coarse position adjustment |
| SPACE | Capture frame |
| P | Get camera preview |

## Troubleshooting

### Arduino Not Found

```bash
# Check ports
ls /dev/tty*

# Or use arduino-cli
arduino-cli board list
```

### Camera Not Detected

```bash
# Test camera
gphoto2 --auto-detect

# Kill conflicting processes
killall gphoto2 gvfs-gphoto2-volume-monitor
```

### Motor Not Moving

- Check 12V power supply
- Verify common ground between Arduino and driver
- Check A4988 current setting (Vref ~0.4V)

## Documentation

- [Hardware Setup](docs/hardware-setup.md) - Wiring and assembly
- [API Reference](docs/api-reference.md) - Arduino command protocol
- [Calibration Workflow](docs/calibration-workflow.md) - Scanning process
- [Quick Reference](docs/quick-reference.md) - Command cheat sheet

## License

MIT License - See [LICENSE](LICENSE)
