# Smart Startup System

## Overview

The Film Scanner now features a **Smart Startup System** that automatically configures your Raspberry Pi connection on first launch. This eliminates the need to manually configure IP addresses every time you set up the application.

## Key Features

🚀 **Auto-Discovery**: Automatically scans your network to find Raspberry Pi devices  
💾 **Persistent Storage**: Configuration saved locally and reused automatically  
🔄 **Easy Reset**: Clear configuration anytime to reconfigure  
🔧 **Flexible Setup**: Choose auto-discovery, manual entry, or localhost  
📱 **Two Interfaces**: Both web app and CLI app share the same configuration  
🔒 **Git-Friendly**: Configuration files ignored by git for security  

## Quick Start

### First Launch

1. **Clone the repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/film-scanner.git
   cd film-scanner/Film-Scanner
   ```

2. **Install dependencies** (if not already done):
   ```bash
   pip install -r requirements.txt
   ```

3. **Launch the application**:
   
   **Option A: Using the launcher (recommended)**
   ```bash
   # On Windows
   launch_scanner.bat
   
   # On Linux/Mac/Pi
   ./launch_scanner.sh
   ```
   
   **Option B: Direct launch**
   ```bash
   # Web Application
   python3 web_app.py
   
   # CLI Application
   python3 "scanner_app_v3 test.py"
   ```

4. **Follow the setup wizard** on first launch:
   - Choose auto-discovery to scan for your Pi
   - Or manually enter the Pi's IP address
   - Configuration is saved automatically

5. **Done!** Future launches will use the saved configuration.

## Usage Scenarios

### Scenario 1: Running on Your Computer (Remote Control)

**First Time:**
```bash
python3 web_app.py
```

The setup wizard will appear:
```
============================================================
   FILM SCANNER - FIRST TIME SETUP
============================================================

Welcome! Let's configure your Film Scanner.

💻 Running on external device - Remote Mode

How would you like to find your Raspberry Pi?

1. Auto-discover Pi on network (recommended)
2. Manually enter Pi IP address
3. Skip (use localhost - for testing only)

Enter your choice (1-3): 1

🔍 Scanning network for Raspberry Pi devices...
This may take a moment...

✓ Found: 192.168.1.100 (raspberrypi.local)

✓ Configuration saved!
```

**Subsequent Launches:**
```bash
python3 web_app.py
```

No setup needed! The app loads your saved configuration:
```
============================================================
   FILM SCANNER WEB APPLICATION
============================================================

📍 Mode: remote
📍 Pi IP: 192.168.1.100
📍 Port: 5000

🔌 Searching for Arduino...
✓ Arduino connected

============================================================
   WEB SERVER STARTING
============================================================

🌐 Access the scanner at:
   • Local:  http://localhost:5000
   • Network: http://192.168.1.100:5000
```

### Scenario 2: Running Directly on Raspberry Pi

When you run the application directly on the Pi, it automatically detects this and uses local mode:

```
============================================================
   FILM SCANNER - FIRST TIME SETUP
============================================================

Welcome! Let's configure your Film Scanner.

📟 Running on Raspberry Pi - Local Mode

✓ Configuration saved!
  Pi IP: 192.168.1.100
  Hostname: raspberrypi
```

### Scenario 3: Fresh Install from GitHub

When you pull the repository fresh from GitHub:

1. **Clone repository** → No configuration file present (ignored by `.gitignore`)
2. **First launch** → Setup wizard runs automatically
3. **Configure once** → Settings saved locally
4. **Pull updates** → Configuration preserved, only code updates
5. **Need to reconfigure?** → Use `--reset` flag

## Command Reference

### Launch Applications

```bash
# Web Application
python3 web_app.py

# CLI Application
python3 "scanner_app_v3 test.py"

# Using launcher (interactive menu)
./launch_scanner.sh          # Linux/Mac/Pi
launch_scanner.bat           # Windows
```

### View Configuration

```bash
# Web app config
python3 web_app.py --config

# CLI app config
python3 "scanner_app_v3 test.py" --config
```

Output:
```
============================================================
   CURRENT CONFIGURATION
============================================================

