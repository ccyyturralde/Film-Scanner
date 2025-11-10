# Film Scanner - Quick Start Guide

## 🚀 Starting the Scanner

```bash
# On Raspberry Pi
./launch_scanner.sh

# Or directly
python3 web_app.py
```

**Access from any device**: `http://<pi-ip>:5000`

## 📋 Basic Workflow

### 1. Initial Setup
1. **Create Roll**: Enter a name and click "New Roll"
2. **Load Film**: Insert first strip (5-6 frames)

### 2. Calibration (First Strip Only)
1. **Position Frame 1**: Use motor controls to align first frame
2. **Capture Frame 1**: Click "📸 Capture Frame 1"
3. **Position Frame 2**: Manually advance and align second frame
4. **Capture Frame 2**: Click "📸 Capture Frame 2 (Complete Calibration)"
   - System learns the spacing between frames

### 3. Scanning Remaining Frames
1. **Frame 3-6**: Just click "📸 CAPTURE"
   - Auto-advance happens automatically between frames
   - Use fine controls for any minor adjustments

### 4. New Strips
1. **Start New Strip**: Click "Start New Strip"
2. **Position First Frame**: Manually align (it travels before motor catches)
3. **Capture First Frame**: Click "📸 Capture First Frame of Strip"
4. **Continue**: Use "📸 CAPTURE" for remaining frames

## 🎮 Controls

### Motor Controls
- **Fine Back / Forward**: Small movements (8 steps)
- **Coarse Back / Forward**: Large movements (192 steps)
- **Full Frame Back / Forward**: Move one complete frame (calibrated)
- **Press and Hold**: Any button for continuous movement

### Camera Controls
- **📸 CAPTURE**: Take photo and auto-advance (if enabled)
- **📷 Get Preview**: Capture preview image
- **Invert**: View negative as positive in preview

### Mode Buttons
- **Mode**: Toggle Manual / Calibrated
- **Auto-Advance**: Toggle ON / OFF

## ⚙️ Settings Panel

### Motor Step Sizes
- **Fine Step**: Small adjustments (default: 8)
- **Coarse Step**: Large movements (default: 192)
- Click "Apply Step Sizes" after changing

### Auto-Refresh Preview
- **Enable**: Check to auto-refresh preview
- **Interval**: 100ms (fast) to 5000ms (slow)
- Preview updates automatically after each capture when enabled

### System
- **Reconnect Arduino**: If connection lost
- **🧪 Test Camera Capture**: Test without affecting frame count

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Space` | Capture frame |
| `←` | Fine backward |
| `→` | Fine forward |
| `Shift + ←` | Coarse backward |
| `Shift + →` | Coarse forward |
| `P` | Get preview |
| `M` | Toggle mode |
| `A` | Toggle auto-advance |

## 💡 Tips

### For Best Results
1. **Focus**: Use manual focus for consistency
2. **Exposure**: Set manual exposure (don't use auto)
3. **Preview**: Check alignment before capturing
4. **Lighting**: Keep consistent lighting across strip

### Troubleshooting
- **Arduino not found**: Click "Reconnect Arduino"
- **Camera not detected**: Check USB mode is PTP
- **Preview timeout**: Camera may be in sleep mode
- **Motor not moving**: Check 12V power supply
- **Buttons laggy**: Reduce auto-refresh interval

## 📱 Mobile Tips

### Touch Controls
- **Press and Hold**: Touch motor buttons to move continuously
- **Quick Tap**: Tap once for single step
- **Two Fingers**: Pinch to zoom on preview

### Best Practices
- Use landscape mode for better layout
- Keep screen on during scanning
- Connect to power (scanning can take a while)

## 🎯 Frame Alignment

### Understanding Frame 1
⚠️ **Important**: Frame 1 of each strip travels manually before the motor grabs it.
- Position Frame 1 carefully by hand
- The motor will catch it and hold position
- Frame 1 → Frame 2 distance = calibrated spacing

### Why This Works
- Manual engagement allows for strip insertion
- Frame 2+ use accurate motor positioning
- Same spacing works for entire strip
- Recalibration not needed for subsequent strips

## 🔧 Common Adjustments

### If frames are too close together
1. Go to Settings
2. Increase Fine Step to 10-12
3. Or increase Coarse Step to 200-250
4. Test with motor controls

### If frames are too far apart
1. Go to Settings
2. Decrease Fine Step to 5-6
3. Or decrease Coarse Step to 150-180
4. Test with motor controls

### If preview is too slow
1. Go to Settings → Auto-Refresh Preview
2. Increase interval to 2000ms or more
3. Or disable auto-refresh
4. Use "Get Preview" button manually

### If preview is too fast (causing lag)
1. Disable auto-refresh
2. Or increase interval to 3000ms+
3. Preview manually when needed

## 📊 Status Display

### Connection Badges
- 🟢 **Green**: Connected and working
- 🔴 **Red**: Disconnected or error

### Status Values
- **Roll**: Current roll name
- **Strip**: Current strip number
- **Frame**: Total frames captured
- **Position**: Motor position in steps
- **Mode**: MANUAL or CALIBRATED
- **Advance**: Frame spacing (after calibration)

## 🎬 Example Session

```
1. Start scanner → http://192.168.1.100:5000
2. Create roll: "Kodak Gold 200 - 2025-11"
3. Load first strip
4. Position frame 1 → Capture
5. Position frame 2 → Capture (calibration done!)
6. Frames 3-6: Just hit CAPTURE each time
7. Load next strip
8. Start New Strip → Position frame 1 → Capture
9. Frames 2-6: Just hit CAPTURE
10. Repeat for all strips
11. Images on camera SD card!
```

## 🆘 Getting Help

### Check Status Messages
The status bar shows what's happening:
- Watch for error messages
- "✓" means success
- "✗" means error (check console)

### Console Output
Terminal shows detailed logs:
- Arduino connection status
- Camera detection
- Capture success/failure
- Error messages with solutions

### Test Before Scanning
1. Click "🧪 Test Camera Capture"
2. Check camera SD card for test image
3. If successful, camera is working correctly
4. Frame count NOT affected by test

## 🌟 Pro Tips

1. **Preview Before Capture**: Get preview to check alignment
2. **Adjust Settings Once**: Set step sizes at start, don't change mid-roll
3. **Consistent Workflow**: Use same process for each strip
4. **Check Camera SD**: Verify images are saving correctly
5. **Take Breaks**: Scanner can run for hours, you don't have to

---

**Need more help?** Check `REBUILD_SUMMARY.md` for technical details or `README.md` for full documentation.

**Ready to scan?** `python3 web_app.py` and go! 🎞️

