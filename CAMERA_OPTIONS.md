# Camera Control Options for Film Scanner

## Current Issue: gphoto2 Limitations

**Problems you're experiencing:**
- Capture fails
- Autofocus doesn't work
- Preview doesn't show live view
- Camera screen goes black

**Why gphoto2 can be problematic:**
- Camera-specific support varies wildly
- Some camera models don't expose all features via USB
- Preview mode is slow and unreliable (1 FPS)
- Camera must be in specific USB mode (PTP/MTP)
- Conflicts with camera's own USB mass storage mode

## ⭐ RECOMMENDED SOLUTION: HDMI Capture Card

### What You Need:
**USB HDMI Capture Card** ($15-30 on Amazon)
- Look for: "USB HDMI Video Capture Card" or "USB HDMI Grabber"
- Must support: 1080p input, UVC (USB Video Class)
- Popular models:
  - Elgato Cam Link 4K (premium, $130)
  - Generic USB 3.0 HDMI capture (~$20-30)
  - Mirabox/LEADEDSE/GUERMOK brands work well

### How It Works:
```
Camera HDMI Out → HDMI Cable → USB Capture Card → Raspberry Pi USB
                                                      ↓
                                            Shows up as /dev/video0
                                                      ↓
                                            Stream to web browser
```

### Benefits:
- ✅ **True live preview** - See exactly what camera sees in real-time
- ✅ **30 FPS smooth video** - Not choppy like gphoto2 preview
- ✅ **Camera screen stays on** - HDMI output keeps camera awake
- ✅ **No USB conflicts** - gphoto2 only used for triggering shutter
- ✅ **Works with ANY camera** - Even point-and-shoots with HDMI out
- ✅ **Better focusing** - See live image while focusing
- ✅ **Professional workflow** - Same as studio setups

### Setup Steps:

1. **Buy capture card** (~$20-30)
   
2. **Connect hardware:**
   ```
   Camera → Mini HDMI to HDMI cable → Capture card → USB to Pi
   ```

3. **Test device shows up:**
   ```bash
   ls -l /dev/video*
   # Should see /dev/video0 or similar
   
   v4l2-ctl --device=/dev/video0 --info
   # Should show capture card info
   ```

4. **Install streaming software:**
   ```bash
   sudo apt install mjpg-streamer
   # OR
   sudo apt install ffmpeg
   ```

5. **I'll update the web app** to use the video device for preview!

### Cost vs Benefit:
- **Cost**: $20-30 for capture card
- **Benefit**: Professional live view, reliable operation, works with any camera
- **ROI**: Saves hours of frustration, makes scanning much faster

---

## Alternative 1: Fix gphoto2 Issues

If you want to stick with gphoto2, try these fixes:

### Step 1: Run Diagnostics
```bash
cd Film-Scanner
chmod +x camera_test.py
python3 camera_test.py
```

This will show exactly what's failing.

### Step 2: Common Fixes

**Camera Not Capturing:**
1. Check camera USB mode:
   - Should be in "PTP" or "PC Connect" mode
   - NOT in "Mass Storage" or "Charge Only"
   - Check camera menu: USB Connection → PTP

2. Check USB cable:
   - Must be data cable (not power-only)
   - Try different USB port on Pi

3. Camera settings:
   - Turn off auto-sleep
   - Set to Manual (M) mode
   - Ensure SD card is inserted and has space

**Autofocus Not Working:**
```bash
# Test if camera supports remote autofocus
gphoto2 --list-config | grep -i focus

# If "autofocus" appears, test with:
gphoto2 --set-config autofocus=1
```

Some cameras don't support remote AF via USB. You'll need to:
- Use camera's manual focus
- Or use half-press shutter before capture
- Or use HDMI capture (shows live view for manual focusing)

**Preview Fails:**
```bash
# Test preview directly
gphoto2 --capture-preview --filename=/tmp/test.jpg
ls -l /tmp/test.jpg

# If this works, issue is in web app
# If this fails, camera doesn't support preview mode well
```

### Step 3: Camera-Specific Workarounds

