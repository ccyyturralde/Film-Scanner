# Pi Reflash Complete Setup Checklist

## ✅ Pre-Reflash Preparation
- [ ] Backup any custom configuration files
- [ ] Note your WiFi credentials
- [ ] Choose a username and password you'll remember

## ✅ Reflashing Pi

### Using Raspberry Pi Imager

1. **Download Imager**: https://www.raspberrypi.com/software/
2. **Select OS**: Raspberry Pi OS Lite (64-bit) recommended
3. **Press Ctrl+Shift+X** for Advanced Options:
   ```
   ✓ Set hostname: filmscanner
   ✓ Enable SSH
   ✓ Set username: [your choice]
   ✓ Set password: [your choice - don't forget this!]
   ✓ Configure WiFi: [your network]
   ✓ Set locale: [your timezone]
   ```
4. **Write to SD card**
5. **Boot Pi** (wait 2-3 minutes for first boot)

## ✅ Installation (Choose ONE method)

### Method 1: Automated One-Line Install (Easiest)

```bash
# SSH into Pi
ssh pi@filmscanner.local

# Run installer
curl -sSL https://raw.githubusercontent.com/ccyyturralde/Film-Scanner/Web-app-automated-edge-detection/scripts/install.sh | bash
```

### Method 2: Manual Git Clone + Setup

```bash
# SSH into Pi
ssh pi@filmscanner.local

# Clone and setup
git clone -b Web-app-automated-edge-detection https://github.com/ccyyturralde/Film-Scanner.git
cd Film-Scanner
sudo bash scripts/setup_pi.sh
```

## ✅ What Gets Installed

The setup script (`setup_pi.sh`) installs **EVERYTHING** you need:

### System Packages
- [x] Python 3 + pip + venv + dev tools
- [x] gphoto2 (camera control)
- [x] FFmpeg (video/image processing)
- [x] OpenCV dependencies (libjpeg, libtiff, libpng, libfreetype, libatlas)
- [x] SDL2 libraries (for pygame/touchscreen)
- [x] Fonts (DejaVu)
- [x] Git, rsync, avahi-daemon

### Python Packages (in virtual environment)
- [x] Flask >= 2.3.0 (web framework)
- [x] Flask-SocketIO >= 5.3.0 (real-time updates)
- [x] **OpenCV >= 4.8.0** (for automatic alignment improvements)
- [x] **NumPy >= 1.24.0** (for alignment calculations)
- [x] Pillow >= 10.0.0 (image processing)
- [x] pyserial >= 3.5 (Arduino communication)
- [x] pygame >= 2.5.0 (touchscreen UI)
- [x] evdev >= 1.6.0 (touch input)
- [x] psutil >= 5.9.0 (system monitoring)

### Application Setup
- [x] Copies application to `/opt/film-scanner`
- [x] Creates virtual environment with `--system-site-packages`
- [x] Installs all Python dependencies
- [x] **Verifies all imports work** (new!)
- [x] Sets up hardware permissions (dialout, video, input, gpio groups)
- [x] Creates data directories (`~/scans`, `~/.film_scanner`)
- [x] Creates default config files

### Services
- [x] `film-scanner.service` - Web application
- [x] `film-scanner-touchscreen.service` - TFT UI (optional)
- [x] Both configured for auto-start
- [x] Auto-restart on failure

### Helper Commands
- [x] `start-scanner` / `stop-scanner`
- [x] `start-touchscreen` / `stop-touchscreen`
- [x] `film-scanner` - Main CLI command
- [x] `scanner-run` - Run scripts with venv Python

## ✅ Post-Installation Verification

Run the verification script:

```bash
cd Film-Scanner  # or /opt/film-scanner
bash scripts/verify_install.sh
```

This checks:
- [x] Virtual environment
- [x] All Python dependencies
- [x] System packages (gphoto2, ffmpeg)
- [x] Hardware permissions
- [x] Serial ports (Arduino)
- [x] Camera detection
- [x] Network configuration
- [x] Systemd services
- [x] Data directories
- [x] **Alignment system** (frame detector module)

## ✅ First-Time Configuration

### 1. Flash Arduino

```bash
cd Film-Scanner
./scripts/flash_arduino.sh
```

### 2. Start Web Interface

```bash
start-scanner

# Or manually
python3 web_app.py
```

### 3. Access Web UI

Open browser to: **http://filmscanner.local:5000**

Or use IP address: **http://192.168.x.x:5000**

### 4. Configuration Wizard

On first launch, the web app will ask:
- Deployment mode (choose "Raspberry Pi")
- Pi IP (auto-detected)
- Port (default: 5000)

### 5. Connect Hardware

- **Arduino**: Plug in via USB → Check status in web UI
- **Camera**: Turn ON, set to PTP mode → Check status in web UI
- **Capture Card**: Plug in (for alignment preview)

## ✅ Testing Automatic Alignment

The new alignment improvements are included! Test them:

```bash
# Test with an image file
python3 test_alignment.py path/to/test/image.jpg

# Or capture from camera
python3 test_alignment.py
```

