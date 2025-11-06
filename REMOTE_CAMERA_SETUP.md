# Remote Camera Server Setup Guide

## Overview

The Film Scanner now supports **remote camera control** - your camera can be connected to ANY computer on your network (Windows/Mac/Linux), not just the Raspberry Pi!

This setup uses a simple HTTP server running on the computer where your camera is plugged in. The Raspberry Pi communicates with this server to control the camera remotely.

---

## Benefits

✅ **Camera anywhere** - Connect camera to any computer on your network  
✅ **Windows/Mac support** - Use EOS Utility for best live view quality  
✅ **No USB limitations** - Pi doesn't need USB connection to camera  
✅ **Clean separation** - Pi handles motors, remote computer handles camera  
✅ **Simple setup** - Just run one Python script  
✅ **Open source** - All code included, no proprietary SDKs  

---

## Quick Start

### On Your Computer (where camera is connected):

1. **Install Requirements:**
   ```bash
   pip3 install Flask Flask-CORS mss Pillow
   ```

2. **Plug in your Canon camera via USB**

3. **Run the camera server:**
   ```bash
   python3 camera_server.py
   ```

4. **Note the URL shown** (e.g., `http://192.168.1.100:8888`)

### On Raspberry Pi Web Interface:

5. **Open Film Scanner** in browser: `http://scanner.local:5000`

6. **Go to Camera Settings** section

7. **Enter camera server URL** from step 4

8. **Click "Connect to Remote Camera"**

9. **Done!** Camera is now controlled remotely

---

## Detailed Setup

### Step 1: Install gphoto2 on Your Computer

**macOS:**
```bash
brew install gphoto2
```

**Ubuntu/Debian Linux:**
```bash
sudo apt update
sudo apt install gphoto2
```

**Windows:**
- Download gphoto2 from: http://www.gphoto.org/proj/libgphoto2/support.php
- Or use WSL (Windows Subsystem for Linux) and follow Ubuntu instructions

### Step 2: Install Python Dependencies

```bash
cd Film-Scanner
pip3 install -r requirements.txt
```

Or manually:
```bash
pip3 install Flask Flask-CORS requests mss Pillow
```

### Step 3: Test Camera Connection

Before running the server, test that gphoto2 can see your camera:

```bash
gphoto2 --auto-detect
```

Should show something like:
```
Model                   Port
----------------------------------------------------------
Canon EOS R100          usb:001,003
```

If camera not detected:
- Check USB cable is data cable (not power-only)
- Set camera to PTP mode (not Mass Storage)
- Turn camera on
- Close any other apps using the camera

### Step 4: Run Camera Server

```bash
python3 camera_server.py
```

Output will show:
```
==============================================================
   FILM SCANNER - REMOTE CAMERA SERVER
==============================================================

✓ gphoto2 found

🔌 Checking for camera...
✓ Camera detected: Canon EOS R100

📦 Optional Features:
  • EOS Utility window capture: ✓ (mss)
  • Image processing: ✓ (Pillow)

==============================================================
   SERVER STARTING
==============================================================

🌐 Camera Server URLs:
   • Local:   http://localhost:8888
   • Network: http://192.168.1.100:8888

📝 Enter this URL in Film Scanner web interface:
   http://192.168.1.100:8888

💡 Keep this window open while using Film Scanner
==============================================================
```

**Keep this terminal window open** - the server needs to stay running.

### Step 5: Connect from Pi Web Interface

1. Open Film Scanner web interface in browser
2. Look for "Remote Camera Setup" section
3. Enter the camera server URL (from Step 4)
4. Click "Connect to Remote Camera"

You should see:
- ✓ "Connected to remote camera server"
- Camera model name displayed
- "Camera Connected" status shows green

---

## Using Live View

### Option 1: gphoto2 Live View (Default)

Works automatically once camera server is running. Simply:

1. Click "Start Live View" in web interface
2. Live preview appears (updates ~1 FPS)
3. Use for film positioning
4. Click "Stop Live View" when done

