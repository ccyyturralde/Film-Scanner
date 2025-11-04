# Scanner Calibrated Step Mode - Technical Workflow

## Key Concepts

### Frame Engagement Issue
- First frame of each strip does not engage the sprocket until ~50% into the scanning window
- Therefore: First frame position is ONLY for visual alignment, not step calibration
- Step calibration must use frame 1 → frame 2 distance

### Calibration Data
- **frame_advance**: Steps between aligned frame 1 and aligned frame 2
- This is the ONLY reliable measurement for frame spacing
- Used for all remaining frames in all strips

### Strip Structure
- 5-6 frames per strip (depending on film carrier)
- Frame size constant throughout roll
- Frame gap has minor variance requiring occasional touch-ups

## Workflow Stages

### Stage 1: Initial Calibration (Strip 1 Only)

**Purpose**: Learn the true frame advance distance

**Steps**:
1. Press `C` to enter calibration
2. Position frame 1 using arrows
   - This position is for alignment only
   - Not used in step calculations
3. Press `SPACE` → Captures frame 1, records position
4. Manually advance to frame 2 using arrows
5. Press `SPACE` → Captures frame 2, records position
6. System calculates: `frame_advance = position_2 - position_1`

**Result**: 
- Strip 1 has 2 frames captured
- `frame_advance` stored for entire roll
- Mode switches to 'calibrated'

### Stage 2: Complete Strip 1

**Purpose**: Finish remaining frames in strip 1 using calibrated advance

**Operation**:
- For each frame 3, 4, 5 (or 6):
  - `SPACE` → Auto-advance frame_advance steps, then capture
  - Fine adjustments available with arrows before capture
  - Shift+arrows to jump full frames if needed

### Stage 3: New Strip (Strips 2, 3, 4, etc.)

**Purpose**: Load new strip and continue with learned spacing

**Steps**:
1. Press `S` to start new strip
2. Load new film strip physically
3. Position first frame using arrows
   - Again, this is just for visual alignment
   - frame_advance from calibration is still used
4. Press `SPACE` → Captures first frame of new strip
5. Continue with auto-advance for remaining frames

### Stage 4: Subsequent Frames on New Strip

**Operation**:
- Same as Strip 1 completion
- `SPACE` → Auto-advance + capture
- Manual adjustments always available

## Control Reference

### Movement
- `← →` : Fine adjustment (8 or 64 steps based on mode)
- `Shift+← →` : Full frame forward/backward
- `G` : Toggle small/LARGE step size

### Capture & Advance
- `SPACE` : Capture (and auto-advance if enabled and frame > 1)
- `A` : Toggle auto-advance ON/OFF
- `F` : Manual autofocus

### Workflow Commands
- `C` : Calibrate (only for strip 1)
- `S` : Start new strip (requires calibration first)
- `M` : Toggle manual/calibrated mode
- `N` : New roll
- `Z` : Zero position
- `Q` : Quit

## Calibration Math

```
Strip 1, Frame 1: position = X (not used for calculation)
Strip 1, Frame 2: position = Y

frame_advance = Y - X

All subsequent frames:
  next_position = current_position + frame_advance
```

## Fine-Tuning Strategy

### When to Adjust
- After loading each new strip (minor variance in first frame position)
- If frames drift during a strip (mechanical slippage)
- When switching film carriers (different gap characteristics)

### How to Adjust
1. Turn off auto-advance: `A`
2. Use arrows for precise positioning
3. Capture when aligned: `SPACE`
4. Manually advance to next frame: `Shift+→`
5. Or turn auto-advance back on: `A`

## State Persistence

### Saved Data
- roll_name
- frame_count (total frames captured)
- strip_count (current strip number)
- frames_in_strip (frames in current strip)
- frame_advance (calibrated spacing)
- frame_positions[] (position of each captured frame)
- mode (manual/calibrated)
- auto_advance (ON/OFF)

### File Location
```
~/scans/YYYY-MM-DD/roll_name/.scan_state.json
```

### Resume Capability
- Can resume mid-roll if interrupted
- Maintains calibration data
- Tracks strip and frame counts

## Best Practices

1. **Always calibrate Strip 1 carefully**
   - This sets spacing for entire roll
   - Take time to align frames 1 and 2 precisely

2. **Use auto-advance for efficiency**
   - Fastest workflow for consistent film
   - Turn off only when drift occurs

3. **Fine-tune as needed**
   - Minor adjustments are normal
   - Don't recalibrate unless major issue

4. **Monitor first frame of each strip**
   - Most variance occurs here
   - Subsequent frames typically track well

5. **Shift+arrows for recovery**
   - If you overshoot, use Shift+← to backup
   - Better than manual re-positioning

## Troubleshooting

### Frames drifting progressively
- Check mechanical connection
- Verify no film slippage
- May need to recalibrate if severe

### First frame of new strip misaligned
- Normal - use arrows to align
- Do NOT recalibrate
- Subsequent frames should track

### Auto-advance overshoots/undershoots
- Minor variance is normal
- Use arrows to fine-tune before capture
- Consider recalibrating if consistently off

### Lost calibration
- Restart roll with `N` if needed
- Or manually set mode to manual: `M`
- Recalibrate with `C`

## Technical Notes

### Motor Steps
- fine_step: 8 steps
- coarse_step: 64 steps
- default_advance: 1200 steps (35mm estimate)
- Actual advance learned from calibration

### Timing
- step_delay: 800 microseconds between motor steps
- Auto-advance includes 0.5s settle time
- Camera operations timeout at 20s

### Camera Capture
- Images saved to camera SD card only
- Format: RAW (CR3/NEF/ARW depending on camera)
- Autofocus triggered before each capture
- Camera connection checked every 5 seconds
