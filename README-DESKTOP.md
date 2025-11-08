# Film Scanner - Desktop Application

Modern Qt-based desktop application for 35mm film scanning. Runs on **Windows**, **Mac**, or **Linux** with a responsive GUI, eliminating button delay issues and providing seamless integration with Canon EOS Utility.

## ✨ Key Improvements Over Raspberry Pi Version

- **⚡ Zero Button Delay** - Native desktop responsiveness
- **🖥️ Modern GUI** - Clean Qt interface with real-time updates
- **📷 EOS Utility Integration** - One-click launch for camera preview
- **⌨️ Keyboard Shortcuts** - Rapid operation without mouse
- **💾 Auto-Save** - Session state persists automatically
- **🔄 Hot-Reload** - Resume interrupted scans instantly

## 🎯 Features

### Motor Control
- **Fine/Coarse Adjustment** - Arrow keys for precise positioning
- **Frame Advance/Backup** - Shift+Arrow for full frame movement
- **Zero Position** - Quick reset with Z key
- **Real-time Position** - Live step counter

### Session Management
- **Roll Tracking** - Named sessions with metadata
- **Calibration** - One-time frame spacing measurement
- **Strip-Based Workflow** - Hand-feed multiple strips per roll
- **Resume Capability** - Continue after interruption

### Camera Integration
- **EOS Utility Launch** - Built-in button to open Canon software
- **Live Preview** - Use EOS Utility for composition
- **Auto-Advance** - Optional post-capture movement
- **Frame Counter** - Track progress by strip and total

## 📋 Requirements

### Hardware
- Windows PC (Windows 10/11 recommended)
- Arduino Uno/Nano with Film Scanner firmware
- Canon DSLR with USB connection
- NEMA 17 stepper motor + A4988 driver
- USB cables for Arduino and camera

### Software
- Python 3.9 or newer
- Canon EOS Utility 3 (optional, for camera preview)
- Arduino firmware (already flashed to Arduino)

## 🚀 Quick Start

### 1. Install Python Dependencies

```bash
# Install required packages
pip install -r requirements-desktop.txt
```

### 2. Connect Hardware

1. **Plug in Arduino** via USB
2. **Connect Canon camera** via USB
3. **Power on** stepper motor (12V)

### 3. Run Application

```bash
python scanner_desktop.py
```

The app will auto-detect your Arduino on startup!

## 📖 Usage Guide

### First Time Setup

1. **Launch Application**
   ```bash
   python scanner_desktop.py
   ```

2. **Verify Arduino Connection**
   - Status should show "Arduino: Connected ✓"
   - If not, check USB cable and try Reconnect

3. **Create New Roll**
   - Enter roll name (e.g., "Kodak-Portra400-001")
   - Click "New Roll" or press **N**
   - Metadata folder created at `~/scans/YYYY-MM-DD/roll-name/`

4. **Calibrate Frame Spacing (First Strip Only)**
   - Load film strip 1
   - Position frame 1 with arrow keys (even if partially off mask)
   - Click "Calibrate" or press **C**
   - Position and **capture frame 1**
   - Move to frame 2 with arrow keys
   - Position and **capture frame 2**
   - System learns frame-to-frame distance
   - **✓ Frames 1 and 2 captured during calibration!**

5. **Continue with Remaining Frames**
   - Press **Space** to capture frame 3
   - Motor auto-advances using calibrated spacing
   - Press **Space** for frames 4-6
   - Fine-tune position with arrows before each capture
   - Motor auto-advances between frames

### New Strip Workflow

After completing a strip (typically 5-6 frames):

1. Press **S** or click "New Strip"
2. Hand-feed next strip
3. Position frame 1 with arrow keys (fine-tune precisely!)
4. Press **Space** to capture frame 1
5. Motor auto-advances using calibrated spacing
6. Press **Space** for each remaining frame (2-6)
7. Fine-tune with arrows before each capture as needed

System uses previously calibrated spacing, but **always allows fine adjustments!**

### Why Manual Fine-Tuning is Always Available

- Film strips may have slight spacing variations
- Different strip cuts may not be perfectly uniform
- You can adjust before EVERY capture with arrow keys
- Computer vision auto-alignment didn't work reliably (confused subjects with frame lines)
- Manual control ensures perfect alignment every time

## ⌨️ Keyboard Shortcuts

| Key | Action | Description |
|-----|--------|-------------|
| **←** | Fine Back | Small backward step (8 steps) |
| **→** | Fine Forward | Small forward step (8 steps) |
| **Shift+←** | Frame Back | Full frame backward |
| **Shift+→** | Frame Forward | Full frame forward |
| **Space** | Capture | Capture frame + auto-advance |
| **C** | Calibrate | Start calibration wizard |
| **S** | New Strip | Begin new film strip |
| **N** | New Roll | Create new scanning session |
| **Z** | Zero Position | Reset position counter to 0 |

## 🎥 Camera Integration

### Using EOS Utility (Recommended)

1. **Launch EOS Utility**
   - Click "Launch EOS Utility" button
   - Or install separately and run before app

2. **Use EOS Utility For:**
   - Live View preview
   - Manual focus
   - Exposure settings
   - White balance
   - Camera configuration

3. **Return to Film Scanner For:**
   - Frame capture (Space key)
   - Motor control
   - Session management
   - Frame counting

### Camera Files

- Images save to **camera SD card** in native RAW format
- No computer download required
- Transfer files when convenient

## 🎛️ Configuration

### Motor Settings

Edit in `scanner_desktop.py` if needed:

```python
self.fine_step = 8       # Fine movement steps
self.coarse_step = 64    # Coarse movement steps
```

