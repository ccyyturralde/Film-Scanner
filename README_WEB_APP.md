# 35mm Film Scanner - Web App Version

A modern web interface for controlling your 35mm film scanner from any device - desktop, tablet, or smartphone.

## Features

- 🌐 **Web-based interface** - Access from any browser
- 📱 **Mobile-responsive** - Use your phone or tablet as a remote control
- ⚡ **Real-time updates** - WebSocket connection for instant status updates
- 🎯 **Touch-friendly** - Optimized buttons and controls for touchscreens
- ⌨️ **Keyboard shortcuts** - Fast desktop control with arrow keys and hotkeys
- 🔄 **State persistence** - Resume scanning sessions automatically

## What Changed from the Terminal Version?

### Old (.sh/terminal version):
- Required terminal/SSH access
- Text-based curses interface
- Had to be physically at computer or SSH in
- Arrow keys only for navigation

### New (Web version):
- Access from any device on your network
- Modern, visual interface
- Use your phone as a wireless remote
- Touch controls + keyboard shortcuts
- Multiple devices can monitor status simultaneously

## Requirements

### Hardware
- Arduino with film scanner firmware
- Camera compatible with gphoto2 (DSLR/mirrorless)
- Computer running the web server (Raspberry Pi, laptop, etc.)

### Software
- Python 3.7 or higher
- gphoto2 (for camera control)
- All Python dependencies (see requirements.txt)

## Installation

### 1. Install System Dependencies

**On Raspberry Pi / Linux:**
```bash
sudo apt update
sudo apt install python3 python3-pip gphoto2
```

**On macOS:**
```bash
brew install python3 gphoto2
```

**On Windows:**
- Install Python 3 from python.org
- Install gphoto2 (more complex - may need WSL)

### 2. Install Python Dependencies

```bash
cd Film-Scanner
pip install -r requirements.txt
```

### 3. Connect Hardware

1. Connect Arduino via USB
2. Connect camera via USB
3. Ensure camera is in PTP/PC mode (not mass storage)

## Usage

### Starting the Server

```bash
python web_app.py
```

The server will:
- Automatically search for Arduino
- Start on port 5000
- Be accessible on your network

### Accessing the Interface

**From the same computer:**
```
http://localhost:5000
```

