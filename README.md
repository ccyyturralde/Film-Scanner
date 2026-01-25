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
| Arduino | Uno R3, R4 Minima, or R4 WiFi (via USB) |
| Motor | NEMA 17 stepper (standard or pancake) |
| Driver | A4988 stepper driver |
| Camera | Canon DSLR with USB/PTP support |
| Power | 12V 2A for motor driver |

## Quick Start

### Raspberry Pi (fresh install)

```bash
git clone https://github.com/YOUR_USERNAME/Film-Scanner.git
cd Film-Scanner
sudo bash scripts/setup_pi.sh   # installs deps, service, helper commands
start-scanner                    # launches the web app (service already enabled)
```

- Access at `http://<raspberry-pi-ip>:5000`
- Service starts automatically on boot: `film-scanner.service`
- Stop or restart: `stop-scanner` / `sudo systemctl restart film-scanner.service`

### Manual install (existing setup)

```bash
git clone https://github.com/YOUR_USERNAME/Film-Scanner.git
cd Film-Scanner
bash scripts/setup.sh
```

### Flash Arduino

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

Stepper coils (must be paired or motor will only vibrate)
- Coil A (A1/A2): Black & Blue
- Coil B (B1/B2): Red & Green
Swapping A1↔A2 or B1↔B2 only flips direction; crossing coils will not work.

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
│   ├── setup.sh          # Manual dependency install
│   ├── setup_pi.sh       # Automated Pi install + service
│   ├── flash_arduino.sh
│   └── health_check.sh   # Wrapper for health_check.py
├── static/               # Web assets
│   ├── css/style.css
│   └── js/app.js
├── templates/            # HTML templates
│   └── index.html
├── web_app.py            # Main application
├── config_manager.py     # Configuration handling
├── health_check.py       # Auto-repair utility
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

### Quick Fix: Health Check

If something isn't working, run the automatic health check and repair utility:

```bash
python3 health_check.py
```

This will:
- Compare your installation against GitHub
- Pull the latest code
- Fix missing/outdated dependencies
- Remove deprecated files
- Restart services

Run with `--check` to see issues without fixing them.

## Documentation

- [Hardware Setup](docs/hardware-setup.md) - Wiring and assembly
- [API Reference](docs/api-reference.md) - Arduino command protocol
- [Calibration Workflow](docs/calibration-workflow.md) - Scanning process
- [Quick Reference](docs/quick-reference.md) - Command cheat sheet

## Future Enhancements

### ML-Based Frame Gap Detection

The current auto-alignment uses computer vision (column brightness, vertical continuity, uniformity analysis) to detect frame gaps. A future enhancement would use machine learning for more robust detection:

**Approach:**
1. Build a sample image library with labeled examples:
   - "aligned" (frame fully visible, no gap)
   - "gap_left" (gap visible on left side)
   - "gap_right" (gap visible on right side)
2. Extract features: `column_uniformity`, `vertical_continuity`, `col_mean`, `col_std`
3. Train a simple classifier (SVM or Random Forest) using scikit-learn
4. Deploy the trained model for real-time inference on the Pi

**Requirements:**
- ~50-100 labeled sample images
- scikit-learn for training
- Model export via joblib

**Why ML?** The key insight is that frame gaps have consistent vertical uniformity (same brightness top-to-bottom) regardless of absolute brightness. An ML model can learn this pattern more robustly than hand-tuned thresholds.

## License

MIT License - See [LICENSE](LICENSE)
