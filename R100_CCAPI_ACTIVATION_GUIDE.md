# Canon R100 CCAPI Activation Guide

## ⚠️ CRITICAL: CCAPI Must Be Enabled First

Your Canon R100 supports the Camera Control API (CCAPI), but it's **not enabled by default**. You must activate it using Canon's desktop software before it will work with the film scanner.

---

## Step-by-Step CCAPI Activation

### Prerequisites:
- Canon R100 with latest firmware
- Windows or Mac computer
- USB cable
- Internet connection

### Step 1: Update Camera Firmware

1. **Check current firmware:**
   - Camera: MENU → Setup → Firmware version
   - Note the version number

2. **Download latest firmware:**
   - Visit: https://www.canon.com/support
   - Search for "EOS R100"
   - Download latest firmware if update available

3. **Install firmware update:**
   - Follow Canon's firmware update instructions
   - This usually involves copying firmware to SD card and running update from camera

### Step 2: Download Canon EOS Utility

1. **Download EOS Utility:**
   - Visit: https://www.canon.com/support
   - Search: "EOS R100"
   - Download: **EOS Utility** software (NOT Camera Connect app)
   - Available for Windows and macOS

2. **Install EOS Utility:**
   - Run the installer
   - Follow on-screen instructions
   - Restart computer if prompted

### Step 3: Activate CCAPI

1. **Connect camera to computer:**
   - Use USB cable
   - Turn camera ON
   - Set camera to PC connection mode

2. **Launch EOS Utility:**
   - Open EOS Utility application
   - Camera should be detected automatically

3. **Enable CCAPI:**
   - In EOS Utility, look for:
     - **Camera Settings** or **Preferences**
     - **Enable Remote API** or **Enable CCAPI**
   - Check the box to enable CCAPI
   - Apply/Save settings

4. **Verify on camera:**
   - After activation, go to: MENU → Wireless settings
   - You should now see a **new menu option** for CCAPI or Remote Control
   - This confirms CCAPI is activated

### Step 4: Configure Camera WiFi for CCAPI

1. **On camera: MENU → Wireless settings**

2. **Choose connection type:**
   
   **Option A: Infrastructure Mode (Recommended)**
   - Select: **Connect to Network** (not smartphone)
   - Choose your WiFi network (same as Pi)
   - Enter WiFi password
   - Camera will get IP address from router
   
   **Option B: Access Point Mode**
   - Select: **Camera Access Point Mode**
   - Note: This creates a WiFi network from the camera
   - Pi must connect to camera's network (will lose internet/SSH access)

3. **Enable Remote Control:**
   - Look for: **Remote Control** or **PC Remote**
   - Enable it
   - This puts camera in CCAPI mode

---

## Recommended Setup: Infrastructure Mode

**Why:** Allows Pi to maintain internet/SSH access while connected to camera.

### Setup Process:

1. **Camera WiFi Settings:**
   ```
   MENU → Wireless Settings → WiFi/Bluetooth Connection
   → Connect to Network (Infrastructure)
   → Select your WiFi network
   → Enter password
   → Enable Remote Control
   ```

2. **Find Camera IP:**
   ```
   MENU → Wireless Settings → WiFi Details
   Note the IP address (e.g., 192.168.1.50)
   ```

3. **Verify from Pi:**
   ```bash
   # SSH into Pi
   ping <camera_ip>
   
   # Test CCAPI endpoint
   curl http://<camera_ip>:8080/ccapi
   ```

4. **Run Film Scanner:**
   ```bash
   cd ~/Film-Scanner
   python3 web_app.py
   ```

5. **Setup Canon WiFi in web interface:**
   - Open: http://Scanner.local:5000
   - Click: "Setup Canon WiFi"
   - Enter camera IP address
   - Should connect successfully!

---

## Alternative: Access Point Mode

**⚠️ Warning:** Using camera as access point will disconnect Pi from your home network.

### Setup Process:

1. **Camera WiFi Settings:**
   ```
   MENU → Wireless Settings → WiFi/Bluetooth Connection
   → Camera Access Point Mode
   Note SSID and password displayed
   ```

2. **Connect Pi to Camera WiFi:**
   ```bash
   # From Pi terminal:
   sudo nmcli dev wifi connect "<camera_ssid>" password "<camera_password>"
   ```

3. **Camera IP in AP mode:**
   - Usually: `192.168.50.10` or `192.168.1.1`
   - Check camera menu for exact IP

4. **Test connection:**
   ```bash
   ping 192.168.50.10
   curl http://192.168.50.10:8080/ccapi
   ```

5. **Run scanner:**
   ```bash
   python3 web_app.py
   ```

6. **Access web interface:**
   - You can't use Scanner.local anymore (no network DNS)
   - Use Pi's new IP on camera network
   - Check with: `ip addr show wlan0`
   - Access: `http://<pi_ip>:5000` from another device on camera network

**Limitation:** You'll lose SSH access from your main network. Consider using Infrastructure Mode instead.

---

## Troubleshooting

### Issue: Can't Find CCAPI Option in EOS Utility

