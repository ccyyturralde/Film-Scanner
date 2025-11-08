# Film Scanner Desktop - Complete Workflow Guide

## Understanding the Film Strip Process

Your film is cut into **strips of 5-6 frames each**. A typical 36-frame roll = 6-7 strips.

### Why Frame 1 is Special

When you load a strip into the scanner:
- The **motor is in the middle** of the scanning mask
- Frame 1 is positioned **halfway across** the mask initially
- This is normal and expected!
- The motor can't move frame 1 to center until you advance

## The Complete Process

### Phase 1: One-Time Calibration (Strip 1 Only)

**Purpose:** Capture frames 1 & 2 and learn the distance between them

```
1. New Roll (N key)
   └─> Enter roll name
   └─> Set frames per strip (5 or 6)

2. Load Strip 1
   └─> Hand-feed into scanner
   └─> Frame 1 starts halfway across mask (normal!)
   └─> Motor engages in middle of scanning area

3. Calibrate (C key)
   ├─> Position frame 1 perfectly (use ←/→ arrows)
   ├─> Click OK to CAPTURE frame 1 ✓
   ├─> Move to frame 2 (use ←/→ arrows)
   ├─> Click OK to CAPTURE frame 2 ✓
   └─> System calculates distance (e.g., "1245 steps")

✓ Frames 1 and 2 captured during calibration!
✓ Frame spacing learned!
```

### Phase 2: Complete Strip 1 (Frames 3-6)

```
4. Continue Forward
   ├─> Press SPACE → Frame 3 captured ✓
   ├─> Motor auto-advances 1245 steps
   ├─> Fine-tune with arrows if needed
   ├─> Press SPACE → Frame 4 captured ✓
   ├─> Motor auto-advances 1245 steps
   ├─> Press SPACE → Frame 5 captured ✓
   ├─> Motor auto-advances 1245 steps
   ├─> Press SPACE → Frame 6 captured ✓
   └─> Strip 1 COMPLETE (6 frames ✓)
```

### Phase 3: Additional Strips (2-6)

For each remaining strip (uses saved calibration):

```
5. New Strip (S key)
   ├─> Remove completed strip
   ├─> Hand-feed next strip
   │   └─> Frame 1 starts halfway across mask (like before)
   └─> Position frame 1 perfectly (use arrows)

6. Capture All Frames
   ├─> Press SPACE → Frame 1 ✓
   ├─> Motor advances (using saved 1245 steps)
   ├─> Adjust with arrows if needed
   ├─> Press SPACE → Frame 2 ✓
   ├─> Motor advances (using saved 1245 steps)
   ├─> Press SPACE → Frame 3 ✓
   └─> ...continue through frame 6

7. Repeat for remaining strips
   └─> Same process: S key, position frame 1, capture all 6 frames
```

## Key Points

### ✅ Always Available: Fine-Tuning

- **Before EVERY capture**, you can adjust position with arrow keys
- This accounts for:
  - Slight variations in frame spacing
  - Different strip cuts
  - Film curl or tension
- Computer vision auto-alignment was tried but **failed** (confused subjects with frame lines)
- Manual control = perfect alignment every time

### Frame Spacing Settings

```
Frames per Strip: [4] [5] [6] [7] [8]  ← Adjustable
```

- Set based on how you cut your film
- Typical: 6 frames per strip for 36-exposure roll
- Can be 5 frames if you prefer shorter strips

### Strip Progress Display

```
Status:
  Roll: Portra400-001
  Total Frames: 18
  Current: Strip 3, Frame 3/6  ← Shows progress
  Position: 3,735 steps
  Frame Spacing: 1245 steps ✓
```

## Troubleshooting Common Issues

### "Frame spacing seems inconsistent"

**This is normal!** Film strips are not perfectly uniform:
- Different perforations may vary slightly
- Strip cutting may not be exact
- Film tension affects spacing

**Solution:** Always fine-tune with arrows before each capture.

### "I'm at frame 6 but motor wants to advance more"

**Expected behavior:**
- Auto-advance stops after frame 6/6
- Status shows "Strip N complete! Press S for next strip"
- Motor won't auto-advance past last frame

### "First frame is partially off the mask"

**This is normal!**
- When loading a strip, frame 1 is halfway across
- Motor is positioned in the middle
- Use arrows to center frame 1 before first capture

### "Calibration says Frame 2 must be ahead of Frame 1"

**You moved backwards!**
- During calibration, frame 2 must be FORWARD from frame 1
- Use → arrows to advance to frame 2
- Don't use ← arrows during calibration step 2

## Keyboard Shortcuts Quick Reference

| Key | Action | When to Use |
|-----|--------|-------------|
| **←** | Fine back | Precise alignment |
| **→** | Fine forward | Precise alignment |
| **Shift+←** | Full frame back | Return to previous frame |
| **Shift+→** | Full frame forward | Jump to next frame |
| **Space** | CAPTURE | When frame is perfectly aligned |
| **C** | Calibrate | Once on first strip only |
| **S** | New strip | After completing each strip |
| **N** | New roll | Start new scanning session |
| **Z** | Zero position | Reset counter (rarely needed) |

## Example Session

**Roll:** Kodak Gold 200, 36 exposures, 6 strips

```
Session Started: 2024-11-07 14:30

Strip 1:
  - Calibrated: 1248 steps
  - Frames: 6/6 ✓
  - Total: 6 frames

Strip 2:
  - Used calibration
  - Frames: 6/6 ✓
  - Total: 12 frames

Strip 3:
  - Used calibration
  - Frames: 6/6 ✓
  - Total: 18 frames

Strip 4:
  - Used calibration
  - Frames: 6/6 ✓
  - Total: 24 frames

Strip 5:
  - Used calibration
  - Frames: 6/6 ✓
  - Total: 30 frames

Strip 6:
  - Used calibration
  - Frames: 6/6 ✓
  - Total: 36 frames

Session Complete: 36 frames scanned
Time: 28 minutes
Output: Camera SD card (IMG_0001.CR3 through IMG_0036.CR3)
```

## Tips for Success

1. **Calibrate carefully** - Take your time aligning frames 1 and 2
2. **Always fine-tune** - Use arrows before every capture
3. **Check frame lines** - Ensure frame is perfectly centered
4. **Use EOS Utility** - Launch for live preview and focus
5. **Save often** - App auto-saves, but sessions are resumable
6. **Label strips** - Use camera notes or write down which strip you're on
7. **Consistent lighting** - Keep lightbox brightness constant

---

**Happy Scanning! 🎞️📷**

