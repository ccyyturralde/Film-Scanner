# Film Scanner Systemd Services

This directory contains systemd service files for running the Film Scanner on a Raspberry Pi.

## Services

### film-scanner-touchscreen.service
Runs the touch screen UI which provides a graphical interface on the 3.5" TFT display.
This service also manages the web application (start/stop/restart).

### film-scanner-web.service
Runs the web application standalone (use this if you don't have a touch screen).

## Installation

### Automatic Installation
Run the setup script:
```bash
sudo ./scripts/setup_touchscreen.sh
```

### Manual Installation

1. **Copy service files:**
   ```bash
   sudo cp services/film-scanner-touchscreen.service /etc/systemd/system/
   sudo cp services/film-scanner-web.service /etc/systemd/system/
   ```

2. **Edit the paths in the service files:**
   Update `WorkingDirectory` and `ExecStart` paths to match your installation:
   ```bash
   sudo nano /etc/systemd/system/film-scanner-touchscreen.service
   ```

3. **Reload systemd:**
   ```bash
   sudo systemctl daemon-reload
   ```

4. **Enable the service you want:**
   
   For touch screen UI (recommended if you have a TFT display):
   ```bash
   sudo systemctl enable film-scanner-touchscreen.service
   ```
   
   For web app only (no touch screen):
   ```bash
   sudo systemctl enable film-scanner-web.service
   ```

## Usage

### Start/Stop/Restart

```bash
# Touch screen UI
sudo systemctl start film-scanner-touchscreen
sudo systemctl stop film-scanner-touchscreen
sudo systemctl restart film-scanner-touchscreen

# Web app only
sudo systemctl start film-scanner-web
sudo systemctl stop film-scanner-web
sudo systemctl restart film-scanner-web
```

### Check Status

```bash
sudo systemctl status film-scanner-touchscreen
sudo systemctl status film-scanner-web
```

### View Logs

```bash
# Real-time logs
journalctl -u film-scanner-touchscreen -f
journalctl -u film-scanner-web -f

# Last 100 lines
journalctl -u film-scanner-touchscreen -n 100
journalctl -u film-scanner-web -n 100
```

### Disable Auto-Start

```bash
sudo systemctl disable film-scanner-touchscreen
sudo systemctl disable film-scanner-web
```

## Troubleshooting

### Service won't start
1. Check the paths in the service file are correct
2. Check logs: `journalctl -u film-scanner-touchscreen -n 50`
3. Ensure dependencies are installed: `pip3 install pygame`

### Touch screen not responding
1. Check touch device exists: `ls -la /dev/input/`
2. Test touch input: `evtest /dev/input/event0`
3. May need to adjust SDL environment variables

### Display issues
1. Check framebuffer exists: `ls -la /dev/fb*`
2. Test framebuffer: `cat /dev/urandom > /dev/fb1`
3. Check display driver is loaded: `dmesg | grep -i lcd`
