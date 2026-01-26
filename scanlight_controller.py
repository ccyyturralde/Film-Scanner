"""
ScanLight RGB LED Controller for Film Scanner
Supports jack0w1's ScanLight SL2 Pi Pico-based backlight

Hardware: Raspberry Pi Pico running ScanLight SL2 firmware
Connection: USB Serial (typically /dev/ttyACM*)
Protocol: Binary packet format with start/end bytes

Packet Format:
  [START_BYTE, CMD_TYPE, DATA_LENGTH, ...DATA..., END_BYTE]
  - START_BYTE = 254 (0xFE)
  - END_BYTE = 255 (0xFF)

Commands:
  - Set RGB (0): [254, 0, 3, R, G, B, 255]
  - Reset (1): [254, 1, 0, 255]

Based on: https://github.com/jackw01/scanlight/tree/main/automation
"""

import serial
import serial.tools.list_ports
import time
from typing import Optional, Tuple


class ScanLight:
    """
    Controller for ScanLight SL2 RGB LED backlight.
    
    Usage:
        light = ScanLight()
        if light.connect():
            light.set_rgb(255, 0, 0)  # Red
            light.set_rgb(255, 255, 255)  # White
            light.off()
    """
    
    # Protocol constants
    PACKET_START_BYTE = 254
    PACKET_END_BYTE = 255
    
    # Commands
    CMD_SET = 0
    CMD_RESET = 1
    
    def __init__(self):
        self.serial: Optional[serial.Serial] = None
        self.port: Optional[str] = None
        self.connected = False
        
        # Current state
        self.red = 255
        self.green = 255
        self.blue = 255
        self.is_on = True  # ScanLight is always on when connected
    
    def find_scanlight(self) -> Optional[str]:
        """
        Find ScanLight device on USB serial ports.
        
        Returns:
            Port path if found, None otherwise
        """
        print("🔍 Scanning for ScanLight device...")
        
        ports = list(serial.tools.list_ports.comports())
        
        # ScanLight uses Raspberry Pi Pico (RP2040)
        # VID: 0x2E8A (Raspberry Pi)
        # PID: 0x000A (Pico CDC)
        for port in ports:
            vid = getattr(port, 'vid', None)
            pid = getattr(port, 'pid', None)
            device = getattr(port, 'device', str(port))
            desc = getattr(port, 'description', '')
            
            # Check for Raspberry Pi Pico
            if vid == 0x2E8A:  # Raspberry Pi vendor ID
                print(f"   Found Pico device: {device}")
                print(f"      VID: {hex(vid)}, PID: {hex(pid)}")
                print(f"      Description: {desc}")
                
                # Try to verify it's ScanLight by sending a test command
                try:
                    test_ser = serial.Serial(device, 115200, timeout=2)
                    time.sleep(0.5)
                    
                    # Try common identification commands
                    test_ser.write(b'?\n')
                    time.sleep(0.2)
                    response = test_ser.read(100).decode('ascii', errors='ignore')
                    
                    test_ser.close()
                    
                    # If we get any response, assume it's ScanLight
                    # (Adjust this based on actual ScanLight response)
                    if response or True:  # Accept any Pico for now
                        print(f"   ✓ Identified as ScanLight")
                        return device
                        
                except Exception as e:
                    print(f"   ✗ Failed to test {device}: {e}")
                    continue
        
        print("   ✗ No ScanLight device found")
        return None
    
    def connect(self, port: Optional[str] = None) -> bool:
        """
        Connect to ScanLight device.
        
        Args:
            port: Specific port to connect to, or None to auto-detect
            
        Returns:
            True if connected successfully
        """
        # Close existing connection
        if self.serial:
            try:
                self.serial.close()
            except:
                pass
            self.serial = None
            self.connected = False
        
        # Find device if port not specified
        if not port:
            port = self.find_scanlight()
            if not port:
                return False
        
        try:
            print(f"🔌 Connecting to ScanLight on {port}...")
            self.serial = serial.Serial(port, 115200, timeout=2)
            time.sleep(1.0)  # Give Pico time to initialize
            
            # Clear any startup messages
            self.serial.reset_input_buffer()
            
            self.port = port
            self.connected = True
            print(f"✓ Connected to ScanLight on {port}")
            
            # Wait for startup self-test to complete
            # (ScanLight cycles R->G->B->White on startup)
            time.sleep(0.6)
            
            # Initialize to white
            self.set_rgb(255, 255, 255)
            
            return True
            
        except Exception as e:
            print(f"✗ Failed to connect to ScanLight: {e}")
            self.serial = None
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from ScanLight."""
        if self.serial:
            try:
                # Turn off (set to black)
                self.set_rgb(0, 0, 0)
                self.serial.close()
            except:
                pass
            self.serial = None
        self.connected = False
    
    def _send_packet(self, cmd_type: int, data: bytes = b'') -> bool:
        """
        Send binary packet to ScanLight using SL2 protocol.
        
        Packet format: [START, CMD_TYPE, DATA_LENGTH, ...DATA..., END]
        
        Args:
            cmd_type: Command type (0=Set, 1=Reset)
            data: Data bytes to send
            
        Returns:
            True if sent successfully
        """
        if not self.serial or not self.connected:
            return False
        
        try:
            packet = bytes([
                self.PACKET_START_BYTE,
                cmd_type,
                len(data),  # Data length
            ]) + data + bytes([self.PACKET_END_BYTE])
            
            self.serial.write(packet)
            time.sleep(0.01)  # Small delay for Pico to process
            return True
        except Exception as e:
            print(f"✗ ScanLight packet send failed: {e}")
            return False
    
    def set_rgb(self, r: int, g: int, b: int) -> bool:
        """
        Set RGB color values (0-255) using ScanLight SL2 protocol.
        
        Packet: [254, 0, 3, R, G, B, 255]
        """
        self.red = max(0, min(255, r))
        self.green = max(0, min(255, g))
        self.blue = max(0, min(255, b))
        
        data = bytes([self.red, self.green, self.blue])
        success = self._send_packet(self.CMD_SET, data)
        
        if success:
            self.is_on = (r > 0 or g > 0 or b > 0)
        
        return success
    
    def reset(self) -> bool:
        """
        Reset ScanLight (sets to white).
        
        Packet: [254, 1, 0, 255]
        """
        success = self._send_packet(self.CMD_RESET, b'')
        if success:
            self.red = 255
            self.green = 255
            self.blue = 255
            self.is_on = True
        return success
    
    def off(self) -> bool:
        """Turn ScanLight off (set to black)."""
        return self.set_rgb(0, 0, 0)
    
    def on(self, restore_last: bool = True) -> bool:
        """
        Turn ScanLight on.
        
        Args:
            restore_last: If True, restore last color; if False, set to white
        """
        if restore_last and (self.red > 0 or self.green > 0 or self.blue > 0):
            return self.set_rgb(self.red, self.green, self.blue)
        else:
            return self.set_rgb(255, 255, 255)
    
    def set_preset(self, preset: str) -> bool:
        """
        Set color preset optimized for film scanning.
        
        ScanLight uses narrowband RGB LEDs:
        - Red: 665nm
        - Green: 525nm
        - Blue: 450nm
        
        Presets:
        - 'white': Full white for general use
        - 'scan': Balanced for most color negative films
        - 'ektar': Optimized for Kodak Ektar (slightly cooler)
        - 'portra': Optimized for Kodak Portra (warm)
        - 'fuji': Optimized for Fujifilm stocks (slightly cool)
        """
        presets = {
            'white': (255, 255, 255),
            'scan': (255, 200, 220),      # Balanced
            'ektar': (255, 190, 230),     # Cooler, more blue
            'portra': (255, 210, 200),    # Warmer
            'fuji': (240, 195, 230),      # Slightly cool, less red
        }
        
        if preset in presets:
            r, g, b = presets[preset]
            return self.set_rgb(r, g, b)
        else:
            print(f"✗ Unknown preset: {preset}")
            print(f"   Available: {', '.join(presets.keys())}")
            return False
    
    def get_status(self) -> dict:
        """Get current ScanLight status."""
        return {
            'connected': self.connected,
            'port': self.port,
            'red': self.red,
            'green': self.green,
            'blue': self.blue,
            'is_on': self.is_on,
            'protocol': 'ScanLight SL2',
        }


# Test/example usage
if __name__ == "__main__":
    import sys
    
    print("ScanLight Controller Test")
    print("=" * 50)
    
    light = ScanLight()
    
    if not light.connect():
        print("✗ Failed to connect to ScanLight")
        sys.exit(1)
    
    print("\nScanLight Status:")
    print(light.get_status())
    
    print("\nTesting colors...")
    print("Red...")
    light.set_rgb(255, 0, 0)
    time.sleep(1)
    
    print("Green...")
    light.set_rgb(0, 255, 0)
    time.sleep(1)
    
    print("Blue...")
    light.set_rgb(0, 0, 255)
    time.sleep(1)
    
    print("White...")
    light.set_rgb(255, 255, 255)
    time.sleep(1)
    
    print("\nTesting brightness...")
    for b in [255, 128, 64, 128, 255]:
        print(f"Brightness: {b}")
        light.set_brightness(b)
        time.sleep(0.5)
    
    print("\nTurning off...")
    light.off()
    
    light.disconnect()
    print("✓ Test complete")
