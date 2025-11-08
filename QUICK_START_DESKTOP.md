# Quick Start - Desktop Version

Get scanning in 5 minutes! 🚀

## Prerequisites

- ✅ Windows 10/11 (or Mac/Linux)
- ✅ Python 3.9 or newer
- ✅ Arduino with film scanner firmware already flashed
- ✅ Canon DSLR camera

## Installation Steps

### 1. Install Python (if needed)

**Windows:**
```bash
# Download from python.org
# During install, CHECK "Add Python to PATH"
```

**Verify:**
```bash
python --version
# Should show Python 3.9 or higher
```

### 2. Install Dependencies

```bash
# Navigate to project folder
cd Film-Scanner

# Install required packages
pip install -r requirements-desktop.txt
```

Expected install time: 1-2 minutes

### 3. Connect Hardware

1. **Arduino** → USB port
2. **Camera** → USB port  
3. **Motor power** → 12V supply ON

### 4. Run Application

```bash
python scanner_desktop.py
```

**Expected behavior:**
- Window opens with "Film Scanner - Desktop Edition"
- Status shows "Arduino: Connected ✓" (after 2-3 seconds)
- If Arduino not found, check USB cable

## First Scan

### Step 1: Create Roll
1. Type roll name: `Test-Roll-001`
2. Click **"New Roll"** (or press `N`)

### Step 2: Load Film
1. Hand-feed strip 1 into scanner
2. Use **arrow keys** to position frame 1 perfectly

### Step 3: Calibrate (Captures Frames 1 & 2)
1. Click **"Calibrate"** (or press `C`)
2. Position frame 1 perfectly with arrow keys
3. Click OK to **CAPTURE frame 1**
4. Use **arrow keys** to move to frame 2
5. Click OK to **CAPTURE frame 2** - spacing is now learned!

**Result:** Frames 1 and 2 captured, spacing calculated!

### Step 4: Continue with Frames 3-6
1. Press **Space** to capture frame 3
2. Motor auto-advances to frame 4
3. Press **Space** to capture frame 4
4. Continue for frames 5-6
5. Fine-tune position with arrow keys before each capture if needed

### Step 5: New Strips
1. When strip complete, press **S** for new strip
2. Hand-feed next strip, position frame 1
3. Press **Space** to continue scanning

## Using Camera Preview

### With EOS Utility (Canon)
1. Click **"Launch EOS Utility"** button
2. Use EOS Utility for:
   - Live View
   - Focus
   - Camera settings
3. Return to scanner app to capture frames

### Without EOS Utility
- Camera will still capture to SD card
- Use camera's own LCD for preview

## Common First-Time Issues

### ❌ "Arduino not found"
**Fix:** 
- Check USB cable is data-capable (not charge-only)
- Try different USB port
- Verify Arduino firmware is flashed (should show "READY NEMA17" in serial monitor)

### ❌ Motor doesn't move
**Fix:**
- Verify 12V power supply is ON
- Check green LED on A4988 driver
- Common ground between Arduino GND and 12V GND

### ❌ EOS Utility button does nothing
**Fix:**
- Install Canon EOS Utility 3 from Canon website
- Or just launch EOS Utility manually before starting scanner app

### ❌ Arrow keys don't work
**Fix:**
- Click inside the application window to focus it
- Try clicking on the motor control area

## Keyboard Shortcuts Cheat Sheet

```
← →              Fine movement
Shift+← →        Frame jump
Space            Capture frame
C                Calibrate
S                New strip
N                New roll
Z                Zero position
```

## File Locations

**Session data:**
```
C:\Users\YourName\scans\2024-11-07\Test-Roll-001\
    └── .scan_state.json
```

**Camera images:**
```
Camera SD Card\DCIM\
    └── IMG_0001.CR3 (RAW files)
```

## Next Steps

✅ Scan complete? Transfer RAW files from camera SD card
✅ Want to resume? Create roll with same name, choose "Resume"
✅ Need help? Check README-DESKTOP.md or GitHub issues

---

**🎉 Happy Scanning!**

Having issues? The log area at bottom of app shows real-time diagnostic info.

