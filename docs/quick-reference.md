# Film Scanner - Quick Reference

## Web Interface Controls

### Movement (Arrow Keys or Buttons)

| Control | Action |
|---------|--------|
| ← → | Fine position adjustment |
| Shift + ← → | Coarse position adjustment |
| Zero | Reset position counter |

### Capture

| Control | Action |
|---------|--------|
| SPACE or Capture button | Capture frame |
| P or Preview button | Get camera preview |
| Auto-advance toggle | Enable/disable automatic frame advance |

## Standard Workflow

1. **Create Roll**: Enter a name for your film roll
2. **Calibrate** (first strip only):
   - Position frame 1 using arrows
   - Click "Capture Frame 1"
   - Position frame 2 using arrows
   - Click "Capture Frame 2"
   - System learns frame spacing
3. **Scan**: Click CAPTURE for each frame
4. **New Strip**: Click "New Strip", position first frame, continue

## Status Display

```
Roll: [roll_name]
Frame: [count]
Strip: [strip_number]
Position: [steps]
Mode: MANUAL/CALIBRATED
Frame Advance: [steps]
Camera: Connected/Not connected
Arduino: Connected/Not connected
Auto-advance: ON/OFF
```

## Modes

### Manual Mode
- Full manual control
- Position each frame individually
- No automatic advancement

### Calibrated Mode
- Uses learned frame spacing
- Auto-advance moves to next frame after capture
- Fine adjustments still available

## Arduino Commands (Serial)

For direct serial testing via `screen /dev/ttyACM0 115200`:

| Command | Description |
|---------|-------------|
| f | Fine step forward |
| b | Fine step backward |
| F | Coarse step forward |
| B | Coarse step backward |
| N | Full frame advance |
| R | Full frame reverse |
| ? | Show status |
| Z | Zero position |
| E | Enable motor |
| M | Disable motor |

## File Locations

| Item | Location |
|------|----------|
| Images | Camera SD card (.CR3/.CR2) |
| Roll state | `~/scans/DATE/roll_name/.scan_state.json` |
| Config | `~/.film_scanner/scanner_config.json` |

## Quick Tips

1. **Drift correction**: Use fine arrows between frames
2. **Focus check**: Use Preview before capturing
3. **Problem frame**: Disable auto-advance, position manually
4. **Resume roll**: Enter same roll name, choose "Resume"

## Troubleshooting Quick Fixes

| Problem | Fix |
|---------|-----|
| Motor not responding | Click "Connect Arduino" button |
| Camera not found | Check USB, ensure PTP mode |
| Preview fails | Run `killall gphoto2` on Pi |
| Position wrong | Use fine arrows to adjust |
| Something broken | Run `python3 health_check.py` |

## Health Check & Auto-Repair

The `health_check.py` utility compares your installation against GitHub and fixes issues automatically:

```bash
# Full check and automatic repair
python3 health_check.py

# Check only (don't fix anything)
python3 health_check.py --check

# Verbose output (show all details)
python3 health_check.py --verbose
```

### What it checks:
- Git repository status (compares with GitHub)
- Core files (missing or corrupted)
- Deprecated files (old files that should be removed)
- Python dependencies (missing or outdated)
- System packages (gphoto2, etc.)
- Banned packages (eventlet - causes conflicts)
- Serial permissions (dialout group)
- Systemd services

### What it fixes:
- Pulls latest code from GitHub
- Removes deprecated files
- Installs/upgrades Python packages
- Uninstalls conflicting packages
- Adds user to dialout group
- Restarts systemd services