**Expected results:**
- ✓ 90-99% confidence (was 80%)
- ✓ Gaps cleared on both edges
- ✓ Detailed logging showing gap widths
- ✓ Visualization showing detected gaps

## ✅ Alignment Features Included

Your system now has:
- **Multi-pass edge detection** - 8 passes with adaptive thresholds
- **Three detection methods** - Traditional, uniformity-first, adaptive percentile
- **Smart fine-tuning** - Progressive step adjustment (2.0x → 1.5x → 1.2x)
- **Accurate confidence** - 75-99% based on actual alignment quality
- **Better logging** - Shows gap widths and pass-by-pass progress

All dependencies are already installed by `setup_pi.sh`:
- ✓ OpenCV (cv2)
- ✓ NumPy
- ✓ frame_detector module
- ✓ All Flask dependencies

## ✅ Quick Command Reference

```bash
# Service control
start-scanner                     # Start web app
stop-scanner                      # Stop web app
start-touchscreen                 # Start TFT UI
stop-touchscreen                  # Stop TFT UI

# Direct commands
film-scanner web                  # Run web app
film-scanner touch                # Run touchscreen UI  
film-scanner status               # Check status
film-scanner calibrate            # Touch calibration

# Logs
journalctl -u film-scanner -f    # Web app logs
journalctl -u film-scanner-touchscreen -f  # Touchscreen logs

# Testing
bash scripts/verify_install.sh   # Verify installation
python3 test_alignment.py <img>  # Test alignment

# Configuration
python3 web_app.py --reset        # Reset configuration
python3 web_app.py --config       # Show configuration
```

## ✅ Troubleshooting

### Can't SSH to Pi
```bash
# Find Pi on network
sudo nmap -sn 192.168.1.0/24 | grep filmscanner

# Or check your router for "filmscanner"
```

### Permission Denied on Serial
```bash
sudo usermod -a -G dialout $USER
# Then logout/login or reboot
```

### Camera Not Detected
1. Check camera is ON
2. Set USB mode to PTP (not Mass Storage)
3. Test: `gphoto2 --auto-detect`

### Dependency Errors
```bash
# Reinstall packages
cd /opt/film-scanner
sudo -u pi .venv/bin/pip install -r requirements.txt --force-reinstall
```

### Service Won't Start
```bash
# Check logs
journalctl -u film-scanner -n 50 --no-pager

# Restart
sudo systemctl restart film-scanner
```

### Alignment Not Working
```bash
# Verify dependencies
python3 -c "import cv2, numpy; print('OK')"

# Test detector
python3 test_detector.py

# Check logs for alignment attempts
journalctl -u film-scanner | grep "align"
```

## ✅ All Files You Need

Everything is in the repository:

```
Film-Scanner/
├── web_app.py                      # Main web application
├── frame_detector.py               # Alignment detection (ENHANCED)
├── test_alignment.py               # Test alignment (NEW)
├── requirements.txt                # Python dependencies
├── scripts/
│   ├── setup_pi.sh                 # Comprehensive setup (UPDATED)
│   ├── verify_install.sh           # Verification script (NEW)
│   ├── flash_arduino.sh            # Arduino flasher
│   └── install.sh                  # One-line installer
├── arduino/film_scanner/           # Arduino firmware
├── docs/                           # Documentation
├── QUICK_START_AFTER_REFLASH.md   # Quick start guide (NEW)
├── ALIGNMENT_IMPROVEMENTS.md       # Alignment docs (NEW)
└── REFLASH_CHECKLIST.md           # This file (NEW)
```

## ✅ Network Access

Access the scanner from any device:

| Device | URL |
|--------|-----|
| Pi itself | http://localhost:5000 |
| Computer on same network | http://filmscanner.local:5000 |
| Phone on same network | http://192.168.x.x:5000 |

**Note**: `.local` addresses require mDNS support (built-in on Mac/iOS, Bonjour on Windows)

## ✅ Backup After Setup

```bash
# Backup configuration
cp ~/.film_scanner/config.json ~/config_backup.json

# Backup entire setup (for easy restore)
cd ~
tar -czf film-scanner-backup.tar.gz Film-Scanner .film_scanner

# Copy to your computer
scp pi@filmscanner.local:~/film-scanner-backup.tar.gz .
```

## ✅ Update in Future

```bash
cd Film-Scanner  # or /opt/film-scanner
git pull
sudo bash scripts/setup_pi.sh
sudo systemctl restart film-scanner
```

---

## 🎉 You're Done!

Your film scanner is fully set up with:
- ✅ All system dependencies
- ✅ All Python packages  
- ✅ Enhanced automatic alignment (90-99% confidence)
- ✅ Web interface
- ✅ Arduino firmware
- ✅ Optional touchscreen support
- ✅ Auto-start services
- ✅ Helper commands

**Start scanning:** http://filmscanner.local:5000

**Questions?** Check the docs in `/docs` or run `bash scripts/verify_install.sh`
