#!/usr/bin/env python3
"""
Camera Testing and Diagnostics Tool
Run this to diagnose camera connection and capabilities
"""

import subprocess
import sys
import time

def run_cmd(cmd, timeout=5):
    """Run command and return output"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            text=True
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", str(e)

print("="*60)
print("CAMERA DIAGNOSTICS TOOL")
print("="*60)

# 1. Check gphoto2 installation
print("\n1. Checking gphoto2 installation...")
code, out, err = run_cmd(['which', 'gphoto2'])
if code == 0:
    print(f"   ✓ gphoto2 found at: {out.strip()}")
    code, out, err = run_cmd(['gphoto2', '--version'])
    if code == 0:
        print(f"   Version: {out.split(chr(10))[0]}")
else:
    print("   ✗ gphoto2 not found!")
    sys.exit(1)

# 2. Kill any existing gphoto2 processes
print("\n2. Cleaning up existing gphoto2 processes...")
subprocess.run(['killall', 'gphoto2'], capture_output=True)
time.sleep(1)

# 3. Detect camera
print("\n3. Detecting camera...")
code, out, err = run_cmd(['gphoto2', '--auto-detect'], timeout=10)
print(f"   Return code: {code}")
if out:
    print(f"   Output:\n{out}")
if err:
    print(f"   Errors:\n{err}")

if 'usb' not in out.lower():
    print("\n   ✗ No camera detected via USB!")
    print("   Check:")
    print("   - Camera is turned on")
    print("   - USB cable is connected (data cable, not power-only)")
    print("   - Camera is in the correct mode (not in 'charge only')")
    sys.exit(1)

camera_model = "Unknown"
for line in out.split('\n'):
    if 'usb' in line.lower():
        camera_model = line.split('usb')[0].strip()
        break

print(f"   ✓ Camera detected: {camera_model}")

# 4. Check camera abilities
print("\n4. Checking camera capabilities...")
code, out, err = run_cmd(['gphoto2', '--abilities'], timeout=10)
if code == 0:
    print("   Camera abilities:")
    for line in out.split('\n'):
        if 'Capture' in line or 'capture' in line:
            print(f"   {line}")
else:
    print(f"   ✗ Failed to get abilities: {err}")

# 5. List camera configuration
print("\n5. Listing camera configuration...")
code, out, err = run_cmd(['gphoto2', '--list-config'], timeout=10)
if code == 0:
    has_autofocus = 'autofocus' in out.lower()
    has_viewfinder = 'viewfinder' in out.lower()
    has_capture = 'capture' in out.lower()
    
    print(f"   Autofocus support: {'✓' if has_autofocus else '✗'}")
    print(f"   Viewfinder support: {'✓' if has_viewfinder else '✗'}")
    print(f"   Capture support: {'✓' if has_capture else '✗'}")
    
    print("\n   Available config options:")
    for line in out.split('\n')[:20]:  # First 20 options
        if line.strip():
            print(f"   {line}")
else:
    print(f"   ✗ Failed to list config: {err}")

# 6. Test capture preview
print("\n6. Testing capture preview...")
code, out, err = run_cmd(['gphoto2', '--capture-preview', '--filename=/tmp/test_preview.jpg'], timeout=10)
print(f"   Return code: {code}")
if err:
    print(f"   Errors: {err}")
if code == 0:
    print("   ✓ Preview capture works!")
else:
    print("   ✗ Preview capture failed")

# 7. Test actual capture
print("\n7. Testing image capture (will NOT save to Pi)...")
print("   This will take a photo and store it ONLY on camera SD card...")
input("   Press Enter to continue (or Ctrl+C to skip)...")

code, out, err = run_cmd(['gphoto2', '--capture-image'], timeout=30)
print(f"   Return code: {code}")
if out:
    print(f"   Output: {out}")
if err:
    print(f"   Errors: {err}")

if code == 0:
    print("   ✓ Image capture works!")
else:
    print("   ✗ Image capture failed")

# 8. Test autofocus
print("\n8. Testing autofocus...")
code, out, err = run_cmd(['gphoto2', '--set-config', 'autofocus=1'], timeout=10)
print(f"   Return code: {code}")
if err:
    print(f"   Errors: {err}")
if code == 0:
    print("   ✓ Autofocus command works!")
else:
    print("   ✗ Autofocus command failed")

# 9. Get full camera summary
print("\n9. Getting camera summary...")
code, out, err = run_cmd(['gphoto2', '--summary'], timeout=10)
if code == 0:
    print("   Camera Summary:")
    print(out[:500])  # First 500 chars
else:
    print(f"   ✗ Failed to get summary: {err}")

# 10. Check for video devices (HDMI capture cards)
print("\n10. Checking for video capture devices...")
import os
found_video = False
for i in range(10):
    device = f'/dev/video{i}'
    if os.path.exists(device):
        print(f"   ✓ Found: {device}")
        found_video = True
        code, out, err = run_cmd(['v4l2-ctl', '--device', device, '--info'], timeout=2)
        if code == 0:
            for line in out.split('\n')[:3]:
                print(f"      {line}")

if not found_video:
    print("   ✗ No video devices found")
    print("   Consider using a USB HDMI capture card for live preview!")

print("\n" + "="*60)
print("DIAGNOSTICS COMPLETE")
print("="*60)
print("\nCommon issues and fixes:")
print("1. If capture fails: Check camera is in correct USB mode")
print("2. If preview fails: Some cameras don't support it well")
print("3. If autofocus fails: Camera may not support remote AF")
print("4. For better live preview: Use HDMI capture card!")
print("="*60)

