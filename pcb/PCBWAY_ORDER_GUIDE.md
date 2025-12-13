# Ordering from PCBway - Step by Step

## Overview

PCBway offers affordable PCB manufacturing with good quality.
Typical cost: $5-15 for 5 boards + ~$15-25 shipping to USA.
Turnaround: 3-5 days production + shipping.

---

## Step 1: Prepare Gerber Files

In KiCad:

1. Open `film_scanner_controller.kicad_pcb`
2. Go to **File → Plot**
3. Set these options:
   - Plot format: **Gerber**
   - Output directory: **gerbers/**
   - Layers to plot:
     - [x] F.Cu (Front Copper)
     - [x] B.Cu (Back Copper)
     - [x] F.SilkS (Front Silkscreen)
     - [x] B.SilkS (Back Silkscreen)
     - [x] F.Mask (Front Solder Mask)
     - [x] B.Mask (Back Solder Mask)
     - [x] Edge.Cuts (Board Outline)
   - [x] Use Protel filename extensions
   - [x] Generate Gerber job file
4. Click **Plot**

5. Click **Generate Drill Files**
   - Drill file format: **Excellon**
   - Drill units: **Millimeters**
   - Zeros format: **Decimal format**
   - [x] PTH and NPTH in single file
   - Click **Generate Drill File**

6. Navigate to the `gerbers/` folder
7. Select all files and create a ZIP file: `film_scanner_gerbers.zip`

---

## Step 2: Upload to PCBway

1. Go to [www.pcbway.com](https://www.pcbway.com)
2. Click **Quote Now** or **Instant Quote**
3. Click **Add Gerber File** and upload your ZIP

---

## Step 3: Configure PCB Options

### Basic Parameters (use these exact settings)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Board type | Single pieces | |
| Size | 70 x 60 mm | Auto-detected from Gerber |
| Quantity | 5 | Minimum order |
| Layers | 2 | Two-layer board |
| Material | FR-4 | Standard |
| Thickness | 1.6 mm | Standard |
| Min Track/Spacing | 6/6 mil | Standard |
| Min Hole Size | 0.3 mm | Standard |
| Solder Mask | Green | Or your preference |
| Silkscreen | White | Standard |
| Surface Finish | HASL | Cheapest option |
| Copper Weight | 1 oz | Standard |
| Gold Fingers | No | |
| Castellated Holes | No | |
| Remove Order Number | No | (Yes costs extra) |

### Recommended Options

- **HASL (lead-free)** is fine for hobby use
- **ENIG** (gold) is better for fine-pitch but costs more
- **Green solder mask** is cheapest and most reliable

---

## Step 4: Review and Order

1. Verify the auto-detected dimensions match: **70mm x 60mm**
2. Review the preview image - board outline should look correct
3. Check the price (typically $5-15 for basic options)
4. Click **Add to Cart**
5. Choose shipping method:
   - **OCS/AliExpress Standard** (~$10-15, 10-20 days)
   - **DHL/FedEx** (~$25-40, 3-7 days)
6. Complete checkout

---

## Step 5: Order Components

While waiting for PCBs, order components.

### Option A: LCSC Electronics (ships with PCBway)

LCSC is PCBway's sister company. Components can ship together.

1. Go to [www.lcsc.com](https://www.lcsc.com)
2. Search by LCSC part numbers from BOM.csv
3. Add to cart (minimum quantities vary)

### Option B: Amazon/AliExpress (faster for some parts)

**Pre-made modules (easier than SMD):**
- Search "A4988 stepper driver module" 
- Search "USB-C PD trigger 12V" (ZY12PDN)
- Search "MP1584 buck converter module"

### Option C: DigiKey/Mouser (fastest, more expensive)

Professional distributors with guaranteed stock.

---

## Component Ordering Summary

### Must order (not optional):

| Item | Qty | Where | Est. Price |
|------|-----|-------|------------|
| CH224K | 1 | LCSC/AliExpress | $0.50 |
| MP2359 | 1 | LCSC/DigiKey | $0.40 |
| USB-C connector | 1 | LCSC/AliExpress | $0.30 |
| DC Barrel Jack | 1 | LCSC/Amazon | $0.20 |
| SS54 Schottky | 2 | LCSC | $0.20 |
| 16-pin DIP socket | 1 | Amazon/LCSC | $0.10 |
| JST-XH 4-pin | 1 | Amazon/LCSC | $0.10 |
| 10µH inductor | 1 | LCSC | $0.20 |
| Resistors (0603 kit) | 1 kit | Amazon | $8 |
| Capacitors (kit) | 1 kit | Amazon | $10 |
| LEDs (0805) | 4 | LCSC/Amazon | $0.20 |
| 100µF electrolytic | 2 | LCSC/Amazon | $0.20 |

**Estimated component cost: $15-25**

### Separately purchase:

| Item | Where | Est. Price |
|------|-------|------------|
| A4988 driver module | Amazon/AliExpress | $2-5 each |
| NEMA 17 motor | Amazon/AliExpress | $8-15 |
| USB-C PD charger 45W+ | Amazon | $15-25 |
| 12V power supply | Amazon | $8-12 |

---

## PCBway Assembly Service (Optional)

If you don't want to solder SMD components yourself, PCBway offers assembly.

1. When ordering, select **SMT Assembly**
2. Upload BOM.csv and component positions file
3. They source components and solder them
4. Cost: ~$30-50 extra for small quantities

**Recommended for:** People uncomfortable with SMD soldering

---

## Timeline

| Step | Duration |
|------|----------|
| PCB production | 3-5 business days |
| Shipping (standard) | 10-20 days |
| Shipping (express) | 3-7 days |
| Component shipping | 2-20 days (varies) |
| Assembly time | 1-2 hours |

**Plan for 2-4 weeks total with standard shipping.**

---

## Quality Check on Arrival

When PCBs arrive:

1. **Visual inspection**
   - No scratches on copper
   - Silkscreen legible
   - Board edges clean
   - No obvious defects

2. **Dimensional check**
   - Verify 70mm x 60mm size
   - Mounting holes in correct positions

3. **Electrical check (before assembly)**
   - No shorts between power planes
   - Via holes properly plated

---

## Troubleshooting Orders

| Issue | Solution |
|-------|----------|
| Gerbers rejected | Check layer count, file format |
| Wrong size detected | Verify Edge.Cuts layer is closed |
| High price quoted | Check for unusual options enabled |
| Assembly errors | Provide clear BOM with designators |

---

## Support

PCBway has good customer service:
- Email: service@pcbway.com
- Live chat on website
- Review Gerber files before production

They will flag issues before manufacturing.

