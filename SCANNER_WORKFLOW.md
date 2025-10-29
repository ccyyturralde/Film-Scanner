# Film Scanner - Simplified Professional Version

## Overview

This is a cleaned-up, professional film scanner control application that focuses on:
- **Manual Mode**: Full keyboard control for precise positioning
- **Calibrated Mode**: Learn frame spacing once, use for entire roll
- **NO problematic CV**: Removed unreliable computer vision alignment

## Key Improvements

### Proper Calibration Workflow

1. **Manual positioning of frame 1** - You control this completely
2. **Manual positioning of frame 2** - You advance to next frame  
3. **System learns the distance** - This becomes the calibrated advance
4. **Reuse for all frames** - Same distance works for entire roll

### Why This Works Better

- **No CV detection failures** - You visually confirm alignment
- **Frame 1 positioning is irrelevant** - Only the distance between frames matters
- **Consistent 35mm spacing** - Film frames are uniformly spaced
- **Professional workflow** - Similar to commercial scanners

## Operating Modes

### Manual Mode (Default)

Perfect for:
- Initial setup
- Problem frames
- Full control

Workflow:
1. Use arrow keys to position each frame
2. Press SPACE to capture
3. Repeat for each frame

### Calibrated Mode

Perfect for:
- Bulk scanning
- Consistent results
- Speed

Workflow:
1. Position frame 1 manually
2. Press C to start calibration
3. Position frame 2 manually
4. System calculates spacing
5. Press SPACE to auto-advance and capture each frame

## Controls

| Key | Action | Description |
|-----|--------|-------------|
| **← →** | Manual jog | Move film backward/forward |
| **G** | Toggle step size | Switch between small/LARGE steps |
| **SPACE** | Capture | Capture frame (auto-advance if calibrated) |
| **A** | Advance | Move one frame forward |
| **C** | Calibrate | Learn frame spacing |
| **M** | Mode toggle | Switch Manual/Calibrated |
| **N** | New roll | Start new roll |
| **P** | Preview | Capture preview image |
| **Z** | Zero | Reset position counter |
| **Q** | Quit | Exit application |

## Workflow Examples

### First-Time Setup

```
1. Start app: python3 scanner_app.py
2. Press N → Enter roll name
3. Insert film into scanner
4. Use arrows to position frame 1
5. Press C to calibrate
6. Use arrows to position frame 2
7. Press ENTER when aligned
8. System learns spacing (e.g., 1200 steps)
9. Press SPACE for each subsequent frame
```

### Resuming a Roll

```
1. Start app
2. Press N → Enter same roll name
3. Choose "Resume"
4. Continue from last frame
```

### Manual Scanning (No Calibration)

```
1. Press N → New roll
2. Stay in Manual mode
3. Use arrows for each frame
4. Press SPACE to capture
5. Repeat
```

## Position Tracking

The system tracks:
- Current position (steps from zero)
- Frame positions (where each frame was captured)
- Calibrated advance distance

This data is saved in `.scan_state.json` for each roll.

## Troubleshooting

### "Frame 1 not aligned" Error
**This is removed!** The new version doesn't try to detect alignment. You manually confirm when frames are positioned correctly.

### Inconsistent Advance
- Check motor coupling (no slippage)
- Verify step settings match your hardware
- Recalibrate if needed

### Different Frame Spacing
- Some cameras have variable spacing
- Use Manual mode for these
- Or recalibrate mid-roll

## Motor Configuration

Edit these values in the code to match your hardware:

```python
self.fine_step = 8       # Steps for fine movement
self.coarse_step = 64    # Steps for coarse movement
self.step_delay = 800    # Microseconds between steps
self.default_advance = 1200  # Default frame advance
```

## File Structure

Scans are saved to:
```
~/scans/
└── 2024-10-29/
    └── roll_name/
        ├── .scan_state.json
        ├── 20241029-120000.cr3
        ├── 20241029-120030.cr3
        └── ...
```

## Hardware Notes

### Arduino Commands

The app sends these commands:
- `f/b` - Fine forward/backward
- `F/B` - Coarse forward/backward  
- `H123` - Forward exact steps
- `h123` - Backward exact steps
- `Z` - Zero position
- `U/E/M` - Unlock/Enable/Disable motor

### Step Sizes

Adjust based on your setup:
- **Fine steps**: Small adjustments (8 default)
- **Coarse steps**: Large movements (64 default)
- **Frame advance**: ~1200 steps for 35mm (calibrated)

## Why This Approach?

1. **Reliability** - No CV detection failures
2. **Speed** - Calibrate once, scan many
3. **Flexibility** - Manual override always available
4. **Professional** - Similar to commercial scanners
5. **Simple** - Less complexity, fewer failure points

## Summary

This version removes the problematic "smart align" features and focuses on what works:
- You control frame alignment visually
- System learns consistent frame spacing
- Calibrated advance for efficiency
- Manual mode for full control

The key insight: **35mm frames are uniformly spaced**, so learning the distance once and reusing it is more reliable than complex CV detection.
