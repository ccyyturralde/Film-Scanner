# WiFi Access Point - Future Implementation Ideas

**Date:** November 6, 2025  
**Hardware:** Raspberry Pi 4 Model B (4GB RAM), ESP32-WROOM-32 DevBoard v2

---

## Overview

This document outlines options for controlling the Film Scanner from a mobile phone **without requiring an existing WiFi network**. The Pi 4 has built-in WiFi and Bluetooth, opening up several possibilities.

---

## Option 1: Raspberry Pi 4 as WiFi Access Point (RECOMMENDED)

### Why This is Best:
- ✅ No additional hardware needed
- ✅ Works on ANY phone (iPhone, Android, etc.)
- ✅ Existing Flask web app works unchanged - zero code modifications
- ✅ Faster than Bluetooth (higher bandwidth for live preview)
- ✅ Better range (30-50m vs 10m for Bluetooth)
- ✅ More reliable connection
- ✅ Standard HTTP/WebSocket - easy to debug
- ✅ Can still SSH to Pi from phone/laptop connected to Pi's network

### Trade-offs:
- ❌ Pi's WiFi is tied up (can't connect to internet via WiFi simultaneously)
- ✅ But Ethernet still works for internet if needed

### Implementation Steps:

#### 1. Install Required Packages
```bash
sudo apt update
sudo apt install hostapd dnsmasq dhcpcd5
sudo systemctl stop hostapd
sudo systemctl stop dnsmasq
```

#### 2. Configure Static IP for WiFi Interface
Edit `/etc/dhcpcd.conf`:
```bash
# Add at the end:
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
```

#### 3. Configure DHCP Server (dnsmasq)
Backup original: `sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig`

Create `/etc/dnsmasq.conf`:
```
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
domain=local
address=/filmscanner.local/192.168.4.1
```

#### 4. Configure Access Point (hostapd)
Create `/etc/hostapd/hostapd.conf`:
```
interface=wlan0
driver=nl80211
ssid=FilmScanner
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=scanner2025
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
```

Edit `/etc/default/hostapd`:
```
DAEMON_CONF="/etc/hostapd/hostapd.conf"
```

#### 5. Enable IP Forwarding (Optional - for internet sharing via Ethernet)
Edit `/etc/sysctl.conf`:
```
net.ipv4.ip_forward=1
```

Apply: `sudo sysctl -w net.ipv4.ip_forward=1`

Add NAT rules (if sharing internet from eth0):
```bash
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
sudo iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
sudo iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT

# Save rules
sudo sh -c "iptables-save > /etc/iptables.ipv4.nat"
```

#### 6. Enable Services
```bash
sudo systemctl unmask hostapd
sudo systemctl enable hostapd
sudo systemctl enable dnsmasq
sudo systemctl start hostapd
sudo systemctl start dnsmasq
```

#### 7. Reboot
```bash
sudo reboot
```

### Using the AP:
1. On your phone/tablet, connect to WiFi network: `FilmScanner`
2. Password: `scanner2025`
3. Open browser to: `http://192.168.4.1:5000`
4. Can also SSH: `ssh pi@192.168.4.1`

### Reverting to Normal WiFi:
To temporarily disable AP and use normal WiFi:
```bash
sudo systemctl stop hostapd
sudo systemctl stop dnsmasq
# Use normal WiFi config
```

To re-enable:
```bash
sudo systemctl start hostapd
sudo systemctl start dnsmasq
```

---

## Option 2: ESP32 as WiFi Access Point + Serial Bridge

### Why Consider This:
- Pi's WiFi remains free to connect to home network
- Extended range (ESP32 can be positioned optimally)
- Can add hardware features (OLED display, buttons, battery monitoring)

### How It Works:
1. ESP32 creates WiFi AP (e.g., "FilmScanner-ESP32")
2. Phone connects to ESP32's WiFi
3. ESP32 connects to Pi via USB/Serial
4. ESP32 receives HTTP requests from phone over WiFi
5. ESP32 forwards commands to Pi via serial protocol
6. Pi processes and responds back through ESP32

### Implementation Outline:

#### ESP32 Code (Arduino):
```cpp
#include <WiFi.h>
#include <WebServer.h>

const char* ssid = "FilmScanner";
const char* password = "scanner2025";

WebServer server(80);

void setup() {
  Serial.begin(115200);  // To Raspberry Pi
  
  // Create Access Point
  WiFi.softAP(ssid, password);
  IPAddress IP = WiFi.softAPIP();
  
  // Setup routes
  server.on("/", handleRoot);
  server.on("/api/status", handleStatus);
  server.on("/api/move", handleMove);
  // ... more routes
  
  server.begin();
}

void loop() {
  server.handleClient();
}

void handleMove() {
  // Parse JSON from phone
  String direction = server.arg("direction");
  
  // Send to Pi via serial
  Serial.println("MOVE:" + direction);
  
  // Wait for response
  String response = Serial.readStringUntil('\n');
  
  // Send back to phone
  server.send(200, "application/json", response);
}
```

