# Canon R100 WiFi Setup Guide

## Overview

The Film Scanner now supports **Canon R100 WiFi** for high-quality live view streaming! This guide will help you set up and use your Canon R100 with the scanner.

### What This Provides:
- ✅ **Smooth WiFi Live View** - Real-time preview from your Canon R100
- ✅ **Connection Monitoring** - Automatic disconnect detection and reconnection
- ✅ **Easy Setup** - Guided pairing process for Pi and camera
- ✅ **gphoto2 for Capture** - Autofocus and capture still use reliable gphoto2

### What Changed:
- ❌ **Removed gphoto2 Live View** - Old 1 FPS preview system completely removed
- ✅ **Canon WiFi ONLY for Live View** - Live view now requires Canon WiFi connection
- ✅ **gphoto2 for AF & Capture Only** - USB connection still used for autofocus and triggering

---

## Prerequisites

### Hardware Requirements:
1. **Canon R100 Camera** with WiFi enabled
2. **Raspberry Pi** (any model with WiFi)
3. **USB Cable** for camera (for gphoto2 autofocus/capture)
4. **WiFi Network** that both devices can connect to

### Software Requirements:
All dependencies are included in `requirements.txt`:
```bash
pip3 install -r requirements.txt
```

Key packages:
- `requests` - For Canon API communication
- `urllib3` - HTTP library for camera connection
- `Flask-SocketIO` - For live view streaming to web interface

---

## Setup Methods

You have **two options** for connecting your Canon R100:

### Option 1: Infrastructure Mode (Recommended)
Both Pi and camera connect to your **home WiFi network**.

**Pros:**
- ✅ Easy to set up
- ✅ Can access scanner from other devices on network
- ✅ Stable connection

**Cons:**
- ⚠️ Requires existing WiFi network

### Option 2: Camera Access Point Mode
Camera creates its own WiFi network, Pi connects to it.

**Pros:**
- ✅ Works without home WiFi
- ✅ Portable setup

**Cons:**
- ⚠️ Pi loses internet connection
- ⚠️ Can't access scanner from other devices easily
- ⚠️ More complex setup

---

## Quick Start Guide

### Step 1: Enable Camera WiFi

On your Canon R100:

1. Press **MENU** button
2. Navigate to: **Wireless Communication Settings** (wrench icon)
3. Select: **WiFi/Bluetooth Connection** → **Enable**
4. Choose connection mode:
   - **Infrastructure Mode**: Select **Connect to Network** and choose your WiFi
   - **AP Mode**: Select **Camera Access Point Mode**

### Step 2: Connect Pi to Same Network

**For Infrastructure Mode:**
- Pi should already be on your home WiFi
- No changes needed

**For AP Mode:**
1. On Pi, scan for WiFi networks:
   ```bash
   sudo iwlist wlan0 scan | grep ESSID
   ```
2. Connect to camera's network (usually named like "EOS R100"):
   ```bash
   sudo nmcli dev wifi connect "EOS_R100_XXXX" password "your_camera_password"
   ```

### Step 3: Run Setup Wizard

Two ways to set up:

#### Option A: During Initial Setup
When you first run the scanner:
```bash
python3 web_app.py
```

The setup wizard will ask if you want to configure a Canon WiFi camera. Answer **yes** and follow prompts.

#### Option B: Via Web Interface (After Setup)
1. Start the scanner:
   ```bash
   python3 web_app.py
   ```

2. Open web interface: `http://<pi_ip>:5000`

3. Click **"Setup Canon WiFi"** button

4. Choose:
   - **Auto-scan**: Automatically find camera on network (easiest)
   - **Manual IP**: Enter camera IP address if you know it

### Step 4: Test Connection

Once connected:
1. Click **"Start Live View"** button in web interface
2. You should see smooth real-time preview from camera
3. Battery level and connection status shown in interface

---

## Finding Your Camera's IP Address

If auto-scan doesn't work, manually find the IP:

### Method 1: Check Camera Menu
1. On Canon R100: **MENU** → **Wireless Settings** → **WiFi Details**
2. Note the IP address shown (e.g., `192.168.1.10`)

### Method 2: Check Router
1. Log into your WiFi router admin panel
2. Look for connected devices
3. Find device named "Canon" or "EOS R100"

### Method 3: Network Scan
On the Pi:
```bash
sudo nmap -sn 192.168.1.0/24
```
Look for Canon device in output.

---

## Usage Workflow

### Typical Scanning Session:

1. **Connect Hardware:**
   - Connect camera to Pi via USB (for gphoto2)
   - Ensure camera and Pi on same WiFi network

2. **Start Scanner:**
   ```bash
   cd Film-Scanner
   python3 web_app.py
   ```

3. **Connect Canon WiFi** (in web interface):
   - Click "Setup Canon WiFi" or "Connect Canon"
   - Auto-scan or enter IP
   - Wait for connection confirmation

4. **Start Live View:**
   - Click "Start Live View"
   - Position your film using the preview
   - Use fine/coarse controls to adjust

