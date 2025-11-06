# Quick Camera Testing Guide

## ✅ Ready to Test!

I've optimized the gphoto2 capture and autofocus implementation. Everything is ready.

## Quick Test Steps

### 1. Start the App

```bash
cd ~/Film-Scanner/Film-Scanner
python3 web_app.py
```

### 2. Open Web Interface

Go to: `http://your-pi-ip:5000`

### 3. Test Camera Capture

Click: **"🧪 Test Camera Capture"** button in System section

**This will:**
- Test if gphoto2 can capture from your camera
- Show detailed console output
- NOT affect frame count (it's just a test)
- Save photo to camera SD card

### 4. Watch Console

The terminal where you ran `python3 web_app.py` will show:

**✅ Success looks like:**
```
==========================================================
TEST CAPTURE (frame count will NOT be incremented)
==========================================================
📷 Starting capture sequence...
   [1/2] Attempting autofocus...
   ✓ Autofocus successful
   [2/2] Capturing image...
✓ Successfully captured frame #0
==========================================================
TEST RESULT: SUCCESS
==========================================================
```

**⚠️ Partial success (autofocus doesn't work but capture does):**
```
📷 Starting capture sequence...
   [1/2] Attempting autofocus...
   ⚠ Autofocus not available (continuing with current focus)
   [2/2] Capturing image...
✓ Successfully captured frame #0
```
**This is OK!** Many cameras don't support remote AF. Just use manual focus.

**❌ Failure looks like:**
```
✗ Capture failed (return code: 1)
   Error: Could not claim the USB device
   → Fix: Camera is locked by another process
   → Run: sudo killall gphoto2 gvfs-gphoto2-volume-monitor
```

## If Test Fails

### Quick Fixes to Try:

1. **Kill interfering processes:**
   ```bash
   sudo killall gphoto2
   sudo killall gvfs-gphoto2-volume-monitor
   ```

2. **Check camera USB mode:**
   - Camera Menu → Settings → USB
   - Set to: **PTP** (not Mass Storage)

3. **Check camera settings:**
   - Camera is powered on
   - Battery charged
   - SD card inserted with space
   - Camera in Manual (M) or Program (P) mode

4. **Restart and try again:**
   ```bash
   # Stop the web app (Ctrl+C)
   python3 web_app.py
   # Try test capture again
   ```

## What Gets Tested

✅ **Test Capture checks:**
- Camera USB connection
- gphoto2 can control camera
- Autofocus command (may not be supported - that's OK)
- Image capture command
- Camera SD card is writable

## After Testing

### If Test Capture Works:
🎉 **You're ready to scan!**
1. Create a new roll
2. Follow calibration workflow
3. Start scanning

### If Autofocus Fails but Capture Works:
✅ **Still ready to scan!**
- Use manual focus on camera lens
- Or use camera's autofocus button before capture
- Capture will work fine

### If Capture Fails:
📝 **Send me the console output showing:**
- The full error message
- Your camera model
- What you see on camera LCD

I'll provide specific fixes for your setup!

## Console Output to Watch

Every time you test or capture, you'll see detailed progress:

```
📷 Starting capture sequence...    ← Starting
   [1/2] Attempting autofocus...   ← Step 1
   ✓ Autofocus successful          ← AF worked
   [2/2] Capturing image...         ← Step 2  
✓ Successfully captured frame #1   ← Success!
```

This helps debug any issues immediately.

## Advanced: Manual Test

If you want to test gphoto2 directly:

```bash
# Kill any processes
sudo killall gphoto2

# Detect camera
gphoto2 --auto-detect

# Test autofocus (may fail - that's OK)
gphoto2 --set-config autofocus=1

# Test capture
gphoto2 --capture-image
```

If the last command works, camera capture works!

## Files Changed

All improvements are in the code, ready to use:
- Enhanced error handling
- Automatic retry on failures
- Better process management
- Detailed console logging
- Test capture feature

## Documentation

For more details, see:
- `GPHOTO2_IMPLEMENTATION.md` - Full technical details
- `CAMERA_OPTIONS.md` - Alternative approaches (HDMI capture)
- `camera_test.py` - Diagnostic script

## Ready!

**Just run the test capture and let me know the result!** 🚀

The console output will tell us exactly what's working and what's not.

