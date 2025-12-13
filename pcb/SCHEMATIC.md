# Film Scanner Motor Controller - Schematic Description

## Block Diagram

```
                                    ┌─────────────────────────────────────────┐
                                    │         FILM SCANNER CONTROLLER         │
                                    │                                         │
    ┌─────────┐     ┌─────────┐     │    ┌─────────┐                         │
    │ USB-C   │────▶│ CH224K  │─────┼───▶│ 12V BUS │◀────────────┐           │
    │ Charger │     │ PD Chip │     │    └────┬────┘             │           │
    └─────────┘     └─────────┘     │         │              ┌───┴───┐       │
                        │           │         │              │ DC IN │       │
                        ▼           │         │              │ 12V   │       │
                   ┌────────┐       │         │              └───────┘       │
                   │ LED3   │       │         │                              │
                   │ PD OK  │       │         ▼                              │
                   └────────┘       │    ┌─────────┐     ┌────────┐          │
                                    │    │ MP2359  │────▶│ 5V BUS │          │
                                    │    │ 12V→5V  │     └───┬────┘          │
                                    │    └─────────┘         │               │
                                    │         │              ▼               │
                                    │         │         ┌────────┐           │
                                    │         │         │ LED2   │           │
                                    │         │         │ 5V OK  │           │
                                    │         │         └────────┘           │
                                    │         ▼                              │
                                    │    ┌─────────┐                         │
                                    │    │ LED1    │                         │
                                    │    │ 12V OK  │                         │
                                    │    └─────────┘                         │
                                    │                                         │
                                    │    ┌─────────────────────────────────┐ │
                                    │    │        A4988 SOCKET             │ │
                                    │    │  (16-pin for carrier module)    │ │
                                    │    │                                 │ │
                                    │    │  VMOT ◀── 12V                   │ │
                                    │    │  VDD  ◀── 5V                    │ │
                                    │    │  GND  ◀── GND                   │ │
                                    │    │                                 │ │
                                    │    │  STEP ◀── Arduino D2            │ │
                                    │    │  DIR  ◀── Arduino D3            │ │
                                    │    │  EN   ◀── Arduino D4            │ │
                                    │    │                                 │ │
                                    │    │  1A ──▶─┐                       │ │
                                    │    │  1B ──▶─┼──▶ Motor Coil A       │ │
                                    │    │  2A ──▶─┤                       │ │
                                    │    │  2B ──▶─┴──▶ Motor Coil B       │ │
                                    │    │                                 │ │
                                    │    │  MS1, MS2, MS3 ── Directly      │ │
                                    │    │  directly on module or via      │ │
                                    │    │  jumpers                        │ │
                                    │    └─────────────────────────────────┘ │
                                    │                                         │
                                    │    ┌────────┐                          │
                                    │    │ LED4   │◀── Step signal           │
                                    │    │Activity│                          │
                                    │    └────────┘                          │
                                    │                                         │
                                    └─────────────────────────────────────────┘
```

## Detailed Circuit Sections

### 1. USB-C Power Delivery Input (J1)

```
USB-C Connector (16-pin, power-only configuration)
═══════════════════════════════════════════════════

Pin assignments:
  A1 (GND)  ─────┬───── GND
  A4 (VBUS) ─────┼───── VBUS_USB ──▶ To CH224K VIN
  A5 (CC1)  ─────┼───── CC1 ──────▶ To CH224K CC1
  A8 (SBU1) ─────┼───── NC
  A9 (VBUS) ─────┼───── VBUS_USB
  A12(GND)  ─────┤
                 │
  B1 (GND)  ─────┤
  B4 (VBUS) ─────┼───── VBUS_USB
  B5 (CC2)  ─────┼───── CC2 ──────▶ To CH224K CC2
  B8 (SBU2) ─────┼───── NC
  B9 (VBUS) ─────┼───── VBUS_USB
  B12(GND)  ─────┴───── GND

VBUS Protection:
  VBUS_USB ──┬── FUSE (2A polyfuse) ──┬── CH224K VIN
             │                        │
             └── TVS (SMBJ15A) ───────┴── GND
```

### 2. CH224K USB-C PD Controller (U1)

```
CH224K Pin Configuration (for 12V output)
═════════════════════════════════════════

                    ┌────────────┐
           VIN ─────┤1  VIN  VDD├───── 5V (from buck)
                    │           │
           CC1 ─────┤2  CC1  VO1├───── 12V_USB (output)
                    │           │
           CC2 ─────┤3  CC2  VO2├───── 12V_USB (output)
                    │           │
          CFG1 ─────┤4 CFG1  GND├───── GND
           NC       │           │
                    │           │
          CFG2 ─────┤5 CFG2 CFG3├───── CFG3 (NC)
           1K to    │           │      NC
           GND      └────────────┘

CFG Pin Configuration for 12V:
  CFG1: Leave floating (open)
  CFG2: Connect to GND via 1K resistor
  CFG3: Leave floating (open)

Capacitors:
  C1: 10µF ceramic on VIN (close to pin)
  C2: 10µF ceramic on VO1/VO2 (output)

LED3 (PD Status):
  VO1 ── 1K resistor ── LED3 (Blue) ── GND
  (LED lights when 12V is negotiated)
```