5. **Capture Frames:**
   - Click "Autofocus" (uses gphoto2 via USB)
   - Click "Capture" to take photo (via gphoto2)
   - Auto-advance to next frame (if calibrated)

6. **Connection Monitoring:**
   - System automatically monitors WiFi connection
   - If connection lost, notification appears
   - Click "Reconnect" to re-establish

### Important Notes:

- **Live View**: Canon WiFi ONLY
- **Autofocus**: gphoto2 via USB
- **Capture**: gphoto2 via USB
- **Both connections needed**: WiFi for preview, USB for control

---

## API Endpoints

### Setup & Connection

#### Setup Canon WiFi Camera
```http
POST /api/setup_canon_wifi
Content-Type: application/json

{
  "camera_ip": "192.168.1.10"  // Optional, auto-scans if omitted
}

Response:
{
  "success": true,
  "camera_model": "Canon EOS R100",
  "camera_ip": "192.168.1.10",
  "error": null
}
```

#### Scan for Canon Cameras
```http
POST /api/scan_canon_cameras

Response:
{
  "success": true,
  "camera_ip": "192.168.1.10"
}
```

#### Disconnect Canon WiFi
```http
POST /api/disconnect_canon

Response:
{
  "success": true
}
```

### Live View

#### Start Live View
```http
POST /api/start_liveview

Response:
{
  "success": true
}
```

#### Stop Live View
```http
POST /api/stop_liveview

Response:
{
  "success": true
}
```

### Status

#### Get Status
```http
GET /api/status

Response:
{
  "camera_type": "canon_wifi",
  "camera_connected": true,
  "camera_model": "Canon EOS R100",
  "liveview_active": true,
  "canon_wifi_ip": "192.168.1.10",
  "canon_battery": 85,
  ...
}
```

---

## Troubleshooting

### Camera Not Found During Scan

**Problem**: Auto-scan doesn't find camera

**Solutions:**
1. Check camera WiFi is enabled
2. Ensure Pi and camera on same network:
   ```bash
   # On Pi:
   ip addr show wlan0
   
   # Should be same subnet as camera (e.g., 192.168.1.x)
   ```
3. Try manual IP entry instead
4. Check firewall settings on Pi:
   ```bash
   sudo ufw status
   # If enabled, allow port 8080:
   sudo ufw allow 8080
   ```

### Connection Drops During Scanning

**Problem**: WiFi connection lost during use

**Solutions:**
1. Move camera and Pi closer together
2. Reduce WiFi interference (turn off other devices)
3. Use Infrastructure Mode instead of AP Mode
4. Check camera battery level (low battery can cause disconnects)
5. Increase reconnection attempts in `canon_wifi.py`:
   ```python
   # In _connection_monitor_loop:
   if consecutive_failures >= 5:  # Increase from 3 to 5
   ```

### Live View Not Starting

**Problem**: "Failed to start live view" error

**Solutions:**
1. Check camera is in correct mode:
   - Not in sleep mode
   - Lens cap removed
   - Mode dial on M, Av, Tv, or P
2. Restart camera WiFi:
   - On camera: Disable WiFi → Enable WiFi
3. Check Canon API is enabled on camera:
   - **MENU** → **Wireless** → **Remote Control** → **Enable**
4. Reconnect WiFi connection

### Autofocus/Capture Not Working

**Problem**: Can connect WiFi but can't capture

**Solutions:**
1. Check USB cable is connected
2. Verify gphoto2 can see camera:
   ```bash
   gphoto2 --auto-detect
   ```
3. Set camera to PTP mode:
   - **MENU** → **USB Connection** → **PTP**
4. Kill interfering processes:
   ```bash
   killall gphoto2 gvfs-gphoto2-volume-monitor
   ```

### Slow Live View Frame Rate

**Problem**: Live view is choppy or slow

**Solutions:**
1. Check WiFi signal strength
2. Reduce live view quality in `canon_wifi.py`:
   ```python
   # In start_liveview:
   json={"liveviewsize": "small"}  # Change from "medium" to "small"
   ```
3. Check Pi CPU usage:
   ```bash
   top
   # If high, close other programs
   ```
4. Use 5GHz WiFi instead of 2.4GHz if available

### IP Address Changes

**Problem**: Camera IP keeps changing between sessions

**Solutions:**
1. **Set Static IP on Router:**
   - Log into router admin
   - Find Canon device MAC address
   - Assign static/reserved IP

2. **Set Static IP on Camera** (if supported):
   - Check camera manual for static IP settings

3. **Use Auto-Scan Every Time:**
   - Don't rely on saved IP
   - Always scan on startup

---

## Advanced Configuration

### Custom Canon API Port

Default port is 8080. To change:

Edit `canon_wifi.py`:
```python
# In connect method:
self.api_base = f"http://{camera_ip}:8080/ccapi"  # Change 8080 to your port
```

### Adjust Connection Monitor Interval

Default checks every 5 seconds. To change:

Edit `canon_wifi.py`:
```python
# In _connection_monitor_loop:
time.sleep(5)  # Change 5 to desired seconds
```

### Change Live View Quality

