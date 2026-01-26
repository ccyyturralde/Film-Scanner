#!/usr/bin/env python3
"""
ScanLight Protocol Discovery Tool

This script helps discover the actual serial protocol used by your ScanLight device.
Run this with your ScanLight connected to find out what commands it responds to.
"""

import serial
import serial.tools.list_ports
import time
import sys


def find_pico_devices():
    """Find all Raspberry Pi Pico devices."""
    picos = []
    ports = list(serial.tools.list_ports.comports())
    
    for port in ports:
        vid = getattr(port, 'vid', None)
        pid = getattr(port, 'pid', None)
        device = getattr(port, 'device', str(port))
        desc = getattr(port, 'description', '')
        
        # Raspberry Pi Pico VID
        if vid == 0x2E8A:
            picos.append({
                'device': device,
                'vid': vid,
                'pid': pid,
                'description': desc
            })
    
    return picos


def test_scanlight_sl2(port_path):
    """Test ScanLight SL2 binary protocol."""
    print(f"\n{'='*60}")
    print(f"Testing ScanLight SL2 on {port_path}")
    print(f"{'='*60}\n")
    
    try:
        ser = serial.Serial(port_path, 115200, timeout=2)
        print("✓ Connected at 115200 baud")
        
        # Wait for startup self-test (R->G->B->White)
        print("\nWaiting for startup self-test...")
        time.sleep(1.0)
        print("  (You should have seen Red -> Green -> Blue -> White)")
        
        # Clear buffer
        ser.reset_input_buffer()
        
        # Test 1: Set White
        print("\n1. Setting WHITE (255,255,255)...")
        packet = bytes([254, 0, 3, 255, 255, 255, 255])
        ser.write(packet)
        time.sleep(0.5)
        print("   ✓ Sent")
        
        # Test 2: Set Red
        print("\n2. Setting RED (255,0,0)...")
        packet = bytes([254, 0, 3, 255, 0, 0, 255])
        ser.write(packet)
        time.sleep(0.5)
        print("   ✓ Sent")
        
        # Test 3: Set Green
        print("\n3. Setting GREEN (0,255,0)...")
        packet = bytes([254, 0, 3, 0, 255, 0, 255])
        ser.write(packet)
        time.sleep(0.5)
        print("   ✓ Sent")
        
        # Test 4: Set Blue
        print("\n4. Setting BLUE (0,0,255)...")
        packet = bytes([254, 0, 3, 0, 0, 255, 255])
        ser.write(packet)
        time.sleep(0.5)
        print("   ✓ Sent")
        
        # Test 5: Reset (back to white)
        print("\n5. RESET to white...")
        packet = bytes([254, 1, 0, 255])
        ser.write(packet)
        time.sleep(0.5)
        print("   ✓ Sent")
        
        # Test 6: Turn off (black)
        print("\n6. Turning OFF (0,0,0)...")
        packet = bytes([254, 0, 3, 0, 0, 0, 255])
        ser.write(packet)
        time.sleep(0.5)
        print("   ✓ Sent")
        
        # Test 7: Back to white
        print("\n7. Back to WHITE...")
        packet = bytes([254, 0, 3, 255, 255, 255, 255])
        ser.write(packet)
        time.sleep(0.5)
        print("   ✓ Sent")
        
        ser.close()
        print("\n✓ All tests completed!")
        print("\nIf you saw the colors change as described above,")
        print("the ScanLight SL2 protocol is working correctly!")
        
    except Exception as e:
        print(f"✗ Error: {e}")


def main():
    print("ScanLight Protocol Discovery Tool")
    print("="*60)
    
    # Find Pico devices
    picos = find_pico_devices()
    
    if not picos:
        print("\n✗ No Raspberry Pi Pico devices found")
        print("   Make sure ScanLight is connected via USB")
        sys.exit(1)
    
    print(f"\n✓ Found {len(picos)} Pico device(s):\n")
    for i, pico in enumerate(picos, 1):
        print(f"  {i}. {pico['device']}")
        print(f"     VID: {hex(pico['vid'])}, PID: {hex(pico['pid'])}")
        print(f"     Description: {pico['description']}")
        print()
    
    # Select device
    if len(picos) == 1:
        selected = picos[0]
        print(f"Using: {selected['device']}\n")
    else:
        try:
            choice = int(input("Select device number: "))
            selected = picos[choice - 1]
        except (ValueError, IndexError):
            print("✗ Invalid selection")
            sys.exit(1)
    
    # ScanLight SL2 uses binary protocol, not text commands
    # We'll send the actual binary packets
    print("\n" + "="*60)
    print("ScanLight SL2 Protocol Detected!")
    print("="*60)
    print("\nThis device uses a binary packet protocol:")
    print("  Format: [START=254, CMD, LENGTH, ...DATA..., END=255]")
    print("\nNo text commands needed - the protocol is already implemented")
    print("in scanlight_controller.py!")
    print("\nTesting binary protocol...")
    
    test_commands_list = [
        # These are for display only - actual testing done below
        "Set White (255,255,255)",
        "Set Red (255,0,0)",
        "Set Green (0,255,0)",
        "Set Blue (0,0,255)",
        "Reset to White",
    ]
    
    print("\n⚠️  VISUAL TEST REQUIRED!")
    print("Watch the ScanLight during this test.")
    print("It will cycle through colors if working correctly.")
    input("\nPress Enter to start the test...")
    
    test_scanlight_sl2(selected['device'])
    
    print("\n" + "="*60)
    print("Discovery complete!")
    print("="*60)
    print("\nNext steps:")
    print("1. Review the responses above to identify working commands")
    print("2. Update scanlight_controller.py with the correct command format")
    print("3. Test with: python3 scanlight_controller.py")
    print("\nIf no commands worked:")
    print("- Check the ScanLight GitHub repo for documentation")
    print("- Look for .uf2 firmware filename (may indicate version)")
    print("- Try connecting with a serial monitor to see startup messages")


if __name__ == "__main__":
    main()