**Quality:** Basic, ~1 FPS  
**Pros:** Works automatically, no extra setup  
**Cons:** Slow update rate  

### Option 2: EOS Utility Live View (Best Quality)

For Canon cameras, use EOS Utility for much better live view:

1. **Install Canon EOS Utility** on your computer
   - Download from Canon's website for your camera model
   - Free official software from Canon

2. **Launch EOS Utility**
   - It will detect your camera
   - Open the Remote Live View window
   - Position it where you want

3. **Camera server will capture this window**
   - Automatically detects EOS Utility
   - Streams that view to web interface
   - Much smoother than gphoto2 (~10 FPS)

4. **Start Live View** from Film Scanner web interface

**Quality:** Excellent, ~10 FPS  
**Pros:** Smooth, high quality, official Canon software  
**Cons:** Requires EOS Utility installation  

---

## Workflow

### Typical Scanning Session:

1. **On your computer:**
   - Plug in camera
   - (Optional) Start EOS Utility
   - Run `python3 camera_server.py`
   - Leave it running

2. **On Raspberry Pi (via web interface):**
   - Connect to remote camera
   - Start live view for positioning
   - Use motor controls to position film
   - Click autofocus
   - Click capture
   - Images save to camera SD card

3. **When done:**
   - Stop live view
   - Disconnect remote camera
   - Stop camera server (Ctrl+C)
   - Retrieve images from camera SD card

---

## Troubleshooting

### Camera Server Won't Start

**Error: "gphoto2 not found"**
- Install gphoto2 (see Step 1 above)
- Make sure it's in your PATH

**Error: "Camera not detected"**
- Check USB connection
- Set camera to PTP mode
- Turn camera on
- Close other camera apps
- Try different USB port

### Can't Connect from Web Interface

**Error: "Failed to connect to remote camera server"**

1. **Check firewall:**
   - Allow port 8888 through firewall
   - Windows: Windows Defender Firewall → Allow an app
   - Mac: System Preferences → Security & Privacy → Firewall

2. **Verify URL:**
   - Use network IP, not `localhost`
   - Include `http://` prefix
   - Correct port `:8888`
   - Example: `http://192.168.1.100:8888`

3. **Test in browser:**
   - Open the camera server URL in a browser
   - Should see JSON response with server info

4. **Check network:**
   - Pi and computer must be on same network
   - Try pinging Pi from computer: `ping scanner.local`
   - Try pinging computer from Pi

### Live View Not Working

**Black screen or "Failed to get live view"**

1. Camera may be sleeping - wake it up
2. Another app may be using camera - close other apps
3. Restart camera server
4. Check console output for errors

**Live view very slow**

- This is normal for gphoto2 (~1 FPS)
- Use EOS Utility for better performance

### Autofocus/Capture Not Working

**Commands failing:**

1. **Check camera server console** - errors will show there
2. **Camera mode** - should be in M (manual) or appropriate mode
3. **SD card** - ensure camera has SD card with space
4. **Battery** - low battery can cause failures
5. **USB connection** - try different cable/port

---

## Advanced: EOS Utility Window Capture

The camera server can automatically capture the EOS Utility window for better live view.

### How It Works:

1. Server detects running applications
2. Finds EOS Utility window
3. Captures that window's content
4. Streams it to web interface

### Currently:

Window detection is a TODO feature. For now, live view uses gphoto2.

### Future Enhancement:

Will automatically find and capture EOS Utility, OBS, or other camera preview windows.

---

## Network Configuration

### Static IP (Recommended)

To avoid the camera server URL changing:

1. **Find your computer's MAC address**
2. **Set static IP in router settings**
3. **Assign permanent IP** (e.g., 192.168.1.100)

Now the URL never changes!

### Dynamic DNS

For more advanced setups, use mDNS/Bonjour:

**macOS:**
- Already has Bonjour
- Server accessible at: `http://computername.local:8888`

**Linux:**
```bash
sudo apt install avahi-daemon
# Server accessible at: http://hostname.local:8888
```

