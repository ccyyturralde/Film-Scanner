# WiFi Version Wiring Diagram

## Complete System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Power Distribution                       │
└─────────────────────────────────────────────────────────────────┘

12V Power Supply (2A minimum)
    │
    ├──────────┬──────────┬────────────┐
    │          │          │            │
    ▼          ▼          ▼            ▼
┌─────┐   ┌────────┐  ┌──────┐   ┌────────┐
│Motor│   │A4988   │  │Arduino│   │Common  │
│     │   │Driver  │  │R4 WiFi│   │Ground  │
│     │   │VMOT    │  │VIN    │   │Rail    │
└─────┘   └────────┘  └──────┘   └────────┘
                         6-24V      Connect:
                         Input      - 12V GND
                                    - Arduino GND
                                    - Driver GND

⚠️  CRITICAL: All grounds must be connected together!
```

## Arduino R4 WiFi Power Options

### Option 1: Direct VIN Connection (Simplest)

```
12V Power Supply
    │
    ├─── (+) ──→ Arduino VIN pin
    │
    └─── (−) ──→ Arduino GND pin

Pros:
✓ Simple - just 2 wires
✓ Works with 6-24V input
✓ No additional components

Cons:
✗ Onboard regulator may get warm
✗ Less efficient (~60%)
```

### Option 2: Buck Converter (Recommended)

```
12V Power Supply
    │
    ├─── (+) ──→ Buck Converter IN+
    │              │
    │              ▼
    │         Buck Converter
    │         (12V → 5V, 1A)
    │              │
    │              ├──→ Arduino 5V pin
    │              └──→ Arduino GND
    │
    └─── (−) ──→ Buck Converter IN− / GND

Pros:
✓ Cooler operation
✓ More efficient (~85%)
✓ Stable 5V output
✓ Less stress on Arduino regulator

Cons:
✗ Requires buck converter module ($2-5)
✗ Slightly more complex wiring

Recommended buck converters:
- LM2596 module (adjustable, common)
- MP1584EN module (compact)
- XL4015 module (high quality)
```

## Motor Driver Wiring

### A4988 Driver

```
Arduino R4 WiFi              A4988 Driver
┌─────────────┐          ┌──────────────┐
│   Pin D2    ├─────────→│ STEP         │
│   Pin D3    ├─────────→│ DIR          │
│   Pin D4    ├─────────→│ ENABLE       │
│   GND       ├─────────→│ GND          │
└─────────────┘          └──────────────┘

A4988 Power
┌──────────────┐
│ VMOT  ←──────┼─── 12V+
│ GND   ←──────┼─── 12V− (common ground)
│ VDD   ←──────┼─── 5V (from Arduino 5V pin or buck)
└──────────────┘

A4988 to Motor (NEMA 17)
┌──────────────┐          ┌──────────┐
│ 1A (Red)     ├─────────→│ Red      │
│ 1B (Green)   ├─────────→│ Green    │ Coil B
│ 2A (Blue)    ├─────────→│ Blue     │
│ 2B (Black)   ├─────────→│ Black    │ Coil A
└──────────────┘          └──────────┘
```

### TMC2209 Driver (Quieter Alternative)

```
⚠️  TMC2209 has DIFFERENT motor pinout than A4988!

Arduino R4 WiFi              TMC2209 Driver
┌─────────────┐          ┌──────────────┐
│   Pin D2    ├─────────→│ STEP         │
│   Pin D3    ├─────────→│ DIR          │
│   Pin D4    ├─────────→│ EN           │
│   GND       ├─────────→│ GND          │
└─────────────┘          └──────────────┘

TMC2209 Power
┌──────────────┐
│ VM    ←──────┼─── 12V+
│ GND   ←──────┼─── 12V− (common ground)
│ VIO   ←──────┼─── 5V (logic power)
└──────────────┘

TMC2209 to Motor (DIFFERENT order!)
┌──────────────┐          ┌──────────┐
│ A2 (Black)   ├─────────→│ Black    │ Coil A
│ A1 (Blue)    ├─────────→│ Blue     │
│ B1 (Red)     ├─────────→│ Red      │ Coil B
│ B2 (Green)   ├─────────→│ Green    │
└──────────────┘          └──────────┘

