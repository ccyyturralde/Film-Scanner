# PCB Assembly Guide

## Before You Start

**Required Tools:**
- Soldering iron (temperature controlled, 350°C)
- Solder (0.5mm leaded or lead-free)
- Flux (liquid or paste)
- Tweezers (fine tip, ESD safe)
- Multimeter
- Magnification (loupe or microscope)
- Hot air station (optional, for USB-C connector)

**Order of Assembly:**
1. SMD components (smallest first)
2. Through-hole components
3. Connectors
4. Test before installing driver module

---

## Step 1: SMD Passive Components (0603/0805)

Solder in this order:

### Resistors (0603)
| Ref | Value | Location | Notes |
|-----|-------|----------|-------|
| R1 | 1K | Near CH224K | CFG2 pulldown |
| R2 | 4.7K | Near LED1 | 12V LED current |
| R3 | 1K | Near LED2 | 5V LED current |
| R4 | 1K | Near LED3 | PD LED current |
| R5 | 1K | Near LED4 | Step LED current |
| R6 | 40.2K | Near MP2359 | FB divider top |
| R7 | 10K | Near MP2359 | FB divider bottom |
| R8 | 10K | Near A4988 socket | SLEEP pullup |
| R9 | 100Ω | Signal path | STEP protection |
| R10 | 100Ω | Signal path | DIR protection |
| R11 | 100Ω | Signal path | EN protection |

### Ceramic Capacitors (0603/0805)
| Ref | Value | Package | Location |
|-----|-------|---------|----------|
| C1 | 10µF | 0805 | CH224K VIN |
| C2 | 10µF | 0805 | CH224K output |
| C3 | 100nF | 0603 | MP2359 VIN |
| C4 | 100nF | 0603 | MP2359 BST |
| C5 | 22µF | 0805 | MP2359 output |
| C7 | 100nF | 0603 | 12V decoupling |

### LEDs (0805)
| Ref | Color | Anode Side |
|-----|-------|------------|
| LED1 | Green | Toward R2 |
| LED2 | Green | Toward R3 |
| LED3 | Blue | Toward R4 |
| LED4 | Yellow | Toward R5 |

**LED Orientation:** The cathode (negative) is usually marked with a green line or T-shape on the bottom.

---

## Step 2: SMD ICs

### U1 - CH224K (SOP-10)
1. Apply flux to pads
2. Align pin 1 (marked with dot) to pin 1 pad
3. Tack one corner pin
4. Check alignment
5. Solder remaining pins
6. Clean flux residue

**Pin 1 identification:** Small dot on chip corner

### U2 - MP2359DJ (SOT23-6)
1. Apply flux to pads
2. Align pin 1 to pad 1
3. Tack one corner
4. Solder remaining pins

**Pin 1 identification:** Marked with dot or bar

---

## Step 3: SMD Diodes

### D1, D2 - SS54 Schottky (SMA package)
**CRITICAL: Observe polarity!**
- Cathode (bar marking) faces TOWARD 12V bus
- Anode faces toward power source

### D3 - SMBJ15A TVS (SMB package)
- Cathode bar faces toward VBUS
- This is reverse polarity from a regular diode orientation

---

## Step 4: Inductor

### L1 - 10µH Shielded Inductor
- No polarity
- Align with pad orientation
- Use generous solder for good thermal connection

---

## Step 5: Through-Hole Components

### Electrolytic Capacitors
| Ref | Value | Notes |
|-----|-------|-------|
| C6 | 100µF 25V | 12V bulk, observe polarity (- stripe = negative) |
| C8 | 100µF 25V | VMOT decoupling, CRITICAL for driver |

**CRITICAL:** C8 must be as close as possible to A4988 pins 15 and 16.

### Resettable Fuse
| Ref | Value |
|-----|-------|
| F1 | 2A PTC |

No polarity.

---

## Step 6: Connectors

### J1 - USB-C Receptacle
This is the trickiest component.

**Option A - Hot Air:**
1. Apply solder paste to all pads
2. Place connector carefully
3. Heat with hot air at 380°C
4. Allow to cool

**Option B - Hand Solder:**
1. Tack the large mounting tabs first
2. Solder each pin carefully with fine tip
3. Check for bridges between pins
4. Use flux and solder wick to clean bridges

