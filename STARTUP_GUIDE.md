# Film Scanner - Smart Startup Guide

## Overview

The Film Scanner now includes a smart startup system that automatically configures your Raspberry Pi connection on first launch. Configuration is saved locally and reused on subsequent launches.

## Features

✅ **Auto-discovery**: Automatically scan your network for Raspberry Pi devices
✅ **Manual entry**: Option to manually enter Pi IP address
✅ **Persistent config**: Settings saved to `~/.film_scanner/scanner_config.json`
✅ **Easy reset**: Clear configuration anytime to reconfigure
✅ **Two apps supported**: Both web app and CLI app use the same configuration

## First Time Setup

### Option 1: Auto-Discovery (Recommended)

When you first launch either application, you'll be prompted:

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

Enter your choice (1-3):
```

Select **Option 1** for automatic discovery. The system will:
- Scan your local network for Raspberry Pi devices
- Display found devices with IP addresses and hostnames
- Let you select which Pi to use
- Test the connection
- Save the configuration

### Option 2: Manual Entry

Select **Option 2** if auto-discovery doesn't work:
- Enter the Pi's IP address manually
- System will test the connection
- If successful, configuration is saved

### Option 3: Localhost (Testing Only)

Select **Option 3** only for local testing when running directly on the Pi.

## Running the Applications

### Web Application

```bash
cd Film-Scanner
python3 web_app.py
```

On first launch, you'll see the setup wizard. After configuration, the app will display:

```
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

### CLI Application

```bash
cd Film-Scanner
python3 "scanner_app_v3 test.py"
```

On first launch, you'll see the setup wizard. After configuration:

```
============================================================
   FILM SCANNER CLI APPLICATION
============================================================

📍 Mode: remote
📍 Pi IP: 192.168.1.100
📍 Port: 5000

💡 Tip: To reset configuration, run:
   python3 "scanner_app_v3 test.py" --reset

============================================================

Press ENTER to start scanner interface...
```

## Configuration Management

### View Current Configuration

**Web App:**
```bash
python3 web_app.py --config
```

**CLI App:**
```bash
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

To reconfigure your setup, use the `--reset` flag:

**Web App:**
```bash
python3 web_app.py --reset
```

**CLI App:**
```bash
python3 "scanner_app_v3 test.py" --reset
```

This will delete the configuration file and allow you to run setup again.

### Manual Configuration Reset

You can also manually delete the configuration file:

```bash
rm ~/.film_scanner/scanner_config.json
```

Next time you launch the app, the setup wizard will run automatically.

## Configuration File Location

Configuration is stored at:
```
~/.film_scanner/scanner_config.json
```

Example configuration file:
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

## Configuration Modes

### Local Mode
- Running directly on Raspberry Pi
- Uses Pi's own IP address
- No network scanning needed

### Remote Mode
- Running on external computer
- Connects to Raspberry Pi over network
- Requires Pi IP address (auto-discovered or manual)

## Troubleshooting

### Auto-discovery Not Finding Pi

If auto-discovery doesn't find your Raspberry Pi:

1. **Check network connection**: Ensure both devices are on the same network
2. **Check Pi hostname**: Pi might not have recognizable hostname
3. **Use manual entry**: Enter IP address directly (Option 2)
4. **Find Pi IP manually**: Run on the Pi: `hostname -I`

### Connection Test Fails

If the connection test fails after entering an IP:

1. **Verify Pi is powered on**
2. **Check IP address**: Run `hostname -I` on the Pi
3. **Check firewall**: Ensure no firewall blocking
4. **Ping test**: From your computer: `ping <pi-ip>`

### Config File Issues

If you get configuration errors:

1. **Delete config file**: `rm ~/.film_scanner/scanner_config.json`
2. **Check permissions**: Ensure `~/.film_scanner/` directory is writable
3. **Restart application**: Configuration will be recreated

## Using Standalone Config Manager

The configuration manager can be run independently:

```bash
cd Film-Scanner
python3 config_manager.py
```

Options:
```bash
python3 config_manager.py --setup     # Run setup wizard
python3 config_manager.py --show      # Show current config
python3 config_manager.py --reset     # Delete configuration
```

## Network Requirements

For remote operation:
- Both devices must be on same local network
- Raspberry Pi must have static IP or DHCP reservation (recommended)
- Network must allow ICMP (ping) for discovery

## Tips

1. **Static IP Recommended**: Set a static IP on your Pi for consistent connection
2. **Same Network**: Ensure your computer and Pi are on the same network
3. **Hostname**: Give your Pi a recognizable hostname for easier identification
4. **Multiple Pis**: If you have multiple Pis, select the correct one during auto-discovery
5. **Fresh Start**: Use `--reset` flag anytime you want to reconfigure

## GitHub Workflow

The configuration system is designed to work with GitHub pull requests:

1. **Clone repo** → Config not included (ignored by `.gitignore`)
2. **First run** → Setup wizard creates local config
3. **Reset anytime** → Delete config file or use `--reset`
4. **Pull updates** → Config preserved, only code updates
5. **Fresh install** → Setup wizard runs automatically

## Integration with Existing Setup

The smart startup system is **backward compatible**:
- Doesn't modify existing Arduino or camera functionality
- Only adds configuration management layer
- Apps work the same after configuration
- Can be disabled by removing config file

## Advanced: Custom Configuration

For advanced users, you can manually create the configuration file:

```bash
mkdir -p ~/.film_scanner
cat > ~/.film_scanner/scanner_config.json << EOF
{
  "setup_complete": true,
  "setup_date": "$(date -I)",
  "mode": "remote",
  "pi_ip": "YOUR_PI_IP",
  "hostname": "YOUR_HOSTNAME",
  "port": 5000
}
EOF
```

Replace `YOUR_PI_IP` and `YOUR_HOSTNAME` with your values.

## Summary

The smart startup system makes it easy to:
- Configure once, run anywhere
- Discover Pi automatically
- Switch between configurations
- Reset and reconfigure anytime
- Work with GitHub workflows

No more manual IP address hunting every time you start the app!