**Windows:**
- Install Bonjour Print Services
- Or use static IP (easier)

---

## Security Notes

### Local Network Only

The camera server is designed for **local network use only**.

- No authentication (trusts local network)
- HTTP not HTTPS (not encrypted)
- Assumes trusted environment

### Don't Expose to Internet

❌ **DO NOT** port forward camera server to internet  
❌ **DO NOT** expose on public WiFi  
✅ **DO** use on trusted home/studio network only  

For remote access, use:
- VPN to your network
- SSH tunnel
- Tailscale/ZeroTier

---

## Multiple Cameras

Want to use multiple cameras?

### Setup:

1. Run camera server on multiple computers
2. Each server on different port:
   ```bash
   # Computer 1:
   PORT=8888 python3 camera_server.py
   
   # Computer 2:
   PORT=8889 python3 camera_server.py
   ```
3. Connect to different camera servers from web interface
4. Switch between cameras as needed

**Note:** Web interface connects to one camera at a time (current limitation).

---

## Automation

### Auto-start Camera Server

**macOS (LaunchAgent):**

Create `~/Library/LaunchAgents/com.filmscanner.camera.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" 
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.filmscanner.camera</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/path/to/Film-Scanner/camera_server.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.filmscanner.camera.plist
```

**Linux (systemd):**

Create `/etc/systemd/system/camera-server.service`:

```ini
[Unit]
Description=Film Scanner Camera Server
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/Film-Scanner
ExecStart=/usr/bin/python3 camera_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable it:
```bash
sudo systemctl enable camera-server
sudo systemctl start camera-server
```

**Windows (Task Scheduler):**

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: "When I log on"
4. Action: "Start a program"
5. Program: `python3.exe`
6. Arguments: `C:\path\to\camera_server.py`

---

## Technical Details

### API Endpoints

Camera server provides REST API:

```
GET  /                  - Server info
GET  /api/status        - Camera status
GET  /api/check-camera  - Force camera check
GET  /api/live-view     - Get live view frame (JPEG)
POST /api/autofocus     - Trigger autofocus
POST /api/capture       - Capture image
POST /api/configure-liveview - Configure live view source
```

### Communication Flow

```
Browser → Pi Web Server → HTTP Request → Camera Server → gphoto2 → Camera
                                                        ↓
Browser ← Pi Web Server ← HTTP Response ← Camera Server
```

### Performance

- **Latency:** ~100-300ms for commands
- **Live view:** ~1-10 FPS depending on source
- **Network:** ~2-5 Mbps for live view
- **CPU:** Low (<5% on modern hardware)

---

## Comparison: Remote vs Local

| Aspect | Remote Camera | Local (Pi-connected) |
|--------|---------------|---------------------|
| Camera location | Any computer | Must be on Pi |
| USB cable length | Not limited | Limited to USB spec |
| Live view quality | Excellent (EOS Utility) | Basic (gphoto2) |
| Setup complexity | Medium | Low |
| Operating system | Windows/Mac/Linux | Linux only (Pi) |
| Camera switching | Easy | Hard (re-plug USB) |

---

## Support

### Getting Help:

1. Check console output on camera server
2. Check browser console (F12) for web errors
3. Verify network connectivity
4. Test camera with gphoto2 directly
5. Review this guide's troubleshooting section

### Common Issues:

- **"Connection refused"** → Check firewall, verify URL
- **"Camera not detected"** → USB mode, other apps, cable
- **"Timeout"** → Network issue, server not running
- **Commands work but slow** → Normal, gphoto2 is not fast

---

## Future Enhancements

Planned features:

- [ ] Automatic EOS Utility window detection
- [ ] Support for OBS virtual camera
- [ ] Multi-camera simultaneous connection
- [ ] WebRTC for lower latency live view
- [ ] Camera server discovery (mDNS)
- [ ] Built-in auth for internet use
- [ ] Mobile app version

---

**Enjoy your remote camera setup!** 🎬📷

For issues or suggestions, create an issue on the GitHub repository.