#### Pi Code (Python - Add Serial Handler):
```python
# Add to web_app.py or create separate serial_handler.py

import serial
import json

def handle_esp32_commands():
    esp32 = serial.Serial('/dev/ttyUSB0', 115200)
    
    while True:
        if esp32.in_waiting:
            cmd = esp32.readline().decode().strip()
            
            if cmd.startswith("MOVE:"):
                direction = cmd.split(":")[1]
                # Process move command
                result = scanner.move(direction)
                response = json.dumps({"success": result})
                esp32.write(response.encode() + b'\n')
            
            # ... handle other commands
```

### Pros:
- Pi can maintain internet connection
- Extended range potential
- Offload WiFi from Pi

### Cons:
- Requires implementing serial protocol
- Additional hardware/complexity
- Some latency in serial communication
- Need to modify existing code

---

## Option 3: ESP32 in Dual Mode (AP + Station) + Pi Creates Network

### How It Works:
1. Pi creates its own WiFi network (using Option 1 setup)
2. ESP32 runs in AP+STA mode simultaneously:
   - Acts as Access Point for phone connection
   - Acts as WiFi client connected to Pi's network
3. ESP32 proxies/routes HTTP requests between phone and Pi

### ESP32 Dual Mode Code:
```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>

// AP settings (for phone)
const char* ap_ssid = "FilmScanner-Mobile";
const char* ap_password = "scanner2025";

// Station settings (connect to Pi)
const char* sta_ssid = "FilmScanner-Pi";
const char* sta_password = "pi_network_pass";

WebServer server(80);
String piIP = "192.168.4.1";

void setup() {
  // Set up as AP
  WiFi.softAP(ap_ssid, ap_password);
  
  // Connect to Pi's network
  WiFi.begin(sta_ssid, sta_password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
  
  // Proxy routes
  server.onNotFound(handleProxy);
  server.begin();
}

void handleProxy() {
  HTTPClient http;
  String url = "http://" + piIP + ":5000" + server.uri();
  
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  
  int httpCode;
  if (server.method() == HTTP_GET) {
    httpCode = http.GET();
  } else if (server.method() == HTTP_POST) {
    httpCode = http.POST(server.arg("plain"));
  }
  
  String response = http.getString();
  server.send(httpCode, "application/json", response);
  http.end();
}
```

### Pros:
- Extended range (ESP32 closer to work area)
- Pi's network is isolated
- Can use existing HTTP protocol

### Cons:
- Most complex setup
- Two networks to manage
- ESP32 needs good positioning to reach both Pi and phone

---

## Option 4: Web Bluetooth API (NOT RECOMMENDED)

### How It Works:
- Pi advertises as Bluetooth Low Energy (BLE) device
- Web page uses JavaScript Web Bluetooth API
- Browser connects directly to Pi via Bluetooth

### Why NOT Recommended:
- ❌ Only works on Android (no iOS Safari support)
- ❌ Requires HTTPS or localhost (security requirement)
- ❌ Much slower than WiFi (bandwidth limitations)
- ❌ Shorter range (~10m vs 30m+)
- ❌ Connection can be finicky
- ❌ More complex to implement
- ❌ Would need to rewrite web app for BLE characteristics

### Only Consider If:
- You absolutely need Pi's WiFi for something else AND don't want ESP32
- You only use Android phones
- You're okay with slower performance

---

## SSH Access Reference

### When Pi is in AP Mode:

**From device connected to Pi's AP:**
```bash
ssh pi@192.168.4.1
```

**What you CAN do:**
- SSH from any device connected to Pi's AP network
- Run commands normally
- Stop/start web app
- View logs

**What you CAN'T do:**
- SSH from devices on your home WiFi (unless Ethernet connected)
- Pi can't reach internet via WiFi (but Ethernet still works)

---

## Controlling the Web App

### Stop/Start Methods:

#### Method 1: Foreground (Development)
```bash
# Start
python3 web_app.py

# Stop
Ctrl+C
```

#### Method 2: Using Screen (Recommended for AP mode)
```bash
# Start in screen
screen -S scanner
python3 web_app.py
# Detach: Ctrl+A, then D

# Reattach later
screen -r scanner

# Stop inside screen
Ctrl+C
```

#### Method 3: Systemd Service (Production)

