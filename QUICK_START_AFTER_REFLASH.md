# Quick Start After Pi Reflash

## Step 1: Flash Raspberry Pi OS

Use Raspberry Pi Imager with **Advanced Options** (Ctrl+Shift+X):

- **OS**: Raspberry Pi OS Lite (64-bit) recommended
- **Hostname**: `filmscanner`
- **Username**: Your choice (e.g., `pi`)
- **Password**: Your choice
- **WiFi**: Configure your network
- **SSH**: Enable SSH
- **Locale**: Set timezone

## Step 2: Initial Connection

```bash
# SSH into your Pi
ssh pi@filmscanner.local

# Or use the IP address
ssh pi@192.168.x.x
```

## Step 3: One-Line Installation

Run the automated installer that handles everything:

```bash
curl -sSL https://raw.githubusercontent.com/ccyyturralde/Film-Scanner/Web-app-automated-edge-detection/scripts/install.sh | bash
```

**OR** if you prefer manual control:

```bash
# Clone repository
git clone -b Web-app-automated-edge-detection https://github.com/ccyyturralde/Film-Scanner.git
cd Film-Scanner

# Run comprehensive setup
sudo bash scripts/setup_pi.sh
```

The `setup_pi.sh` script will:
- ✓ Install all system packages (gphoto2, OpenCV dependencies, etc.)
- ✓ Install Python packages (Flask, OpenCV, NumPy, pygame, etc.)
- ✓ Create virtual environment with all dependencies
- ✓ Set up systemd services for auto-start
- ✓ Configure hardware permissions (serial, video, input groups)
- ✓ Optionally configure TFT touchscreen
- ✓ Create helper commands (`start-scanner`, `film-scanner`, etc.)

## Step 4: Flash Arduino

```bash
cd ~/Film-Scanner
./scripts/flash_arduino.sh
```

The script will:
- Detect your Arduino (R3/R4 supported)
- Flash the film scanner firmware
- Verify communication

## Step 5: Start Scanner

```bash
# Start web interface (will auto-start on boot)
start-scanner

# Or manually
python3 web_app.py
```

Access at: **http://filmscanner.local:5000** or **http://\<pi-ip\>:5000**

## Optional: Touchscreen Setup

If you have a 3.5" TFT touchscreen:

```bash
# The setup_pi.sh script will ask about this
# Or run manually:
sudo bash scripts/setup_touchscreen.sh
```

## Quick Reference Commands

After installation, these commands are available:

```bash
# Web app control
start-scanner              # Start web interface
stop-scanner               # Stop web interface

# Touchscreen control
start-touchscreen          # Start TFT UI
stop-touchscreen           # Stop TFT UI

# Direct commands
film-scanner web           # Run web app directly
film-scanner touch         # Run touchscreen UI
film-scanner status        # Check service status
film-scanner calibrate     # Touch calibration tool

# Service logs
journalctl -u film-scanner -f                  # Web app logs
journalctl -u film-scanner-touchscreen -f      # Touchscreen logs
```

## Verification Checklist

After setup, verify everything works:

- [ ] SSH connection works
- [ ] Web interface loads at http://filmscanner.local:5000
- [ ] Arduino detected (check web interface status)
- [ ] Camera detected (check web interface status)
- [ ] Can capture preview image
- [ ] Auto-alignment works (new improvements!)
- [ ] Can capture test photo to camera SD card

## Alignment Improvements

Your system now includes enhanced automatic alignment:
- **Multi-pass edge detection** (8 passes with adaptive thresholds)
- **Confidence scoring** (90-99% instead of stuck at 80%)
- **Better gap detection** (3 methods: traditional, uniformity-first, adaptive)
- **Improved fine-tuning** (progressive step adjustment)

Test alignment with:
```bash
python3 test_alignment.py path/to/test/image.jpg
```

## Troubleshooting

### SSH Connection Issues
```bash
# Find Pi IP address on router
# Or use:
sudo nmap -sn 192.168.1.0/24 | grep filmscanner
```

### Permission Denied on Serial Port
```bash
sudo usermod -a -G dialout $USER
# Then logout/login or reboot
```

### Camera Not Detected
```bash
# Check camera connection
gphoto2 --auto-detect

# Check USB mode on camera (should be PTP or MTP, not Mass Storage)
```

