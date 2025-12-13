# PCB Layout Guidelines

## Board Specifications

| Parameter | Value |
|-----------|-------|
| Dimensions | 70mm x 60mm |
| Layers | 2 (Top copper, Bottom copper) |
| Thickness | 1.6mm |
| Copper weight | 1 oz (35µm) |
| Min trace width | 0.3mm (12 mil) for signals |
| Min trace width | 1.0mm (40 mil) for power |
| Min clearance | 0.2mm (8 mil) |
| Via size | 0.6mm pad, 0.3mm drill |

---

## Component Placement

### Top View Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  ●                                                               ●  │
│   M3                        TITLE: Film Scanner Controller       M3 │
│                                                                     │
│  ┌───────┐                                           ┌─────────┐   │
│  │       │                                           │  MOTOR  │   │
│  │ USB-C │   ┌─────────────────────────────────┐    │   JST   │   │
│  │  J1   │   │                                 │    │   J3    │   │
│  │       │   │                                 │    └─────────┘   │
│  └───────┘   │         A4988 SOCKET            │                   │
│              │            (U3)                 │    ○ ○ ○ ○        │
│   CH224K     │                                 │    LED1-4         │
│    (U1)      │       ┌───────────────┐        │                   │
│              │       │   HEATSINK    │        │                   │
│              │       │     AREA      │        │                   │
│  ┌─────┐     │       └───────────────┘        │    ┌─────────┐   │
│  │ DC  │     │                                 │    │ ARDUINO │   │
│  │ IN  │     └─────────────────────────────────┘    │ HEADER  │   │
│  │ J2  │                                            │   J4    │   │
│  └─────┘      ┌─────┐    C6    C8                   └─────────┘   │
│               │BUCK │   100µF  100µF                              │
│   D1  D2      │ U2  │     ●      ●                  ┌─────┐       │
│   ●   ●       └─────┘                               │ 5V  │       │
│                                                     │ OUT │       │
│                  L1                                 │ J5  │       │
│                  ●                                  └─────┘       │
│  ●                                                               ●  │
│   M3                                                             M3 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Zone Definitions

### Zone 1: Power Input (Left Side)
- USB-C connector J1 (top left edge)
- DC barrel jack J2 (left side)
- CH224K PD controller U1 (near USB-C)
- Schottky diodes D1, D2 (power OR-ing)
- Input protection TVS, fuse

**Keep high current paths short and wide.**

### Zone 2: Power Regulation (Center Left)
- Buck converter U2 (MP2359)
- Inductor L1
- Input/output capacitors
- Bulk electrolytic C6

**Keep inductor loop area small. Place input cap close to IC.**

### Zone 3: Motor Driver (Center)
- 16-pin DIP socket for A4988
- VMOT capacitor C8 (CRITICAL - as close as possible)
- Microstepping jumpers

**C8 must be within 10mm of pins 15/16. This is critical for driver stability.**

### Zone 4: Connectors (Right Side)
- Motor output J3 (top right)
- Arduino header J4 (right side)
- 5V output J5 (bottom right)

**Place on board edge for easy cable access.**

### Zone 5: Indicators (Right Side)
- LED1: 12V power
- LED2: 5V power
- LED3: PD status
- LED4: Step activity

**Align vertically for neat appearance.**

---

## Trace Width Guidelines

| Net | Width | Notes |
|-----|-------|-------|
| GND | Plane/Pour | Use ground pour on bottom layer |
| 12V_BUS | 1.5mm | High current path |
| VBUS_USB | 1.2mm | USB power input |
| 12V_USB | 1.0mm | After PD chip |
| 12V_DC | 1.0mm | DC jack input |
| 5V_BUS | 0.8mm | Regulated 5V |
| VMOT | 1.5mm | Motor power |
| MOTOR_1A/1B/2A/2B | 0.8mm | Motor coils |
| STEP, DIR, EN | 0.3mm | Logic signals |
| CC1, CC2 | 0.25mm | USB-C CC signals |