Edit `canon_wifi.py`:
```python
# In start_liveview:
json={
    "liveviewsize": "medium"  # Options: "small" (512x384), "medium" (1024x768)
}
```

---

## Technical Details

### Canon Camera Control API (CCAPI)

The Canon R100 uses Canon's official CCAPI for WiFi control:
- **Protocol**: HTTP REST API
- **Port**: 8080 (default)
- **Endpoints**: `/ccapi/ver100/...`
- **Format**: JSON

### Communication Flow

```
Web Browser
    ↓ WebSocket
Flask-SocketIO Server
    ↓ Python
canon_wifi.py
    ↓ HTTP (CCAPI)
Canon R100 Camera (WiFi)

Separate USB Connection:
gphoto2 (USB) → Canon R100 → Autofocus/Capture
```

### Live View Streaming

1. **Request**: HTTP GET to `/ccapi/ver100/shooting/liveview/flip`
2. **Response**: Multipart JPEG stream or single JPEG
3. **Frame Rate**: ~10 FPS (configurable)
4. **Broadcast**: Base64 encoded JPEG via SocketIO to all web clients

### Connection Monitoring

- Background thread checks connection every 5 seconds
- Uses `/ccapi/ver100/deviceinformation` endpoint
- 3 consecutive failures = connection lost
- Triggers callback to update UI

---

## Comparison: Canon WiFi vs gphoto2 vs HDMI Capture

| Feature | Canon WiFi | gphoto2 USB | HDMI Capture |
|---------|------------|-------------|--------------|
| **Live View** | ✅ ~10 FPS smooth | ❌ Removed | ✅ 30 FPS smooth |
| **Autofocus** | ⚠️ Via gphoto2 | ✅ Yes | ❌ Manual |
| **Capture** | ⚠️ Via gphoto2 | ✅ Yes | ❌ Via gphoto2 |
| **Setup** | 🟡 Medium | ✅ Easy | 🔴 Hardware needed |
| **Cost** | $0 | $0 | $20-30 |
| **Reliability** | 🟡 WiFi dependent | ✅ Very good | ✅ Excellent |
| **Portability** | ✅ Wireless | 🟡 USB cable | 🔴 Extra hardware |

---

## FAQ

### Q: Can I use Canon WiFi without USB cable?
**A:** No. The USB connection is still needed for gphoto2 autofocus and capture. WiFi is ONLY for live view.

### Q: Does this work with other Canon cameras?
**A:** Potentially! Any Canon camera with CCAPI support should work. Test with your camera model.

### Q: Why not use gphoto2 for live view too?
**A:** gphoto2 live view is very slow (~1 FPS) and unreliable. Canon WiFi provides much better live view quality (10+ FPS).

### Q: What if my camera doesn't support WiFi?
**A:** You have two options:
1. Use an HDMI capture card (recommended - see `CAMERA_OPTIONS.md`)
2. No live view (use camera screen, manual positioning)

### Q: Can I switch between Canon WiFi and HDMI capture?
**A:** Not simultaneously. The system is now optimized for Canon WiFi live view only. For HDMI capture, see previous documentation.

### Q: Does this drain camera battery faster?
**A:** Yes, WiFi uses more power than USB alone. Keep camera plugged into AC adapter for long scanning sessions, or have spare batteries ready.

### Q: Can I use this with a phone/tablet?
**A:** Yes! The web interface works on any device with a browser. Connect to `http://<pi_ip>:5000` from your phone.

---

## Support & Development

### Files Modified:
- `canon_wifi.py` - New Canon WiFi camera control module
- `web_app.py` - Integrated Canon WiFi, removed old live view
- `config_manager.py` - Added Canon camera setup wizard
- `requirements.txt` - Added requests and urllib3

### Future Enhancements:
- [ ] Canon WiFi autofocus support (via CCAPI)
- [ ] Canon WiFi capture support (currently uses gphoto2)
- [ ] Multi-camera support
- [ ] Live histogram/focus peaking
- [ ] Saved camera profiles

### Reporting Issues:
If you encounter problems:
1. Check this troubleshooting guide first
2. Check console output for error messages
3. Test with: `python3 canon_wifi.py` (standalone test mode)
4. Report issue with:
   - Camera model
   - Error messages
   - Connection method (Infrastructure/AP)
   - Network setup

---

## Quick Reference Commands

```bash
# Install dependencies
pip3 install -r requirements.txt

# Run scanner with Canon WiFi setup
python3 web_app.py

# Reset configuration (re-run setup)
python3 web_app.py --reset

# Show current configuration
python3 web_app.py --config

# Test Canon WiFi connection (standalone)
python3 canon_wifi.py

# Check camera IP (on Pi)
sudo nmap -sn 192.168.1.0/24 | grep -i canon

# Kill interfering processes
killall gphoto2 gvfs-gphoto2-volume-monitor

# Check gphoto2 connection
gphoto2 --auto-detect

# View scanner logs
tail -f scanner_log.txt  # If logging enabled
```

---

## License

This Canon WiFi integration is part of the Film Scanner project and uses the same license.

Canon and EOS are trademarks of Canon Inc.

---

**Happy Scanning! 📷🎞️**

