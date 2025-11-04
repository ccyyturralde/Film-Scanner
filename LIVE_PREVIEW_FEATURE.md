# Live Preview Feature

## Overview

The web app now includes a **live camera preview** feature that lets you see what the camera is seeing in real-time. Perfect for framing and positioning film while working away from your desk.

## Features

### ✅ Simple Live View
- Real-time preview from your camera
- ~1 frame per second update rate
- View on any device (phone, tablet, desktop)

### 🔄 Negative/Positive Toggle
- **View as Negative** - See the inverted image (for viewing negatives as positives)
- **View as Positive** - See the normal camera view (default)
- Instant toggle with CSS filter
- Works for both B&W and color negatives

### 💡 On-Demand
- Start/stop preview when needed
- Saves camera battery when not in use
- Automatic cleanup when stopped

## How to Use

### 1. Start Preview
Click the **"Start Preview"** button in the Live Preview section.

### 2. View the Image
- Preview window appears below the controls
- Updates automatically ~1 frame per second
- Shows what the camera sees in real-time

### 3. Toggle Negative/Positive
- Click **"View as Positive"** to invert negatives (see them as positives)
- Click **"View as Negative"** to see the normal camera view
- Toggle anytime while preview is running

### 4. Position Your Film
- Use motor controls to adjust framing
- See results immediately in preview
- Perfect alignment before capture

### 5. Stop Preview
Click **"Stop Preview"** when done to save camera battery.

## Use Cases

### Perfect for:
- 📐 **Framing**: See exact frame boundaries
- 🎯 **Positioning**: Align film precisely
- 👁️ **Verification**: Check if frame is in view
- 📱 **Mobile Control**: Work from your couch/across room
- 🔍 **Inspection**: Verify film is loaded correctly

### Works Great With:
- Negatives (invert to see as positive)
- Slide film (view normally)
- Any gphoto2-compatible camera
- Both B&W and color film

## Technical Details

### How It Works

**Backend (Python):**
```python
# Background thread continuously captures preview
gphoto2 --capture-preview --filename=preview.jpg

# Encodes as base64
base64.b64encode(image_data)

# Broadcasts via WebSocket to all clients
socketio.emit('preview_frame', {'image': base64_data})
```

**Frontend (JavaScript):**
```javascript
// Receives frames
socket.on('preview_frame', (data) => {
    previewImg.src = 'data:image/jpeg;base64,' + data.image;
});

// Inverts with CSS
img.style.filter = 'invert(1)';  // Negative → Positive
```

### Performance

- **Frame Rate**: ~1 FPS (adequate for framing)
- **Latency**: ~500ms-1s (local network)
- **Image Size**: ~100-500KB per frame
- **CPU Usage**: Minimal (single background thread)
- **Camera Battery**: Moderate drain (live view is power-hungry)

### Camera Compatibility

Works with any camera that supports `gphoto2 --capture-preview`:
- ✅ Most Canon DSLRs/mirrorless
- ✅ Most Nikon DSLRs/mirrorless
- ✅ Sony mirrorless (most models)
- ⚠️ Some older cameras may not support live view

**Test your camera:**
```bash
gphoto2 --capture-preview --filename=test.jpg
```

If this creates `test.jpg`, your camera is compatible!

## UI Components

### Buttons
- **Start Preview** - Begins live preview stream
- **Stop Preview** - Ends live preview stream
- **View as Positive** - Inverts image (for negatives)
- **View as Negative** - Normal view (for slides)

### Preview Window
- Hidden by default
- Appears when preview starts
- Full-width responsive image
- Smooth CSS transitions

### Disabled State
- "View as Positive/Negative" button disabled when preview is stopped
- Prevents confusion

## Tips & Best Practices

### 💡 Power Management
- **Turn off preview** when not actively positioning
- Live view drains camera battery quickly
- Only use when needed

### 📱 Mobile Usage
- Preview works great on phones
- Pinch to zoom in browser if needed
- Landscape mode gives larger preview

