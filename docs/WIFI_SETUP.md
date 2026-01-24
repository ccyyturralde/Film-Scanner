# WiFi Setup Guide - Arduino R4 WiFi

This guide explains how to set up the WiFi version of the Film Scanner, which eliminates the need for a USB cable between the Raspberry Pi and Arduino.

## Overview

In this configuration:
- **Arduino R4 WiFi** communicates wirelessly with the Raspberry Pi via TCP/IP
- **Arduino** is powered from the motor's 12V supply (via VIN pin)
- **USB ports saved**: 1 (Arduino no longer needs USB)

## Hardware Requirements

- Arduino Uno R4 WiFi (required - has ESP32-S3 WiFi coprocessor)
- 12V power supply (for motor and Arduino)
- WiFi network (router/access point)
- Raspberry Pi 4 connected to same WiFi network

## Wiring Diagram

### Power Distribution

```
12V Power Supply
    ├─→ Motor Driver VMOT
    ├─→ Arduino VIN (6-24V input)
    └─→ Common GND

GND (Common Ground - CRITICAL!)
    ├─→ Motor Driver GND
    ├─→ Arduino GND
    └─→ 12V Supply GND
```

### Motor Control (unchanged)

```
Arduino R4 WiFi → A4988/TMC2209 Driver
Pin D2 → STEP
Pin D3 → DIR
Pin D4 → ENABLE
GND → GND (common ground)
```

### Arduino Power from Motor Supply

```
Option 1: Direct VIN (simplest)
    12V+ → Arduino VIN pin
    12V- → Arduino GND pin
    
Option 2: Buck Converter (recommended for cooler operation)
    12V+ → Buck Converter IN+
    12V- → Buck Converter IN-
    Buck 5V OUT → Arduino 5V pin
    Buck GND → Arduino GND
```

**Note:** The Arduino R4 WiFi's VIN accepts 6-24V, so 12V is perfect. The onboard regulator will convert it to 5V/3.3V as needed.

## Software Setup

### Step 1: Configure WiFi Settings

Edit `arduino/film_scanner/wifi_config.h`:

```cpp
// Your WiFi network name (SSID)
const char* WIFI_SSID = "YourNetworkName";

// Your WiFi password
const char* WIFI_PASSWORD = "YourPassword123";

// TCP Server Port
const uint16_t TCP_PORT = 8888;

// Static IP (recommended)
const bool USE_STATIC_IP = true;
const char* STATIC_IP = "192.168.1.100";    // Arduino's IP
const char* GATEWAY = "192.168.1.1";         // Your router
const char* SUBNET = "255.255.255.0";
const char* DNS_SERVER = "192.168.1.1";
```

**Static IP Recommendation:**
Using a static IP makes the Arduino easier to find on your network. Choose an IP address that:
- Is in your router's subnet (usually 192.168.1.x or 192.168.0.x)
- Is outside your router's DHCP range (usually .100 or higher is safe)
- Doesn't conflict with other devices

To find your network settings:
```bash
# On Raspberry Pi
ip route | grep default    # Shows your gateway (router IP)
ifconfig wlan0             # Shows your Pi's IP and subnet
```

### Step 2: Flash Arduino Firmware

```bash
cd Film-Scanner/arduino/film_scanner
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:renesas_uno:unor4wifi
```

**Note:** You'll need USB connected ONE TIME to flash the firmware. After that, you can disconnect USB and power via VIN.

### Step 3: Configure Python Web App

Edit `web_app.py` to set your Arduino's IP:

```python
# WiFi Configuration
USE_WIFI_ARDUINO = True
ARDUINO_WIFI_IP = "192.168.1.100"  # Must match your Arduino's IP
ARDUINO_WIFI_PORT = 8888           # Must match TCP_PORT in wifi_config.h
```

### Step 4: Test Connection

1. **Power up Arduino** (via VIN from 12V supply)
2. **Watch the LED matrix** on Arduino R4 WiFi:
   - "W" pattern: Connecting to WiFi
   - IP address scrolls: WiFi connected!
   - Happy face: Ready and waiting for client
   
3. **On Raspberry Pi**, start the web app:
   ```bash
   python3 web_app.py
   ```

4. **Check the logs**:
   ```
   🔌 Connecting to Arduino R4 WiFi at 192.168.1.100:8888...
   ✓ Connected to Arduino R4 WiFi at 192.168.1.100:8888
   ✓ Arduino R4 WiFi connected via TCP
   ```

## Troubleshooting

### Arduino Won't Connect to WiFi

**LED shows "W" pattern continuously:**

1. **Check WiFi credentials**:
   - Verify SSID and password in `wifi_config.h`
   - Make sure there are no typos or extra spaces
   - WiFi password is case-sensitive

2. **Check WiFi network**:
   - Arduino R4 WiFi only supports 2.4GHz WiFi (not 5GHz)
   - Make sure your router has 2.4GHz enabled
   - Try moving Arduino closer to router

3. **Check Serial monitor** (if USB still connected):
   ```bash
   screen /dev/ttyACM0 115200
   # Look for WiFi connection errors
   ```

### Pi Can't Connect to Arduino

