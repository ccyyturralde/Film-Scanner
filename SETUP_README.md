# Setup Guide - Film Scanner Web App

Complete setup instructions for getting your Film Scanner running on Raspberry Pi.

## 🎯 Overview

This guide covers transferring files from your Windows computer to your Raspberry Pi and running the automated setup.

## 📋 What You Need

### Hardware
- ✅ Raspberry Pi (any model with WiFi/Ethernet)
- ✅ SD card with Raspberry Pi OS installed
- ✅ Power supply for Pi
- ✅ Arduino (for motor control)
- ✅ Camera (gphoto2 compatible)

### Network
- ✅ Pi connected to same network as your computer/phone
- ✅ SSH enabled on Pi (default on Raspberry Pi OS)

### Software on Pi
- ✅ Raspberry Pi OS (Lite or Desktop)
- ✅ SSH enabled (default)
- Everything else installed by setup script!

## 🚀 Quick Start (3 Methods)

### Method 1: PowerShell Transfer Script (Windows - Easiest)

**Prerequisites:**
- OpenSSH Client installed (Windows 10/11 built-in)
- Pi on same network

**Steps:**
```powershell
# In PowerShell, navigate to Film-Scanner directory
cd C:\Cursor\Film-Scanner\Film-Scanner

# Run transfer script
.\transfer_to_pi.ps1

# Follow prompts - it will:
# 1. Transfer all files to Pi
# 2. Optionally run setup automatically
```

**That's it!** The script handles everything.

### Method 2: Manual SCP (Any OS)

**Prerequisites:**
- SSH/SCP client installed

**Steps:**

**Windows PowerShell:**
```powershell
scp -r C:\Cursor\Film-Scanner\Film-Scanner pi@raspberrypi.local:~/Scanner-Web
ssh pi@raspberrypi.local
cd ~/Scanner-Web
chmod +x setup_pi.sh
./setup_pi.sh
```

**Mac/Linux:**
```bash
scp -r ~/Film-Scanner pi@raspberrypi.local:~/Scanner-Web
ssh pi@raspberrypi.local
cd ~/Scanner-Web
chmod +x setup_pi.sh
./setup_pi.sh
```

### Method 3: Git Clone (If Files Are in Git Repository)

**On your Pi:**
```bash
git clone https://github.com/yourusername/Film-Scanner.git ~/Scanner-Web
cd ~/Scanner-Web
git checkout web-mobile-version
chmod +x setup_pi.sh
./setup_pi.sh
```

## 🔧 What the Setup Script Does

The `setup_pi.sh` script automatically:

1. **Detects Network Info**
   - Finds Pi's IP address
   - Shows hostname

2. **Creates Directory Structure**
   - `~/Scanner-Web/` - Application files
   - `~/scans/` - Scan storage
   - `templates/`, `static/` - Web files

3. **Installs Dependencies**
   - System: Python3, gphoto2, git
   - Python: Flask, Flask-SocketIO, pyserial

4. **Configures System**
   - Adds user to `dialout` group (Arduino access)
   - Creates Python virtual environment
   - Sets up systemd service

5. **Creates Helper Scripts**
   - `start_scanner.sh` - Easy launcher
   - Desktop shortcut (if using desktop)
   - Connection info file

6. **Tests Hardware**
   - Checks for Arduino
   - Checks for camera
   - Reports results

7. **Shows Access Info**
   - Displays IP address
   - Shows access URLs
   - Provides quick commands

**Time Required:** 5-10 minutes (mostly downloading packages)

## 📡 After Setup

### Access URLs

The setup script will display something like:

```
Your Network Information:
  IP Address: 192.168.1.100
  Hostname:   raspberrypi

Access the Scanner:
  http://192.168.1.100:5000
  http://raspberrypi.local:5000
```

### Starting the Scanner

**Option 1: Manual (Good for testing)**
```bash
cd ~/Scanner-Web
./start_scanner.sh
```

**Option 2: Systemd Service (Runs in background)**
```bash
# Start now
sudo systemctl start film-scanner

# Enable on boot
sudo systemctl enable film-scanner

# Check status
sudo systemctl status film-scanner
```

**Option 3: Desktop Icon (If using Desktop)**
Double-click "Film Scanner" icon on desktop

### From Your Phone

