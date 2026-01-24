# Quick Start - WiFi Version

## What You Need

1. **Arduino Uno R4 WiFi** (must be R4 WiFi - R3/R4 Minima won't work)
2. **12V 2A power supply** (powers both motor and Arduino)
3. **WiFi network** (2.4GHz - Arduino doesn't support 5GHz)
4. **Raspberry Pi** on same WiFi network

## 5-Minute Setup

### 1. Configure WiFi (2 min)

Edit `arduino/film_scanner/wifi_config.h`:

```cpp
const char* WIFI_SSID = "YourNetworkName";      // Your WiFi name
const char* WIFI_PASSWORD = "YourPassword";     // Your WiFi password
const char* STATIC_IP = "192.168.1.100";        // Arduino's IP
const char* GATEWAY = "192.168.1.1";            // Your router's IP
```

### 2. Flash Arduino (1 min)

Connect Arduino via USB ONE TIME:

```bash
cd arduino/film_scanner
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:renesas_uno:unor4wifi
```

Watch the LED matrix:
- "W" = Connecting to WiFi
- IP scrolls = Connected!
- Happy face = Ready

### 3. Configure Python (30 sec)

Edit `web_app.py` line 68-70:

```python
USE_WIFI_ARDUINO = True
ARDUINO_WIFI_IP = "192.168.1.100"  # Match your Arduino's IP
ARDUINO_WIFI_PORT = 8888
```

### 4. Wire Power (1 min)

```
12V Power Supply:
  (+) → Arduino VIN pin
  (−) → Arduino GND pin
  
Motor driver stays the same:
  D2 → STEP
  D3 → DIR
  D4 → ENABLE
  GND → Common ground
```

**⚠️ CRITICAL:** Connect ALL grounds together:
- 12V supply GND
- Arduino GND  
- Motor driver GND

### 5. Test (30 sec)

```bash
python3 web_app.py
```

Open `http://<pi-ip>:5000`

Should see: "Arduino: Connected (R4 WiFi TCP)"

## Troubleshooting

### Arduino won't connect to WiFi
- Check SSID/password spelling
- Verify WiFi is 2.4GHz (not 5GHz)
- Move Arduino closer to router

### Pi can't connect to Arduino
```bash
ping 192.168.1.100        # Should respond
telnet 192.168.1.100 8888 # Should see "READY NEMA17"
```

If no response:
- Check `STATIC_IP` in `wifi_config.h`
- Update `ARDUINO_WIFI_IP` in `web_app.py`
- Watch LED matrix for actual IP address

### Motor buzzes but doesn't move
- **Common ground missing!** Connect all GND together
- Verify: Arduino GND = Driver GND = 12V GND

## Success Checklist

- [x] Arduino LED shows happy face
- [x] Pi connects to Arduino (no "Connection timeout")
- [x] Web interface shows "Arduino: Connected"
- [x] Motor responds to ← → buttons
- [x] No USB cable to Arduino needed!

## Next Steps

1. Disconnect USB cable (no longer needed!)
2. Run full calibration
3. Scan a test roll
4. Enjoy wireless operation 🎉

## Getting Help

- **Full setup guide**: [docs/WIFI_SETUP.md](docs/WIFI_SETUP.md)
- **Wiring diagrams**: [docs/WIFI_WIRING.md](docs/WIFI_WIRING.md)
- **Branch README**: [README_WIFI.md](README_WIFI.md)

## Reverting to USB

If you need to go back to USB Serial version:

```bash
git checkout Web-app-automated-edge-detection
```

Your original working version is safe!
