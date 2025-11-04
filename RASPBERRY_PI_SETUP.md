# Raspberry Pi Setup Guide

Complete guide for installing the Film Scanner Web App on your Raspberry Pi.

## 🚀 Quick Install (Recommended)

### One-Line Installation

If you have the files on your Pi already:

```bash
cd /path/to/Film-Scanner && chmod +x setup_pi.sh && ./setup_pi.sh
```

Or clone from git first:

```bash
git clone <your-repo-url> ~/Scanner-Web && cd ~/Scanner-Web && chmod +x setup_pi.sh && ./setup_pi.sh
```

### What the Setup Script Does

1. ✅ Detects your Pi's IP address automatically
2. ✅ Creates installation directory at `~/Scanner-Web`
3. ✅ Installs system dependencies (Python, gphoto2, etc.)
4. ✅ Sets up Python virtual environment
5. ✅ Installs Python packages
6. ✅ Configures serial port permissions
7. ✅ Creates systemd service
8. ✅ Creates launcher script
9. ✅ Tests camera and Arduino
10. ✅ Displays connection info

**Time Required:** ~5-10 minutes (depending on Pi model)

## 📋 Prerequisites

### Hardware
- Raspberry Pi (any model with network)
- SD card with Raspberry Pi OS
- Network connection (WiFi or Ethernet)
- Arduino (for motor control)
- Camera (gphoto2 compatible)

### Software
- Raspberry Pi OS (Lite or Desktop)
- Internet connection for downloading packages

## 🔧 Manual Setup (If Script Fails)

### Step 1: Update System
```bash
sudo apt update
sudo apt upgrade -y
```

### Step 2: Install Dependencies
```bash
sudo apt install -y python3 python3-pip python3-venv gphoto2 git
```

### Step 3: Create Directory
```bash
mkdir -p ~/Scanner-Web
cd ~/Scanner-Web
```

### Step 4: Copy Files
Copy or clone your scanner files to `~/Scanner-Web`

### Step 5: Set Up Python
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 6: Configure Permissions
```bash
sudo usermod -a -G dialout $USER
# Log out and back in after this
```

### Step 7: Test
```bash
python web_app.py
```

## 📡 Finding Your Pi's IP Address

### Method 1: On the Pi
```bash
hostname -I
```

### Method 2: From Another Computer
```bash
# Linux/Mac
ping raspberrypi.local

# Windows
ping raspberrypi
```

### Method 3: Router Admin Panel
Check your router's connected devices list

### Method 4: Network Scanner
Use an app like Fing on your phone

## 🎯 After Installation

### Starting the Scanner

**Option 1: Manual Start**
```bash
cd ~/Scanner-Web
./start_scanner.sh
```

**Option 2: Systemd Service**
```bash
# Start once
sudo systemctl start film-scanner

# Enable auto-start on boot
sudo systemctl enable film-scanner

# Check status
sudo systemctl status film-scanner

# View logs
sudo journalctl -u film-scanner -f

# Stop service
sudo systemctl stop film-scanner
```

**Option 3: Desktop Shortcut**
If using Raspberry Pi Desktop, double-click the "Film Scanner" icon on desktop

### Accessing the Web Interface

**From the Pi itself:**
```
http://localhost:5000
```

**From your phone/computer:**
```
http://192.168.1.XXX:5000
(use the IP shown during setup)
```

**Using hostname:**
```
http://raspberrypi.local:5000
```

## 📱 Mobile Access Setup

### Add to Phone Home Screen

**iOS (Safari):**
1. Open `http://pi-ip:5000` in Safari
2. Tap Share button
3. Select "Add to Home Screen"
4. Tap "Add"

**Android (Chrome):**
1. Open `http://pi-ip:5000` in Chrome
2. Tap menu (⋮)
3. Select "Add to Home screen"
4. Tap "Add"

Now you have a scanner "app" on your phone!

## 🔧 Configuration

### Change Port (from 5000)

Edit `~/Scanner-Web/web_app.py`:
```python
socketio.run(app, host='0.0.0.0', port=8080, debug=True)
```

### Auto-Start on Boot

```bash
sudo systemctl enable film-scanner
```

### Disable Auto-Start

```bash
sudo systemctl disable film-scanner
```

## 🐛 Troubleshooting

### Arduino Not Found

**Check connection:**
```bash
ls /dev/ttyACM* /dev/ttyUSB*
```

**Check permissions:**
```bash
groups
# Should include 'dialout'
```

**Add to dialout group:**
```bash
sudo usermod -a -G dialout $USER
# Log out and back in
```

### Camera Not Detected

**Check connection:**
```bash
gphoto2 --auto-detect
```

**Kill competing processes:**
```bash
sudo killall gphoto2
```

**Check camera mode:**
- Camera must be in PTP/PC mode
- Not in mass storage mode

### Can't Access from Phone

**Check firewall:**
```bash
sudo ufw status
# If active, allow port 5000
sudo ufw allow 5000
```

**Check same network:**
- Pi and phone must be on same WiFi

