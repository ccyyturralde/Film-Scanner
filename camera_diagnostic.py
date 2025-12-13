#!/usr/bin/env python3
"""
Camera Capture Diagnostic Tool
Run this to diagnose issues with gphoto2 camera capture
"""

import subprocess
import time
import sys
import os

def run_command(cmd, timeout=10):
    """Run a command and return result"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)

def kill_gphoto2():
    """Kill all gphoto2 processes"""
    print("🧹 Cleaning up gphoto2 processes...")
    subprocess.run(["killall", "gphoto2"], capture_output=True, timeout=1)
    time.sleep(0.2)
    subprocess.run(["killall", "-9", "gphoto2"], capture_output=True, timeout=1)
    subprocess.run(["killall", "gvfs-gphoto2-volume-monitor"], capture_output=True, timeout=1)
    subprocess.run(["killall", "-9", "PTPCamera"], capture_output=True, timeout=1)
    time.sleep(0.5)
    print("   ✓ Cleanup complete")

def main():
    print("="*60)
    print("CAMERA CAPTURE DIAGNOSTIC")
    print("="*60)
    
    # Step 1: Check for running processes
    print("\n1. Checking for interfering processes...")
    rc, out, err = run_command(["ps", "aux"])
    gphoto_procs = [line for line in out.split('\n') if 'gphoto' in line.lower()]
    if gphoto_procs:
        print("   ⚠ Found gphoto2 processes:")
        for proc in gphoto_procs[:3]:  # Show first 3
            print(f"     {proc[:80]}...")
        kill_gphoto2()
    else:
        print("   ✓ No interfering processes")
    
    # Step 2: Check USB devices
    print("\n2. Checking USB devices...")
    rc, out, err = run_command(["lsusb"])
    camera_found = False
    for line in out.split('\n'):
        if any(brand in line.lower() for brand in ['canon', 'nikon', 'sony', 'fuji', 'olympus']):
            print(f"   📷 Found: {line}")
            camera_found = True
    if not camera_found:
        print("   ⚠ No camera found in USB devices")
        print("   → Check: Camera is ON and connected via USB")
    
    # Step 3: Test gphoto2 detection
    print("\n3. Testing gphoto2 camera detection...")
    rc, out, err = run_command(["gphoto2", "--auto-detect"])
    if rc == 0 and "usb" in out.lower():
        print("   ✓ Camera detected by gphoto2:")
        for line in out.split('\n')[2:]:  # Skip header lines
            if 'usb' in line.lower():
                print(f"     {line}")
    else:
        print("   ✗ Camera not detected by gphoto2")
        print("   → Check: Camera is in PTP/MTP USB mode (not Mass Storage)")
        if err:
            print(f"   Error: {err[:200]}")
        return
    
    # Step 4: Check camera abilities
    print("\n4. Checking camera capabilities...")
    rc, out, err = run_command(["gphoto2", "--abilities"], timeout=5)
    if rc == 0:
        if "capture" in out.lower():
            print("   ✓ Camera supports capture")
        else:
            print("   ⚠ Camera may not support capture via USB")
    else:
        print("   ⚠ Could not query camera abilities")
    
    # Step 5: Test single capture
    print("\n5. Testing single capture...")
    kill_gphoto2()  # Clean slate
    time.sleep(1)
    
    print("   Attempting capture #1...")
    rc, out, err = run_command(["gphoto2", "--capture-image"], timeout=30)
    if rc == 0:
        print("   ✓ First capture successful!")
        if out:
            print(f"     Output: {out[:200]}")
    else:
        print(f"   ✗ First capture failed (code: {rc})")
        if err:
            print(f"     Error: {err[:200]}")
        return
    
    # Step 6: Test repeated capture
    print("\n6. Testing repeated captures...")
    for i in range(3):
        print(f"   Attempting capture #{i+2}...")
        
        # Clean between captures
        kill_gphoto2()
        time.sleep(1.5)  # Give camera time to reset
        
        rc, out, err = run_command(["gphoto2", "--capture-image"], timeout=30)
        if rc == 0:
            print(f"   ✓ Capture #{i+2} successful!")
        else:
            print(f"   ✗ Capture #{i+2} failed (code: {rc})")
            if err:
                error_lower = err.lower()
                if "busy" in error_lower or "claim" in error_lower or "lock" in error_lower:
                    print("     → Camera appears to be locked/busy")
                    print("     → Try: gphoto2 --reset")
                    # Try reset
                    print("     Attempting camera reset...")
                    subprocess.run(["gphoto2", "--reset"], capture_output=True, timeout=3)
                    time.sleep(2)
                elif "ptp" in error_lower:
                    print("     → PTP communication error")
                else:
                    print(f"     Error: {err[:200]}")
            break
        time.sleep(2)  # Wait between captures
    
    # Step 7: Test with --force-overwrite
    print("\n7. Testing capture with --force-overwrite flag...")
    kill_gphoto2()
    time.sleep(1.5)
    
    rc, out, err = run_command(["gphoto2", "--capture-image", "--force-overwrite"], timeout=30)
    if rc == 0:
        print("   ✓ Capture with --force-overwrite successful!")
    else:
        print(f"   ✗ Capture with --force-overwrite failed (code: {rc})")
    
    # Step 8: Check for alternative capture methods
    print("\n8. Checking alternative capture methods...")
    kill_gphoto2()
    time.sleep(1)
    
    # Test capture-image-and-download (different method)
    rc, out, err = run_command(["gphoto2", "--capture-image-and-download", "--filename=/tmp/test.jpg"], timeout=30)
    if rc == 0:
        print("   ✓ Capture-and-download method works!")
        if os.path.exists("/tmp/test.jpg"):
            size = os.path.getsize("/tmp/test.jpg")
            print(f"     File size: {size} bytes")
            os.remove("/tmp/test.jpg")
    else:
        print("   ✗ Capture-and-download method failed")
    
    # Final summary
    print("\n" + "="*60)
    print("DIAGNOSTIC SUMMARY")
    print("="*60)
    print("\nRecommendations based on results:")
    print("1. Always kill gphoto2 processes before capture")
    print("2. Add 1.5-2 second delay after killing processes")
    print("3. Consider using --force-overwrite flag")
    print("4. If repeated captures fail, use 'gphoto2 --reset' between attempts")
    print("5. Ensure camera is in PTP/MTP mode (not Mass Storage)")
    print("\nTo implement the fix, replace the methods in web_app.py")
    print("with the versions from capture_fix.py")
    print("="*60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDiagnostic cancelled by user")
        sys.exit(0)
