#!/usr/bin/env python3
"""
Configuration Manager for Film Scanner
Handles first-time setup, IP discovery, and persistent settings
"""

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

class ConfigManager:
    def __init__(self, config_file="scanner_config.json"):
        """Initialize config manager with default config file name"""
        self.config_dir = Path.home() / ".film_scanner"
        self.config_file = self.config_dir / config_file
        self.config = {}
        
    def config_exists(self):
        """Check if configuration file exists"""
        return self.config_file.exists()
    
    def load_config(self):
        """Load configuration from file"""
        if not self.config_exists():
            return None
        
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
            return self.config
        except Exception as e:
            print(f"Error loading config: {e}")
            return None
    
    def save_config(self, config):
        """Save configuration to file"""
        # Create config directory if it doesn't exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            self.config = config
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def delete_config(self):
        """Delete configuration file (for reset)"""
        try:
            if self.config_file.exists():
                self.config_file.unlink()
                print(f"Configuration deleted: {self.config_file}")
                return True
            else:
                print("No configuration file to delete")
                return False
        except Exception as e:
            print(f"Error deleting config: {e}")
            return False
    
    def get_local_ip(self):
        """Get the local IP address of this machine"""
        try:
            # Create a socket to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Connect to an external server (doesn't actually send data)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            return "127.0.0.1"
    
    def scan_network_for_pi(self):
        """Scan local network for Raspberry Pi devices"""
        print("\n🔍 Scanning network for Raspberry Pi devices...")
        print("This may take a moment...\n")
        
        local_ip = self.get_local_ip()
        network_prefix = '.'.join(local_ip.split('.')[:-1])
        
        pi_devices = []
        
        # Quick scan of common addresses
        for i in range(1, 255):
            ip = f"{network_prefix}.{i}"
            try:
                # Try to connect with a short timeout
                result = subprocess.run(
                    ["ping", "-c", "1", "-W", "1", ip],
                    capture_output=True,
                    timeout=2
                )
                
                if result.returncode == 0:
                    # Try to identify if it's a Pi by checking hostname
                    try:
                        hostname = socket.gethostbyaddr(ip)[0]
                        if 'raspberry' in hostname.lower() or 'pi' in hostname.lower():
                            pi_devices.append({'ip': ip, 'hostname': hostname})
                            print(f"✓ Found: {ip} ({hostname})")
                    except:
                        # If it responds to ping but no hostname, might still be a Pi
                        pass
            except:
                continue
        
        return pi_devices
    
    def interactive_setup(self):
        """Interactive first-time setup wizard"""
        print("\n" + "="*60)
        print("   FILM SCANNER - FIRST TIME SETUP")
        print("="*60)
        print("\nWelcome! Let's configure your Film Scanner.\n")
        
        # Check if we're running on the Pi itself
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
                is_raspberry_pi = 'Raspberry Pi' in cpuinfo
        except:
            is_raspberry_pi = False
        
        config = {
            'setup_complete': True,
            'setup_date': str(Path.home())
        }
        
        if is_raspberry_pi:
            print("📟 Running on Raspberry Pi - Local Mode")
            local_ip = self.get_local_ip()
            config['mode'] = 'local'
            config['pi_ip'] = local_ip
            config['hostname'] = socket.gethostname()
            
            print(f"\n✓ Configuration saved!")
            print(f"  Pi IP: {local_ip}")
            print(f"  Hostname: {socket.gethostname()}")
            
        else:
            print("💻 Running on external device - Remote Mode\n")
            print("How would you like to find your Raspberry Pi?\n")
            print("1. Auto-discover Pi on network (recommended)")
            print("2. Manually enter Pi IP address")
            print("3. Skip (use localhost - for testing only)")
            
            while True:
                choice = input("\nEnter your choice (1-3): ").strip()
                
                if choice == '1':
                    # Auto-discover
                    pi_devices = self.scan_network_for_pi()
                    
                    if not pi_devices:
                        print("\n⚠️  No Raspberry Pi devices found automatically.")
                        print("You can try manual entry or check your network connection.")
                        retry = input("\nRetry scan? (y/n): ").strip().lower()
                        if retry == 'y':
                            continue
                        else:
                            choice = '2'  # Fall through to manual entry
                    else:
                        if len(pi_devices) == 1:
                            selected_pi = pi_devices[0]
                            print(f"\n✓ Using {selected_pi['ip']} ({selected_pi['hostname']})")
                        else:
                            print(f"\nFound {len(pi_devices)} devices:")
                            for idx, pi in enumerate(pi_devices, 1):
                                print(f"{idx}. {pi['ip']} ({pi['hostname']})")
                            
                            while True:
                                sel = input(f"\nSelect device (1-{len(pi_devices)}): ").strip()
                                try:
                                    sel_idx = int(sel) - 1
                                    if 0 <= sel_idx < len(pi_devices):
                                        selected_pi = pi_devices[sel_idx]
                                        break
                                    else:
                                        print("Invalid selection")
                                except:
                                    print("Invalid input")
                        
                        config['mode'] = 'remote'
                        config['pi_ip'] = selected_pi['ip']
                        config['hostname'] = selected_pi.get('hostname', 'unknown')
                        break
                
                if choice == '2':
                    # Manual entry
                    while True:
                        pi_ip = input("\nEnter Raspberry Pi IP address: ").strip()
                        
                        # Validate IP format
                        try:
                            socket.inet_aton(pi_ip)
                            
                            # Try to ping it
                            print(f"Testing connection to {pi_ip}...")
                            result = subprocess.run(
                                ["ping", "-c", "2", "-W", "2", pi_ip],
                                capture_output=True,
                                timeout=5
                            )
                            
                            if result.returncode == 0:
                                print(f"✓ Successfully connected to {pi_ip}")
                                config['mode'] = 'remote'
                                config['pi_ip'] = pi_ip
                                try:
                                    hostname = socket.gethostbyaddr(pi_ip)[0]
                                    config['hostname'] = hostname
                                except:
                                    config['hostname'] = 'unknown'
                                break
                            else:
                                print(f"⚠️  Could not reach {pi_ip}")
                                retry = input("Try another IP? (y/n): ").strip().lower()
                                if retry != 'y':
                                    break
                        except:
                            print("Invalid IP address format")
                    break
                
                elif choice == '3':
                    # Localhost
                    print("\n⚠️  Using localhost (testing mode)")
                    config['mode'] = 'local'
                    config['pi_ip'] = '127.0.0.1'
                    config['hostname'] = 'localhost'
                    break
                
                else:
                    print("Invalid choice. Please enter 1, 2, or 3.")
        
        # Additional settings
        print("\n" + "-"*60)
        print("Additional Settings")
        print("-"*60)
        
        port = input("\nWeb server port (default: 5000): ").strip()
        config['port'] = int(port) if port else 5000
        
        # Camera setup
        print("\n" + "-"*60)
        print("Camera Configuration (Optional)")
        print("-"*60)
        print("\nDo you want to configure a Canon R100 WiFi camera now?")
        print("(You can also do this later via the web interface)")
        
        setup_camera = input("\nSetup Canon R100 WiFi? (y/n, default: n): ").strip().lower()
        
        if setup_camera == 'y':
            print("\n📷 Canon R100 WiFi Setup")
            print("-" * 60)
            
            # Import Canon WiFi module
            try:
                from canon_wifi import CanonWiFiCamera
                
                canon_camera = CanonWiFiCamera()
                camera_ip = canon_camera.setup_wizard()
                
                if camera_ip:
                    config['canon_wifi_enabled'] = True
                    config['canon_wifi_ip'] = camera_ip
                    config['camera_type'] = 'canon_wifi'
                    print("\n✓ Canon WiFi camera configured!")
                else:
                    config['canon_wifi_enabled'] = False
                    print("\n⚠ Canon WiFi setup skipped")
            except ImportError:
                print("⚠ Canon WiFi module not available")
                config['canon_wifi_enabled'] = False
        else:
            config['canon_wifi_enabled'] = False
            config['camera_type'] = 'gphoto2'  # Default to USB camera
        
        # Save configuration
        if self.save_config(config):
            print("\n" + "="*60)
            print("✓ SETUP COMPLETE!")
            print("="*60)
            print(f"\nConfiguration saved to: {self.config_file}")
            print("\nYou can now start using the Film Scanner.")
            print("\nTo reset configuration, delete this file:")
            print(f"  {self.config_file}")
            print("\nOr run with --reset flag")
            print("="*60 + "\n")
            return config
        else:
            print("\n❌ Failed to save configuration")
            return None
    
    def get_config(self):
        """Get configuration, running setup if needed"""
        if self.config_exists():
            config = self.load_config()
            if config:
                return config
        
        # No config exists or failed to load - run setup
        return self.interactive_setup()
    
    def print_config(self):
        """Print current configuration"""
        config = self.load_config()
        if not config:
            print("No configuration found")
            return
        
        print("\n" + "="*60)
        print("   CURRENT CONFIGURATION")
        print("="*60)
        print(f"\nMode: {config.get('mode', 'unknown')}")
        print(f"Pi IP: {config.get('pi_ip', 'unknown')}")
        print(f"Hostname: {config.get('hostname', 'unknown')}")
        print(f"Port: {config.get('port', 5000)}")
        print(f"\nCamera Type: {config.get('camera_type', 'not configured')}")
        if config.get('canon_wifi_enabled'):
            print(f"Canon WiFi IP: {config.get('canon_wifi_ip', 'not set')}")
        print(f"\nConfig file: {self.config_file}")
        print("="*60 + "\n")


def main():
    """Command-line interface for config management"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Film Scanner Configuration Manager')
    parser.add_argument('--reset', action='store_true', help='Delete configuration and run setup again')
    parser.add_argument('--show', action='store_true', help='Show current configuration')
    parser.add_argument('--setup', action='store_true', help='Run setup wizard')
    
    args = parser.parse_args()
    
    config_mgr = ConfigManager()
    
    if args.reset:
        print("Resetting configuration...")
        config_mgr.delete_config()
        print("\nRun the application again to set up a new configuration.")
    elif args.show:
        config_mgr.print_config()
    elif args.setup:
        config_mgr.interactive_setup()
    else:
        # Just get/create config
        config = config_mgr.get_config()
        if config:
            config_mgr.print_config()


if __name__ == '__main__':
    main()

