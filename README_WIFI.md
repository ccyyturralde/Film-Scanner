# 35mm Film Scanner - WiFi Version

Professional-grade 35mm film scanner using **Arduino R4 WiFi** (wireless), Raspberry Pi, and DSLR camera.

## 🆕 What's Different in This Branch?

This `arduino-r4-wifi` branch uses **wireless TCP/IP communication** instead of USB Serial:

| Feature | Main Branch | WiFi Branch (this) |
|---------|-------------|-------------------|
| Arduino | R3/R4 via USB | **R4 WiFi only** |
| Connection | USB Serial | **WiFi TCP** |
| Arduino Power | USB from Pi | **12V motor supply** |
| USB Ports Used | 3 (Arduino + Camera + Capture) | **2 (Camera + Capture)** |
| Range | 3-5 meters (USB cable) | **~30 meters (WiFi)** |

### Key Advantages

✅ **One less USB cable** - Arduino powered from motor's 12V supply  
✅ **Free USB port** - available for future expansion  
✅ **Flexible placement** - Arduino can be anywhere on WiFi network  
✅ **Easier troubleshooting** - test motor control with `telnet`  
✅ **Same reliability** - TCP ensures command delivery  

## Hardware Requirements

| Component | Details | Notes |
|-----------|---------|-------|
| **Arduino** | **Uno R4 WiFi** | **Required** - has ESP32-S3 for WiFi |
| Raspberry Pi | Pi 4 (2GB+ RAM) | Must be on same WiFi network |
| Motor | NEMA 17 stepper | 1.0-1.5A, 40-50 N⋅cm |
| Driver | A4988 or TMC2209 | TMC2209 quieter |
| Camera | Canon DSLR | USB/PTP support, RAW capture |
| Capture Card | USB HDMI capture | For live preview |
| **Power** | **12V 2A supply** | **Powers motor AND Arduino** |
| **WiFi Router** | **2.4GHz network** | **Arduino connects here** |

⚠️ **Important:** Arduino Uno R3 and R4 Minima do NOT have WiFi. You must use R4 WiFi for this branch.

## Quick Start

### 1. Configure WiFi Settings

Edit `arduino/film_scanner/wifi_config.h`:

```cpp
const char* WIFI_SSID = "YourNetworkName";
const char* WIFI_PASSWORD = "YourPassword123";
const uint16_t TCP_PORT = 8888;

// Recommended: Use static IP
const bool USE_STATIC_IP = true;
const char* STATIC_IP = "192.168.1.100";
const char* GATEWAY = "192.168.1.1";
const char* SUBNET = "255.255.255.0";
```

### 2. Flash Arduino (One-Time USB Connection)

```bash
cd Film-Scanner/arduino/film_scanner
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:renesas_uno:unor4wifi
```

**Verify flash succeeded:** LED matrix should show:
- "W" pattern (connecting to WiFi)
- IP address scrolls across (WiFi connected!)
- Happy face (ready)

### 3. Configure Python Web App

Edit `web_app.py`:

```python
USE_WIFI_ARDUINO = True
ARDUINO_WIFI_IP = "192.168.1.100"  # Match your Arduino's IP
ARDUINO_WIFI_PORT = 8888
```

### 4. Power Arduino from Motor Supply

**Option A - Direct VIN (simplest):**
```
12V+ → Arduino VIN pin
12V− → Arduino GND pin
```

**Option B - Buck Converter (recommended):**
```
12V+ → Buck Converter → 5V → Arduino 5V pin
12V− → Buck GND → Arduino GND
```

### 5. Run Scanner

```bash
python3 web_app.py
```

Access at `http://<raspberry-pi-ip>:5000`

## Wiring

