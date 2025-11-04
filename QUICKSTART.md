# Quick Start Guide - Web Version

## 🚀 Get Started in 3 Steps

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Connect Hardware
- Plug in Arduino (USB)
- Plug in Camera (USB)
- Make sure camera is in PTP/PC mode

### 3. Start the Server
```bash
python web_app.py
```

## 📱 Access the Interface

### On the same computer:
```
http://localhost:5000
```

### From your phone/tablet:
1. Make sure phone is on same WiFi network
2. Find your computer's IP address:
   - **Windows**: Open PowerShell, type `ipconfig`
   - **Mac/Linux**: Open Terminal, type `ifconfig`
   - Look for IP like: `192.168.1.100`
3. Open browser on phone
4. Go to: `http://192.168.1.100:5000` (use your actual IP)

## 🎯 First Scan Workflow

1. **Open the web interface in your browser**

2. **Create a Roll**
   - Type a roll name (e.g., "Vacation Photos")
   - Click "New Roll"

3. **Calibrate (First Strip Only)**
   - Click "Start Calibration"
   - Use motor controls to position frame 1
   - Click "Capture Frame 1"
   - Use motor controls to position frame 2
   - Click "Capture Frame 2"
   - ✓ Calibration complete!

4. **Scan Remaining Frames**
   - Just press "CAPTURE" button
   - Motor auto-advances (if enabled)
   - Repeat for all frames

5. **New Strip**
   - Click "Start New Strip"
   - Position first frame
   - Click "Capture First Frame"
   - Continue scanning

## 🎮 Controls Cheat Sheet

### Essential Buttons
- **CAPTURE** - Take photo
- **Autofocus** - Focus camera
- **Fine Forward/Back** - Small movements
- **Coarse Forward/Back** - Big movements

### Desktop Keyboard Shortcuts
- `Space` - Capture
- `←` `→` - Move motor
- `F` - Focus
- `G` - Toggle step size

## ❓ Troubleshooting

**Arduino not connecting?**
- Try unplugging and reconnecting USB
- Click "Reconnect Arduino"

**Camera not detected?**
- Make sure camera is ON
- Set camera to PC/PTP mode (not mass storage)
- Try a different USB cable

**Can't access from phone?**
- Check both devices on same WiFi
- Double-check IP address
- Try `http://computer-name.local:5000`

## 💡 Tips

- **Add to Home Screen** on phone for quick access
- **Keep phone screen on** during scanning
- **Use landscape mode** on tablets for better layout
- **Auto-advance ON** = motor moves automatically after capture
- **Auto-advance OFF** = you control when to advance

## 🔄 Differences from Terminal Version

| Terminal | Web |
|----------|-----|
| SSH needed | Browser only |
| Keyboard only | Touch + keyboard |
| One user | Multiple viewers |
| Text interface | Visual buttons |

---

**Need more details?** See `README_WEB_APP.md` for complete documentation.

**Happy scanning! 📸**

