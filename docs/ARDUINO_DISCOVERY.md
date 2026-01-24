# Arduino Discovery Guide - First Time WiFi Connection

## How It Works

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Your Network Setup                        │
└─────────────────────────────────────────────────────────────┘

Internet ←→ Router (192.168.1.1)
             │
             ├─→ Raspberry Pi (192.168.1.50)
             │   ├─ Hostname: raspberrypi.local
             │   ├─ Runs Flask web server on port 5000
             │   ├─ USB → Camera (gphoto2)
             │   └─ USB → HDMI Capture Card
             │
             └─→ Arduino R4 WiFi (192.168.1.100)
                 └─ Runs TCP server on port 8888


┌─────────────────────────────────────────────────────────────┐
│              How You Access the Scanner                      │
└─────────────────────────────────────────────────────────────┘

Your Phone/Computer (any device on WiFi)
    │
    └─→ http://raspberrypi.local:5000  ← Web browser
            │
            └─→ Raspberry Pi Flask Web App
                    │
                    ├─→ WiFi TCP → Arduino R4 WiFi (motor control)
                    ├─→ USB → Camera (capture images)
                    └─→ USB → Capture Card (live preview)
```

**Key Point:** You access the web interface via the **Raspberry Pi's hostname** - this hasn't changed. Only the Pi↔Arduino connection changed from USB to WiFi.

## First-Time Arduino Connection

### Method 1: Watch LED Matrix (Easiest) ⭐

When Arduino boots up with WiFi enabled:

1. **LED shows "W"** - Connecting to WiFi
2. **IP address scrolls across** - Note this IP! (e.g., 192.168.1.100)
3. **Happy face** - Ready and waiting

**Write down the IP address** you see scrolling, then update `web_app.py`:

```python
ARDUINO_WIFI_IP = "192.168.1.100"  # The IP you saw on LED matrix
```

### Method 2: USB Serial Monitor (During First Setup)

While Arduino is still connected via USB for flashing:

```bash
# Connect to Arduino serial monitor
screen /dev/ttyACM0 115200

# You'll see output like:
# === WiFi Setup ===
# Connecting to: YourNetwork
# .....
# ✓ WiFi connected!
# IP Address: 192.168.1.100
# TCP Port: 8888
```

Write down the IP address, then you can disconnect USB.

### Method 3: Check Router's DHCP Leases

If using DHCP (not static IP):

1. Log into your router's admin page (usually http://192.168.1.1)
2. Find DHCP leases or connected devices
3. Look for device named "Arduino" or with manufacturer "Espressif"
4. Note the IP address

### Method 4: Network Scan (Advanced)

From Raspberry Pi:

```bash
# Install nmap if needed
sudo apt install nmap

# Scan your network
sudo nmap -sn 192.168.1.0/24

# Or use arp-scan
sudo apt install arp-scan
sudo arp-scan --localnet | grep -i espressif
```

### Method 5: Static IP (Recommended)

**Best practice:** Configure static IP in `wifi_config.h` BEFORE flashing:

```cpp
const bool USE_STATIC_IP = true;
const char* STATIC_IP = "192.168.1.100";
const char* GATEWAY = "192.168.1.1";
const char* SUBNET = "255.255.255.0";
```

Then Arduino will **always** use 192.168.1.100. No discovery needed!

## Verifying Connection

### 1. Ping Test

```bash
# From Raspberry Pi
ping 192.168.1.100

# Should see:
# 64 bytes from 192.168.1.100: icmp_seq=1 ttl=255 time=3.2 ms
# ✓ Arduino is on network!
```

### 2. TCP Connection Test

```bash
# From Raspberry Pi
telnet 192.168.1.100 8888

# Should see:
# READY NEMA17
# Film Scanner Motor Control (WiFi)
# ✓ TCP server working!

# Try commands:
?      # Status
F      # Forward
b      # Backward fine
```

Press `Ctrl+]` then type `quit` to exit telnet.

### 3. Test from Web App

```bash
# From Raspberry Pi
python3 web_app.py

# Should see in logs:
# 🔌 Connecting to Arduino R4 WiFi at 192.168.1.100:8888...
# ✓ Connected to Arduino R4 WiFi at 192.168.1.100:8888
```

## Connection Sequence (What Happens)

### Arduino Boot Sequence

```
1. Arduino powers on (from 12V VIN)
   └─→ LED: Idle (single dot)

2. Arduino connects to WiFi
   └─→ LED: "W" pattern (connecting)
   
3. WiFi connected, got IP address
   └─→ LED: IP scrolls across matrix
   
4. TCP server starts on port 8888
   └─→ LED: Happy face (ready)
   
5. Waiting for Pi to connect...
```

### Raspberry Pi Boot Sequence

```
1. Pi boots, connects to WiFi
   └─→ Gets IP: 192.168.1.50
   
2. Flask web app starts (web_app.py)
   └─→ Listens on port 5000
   
3. Web app tries to connect to Arduino
   └─→ Opens TCP socket to 192.168.1.100:8888
   
4. Arduino accepts connection
   └─→ Sends "READY NEMA17"
   