```
Power Distribution
==================
12V Power Supply (2A min)
    ├─→ Motor Driver VMOT
    ├─→ Arduino VIN (6-24V) OR Buck Converter IN
    └─→ Common GND rail ⚠️ CRITICAL!

Motor Control (unchanged)
==========================
Arduino R4 WiFi → A4988/TMC2209
Pin D2 → STEP
Pin D3 → DIR
Pin D4 → ENABLE
GND → GND (common ground)

WiFi Connection
===============
Raspberry Pi ←──WiFi──→ Arduino R4 WiFi
(wlan0)                 (192.168.1.100:8888)
```

**⚠️ CRITICAL:** All grounds must be connected:
- 12V supply GND
- Arduino GND
- Motor driver GND

See [docs/WIFI_WIRING.md](docs/WIFI_WIRING.md) for detailed diagrams.

## Documentation

- [**WiFi Setup Guide**](docs/WIFI_SETUP.md) - Complete setup and configuration
- [**Wiring Diagrams**](docs/WIFI_WIRING.md) - Power and connections
- [Hardware Setup](docs/hardware-setup.md) - General hardware info
- [API Reference](docs/api-reference.md) - Arduino command protocol (unchanged)
- [Calibration Workflow](docs/calibration-workflow.md) - Scanning process (unchanged)

## Troubleshooting

### Arduino Won't Connect to WiFi

**LED shows "W" continuously:**