**Canon Cameras:**
- May need to be in "Movie Mode" for live view
- Some models require: `gphoto2 --set-config viewfinder=1` first

**Nikon Cameras:**
- Often don't support remote autofocus
- Live view may require: `gphoto2 --set-config liveview=1`

**Sony Cameras:**
- Often require "PC Remote" mode
- May need "USB LUN Setting" → "Single"

---

## Alternative 2: Python gphoto2 Library

More direct control than command-line gphoto2:

```bash
sudo apt install libgphoto2-dev
pip3 install gphoto2
```

Better error handling and more reliable, but still camera-dependent.

---

## Alternative 3: Camera WiFi/Network API

Some modern cameras have WiFi and HTTP APIs:

**Canon**: Canon Camera Connect SDK
**Nikon**: Nikon SDK / SnapBridge
**Sony**: Sony Camera Remote API

Usually requires:
- Camera WiFi enabled
- Pi connected to camera's WiFi network
- HTTP requests for control

More complex setup, but can provide great live view.

---

## Alternative 4: Webcam Mode

Some modern cameras can act as webcams:

**Canon EOS Webcam Utility** (Windows/Mac only - doesn't help Pi)
**Sony Imaging Edge Webcam** (Windows/Mac only)

Generally not available for Linux/Pi.

---

## My Recommendation

**FOR FILM SCANNING: Use HDMI Capture Card**

Here's why this is the BEST solution for your use case:

1. **You need reliable live view** - Critical for film scanning to see exact frame position
2. **Camera screen going black is annoying** - HDMI keeps it alive
3. **Small camera screen** - You mentioned this is an issue
4. **Works with any camera** - Future-proof if you upgrade
5. **Professional approach** - This is how studios do tethered shooting
6. **Cheap** - $20-30 is worth the reliability

### Next Steps If You Go HDMI Route:

1. **Order a USB HDMI capture card**
   - Search Amazon: "USB HDMI Video Capture UVC"
   - Get one that supports 1080p and UVC (most do)

2. **When it arrives, let me know** and I'll:
   - Update web app to detect video device
   - Add mjpeg streaming for smooth live preview
   - Keep gphoto2 for shutter trigger only
   - Add focus peaking indicators
   - Add zoom controls for precise framing

3. **Result**: 
   - Smooth 30 FPS live preview on webpage
   - Large, clear view for positioning film
   - Reliable capture with gphoto2
   - Camera never sleeps

---

## Testing Your Current Setup

**Run the diagnostic script I just created:**

```bash
cd Film-Scanner
chmod +x camera_test.py
python3 camera_test.py
```

This will tell us:
- What camera model is detected
- What features it supports  
- If capture/preview/autofocus work via gphoto2
- What's specifically failing

**Send me the output** and I can help troubleshoot OR confirm that HDMI capture is the way to go.

---

## Summary Table

| Method | Live View | Capture | AF | Cost | Reliability | Setup |
|--------|-----------|---------|----|----- |-------------|-------|
| **HDMI Capture** | ✅ 30 FPS | ✅ | ❌* | $20-30 | ⭐⭐⭐⭐⭐ | Easy |
| gphoto2 CLI | ⚠️ 1 FPS | ⚠️ | ⚠️ | $0 | ⭐⭐⭐ | Easy |
| python-gphoto2 | ⚠️ 1 FPS | ✅ | ⚠️ | $0 | ⭐⭐⭐⭐ | Medium |
| Camera WiFi | ✅ Good | ✅ | ✅ | $0 | ⭐⭐ | Hard |
| Webcam Mode | ✅ Good | ✅ | ✅ | $0 | ⭐ | Not for Pi |

*AF still done via gphoto2 or camera, but you can see focus clearly

---

## What I Can Do Right Now

1. **Create gphoto2 debugging fixes** - Based on diagnostic output
2. **Add HDMI capture support** - Ready for when you get the card
3. **Implement python-gphoto2** - More reliable than CLI
4. **Add manual focus aids** - Focus peaking, zoom, etc.

Let me know which direction you want to go!

