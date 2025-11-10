# Film Scanner Desktop Application

A modern, integrated film scanning application with live view and single-button operation.

## Key Features

### 🎥 Live View with Color Inversion
- Real-time camera preview directly in the app
- **Invert colors** to view film negatives as positives
- No need for external camera software

### ⚡ One-Button Scanning
Press **SPACE** and the app automatically:
1. **Autofocus** the camera
2. **Capture** the image  
3. **Advance** to next frame

All in one action - no switching between apps!

### 🎯 Smart Frame Spacing
- Calibrate once by capturing two frames
- App learns and remembers spacing
- Auto-advances perfectly every time
- Manual fine-tuning always available

## Quick Start

1. **Install dependencies**: See [SETUP_GUIDE.md](SETUP_GUIDE.md)
2. **Connect camera and Arduino**
3. **Run**: `python scanner_desktop.py`
4. **Create new roll** (N key)
5. **Start live view** and enable color inversion
6. **Calibrate** first strip (C key)
7. **Press SPACE** to scan each frame!

## System Requirements

- Python 3.9+
- PySide6 (Qt6)
- OpenCV
- gphoto2 with libgphoto2
- Canon camera with USB support
- Arduino with stepper motor control

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

- **SPACE**: Autofocus + Capture + Advance
- **Arrow Keys**: Fine positioning
- **C**: Calibrate frame spacing
- **S**: Start new strip
- **N**: New roll

## Documentation

- **[SETUP_GUIDE.md](SETUP_GUIDE.md)**: Complete installation and setup instructions
- **[requirements-desktop.txt](requirements-desktop.txt)**: Python dependencies

## What's New

### Version 2.0 - Integrated Camera Control

- ✅ Removed dependency on EOS Utility
- ✅ Built-in live view with real-time preview
- ✅ Color inversion for viewing film positives
- ✅ Single-button operation: autofocus → capture → advance
- ✅ Direct camera control via gphoto2
- ✅ Improved UI with split-panel layout

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
