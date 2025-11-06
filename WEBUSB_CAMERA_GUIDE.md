# WebUSB Camera Control - User Guide

## 🎯 What is WebUSB Camera Control?

The Film Scanner uses **WebUSB** technology to control your Canon camera directly from your web browser - **no apps**, **no servers**, just open the webpage and connect!

---

## ✨ Benefits

- ✅ **No separate apps** - Everything in the browser
- ✅ **Simple setup** - Click "Connect Camera" and you're done
- ✅ **Direct control** - Autofocus and capture via USB
- ✅ **EOS Utility integration** - Share EOS Utility window for smooth live view
- ✅ **One-time authorization** - Browser remembers your camera
- ✅ **Open source** - No proprietary SDKs

---

## 📋 Requirements

### Browser:
- **Chrome** (v61+) ✅ Recommended
- **Edge** (v79+) ✅ Recommended
- **Opera** (v48+) ✅ Works
- **Firefox** ❌ Not supported (no WebUSB yet)
- **Safari** ❌ Not supported

### Camera:
- Canon DSLR or Mirrorless with USB connection
- Camera in **PTP mode** (not Mass Storage)
- USB data cable (not power-only)

### Optional (for best live view):
- Canon EOS Utility installed
- Same computer viewing the webpage

---

## 🚀 Quick Start (5 minutes)

### Step 1: Open the Web Interface

1. Open **Chrome** or **Edge** browser
2. Navigate to: `http://scanner.local:5000`
   - Or use your Pi's IP: `http://192.168.1.x:5000`

### Step 2: Connect Your Camera

1. **Plug in your Canon camera** via USB
2. **Turn camera on**
3. Set camera to **PTP mode**:
   - Canon: Menu → Settings → USB Connection → PTP
4. Click **"📷 Connect Camera"** button
5. Browser will show a popup with USB devices
6. **Select your Canon camera**
7. Click **"Connect"**

✓ **Done!** Camera is now connected.

### Step 3: Use Camera Controls

- Click **"🎯 Autofocus"** to focus
- Click **"📸 Capture Image"** to take photo
- Images save to camera SD card

### Step 4: (Optional) Add Live View

For smooth live view (~10 FPS):

1. **Install Canon EOS Utility** (free from Canon)
2. **Open EOS Utility**
3. **Start Remote Live View** in EOS Utility
4. In Film Scanner webpage:
   - Click **"📹 Start Live View"**
   - Select the **EOS Utility window** when prompted
   - Click **"Share"**

✓ **Done!** Live view appears in the webpage.

---

## 📖 Detailed Instructions

### First Time Setup

#### Browser Permissions

WebUSB requires **one-time permission** to access your camera:

1. Click "Connect Camera"
2. Browser shows: **"scanner.local wants to connect to a USB device"**
3. Select your Canon camera from the list
4. Click "Connect"

**Your browser remembers this!** Next time, camera reconnects automatically.

#### Camera USB Mode

Your camera must be in **PTP mode**:

**Canon Cameras:**
- Go to: `Menu → Settings → Communication → USB Connection`
- Select: `PTP` (not `Mass Storage` or `Print/PTP`)

**If you don't see PTP:**
- Check camera is in shooting mode (not playback)
- Try turning camera off and on
- Check USB cable is data cable (not power-only)

### Using Camera Controls

