#!/usr/bin/env python3
"""
Canon R100 Connection Diagnostic Tool
Tests if camera has CCAPI enabled and is accessible
"""

import requests
import urllib3
import socket
import subprocess
import sys

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

print("="*60)
print("   CANON R100 CONNECTION DIAGNOSTIC")
print("="*60)
print()

# Get camera IP
camera_ip = input("Enter camera IP address (or press Enter to scan): ").strip()

if not camera_ip:
    print("\n🔍 Scanning common camera IPs...")
    common_ips = ["192.168.1.2", "192.168.1.10", "192.168.50.10", "192.168.1.50"]
    
    # Get local network
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        network_prefix = '.'.join(local_ip.split('.')[:-1])
        
        for i in range(2, 20):
            common_ips.append(f"{network_prefix}.{i}")
    except:
        pass
    
    found = None
    for ip in common_ips:
        try:
            print(f"   Trying {ip}...", end=" ")
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "1", ip],
                capture_output=True,
                timeout=2
            )
            if result.returncode == 0:
                print("✓ responds")
                found = ip
                break
            else:
                print("✗")
        except:
            print("✗")
    
    if not found:
        print("\n❌ No camera found on network")
        print("\nTroubleshooting:")
        print("1. Check camera WiFi is enabled")
        print("2. Check camera is on same network as Pi")
        print("3. Check camera WiFi details for IP address")
        sys.exit(1)
    
    camera_ip = found
    print(f"\n✓ Found device at {camera_ip}")

print("\n" + "="*60)
print(f"Testing: {camera_ip}")
print("="*60)

# Test 1: Ping
print("\nTest 1: Network Connectivity")
print("-"*60)
try:
    result = subprocess.run(
        ["ping", "-c", "3", camera_ip],
        capture_output=True,
        timeout=5
    )
    if result.returncode == 0:
        print(f"✓ Camera responds to ping at {camera_ip}")
    else:
        print(f"✗ Camera doesn't respond to ping")
        print("   Check camera is on network and IP is correct")
        sys.exit(1)
except Exception as e:
    print(f"✗ Ping failed: {e}")
    sys.exit(1)

# Test 2: Port 8080 accessibility
print("\nTest 2: CCAPI Port 8080")
print("-"*60)
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    result = sock.connect_ex((camera_ip, 8080))
    sock.close()
    
    if result == 0:
        print(f"✓ Port 8080 is open on {camera_ip}")
    else:
        print(f"✗ Port 8080 is CLOSED or filtered")
        print("\n⚠️  CRITICAL ISSUE:")
        print("   Port 8080 should be open for CCAPI")
        print("\nPossible causes:")
        print("   1. CCAPI not enabled on camera (most likely)")
        print("   2. Camera in smartphone mode (not PC/Remote mode)")
        print("   3. Camera firewall blocking port")
        print("\nSolution:")
        print("   See R100_CCAPI_ACTIVATION_GUIDE.md for activation steps")
        sys.exit(1)
except Exception as e:
    print(f"✗ Port check failed: {e}")

# Test 3: CCAPI endpoint
print("\nTest 3: CCAPI API Endpoint")
print("-"*60)
url = f"http://{camera_ip}:8080/ccapi"

try:
    print(f"Requesting: {url}")
    response = requests.get(url, timeout=5, verify=False)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code in [200, 301, 302]:
        print("✓ CCAPI endpoint responds!")
    else:
        print(f"⚠️  Unusual response: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
except requests.exceptions.ConnectionError:
    print("✗ Connection refused")
    print("\n⚠️  CCAPI NOT ACCESSIBLE")
    print("\nThis means:")
    print("   1. CCAPI is not enabled on camera, OR")
    print("   2. Camera is in wrong mode (smartphone vs PC)")
    print("\nSolution:")
    print("   1. Enable CCAPI using Canon EOS Utility")
    print("   2. Set camera to Remote Control/PC mode (not smartphone)")
    print("   3. See R100_CCAPI_ACTIVATION_GUIDE.md")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)

# Test 4: Device information
print("\nTest 4: Camera Information")
print("-"*60)
info_url = f"http://{camera_ip}:8080/ccapi/ver100/deviceinformation"

try:
    response = requests.get(info_url, timeout=5, verify=False)
    
    if response.status_code == 200:
        info = response.json()
        print("✓ CCAPI FULLY FUNCTIONAL!")
        print(f"\nCamera Model: {info.get('productname', 'Unknown')}")
        print(f"Firmware: {info.get('firmwareversion', 'Unknown')}")
        print(f"Serial: {info.get('serialnumber', 'Unknown')}")
        
        print("\n" + "="*60)
        print("✅ SUCCESS! Camera is ready for WiFi control!")
        print("="*60)
        print("\nYou can now:")
        print("1. Run the film scanner: python3 web_app.py")
        print("2. Setup Canon WiFi in web interface")
        print("3. Use camera IP:", camera_ip)
        
    else:
        print(f"⚠️  Camera responded but with error: {response.status_code}")
        print("Response:", response.text[:200])
        
        if response.status_code == 401:
            print("\n⚠️  Authentication required")
            print("   Camera may need pairing first")
        elif response.status_code == 403:
            print("\n⚠️  Access forbidden")
            print("   Check camera is in Remote Control mode")
        
except requests.exceptions.ConnectionError:
    print("✗ Cannot get device information")
    print("\n⚠️  CCAPI is present but not fully functional")
    print("\nPossible issues:")
    print("   1. Camera in wrong mode (set to Remote Control/PC)")
    print("   2. CCAPI partially enabled")
    print("   3. Firmware issue")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "="*60)
print("Diagnostic Complete")
print("="*60)

# Test 5: Camera mode check
print("\nTest 5: Camera Mode Detection")
print("-"*60)
print("\nCheck camera screen:")
print("• Does it say 'PC Remote' or 'Remote Control'? → ✓ Correct")
print("• Does it say 'Waiting for smartphone'? → ✗ Wrong mode")
print("• Does it show WiFi icon? → ✓ WiFi enabled")
print("\nIf camera says 'waiting for smartphone':")
print("  → Change mode to PC/Remote Control (not smartphone app)")

print("\n" + "="*60)
print("Next Steps:")
print("="*60)

if response.status_code == 200:
    print("\n✅ Camera is ready! Use IP:", camera_ip)
else:
    print("\n⚠️  Camera needs CCAPI activation")
    print("\nFollow these steps:")
    print("1. Read: R100_CCAPI_ACTIVATION_GUIDE.md")
    print("2. Download Canon EOS Utility on Windows/Mac")
    print("3. Connect camera via USB to computer")
    print("4. Enable CCAPI in EOS Utility settings")
    print("5. On camera: Set to Remote Control mode (not smartphone)")
    print("6. Run this test again")

print()

