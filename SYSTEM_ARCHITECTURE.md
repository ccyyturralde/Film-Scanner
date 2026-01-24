# System Architecture - WiFi Version

## How You Access The Scanner (Unchanged!)

```
┌─────────────────────────────────────────────────────────────────┐
│                     Your Phone/Laptop/Computer                   │
│                                                                   │
│   Open web browser and go to:                                   │
│   http://raspberrypi.local:5000                                 │
│                                                                   │
│   ✓ Same as before - Pi hostname unchanged!                     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ WiFi Network
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Raspberry Pi                              │
│                   (raspberrypi.local)                           │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │   Flask Web App (port 5000)                             │   │
│  │   - Serves web interface                                 │   │
│  │   - Handles scanning workflow                            │   │
│  │   - Processes images                                     │   │
│  └──────────────────┬──────────────────┬───────────────────┘   │
│                     │                  │                         │
│                     │                  │                         │
│  ┌──────────────────▼─────┐  ┌────────▼────────┐               │
│  │   USB Port 1           │  │  USB Port 2     │               │
│  │   HDMI Capture Card    │  │  Canon Camera   │               │
│  │   (Live Preview)       │  │  (RAW Capture)  │               │
│  └────────────────────────┘  └─────────────────┘               │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │   WiFi Connection (NEW!)                                  │  │
│  │   Connects to: 192.168.1.100:8888                        │  │
│  │   Sends motor commands: F, B, f, b, etc.                 │  │
│  └─────────────────────────────┬─────────────────────────────┘  │
└─────────────────────────────────┼─────────────────────────────────┘
                                  │
                                  │ WiFi TCP (port 8888)
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Arduino Uno R4 WiFi                          │
│                   IP: 192.168.1.100                             │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │   TCP Server (port 8888)                                  │  │
│  │   - Receives motor commands from Pi                       │  │
│  │   - LED matrix shows WiFi status                          │  │
│  │   - Displays IP address on boot                           │  │
│  └─────────────────────────┬─────────────────────────────────┘  │
│                             │                                     │
│  ┌──────────────────────────▼──────────────────────────────┐    │
│  │   Motor Control Pins                                     │    │
│  │   D2 → STEP  |  D3 → DIR  |  D4 → ENABLE               │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                              │                                    │
│  ┌───────────────────────────▼──────────────────────────────┐   │
│  │   Power Input: VIN (from 12V motor supply)              │   │
│  │   No USB cable to Pi needed! ✓                          │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬──────────────────────────────────┘
                                │
                                │ Control Signals
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   A4988/TMC2209 Stepper Driver                   │
│                                                                   │
│   STEP ← D2  |  DIR ← D3  |  ENABLE ← D4                       │
│   VMOT ← 12V |  VDD ← 5V  |  GND ← Common Ground              │
└───────────────────────────────┬──────────────────────────────────┘
                                │
                                │ Motor Power
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         NEMA 17 Stepper Motor                    │
│                      (Film Transport Mechanism)                  │
└─────────────────────────────────────────────────────────────────┘
```

## What Changed vs. Original Version

### ❌ What DID NOT Change

- ✅ Web interface access: Still `http://raspberrypi.local:5000`
- ✅ Pi hostname: Still `raspberrypi.local`
- ✅ Camera connection: Still USB to Pi (port 1 or 2)
- ✅ Capture card connection: Still USB to Pi
- ✅ Motor control commands: Same protocol (F, B, f, b, etc.)
- ✅ Scanning workflow: Identical
- ✅ Web interface features: All unchanged
- ✅ Image capture: Same gphoto2 integration

### ✅ What DID Change

- 🔄 Arduino connection: USB Serial → WiFi TCP
- 🔄 Arduino power: USB from Pi → 12V VIN from motor supply
- 🔄 USB ports used: 3 → 2 (saved 1 port!)
- 🔄 Arduino firmware: Added WiFi TCP server
- 🔄 Python code: Added socket communication

## Power Distribution

```
┌────────────────────────────────────────────────────────────┐
│                    Power Supplies                           │
└────────────────────────────────────────────────────────────┘

5V USB-C Power Supply (3A)
    │
    └─→ Raspberry Pi
        ├─ Powers Pi itself
        ├─ Powers USB devices (camera, capture card)
        └─ NO LONGER powers Arduino! ✓

12V DC Power Supply (2A minimum)
    │
    ├─→ Motor Driver VMOT (motor power)
    │
    └─→ Arduino VIN (6-24V input)  ← NEW!
        Arduino's onboard regulator converts to 5V/3.3V

⚠️  CRITICAL: Common Ground
    All GND must be connected:
    - 12V Supply GND
    - Arduino GND
    - Motor Driver GND
```

## Connection Summary Table

