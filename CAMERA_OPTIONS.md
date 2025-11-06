# Camera Control Options for Film Scanner

## Current Status: Simple USB-only Setup

This project focuses on being an **open-source**, **accessible** solution for film scanning without proprietary dependencies or complex setup requirements.

### What's Supported:
- ✅ **gphoto2 USB Control** - Autofocus and capture via USB
- ✅ **Simple setup** - No WiFi complexity or proprietary SDKs
- ✅ **Works with most cameras** - Any camera supported by gphoto2

### What's Not Available:
- ❌ **Live view** - Removed due to complexity/reliability issues
- ❌ **Canon WiFi/CCAPI** - Requires proprietary SDK from Canon
- ❌ **HDMI capture** - Code removed to simplify codebase

---

## Why Keep It Simple?

**Canon WiFi/CCAPI Issues:**
- Requires applying for Canon's SDK and API kit
- Adds proprietary dependencies that conflict with open-source principles
- Complex setup process with multiple tools and configurations
- Not suitable for an accessible open-source project

**gphoto2 Live View Issues:**
- Very slow (1 FPS)
- Unreliable across different camera models
- Often conflicts with capture functionality

**HDMI Capture Issues:**
- Requires additional hardware ($20-30)
- Adds complexity to setup
- Not all cameras have HDMI output

---

## Alternative Solution 1: HDMI Capture Card

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

## Recommended Approach

### USB-Only with gphoto2

**This is the current supported solution:**

1. **Simple setup** - Just plug in USB cable
2. **Open source** - No proprietary dependencies
3. **Works with most cameras** - Any camera supported by gphoto2
4. **Reliable capture** - gphoto2 handles AF and capture
5. **No extra hardware** - $0 cost

**Limitations:**
- No live view (use camera's screen for framing)
- Requires camera to support remote control via USB
- Camera must be in PTP mode

### Optional: HDMI Capture Card (Future)

If you need live view and are willing to add hardware:

1. **True live view** - See what camera sees in real-time
2. **30 FPS smooth** - Professional monitoring
3. **Works with any camera** - Just needs HDMI output
4. **Affordable** - $20-30 one-time purchase

**Note**: HDMI capture support not currently in the codebase but could be added as a future enhancement if there's community interest.

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

| Method | Live View | Capture | AF | Cost | Reliability | Setup | Status |
|--------|-----------|---------|----|----- |-------------|-------|--------|
| **gphoto2 USB** | ❌ None | ✅ | ✅ | $0 | ⭐⭐⭐⭐ | Easy | ✅ Current |
| HDMI Capture | ✅ 30 FPS | ✅ | ⚠️* | $20-30 | ⭐⭐⭐⭐⭐ | Medium | ⚠️ Future |
| python-gphoto2 | ❌ None | ✅ | ⚠️ | $0 | ⭐⭐⭐⭐ | Medium | ⚠️ Alternative |

*AF via gphoto2, capture via gphoto2

---

## Philosophy

This project aims to be:
- ✅ **Open source** - No proprietary dependencies
- ✅ **Accessible** - Simple setup without complex requirements
- ✅ **Reliable** - Focus on what works consistently
- ✅ **Community-driven** - Built for and by the community

We avoid:
- ❌ Proprietary SDKs requiring applications/approvals
- ❌ Overly complex WiFi/network configurations
- ❌ Dependencies that limit accessibility