1. Check `wifi_config.h` - verify SSID/password
2. Ensure WiFi is 2.4GHz (Arduino doesn't support 5GHz)
3. Move Arduino closer to router
4. Check Serial monitor: `screen /dev/ttyACM0 115200`

### Pi Can't Connect to Arduino

**"Connection timeout" error:**

1. Verify Arduino IP: LED matrix shows IP on startup
2. Update `ARDUINO_WIFI_IP` in `web_app.py`
3. Test manually:
   ```bash
   ping 192.168.1.100
   telnet 192.168.1.100 8888
   # Should see "READY NEMA17"
   ```

### Motor Not Moving

Same troubleshooting as USB version:

1. Check 12V power supply (2A minimum)
2. Verify common ground (Arduino GND = Driver GND = 12V GND)
3. Test motor via telnet:
   ```bash
   telnet 192.168.1.100 8888
   F    # Forward
   B    # Backward
   ```

### Arduino Resets During Movement

**Cause:** Insufficient power

**Fix:**
- Use 2A power supply minimum (not 1A)
- Add 100μF capacitor across 12V supply
- Use buck converter for stable Arduino power

See [WIFI_SETUP.md](docs/WIFI_SETUP.md) for complete troubleshooting guide.

## Workflow (Unchanged)

1. **Create Roll**: Enter a name for your film roll
2. **Calibrate**: Position and capture first two frames to learn spacing
3. **Scan**: Capture frames with automatic advance
4. **New Strip**: Load next strip and continue

Motor control and scanning workflow are identical to USB version.

## Branch Information

### Switching Branches

**To use WiFi version:**
```bash
git checkout arduino-r4-wifi
```

**To revert to USB Serial version:**
```bash
git checkout Web-app-automated-edge-detection
```

Your original working version is safe on the main branch.

### What's Modified

**New files:**
- `arduino/film_scanner/wifi_config.h` - WiFi settings
- `docs/WIFI_SETUP.md` - Setup guide
- `docs/WIFI_WIRING.md` - Wiring diagrams
- `README_WIFI.md` - This file

**Modified files:**
- `arduino/film_scanner/film_scanner.ino` - WiFi TCP server
- `web_app.py` - Socket communication instead of Serial

**Unchanged:**
- All motor control logic
- All scanning workflows
- Camera control
- Frame detection
- Web interface

## Performance Notes

### Latency

WiFi adds ~10-20ms latency vs USB Serial (~5-10ms). This is negligible for film scanning.

### Reliability

WiFi TCP is very reliable because:
- Commands are small (single characters)
- TCP guarantees delivery
- No high-frequency communication needed
- Local network has minimal interference

### Range

WiFi range: ~30 meters (vs 3-5m USB cable)
- Through walls: ~15-20 meters
- Line of sight: ~30-50 meters
- Use WiFi extender for longer range

## Testing WiFi Connection

### Manual Motor Control (Telnet)

```bash
telnet 192.168.1.100 8888
# Connected! Should see "READY NEMA17"

# Try commands:
?      # Status
F      # Forward (coarse)
f      # Forward (fine)
B      # Backward (coarse)
b      # Backward (fine)
S1200  # Set steps per frame
M      # Motor off
E      # Motor on
```

### Python Test Script

```python
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("192.168.1.100", 8888))

# Read greeting
print(sock.recv(1024).decode())

# Send command
sock.send(b"?\n")
print(sock.recv(1024).decode())

sock.close()
```

## Features (Same as Main Branch)

- **Precise Motor Control**: Fine and coarse positioning
- **Automated Scanning**: Calibrated frame advance
- **Professional Workflow**: Capture to camera SD card
- **Smart Calibration**: Learn frame spacing
- **Resume Capability**: Continue after interruption
- **Live Preview**: Via HDMI capture card
- **Auto-Alignment**: Computer vision frame detection
- **Web Interface**: Mobile-friendly browser control

## Future Enhancements

Possible with WiFi version:

- **OTA firmware updates** - update Arduino over WiFi
- **Arduino web interface** - control motor from Arduino's own web page
- **Remote monitoring** - check scanner status from anywhere
- **Multi-client** - connect multiple devices to same Arduino
- **MQTT integration** - for home automation

## Advantages Summary

| Benefit | Impact |
|---------|--------|
| **Free USB port** | Can add more USB devices to Pi |
| **Shared power** | One less power supply/cable |
| **Flexible placement** | Arduino doesn't need to be near Pi |
| **Easy testing** | Use telnet for quick motor tests |
| **Wireless setup** | Cleaner physical setup |
| **Future expandability** | OTA updates, web interface, MQTT |

## Safety Notes

⚠️ **Common Ground Required**
- Arduino GND, motor driver GND, and 12V supply GND must be connected
- Without common ground, motor will buzz but not move

⚠️ **Power Supply**
- Use 2A minimum (3A recommended)
- Motor draws current spikes during movement
- Underpowered supply causes Arduino to reset

⚠️ **VIN Pin Limits**
- Arduino VIN accepts 6-24V
- Above 12V, regulator gets warm
- Buck converter recommended for cooler operation

⚠️ **WiFi Network**
- Arduino R4 WiFi only supports 2.4GHz (not 5GHz)
- WPA2 security supported
- Hidden SSID may cause connection issues

## Project Structure

```
Film-Scanner/
├── arduino/
│   └── film_scanner/
│       ├── film_scanner.ino      # WiFi firmware
│       └── wifi_config.h         # WiFi settings
├── docs/
│   ├── WIFI_SETUP.md            # Setup guide
│   ├── WIFI_WIRING.md           # Wiring diagrams
│   ├── hardware-setup.md        # General hardware
│   └── ...
├── web_app.py                   # Modified for WiFi
├── README_WIFI.md              # This file
└── ...
```

## Getting Help

If you encounter issues:

1. **Check LED matrix status** - shows WiFi/system state
2. **Review Serial monitor** - `screen /dev/ttyACM0 115200`
3. **Test with telnet** - verify TCP connection works
4. **Verify WiFi is 2.4GHz** - Arduino doesn't support 5GHz
5. **Check common ground** - all GND must be connected
6. **Read troubleshooting guides** - see docs/WIFI_SETUP.md

## License

MIT License - See [LICENSE](LICENSE)

## Acknowledgments

- Arduino WiFi firmware based on Arduino WiFiS3 library
- Motor control logic unchanged from USB version
- Web interface and scanning workflow preserved

---

**Ready to go wireless? Follow the [WiFi Setup Guide](docs/WIFI_SETUP.md) to get started!** 🚀