Mode: remote
Pi IP: 192.168.1.100
Hostname: raspberrypi.local
Port: 5000
Config file: /home/username/.film_scanner/scanner_config.json
============================================================
```

### Reset Configuration

```bash
# Web app reset
python3 web_app.py --reset

# CLI app reset
python3 "scanner_app_v3 test.py" --reset
```

Or manually delete:
```bash
rm -rf ~/.film_scanner/
```

### Standalone Config Manager

```bash
# Run setup wizard only
python3 config_manager.py --setup

# Show current config
python3 config_manager.py --show

# Reset configuration
python3 config_manager.py --reset
```

## Configuration File

### Location
```
~/.film_scanner/scanner_config.json
```

On Windows:
```
C:\Users\YourUsername\.film_scanner\scanner_config.json
```

### Structure

```json
{
  "setup_complete": true,
  "setup_date": "/home/username",
  "mode": "remote",
  "pi_ip": "192.168.1.100",
  "hostname": "raspberrypi.local",
  "port": 5000
}
```

### Configuration Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `local` | Running on the Pi itself | Direct Pi operation |
| `remote` | Running on external device | Laptop/desktop control |

## Auto-Discovery

The auto-discovery feature scans your local network to find Raspberry Pi devices.

### How It Works

1. **Network Detection**: Finds your local network range
2. **IP Scanning**: Pings all addresses in the range
3. **Hostname Check**: Identifies devices with "raspberry" or "pi" in hostname
4. **Connection Test**: Verifies the device is reachable
5. **User Selection**: If multiple Pis found, you choose which one

### Requirements for Auto-Discovery

✅ Both devices on same local network  
✅ ICMP (ping) enabled on network  
✅ Raspberry Pi has recognizable hostname  
✅ Pi is powered on and connected  

### If Auto-Discovery Doesn't Work

1. **Use Manual Entry**: Choose option 2 in setup
2. **Find Pi IP manually**: Run on the Pi:
   ```bash
   hostname -I
   ```
3. **Check network**: Ensure same subnet
4. **Check firewall**: Disable temporarily to test

## Network Setup Tips

### Recommended: Static IP for Raspberry Pi

Set a static IP on your Pi for consistent connections:

**Edit `/etc/dhcpcd.conf` on the Pi:**
```bash
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1 8.8.8.8
```

Or reserve the IP in your router's DHCP settings.

### Set a Recognizable Hostname

```bash
# On the Raspberry Pi
sudo hostnamectl set-hostname film-scanner
```

This makes auto-discovery easier.

## Troubleshooting

### Issue: "No Raspberry Pi devices found automatically"

**Solutions:**
- Check both devices are on same network
- Try manual entry with IP address
- Verify Pi is powered on: `ping <pi-ip>`
- Check router allows device discovery

### Issue: "Connection test failed"

**Solutions:**
- Verify IP address is correct
- Check Pi is running and accessible
- Test with: `ping <pi-ip>`
- Disable firewall temporarily
- Ensure Pi is on network

### Issue: "Configuration file error"

**Solutions:**
```bash
# Delete corrupted config
rm -rf ~/.film_scanner/

# Restart application
python3 web_app.py
```

### Issue: "Can't write to config file"

**Solutions:**
```bash
# Check directory exists and is writable
mkdir -p ~/.film_scanner
chmod 755 ~/.film_scanner

# Check file permissions if file exists
ls -la ~/.film_scanner/
```

## Advanced Usage

### Multiple Raspberry Pi Devices

If you have multiple Pis and want to switch between them:

1. **View current config**:
   ```bash
   python3 web_app.py --config
   ```

2. **Reset to choose different Pi**:
   ```bash
   python3 web_app.py --reset
   python3 web_app.py  # Run setup again
   ```

### Custom Port Configuration

During setup, you can specify a custom port:
```
Web server port (default: 5000): 8080
```

### Manual Configuration Creation

For automation or advanced setups:

```bash
mkdir -p ~/.film_scanner

