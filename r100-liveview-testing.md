# gphoto2 Live Preview Troubleshooting - RESOLVED

## Problem
Live preview was not working for Canon EOS R100 through gphoto2 on the mobile web version branch.

## Root Cause
The camera's viewfinder mode was disabled (set to 0). Canon EOS cameras require the viewfinder to be explicitly enabled via gphoto2 configuration before capturing live preview frames.

## Solution
Enable the viewfinder mode before capturing previews:
```bash
gphoto2 --set-config viewfinder=1
gphoto2 --capture-preview
```

## Camera Details
- Model: Canon EOS R100
- Connection: USB, PTP mode
- Capabilities: Supports "Preview" capture mode
- Configuration path: `/main/actions/viewfinder`

## Key Configuration Settings
```bash
# Check viewfinder status
gphoto2 --get-config viewfinder
# Returns: Current: 0 (disabled) or 1 (enabled)

# Check EVF mode
gphoto2 --get-config evfmode

# Capture target (should be set appropriately)
gphoto2 --get-config capturetarget
# Current: Memory card (other option: Internal RAM)
```

## Implementation Requirements for Web App

### Session Start (Live Preview Enable)
1. Enable viewfinder: `gphoto2 --set-config viewfinder=1`
2. Optionally set EVF mode: `gphoto2 --set-config evfmode=1`
3. Set capture target if needed

### During Live Preview
- Repeatedly call: `gphoto2 --capture-preview --force-overwrite`
- Preview is saved as `preview.jpg` in current working directory
- Recommended interval: 100-500ms between captures depending on performance needs
- Serve the preview.jpg file to the web interface

### Session End (Live Preview Disable)
- Disable viewfinder to save battery: `gphoto2 --set-config viewfinder=0`

## Test Command for Continuous Preview
```bash
gphoto2 --set-config viewfinder=1
while true; do
  gphoto2 --capture-preview --force-overwrite
  sleep 0.2
done
```

## Important Notes
- The viewfinder MUST be enabled before ANY preview capture will work
- Without `viewfinder=1`, you'll get PTP timeout errors or "Could not find device" errors
- The preview.jpg file location is relative to the working directory where gphoto2 is executed
- Remember to disable viewfinder when done to preserve camera battery
- Consider error handling for camera disconnection or USB issues

## Working Directory
Current implementation is in: `~/film-scanner-web`
