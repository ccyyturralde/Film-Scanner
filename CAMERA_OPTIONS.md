# Camera Control Options for Film Scanner

## ⭐ NEW: Remote Camera Server (Recommended)

The Film Scanner now supports **remote camera control** - your camera can be connected to ANY computer on your network, not just the Raspberry Pi!

### What You Get:
- ✅ **Camera on any computer** - Windows, Mac, or Linux
- ✅ **Excellent live view** - Use Canon EOS Utility (~10 FPS)
- ✅ **Simple HTTP server** - Just run one Python script
- ✅ **gphoto2 control** - Reliable autofocus and capture
- ✅ **Open source** - No proprietary SDKs required
- ✅ **Flexible setup** - Camera doesn't need to be near Pi

### How It Works:
```
Your Computer (Camera plugged in here)
├── Camera Server (Python script)
├── Canon EOS Utility (for live view)
└── gphoto2 (for control)
        ↕ HTTP over WiFi
Raspberry Pi (Motor control + Web interface)
```

**See:** [REMOTE_CAMERA_SETUP.md](REMOTE_CAMERA_SETUP.md) for complete setup guide

---

## Current Status: Two Camera Modes

This project is **open-source** and **accessible** - no proprietary dependencies required!

### Mode 1: Remote Camera (NEW - Recommended ⭐)
- ✅ **Camera server on any computer** - Windows/Mac/Linux supported
- ✅ **Excellent live view** - EOS Utility integration (~10 FPS)
- ✅ **gphoto2 control** - Autofocus and capture
- ✅ **Network-based** - Camera anywhere on your network

### Mode 2: Local USB (Traditional)
- ✅ **Direct Pi connection** - Camera plugged into Raspberry Pi
- ✅ **gphoto2 control** - Autofocus and capture  
- ❌ **No live view** - Use camera's screen
- ✅ **Simple setup** - Just USB cable

---

## Why Remote Camera Server?

**Solves Previous Limitations:**

❌ **Old Problem:** Canon WiFi/CCAPI required proprietary SDK  
✅ **New Solution:** Open-source HTTP server, no SDK needed

❌ **Old Problem:** gphoto2 live view too slow (1 FPS)  
✅ **New Solution:** Use EOS Utility on user's computer (~10 FPS)

❌ **Old Problem:** HDMI capture requires extra hardware  
✅ **New Solution:** Software-only, leverage existing EOS Utility

❌ **Old Problem:** Camera must be near Pi (USB cable length)  
✅ **New Solution:** Camera anywhere on network

**Bonus:** Works on Windows/Mac where EOS Utility is available!

---

## Quick Start: Remote Camera Server

### 5-Minute Setup:

1. **On your computer** (where camera is):
   ```bash
   cd Film-Scanner
   pip3 install Flask Flask-CORS
   python3 camera_server.py
   ```

2. **Note the URL** shown (e.g., `http://192.168.1.100:8888`)

3. **In Film Scanner web interface**:
   - Enter that URL in Camera Settings
   - Click "Connect to Remote Camera"
   - Done!

4. **(Optional) For best live view**:
   - Install Canon EOS Utility
   - Open it before starting camera server
   - Enjoy ~10 FPS smooth preview

**Full Guide:** [REMOTE_CAMERA_SETUP.md](REMOTE_CAMERA_SETUP.md)

---

## Comparison Table

| Feature | Remote Camera | Local USB |
|---------|--------------|-----------|
| Camera location | Any computer on network | Must be on Pi |
| Live view | ✅ Excellent (~10 FPS via EOS Utility) | ❌ None |
| Setup | Medium (one-time) | Easy |
| OS Support | Windows/Mac/Linux | Linux only |
| Extra software | Python + gphoto2 | gphoto2 only |
| USB cable limit | No limit (wireless) | ~15 feet |
| Best for | EOS Utility users, live view needs | Simple setups, direct control |

---

## Alternative: HDMI Capture Card (Not Implemented)

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