**From phone/tablet on same network:**
```
http://192.168.1.XXX:5000
```
(Replace with your computer's IP address)

**Finding your IP address:**
- Linux/Mac: `ifconfig` or `ip addr`
- Windows: `ipconfig`
- Look for IP starting with 192.168.x.x or 10.x.x.x

## How to Use

### First Time Setup

1. **Create a Roll**
   - Enter a roll name (e.g., "Kodak Portra 400 - Beach")
   - Click "New Roll"

2. **Calibration (Strip 1 only)**
   - Load your first film strip
   - Click "Start Calibration"
   - Position frame 1 using motor controls
   - Click "Capture Frame 1"
   - Advance to frame 2 using motor controls
   - Click "Capture Frame 2"
   - Frame spacing is now learned!

3. **Continue Scanning Strip 1**
   - Press "Capture" for each remaining frame
   - With auto-advance ON, motor automatically advances
   - Fine-tune position with arrow buttons as needed

4. **Subsequent Strips**
   - Click "Start New Strip"
   - Position first frame
   - Click "Capture First Frame"
   - Continue with remaining frames

### Controls Reference

#### Motor Controls
- **Fine Forward/Back** - Small adjustments (8 steps)
- **Coarse Forward/Back** - Large movements (64 steps)
- **Full Frame Forward/Back** - Move one complete frame (calibrated distance)
- **Toggle Step Size** - Switch between fine/coarse
- **Zero Position** - Reset position counter to 0

#### Camera Controls
- **Autofocus** - Trigger camera autofocus
- **CAPTURE** - Take photo (auto-advances if enabled)
- **Mode** - Toggle between Manual/Calibrated mode
- **Auto-Advance** - Toggle automatic frame advance after capture

#### Keyboard Shortcuts (Desktop)
- `Space` - Capture
- `←/→` - Fine move backward/forward
- `Shift + ←/→` - Coarse move
- `F` - Autofocus
- `G` - Toggle step size
- `A` - Toggle auto-advance
- `M` - Toggle mode

## Mobile Usage Tips

### Portrait Mode
- All controls are vertically stacked
- Large touch targets for easy pressing
- Status at top, controls below

### Landscape Mode
- More compact layout
- Grid-based control layout
- Ideal for tablets

### Best Practices
- Add webpage to home screen for quick access
- Keep screen on during scanning sessions
- Use in landscape for easier control access

## Workflow Comparison

### Terminal Version Workflow:
```
1. SSH into Pi
2. Navigate to directory
3. Run Python script
4. Navigate curses interface with keyboard
5. Can't see status from other devices
```

### Web Version Workflow:
```
1. Open browser on phone
2. Navigate to http://pi-address:5000
3. Visual interface with buttons
4. Monitor from multiple devices
5. Use touch controls naturally
```

## Network Configuration

### Access from Outside Your Home Network (Advanced)

If you want to access the scanner from outside your home:

1. **Port Forwarding** (requires router access)
   - Forward port 5000 to your server's internal IP
   - Access via your public IP

2. **VPN** (more secure)
   - Set up VPN to your home network
   - Connect via VPN, then access normally

3. **Reverse Tunnel** (e.g., ngrok)
   ```bash
   ngrok http 5000
   ```
   - Provides public URL temporarily
   - Good for testing

⚠️ **Security Warning:** The web app has no authentication. Don't expose it to the public internet without adding security!

## Troubleshooting

### Arduino Not Found
- Check USB connection
- Try different USB ports
- Click "Reconnect Arduino" button
- Check serial port permissions (Linux: add user to `dialout` group)

### Camera Not Detected
- Ensure camera is on and in PC/PTP mode
- Disconnect and reconnect USB
- Kill competing gphoto2 processes: `killall gphoto2`
- Test with: `gphoto2 --auto-detect`

### Can't Access from Phone
- Ensure phone and computer on same WiFi
- Check firewall isn't blocking port 5000
- Verify correct IP address
- Try http://computer-name.local:5000

### Images Not Saving
- Currently images save to camera SD card only
- Check SD card has space
- Check camera settings

## State Management

The scanner automatically saves state to:
```
~/scans/YYYY-MM-DD/roll-name/.scan_state.json
```

This includes:
- Frame count
- Strip count  
- Position
- Calibration data
- Mode settings

Resume scanning by creating a roll with the same name and clicking "Resume".

## Architecture

### Backend (Flask + Flask-SocketIO)
- REST API for actions (capture, move, etc.)
- WebSocket for real-time status updates
- Serial communication with Arduino
- gphoto2 subprocess calls for camera

### Frontend (Vanilla JS + CSS)
- Socket.IO client for WebSocket
- Responsive CSS Grid/Flexbox layout
- Touch-optimized button sizes
- Real-time UI updates

### Communication Flow
```
Phone Browser
    ↕ WebSocket
Flask Server
    ↕ Serial
Arduino → Stepper Motor
    
Flask Server
    ↕ gphoto2
Camera
```

## Development

### Running in Debug Mode
Already enabled in `web_app.py`:
```python
socketio.run(app, host='0.0.0.0', port=5000, debug=True)
```

### Changing Port
Edit `web_app.py`:
```python
socketio.run(app, host='0.0.0.0', port=8080, debug=True)
```

### Custom Styling
Edit `static/css/style.css` to customize colors, sizes, layout.

## Comparison: Terminal vs Web

| Feature | Terminal (.sh) | Web App |
|---------|---------------|---------|
| Interface | Curses (text) | HTML/CSS (visual) |
| Access | SSH required | Browser only |
| Mobile | Difficult | Native |
| Multiple viewers | No | Yes |
| Touch support | No | Yes |
| Learning curve | Medium | Low |
| Setup | Simpler | Requires server |

## Future Enhancements

Potential additions:
- [ ] User authentication
- [ ] Image preview/gallery
- [ ] Auto-download images from camera
- [ ] Scanning statistics/dashboard
- [ ] Multiple scanner support
- [ ] PWA (Progressive Web App) support
- [ ] Save/load preset configurations

## License

Same as original scanner project.

## Credits

Web app conversion maintains all functionality of the original terminal-based scanner while adding modern web interface capabilities.

---

**Enjoy scanning your film from the comfort of your couch! 📸**