cat > ~/.film_scanner/scanner_config.json << 'EOF'
{
  "setup_complete": true,
  "setup_date": "2024-01-01",
  "mode": "remote",
  "pi_ip": "192.168.1.100",
  "hostname": "raspberrypi.local",
  "port": 5000
}
EOF
```

## Security Considerations

### Configuration File Security

- Config files stored in user home directory (not in repo)
- `.gitignore` prevents accidental commits
- Only contains IP addresses and port numbers
- No passwords or sensitive data stored

### Network Security

- Connections only on local network
- No external internet connections required
- Web server binds to all interfaces (0.0.0.0) for LAN access
- Consider firewall rules for production use

## Integration with Existing Workflow

The smart startup system integrates seamlessly:

✅ **Backward Compatible**: All existing features work unchanged  
✅ **Non-Intrusive**: Only adds configuration layer  
✅ **Optional**: Can bypass by using localhost  
✅ **Maintainable**: Easy to reset and reconfigure  
✅ **Documented**: Comprehensive guides provided  

## File Structure

```
Film-Scanner/
├── config_manager.py          # Configuration management module
├── web_app.py                 # Web application (updated)
├── scanner_app_v3 test.py     # CLI application (updated)
├── launch_scanner.sh          # Linux/Mac launcher
├── launch_scanner.bat         # Windows launcher
├── SMART_STARTUP_README.md    # This file
├── STARTUP_GUIDE.md           # Detailed startup guide
└── .gitignore                 # Updated to ignore config files
```

Configuration stored at:
```
~/.film_scanner/
└── scanner_config.json        # User's configuration
```

## Examples

### Example 1: First-Time Setup with Auto-Discovery

```bash
$ python3 web_app.py

============================================================
   FILM SCANNER - FIRST TIME SETUP
============================================================

Welcome! Let's configure your Film Scanner.

💻 Running on external device - Remote Mode

How would you like to find your Raspberry Pi?

1. Auto-discover Pi on network (recommended)
2. Manually enter Pi IP address
3. Skip (use localhost - for testing only)

Enter your choice (1-3): 1

🔍 Scanning network for Raspberry Pi devices...
This may take a moment...

✓ Found: 192.168.1.100 (raspberrypi.local)
✓ Found: 192.168.1.150 (pi-zero.local)

Found 2 devices:
1. 192.168.1.100 (raspberrypi.local)
2. 192.168.1.150 (pi-zero.local)

Select device (1-2): 1

✓ Using 192.168.1.100 (raspberrypi.local)

------------------------------------------------------------
Additional Settings
------------------------------------------------------------

Web server port (default: 5000): 

============================================================
✓ SETUP COMPLETE!
============================================================

Configuration saved to: /home/user/.film_scanner/scanner_config.json

You can now start using the Film Scanner.

To reset configuration, delete this file:
  /home/user/.film_scanner/scanner_config.json

Or run with --reset flag
============================================================
```

### Example 2: Subsequent Launch (No Setup)

```bash
$ python3 web_app.py

============================================================
   FILM SCANNER WEB APPLICATION
============================================================

📍 Mode: remote
📍 Pi IP: 192.168.1.100
📍 Port: 5000

🔌 Searching for Arduino...
✓ Arduino connected

============================================================
   WEB SERVER STARTING
============================================================

🌐 Access the scanner at:
   • Local:  http://localhost:5000
   • Network: http://192.168.1.100:5000

📱 From your phone/tablet:
   • http://192.168.1.100:5000

💡 Tip: To reset configuration, run:
   python3 web_app.py --reset
============================================================
```

### Example 3: Reset and Reconfigure

```bash
$ python3 web_app.py --reset

Resetting configuration...
Configuration deleted: /home/user/.film_scanner/scanner_config.json

✓ Configuration reset. Restart the application to run setup.

$ python3 web_app.py
# Setup wizard runs again...
```

## Summary

The Smart Startup System provides:

1. ✅ **One-Time Setup**: Configure once, use forever
2. ✅ **Auto-Discovery**: Find your Pi automatically
3. ✅ **Persistent Config**: Never lose your settings
4. ✅ **Easy Reset**: Reconfigure anytime
5. ✅ **Git-Friendly**: Safe for version control
6. ✅ **Cross-Platform**: Works on Windows, Linux, Mac, Pi
7. ✅ **User-Friendly**: Clear prompts and helpful messages
8. ✅ **Flexible**: Auto, manual, or localhost modes

**No more manual IP configuration every time you start the app!**

---

For more detailed information, see [STARTUP_GUIDE.md](STARTUP_GUIDE.md)