5. Web app confirms Arduino connected
   └─→ Status: "Arduino: Connected (R4 WiFi TCP)"
```

## Accessing the Web Interface

**From any device on your WiFi network:**

```bash
# Using hostname (recommended)
http://raspberrypi.local:5000

# Or using Pi's IP address
http://192.168.1.50:5000
```

**Not:** `http://192.168.1.100` ← This is Arduino, not the web interface!

### Finding Pi's Hostname

```bash
# From Pi
hostname -f
# Output: raspberrypi.local

# Or check IP
hostname -I
# Output: 192.168.1.50
```

### Changing Pi's Hostname (Optional)

```bash
sudo raspi-config
# Navigate to: System Options → Hostname
# Change to: film-scanner

# Then access via:
http://film-scanner.local:5000
```

## Troubleshooting First Connection

### Arduino Shows "W" Forever

**WiFi not connecting:**

1. Check `wifi_config.h` - typos in SSID/password?
2. Is WiFi 2.4GHz? (Arduino doesn't support 5GHz)
3. Is router within range?
4. Check Serial monitor for errors

### Arduino Shows "X" on LED

**WiFi error:**

1. Wrong password
2. Router not responding
3. Network unreachable

### Pi Can't Connect to Arduino

**"Connection timeout" error:**

1. **Wrong IP address** - Check what Arduino displays on LED
2. **Different subnet** - Pi and Arduino must be on same network
3. **Firewall** - Check if Pi or router blocking port 8888
4. **Arduino not ready** - Wait for happy face on LED matrix

**Test manually:**

```bash
# Can Pi reach Arduino?
ping 192.168.1.100

# Can Pi connect to TCP port?
telnet 192.168.1.100 8888

# If telnet works but web_app.py doesn't:
# - Check ARDUINO_WIFI_IP in web_app.py
# - Check ARDUINO_WIFI_PORT matches wifi_config.h
```

### Can't Access Web Interface

**"Cannot reach raspberrypi.local:5000"**

1. **Pi not on WiFi** - Check Pi's WiFi connection
   ```bash
   ifconfig wlan0
   ```

2. **Flask not running** - Start web app
   ```bash
   python3 web_app.py
   ```

3. **Wrong hostname** - Try IP instead
   ```bash
   # Find Pi's IP
   hostname -I
   
   # Access via IP
   http://192.168.1.50:5000
   ```

4. **Firewall blocking port 5000**
   ```bash
   # Check if Flask is listening
   sudo netstat -tulpn | grep 5000
   ```

## Network Diagram with Real IPs

```
Your Home Network (192.168.1.0/24)

Router: 192.168.1.1
    │
    ├─ Your Phone/Laptop (192.168.1.X)
    │  └─ Access web interface:
    │     http://raspberrypi.local:5000
    │
    ├─ Raspberry Pi (192.168.1.50)
    │  ├─ Hostname: raspberrypi.local
    │  ├─ Runs Flask on port 5000 ← You connect here
    │  ├─ Connects to Arduino via WiFi TCP
    │  ├─ USB → Canon Camera (gphoto2)
    │  └─ USB → HDMI Capture Card
    │
    └─ Arduino R4 WiFi (192.168.1.100)
       └─ Runs TCP server on port 8888 ← Pi connects here
          Controls motor via D2/D3/D4
```

## Quick Reference

### Connection Ports

| Device | Port | Protocol | Purpose |
|--------|------|----------|---------|
| **Raspberry Pi** | 5000 | HTTP | Web interface (you access this) |
| **Arduino** | 8888 | TCP | Motor control (Pi connects here) |
| Camera | USB | USB/PTP | Image capture |
| Capture Card | USB | USB Video | Live preview |

### IP Addresses (Your Configuration)

Update these in your setup:

| Device | Default IP | Your IP | Hostname |
|--------|-----------|---------|----------|
| Router | 192.168.1.1 | __________ | - |
| Raspberry Pi | 192.168.1.50 | __________ | raspberrypi.local |
| Arduino | 192.168.1.100 | __________ | arduino-r4.local |

### Configuration Files

| File | What to Set | Example |
|------|-------------|---------|
| `arduino/film_scanner/wifi_config.h` | WIFI_SSID, WIFI_PASSWORD, STATIC_IP | "MyNetwork", "pass123", "192.168.1.100" |
| `web_app.py` | ARDUINO_WIFI_IP | "192.168.1.100" |

## Summary

**Key Points:**

1. ✅ **Web interface:** Still accessed via Pi's hostname (`raspberrypi.local:5000`)
2. ✅ **Camera & Capture Card:** Still connected via USB to Pi (unchanged)
3. ✅ **Arduino:** Now connects via WiFi instead of USB
4. ✅ **First connection:** Arduino displays its IP on LED matrix
5. ✅ **Configuration:** Set Arduino's IP in both `wifi_config.h` and `web_app.py`

**Connection Flow:**

```
You → Pi hostname → Flask web app → WiFi → Arduino → Motor
```

**NOT:**

```
You → Arduino directly  ❌ Wrong!
```

You always access the scanner through the Raspberry Pi's web interface!
