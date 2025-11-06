# Camera Issues - Quick Troubleshooting

## Step 1: Run Diagnostics on Your Pi

```bash
cd ~/Film-Scanner/Film-Scanner
chmod +x camera_test.py
python3 camera_test.py
```

This will show you exactly what's working and what's failing.

## Step 2: Quick Fixes to Try

### Fix 1: Camera USB Mode
1. Turn on your camera
2. Go to camera menu → Settings
3. Look for: "USB Mode" or "USB Connection" or "PC Connection"
4. Set to: **PTP** (not Mass Storage, not MTP)
5. Reconnect USB cable

### Fix 2: Kill Conflicting Processes
```bash
# Run this before starting web app
sudo killall gphoto2
sudo pkill -9 gphoto2
sudo systemctl stop gvfs-gphoto2-volume-monitor
sudo systemctl disable gvfs-gphoto2-volume-monitor
```

### Fix 3: Test Camera Manually
```bash
# Test if camera responds
gphoto2 --auto-detect

# Test preview
gphoto2 --capture-preview --filename=/tmp/test.jpg
ls -l /tmp/test.jpg

# Test capture (takes photo to camera SD card)
gphoto2 --capture-image

# Test autofocus
gphoto2 --set-config autofocus=1
```

## Step 3: Check Camera Settings

Make sure camera has:
- [ ] SD card inserted with free space
- [ ] Battery charged
- [ ] Auto-sleep/power-save turned OFF
- [ ] In Manual (M) mode or Program (P) mode
- [ ] Live View disabled (unless testing preview)

## Common Camera-Specific Issues

### Canon:
- May need "Remote Control" setting enabled
- Some models: Camera menu → Wireless → Enable for remote control
- Try Movie mode for live view

### Nikon:
- Often doesn't support remote autofocus
- May need manual focus
- Check "USB" setting in camera menu

### Sony:
- Set "USB Connection" → "PC Remote"
- Set "USB LUN Setting" → "Single" (not Multi)
- Disable "Auto Power Off"

## Step 4: If Still Failing...

**Consider USB HDMI Capture Card ($20-30)**

This is actually the BETTER solution for film scanning:
- Smooth 30 FPS live preview
- Works with ANY camera  
- Camera screen stays on
- See exact focus in real-time
- Professional approach

See `CAMERA_OPTIONS.md` for details!

## Need More Help?

Run the diagnostic script and send me the output:
```bash
python3 camera_test.py > camera_diag.txt 2>&1
cat camera_diag.txt
```

I can then provide specific fixes for your camera model.

