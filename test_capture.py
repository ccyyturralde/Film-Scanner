#!/usr/bin/env python3
"""
Simple Camera Capture Test
Tests if the camera can capture multiple times in succession
"""

import subprocess
import time
import sys

def kill_gphoto2():
    """Kill all gphoto2 processes"""
    print("  Cleaning up processes...", end='', flush=True)
    subprocess.run(["killall", "gphoto2"], capture_output=True, timeout=1)
    subprocess.run(["killall", "-9", "gphoto2"], capture_output=True, timeout=1)
    subprocess.run(["killall", "gvfs-gphoto2-volume-monitor"], capture_output=True, timeout=1)
    time.sleep(0.5)
    print(" done")

def test_capture(attempt_num):
    """Test a single capture"""
    print(f"\nCapture #{attempt_num}:")
    
    # Always clean up first
    kill_gphoto2()
    time.sleep(1.5)  # Give USB time to release
    
    # Try capture with force-overwrite
    print("  Capturing...", end='', flush=True)
    result = subprocess.run(
        ["gphoto2", "--capture-image", "--force-overwrite"],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    if result.returncode == 0:
        print(" ✓ SUCCESS")
        return True
    else:
        print(f" ✗ FAILED (code: {result.returncode})")
        if result.stderr:
            print(f"  Error: {result.stderr[:100]}")
        
        # Try reset on failure
        print("  Attempting reset...", end='', flush=True)
        subprocess.run(["gphoto2", "--reset"], capture_output=True, timeout=3)
        time.sleep(2)
        print(" done")
        return False

def main():
    print("="*50)
    print("CAMERA CAPTURE REPEATABILITY TEST")
    print("="*50)
    print("\nThis will attempt 5 captures in succession.")
    print("Press Ctrl+C to cancel at any time.\n")
    
    # Initial check
    print("Checking camera connection...")
    result = subprocess.run(
        ["gphoto2", "--auto-detect"],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if "usb" not in result.stdout.lower():
        print("✗ No camera detected!")
        print("  Check that camera is ON and in PTP/MTP mode")
        sys.exit(1)
    
    print("✓ Camera detected\n")
    
    # Run capture tests
    successes = 0
    failures = 0
    
    for i in range(5):
        if test_capture(i + 1):
            successes += 1
        else:
            failures += 1
        
        if i < 4:  # Don't wait after last capture
            print("  Waiting 3 seconds before next capture...")
            time.sleep(3)
    
    # Summary
    print("\n" + "="*50)
    print("RESULTS:")
    print(f"  Successful captures: {successes}/5")
    print(f"  Failed captures: {failures}/5")
    
    if successes == 5:
        print("\n✓ All captures successful! The fix is working.")
    elif successes > 0:
        print("\n⚠ Partial success. May need more delay or reset between captures.")
    else:
        print("\n✗ All captures failed. Check camera settings and connection.")
    
    print("="*50)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user")
        sys.exit(0)