#### Autofocus
- Click "🎯 Autofocus" button
- Camera will focus (you'll hear it)
- Green notification: "✓ Autofocus triggered"

**If autofocus doesn't work:**
- Some cameras don't support remote AF
- Use manual focus or camera's AF button

#### Capture Image
- Click "📸 Capture Image" button
- Camera captures photo
- Image saves to camera SD card
- Green notification: "✓ Image captured"

**Tips:**
- Make sure SD card is in camera
- Check camera has space
- Camera battery should be charged

### Live View Setup

For the best live view experience:

#### Method 1: EOS Utility (Recommended)

**Why:** Smooth ~10 FPS, official Canon software

**Steps:**
1. **Download EOS Utility** from Canon's website
   - Free for all Canon camera owners
   - Available for Windows and macOS
   
2. **Install and launch** EOS Utility
   - Camera should be detected automatically
   
3. **Start Remote Live View**
   - Click "Remote Shooting" or "Remote Live View"
   - A window opens showing camera view
   
4. **Share window to webpage**
   - In Film Scanner, click "Start Live View"
   - Browser asks: "Share your screen"
   - Select "Window" tab
   - Choose **EOS Utility** window
   - Click "Share"

✓ Live view appears in webpage (~10 FPS)

#### Method 2: Without EOS Utility

If you don't have EOS Utility, you can:
- Use camera's built-in screen
- Position film manually
- Use autofocus before capture

---

## 🎬 Complete Workflow

### Typical Scanning Session:

1. **Connect Everything:**
   - Plug camera into computer via USB
   - Camera in PTP mode, turned on
   - Open Film Scanner in Chrome/Edge
   - Click "Connect Camera"

2. **Setup Live View (Optional):**
   - Open EOS Utility
   - Start Remote Live View
   - Share window to Film Scanner

3. **Scan Films:**
   - Position film using motor controls
   - View position in live view
   - Click "Autofocus"
   - Click "Capture"
   - Repeat for each frame

4. **Finish:**
   - Retrieve images from camera SD card
   - Disconnect camera when done

---

## 🔧 Troubleshooting

### Browser Issues

**"WebUSB Not Supported" warning**
- **Solution:** Use Chrome, Edge, or Opera
- Firefox and Safari don't support WebUSB yet

**"HTTPS Required" warning**
- **Solution:** Access via `localhost`, `.local` hostname, or use HTTPS
- WebUSB requires secure connection (except localhost)

### Connection Issues

**Camera not appearing in device list**
- Check USB cable is plugged in
- Camera is turned on
- Camera is in PTP mode (not Mass Storage)
- Try different USB port
- Close other apps using camera (like photo apps)

**"Failed to connect" error**
- Camera might be in use by another app
- Restart camera
- Restart browser
- Try unplugging and replugging USB

**Camera disconnects randomly**
- Check USB cable quality
- Camera may be going to sleep - disable auto-sleep
- Try different USB port
- Check camera battery level

### Autofocus/Capture Issues

**Autofocus doesn't work**
- Your camera may not support remote AF
- Use manual focus or camera's AF button
- Check camera is in appropriate mode (M, Av, Tv, etc.)

**Capture fails**
- Check SD card is in camera
- Check SD card has space
- Check camera battery level
- Camera mode might not allow capture
- Try capturing manually first to test

### Live View Issues

**Can't select EOS Utility window**
- Make sure EOS Utility is running
- Start Remote Live View in EOS Utility first
- Try refreshing webpage and trying again

**Live view is laggy**
- This is normal - browser capture is ~10 FPS
- Close other browser tabs
- Close other apps to free up resources

**Black screen**
- Reselect the EOS Utility window
- Make sure Remote Live View is active in EOS Utility
- Try stopping and restarting live view

---

## 💡 Tips & Best Practices

### For Best Experience:

1. **Use Chrome or Edge** - Best WebUSB support
2. **Use EOS Utility** - Much better than no live view
3. **Close other camera apps** - Prevent USB conflicts
4. **Disable camera sleep** - Prevents disconnections
5. **Use good USB cable** - Quality matters!
6. **Keep camera charged** - USB may not charge while connected

### Workflow Optimization:

1. **One-time setup:**
   - First connection authorizes camera
   - Browser remembers it
   - Future visits auto-reconnect

2. **Leave EOS Utility open:**
   - Faster to start live view
   - Just share window each session
   - Browser remembers window too!

3. **Dedicated browser:**
   - Use one browser tab for Film Scanner
   - Don't close it between scans
   - Camera stays connected

---

## 🔒 Privacy & Security

### What Data is Shared?

- **Nothing leaves your computer!**
- WebUSB communicates directly with camera
- No data sent to internet or servers
- All processing happens locally

### Browser Permissions

- **USB Access:** Only to Canon cameras you authorize
- **Screen Sharing:** Only EOS Utility window you select
- **You control everything:** Revoke anytime in browser settings

### Revoking Permissions

**To remove camera authorization:**

**Chrome/Edge:**
1. Click padlock icon in address bar
2. Click "Site settings"
3. Find "USB devices"
4. Click "Remove" next to your camera

---

## 📊 Technical Details

### How It Works

```
Your Computer:
Browser (Chrome/Edge)
  ↓ WebUSB API
USB Port
  ↓ USB Cable
Canon Camera
```

- **WebUSB:** Browser standard for USB device access
- **PTP Protocol:** Standard camera control protocol
- **JavaScript:** All code runs in browser
- **No server:** Direct browser-to-camera communication

### Supported Commands

Current implementation:
- ✅ Camera detection and connection
- ✅ Autofocus trigger
- ✅ Image capture (shutter release)
- ✅ Session management
- ✅ Device info

Future enhancements:
- ⏳ Live view via PTP (without EOS Utility)
- ⏳ Exposure settings control
- ⏳ Focus distance control
- ⏳ Image download from camera

### Performance

- **Connection time:** 2-3 seconds
- **Autofocus:** Instant command (camera speed varies)
- **Capture:** Instant command (camera speed varies)
- **Live view:** ~10 FPS (via EOS Utility window capture)

---

## 🆚 Comparison

| Feature | WebUSB | Old (Server) | gphoto2 USB |
|---------|--------|--------------|-------------|
| Setup | Browser only | Install Python server | gphoto2 on Pi |
| Apps needed | None | Python script | None |
| Live view | Via EOS Utility | Via server | Not available |
| Platform | Windows/Mac/Linux | Windows/Mac/Linux | Pi only |
| Complexity | Low | Medium | Low |
| User experience | Best | Good | Basic |

---

## ❓ FAQ

**Q: Do I need to run a server?**  
A: No! WebUSB runs entirely in your browser.

**Q: Will this work on my phone?**  
A: No, WebUSB is not supported on mobile browsers yet.

**Q: Can I use Firefox?**  
A: Not yet. Firefox doesn't support WebUSB. Use Chrome or Edge.

**Q: Does this work with all Canon cameras?**  
A: Most modern Canon DSLRs and mirrorless cameras work. Very old models may not.

**Q: Do I need EOS Utility?**  
A: No, but it provides excellent live view. Without it, you can still capture but no live preview.

**Q: Is this safe for my camera?**  
A: Yes! Uses standard PTP protocol that Canon officially supports.

**Q: Will my camera be drained?**  
A: USB connection uses power, but less than WiFi. Keep camera charged.

**Q: Can I download images via WebUSB?**  
A: Not yet implemented, but planned. For now, images stay on SD card.

**Q: What if I have multiple cameras?**  
A: Connect one at a time. Browser shows all connected cameras to choose from.

---

## 🐛 Known Issues

### Current Limitations:

1. **Browser support:** Chrome/Edge only (Firefox/Safari don't support WebUSB)
2. **Mobile:** Not available on phones/tablets
3. **Image download:** Can't download images from camera yet (use SD card)
4. **Live view:** Requires EOS Utility or manual positioning
5. **Camera settings:** Can't change exposure/ISO yet

### Planned Improvements:

- Direct PTP live view (no EOS Utility needed)
- Image download from camera
- Exposure control (ISO, shutter, aperture)
- Multi-camera support
- Focus distance control

---

## 📚 Additional Resources

- **WebUSB Specification:** https://wicg.github.io/webusb/
- **Canon EOS Utility:** Download from Canon support site
- **PTP Protocol:** Standard camera protocol (ISO 15740)

---

## 💬 Need Help?

If you're stuck:

1. Check this guide's Troubleshooting section
2. Check browser console (F12) for errors
3. Try different USB port/cable
4. Restart camera and browser
5. Create an issue on GitHub

---

**Enjoy your WebUSB camera control!** 📷

No apps, no servers, just browser magic! ✨