### Python Package Issues
```bash
# Reinstall packages in virtual environment
cd /opt/film-scanner
sudo -u pi .venv/bin/pip install -r requirements.txt --force-reinstall
```

### Service Won't Start
```bash
# Check logs
journalctl -u film-scanner -n 50

# Restart service
sudo systemctl restart film-scanner
```

## Complete Dependency List

The setup script installs:

**System Packages:**
- gphoto2 (camera control)
- Python 3 + pip + venv
- OpenCV dependencies (libjpeg, libtiff, libpng, libfreetype)
- SDL2 libraries (for pygame/touchscreen)
- FFmpeg
- Serial tools

**Python Packages:**
- Flask >= 2.3.0 (web framework)
- Flask-SocketIO >= 5.3.0 (real-time updates)
- OpenCV >= 4.8.0 (image processing for alignment)
- NumPy >= 1.24.0 (array operations)
- Pillow >= 10.0.0 (image handling)
- pyserial >= 3.5 (Arduino communication)
- pygame >= 2.5.0 (touchscreen UI)
- evdev >= 1.6.0 (touch input)
- psutil >= 5.9.0 (system monitoring)

**All dependencies for the new alignment improvements are included!**

## Post-Installation Configuration

### First-Time Web App Launch

The web app will run a configuration wizard on first launch:
1. Choose deployment mode (Pi, Computer, or Custom)
2. Set Pi IP address (auto-detected on Pi)
3. Set port (default: 5000)
4. Configuration saved to `~/.film_scanner/config.json`

To reconfigure later:
```bash
python3 web_app.py --reset
```

### Alignment ROI Configuration

After first preview:
```bash
# Auto-detect lit region (recommended)
curl -X POST http://localhost:5000/api/detect_alignment_roi

# Or set manually in web interface
# Settings → Alignment → Set ROI
```

## Performance Tips

For best alignment performance:
- Use good lighting (LED backlight)
- Keep lens clean
- Ensure film is flat
- Use alignment preview to verify before scanning
- Monitor confidence scores (aim for 90%+)

## Backup Important Files

After configuration:
```bash
# Backup config
cp ~/.film_scanner/config.json ~/config_backup.json

# Backup scans
rsync -av ~/scans/ /path/to/backup/
```

## Network Access

The web interface is accessible from any device on your network:
- **From Pi**: http://localhost:5000
- **From computer**: http://filmscanner.local:5000
- **From phone**: http://\<pi-ip\>:5000

**Note**: `.local` addresses require mDNS/Bonjour support on the client device.

## Update to Latest Version

```bash
# /opt/film-scanner is a COPY (no .git). Use a clone in your home directory:
cd ~/Film-Scanner   # or clone first: git clone https://github.com/ccyyturralde/Film-Scanner.git ~/Film-Scanner
git pull
sudo bash scripts/update_pi.sh   # syncs to /opt and restarts service
```

---

### Updating the app on the Pi

**Important:** `/opt/film-scanner` is an install copy (no git). Don't run `git pull` there.

- **If you already have a clone** (e.g. `~/Film-Scanner`):
  ```bash
  cd ~/Film-Scanner && git pull && sudo bash scripts/update_pi.sh
  ```
- **If you don't have a clone yet:**
  ```bash
  cd ~ && git clone https://github.com/ccyyturralde/Film-Scanner.git
  cd Film-Scanner && sudo bash scripts/setup_pi.sh
  ```
  For later updates, use the first set of commands from your home-directory clone.

### Web app won't load after reboot

1. **Check if the service is running**
   ```bash
   sudo systemctl status film-scanner.service
   ```
2. **See why it failed** (last 80 lines of log; look for "❌ Film Scanner failed to start" and the traceback below it)
   ```bash
   journalctl -u film-scanner.service -n 80 --no-pager
   ```
3. **Try starting the app manually** (to see errors in the terminal)
   ```bash
   cd /opt/film-scanner   # or your clone path
   .venv/bin/python web_app.py
   ```
4. **If config is missing or broken**, reset and re-run setup:
   ```bash
   .venv/bin/python web_app.py --reset
   # then run again to go through setup
   .venv/bin/python web_app.py
   ```

---

**Need help?** Check the full documentation in the `/docs` folder or logs via `journalctl`.
