# Film Scanner v2 - Quick Reference Card

## Essential Controls

```
MOVEMENT
├── ← →           Fine adjust (8 or 64 steps)
├── Shift+← →     Full frame back/forward
└── G             Toggle small/LARGE steps

CAPTURE
├── SPACE         Capture + auto-advance
├── F             Autofocus
└── A             Toggle auto-advance ON/OFF

SETUP
├── N             New roll
├── C             Calibrate (captures frames 1 & 2)
└── M             Manual/Calibrated mode

UTILITY
├── Z             Zero position
└── Q             Quit
```

## Standard Workflow

```
1. N → Create roll
2. Position frame 1 with arrows
3. C → Calibrate
   - SPACE to confirm frame 1 (captures)
   - Position frame 2 with arrows
   - SPACE to confirm frame 2 (captures)
4. SPACE for each remaining frame
```

## Status Display

```
Roll: [roll_name]
Frame: [count]          ← No limit!
Position: [steps]
Mode: MANUAL/CALIBRATED
Frame advance: [steps]
Camera: ✓/✗ Connected   ← Live status
Auto-advance: ON/OFF
```

## Key Improvements

| Feature | What Changed |
|---------|-------------|
| **Capture Order** | Captures THEN advances (was opposite) |
| **Calibration** | Captures both frames 1 & 2 |
| **Fine Adjust** | Always available, even in calibrated mode |
| **Shift+Arrows** | Jump full frame forward/back |
| **Autofocus** | F key (replaced preview) |
| **Camera Files** | Saved to SD card (not downloaded) |
| **Frame Counter** | Unlimited (was capped) |

## Calibration Explained

```
Position Frame 1 → C → SPACE (captures)
                        ↓
                Position Frame 2
                        ↓
                    SPACE (captures)
                        ↓
                 Spacing = Pos2 - Pos1
                        ↓
              Use for all frames
```

## Modes

### Manual Mode
- Full control
- No automation
- Position each frame

### Calibrated + Auto-Advance ON
- SPACE = capture + advance
- Most efficient
- Fine-tune with arrows

### Calibrated + Auto-Advance OFF  
- SPACE = capture only
- Shift+Right to advance
- More control

## Quick Tips

1. **Drift correction**: Use arrows between frames
2. **Different spacing**: Recalibrate mid-roll with C
3. **Problem frame**: Turn off auto-advance (A), position manually
4. **Jump frames**: Shift+arrows moves full frame
5. **Focus check**: Press F before capturing

## Files

- **Images**: Camera SD card (.CR3)
- **State**: `~/scans/DATE/roll/.scan_state.json`

## Remember

- Calibration captures frames 1 & 2 (no missing!)
- Auto-advance happens AFTER capture
- Fine adjustments always work
- Camera status shown live
- SPACE for all confirmations
