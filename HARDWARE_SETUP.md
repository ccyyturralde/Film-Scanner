# Hardware Setup Guide

## Complete Assembly Instructions

### Required Components

#### Electronics
- **Windows/Mac/Linux PC** with USB ports
  - Python 3.9+ installed
  - See [SETUP_GUIDE.md](SETUP_GUIDE.md) for software requirements

- **Arduino Uno or Nano**
  - USB cable (Type A to B for Uno, Mini-B for Nano)
  
- **NEMA 17 Stepper Motor**
  - Model: BJ42D22-23V01 or equivalent
  - Torque: 40-50 N⋅cm minimum
  - Current: 1.0-1.5A per phase
  
- **A4988 Stepper Driver**
  - With heatsink
  - Optional: DRV8825 for higher microstepping
  
- **Power Supply**
  - 12V DC, 2A minimum
  - Barrel jack or terminal connections

#### Mechanical
- Film transport mechanism (3D printed or purchased)
- GT2 timing belt and pulleys (optional, for gearing)
- Smooth rods or linear rails
- Film reels or holders
- Light source (LED panel or flash)

### Wiring Diagram

```
POWER DISTRIBUTION
==================
12V PSU (+) ──┬── A4988 VMOT
              └── Common VCC rail

12V PSU (-) ──┬── A4988 GND
              ├── Arduino GND
              └── Common GND rail

5V (from Pi or separate) ── A4988 VDD

ARDUINO TO A4988
================
Arduino D2 ────── A4988 STEP
Arduino D3 ────── A4988 DIR
Arduino D4 ────── A4988 ENABLE
Arduino GND ───── A4988 GND

A4988 TO MOTOR
==============
A4988 1A ──── Motor Black  ┐
A4988 1B ──── Motor Blue   ├─ Coil A
                            ┘
A4988 2A ──── Motor Red    ┐
A4988 2B ──── Motor Green  ├─ Coil B
                            ┘

COMPUTER
========
USB Port 1 ────── Arduino USB
USB Port 2 ────── Camera USB (Canon DSLR)
```

### Step-by-Step Assembly

#### 1. Prepare Your Computer

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for complete software installation instructions.

**Quick summary:**
```bash
# Install Python dependencies
pip install -r requirements-desktop.txt

# Install libgphoto2 (for camera control)
# On Windows: Use MSYS2
# On Mac: brew install libgphoto2
# On Linux: sudo apt install libgphoto2-dev
```

#### 2. Assemble Motor Driver

1. **Install heatsink** on A4988 chip
2. **Insert A4988** into breadboard or shield
3. **Connect capacitor** (100μF) across VMOT and GND
4. **Set current limit**:
   ```
   Vref = I_max × 8 × R_sense
   For 1A: Vref = 1.0 × 8 × 0.05 = 0.4V
   
   Adjust potentiometer while measuring between
   pot wiper and GND to get 0.4-0.5V
   ```

#### 3. Connect Motor

1. **Identify coils** with multimeter:
   - Measure resistance between wires
   - Pairs with 2-4Ω are same coil
   - Typical: Black+Blue = Coil A, Red+Green = Coil B

2. **Connect to driver**:
   ```
   Coil A → 1A, 1B
   Coil B → 2A, 2B
   ```

3. **Test direction**:
   - If motor runs backward, swap one coil

#### 4. Arduino Setup

1. **Flash firmware**:
   ```bash
   # Connect Arduino to Pi
   cd ~/film-scanner
   
   # Using Arduino IDE (graphical)
   # OR using CLI:
   arduino-cli compile --fqbn arduino:avr:uno Arduino_Film_Scanner/
   arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:avr:uno Arduino_Film_Scanner/
   ```

2. **Test connection**:
   ```bash
   screen /dev/ttyACM0 115200
   # Type: ?
   # Should see: STATUS output
   # Type: F
   # Motor should move
   # Ctrl-A, K to exit
   ```

### Camera Setup

#### Canon DSLR Configuration

1. **Camera settings**:
   - Mode: Manual (M)
   - Image Quality: RAW (CR3/CR2)
   - Auto Power Off: Disable
   - Wi-Fi/Bluetooth: Disable (saves battery)

2. **Connection**:
   ```bash
   # Connect camera via USB
   # Turn on camera
   
   # Test detection
   gphoto2 --auto-detect
   # Should show: Canon EOS...
   
   # Test capture
   gphoto2 --capture-image
   # Image saves to SD card
   ```

