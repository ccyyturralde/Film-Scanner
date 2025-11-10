# Film Scanner Setup Guide

## Installation Steps for Windows

### 1. Install Python Dependencies

First, install the required Python packages:

```bash
pip install -r requirements-desktop.txt
```

### 2. Install libgphoto2 (for Camera Control)

For Windows, you need to install libgphoto2. Here are the options:

#### Option A: Using MSYS2 (Recommended)
1. Download and install MSYS2 from https://www.msys2.org/
2. Open MSYS2 terminal and run:
   ```bash
   pacman -S mingw-w64-x86_64-libgphoto2
   ```
3. Add MSYS2 bin directory to your PATH:
   - Add `C:\msys64\mingw64\bin` to your system PATH

#### Option B: Pre-built Windows Binaries
1. Download libgphoto2 Windows binaries from: http://www.gphoto.org/proj/libgphoto2/support.php
2. Extract and add to your PATH

### 3. Camera Setup

1. **Connect your Canon camera via USB**
2. **Set camera to PC/PTP mode** (check camera menu)
3. **Disable Canon software** that auto-launches when connecting camera
4. **Test camera detection**:
   ```bash
   gphoto2 --auto-detect
   ```
   You should see your camera listed.

### 4. Arduino Setup

1. Connect Arduino via USB
2. Upload the stepper motor control sketch
3. The app will auto-detect the Arduino on startup

## Usage

### Starting the App

```bash
python scanner_desktop.py
```

### Quick Start Workflow

1. **Connect Camera & Arduino**
   - Arduino status should show "Connected ✓"
   - Camera status should show "Connected ✓"

2. **Start Live View**
   - Click "Start Live View" button
   - Enable "Invert Colors (Show Positive)" to see film as positive image
   - This lets you preview exactly what you're scanning

3. **Create New Roll**
   - Enter roll name (e.g., "Kodak-Portra400-001")
   - Click "New Roll" (or press N)

4. **Calibrate Frame Spacing** (first strip only)
   - Press C to start calibration
   - Manually position frame 1 with arrow keys
   - Capture frame 1
   - Manually position frame 2 with arrow keys
   - Capture frame 2
   - System learns the spacing automatically

5. **Scan Remaining Frames**
   - Press SPACE for each frame
   - The app will automatically:
     - **Autofocus** the camera
     - **Capture** the image
     - **Advance** to next frame
   - All in ONE button press!

6. **New Strips**
   - When strip is complete, press S for next strip
   - Manually feed new strip and position first frame
   - Press SPACE to continue scanning

## Keyboard Shortcuts

- **SPACE**: Autofocus → Capture → Advance (all in one!)
- **← / →**: Fine adjustment (left/right)
- **Shift+← / →**: Full frame back/forward
- **C**: Calibrate frame spacing
- **S**: Start new strip
- **N**: New roll
- **Z**: Zero position

## Features

### Live View with Color Inversion
- Real-time camera preview directly in the app
- Toggle "Invert Colors" to see film negatives as positives
- Perfect for composing and focusing

### Single-Button Scanning
- Press SPACE once and the app handles:
  1. Autofocus
  2. Capture
  3. Advance to next frame
- No need to switch between apps or click multiple buttons

### Automatic Frame Spacing
- Calibrate once per session
- App automatically advances the correct distance
- Manual fine-tuning always available with arrow keys

## Troubleshooting

### Camera Not Detected
- Make sure camera is in PC/PTP mode
- Close any Canon software (EOS Utility, etc.)
- Try unplugging and reconnecting the camera
- Run `gphoto2 --auto-detect` to test

### Live View Not Working
- Some cameras require special settings
- Check camera manual for "PC Live View" settings
- Ensure camera is not in locked/standby mode

### Autofocus Fails
- Some cameras don't support autofocus via gphoto2
- You can still focus manually through live view
- The app will capture even if autofocus fails

### Arduino Not Found
- Check USB connection
- Ensure Arduino sketch is uploaded
- Try a different USB port
- Check Device Manager for COM port

### gphoto2 Import Error
If you see "gphoto2 not available", the app will still run but camera features will be disabled. Make sure to install libgphoto2 (see step 2 above).

## File Output

Scanned images are saved to:
```
~/scans/YYYY-MM-DD/RollName/RollName_frame_0001.jpg
```

## Tips

1. **Use Color Inversion**: Enable "Invert Colors" to see the positive image while scanning
2. **One-Press Workflow**: Just press SPACE repeatedly - the app does the rest
3. **Manual Adjustments**: You can still fine-tune position with arrow keys before pressing SPACE
4. **Live View Always On**: Keep live view running for immediate feedback

## Support

If you encounter issues:
1. Check that all dependencies are installed
2. Verify camera and Arduino connections
3. Check the Activity Log in the app for error messages
4. Test camera with `gphoto2 --auto-detect`