### Frame Spacing

- **Calibrated automatically** during first strip
- Typical 35mm: ~1200 steps
- Adjusts for your specific hardware

### Arduino Commands

The app sends these commands to Arduino:

| Command | Function |
|---------|----------|
| `f` / `b` | Fine forward/backward |
| `F` / `B` | Coarse forward/backward |
| `H[n]` / `h[n]` | Precise movement (steps) |
| `Z` | Zero position |
| `E` / `M` | Enable/disable motor |

See `ARDUINO_API.md` for complete protocol.

## 📁 File Structure

```
~/scans/
└── YYYY-MM-DD/
    └── roll-name/
        ├── .scan_state.json    # Session state
        └── metadata.txt        # Optional notes
        
Camera SD Card/
└── DCIM/
    └── IMG_0001.CR3...         # RAW images
```

## 🔧 Troubleshooting

### Arduino Not Detected

```bash
# Windows: Check Device Manager for COM ports
# Look for "Arduino Uno" or similar

# Verify Arduino is flashed with correct firmware
# Should print "READY NEMA17" on serial connection
```

**Solutions:**
- Try different USB cable
- Reinstall Arduino drivers
- Check COM port in Device Manager
- Re-flash Arduino firmware

### Motor Not Moving

**Check:**
- 12V power supply connected
- A4988 driver current setting (Vref ~0.4-0.5V)
- Common ground between Arduino, driver, and power supply
- Motor wiring to driver (coils 1A/1B, 2A/2B)

**Test:**
```bash
# Open Arduino Serial Monitor at 115200 baud
# Send: ?
# Should see status with position info
# Send: F
# Motor should move forward
```

### EOS Utility Not Found

The app looks for EOS Utility in standard locations:
- `C:\Program Files\Canon\EOS Utility\EOS Utility 3\`
- `C:\Program Files (x86)\Canon\EOS Utility\`

**Solutions:**
- Install Canon EOS Utility 3 from Canon website
- Or launch EOS Utility manually before starting scanner app

### Button Delay / Lag

Desktop app should have **zero delay** compared to Raspberry Pi.

If experiencing lag:
- Close other heavy applications
- Check CPU usage (should be < 5%)
- Verify Python version is 3.9+

## 🆚 Comparison: Desktop vs Raspberry Pi

| Feature | Desktop App | Raspberry Pi |
|---------|-------------|--------------|
| **Responsiveness** | Instant | 100-500ms delay |
| **GUI** | Modern Qt | Terminal curses |
| **Camera Preview** | EOS Utility | Limited |
| **Setup** | Run .py file | OS config needed |
| **Performance** | Native | Shared resources |
| **Portability** | Windows/Mac/Linux | Requires Pi |

## 🔨 Building Standalone Executable (Optional)

To create a standalone `.exe` (no Python required):

```bash
# Install PyInstaller
pip install pyinstaller

# Build executable
pyinstaller --onefile --windowed --name "FilmScanner" scanner_desktop.py

# Output in dist/FilmScanner.exe
```

Double-click `FilmScanner.exe` to run!

## 🚦 Complete Workflow Example

**Scanning a 36-frame roll (6 strips × 6 frames each):**

### Strip 1 - With Calibration

1. **Create Roll** (N key)
   - Enter name: "Portra400-Vacation-2024"
   - Set frames per strip: 6 (or 5, depending on your cuts)

2. **Load First Strip**
   - Hand-feed strip into scanner
   - Note: Frame 1 may be partially off mask initially - normal!

3. **Calibrate** (C key - ONLY ONCE, First Strip Only)
   - Position frame 1 perfectly with arrows
   - Click OK → Frame 1 captured ✓
   - Move to frame 2 with arrows
   - Click OK → Frame 2 captured ✓
   - System calculates: "1245 steps" (example)

4. **Continue Strip 1**
   - Press Space → Frame 3 captured
   - Motor advances 1245 steps automatically
   - Press Space → Frame 4 captured
   - Continue through frames 5-6
   - Fine-tune with arrows before each capture if needed

### Strips 2-6 - Using Calibrated Spacing

5. **New Strip** (S key)
   - Remove completed strip
   - Hand-feed strip 2
   - Position frame 1 (fine-tune precisely!)
   - Press Space → Frame 1 captured
   - Motor advances automatically
   - Press Space for frames 2-6
   - Adjust with arrows as needed before each capture

6. **Repeat for Strips 3-6**
   - Same process: S key, position, Space through all frames
   - Always fine-tune before captures

7. **Complete**
   - 36 frames on camera SD card (.CR3 RAW files)
   - Session metadata in `~/scans/2024-11-07/Portra400-Vacation-2024/`
   - Ready to transfer and develop!

## 📚 Additional Documentation

- `ARDUINO_API.md` - Serial protocol reference
- `HARDWARE_SETUP.md` - Wiring diagrams
- `Arduino_Film_Scanner/` - Arduino firmware

## 🐛 Known Issues

- EOS Utility path detection works for Canon only (Nikon users: launch NX manually)
- Frame counter is manual (future: integrate with camera SDK)
- Position tracking resets on app restart (use saved state to resume)

## 🛣️ Roadmap

- [ ] Direct camera SDK integration (bypass EOS Utility)
- [ ] Live histogram preview
- [ ] Automatic exposure adjustment
- [ ] Batch export with frame numbering
- [ ] Multi-camera support
- [ ] Cloud backup integration

## 📄 License

MIT License - See LICENSE file

## 🙏 Credits

Built for the film photography community. Contributions welcome!

---

**Need Help?** Open an issue on GitHub with your system info and error message.