NOTE: TMC2209 pins are NOT a drop-in replacement!
      If swapping A4988↔TMC2209, you MUST rewire the motor.
```

## Complete System Wiring (Text Diagram)

```
                    ┌───────────────────────┐
                    │   12V Power Supply    │
                    │      (2A minimum)     │
                    └───┬───────────────┬───┘
                        │               │
                   ┌────┴────┐     ┌────┴────┐
                   │   12V+  │     │   12V−  │
                   └────┬────┘     └────┬────┘
                        │               │
        ┌───────────────┼───────────────┼──────────────┐
        │               │               │              │
        │               │               │              │
        ▼               ▼               ▼              ▼
   ┌────────┐     ┌─────────┐    ┌──────────┐   ┌─────────┐
   │A4988   │     │Arduino  │    │Motor     │   │Common   │
   │VMOT    │     │VIN      │    │(power    │   │GND      │
   │        │     │         │    │ line)    │   │Rail     │
   └────────┘     └─────────┘    └──────────┘   └────┬────┘
                                                      │
                  ┌───────────────────────────────────┤
                  │                                   │
                  ▼                                   ▼
           ┌─────────────┐                     ┌──────────┐
           │Arduino GND  │                     │Driver GND│
           └─────────────┘                     └──────────┘

┌─────────────────────────────────────────────────────────────┐
│  WiFi Connection (No USB cable needed!)                     │
│                                                              │
│  Raspberry Pi  ←──── WiFi Network ────→  Arduino R4 WiFi   │
│  (192.168.1.x)        (2.4GHz)           (192.168.1.100)   │
│                                                              │
│  TCP Port: 8888                                             │
└─────────────────────────────────────────────────────────────┘
```

## Pin Reference Table

### Arduino R4 WiFi Pins Used

| Pin  | Function      | Connects To         |
|------|---------------|---------------------|
| D2   | STEP signal   | Driver STEP         |
| D3   | DIR signal    | Driver DIR          |
| D4   | ENABLE signal | Driver ENABLE       |
| GND  | Ground        | Common GND rail     |
| VIN  | Power input   | 12V+ (Option 1)     |
| 5V   | Power input   | Buck 5V (Option 2)  |

### A4988 Stepper Driver Pins

| Pin    | Function       | Connects To              |
|--------|----------------|--------------------------|
| STEP   | Step pulse     | Arduino D2               |
| DIR    | Direction      | Arduino D3               |
| ENABLE | Motor enable   | Arduino D4               |
| MS1    | Microstep 1    | HIGH for 1/16 step       |
| MS2    | Microstep 2    | HIGH for 1/16 step       |
| MS3    | Microstep 3    | HIGH for 1/16 step       |
| RESET  | Reset          | Tie to SLEEP             |
| SLEEP  | Sleep          | Tie to RESET             |
| VMOT   | Motor power    | 12V+                     |
| GND    | Ground         | Common GND rail          |
| VDD    | Logic power    | 5V                       |
| 1A/2A  | Motor coils    | Motor wires              |
| 1B/2B  | Motor coils    | Motor wires              |

## Raspberry Pi Connections (Unchanged)

```
Raspberry Pi USB Ports:
    │
    ├─── USB Port 1 ──→ HDMI Capture Card
    │
    └─── USB Port 2 ──→ Canon DSLR Camera

    (Arduino no longer needs USB! 🎉)

Raspberry Pi Power:
    5V Power Supply (3A) → USB-C power input