Create `/etc/systemd/system/film-scanner.service`:
```ini
[Unit]
Description=Film Scanner Web App
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Film-Scanner/Film-Scanner
ExecStart=/usr/bin/python3 /home/pi/Film-Scanner/Film-Scanner/web_app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and control:
```bash
# Enable auto-start on boot
sudo systemctl enable film-scanner

# Start service
sudo systemctl start film-scanner

# Stop service
sudo systemctl stop film-scanner

# Restart service
sudo systemctl restart film-scanner

# Check status
sudo systemctl status film-scanner

# View logs
sudo journalctl -u film-scanner -f
```

#### Method 4: Kill Process (Emergency)
```bash
# Find process
ps aux | grep web_app.py

# Kill by PID
kill <PID>

# Or kill by name
pkill -f web_app.py

# Force kill (last resort)
killall -9 python3  # WARNING: kills ALL python3 processes
```

---

## Recommended Implementation Plan

### Phase 1: Basic AP Mode (Simplest Start)
1. Configure Pi 4 as WiFi Access Point (Option 1)
2. No code changes needed
3. Test with existing web app
4. Verify SSH access works

### Phase 2: Production Setup (After Testing)
1. Set up web app as systemd service
2. Configure auto-start on boot
3. Create start/stop scripts for easy management

### Phase 3: Optional Enhancement (If Needed)
1. Add ESP32 for extended range (Option 2 or 3)
2. Only if needed - don't add complexity unnecessarily

---

## Quick Reference Commands

### Check WiFi Status:
```bash
sudo systemctl status hostapd
sudo systemctl status dnsmasq
iwconfig wlan0
```

### View Connected Devices:
```bash
# See who's connected to your AP
cat /var/lib/misc/dnsmasq.leases
```

### Toggle AP Mode:
```bash
# Disable AP (use normal WiFi)
sudo systemctl stop hostapd
sudo systemctl stop dnsmasq

# Enable AP
sudo systemctl start hostapd
sudo systemctl start dnsmasq
```

### Check Web App Status:
```bash
# If running as service
sudo systemctl status film-scanner

# If in screen
screen -ls
screen -r scanner

# Check if process running
ps aux | grep web_app.py
```

---

## Network Topology Diagrams

### Option 1: Pi as AP
```
[Phone] --WiFi--> [Pi 4 WiFi AP] --USB--> [Arduino]
                  [192.168.4.1]           [Film Scanner]
                       |
                    Ethernet (optional for internet)
                       |
                   [Router]
```

### Option 2: ESP32 as AP + Serial
```
[Phone] --WiFi--> [ESP32 AP] --USB/Serial--> [Pi 4] --USB--> [Arduino]
                                              [Ethernet to Router]
```

### Option 3: Dual Mode
```
[Phone] --WiFi--> [ESP32 AP]
                     |
                  WiFi Client
                     |
                  [Pi WiFi AP] --USB--> [Arduino]
                  [Ethernet to Router]
```

---

## Testing Checklist

When implementing AP mode:
- [ ] Can connect to Pi's WiFi network from phone
- [ ] Can access web app at http://192.168.4.1:5000
- [ ] Can SSH to pi@192.168.4.1
- [ ] All web app features work (motor, camera, preview)
- [ ] WebSocket connection works (live updates)
- [ ] Can stop/restart web app via SSH
- [ ] Range is acceptable for work area
- [ ] Pi responds promptly (no lag)
- [ ] Connection is stable (doesn't drop)
- [ ] Multiple devices can connect if needed

---

## Notes & Considerations

- **Password Security:** Change default passwords in production
- **Range:** WiFi typically 30-50m, can be extended with ESP32
- **Battery:** Pi 4 needs ~15W, consider power options for portable use
- **Internet:** If needed during scanning, use Ethernet or USB WiFi adapter
- **Multiple Users:** AP mode supports multiple connections (default ~4-8)
- **Performance:** WiFi is much faster than needed for this application
- **Fallback:** Can always revert to connecting Pi to home WiFi if needed

---

## Future Enhancements

- Add physical power button on GPIO
- Add small OLED display showing WiFi status/IP
- Battery pack integration for portable operation
- Auto-shutdown script after inactivity
- mDNS/Bonjour for filmscanner.local access
- Captive portal for easier first-time connection
- Web-based AP configuration page

---

## Conclusion

**Recommendation:** Start with Option 1 (Pi 4 as WiFi AP). It's the simplest, requires no hardware changes, and your existing web app works perfectly as-is. Only add ESP32 complexity if you find you need extended range or want to keep Pi's WiFi free for other purposes.

The Pi 4's built-in WiFi is more than capable for this application, and the ease of implementation makes it the clear winner for a first version.

