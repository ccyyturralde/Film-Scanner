# Film Scanner Setup Guide

## Installation Steps for Windows

### 1. Install Python Dependencies

First, install the required Python packages:

```bash
pip install -r requirements-desktop.txt
```

### 2. No Additional Camera Libraries Needed!

The app uses **Qt's built-in camera framework** which works natively on Windows with any USB camera. No additional installations required!

**What this means:**
- ✅ Works with Canon, Nikon, Sony, any brand
- ✅ No SDK registration needed
- ✅ No complex driver installation
- ✅ Native Windows support

### 3. Camera Setup

1. **Connect your DSLR via USB**
2. **Enable "PC Connection" or "USB Video" mode** on your camera:
   - Canon: Set to "Movie" mode or enable "USB Video Out"
   - Nikon: Enable "USB Video Mode"
   - Sony: Set to "PC Remote" or "MTP"
3. **The app will detect your camera** automatically
   - If not detected, click the 🔄 refresh button
   - Try different USB ports/cables if needed

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

2. **Select Camera**
   - Choose your camera from the dropdown
   - Click "Start Live View" button
   - You'll see real-time preview from your camera

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
     - **Capture** the image from live view
     - **Advance** to next frame
   - All in ONE button press!
   - **Note**: Focus manually using your camera or live view before capturing

6. **New Strips**
   - When strip is complete, press S for next strip
   - Manually feed new strip and position first frame
   - Press SPACE to continue scanning

## Keyboard Shortcuts

- **SPACE**: Capture → Advance (all in one!)
- **← / →**: Fine adjustment (left/right)
- **Shift+← / →**: Full frame back/forward
- **C**: Calibrate frame spacing
- **S**: Start new strip
- **N**: New roll
- **Z**: Zero position

## Features

### Live View Preview
- Real-time camera preview directly in the app
- Works with any USB camera on Windows
- Perfect for composing and focusing
- **Tip**: Adjust camera settings (exposure, white balance) using your camera's controls

### Single-Button Scanning
- Press SPACE once and the app handles:
  1. Capture from live view
  2. Advance to next frame
- No need to switch between apps or click multiple buttons
- Focus manually for best results

### Automatic Frame Spacing
- Calibrate once per session
- App automatically advances the correct distance
- Manual fine-tuning always available with arrow keys

## Troubleshooting

### Camera Not Detected
- Make sure camera is in USB Video/PC Connection mode
- Try different USB port or cable
- Click the 🔄 refresh button
- Restart the app
- Check Windows Camera app to see if camera works there

### Live View Not Working
- Ensure camera is in the correct USB mode (not just charging mode)
- Some cameras need to be in "Movie" mode
- Try restarting both camera and app
- Check camera battery level

### Image Quality Issues
- Camera captures at whatever resolution/quality it's set to in USB mode
- For best quality: Use camera's own shutter button and monitor for new files
- Or: Use a higher-end camera with better USB video quality

### Arduino Not Found
- Check USB connection
- Ensure Arduino sketch is uploaded
- Try a different USB port
- Check Device Manager for COM port

### Alternative: External Camera Control
If you prefer higher quality images:
1. Keep live view running for positioning
2. Trigger capture on your camera directly
3. App will detect and auto-advance
4. Or simply press SPACE to manually advance after each shot

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

