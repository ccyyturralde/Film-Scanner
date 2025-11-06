#!/usr/bin/env python3
"""
Canon R100 WiFi Control Module
Handles WiFi connection, live view streaming, and connection monitoring
Uses Canon Camera Control API (CCAPI)
"""

import requests
import threading
import time
import json
import socket
from datetime import datetime
from requests.auth import HTTPDigestAuth
import urllib3

# Disable SSL warnings for camera's self-signed certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class CanonWiFiCamera:
    """Canon R100 WiFi Camera Controller"""
    
    def __init__(self):
        self.camera_ip = None
        self.connected = False
        self.pairing_code = None
        self.session = None
        self.liveview_active = False
        self.liveview_thread = None
        self.liveview_stop_event = threading.Event()
        self.connection_check_thread = None
        self.connection_lost_callback = None
        self.last_frame = None
        self.last_frame_time = None
        
        # Camera info
        self.camera_model = "Unknown"
        self.battery_level = None
        self.firmware_version = None
        
        # CCAPI endpoints
        self.api_base = None
        
    def scan_for_camera(self, timeout=10):
        """
        Scan local network for Canon cameras
        Canon cameras typically broadcast mDNS service "_ccapi._tcp"
        """
        print("🔍 Scanning for Canon cameras on network...")
        
        # Try common Canon camera IP addresses
        common_ips = [
            "192.168.1.2",
            "192.168.1.10", 
            "192.168.10.1",
            "192.168.50.10"
        ]
        
        # Get local network range
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            network_prefix = '.'.join(local_ip.split('.')[:-1])
            
            # Add local network range to scan
            for i in [2, 10, 20, 50, 100]:
                common_ips.append(f"{network_prefix}.{i}")
        except:
            pass
        
        # Try each IP
        for ip in common_ips:
            print(f"   Trying {ip}...")
            if self._test_camera_connection(ip):
                print(f"✓ Found Canon camera at {ip}")
                return ip
        
        print("✗ No Canon camera found on network")
        return None
    
    def _test_camera_connection(self, ip, timeout=2):
        """Test if a Canon camera is at this IP"""
        try:
            url = f"http://{ip}:8080/ccapi"
            response = requests.get(url, timeout=timeout, verify=False)
            
            # Canon CCAPI returns 200 or redirects to version endpoint
            if response.status_code in [200, 301, 302]:
                return True
        except:
            pass
        
        return False
    
    def connect(self, camera_ip=None):
        """
        Connect to Canon camera via WiFi
        If camera_ip is None, will scan for camera
        """
        print("\n" + "="*60)
        print("   CANON R100 WIFI CONNECTION")
        print("="*60)
        
        # Find camera if IP not provided
        if not camera_ip:
            camera_ip = self.scan_for_camera()
            if not camera_ip:
                print("\n❌ Could not find Canon camera on network")
                print("\nTroubleshooting:")
                print("1. Ensure camera WiFi is ON")
                print("2. Connect Pi to same WiFi network as camera")
                print("3. Check camera WiFi settings for IP address")
                return False
        
        self.camera_ip = camera_ip
        self.api_base = f"http://{camera_ip}:8080/ccapi"
        
        print(f"\n📡 Connecting to camera at {camera_ip}...")
        
        # Test connection and get device info
        try:
            response = requests.get(
                f"{self.api_base}/ver100/deviceinformation",
                timeout=5,
                verify=False
            )
            
            if response.status_code == 200:
                info = response.json()
                self.camera_model = info.get('productname', 'Canon Camera')
                self.firmware_version = info.get('firmwareversion', 'Unknown')
                
                print(f"✓ Connected to {self.camera_model}")
                print(f"  Firmware: {self.firmware_version}")
                
                self.connected = True
                self._start_connection_monitor()
                
                return True
            else:
                print(f"✗ Camera responded with status {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            print(f"✗ Connection timeout - camera not responding at {camera_ip}")
            print("   Check camera WiFi is enabled and IP address is correct")
            return False
        except requests.exceptions.ConnectionError:
            print(f"✗ Connection failed - cannot reach {camera_ip}")
            print("   Ensure Pi and camera are on same network")
            return False
        except Exception as e:
            print(f"✗ Connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from camera"""
        print("🔌 Disconnecting from camera...")
        
        # Stop live view if active
        if self.liveview_active:
            self.stop_liveview()
        
        # Stop connection monitor
        if self.connection_check_thread:
            self.connection_check_thread = None
        
        self.connected = False
        self.camera_ip = None
        
        print("✓ Disconnected")
    
    def _start_connection_monitor(self):
        """Start background thread to monitor connection"""
        if self.connection_check_thread is None or not self.connection_check_thread.is_alive():
            self.connection_check_thread = threading.Thread(
                target=self._connection_monitor_loop,
                daemon=True
            )
            self.connection_check_thread.start()
            print("✓ Connection monitor started")
    
    def _connection_monitor_loop(self):
        """Background loop to check connection status"""
        consecutive_failures = 0
        
        while self.connected:
            try:
                # Ping camera every 5 seconds
                time.sleep(5)
                
                if not self.check_connection():
                    consecutive_failures += 1
                    print(f"⚠ Connection check failed ({consecutive_failures}/3)")
                    
                    if consecutive_failures >= 3:
                        print("❌ Connection lost to camera!")
                        self.connected = False
                        
                        # Notify callback if registered
                        if self.connection_lost_callback:
                            self.connection_lost_callback()
                        
                        break
                else:
                    consecutive_failures = 0
                    
            except Exception as e:
                print(f"Connection monitor error: {e}")
                consecutive_failures += 1
    
    def check_connection(self):
        """Check if camera is still connected"""
        if not self.camera_ip:
            return False
        
        try:
            response = requests.get(
                f"{self.api_base}/ver100/deviceinformation",
                timeout=3,
                verify=False
            )
            return response.status_code == 200
        except:
            return False
    
    def get_battery_level(self):
        """Get camera battery level"""
        try:
            response = requests.get(
                f"{self.api_base}/ver100/devicestatus/battery",
                timeout=3,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                self.battery_level = data.get('level', 'Unknown')
                return self.battery_level
        except:
            pass
        
        return None
    
    def start_liveview(self, callback=None):
        """
        Start live view streaming
        callback: function to call with each frame (receives jpeg bytes)
        """
        if self.liveview_active:
            print("⚠ Live view already active")
            return True
        
        if not self.connected:
            print("❌ Cannot start live view - not connected to camera")
            return False
        
        print("📹 Starting live view...")
        
        # Enable live view on camera
        try:
            response = requests.post(
                f"{self.api_base}/ver100/shooting/liveview",
                json={"liveviewsize": "medium"},  # medium = 1024x768, small = 512x384
                timeout=5,
                verify=False
            )
            
            if response.status_code not in [200, 201]:
                print(f"✗ Failed to start live view: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"✗ Failed to start live view: {e}")
            return False
        
        # Start streaming thread
        self.liveview_active = True
        self.liveview_stop_event.clear()
        self.liveview_thread = threading.Thread(
            target=self._liveview_loop,
            args=(callback,),
            daemon=True
        )
        self.liveview_thread.start()
        
        print("✓ Live view started")
        return True
    
    def stop_liveview(self):
        """Stop live view streaming"""
        if not self.liveview_active:
            return True
        
        print("📹 Stopping live view...")
        
        # Stop thread
        self.liveview_active = False
        self.liveview_stop_event.set()
        
        if self.liveview_thread:
            self.liveview_thread.join(timeout=2)
        
        # Disable live view on camera
        try:
            requests.delete(
                f"{self.api_base}/ver100/shooting/liveview",
                timeout=3,
                verify=False
            )
        except:
            pass
        
        print("✓ Live view stopped")
        return True
    
    def _liveview_loop(self, callback):
        """Live view streaming loop (runs in background thread)"""
        stream_url = f"{self.api_base}/ver100/shooting/liveview/flip"
        
        frame_count = 0
        error_count = 0
        
        while not self.liveview_stop_event.is_set() and self.liveview_active:
            try:
                # Request live view frame
                response = requests.get(
                    stream_url,
                    timeout=3,
                    verify=False,
                    stream=False
                )
                
                if response.status_code == 200:
                    # Parse multipart response to get JPEG
                    content_type = response.headers.get('Content-Type', '')
                    
                    if 'multipart' in content_type:
                        # Extract boundary
                        boundary = content_type.split('boundary=')[1].strip()
                        parts = response.content.split(f'--{boundary}'.encode())
                        
                        for part in parts:
                            if b'Content-Type: image/jpeg' in part:
                                # Find JPEG data
                                jpeg_start = part.find(b'\xff\xd8')  # JPEG start marker
                                jpeg_end = part.find(b'\xff\xd9')    # JPEG end marker
                                
                                if jpeg_start != -1 and jpeg_end != -1:
                                    jpeg_data = part[jpeg_start:jpeg_end+2]
                                    
                                    self.last_frame = jpeg_data
                                    self.last_frame_time = datetime.now()
                                    
                                    if callback:
                                        callback(jpeg_data)
                                    
                                    frame_count += 1
                                    error_count = 0
                                    break
                    else:
                        # Single JPEG response
                        self.last_frame = response.content
                        self.last_frame_time = datetime.now()
                        
                        if callback:
                            callback(response.content)
                        
                        frame_count += 1
                        error_count = 0
                else:
                    error_count += 1
                    if error_count > 5:
                        print(f"⚠ Live view stream error: {response.status_code}")
                        time.sleep(1)
                
                # Control frame rate (~10 FPS)
                time.sleep(0.1)
                
            except Exception as e:
                error_count += 1
                if error_count % 10 == 0:
                    print(f"⚠ Live view error: {e}")
                time.sleep(0.5)
        
        print(f"📹 Live view stopped (streamed {frame_count} frames)")
    
    def autofocus(self):
        """
        Trigger autofocus on camera
        Note: This uses gphoto2 as Canon CCAPI AF can be complex
        """
        print("📷 Autofocus via CCAPI not yet implemented")
        print("   Using gphoto2 for autofocus...")
        return False
    
    def get_status(self):
        """Get camera status dictionary"""
        return {
            'connected': self.connected,
            'camera_ip': self.camera_ip,
            'camera_model': self.camera_model,
            'firmware_version': self.firmware_version,
            'battery_level': self.battery_level,
            'liveview_active': self.liveview_active,
            'last_frame_time': self.last_frame_time.isoformat() if self.last_frame_time else None
        }
    
    def setup_wizard(self):
        """
        Interactive setup wizard for pairing with Canon R100
        Returns camera IP if successful, None otherwise
        """
        print("\n" + "="*60)
        print("   CANON R100 WIFI SETUP WIZARD")
        print("="*60)
        print("\nThis wizard will help you connect your Canon R100 via WiFi.\n")
        
        print("📋 Prerequisites:")
        print("   1. Canon R100 with WiFi enabled")
        print("   2. Camera and Pi on same WiFi network")
        print("   3. Camera in 'Remote Control' mode\n")
        
        input("Press ENTER when ready to continue...")
        
        print("\n" + "-"*60)
        print("Step 1: Enable Camera WiFi")
        print("-"*60)
        print("\nOn your Canon R100:")
        print("1. Press MENU button")
        print("2. Go to: Wireless Communication Settings")
        print("3. Enable: WiFi/Bluetooth Connection")
        print("4. Select: Connect to Smartphone")
        print("5. Choose: Camera Access Point Mode or Infrastructure Mode")
        print("\nNOTE: If using Camera AP Mode, connect your Pi to the")
        print("      camera's WiFi network first!")
        
        input("\nPress ENTER when camera WiFi is enabled...")
        
        print("\n" + "-"*60)
        print("Step 2: Find Camera on Network")
        print("-"*60)
        
        print("\nHow would you like to connect?\n")
        print("1. Auto-scan network (recommended)")
        print("2. Enter camera IP manually")
        
        while True:
            choice = input("\nChoice (1-2): ").strip()
            
            if choice == '1':
                # Auto-scan
                camera_ip = self.scan_for_camera(timeout=10)
                if camera_ip:
                    break
                else:
                    print("\n⚠ Auto-scan failed")
                    retry = input("Try manual entry? (y/n): ").strip().lower()
                    if retry == 'y':
                        choice = '2'
                        continue
                    else:
                        return None
            
            if choice == '2':
                # Manual entry
                while True:
                    camera_ip = input("\nEnter camera IP address: ").strip()
                    
                    # Validate IP
                    try:
                        socket.inet_aton(camera_ip)
                        
                        print(f"Testing connection to {camera_ip}...")
                        if self._test_camera_connection(camera_ip):
                            print(f"✓ Camera found at {camera_ip}")
                            break
                        else:
                            print(f"✗ No camera at {camera_ip}")
                            retry = input("Try another IP? (y/n): ").strip().lower()
                            if retry != 'y':
                                return None
                    except:
                        print("Invalid IP address format")
                break
        
        print("\n" + "-"*60)
        print("Step 3: Test Connection")
        print("-"*60)
        
        if self.connect(camera_ip):
            print("\n" + "="*60)
            print("✓ SETUP COMPLETE!")
            print("="*60)
            print(f"\nCamera IP: {camera_ip}")
            print(f"Model: {self.camera_model}")
            print(f"Firmware: {self.firmware_version}")
            print("\nThis IP will be saved to your configuration.")
            print("="*60 + "\n")
            
            return camera_ip
        else:
            print("\n❌ Connection test failed")
            return None


def main():
    """Test Canon WiFi connection"""
    camera = CanonWiFiCamera()
    
    # Run setup wizard
    camera_ip = camera.setup_wizard()
    
    if camera_ip:
        print("\nTesting live view...")
        
        def frame_callback(jpeg_data):
            print(f"  Frame received: {len(jpeg_data)} bytes")
        
        if camera.start_liveview(callback=frame_callback):
            print("Live view active - streaming for 10 seconds...")
            time.sleep(10)
            camera.stop_liveview()
        
        camera.disconnect()
    else:
        print("Setup failed")


if __name__ == '__main__':
    main()