**Solutions:**
1. Ensure you downloaded **EOS Utility** (not Camera Connect app)
2. Update EOS Utility to latest version
3. Check Canon's developer site for CCAPI activation tool
4. Some versions may have CCAPI under:
   - Remote Shooting → Settings
   - Camera Settings → Communication Settings
   - Tools → Enable API Access

### Issue: CCAPI Activation Tool Not in EOS Utility

Canon may provide a separate CCAPI activation tool:

1. Visit: https://developercommunity.canon.com/
2. Look for: "CCAPI Activation Tool" or "Camera Control API"
3. Download and run the activation utility
4. Follow instructions to enable CCAPI on R100

**Alternative:** Check Canon forums or contact Canon support for CCAPI activation instructions specific to R100.

### Issue: Camera Says "Waiting for Smartphone"

This means camera is in **Camera Connect mode** (for Canon's smartphone app), NOT CCAPI mode.

**Fix:**
1. Disconnect from smartphone mode
2. Go to: MENU → Wireless → Remote Control (PC)
3. Select the PC/Remote Control option (not smartphone)
4. This enables CCAPI mode

### Issue: Connection Refused on Port 8080

**Check:**
1. Camera is in Remote Control mode (not smartphone mode)
2. CCAPI is actually activated on camera
3. Firewall isn't blocking port 8080:
   ```bash
   # On Pi:
   telnet <camera_ip> 8080
   ```
4. Camera and Pi are on same network/subnet

### Issue: Auto-scan Fails Even with Correct IP

**Try manual connection test:**
```bash
# SSH into Pi
cd ~/Film-Scanner

# Test Python requests directly
python3 << 'EOF'
import requests
import urllib3
urllib3.disable_warnings()

camera_ip = "192.168.1.50"  # Change to your camera IP
url = f"http://{camera_ip}:8080/ccapi"

try:
    response = requests.get(url, timeout=5, verify=False)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
EOF
```

If this returns an error, CCAPI isn't enabled or camera isn't in right mode.

### Issue: Using Access Point Mode - Lost Network Access

**Solutions:**
1. Use Infrastructure Mode instead (recommended)
2. If must use AP mode:
   - Access Pi via direct connection (monitor/keyboard)
   - Or set up Pi to act as bridge/router
   - Or use USB connection for Pi access

---

## Testing CCAPI Connection

### Quick Test Script:

Save as `test_ccapi.py`:
```python
#!/usr/bin/env python3
import requests
import urllib3
urllib3.disable_warnings()

camera_ip = input("Enter camera IP: ")
url = f"http://{camera_ip}:8080/ccapi/ver100/deviceinformation"

print(f"\nTesting CCAPI connection to {camera_ip}...")

try:
    response = requests.get(url, timeout=5, verify=False)
    
    if response.status_code == 200:
        info = response.json()
        print("\n✓ CCAPI CONNECTION SUCCESSFUL!")
        print(f"Camera: {info.get('productname', 'Unknown')}")
        print(f"Firmware: {info.get('firmwareversion', 'Unknown')}")
        print("\nYou can now use Canon WiFi in the film scanner!")
    else:
        print(f"\n✗ CCAPI responded but with error: {response.status_code}")
        print("Check camera is in Remote Control mode, not smartphone mode")
except requests.exceptions.ConnectionError:
    print(f"\n✗ Cannot connect to {camera_ip}:8080")
    print("Possible issues:")
    print("  1. Camera not on network or wrong IP")
    print("  2. CCAPI not enabled on camera")
    print("  3. Camera in smartphone mode instead of PC/Remote mode")
except Exception as e:
    print(f"\n✗ Error: {e}")
```

Run:
```bash
python3 test_ccapi.py
```

---

## Summary Checklist

Before using Canon WiFi with film scanner:

- [ ] Camera firmware updated to latest
- [ ] EOS Utility installed on computer
- [ ] CCAPI activated via EOS Utility
- [ ] Camera WiFi enabled and connected to network
- [ ] Camera in **Remote Control/PC mode** (NOT smartphone mode)
- [ ] Camera IP address known
- [ ] Can ping camera from Pi
- [ ] Can access `http://<camera_ip>:8080/ccapi` from Pi
- [ ] test_ccapi.py script succeeds

Once all checkboxes complete, Canon WiFi will work in the film scanner!

---

## Support Resources

- **Canon Support:** https://www.canon.com/support
- **EOS Utility Download:** Search "EOS R100 EOS Utility" on Canon support
- **CCAPI Documentation:** Canon Developer Community
- **Firmware Updates:** Canon support site → EOS R100

---

## If CCAPI Can't Be Enabled

If you cannot enable CCAPI (due to firmware limitations or other issues), alternatives:

### Option 1: USB Only (No WiFi Live View)
- Use gphoto2 for everything
- No live view (use camera screen)
- Autofocus and capture via USB
- Most reliable, no WiFi needed

### Option 2: HDMI Capture Card
- See `CAMERA_OPTIONS.md` for details
- $20-30 USB HDMI capture device
- Gives 30 FPS live view
- Works with any camera

### Option 3: Screen Mirroring
- Use camera's built-in screen
- Position film manually without live view
- Use USB for control

Contact me if you need help with alternative solutions!

