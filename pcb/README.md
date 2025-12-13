# Film Scanner Motor Controller PCB

A simple, reliable motor controller board for the 35mm film scanner project.

## Features

- **Dual Power Input**: USB-C Power Delivery (12V) OR 12V DC barrel jack
- **NEMA 17 Stepper Support**: Via A4988/DRV8825 driver module
- **Status LEDs**: Power, 5V rail, USB-C PD status, motor activity
- **Arduino Interface**: 4-pin header for Step, Dir, Enable, GND
- **5V Output**: For powering Arduino or other logic

## Specifications

| Parameter | Value |
|-----------|-------|
| Board Size | 70mm x 60mm |
| Input Voltage | 12V (via USB-C PD or DC jack) |
| Motor Voltage | 12V |
| Logic Voltage | 5V (regulated on-board) |
| Max Motor Current | 2A per phase (A4988 limit) |
| 5V Output Current | 2A max |

## Power Input Options

### Option 1: USB-C Power Delivery
- Requires a USB-C PD charger (45W+ recommended)
- CH224K chip negotiates 12V from the charger
- LED indicates successful PD negotiation

### Option 2: 12V DC Barrel Jack
- Standard 5.5mm x 2.1mm barrel jack
- Center positive
- 12V 2A minimum supply required

**Note**: Both can be connected. Schottky diodes prevent backfeed. The higher voltage source will power the board.

## Connectors

| Connector | Type | Purpose |
|-----------|------|---------|
| J1 | USB-C | Power input (PD 12V) |
| J2 | DC Barrel Jack | Power input (12V backup) |
| J3 | 4-pin JST-XH | Motor output (A, A, B, B) |
| J4 | 4-pin header | Arduino (STEP, DIR, EN, GND) |
| J5 | 2-pin header | 5V output (optional Pi/Arduino power) |

## LED Indicators

| LED | Color | Function |
|-----|-------|----------|
| LED1 | Green | 12V power present |
| LED2 | Green | 5V rail OK |
| LED3 | Blue | USB-C PD negotiated |
| LED4 | Yellow | Step pulse activity |

## Driver Module

This board uses a **socket for Pololu-style A4988 or DRV8825 carrier modules**.
These are 16-pin, 0.6" wide modules available from:
- Pololu
- Amazon
- AliExpress

**Do NOT install a bare A4988 chip. Use the carrier module.**

## Assembly Notes

1. Solder SMD components first (CH224K, buck converter IC, small passives)
2. Solder through-hole components (connectors, capacitors, driver socket)
3. Install driver module AFTER board testing
4. Verify 12V and 5V rails before inserting driver

## Files in This Folder

- `README.md` - This file
- `SCHEMATIC.md` - Detailed schematic description
- `BOM.csv` - Bill of Materials with part numbers
- `film_scanner_controller.kicad_sch` - KiCad schematic
- `film_scanner_controller.kicad_pcb` - KiCad PCB layout
- `gerbers/` - Gerber files for PCBway (after export)

## Ordering from PCBway

1. Open the KiCad project
2. Generate Gerber files (File → Plot)
3. Generate drill files
4. Zip the gerber folder
5. Upload to pcbway.com
6. Select: 2-layer, 1.6mm thickness, HASL finish, green solder mask

Typical cost: $5-15 for 5 boards + shipping