### 3. DC Barrel Jack Input (J2)

```
DC Jack (5.5mm x 2.1mm, center positive)
════════════════════════════════════════

          ┌─────────────────┐
   TIP ───┤ + (Center)      │
          │                 │──── 12V_DC
  SLEEVE ─┤ - (Barrel)      │
          │                 │──── GND
          └─────────────────┘

Reverse Polarity Protection:
  12V_DC ── SS54 Schottky ──▶── 12V_BUS
            (Cathode toward bus)
```

### 4. Power OR-ing (Dual Input)

```
Combining USB-C and DC Jack Power
═════════════════════════════════

                ┌── SS54 ──┐
  12V_USB ──────┤          ├──────┬──── 12V_BUS
                └──────────┘      │
                                  │
                ┌── SS54 ──┐      │
  12V_DC  ──────┤          ├──────┘
                └──────────┘

Both diodes are Schottky (SS54, 5A 40V):
  - Low forward voltage drop (~0.5V)
  - Prevents backfeed between sources
  - Whichever source is higher/connected powers the bus

Bulk Capacitor:
  12V_BUS ──┬── 100µF electrolytic ──┬── GND
            │                        │
            └── 100nF ceramic ───────┘

LED1 (12V Power):
  12V_BUS ── 4.7K resistor ── LED1 (Green) ── GND
```

### 5. 5V Buck Converter (U2)

```
MP2359 Buck Converter (12V to 5V, 1.2A)
═══════════════════════════════════════

Alternative: Use AP63205 for 2A output

                         L1 (10µH)
                    ┌────────────┐
  12V_BUS ──┬───────┤VIN     SW├───┬───┬─── 5V_BUS
            │       │           │   │   │
            C3      │      FB├──┼───┤   C5
            100nF   │           │   R5  22µF
            │       │      EN├──┘   │   │
            │       │           │  1K   │
            GND ────┤GND    GND├───┴───┴── GND
                    └────────────┘
                         │
                        BST
                         │
                        C4 (100nF)

Component Values (MP2359):
  L1: 10µH inductor (shielded, 2A saturation)
  C3: 100nF ceramic (input)
  C5: 22µF ceramic (output)
  C4: 100nF ceramic (bootstrap)
  R5: Feedback divider (set for 5V - see datasheet)
      For 5V: R5 = 10K from FB to GND
              R6 = 40.2K from FB to 5V_BUS

LED2 (5V OK):
  5V_BUS ── 1K resistor ── LED2 (Green) ── GND

Output Connector (J5):
  5V_BUS ── 2-pin header ── For Arduino/Pi power
  GND    ──┘
```

### 6. A4988 Driver Socket (16-pin DIP socket)

```
A4988 Carrier Module Socket
═══════════════════════════

Standard Pololu-style 16-pin layout (0.6" wide):

        ┌────────────────────────────┐
        │ ●                        ● │
  EN ───┤ 1  ENABLE         VMOT 16 ├─── 12V_BUS
        │                            │
  MS1 ──┤ 2  MS1             GND  15 ├─── GND (motor supply)
        │                            │
  MS2 ──┤ 3  MS2              2B  14 ├─── Motor Coil B-
        │                            │
  MS3 ──┤ 4  MS3              2A  13 ├─── Motor Coil B+
        │                            │
  RST ──┤ 5  RESET            1A  12 ├─── Motor Coil A+
        │                            │
  SLP ──┤ 6  SLEEP            1B  11 ├─── Motor Coil A-
        │                            │
 STEP ──┤ 7  STEP            VDD  10 ├─── 5V_BUS
        │                            │
  DIR ──┤ 8  DIR             GND   9 ├─── GND (logic)
        │ ●                        ● │
        └────────────────────────────┘

Connections:
  Pin 1  (EN)    ← Arduino D4 via header J4
  Pin 2  (MS1)   ← Directly to jumper header or tie to VDD (high)
  Pin 3  (MS2)   ← Directly to jumper header or tie to VDD (high)
  Pin 4  (MS3)   ← Directly to jumper header or tie to VDD (high)
  Pin 5  (RESET) ← Tie to Pin 6 (SLEEP) - keeps driver enabled
  Pin 6  (SLEEP) ← Tie to VDD via 10K pullup
  Pin 7  (STEP)  ← Arduino D2 via header J4
  Pin 8  (DIR)   ← Arduino D3 via header J4
  Pin 9  (GND)   ← GND
  Pin 10 (VDD)   ← 5V_BUS
  Pin 11 (1B)    → Motor connector J3 pin 2
  Pin 12 (1A)    → Motor connector J3 pin 1
  Pin 13 (2A)    → Motor connector J3 pin 3
  Pin 14 (2B)    → Motor connector J3 pin 4
  Pin 15 (GND)   ← GND
  Pin 16 (VMOT)  ← 12V_BUS

CRITICAL: 100µF electrolytic capacitor across VMOT (pin 16) and GND (pin 15)
          Place as close as possible to pins.

Microstepping Jumpers (optional):
  3x 2-pin headers for MS1, MS2, MS3
  Jumper on = tied to VDD (1/16 stepping)
  Jumper off = floating/low (full step)
  
  Default: All three jumpered for 1/16 microstepping
```