---

## Critical Layout Rules

### 1. VMOT Capacitor (C8)
```
WRONG:
   [A4988]───────────5cm───────────[C8]
   
RIGHT:
   [A4988]─[C8]  (within 5mm)
```
Place C8 directly adjacent to A4988 socket pins 15 and 16.

### 2. Buck Converter Layout
```
        VIN ──┬── C_in ──┬── GND
              │          │
              └── U2 ────┼── SW ── L1 ──┬── VOUT
                  │      │              │
                 GND    GND            C_out
                                        │
                                       GND

Keep the loop: VIN → U2 → L1 → C_out → GND → C_in → VIN
as SMALL as possible.
```

### 3. USB-C Connector
- Route CC1 and CC2 as matched-length pairs
- Keep traces short to CH224K
- VBUS traces should be wide (1mm+)

### 4. Ground Plane
- Use bottom layer as solid ground pour
- Connect all GND pins with vias to ground plane
- Place vias near high-current components

---

## Via Placement

| Location | Via Size | Purpose |
|----------|----------|---------|
| Near bulk caps | 0.8mm pad | Power return path |
| Under A4988 | Multiple 0.6mm | GND thermal relief |
| Near buck IC | 0.6mm | GND for switching noise |
| Signal grounds | 0.6mm | Standard ground vias |

---

## Silkscreen

### Required Labels
- Component designators (R1, C1, U1, etc.)
- Connector pin labels (STEP, DIR, EN, GND)
- Polarity markings for electrolytics and diodes
- USB-C and DC jack labels
- Board title and version

### Optional but Helpful
- Outline around A4988 socket with "PIN 1" marker
- Motor wire color reference
- Voltage labels at test points

---

## Mounting Holes

Four M3 mounting holes:
- Position: 5mm inset from each corner
- Hole diameter: 3.2mm
- Pad diameter: 6mm (optional copper annulus)
- Connected to GND plane for shielding

```
Coordinates:
  Top-left:     (5, 5)
  Top-right:    (65, 5)
  Bottom-left:  (5, 55)
  Bottom-right: (65, 55)
```

---

## Design Rule Check (DRC) Settings

In KiCad, set these DRC rules:

| Rule | Value |
|------|-------|
| Minimum clearance | 0.2mm |
| Minimum track width | 0.25mm |
| Minimum via diameter | 0.6mm |
| Minimum via drill | 0.3mm |
| Minimum hole size | 0.3mm |
| Copper to edge | 0.3mm |

Run DRC before generating Gerbers. Fix all errors.

---

## Thermal Considerations

### Heat Sources
1. **A4988 driver** - Main heat source, use heatsink on module
2. **Schottky diodes** - Warm under load, adequate copper helps
3. **Buck inductor** - Slight warmth, no concern
4. **Buck IC** - Warm, thermal pad to ground pour

### Thermal Relief
- Use thermal spokes on through-hole pads for easier soldering
- Solid connection (no relief) for high-current pads

---

## Fabrication Notes

Add these notes to the Gerber files or order:

```
FABRICATION NOTES:
1. 2-layer PCB, 1.6mm FR-4
2. 1oz copper both sides
3. Green solder mask both sides
4. White silkscreen top side
5. HASL finish (lead-free acceptable)
6. Minimum trace/space: 6/6 mil
7. Minimum drill: 0.3mm
8. Board outline: Edge.Cuts layer
```

---

## Checklist Before Ordering

- [ ] DRC passes with no errors
- [ ] All components placed within board outline
- [ ] No traces crossing board edge
- [ ] All mounting holes present
- [ ] Power traces appropriately wide
- [ ] Ground pour connected with vias
- [ ] Silkscreen legible and not overlapping pads
- [ ] C8 (VMOT cap) is close to A4988 socket
- [ ] USB-C connector accessible from edge
- [ ] Connector orientations verified

