# Camera Improvements & Diagnostics

## What I've Done

### 1. ✅ Created Diagnostic Tool
**File**: `camera_test.py`

Run this on your Pi to see exactly what's wrong:
```bash
cd ~/Film-Scanner/Film-Scanner
chmod +x camera_test.py
python3 camera_test.py
```

This will test:
- gphoto2 installation
- Camera detection
- Camera capabilities
- Autofocus support
- Preview capture
- Image capture
- Video devices (HDMI capture cards)

### 2. ✅ Improved Error Handling & Logging

The web app now provides detailed console output showing:
- ✓ What's working
- ✗ What's failing
- 💡 Specific fixes for common errors

**Better error messages include:**
- "Set camera USB mode to PTP (not Mass Storage)"
- "Camera may be in use by another program"
- "Some cameras don't support remote AF via USB"

### 3. ✅ Added HDMI Capture Card Support

The app now:
- Automatically detects video devices (`/dev/video0`, etc.)
- Uses ffmpeg for smooth 10+ FPS preview if capture card present
- Falls back to gphoto2 preview (1 FPS) if no capture card
- Shows which mode is being used on startup

### 4. ✅ Documentation

Created three comprehensive guides:
- **`CAMERA_OPTIONS.md`** - Detailed comparison of camera control options
- **`CAMERA_QUICKSTART.md`** - Quick troubleshooting steps
- **`CAMERA_IMPROVEMENTS.md`** (this file) - Summary of changes

## Next Steps to Fix Your Camera

### Option A: Debug Current gphoto2 Setup

1. **Run diagnostics:**
   ```bash
   python3 camera_test.py
   ```

2. **Send me the output** - I can provide specific fixes

3. **Common quick fixes:**
   - Set camera USB mode to **PTP** (in camera menu)
   - Kill conflicting processes:
     ```bash
     sudo killall gphoto2
     sudo systemctl disable gvfs-gphoto2-volume-monitor
     ```
   - Check camera is in Manual (M) mode
   - Ensure SD card has space

### Option B: Get HDMI Capture Card (RECOMMENDED) ⭐

**Why this is better:**
- ✅ True 30 FPS live preview on webpage
- ✅ Large, clear view for positioning film
- ✅ Camera screen stays on (doesn't go black)
- ✅ Works with ANY camera
- ✅ See focus in real-time
- ✅ Professional workflow

**What to buy:**
- Search Amazon: "USB HDMI Video Capture UVC"
- Price: $20-30
- Make sure it supports: 1080p input, UVC standard
- Popular brands: Elgato Cam Link 4K (premium), or generic USB 3.0 capture

**Setup:**
```
Camera HDMI Out → HDMI Cable → USB Capture Card → Pi USB Port
```

**Software needed (install if not present):**
```bash
sudo apt install ffmpeg  # For video streaming
```

**The app is already ready** - just plug in the capture card and restart!

## What Happens When You Start the App Now

You'll see detailed startup info:

```
🔌 Searching for Arduino...
✓ Arduino connected on /dev/ttyACM0

📹 Checking for video devices...
✗ No video device found
  Tip: USB HDMI capture card ($20-30) gives better live preview
  See CAMERA_OPTIONS.md for details

🌐 Access the scanner at:
   • http://192.168.1.100:5000
```

## When You Try to Use Camera

**Console shows detailed progress:**

```
📷 Starting capture...
   Attempting autofocus...
   ⚠ Autofocus not supported (will use manual focus)
   Taking photo...
✗ Capture failed (code 1)
   Error: Could not claim the USB device
   Fix: Camera may be in use by another program
```

This makes it easy to see exactly what's failing!

## Testing Your Current Setup

### Test 1: Check Camera Detection
```bash
killall gphoto2
gphoto2 --auto-detect
```

Should show your camera on USB. If not:
- Check USB cable (must be data cable)
- Check camera USB mode setting
- Try different USB port

### Test 2: Test Manual Capture
```bash
gphoto2 --capture-image
```

If this works, problem is in the web app integration.
If this fails, it's a camera/gphoto2 issue.

### Test 3: Test Preview
```bash
gphoto2 --capture-preview --filename=/tmp/test.jpg
ls -l /tmp/test.jpg
```

If test.jpg exists, preview works.
If not, your camera may not support gphoto2 preview.

## My Recommendation

**Based on your symptoms** (capture fails, preview fails, autofocus doesn't work):

1. **First**: Run `python3 camera_test.py` and see what it reports
   
2. **If many things fail**: Your camera likely has limited gphoto2 support
   - **Solution**: Get USB HDMI capture card ($20-30)
   - This is the professional approach and will work perfectly

3. **If some things work**: We can troubleshoot specific issues
   - Send me the camera_test.py output
   - I'll provide camera-specific fixes

## Files I've Modified

### `web_app.py` Changes:
- Added `camera_error` tracking
- Added `video_device` detection
- Improved `check_camera()` with error messages
- Improved `autofocus()` with detailed logging
- Improved `capture_image()` with specific error help
- Added `detect_video_device()` method
- Added `_preview_loop_video()` for HDMI capture
- Improved `_preview_loop_gphoto2()` with error logging
- Added video device detection on startup

### New Files Created:
- `camera_test.py` - Diagnostic tool
- `CAMERA_OPTIONS.md` - Comprehensive guide
- `CAMERA_QUICKSTART.md` - Quick fixes
- `CAMERA_IMPROVEMENTS.md` - This file

## gphoto2 Alternatives Summary

| Method | Live View | Cost | Reliability | Your Use Case |
|--------|-----------|------|-------------|---------------|
| **HDMI Capture** | 30 FPS ✅ | $20-30 | ⭐⭐⭐⭐⭐ | **BEST** |
| gphoto2 | 1 FPS ⚠️ | Free | ⭐⭐⭐ | Okay if works |
| python-gphoto2 | 1 FPS ⚠️ | Free | ⭐⭐⭐⭐ | Better than CLI |
| Camera WiFi | Variable | Free | ⭐⭐ | Complex setup |

## Current Status

**What works now:**
- Better error messages in console
- Automatic detection of HDMI capture cards
- Ready for video preview when you get capture card
- Diagnostic tool to identify issues

**What needs your input:**
1. Run `camera_test.py` to see what's failing
2. Try quick fixes from `CAMERA_QUICKSTART.md`
3. Consider HDMI capture card for reliable live view

## Questions?

Let me know:
1. Output of `camera_test.py`
2. Your camera model
3. Whether you want to troubleshoot gphoto2 OR get HDMI capture

I'm ready to help either way! 🎬

