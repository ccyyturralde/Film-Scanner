"""
ScanLight RGB LED Controller for Film Scanner

Supports both:
  - ScanLight SL2 (v2/v3): older 3-byte RGB protocol with end byte
  - Big ScanLight / ScanLight v4 (BSL1): 6-byte protocol with white, IR,
    shutter trigger, brightness trimming, and telemetry

Hardware: Raspberry Pi Pico (RP2040) running ScanLight firmware
Connection: USB Serial (typically /dev/ttyACM*)
Protocol reference: https://github.com/jackw01/scanlight/blob/main/automation/bsl_control_interface.md

BSL1 packet format (no end byte):
  [0xFE, HEADER, DATA_LENGTH, ...DATA]

SL2 packet format (legacy, has end byte):
  [0xFE, CMD, DATA_LENGTH, ...DATA, 0xFF]
"""

import struct
import serial
import serial.tools.list_ports
import time
import threading
from typing import Optional, Tuple, Dict, Any


# --- Protocol constants ---

PACKET_START = 0xFE

# Host-to-device packet headers (BSL1 / v4)
PKT_H2D_SET_COLOR = 0
PKT_H2D_GET_DEFAULT_RGB = 1
PKT_H2D_GET_FW_VERSION = 2
PKT_H2D_SHUTTER_PULSE = 3
PKT_H2D_DFU_MODE = 4
PKT_H2D_SET_TRIM = 5
PKT_H2D_GET_TRIM = 6

# Device-to-host packet headers (BSL1 / v4)
PKT_D2H_LED_TEMP = 1
PKT_D2H_VBUS = 2
PKT_D2H_FW_VERSION = 3
PKT_D2H_DEFAULT_RGB = 4
PKT_D2H_TRIM = 5