1. **Connect to WiFi** (same network as Pi)
2. **Open browser**
3. **Go to:** `http://192.168.1.XXX:5000` (use your Pi's IP)
4. **Bookmark or add to home screen**

## 🛠️ Troubleshooting Setup

### Can't Find Pi on Network

**Check Pi's IP on the Pi:**
```bash
hostname -I
```

**Or use hostname:**
```
raspberrypi.local
```

**Scan network from computer:**
```bash
# Windows
arp -a

# Mac/Linux
nmap -sn 192.168.1.0/24
```

### SSH Connection Refused

**Enable SSH on Pi:**
```bash
# On Pi directly:
sudo raspi-config
# Interface Options → SSH → Enable

# Or create empty ssh file on boot partition
# (if Pi is headless)
```

### Transfer Script Fails

**Check OpenSSH is installed:**
```powershell
# Windows PowerShell
Get-Command ssh
Get-Command scp

# If not found:
# Settings → Apps → Optional Features → Add OpenSSH Client
```

**Try with IP instead of hostname:**
```powershell
.\transfer_to_pi.ps1 -PiAddress 192.168.1.100 -PiUser pi
```

### Setup Script Errors

**Check internet connection:**
```bash
ping 8.8.8.8
```

**Update package lists:**
```bash
sudo apt update
```

**Run setup again:**
```bash
cd ~/Scanner-Web
./setup_pi.sh
# Script is idempotent - safe to run multiple times
```

### Arduino Not Found After Setup

**Need to log out and back in:**
```bash
# After setup adds you to dialout group
logout
# SSH back in
```

**Check serial devices:**
```bash
ls -la /dev/ttyACM* /dev/ttyUSB*
```

**Verify group membership:**
```bash
groups
# Should show 'dialout'
```

### Camera Not Detected

**Check USB connection**

**Verify camera mode:**
- Must be in PTP/PC mode
- Not in mass storage mode

**Test gphoto2:**
```bash
gphoto2 --auto-detect
```

**Kill competing processes:**
```bash
killall gphoto2
```

## 📊 Directory Structure After Setup

```
~/Scanner-Web/                  # Installation directory
├── web_app.py                 # Flask application
├── requirements.txt           # Python dependencies
├── setup_pi.sh               # Setup script
├── start_scanner.sh          # Launcher script
├── connection_info.txt       # Your access URLs
├── venv/                     # Python virtual environment
├── templates/                # HTML templates
│   └── index.html
├── static/                   # CSS/JS files
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js
└── [documentation files]

~/scans/                      # Scan storage
└── [date]/
    └── [roll-name]/
        └── .scan_state.json

/etc/systemd/system/
└── film-scanner.service      # Systemd service
```

## 🔄 Updating Installation

**Update files:**
```bash
cd ~/Scanner-Web

# If using git:
git pull

# Or re-transfer from Windows with PowerShell script
# Or manually copy updated files
```

**Restart service:**
```bash
sudo systemctl restart film-scanner
```

**Or if running manually:**
```bash
# Press Ctrl+C to stop
# Then start again:
./start_scanner.sh
```

## 🔐 Security Notes

### Default Configuration
- ✅ Safe for home network use
- ❌ No authentication by default
- ❌ Don't expose to internet without security

### Recommended Practices
1. **Keep on local network only**
2. **Use VPN for remote access** (Tailscale, WireGuard)
3. **Set static IP for Pi** (easier to remember)
4. **Regular Pi OS updates:** `sudo apt update && sudo apt upgrade`

### If You Need Remote Access
- Use VPN (most secure)
- Or add authentication (Flask-Login)
- Or use reverse proxy with basic auth (nginx)

See RASPBERRY_PI_SETUP.md for details.

## 📱 Mobile App-Like Experience

### Add to Phone Home Screen

**iOS:**
1. Safari → your Pi URL
2. Share → Add to Home Screen
3. Name it "Film Scanner"

**Android:**
1. Chrome → your Pi URL
2. Menu → Add to Home screen
3. Name it "Film Scanner"

**Result:** Icon on home screen like a native app!

## ⚡ Performance Tips

### Raspberry Pi 4/5
- No optimization needed
- Runs smoothly

### Raspberry Pi 3
- Works great
- Consider headless mode (no desktop)

### Older Models
- Use Raspberry Pi OS Lite (no desktop)
- Disable unused services
- Preview feature may be slower

### Headless Setup (No Monitor)
```bash
# Disable desktop
sudo raspi-config
# System Options → Boot → Console Autologin

# Frees up ~200MB RAM
```

## 🎓 Learning Resources

### First Time Using Raspberry Pi?

**Basic Commands:**
```bash
# Update system
sudo apt update && sudo apt upgrade

# Check IP address
hostname -I

# Check running services
systemctl status

# View logs
journalctl -u film-scanner -f

# Reboot
sudo reboot

# Shutdown
sudo shutdown now
```

**SSH from Windows:**
```powershell
ssh pi@raspberrypi.local
# Default password: raspberry (change it!)
```

**Change Password:**
```bash
passwd
```

### Helpful Links
- Raspberry Pi Docs: https://www.raspberrypi.org/documentation/
- Raspberry Pi Forums: https://forums.raspberrypi.com/
- gphoto2 Cameras: http://gphoto.org/proj/libgphoto2/support.php

## ✅ Setup Checklist

- [ ] Pi connected to network
- [ ] SSH enabled on Pi
- [ ] Files transferred to Pi
- [ ] Setup script completed successfully
- [ ] Arduino connected via USB
- [ ] Camera connected via USB
- [ ] Camera in PTP/PC mode
- [ ] Can access web interface from computer
- [ ] Can access web interface from phone
- [ ] Bookmark saved on phone
- [ ] Desktop shortcut created (if using desktop)

## 🆘 Getting Help

### Check Documentation
1. **QUICKSTART.md** - Using the scanner
2. **README_WEB_APP.md** - Full feature guide
3. **RASPBERRY_PI_SETUP.md** - Detailed Pi instructions
4. **LIVE_PREVIEW_FEATURE.md** - Preview feature guide

### Common Issues
- Connection problems → RASPBERRY_PI_SETUP.md
- Usage questions → QUICKSTART.md
- Feature details → README_WEB_APP.md

### Information to Provide When Asking for Help
```bash
# Pi model
cat /proc/cpuinfo | grep Model

# OS version
cat /etc/os-release

# IP address
hostname -I

# Service status
sudo systemctl status film-scanner

# Recent logs
sudo journalctl -u film-scanner -n 50

# Python version
python3 --version

# gphoto2 version
gphoto2 --version
```

## 🎉 Success!

If you can access the scanner from your phone browser, you're all set!

**Next Steps:**
1. Read QUICKSTART.md for usage
2. Connect hardware (Arduino + Camera)
3. Create your first roll
4. Start scanning!

---

**Happy scanning from anywhere in your house! 📸📱**