### 7. Motor Output Connector (J3)

```
4-pin JST-XH Connector (2.5mm pitch)
Or 4-position screw terminal

  ┌──────────────────────┐
  │  1    2    3    4    │
  └──┬────┬────┬────┬───┘
     │    │    │    │
     │    │    │    └── 2B (Motor Coil B-)
     │    │    └─────── 2A (Motor Coil B+)
     │    └──────────── 1B (Motor Coil A-)
     └───────────────── 1A (Motor Coil A+)

Wire colors for Creality 42-40 motor:
  1A = Red    ─┐ Coil A (Red-Green are continuous)
  1B = Green  ─┘
  2A = Blue   ─┐ Coil B (Blue-Black are continuous)
  2B = Black  ─┘
  
IMPORTANT: 1A/1B MUST be one coil pair, 2A/2B MUST be the other coil pair.
Verify with multimeter - coil pairs have low resistance ~2-4Ω.
If wires are swapped between coils (e.g., Red-Blue, Green-Black), the motor
will seize, vibrate, and get hot instead of rotating!
```

### 8. Arduino Interface (J4)

```
4-pin header (0.1" pitch)

  ┌────────────────┐
  │  1   2   3   4 │
  └──┬───┬───┬───┬─┘
     │   │   │   │
     │   │   │   └── GND
     │   │   └────── EN (Enable) ─── Arduino D4
     │   └────────── DIR ─────────── Arduino D3
     └────────────── STEP ────────── Arduino D2

All signal lines include 100Ω series resistors
for ESD and noise protection.
```

### 9. Step Activity LED (LED4)

```
Step Pulse Indicator
════════════════════

STEP signal ──┬── to A4988 Pin 7
              │
              └── 1K resistor ── LED4 (Yellow) ── GND

LED will flicker during motor movement.
For sustained glow, add RC filter:

STEP ── 10K ──┬── 10µF ──┬── LED4
              │          │
              └──────────┘
                  (optional RC for persistence)
```

## Complete Schematic Net List

```
Net Name        Connections
═══════════════════════════════════════════════════════
GND             USB-C GND pins, DC Jack sleeve, CH224K GND,
                Buck GND, A4988 pins 9&15, all LED cathodes,
                decoupling caps, J4 pin 4, J5 pin 2

VBUS_USB        USB-C VBUS pins (A4,A9,B4,B9), Fuse input,
                TVS anode

VIN_PROTECTED   Fuse output, CH224K VIN, TVS cathode

CC1             USB-C A5, CH224K CC1
CC2             USB-C B5, CH224K CC2

12V_USB         CH224K VO1/VO2, Schottky D1 anode

12V_DC          DC Jack tip, Schottky D2 anode

12V_BUS         D1 cathode, D2 cathode, Buck VIN,
                A4988 VMOT (pin 16), LED1 anode via R,
                bulk capacitor

5V_BUS          Buck output, CH224K VDD, A4988 VDD (pin 10),
                LED2 anode via R, J5 pin 1, pullups

STEP            J4 pin 1, 100Ω resistor, A4988 pin 7,
                LED4 anode via R

DIR             J4 pin 2, 100Ω resistor, A4988 pin 8

ENABLE          J4 pin 3, 100Ω resistor, A4988 pin 1

MOTOR_1A        A4988 pin 12, J3 pin 1
MOTOR_1B        A4988 pin 11, J3 pin 2
MOTOR_2A        A4988 pin 13, J3 pin 3
MOTOR_2B        A4988 pin 14, J3 pin 4
```

## Layout Guidelines

1. **Power path**: Keep 12V and 5V traces wide (40-50 mil minimum)
2. **Ground plane**: Use bottom layer as ground pour
3. **Decoupling**: Place caps close to IC power pins
4. **Buck inductor**: Keep away from sensitive signals
5. **A4988 socket**: Position for easy module insertion
6. **Thermal**: Ensure adequate copper for heat dissipation
7. **Connectors**: Place on board edges for easy access