class ScanLight:
    """
    Controller for ScanLight RGB LED backlight.

    Auto-detects protocol version on connect:
      - BSL1 (big scanlight / v4): full feature set with white, IR,
        shutter control, trim, and telemetry
      - SL2 (v2/v3): basic RGB control only

    Usage:
        light = ScanLight()
        if light.connect():
            light.set_rgb(255, 0, 0)      # Red (narrowband 665nm)
            light.set_white(255)           # 95CRI 5000K white (BSL1 only)
            light.trigger_shutter()        # Remote shutter pulse (BSL1 only)
            light.off()
    """

    def __init__(self):
        self.serial: Optional[serial.Serial] = None
        self.port: Optional[str] = None
        self.connected = False
        self.protocol: Optional[str] = None  # "bsl1" or "sl2"

        # Current colour state
        self.red = 255
        self.green = 255
        self.blue = 255
        self.white = 0
        self.ir = 0
        self.is_on = True

        # Firmware / hardware info (BSL1 only)
        self.fw_version_id: Optional[int] = None
        self.hw_version_id: Optional[int] = None
        self.default_rgb: Optional[Tuple[int, int, int]] = None

        # Trim values (BSL1 only, -127 to 127)
        self.trim_r = 0
        self.trim_g = 0
        self.trim_b = 0
        self.trim_w = 0

        # Telemetry (BSL1 only, updated by _reader_thread)
        self.led_temp_mc: Optional[int] = None   # millidegrees C
        self.vbus_mv: Optional[int] = None        # millivolts
        self._telemetry_lock = threading.Lock()

        # Background reader for telemetry
        self._reader_thread: Optional[threading.Thread] = None
        self._reader_stop = threading.Event()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def find_scanlight(self) -> Optional[str]:
        """Auto-detect ScanLight on USB serial ports (RP2040 VID 0x2E8A)."""
        print("Scanning for ScanLight device...")

        for port in serial.tools.list_ports.comports():
            vid = getattr(port, 'vid', None)
            if vid == 0x2E8A:
                device = getattr(port, 'device', str(port))
                desc = getattr(port, 'description', '')
                print(f"   Found Pico device: {device} ({desc})")
                return device

        print("   No ScanLight device found")
        return None

    def connect(self, port: Optional[str] = None) -> bool:
        """
        Connect to ScanLight and auto-detect protocol version.

        Args:
            port: Specific serial port, or None to auto-detect.

        Returns:
            True if connected successfully.
        """
        self.disconnect()

        if not port:
            port = self.find_scanlight()
            if not port:
                return False

        try:
            print(f"Connecting to ScanLight on {port}...")
            self.serial = serial.Serial(port, 115200, timeout=2)
            time.sleep(1.0)
            self.serial.reset_input_buffer()
            self.port = port
            self.connected = True

            # Probe for BSL1 by requesting firmware version
            if self._probe_bsl1():
                self.protocol = "bsl1"
                self._start_reader()
                self._request_default_rgb()
                self._request_trim()
                print(f"Connected to Big ScanLight (BSL1) on {port}"
                      f" — fw={self.fw_version_id}, hw={self.hw_version_id}")
            else:
                self.protocol = "sl2"
                print(f"Connected to ScanLight SL2 on {port}")

            time.sleep(0.3)
            self.set_rgb(self.red, self.green, self.blue)
            return True

        except Exception as e:
            print(f"Failed to connect to ScanLight: {e}")
            self.serial = None
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from ScanLight."""
        self._stop_reader()
        if self.serial:
            try:
                self.set_rgb(0, 0, 0)
                self.serial.close()
            except Exception:
                pass
            self.serial = None
        self.connected = False
        self.protocol = None

    def _probe_bsl1(self) -> bool:
        """Send a firmware version request; if we get a valid response it's BSL1."""
        try:
            self._send_packet(PKT_H2D_GET_FW_VERSION)
            time.sleep(0.3)

            while self.serial and self.serial.in_waiting >= 3:
                header, data = self._read_packet()
                if header == PKT_D2H_FW_VERSION and len(data) >= 4:
                    self.fw_version_id = struct.unpack('<H', data[0:2])[0]
                    self.hw_version_id = struct.unpack('<H', data[2:4])[0]
                    return True
                # Consume any telemetry that arrived first
                if header is None:
                    break

            return False
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Packet I/O
    # ------------------------------------------------------------------

    def _send_packet(self, header: int, data: bytes = b'') -> bool:
        if not self.serial or not self.connected:
            return False
        try:
            if self.protocol == "sl2":
                # Legacy SL2: [START, CMD, LEN, ...DATA, END]
                pkt = bytes([PACKET_START, header, len(data)]) + data + bytes([0xFF])
            else:
                # BSL1/v4: [START, HEADER, LEN, ...DATA]  (no end byte)
                pkt = bytes([PACKET_START, header, len(data)]) + data
            self.serial.write(pkt)
            time.sleep(0.005)
            return True
        except Exception as e:
            print(f"ScanLight send failed: {e}")
            return False

    def _read_packet(self) -> Tuple[Optional[int], bytes]:
        """Read one BSL1 packet from the serial buffer. Non-blocking."""
        if not self.serial:
            return None, b''
        try:
            # Scan for start byte
            b = self.serial.read(1)
            if not b or b[0] != PACKET_START:
                return None, b''
            header_b = self.serial.read(1)
            length_b = self.serial.read(1)
            if not header_b or not length_b:
                return None, b''
            header = header_b[0]
            length = length_b[0]
            data = self.serial.read(length) if length > 0 else b''
            return header, data
        except Exception:
            return None, b''

    # ------------------------------------------------------------------
    # Background telemetry reader (BSL1 only)
    # ------------------------------------------------------------------

    def _start_reader(self):
        self._reader_stop.clear()
        self._reader_thread = threading.Thread(
            target=self._reader_loop, daemon=True
        )
        self._reader_thread.start()

    def _stop_reader(self):
        self._reader_stop.set()
        if self._reader_thread:
            self._reader_thread.join(timeout=2.0)
            self._reader_thread = None

    def _reader_loop(self):
        """Continuously read telemetry packets from the device."""
        while not self._reader_stop.is_set():
            try:
                if not self.serial or not self.serial.in_waiting:
                    time.sleep(0.05)
                    continue
                header, data = self._read_packet()
                if header is None:
                    continue
                self._handle_device_packet(header, data)
            except Exception:
                time.sleep(0.1)

    def _handle_device_packet(self, header: int, data: bytes):
        with self._telemetry_lock:
            if header == PKT_D2H_LED_TEMP and len(data) >= 4:
                self.led_temp_mc = struct.unpack('<i', data[0:4])[0]
            elif header == PKT_D2H_VBUS and len(data) >= 4:
                self.vbus_mv = struct.unpack('<i', data[0:4])[0]
            elif header == PKT_D2H_FW_VERSION and len(data) >= 4:
                self.fw_version_id = struct.unpack('<H', data[0:2])[0]
                self.hw_version_id = struct.unpack('<H', data[2:4])[0]
            elif header == PKT_D2H_DEFAULT_RGB and len(data) >= 3:
                self.default_rgb = (data[0], data[1], data[2])
            elif header == PKT_D2H_TRIM and len(data) >= 4:
                self.trim_r = struct.unpack('b', data[0:1])[0]
                self.trim_g = struct.unpack('b', data[1:2])[0]
                self.trim_b = struct.unpack('b', data[2:3])[0]
                self.trim_w = struct.unpack('b', data[3:4])[0]

    def _request_default_rgb(self):
        self._send_packet(PKT_H2D_GET_DEFAULT_RGB)
        time.sleep(0.1)

    def _request_trim(self):
        self._send_packet(PKT_H2D_GET_TRIM)
        time.sleep(0.1)

    # ------------------------------------------------------------------
    # Colour control
    # ------------------------------------------------------------------

    def set_rgb(self, r: int, g: int, b: int, save_preset: bool = False) -> bool:
        """
        Set narrowband RGB LED values (0-255).

        LED wavelengths: Red 665nm, Green 525nm, Blue 455nm.
        When using RGB, white and IR are turned off by firmware.

        Args:
            r, g, b: Channel values 0-255.
            save_preset: (BSL1 only) Save as power-on default. Use sparingly
                         — flash has limited write cycles.
        """
        self.red = max(0, min(255, r))
        self.green = max(0, min(255, g))
        self.blue = max(0, min(255, b))

        if self.protocol == "bsl1":
            data = bytes([
                self.red, self.green, self.blue,
                0,  # white off when RGB is on
                0,  # IR off when RGB is on
                1 if save_preset else 0,
            ])
            success = self._send_packet(PKT_H2D_SET_COLOR, data)
        else:
            # SL2: 3-byte RGB
            data = bytes([self.red, self.green, self.blue])
            success = self._send_packet(PKT_H2D_SET_COLOR, data)

        if success:
            self.white = 0
            self.ir = 0
            self.is_on = (r > 0 or g > 0 or b > 0)
        return success

    def set_white(self, brightness: int = 255) -> bool:
        """
        Set the 95CRI 5000K white LEDs (BSL1 only).

        White and RGB/IR cannot be on simultaneously — the firmware
        enforces this.  Ideal for scanning slide/positive film.
        """
        if self.protocol != "bsl1":
            return self.set_rgb(brightness, brightness, brightness)

        w = max(0, min(255, brightness))
        data = bytes([0, 0, 0, w, 0, 0])
        success = self._send_packet(PKT_H2D_SET_COLOR, data)
        if success:
            self.red = self.green = self.blue = 0
            self.ir = 0
            self.white = w
            self.is_on = w > 0
        return success

    def set_ir(self, brightness: int = 255) -> bool:
        """
        Set the 850nm infrared LEDs (BSL1 only).

        Useful for Digital ICE-style dust/scratch detection.
        IR and white/RGB cannot be on simultaneously.
        """
        if self.protocol != "bsl1":
            return False

        ir = max(0, min(255, brightness))
        data = bytes([0, 0, 0, 0, ir, 0])
        success = self._send_packet(PKT_H2D_SET_COLOR, data)
        if success:
            self.red = self.green = self.blue = self.white = 0
            self.ir = ir
            self.is_on = ir > 0
        return success

    def set_single_channel(self, channel: str, brightness: int = 255) -> bool:
        """
        Turn on a single colour channel for multi-pass scanning (BSL1 only).

        The big scanlight web app supports capturing R, G, B separately
        for maximum colour separation on a mono sensor.

        Args:
            channel: One of "red", "green", "blue", "white", "ir".
            brightness: 0-255.
        """
        b = max(0, min(255, brightness))
        mapping = {
            "red":   (b, 0, 0, 0, 0),
            "green": (0, b, 0, 0, 0),
            "blue":  (0, 0, b, 0, 0),
            "white": (0, 0, 0, b, 0),
            "ir":    (0, 0, 0, 0, b),
        }
        vals = mapping.get(channel)
        if vals is None:
            return False

        if self.protocol != "bsl1":
            # SL2 fallback: just set RGB
            return self.set_rgb(vals[0], vals[1], vals[2])

        data = bytes([*vals, 0])
        success = self._send_packet(PKT_H2D_SET_COLOR, data)
        if success:
            self.red, self.green, self.blue, self.white, self.ir = vals
            self.is_on = b > 0
        return success

    # ------------------------------------------------------------------
    # Shutter control (BSL1 only)
    # ------------------------------------------------------------------

    def trigger_shutter(self, pulse_ms: int = 300) -> bool:
        """
        Trigger the camera shutter via the 3.5mm jack (BSL1 only).

        Args:
            pulse_ms: Shutter pulse length in milliseconds (rounded to
                      nearest 10ms, range 10-2550ms).  Fujifilm cameras
                      need at least 300ms.
        """
        if self.protocol != "bsl1":
            return False

        units = max(1, min(255, round(pulse_ms / 10)))
        return self._send_packet(PKT_H2D_SHUTTER_PULSE, bytes([units]))

    # ------------------------------------------------------------------
    # Brightness trimming (BSL1 only)
    # ------------------------------------------------------------------

    def set_trim(self, r: int = 0, g: int = 0, b: int = 0, w: int = 0) -> bool:
        """
        Set brightness trim between left/right LED banks (-127 to 127).

        Positive values increase side-2 brightness; negative increase
        side-1 brightness.  Values are saved to flash automatically.
        """
        if self.protocol != "bsl1":
            return False

        r = max(-127, min(127, r))
        g = max(-127, min(127, g))
        b = max(-127, min(127, b))
        w = max(-127, min(127, w))
        data = struct.pack('4b', r, g, b, w)
        success = self._send_packet(PKT_H2D_SET_TRIM, data)
        if success:
            self.trim_r, self.trim_g, self.trim_b, self.trim_w = r, g, b, w
        return success

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def off(self) -> bool:
        """Turn all LEDs off."""
        if self.protocol == "bsl1":
            data = bytes([0, 0, 0, 0, 0, 0])
            success = self._send_packet(PKT_H2D_SET_COLOR, data)
            if success:
                self.red = self.green = self.blue = self.white = self.ir = 0
                self.is_on = False
            return success
        return self.set_rgb(0, 0, 0)

    def on(self, restore_last: bool = True) -> bool:
        """Turn on, restoring previous colour or defaulting to white."""
        if restore_last and (self.red > 0 or self.green > 0 or self.blue > 0):
            return self.set_rgb(self.red, self.green, self.blue)
        if restore_last and self.white > 0:
            return self.set_white(self.white)
        return self.set_rgb(255, 255, 255)

    def reset(self) -> bool:
        """Reset to white (SL2) or restore defaults (BSL1)."""
        if self.protocol == "sl2":
            success = self._send_packet(1, b'')  # SL2 reset command
            if success:
                self.red = self.green = self.blue = 255
                self.is_on = True
            return success
        return self.set_rgb(255, 255, 255)

    def set_preset(self, preset: str) -> bool:
        """
        Set a colour preset optimised for different film stocks.

        Narrowband RGB wavelengths: Red 665nm, Green 525nm, Blue 455nm.
        These presets adjust relative channel intensity to bias the scan
        towards the strongest absorption band of each film's dye set.

        For the big scanlight, use 'white' preset for positive/slide film
        (switches to the 95CRI white LEDs).
        """
        presets = {
            'white': (255, 255, 255),
            'scan': (255, 200, 220),
            'ektar': (255, 190, 230),
            'portra': (255, 210, 200),
            'fuji': (240, 195, 230),
        }

        if preset == 'white' and self.protocol == "bsl1":
            return self.set_white(255)

        if preset in presets:
            r, g, b = presets[preset]
            return self.set_rgb(r, g, b)

        print(f"Unknown preset: {preset}")
        print(f"   Available: {', '.join(presets.keys())}")
        return False

    # ------------------------------------------------------------------
    # Status / telemetry
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Get current ScanLight status."""
        status: Dict[str, Any] = {
            'connected': self.connected,
            'port': self.port,
            'protocol': self.protocol or 'unknown',
            'red': self.red,
            'green': self.green,
            'blue': self.blue,
            'is_on': self.is_on,
        }

        if self.protocol == "bsl1":
            with self._telemetry_lock:
                status.update({
                    'white': self.white,
                    'ir': self.ir,
                    'fw_version_id': self.fw_version_id,
                    'hw_version_id': self.hw_version_id,
                    'default_rgb': self.default_rgb,
                    'trim': {
                        'r': self.trim_r, 'g': self.trim_g,
                        'b': self.trim_b, 'w': self.trim_w,
                    },
                    'led_temp_c': round(self.led_temp_mc / 1000.0, 1) if self.led_temp_mc is not None else None,
                    'vbus_v': round(self.vbus_mv / 1000.0, 2) if self.vbus_mv is not None else None,
                    'has_shutter': True,
                    'has_white': True,
                    'has_ir': True,
                })

        return status


# ------------------------------------------------------------------
# Standalone test
# ------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    print("ScanLight Controller Test")
    print("=" * 50)

    light = ScanLight()

    if not light.connect():
        print("Failed to connect to ScanLight")
        sys.exit(1)

    print(f"\nProtocol: {light.protocol}")
    print(f"Status: {light.get_status()}")

    print("\nTesting colours...")
    for name, rgb in [("Red", (255,0,0)), ("Green", (0,255,0)),
                       ("Blue", (0,0,255)), ("White", (255,255,255))]:
        print(f"  {name}...")
        light.set_rgb(*rgb)
        time.sleep(1)

    if light.protocol == "bsl1":
        print("\nTesting white LEDs...")
        light.set_white(255)
        time.sleep(1)

        print("Testing IR LEDs...")
        light.set_ir(255)
        time.sleep(1)

        s = light.get_status()
        if s.get('led_temp_c') is not None:
            print(f"\nLED temperature: {s['led_temp_c']}C")
        if s.get('vbus_v') is not None:
            print(f"VBUS voltage: {s['vbus_v']}V")

    print("\nTurning off...")
    light.off()
    light.disconnect()
    print("Test complete")
