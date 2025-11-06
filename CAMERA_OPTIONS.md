# Camera Control Options for Film Scanner

## ⭐ NEW: WebUSB Camera Control (Recommended)

The Film Scanner uses **WebUSB** technology to control your camera directly from the web browser - **no apps**, **no servers**, just open the webpage!

### What You Get:
- ✅ **No apps to install** - Everything in the browser!
- ✅ **Click "Connect Camera"** - That's it!
- ✅ **Excellent live view** - Share EOS Utility window (~10 FPS)
- ✅ **Direct USB control** - Autofocus and capture via PTP
- ✅ **Open source** - No proprietary SDKs
- ✅ **Simple** - Plug camera, open webpage, done

### How It Works:
```
Your Computer (viewing the webpage)
├── Browser (Chrome/Edge)
│   ├── WebUSB API (talks to camera via USB)
│   └── Screen Capture API (shares EOS Utility window)
└── Canon Camera (plugged into YOUR computer, not Pi!)
        ↕ WebSocket to Pi
Raspberry Pi (Motor control only)
```

**See:** [WEBUSB_CAMERA_GUIDE.md](WEBUSB_CAMERA_GUIDE.md) for complete guide

---

## Current Status: Simple Browser-Based Control

This project is **open-source** and **accessible** - no proprietary dependencies!

### WebUSB Mode (Current Implementation)
- ✅ **Browser-only** - No apps to install!
- ✅ **Direct USB control** - Camera plugged into YOUR computer
- ✅ **Excellent live view** - Share EOS Utility window (~10 FPS)
- ✅ **PTP protocol** - Standard camera control
- ✅ **Works on** - Windows/Mac/Linux (Chrome/Edge)
- ✅ **One-time authorization** - Browser remembers your camera

---

## Why WebUSB?

**Solves Previous Limitations:**

❌ **Old Problem:** Canon WiFi/CCAPI required proprietary SDK  
✅ **New Solution:** WebUSB uses standard PTP, no SDK needed

❌ **Old Problem:** gphoto2 live view too slow (1 FPS)  
✅ **New Solution:** Share EOS Utility window (~10 FPS)

❌ **Old Problem:** HDMI capture requires extra hardware  
✅ **New Solution:** Software-only browser APIs

❌ **Old Problem:** Needed separate server/app  
✅ **New Solution:** Everything in browser, no apps!

❌ **Old Problem:** Camera must be near Pi  
✅ **New Solution:** Camera plugged into computer viewing webpage

**Bonus:** Works on Windows/Mac where EOS Utility is available!

---

## Quick Start: WebUSB Camera

### 2-Minute Setup:

1. **Plug camera into your computer** via USB

2. **Open webpage** in Chrome or Edge:
   - Navigate to: `http://scanner.local:5000`

3. **Click "Connect Camera"**:
   - Browser shows device picker
   - Select your Canon camera
   - Click "Connect"

✓ **Done!** No apps, no servers!

4. **(Optional) For live view**:
   - Open Canon EOS Utility
   - Start Remote Live View
   - Click "Start Live View" in webpage
   - Share EOS Utility window
   - Enjoy ~10 FPS preview

**Full Guide:** [WEBUSB_CAMERA_GUIDE.md](WEBUSB_CAMERA_GUIDE.md)

---

## Comparison Table

| Feature | WebUSB | Old Server | gphoto2 on Pi |
|---------|--------|------------|---------------|
| Apps needed | **None!** | Python script | gphoto2 |
| Setup time | **2 min** | 10 min | 5 min |
| Camera location | Your computer | Your computer | On Pi |
| Live view | ✅ Via EOS Utility | ✅ Via server | ❌ None |
| Browser | Chrome/Edge | Any | Any |
| Complexity | **Low** | Medium | Low |
| User experience | **Best** | Good | Basic |

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