### J2 - DC Barrel Jack
- Center pin is positive
- Barrel is ground
- Solder from bottom, component on top

### J3 - Motor Connector (JST-XH 4-pin)
- Check orientation before soldering
- Connector opening faces board edge

### J4 - Arduino Header (1x4)
Pin order: STEP, DIR, EN, GND (left to right)

### J5 - 5V Output (1x2)
Pin order: 5V, GND

### JP1 - Microstepping Jumpers (2x3)
For MS1, MS2, MS3 configuration

### U3 - 16-pin DIP Socket
**DO NOT install driver module yet!**
- Align notch with silkscreen marking
- Solder all 16 pins
- Socket notch indicates pin 1 end

---

## Step 7: Pre-Power Testing

**Before applying power, check these with multimeter:**

| Test | Probe + | Probe - | Expected |
|------|---------|---------|----------|
| No shorts 12V to GND | C6+ | C6- | >10kΩ |
| No shorts 5V to GND | C5+ | C5- | >10kΩ |
| VMOT capacitor | C8+ | C8- | >10kΩ |

**If any shows near 0Ω, you have a short. DO NOT power on!**

---

## Step 8: Initial Power Test

### Test with DC Jack first (easier to debug)

1. Connect 12V DC supply to J2
2. Check LED1 (green) lights up - 12V OK
3. Measure 12V_BUS with multimeter (should be ~11.5V after diode drop)
4. Check LED2 (green) lights up - 5V OK
5. Measure 5V_BUS (should be 4.9-5.1V)

### Test USB-C PD

1. Connect USB-C PD charger (45W+ recommended)
2. Check LED3 (blue) lights up - PD negotiated
3. Check LED1 (green) lights up - 12V OK
4. Measure voltage (should be ~11.5V)

**If LED3 doesn't light:**
- Check CH224K solder joints
- Verify R1 (1K) is connected CFG2 to GND
- Try different PD charger

---

## Step 9: Install A4988 Module

**Only after power tests pass!**

1. Set microstepping jumpers (all 3 installed = 1/16 step)
2. Align A4988 module with socket (enable pin toward edge)
3. Press firmly into socket
4. Connect motor to J3
5. Connect Arduino to J4

### A4988 Module Orientation

```
        ┌─────────────────────────────────┐
        │  POT                            │
        │   ●                             │
        │                                 │
  EN ●──┤                            VMOT├──● 12V
 MS1 ●──┤                             GND├──● GND  
 MS2 ●──┤                              2B├──● Motor
 MS3 ●──┤                              2A├──● Motor
 RST ●──┤                              1A├──● Motor
 SLP ●──┤                              1B├──● Motor
STEP ●──┤                             VDD├──● 5V
 DIR ●──┤                             GND├──● GND
        └─────────────────────────────────┘
         Pin 1 end                  Pin 16 end
```

**CRITICAL:** If installed backwards, you will destroy the driver and possibly the motor!

---

## Step 10: Motor Current Adjustment

Before running motor at full speed:

1. Power on the board
2. Measure voltage between A4988 pot wiper and GND
3. Adjust pot for desired current:
   - Vref = I_motor × 8 × 0.05
   - For 1.0A: Vref = 0.40V
   - For 0.8A: Vref = 0.32V
4. Start conservative (0.3V) and increase if motor misses steps

---

## Troubleshooting

| Symptom | Possible Cause | Solution |
|---------|----------------|----------|
| No LEDs light | Short circuit | Check for bridges |
| LED1 off, others on | 12V diode backwards | Check D1/D2 orientation |
| LED2 off | Buck converter issue | Check L1, C5, U2 |
| LED3 off | PD not negotiating | Check CH224K, R1, charger |
| Motor vibrates only | Current too low | Increase Vref |
| Motor doesn't move | Enable high | Check EN signal |
| Motor very hot | Current too high | Decrease Vref |
| Driver shuts down | Overcurrent/thermal | Reduce current, add heatsink |

---

## Final Checklist

- [ ] All SMD components soldered
- [ ] No solder bridges
- [ ] Electrolytic caps correct polarity
- [ ] 12V power test passed
- [ ] 5V power test passed
- [ ] USB-C PD test passed (LED3 on)
- [ ] A4988 oriented correctly
- [ ] Motor current set appropriately
- [ ] Motor moves in both directions

**Your board is ready for use!**

