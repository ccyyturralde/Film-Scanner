# Simplified PCB - Using Pre-Made Modules

If SMD soldering isn't your thing, here's an easier version using pre-made modules.

**Trade-offs:**
- Easier to assemble (through-hole only)
- Slightly larger board
- Slightly higher cost (~$5-10 more)
- More reliable (modules are pre-tested)

---

## Module-Based Design

Instead of individual SMD chips, use these pre-made modules:

### Required Modules

| Module | Purpose | Size | Price |
|--------|---------|------|-------|
| ZY12PDN | USB-C PD trigger (12V) | 22x15mm | $3-5 |
| MP1584 Mini | 12V to 5V buck | 22x17mm | $1-2 |
| A4988 carrier | Stepper driver | 15x20mm | $2-4 |

---

## Simplified Schematic

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SIMPLIFIED FILM SCANNER CONTROLLER             │
│                                                                     │
│   ┌─────────────┐                                                  │
│   │   USB-C     │     ┌─────────────┐                              │
│   │ (on ZY12PDN)│────▶│  ZY12PDN    │                              │
│   │             │     │  USB-C PD   │──── 12V ──┬──▶ A4988 VMOT    │
│   └─────────────┘     │  Trigger    │           │                  │
│                       └─────────────┘           │                  │
│                                                 │                  │
│   ┌─────────────┐              ┌────────────────┤                  │
│   │   DC Jack   │──── 12V ─────┤                │                  │
│   │  5.5x2.1mm  │              │   OR-ing       │                  │
│   └─────────────┘              │   Diodes       │                  │
│                                └────────────────┘                  │
│                                        │                           │
│                                        ▼                           │
│                                ┌─────────────┐                     │
│                                │   MP1584    │                     │
│                                │ Buck Module │──── 5V ──▶ A4988 VDD│
│                                │  12V → 5V   │     │               │
│                                └─────────────┘     └──▶ 5V Header  │
│                                                                     │
│                                ┌─────────────┐     ┌─────────────┐ │
│                                │   A4988     │     │   Motor     │ │
│   ┌─────────────┐              │   Driver    │────▶│  Connector  │ │
│   │  Arduino    │──────────────▶   Module    │     │   4-pin     │ │
│   │  Header     │  STEP,DIR,EN │             │     └─────────────┘ │
│   │  4-pin      │              └─────────────┘                     │
│   └─────────────┘                                                  │
│                                                                     │
│   LEDs: 12V OK, 5V OK, Step Activity                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## PCB Layout (Simplified)

Board size: 80mm x 65mm (slightly larger to fit modules)