**Error: "Connection timeout" or "Connection refused"**

1. **Verify Arduino is on WiFi**:
   - LED matrix should show IP address on startup
   - Note the IP address displayed

2. **Check IP address matches**:
   - `ARDUINO_WIFI_IP` in `web_app.py` must match Arduino's actual IP
   - If using DHCP, check your router's DHCP leases to find Arduino's IP

3. **Test connection manually**:
   ```bash
   # From Raspberry Pi
   ping 192.168.1.100        # Should respond
   
   # Test TCP connection
   telnet 192.168.1.100 8888
   # Should see "READY NEMA17"
   # Type ? and press Enter
   # Should see STATUS output
   ```

4. **Check firewall** (if any):
   - Make sure port 8888 isn't blocked
   - Arduino's built-in firewall allows all connections

### Motor Not Moving

Same as USB version - motor control logic is unchanged:

1. **Check 12V power supply** - should output 12V, 2A minimum
2. **Verify common ground** - Arduino GND, driver GND, and 12V GND must be connected
3. **Test motor driver** - check A4988/TMC2209 Vref (~0.4V)
4. **Send test command via WiFi**:
   ```bash
   telnet 192.168.1.100 8888
   F    # Should move forward
   B    # Should move backward
   ```

### WiFi Disconnects Randomly

1. **Check power supply**:
   - Weak 12V supply can cause Arduino to reset
   - Motor draws current spikes - use 2A minimum supply
   - Consider using buck converter instead of VIN for stable 5V

2. **Check WiFi signal strength**:
   - Move Arduino closer to router
   - Use WiFi repeater/extender if needed

3. **Increase timeout** in `web_app.py`:
   ```python
   ARDUINO_WIFI_TIMEOUT = 10.0  # Increase from 5.0
   ```

### LED Matrix Shows "X" or "!"

- **"X"**: WiFi/communication error
  - Check WiFi credentials
  - Check if router is accessible
  
- **"!"**: General error
  - Check Serial monitor for details
  - May indicate hardware issue

## Verifying Everything Works

### 1. Arduino LED Matrix Indicators

After powering up, you should see:
1. Single dot (idle)
2. "W" pattern (connecting to WiFi)
3. IP address scrolling (WiFi connected)
4. Happy face (ready for client)

### 2. Web Interface Connection

Open `http://<raspberry-pi-ip>:5000`:
- Status should show "Arduino: Connected (R4 WiFi TCP)"
- IP address should be displayed
- Motor controls should work

### 3. Test Motor Commands

In the web interface:
- Click **←** (fine backward) - motor should move slightly
- Click **→** (fine forward) - motor should move slightly
- Shift + **←** / **→** for coarse movements

## Performance Notes

### Latency

WiFi TCP adds minimal latency compared to USB Serial:
- USB Serial: ~5-10ms per command
- WiFi TCP: ~10-20ms per command (depending on network)

This difference is negligible for film scanning operations. Motor commands are not time-critical.

### Reliability

WiFi is very reliable for this application because:
- Commands are small (single characters + newline)
- TCP ensures delivery (with retry)
- No high-frequency communication needed
- Local network has minimal interference

### Debugging

Enable verbose WiFi debugging:

**In Arduino firmware** (`wifi_config.h`):
```cpp
const bool WIFI_DEBUG = true;
```

**In Python** (`web_app.py`):
```python
WIFI_DEBUG = True
```

Connect Arduino to USB to see debug output:
```bash
screen /dev/ttyACM0 115200
```

## Advantages Over USB Serial

✅ **One less USB cable** - frees up Raspberry Pi USB port  
✅ **Shared power** - Arduino powered from motor supply  
✅ **Flexible placement** - Arduino can be anywhere on network  
✅ **Easier troubleshooting** - can test with telnet  
✅ **Future expandability** - can add web interface to Arduino itself  

## Reverting to USB Serial

To switch back to USB Serial version:

```bash
git checkout Web-app-automated-edge-detection
```

Your original working version remains untouched on the main branch.

## Safety Notes

⚠️ **CRITICAL: Common Ground**
- Always connect Arduino GND to motor driver GND to 12V supply GND
- Without common ground, motor will buzz but not move
- Floating grounds can damage components

⚠️ **Power Supply**
- Use quality 12V 2A supply minimum
- Motor draws current spikes during movement
- Undervoltage can cause Arduino to reset

⚠️ **VIN vs 5V Pin**
- VIN: 6-24V (uses onboard regulator) - may get warm
- 5V pin: 5V only (bypasses regulator) - cooler, needs buck converter
- Never apply >5.5V to 5V pin!

## Next Steps

Once WiFi is working:
1. **Secure the Arduino** - mount it near motor for clean wiring
2. **Cable management** - USB cable no longer needed (except for firmware updates)
3. **Test scanning** - run a full roll to verify reliability
4. **Backup config** - save your `wifi_config.h` settings

## Support

If you encounter issues:
1. Check the LED matrix status indicator
2. Review Serial monitor output (via USB)
3. Test TCP connection with telnet
4. Verify WiFi network is 2.4GHz
5. Ensure all grounds are common

WiFi mode is stable and reliable for film scanning operations!
