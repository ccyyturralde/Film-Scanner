# Canon R100 WiFi - Quick Start

## 🚀 5-Minute Setup

### Step 1: Enable Camera WiFi (2 min)
1. Canon R100: **MENU** → **Wireless** → **Enable**
2. Choose: **Connect to Network** (same as Pi WiFi)
3. Note camera is on and ready

### Step 2: Connect (1 min)
1. Start scanner: `python3 web_app.py`
2. Open web interface: `http://<pi_ip>:5000`
3. Click: **"Setup Canon WiFi"**
4. Click: **"Auto-scan"** (or enter IP manually)
5. Wait for connection ✅

### Step 3: Start Live View (30 sec)
1. Click: **"Start Live View"**
2. See smooth 10 FPS preview 📹
3. Position your film using live view

### Step 4: Capture (30 sec)
1. USB cable connected to camera? ✅
2. Click: **"Autofocus"** (via USB)
3. Click: **"Capture"** (via USB)
4. Done! Photo on camera SD card 📷

---

## 🔧 What You Need

- ✅ Canon R100 with WiFi enabled
- ✅ Raspberry Pi on same WiFi network
- ✅ USB cable (for autofocus/capture)
- ✅ Updated software: `pip3 install -r requirements.txt`

---

## 🎯 Key Points

### Live View:
- **Source**: Canon WiFi only
- **Speed**: ~10 FPS, smooth
- **Button**: "Start Live View"

### Autofocus & Capture:
- **Source**: gphoto2 via USB
- **Required**: USB cable connected
- **Buttons**: "Autofocus" then "Capture"

### Connections Needed:
- **WiFi**: Pi ↔ Camera (for live view)
- **USB**: Pi ↔ Camera (for control)
- **Both required** for full functionality

---

## 🆘 Quick Troubleshooting

### Can't find camera?
```bash
# Check camera IP manually:
# Camera: MENU → Wireless → WiFi Details
# Then enter IP in web interface
```

### Live view won't start?
- Camera in M/Av/Tv/P mode? (not Auto)
- Lens cap removed?
- Camera not in sleep mode?

### Autofocus fails?
- USB cable connected?
- Camera in PTP mode?
- Run: `gphoto2 --auto-detect`

### Connection keeps dropping?
- Move camera and Pi closer
- Use 5GHz WiFi if available
- Check camera battery level

---

## 📖 Full Documentation

For detailed info, see:
- **`CANON_R100_WIFI_SETUP.md`** - Complete setup guide
- **`CANON_WIFI_INTEGRATION_SUMMARY.md`** - Technical details

---

## 💡 Pro Tips

1. **Set static IP**: Reserve camera IP in router for reliability
2. **Battery**: Use AC adapter for long sessions (WiFi drains battery)
3. **Network**: Dedicated 5GHz WiFi gives best performance
4. **Positioning**: Use live view grid lines for film alignment
5. **Workflow**: Start live view → Position → Stop live view → Focus → Capture

---

## 🔄 Typical Workflow

```
Power on camera → Enable WiFi → Start scanner
    ↓
Setup Canon WiFi (once)
    ↓
Start Live View → Position film
    ↓
Stop Live View (optional) → Autofocus → Capture
    ↓
Auto-advance to next frame → Repeat
```

---

## 📞 Need Help?

1. Check `CANON_R100_WIFI_SETUP.md` Troubleshooting section
2. Test standalone: `python3 canon_wifi.py`
3. Check console for error messages
4. Verify network connectivity: `ping <camera_ip>`

---

**Quick Links:**
- Setup Guide: `CANON_R100_WIFI_SETUP.md`
- API Reference: See setup guide Section "API Endpoints"
- Configuration: `python3 web_app.py --config`
- Reset: `python3 web_app.py --reset`

---

**Happy Scanning! 📷🎞️**

*Canon R100 WiFi Integration - Film Scanner v2.0*