```
┌────────────────────────────────────────────────────────────────────────┐
│  ●                                                                  ●  │
│                                                                        │
│   ┌──────────────────┐                          ┌─────────────────┐   │
│   │                  │                          │                 │   │
│   │    ZY12PDN       │      ┌────────────┐     │   A4988 Module  │   │
│   │   USB-C PD       │      │            │     │                 │   │
│   │   Module         │      │   MP1584   │     │    ┌───────┐    │   │
│   │                  │      │   Buck     │     │    │       │    │   │
│   │  ┌────────────┐  │      │   Module   │     │    │Heatsink    │   │
│   │  │  USB-C     │  │      │            │     │    │       │    │   │
│   │  │  (built-in)│  │      │ IN+ OUT+   │     │    └───────┘    │   │
│   │  └────────────┘  │      │ IN- OUT-   │     │                 │   │
│   │                  │      └──┬───┬─────┘     │                 │   │
│   │   VIN  GND  VOUT │         │   │          │                 │   │
│   └────┬────┬────┬───┘         │   │          └────────┬────────┘   │
│        │    │    │             │   │                   │            │
│        │    │    └─────────────┘   │                   │            │
│        │    │                      │                   │            │
│   ┌────┴────┴────┐     ┌───────────┴────┐     ┌───────┴───────┐    │
│   │   DC Jack    │     │    5V Rail     │     │  Motor Out    │    │
│   │              │     │                │     │   JST-XH      │    │
│   └──────────────┘     └────────────────┘     └───────────────┘    │
│                                                                        │
│   ○ ○ ○                                        ┌───────────────┐      │
│   LED1 LED2 LED3                               │ Arduino Header│      │
│   12V  5V   Step                               │ STEP DIR EN GND     │
│                                                └───────────────┘      │
│                                                                        │
│   ┌────────────┐                               ┌───────────────┐      │
│   │ 5V Output  │                               │ Jumpers MS1-3 │      │
│   │   Header   │                               │   ○ ○ ○       │      │
│   └────────────┘                               └───────────────┘      │
│  ●                                                                  ●  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Simplified BOM

| Ref | Component | Quantity | Price | Notes |
|-----|-----------|----------|-------|-------|
| MOD1 | ZY12PDN USB-C PD trigger | 1 | $4 | Set to 12V |
| MOD2 | MP1584 Mini buck converter | 1 | $2 | Adjust to 5V |
| MOD3 | A4988 stepper driver module | 1 | $3 | Pololu-style |
| J1 | DC Barrel Jack 5.5x2.1mm | 1 | $0.30 | Center positive |
| J2 | JST-XH 4-pin | 1 | $0.20 | Motor output |
| J3 | 2.54mm header 1x4 | 1 | $0.10 | Arduino |
| J4 | 2.54mm header 1x2 | 1 | $0.05 | 5V output |
| JP1 | 2.54mm header 2x3 | 1 | $0.10 | Microstepping |
| D1 | SS54 Schottky (SMA) | 2 | $0.20 | Power OR-ing |
| C1 | 100µF 25V electrolytic | 2 | $0.20 | Bulk caps |
| R1 | 4.7K 0603 | 1 | $0.02 | LED1 |
| R2 | 1K 0603 | 2 | $0.04 | LED2, LED3 |
| LED1 | Green 0805 | 1 | $0.05 | 12V indicator |
| LED2 | Green 0805 | 1 | $0.05 | 5V indicator |
| LED3 | Yellow 0805 | 1 | $0.05 | Step indicator |
| - | Pin headers (female) | 3 sets | $1 | For modules |

**Total component cost: ~$12-15**

---

## Wiring the Modules

### ZY12PDN Setup

The ZY12PDN has a button to select voltage. Press until 12V is displayed.

Connections:
- VIN: From USB-C (internal)
- GND: To common ground
- VOUT: 12V output → through diode to 12V bus

### MP1584 Setup

**BEFORE installing, adjust the output voltage:**
1. Connect 12V input
2. Measure output with multimeter
3. Turn potentiometer until output reads 5.0V
4. Mark position or apply nail polish to lock

Connections:
- IN+: From 12V bus
- IN-: To GND
- OUT+: 5V bus
- OUT-: To GND

### A4988 Module

Standard Pololu pinout. Module includes capacitors and components.

---

## Assembly Steps

### Through-hole only assembly:

1. **Solder female headers** for modules
   - 3-pin for ZY12PDN
   - 4-pin for MP1584
   - 16-pin for A4988

2. **Solder DC jack**

3. **Solder screw terminals or JST** for motor

4. **Solder Arduino header**

5. **Solder SMD diodes** (only SMD parts)
   - Or use through-hole 1N5822 instead

6. **Solder SMD LEDs and resistors**
   - Or use through-hole 3mm LEDs

7. **Solder electrolytic capacitors**
   - Observe polarity

8. **Plug in modules**

9. **Test before inserting motor**

---

## Through-Hole Alternative Components

If you want zero SMD:

| SMD Part | Through-Hole Alternative |
|----------|-------------------------|
| SS54 (SMA) | 1N5822 (DO-201) |
| LED 0805 | 3mm LED |
| 0603 resistors | 1/4W axial resistors |
| 100µF 0805 | Already through-hole |

This makes it solderable with basic equipment.

---

## Comparison: Full SMD vs Module-Based

| Aspect | Full SMD Design | Module-Based |
|--------|----------------|--------------|
| Board size | 70x60mm | 80x65mm |
| SMD components | ~30 | 3-6 (diodes, LEDs) |
| Difficulty | Intermediate | Easy |
| Component cost | ~$15 | ~$12 |
| Reliability | Good (if soldered well) | Excellent (pre-tested) |
| Repairability | Harder | Easy (swap modules) |
| Professional look | Better | Acceptable |

---

## Recommendation

**Choose Module-Based if:**
- You're new to PCB assembly
- You don't have SMD soldering equipment
- You want to get it working quickly
- You might want to upgrade/swap components later

**Choose Full SMD if:**
- You have SMD soldering experience
- You want a compact, professional result
- You're making multiple units
- You enjoy the challenge

Both designs will work equally well for the film scanner.