### 🎯 Workflow
1. Position film roughly
2. Start preview
3. Fine-tune position using motor controls
4. Toggle invert if viewing negatives
5. Once aligned, stop preview
6. Capture the frame

### ⚡ Performance
- Preview continues during motor movements
- Can see position changes in real-time
- ~1 second delay is normal
- Local network only (no internet needed)

## Limitations

### What It Doesn't Do
- ❌ No zoom controls (use browser pinch-zoom)
- ❌ No exposure adjustment (camera handles this)
- ❌ No focus peaking or overlays
- ❌ Not video-smooth (1 FPS is intentional)
- ❌ No recording/saving of preview

### Why Keep It Simple
- You're shooting RAW with auto-exposure
- Color correction happens in other software
- This is just for framing/positioning
- Simpler = more reliable
- Less CPU/battery drain

## Troubleshooting

### Preview Won't Start
```
❌ "Failed to start preview"
```

**Check:**
1. Camera is on and connected via USB
2. Camera is in PTP/PC mode (not mass storage)
3. No other gphoto2 processes running: `killall gphoto2`
4. Camera supports live view (test: `gphoto2 --capture-preview --filename=test.jpg`)

### Preview Is Frozen
**Solution:** Click "Stop Preview" then "Start Preview" again

### Preview Is Slow/Laggy
**Normal!** 
- ~1 FPS is intentional to save resources
- Good enough for framing
- If you need faster, edit `web_app.py` and change:
  ```python
  time.sleep(1.0)  # Change to 0.5 for 2 FPS
  ```

### Invert Toggle Doesn't Work
**Check:** Preview must be running first (button is disabled when stopped)

### Preview Interferes with Capture
**By Design:**
- Preview automatically pauses during capture
- `killall gphoto2` ensures no conflicts
- Resume preview after capture if needed

## Code Changes Summary

### Backend (`web_app.py`)
- Added preview thread management
- Added `/api/start_preview` endpoint
- Added `/api/stop_preview` endpoint
- Added `preview_frame` WebSocket event
- Added 85 lines of preview logic

### Frontend (`templates/index.html`)
- Added Live Preview section
- Added preview controls (2 buttons)
- Added preview image container
- Added 16 lines

### Styling (`static/css/style.css`)
- Added preview container styles
- Added image invert class
- Added smooth transitions
- Added 26 lines

### JavaScript (`static/js/app.js`)
- Added preview state management
- Added `togglePreview()` function
- Added `toggleInvert()` function
- Added WebSocket frame handler
- Added 61 lines

**Total: 187 lines added across 4 files**

## Examples

### Viewing Negatives
```
1. Start Preview
2. Click "View as Positive"
3. Negatives now appear as positive images
4. Adjust position as needed
```

### Viewing Slides
```
1. Start Preview
2. Leave as "View as Negative" (normal view)
3. See slide normally
4. Adjust position as needed
```

### Mobile Workflow
```
1. Open web app on phone
2. Walk to scanner
3. Load film strip
4. Start Preview on phone
5. Use motor buttons to position
6. Watch preview update in real-time
7. Stop Preview when aligned
8. Capture frame
```

## Configuration

### Adjust Frame Rate
Edit `web_app.py`, line ~308:
```python
time.sleep(1.0)  # 1 FPS (default)
time.sleep(0.5)  # 2 FPS (faster, more CPU)
time.sleep(2.0)  # 0.5 FPS (slower, save battery)
```

### Adjust Image Quality
gphoto2 uses camera's LCD preview quality by default. To change:
- Adjust camera's LCD brightness/quality settings
- Some cameras allow preview quality configuration

## Future Enhancements (Not Implemented)

If you want to add later:
- [ ] Fullscreen preview mode
- [ ] Brightness/contrast adjustments
- [ ] Grid overlay for alignment
- [ ] Digital zoom controls
- [ ] Capture directly from preview
- [ ] Pause/resume (not stop/start)

## Conclusion

This is a **simple, practical** live preview feature that serves one purpose well: **helping you position and frame film while working remotely from your desk**.

No bells and whistles—just what you need to see what you're doing.

---

**Enjoy seeing your film in real-time! 📹**