#### Lighting Setup

1. **Backlight configuration**:
   - LED panel behind film
   - Diffuser material for even light
   - 5500K color temperature ideal

2. **Exposure settings**:
   - ISO 100-400 (lower = less noise)
   - Aperture f/5.6-f/8 (sharp, good depth)
   - Shutter 1/60-1/125 (bright enough)

### Mechanical Assembly

#### Film Transport Design

```
Side View:
===========
     [Supply Reel]
          |
          ▼
    [Tension Roller]
          |
    ┌─────▼─────┐
    │  Scanning │ ← Camera
    │   Window  │
    └─────┬─────┘
          |
    [Drive Roller] ← Connected to motor
          |
          ▼
     [Take-up Reel]
```

#### Critical Measurements

- **Frame window**: 36mm × 24mm (35mm film)
- **Film path**: Straight as possible at scan point
- **Motor coupling**: No slippage allowed
- **Typical gearing**: 1:1 to 3:1 reduction

### Calibration Values

#### Motor Configuration

These values are configured via the Arduino and calibrated through the desktop app:

```python
# In scanner_desktop.py (reference only - calibrated via UI):
# Steps per movement
self.fine_step = 8       # Fine adjustment
self.coarse_step = 64    # Coarse movement

# Frame advance is learned during calibration (C key)
# Step timing is set in Arduino firmware (default: 800μs)
```

#### Calculating Steps per Frame

1. **Measure film advance**:
   - 35mm frame + gap = ~38mm
   
2. **Calculate steps**:
   ```
   Steps = (38mm / roller_circumference) × steps_per_revolution × gear_ratio
   
   Example:
   - Roller diameter: 10mm (31.4mm circumference)
   - Motor: 200 steps/rev (1.8° per step)
   - Microstepping: 16× (3200 steps/rev)
   - Gear ratio: 1:1
   
   Steps = (38/31.4) × 3200 × 1 = 3873 steps
   ```

### Troubleshooting

#### Motor Issues

| Problem | Solution |
|---------|----------|
| Not moving | Check 12V power, verify ENABLE = LOW |
| Vibrating only | Increase current (adjust Vref) |
| Missing steps | Reduce speed, increase current |
| Getting hot | Reduce current, add cooling |
| Wrong direction | Swap one motor coil |

#### Arduino Issues

| Problem | Solution |
|---------|----------|
| Not detected | Check USB, try different port |
| Wrong port | `ls -l /dev/tty*` to find |
| No response | Reset Arduino, re-flash |
| Garbled text | Check baud rate (115200) |

#### Camera Issues

| Problem | Solution |
|---------|----------|
| Not detected | Check USB, camera power on |
| Capture fails | SD card full? Battery low? |
| USB disconnects | Use powered USB hub |
| Focus issues | Manual focus recommended |

### Microstepping Configuration

A4988 microstepping jumpers (MS1, MS2, MS3):

| MS1 | MS2 | MS3 | Resolution |
|-----|-----|-----|------------|
| LOW | LOW | LOW | Full step |
| HIGH | LOW | LOW | Half step |
| LOW | HIGH | LOW | 1/4 step |
| HIGH | HIGH | LOW | 1/8 step |
| HIGH | HIGH | HIGH | 1/16 step |

**Recommended**: 1/16 microstepping for smooth motion

### Performance Optimization

1. **Motor current**: Just enough to avoid missing steps
2. **Step rate**: 500-2000 steps/second typical
3. **Acceleration**: Not implemented (instant start/stop)
4. **Cooling**: Heatsinks on driver and motor if warm

### Safety Notes

⚠️ **WARNING**: 
- Always use common ground between 12V supply and Arduino
- Never disconnect motor while powered
- Use appropriate wire gauge for motor current
- Add flyback diodes for inductive loads
- Ensure proper ventilation for electronics

---

## Quick Test Procedure

After assembly, test each component:

```bash
# 1. Test Arduino
screen /dev/ttyACM0 115200
> ?
# Should see status

# 2. Test motor
> F
# Should move forward
> B  
# Should move backward

# 3. Test camera
gphoto2 --capture-image

# 4. Run scanner app
python scanner_desktop.py
```

If all tests pass, your hardware is ready for scanning! See [SETUP_GUIDE.md](SETUP_GUIDE.md) for complete usage instructions.