**Try hostname:**
```
http://raspberrypi.local:5000
```

### Port Already in Use

**Find what's using port 5000:**
```bash
sudo lsof -i :5000
```

**Kill the process:**
```bash
sudo kill <PID>
```

**Or use different port** (edit web_app.py)

### Service Won't Start

**Check logs:**
```bash
sudo journalctl -u film-scanner -n 50
```

**Check file permissions:**
```bash
cd ~/Scanner-Web
ls -la web_app.py
# Should be readable/executable
```

**Test manually:**
```bash
cd ~/Scanner-Web
source venv/bin/activate
python web_app.py
# See what error appears
```

## 💡 Performance Tips

### Raspberry Pi 4/5
- No special configuration needed
- Runs smoothly

### Raspberry Pi 3
- Works well
- May want to disable desktop for headless operation

### Raspberry Pi Zero/Zero 2
- Slower but functional
- Recommend using Lite OS (no desktop)
- Preview feature may be slower

### Optimize for Headless (No Monitor)

```bash
# Disable desktop
sudo raspi-config
# System Options → Boot → Console

# Or use Raspberry Pi OS Lite
```

## 🌐 Network Configuration

### Static IP Address (Recommended)

**Edit dhcpcd.conf:**
```bash
sudo nano /etc/dhcpcd.conf
```

**Add at the end:**
```
interface wlan0  # or eth0 for ethernet
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1 8.8.8.8
```

**Restart networking:**
```bash
sudo systemctl restart dhcpcd
```

### Remote Access (Outside Home Network)

**Option 1: VPN (Recommended)**
- Set up WireGuard or OpenVPN
- Most secure method

**Option 2: Port Forwarding**
- Forward port 5000 on router
- Security risk - not recommended

**Option 3: Tailscale**
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```
- Easy peer-to-peer VPN
- Access from anywhere securely

## 📊 System Requirements

### Minimum
- Raspberry Pi Zero 2 W
- 512MB RAM
- 4GB SD card
- WiFi or Ethernet

### Recommended
- Raspberry Pi 3B+ or newer
- 1GB+ RAM
- 16GB+ SD card (for scans)
- Wired Ethernet (more stable)

### Storage
- App size: ~50MB
- Scans stored in `~/scans`
- Plan for scan storage separately

## 🔐 Security Considerations

### Local Network Only
- Default setup is safe for home network
- No authentication by default
- Don't expose to internet without security

### Add Authentication (Advanced)

If you need to expose to internet, add authentication:

**Flask-Login example:**
```python
pip install flask-login
# Then add login system to web_app.py
```

**Or use reverse proxy:**
```bash
# Install nginx
sudo apt install nginx

# Configure with basic auth
sudo apt install apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd username
```

## 📁 File Locations

| Item | Location |
|------|----------|
| App files | `~/Scanner-Web/` |
| Virtual env | `~/Scanner-Web/venv/` |
| Scans | `~/scans/` |
| Service file | `/etc/systemd/system/film-scanner.service` |
| Connection info | `~/Scanner-Web/connection_info.txt` |
| Logs | `journalctl -u film-scanner` |

## 🔄 Updating

### Update from Git
```bash
cd ~/Scanner-Web
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart film-scanner
```

### Reinstall
```bash
cd ~/Scanner-Web
./setup_pi.sh
# Will update existing installation
```

## 🗑️ Uninstall

```bash
# Stop and disable service
sudo systemctl stop film-scanner
sudo systemctl disable film-scanner

# Remove service file
sudo rm /etc/systemd/system/film-scanner.service
sudo systemctl daemon-reload

# Remove installation
rm -rf ~/Scanner-Web

# Remove scans (optional)
# rm -rf ~/scans

# Remove from dialout group (optional)
sudo deluser $USER dialout
```

## 📚 Additional Resources

### Raspberry Pi Resources
- Official Docs: https://www.raspberrypi.org/documentation/
- Forum: https://forums.raspberrypi.com/

### gphoto2 Resources
- Supported Cameras: http://gphoto.org/proj/libgphoto2/support.php
- Documentation: http://gphoto.org/doc/

### Flask Resources
- Flask Docs: https://flask.palletsprojects.com/
- Flask-SocketIO: https://flask-socketio.readthedocs.io/

## ✅ Quick Reference

### Start Scanner
```bash
cd ~/Scanner-Web && ./start_scanner.sh
```

### Check Status
```bash
sudo systemctl status film-scanner
```

### View Logs
```bash
sudo journalctl -u film-scanner -f
```

### Restart Service
```bash
sudo systemctl restart film-scanner
```

### Test Camera
```bash
gphoto2 --auto-detect
```

### Test Arduino
```bash
ls /dev/ttyACM* /dev/ttyUSB*
```

### Get IP Address
```bash
hostname -I
```

---

**Setup complete? Access your scanner at: `http://your-pi-ip:5000`**

**Need help? Check QUICKSTART.md or README_WEB_APP.md for usage instructions!**

