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

- **Stepper Driver** (one of the following):
  - A4988 - Budget option, with heatsink
  - **TMC2209** - Recommended, quieter and cooler operation
  - DRV8825 - Higher microstepping option

- **Power Supply**
  - 12V DC, 2A minimum

### Mechanical

- Film transport rollers with silicone rings (friction drive)
- Film holder/mask
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
A4988 1A ──── Motor Red    (Coil B)
A4988 1B ──── Motor Green  (Coil B)
A4988 2A ──── Motor Blue   (Coil A)
A4988 2B ──── Motor Black  (Coil A)

TMC2209 TO MOTOR (different pin order!)
=======================================
TMC2209 A2 ──── Motor Black  (Coil A)
TMC2209 A1 ──── Motor Blue   (Coil A)
TMC2209 B1 ──── Motor Red    (Coil B)
TMC2209 B2 ──── Motor Green  (Coil B)

⚠️  TMC2209 is NOT a direct drop-in for motor wires!
    Pin order: A2, A1, B1, B2 (vs A4988: 1B, 1A, 2A, 2B)

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

1. Install heatsink on driver chip
2. Insert driver into breadboard or shield
3. Connect capacitor (100μF) across VMOT and GND
4. Set current limit (Vref):

   **A4988:**
   ```
   Vref = I_max × 8 × R_sense
   For 1A motor: Vref ≈ 0.4V
   ```

   **TMC2209:** (much lower Vref!)
   ```
   Vref = I_rms × 2.5 × R_sense
   For 1A motor: Vref ≈ 0.3-0.4V
   ```
   
   | Driver  | Vref for 1A Motor |
   |---------|-------------------|
   | A4988   | ~0.4V (400mV)     |
   | TMC2209 | ~0.3-0.4V (300-400mV) |

### 3. Connect Motor

1. Identify coils with multimeter (pairs with 2-4Ω are same coil):
   - **Red + Green** = Coil B
   - **Black + Blue** = Coil A
   
2. Connect based on your driver (see wiring diagram above):
   - **A4988**: 1A=Red, 1B=Green, 2A=Blue, 2B=Black
   - **TMC2209**: A2=Black, A1=Blue, B1=Red, B2=Green
   
3. If motor runs backward, swap one coil pair (e.g., swap Red↔Green)

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
| Vibrating/buzzing only | Check coil wiring, increase Vref, verify common ground |
| Missing steps | Reduce speed, increase current |
| Getting hot | Reduce current (lower Vref), add cooling |
| Wrong direction | Swap one motor coil pair |
| Buzzing after driver swap | TMC2209 has different pinout - rewire motor! |

### TMC2209 Specific Issues

| Problem | Solution |
|---------|----------|
| Motor buzzes, won't move | Wrong motor pinout - TMC2209 uses A2,A1,B1,B2 order |
| Different Vref readings from different grounds | Grounds not connected - tie Arduino GND to 12V PSU GND |
| Very high Vref at minimum pot | Normal for some boards, start around 0.3-0.4V |
| Motor very hot | Vref too high (>0.5V), turn pot counter-clockwise |

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

### A4988 microstepping (MS1, MS2, MS3):

| MS1 | MS2 | MS3 | Resolution |
|-----|-----|-----|------------|
| LOW | LOW | LOW | Full step |
| HIGH | LOW | LOW | Half step |
| LOW | HIGH | LOW | 1/4 step |
| HIGH | HIGH | LOW | 1/8 step |
| HIGH | HIGH | HIGH | 1/16 step |

### TMC2209 microstepping (MS1, MS2):

| MS1 | MS2 | Resolution |
|-----|-----|------------|
| LOW | LOW | 8 microsteps (default) |
| HIGH | LOW | 16 microsteps |
| LOW | HIGH | 32 microsteps |
| HIGH | HIGH | 64 microsteps |

**Recommended**: 1/16 microstepping for smooth motion

### Driver Comparison

| Feature | A4988 | TMC2209 |
|---------|-------|---------|
| Noise | Audible whine | Near silent |
| Heat | Runs warm | Runs cool |
| Max current | 2A | 2.8A |
| Microstepping | Up to 1/16 | Up to 1/256 |
| Motor pin order | 1B, 1A, 2A, 2B | A2, A1, B1, B2 |
| Vref for 1A | ~0.4V | ~0.3-0.4V |

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
- **CRITICAL: Always connect Arduino GND to 12V supply GND (common ground)**
  - Without common ground, motor will buzz but not move
  - Vref readings will be inconsistent from different ground points
- Never disconnect motor while powered
- Use appropriate wire gauge for motor current
- Ensure proper ventilation for electronics
- When swapping drivers (A4988 ↔ TMC2209), rewire motor - pinouts differ!

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
