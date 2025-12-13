# Hardware Setup Guide

## Required Components

### Electronics

- **Raspberry Pi 4** (2GB minimum, 4GB recommended)
  - MicroSD card (16GB+)
  - Power supply (5V 3A)

- **Arduino Uno** (any of the following):
  - Arduino Uno R3 (ATmega328P) - USB Type A to B cable
  - Arduino Uno R4 Minima (Renesas RA4M1) - USB Type A to C cable
  - Arduino Uno R4 WiFi (Renesas RA4M1 + ESP32-S3) - USB Type A to C cable

- **NEMA 17 Stepper Motor**
  - Model: BJ42D22-23V01 or equivalent
  - Torque: 40-50 N⋅cm minimum
  - Current: 1.0-1.5A per phase

- **A4988 Stepper Driver**
  - With heatsink
  - Optional: DRV8825 for higher microstepping

- **Power Supply**
  - 12V DC, 2A minimum

### Mechanical

- Film transport mechanism
- Film holders/reels
- Light source (LED panel)

## Wiring Diagram

```
POWER DISTRIBUTION
==================
12V PSU (+) ──┬── A4988 VMOT
              └── Common VCC rail

12V PSU (-) ──┬── A4988 GND
              ├── Arduino GND
              └── Common GND rail

5V (from Pi or separate) ── A4988 VDD

ARDUINO TO A4988 (Same for R3 and R4)
=====================================
Arduino D2 ────── A4988 STEP
Arduino D3 ────── A4988 DIR
Arduino D4 ────── A4988 ENABLE
Arduino GND ───── A4988 GND

A4988 TO MOTOR
==============
A4988 1A ──── Motor Red    (Coil A)
A4988 1B ──── Motor Green  (Coil A)
A4988 2A ──── Motor Blue   (Coil B)
A4988 2B ──── Motor Black  (Coil B)

RASPBERRY PI
============
USB Port 1 ────── Arduino USB
USB Port 2 ────── Camera USB
```

## Assembly Steps

### 1. Prepare the Raspberry Pi

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required software
sudo apt install -y git python3-pip gphoto2 screen
pip3 install --break-system-packages pyserial flask flask-socketio pillow
```

### 2. Assemble Motor Driver

1. Install heatsink on A4988 chip
2. Insert A4988 into breadboard or shield
3. Connect capacitor (100μF) across VMOT and GND
4. Set current limit:
   ```
   Vref = I_max × 8 × R_sense
   For 1A: Vref = 1.0 × 8 × 0.05 = 0.4V
   ```

### 3. Connect Motor

1. Identify coils with multimeter (pairs with 2-4Ω are same coil)
2. Connect: Coil A → 1A/1B, Coil B → 2A/2B
3. If motor runs backward, swap one coil pair

### 4. Flash Arduino

```bash
# Install Arduino cores
arduino-cli core install arduino:avr          # For R3
arduino-cli core install arduino:renesas_uno  # For R4

# Flash firmware (choose your board):

# Arduino Uno R3:
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:avr:uno arduino/film_scanner/

# Arduino Uno R4 Minima:
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:renesas_uno:unor4minima arduino/film_scanner/

# Arduino Uno R4 WiFi:
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:renesas_uno:unor4wifi arduino/film_scanner/
```

### 5. Test Connection

```bash
screen /dev/ttyACM0 115200
# Type: ?
# Should see: STATUS output
# Type: F
# Motor should move
# Ctrl-A, K to exit
```

## Camera Setup

### Canon DSLR Configuration

1. Camera settings:
   - Mode: Manual (M)
   - Image Quality: RAW (CR3/CR2)
   - Auto Power Off: Disable
   - USB Mode: PTP

2. Test connection:
   ```bash
   gphoto2 --auto-detect
   gphoto2 --capture-image
   ```

## Troubleshooting

### Motor Issues

| Problem | Solution |
|---------|----------|
| Not moving | Check 12V power, verify ENABLE = LOW |
| Vibrating only | Increase current (adjust Vref) |
| Missing steps | Reduce speed, increase current |
| Getting hot | Reduce current, add cooling |
| Wrong direction | Swap one motor coil pair |

### Arduino Issues

| Problem | Solution |
|---------|----------|
| Not detected | Check USB cable, try different port |
| Wrong port | Run `arduino-cli board list` |
| No response | Reset Arduino, re-flash firmware |
| Garbled text | Check baud rate (115200) |
| R4 not recognized | Install core: `arduino-cli core install arduino:renesas_uno` |

### Camera Issues

| Problem | Solution |
|---------|----------|
| Not detected | Check USB, camera power, PTP mode |
| Capture fails | SD card full? Battery low? |
| USB disconnects | Use powered USB hub |

## Microstepping Configuration

A4988 microstepping jumpers (MS1, MS2, MS3):

| MS1 | MS2 | MS3 | Resolution |
|-----|-----|-----|------------|
| LOW | LOW | LOW | Full step |
| HIGH | LOW | LOW | Half step |
| LOW | HIGH | LOW | 1/4 step |
| HIGH | HIGH | LOW | 1/8 step |
| HIGH | HIGH | HIGH | 1/16 step |

**Recommended**: 1/16 microstepping for smooth motion

## Motor Configuration

Default values in `web_app.py`:

```python
self.fine_step = 8        # Fine adjustment
self.coarse_step = 192    # Coarse movement
self.default_advance = 1200  # Steps per frame (35mm)
self.step_delay = 800     # Microseconds between steps
```

## Safety Notes

⚠️ **WARNING**: 
- Always use common ground between 12V supply and Arduino
- Never disconnect motor while powered
- Use appropriate wire gauge for motor current
- Ensure proper ventilation for electronics

## Quick Test

```bash
# 1. Test Arduino
screen /dev/ttyACM0 115200
> ?   # Status
> F   # Move forward
> B   # Move backward

# 2. Test camera
gphoto2 --capture-image

# 3. Run scanner
python3 web_app.py
```
