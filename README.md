# Film Scanner Desktop Application

A modern, integrated film scanning application with live view and single-button operation.

## Key Features

### 🎥 Live View Preview
- Real-time camera preview directly in the app
- **Native Windows support** - works with any USB camera
- No SDK or driver hassles
- No external camera software needed

### ⚡ One-Button Scanning
Press **SPACE** and the app automatically:
1. **Capture** the image from live view
2. **Advance** to next frame

All in one action - no switching between apps!
(Manual focus recommended for best quality)

### 🎯 Smart Frame Spacing
- Calibrate once by capturing two frames
- App learns and remembers spacing
- Auto-advances perfectly every time
- Manual fine-tuning always available

## Quick Start

1. **Install dependencies**: See [SETUP_GUIDE.md](SETUP_GUIDE.md)
2. **Connect camera and Arduino**
3. **Run**: `python scanner_desktop.py`
4. **Select your camera** from dropdown
5. **Start live view** to see what you're scanning
6. **Create new roll** (N key)
7. **Calibrate** first strip (C key)
8. **Press SPACE** to scan each frame!

## System Requirements

- Python 3.9+
- PySide6 (Qt6 with Multimedia)
- OpenCV, NumPy
- Any USB camera (Canon, Nikon, Sony, webcam)
- Arduino with stepper motor control
- **Windows, Mac, or Linux**

## Interface

```
┌─────────────────────────────────────────────────┐
│  Live View (with color inversion)   │ Controls │
│                                      │          │
│  [Camera preview shows here]         │ Status   │
│                                      │ Motor    │
│  □ Invert Colors (Show Positive)     │ Session  │
│  [Start/Stop Live View]              │ Log      │
└─────────────────────────────────────────────────┘
```

## Keyboard Shortcuts

- **SPACE**: Capture + Advance
- **Arrow Keys**: Fine positioning
- **C**: Calibrate frame spacing
- **S**: Start new strip
- **N**: New roll

## Documentation

- **[SETUP_GUIDE.md](SETUP_GUIDE.md)**: Complete installation and setup instructions
- **[requirements-desktop.txt](requirements-desktop.txt)**: Python dependencies

## What's New

### Version 2.0 - Native Windows Camera Control

- ✅ **Qt-based camera framework** - works natively on Windows!
- ✅ No SDK registration or complex setup required
- ✅ Built-in live view with real-time preview
- ✅ Works with any USB camera (Canon, Nikon, Sony, etc.)
- ✅ Single-button operation: capture → advance
- ✅ Improved UI with split-panel layout
- ✅ Camera selection dropdown
- ✅ Cross-platform support (Windows/Mac/Linux)

### Previous Features Retained

- Arduino motor control
- Frame spacing calibration
- Session state management
- Strip/roll organization
- Keyboard shortcuts
- Activity logging

## License

MIT License - See LICENSE file for details

## Author

Built for efficient film scanning workflows.