| Component | Connects To | Via | Port/Pin |
|-----------|-------------|-----|----------|
| **You (User)** | Raspberry Pi | WiFi → HTTP | Browser → :5000 |
| **Raspberry Pi** | Arduino | WiFi → TCP | Socket → :8888 |
| **Raspberry Pi** | Camera | USB | /dev/usb or gphoto2 |
| **Raspberry Pi** | Capture Card | USB | /dev/video0 |
| **Arduino** | Motor Driver | GPIO | D2, D3, D4 |
| **Motor Driver** | Stepper Motor | Coil Wires | 1A/1B, 2A/2B |

## First-Time Setup: How Pi Finds Arduino

### Step 1: Arduino Broadcasts IP

When Arduino boots:

```
Arduino LED Matrix:
  1. "W" pattern → Connecting to WiFi
  2. IP scrolls → "192.168.1.100" (THIS IS WHAT YOU NEED!)
  3. Happy face → Ready for connection
```

### Step 2: Configure Pi with Arduino's IP

Edit `web_app.py`:

```python
ARDUINO_WIFI_IP = "192.168.1.100"  # The IP you saw on LED matrix
```

### Step 3: Pi Connects to Arduino

When you run `python3 web_app.py`:

```
Pi logs:
  🔌 Connecting to Arduino R4 WiFi at 192.168.1.100:8888...
  ✓ Connected to Arduino R4 WiFi at 192.168.1.100:8888
```

### Step 4: Access Web Interface

From your phone/computer:

```
http://raspberrypi.local:5000

Web interface shows:
  Arduino: Connected (R4 WiFi TCP)
  IP: 192.168.1.100:8888
```

## Network Topology

```
Your WiFi Network (192.168.1.x)
        │
        ├─ Router: 192.168.1.1
        │
        ├─ Your Device: 192.168.1.X (phone/laptop)
        │  └─ Accesses: http://raspberrypi.local:5000
        │
        ├─ Raspberry Pi: 192.168.1.50
        │  ├─ Hostname: raspberrypi.local
        │  ├─ Serves web interface on port 5000
        │  └─ Connects to Arduino on port 8888
        │
        └─ Arduino: 192.168.1.100
           └─ TCP server on port 8888
```

## Data Flow Example: Capture a Frame

```
1. You click "Capture" button in web browser
   └─→ HTTP POST to http://raspberrypi.local:5000/api/capture

2. Pi's Flask app receives request
   └─→ Calls scanner.capture_frame()

3. Pi sends motor command to Arduino via WiFi
   └─→ TCP socket to 192.168.1.100:8888
   └─→ Sends: "N\n" (advance one frame)

4. Arduino receives command, moves motor
   └─→ Sends steps to motor driver via D2 (STEP pin)
   └─→ Motor advances film one frame

5. Pi captures image from camera via USB
   └─→ Runs: gphoto2 --capture-image
   └─→ Image saved to camera's SD card

6. Web interface updates
   └─→ Shows frame count, preview, etc.
```

**Key Point:** The web interface, camera control, and image processing all happen on the Pi. Only motor control commands go to Arduino via WiFi.

## USB Port Comparison

### Before (Main Branch - USB Serial)

```
Raspberry Pi USB Ports:
  Port 1: Arduino Uno R3/R4 (motor control)
  Port 2: HDMI Capture Card (preview)
  Port 3: Canon Camera (capture)
  
Total: 3 USB ports used
```

### After (WiFi Branch - This Branch)

```
Raspberry Pi USB Ports:
  Port 1: HDMI Capture Card (preview)
  Port 2: Canon Camera (capture)
  
Total: 2 USB ports used
Arduino: Powered from 12V motor supply
```

**Result:** 1 USB port freed up! ✓

## Quick Verification Checklist

After setup, verify everything works:

- [ ] Can access web interface: `http://raspberrypi.local:5000` ✓
- [ ] Web shows Arduino connected (R4 WiFi TCP) ✓
- [ ] Camera detected (Canon DSLR listed) ✓
- [ ] Live preview works (HDMI capture card) ✓
- [ ] Motor responds to ← → buttons ✓
- [ ] Arduino LED shows happy face ✓
- [ ] No USB cable to Arduino needed ✓

## Summary

**What you need to know:**

1. 🌐 **Access scanner:** Same as before - `http://raspberrypi.local:5000`
2. 📷 **Camera & capture card:** Same as before - USB to Pi
3. 🤖 **Arduino:** Now wireless via WiFi (no USB cable)
4. 🔌 **Arduino power:** From motor's 12V supply (shared power)
5. 📡 **First connection:** Arduino displays IP on LED matrix
6. ⚙️ **Configuration:** Set Arduino IP in `wifi_config.h` and `web_app.py`

**Everything else works exactly the same!**