```

## Complete Bill of Materials (WiFi Version)

### Required Components

| Component              | Specs                  | Quantity | Notes                    |
|------------------------|------------------------|----------|--------------------------|
| Arduino Uno R4 WiFi    | ESP32-S3 + RA4M1       | 1        | Required for WiFi        |
| NEMA 17 Stepper Motor  | 1.0-1.5A, 40-50 N⋅cm  | 1        | BJ42D22 or Creality 42-40|
| A4988 Stepper Driver   | With heatsink          | 1        | Or TMC2209 for quieter   |
| 12V Power Supply       | 2A minimum             | 1        | Powers motor + Arduino   |
| Buck Converter         | 12V→5V, 1A (optional)  | 1        | Recommended for cooling  |
| Jumper Wires           | Dupont M-M, M-F        | 10-15    | For connections          |
| Raspberry Pi 4         | 2GB+ RAM               | 1        | With WiFi enabled        |
| Canon DSLR             | USB/PTP support        | 1        | RAW capture              |
| HDMI Capture Card      | USB 2.0/3.0            | 1        | Live preview             |

### Optional Components

| Component              | Purpose                          |
|------------------------|----------------------------------|
| Capacitor (100μF)      | Motor power smoothing            |
| Screw terminals        | Cleaner power distribution       |
| Breadboard/PCB         | Permanent installation           |
| Heatsink (for buck)    | If buck converter gets warm      |

## Wiring Checklist

Before powering on:

- [ ] **Common ground verified** - Arduino GND, driver GND, 12V GND connected
- [ ] **VIN/5V connected** - Arduino powered from 12V supply
- [ ] **Motor wires correct** - Coils identified and properly paired
- [ ] **Driver pins connected** - D2→STEP, D3→DIR, D4→ENABLE
- [ ] **Microstepping set** - MS1/MS2/MS3 configured (1/16 recommended)
- [ ] **Vref adjusted** - Driver current limit set (~0.4V for 1A motor)
- [ ] **WiFi configured** - `wifi_config.h` has correct SSID/password
- [ ] **Static IP set** - Arduino IP matches `web_app.py` config
- [ ] **No shorts** - Visually inspect all connections
- [ ] **12V polarity correct** - Red = positive, Black = negative

## Testing Procedure

### 1. Power On Arduino Only (No Motor)

```
Connect: 12V supply → Arduino VIN/GND only
Verify:
  - LED matrix lights up
  - "W" pattern shows (connecting to WiFi)
  - IP address scrolls (WiFi connected)
  - Happy face (ready)
```

### 2. Connect Motor Driver (Motor Disconnected)

```
Connect: D2, D3, D4, GND, and driver power
Verify:
  - Driver LED lights up (if present)
  - No smoke or unusual heat
  - Arduino still responsive
```

### 3. Connect Motor

```
Connect: Motor to driver outputs
Verify:
  - Motor holds position (slight resistance when turned by hand)
  - No buzzing or vibration at idle
```

### 4. Test Motor Movement

```
From Raspberry Pi:
  telnet <arduino-ip> 8888
  F    # Forward - motor should step
  B    # Backward - motor should step
```

## Troubleshooting Common Wiring Issues

### Motor Buzzes But Doesn't Move

**Cause:** Coils not properly paired or common ground missing

**Fix:**
1. Verify coil pairs with multimeter (2-4Ω resistance)
2. Check common ground connection
3. Verify motor wire order matches driver pinout

### Arduino Resets During Motor Movement

**Cause:** Insufficient power supply or missing common ground

**Fix:**
1. Use 12V 2A supply minimum (not 1A)
2. Add 100μF capacitor across motor power
3. Verify common ground connection
4. Consider buck converter for stable Arduino power

### WiFi Won't Connect

**Cause:** Wrong credentials or 5GHz network

**Fix:**
1. Verify SSID/password in `wifi_config.h`
2. Ensure router has 2.4GHz enabled
3. Move Arduino closer to router
4. Check Serial monitor for WiFi error messages

### Motor Gets Hot

**Cause:** Driver current (Vref) too high

**Fix:**
1. Measure Vref with multimeter
2. Adjust to ~0.4V for 1A motor
3. Add heatsink to motor if needed
4. Verify motor current rating

## Safety Warnings

⚠️ **Electrical Safety**
- Never connect/disconnect motor while powered
- Always power off before wiring changes
- Use proper wire gauge (22-24 AWG for signals, 18-20 AWG for power)
- Insulate all exposed connections

⚠️ **Common Ground Critical**
- Floating grounds can damage components
- Motor buzzing without movement indicates ground issue
- Always verify continuity between all ground points

⚠️ **Power Supply**
- Use UL/CE certified power supplies
- 12V 2A minimum - 3A recommended for safety margin
- Ensure supply can handle motor current spikes

## Next Steps

After successful wiring:
1. Secure all connections with solder or screw terminals
2. Mount components in enclosure
3. Label wires for future maintenance
4. Test full range of motion
5. Run calibration workflow

Your Arduino is now wirelessly controlled! 🎉
