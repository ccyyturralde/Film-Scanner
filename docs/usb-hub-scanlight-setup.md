# USB Hub and ScanLight Setup Guide

## USB Hub Compatibility

### ✅ Your Scanner is USB Hub-Ready

The Film Scanner software uses `pyserial`'s `list_ports.comports()` which automatically discovers all USB serial devices regardless of connection topology:

- ✅ Direct USB connection
- ✅ Through powered USB hub
- ✅ Through unpowered hub (if sufficient power)
- ✅ Multiple USB hubs in chain

**Recommendations for Best Results:**

1. **Use a Powered USB Hub** - Ensures stable power to all devices
2. **USB 3.0 Hub Recommended** - Better power delivery and bandwidth
3. **Known Working Devices:**
   - Arduino Uno R3/R4 (motor control)
   - Canon DSLR cameras (via libgphoto2)
   - Raspberry Pi Pico (ScanLight)

### Device Discovery Priority

The scanner prioritizes devices in this order:
1. Known Arduino boards (by VID/PID)
2. Common serial ports (`/dev/ttyACM*`, `/dev/ttyUSB*`)
3. Other serial devices

This means **both Arduino and ScanLight can coexist** on the same hub without conflicts.

## ScanLight Integration

### What is ScanLight?

ScanLight by jack0w1 is a Raspberry Pi Pico-based RGB LED controller that provides:
- Narrowband trichromatic illumination (450nm blue, 525nm green, 665nm red)
- Superior color accuracy vs white light
- Professional scanner-quality results
- USB serial control

### Hardware Connection

```
Raspberry Pi
    │
    └─ USB Hub (3.0 recommended)
         ├─ Arduino Uno R3/R4 (motor control)
         ├─ Canon Camera (via USB)
         └─ ScanLight Pi Pico (backlight control)
```

### Finding Your ScanLight Protocol

The exact serial protocol varies by ScanLight version. Run the discovery tool:

```bash
# On your Raspberry Pi
cd ~/Film-Scanner
python3 test_scanlight_discovery.py
```

This will:
1. Find your ScanLight device
2. Test common command formats
3. Show you which commands work
4. Help you identify the protocol

### Common ScanLight Versions

- **BSL v1**: Original design
- **SL2 (v2/v3)**: Current production version
- Check your `.uf2` firmware file for version info

### Updating the Controller

Once you know the protocol, edit `scanlight_controller.py`:

```python
def set_rgb(self, r: int, g: int, b: int) -> bool:
    # Update this line with actual command format:
    cmd = f"RGB:{r},{g},{b}"  # ← Change to match your ScanLight
    return self.send_command(cmd)
```

### Testing ScanLight

Test standalone before integrating:

```bash
# Test ScanLight connection
python3 scanlight_controller.py

# Should cycle through colors and brightness levels
```

### Integration with Scanner

After verifying ScanLight works, it will be integrated into the main scanner with:
- Web UI controls for RGB values
- Brightness slider
- Presets (white, scan-optimized, etc.)
- Auto-on with capture
- Save/load settings per roll

## Troubleshooting

### "Device not found"

```bash
# Check USB devices
lsusb | grep -i pico
lsusb | grep -i "2e8a"  # Raspberry Pi vendor ID

# Check serial ports
ls -la /dev/tty*
```

### "Permission denied"

```bash
# Add user to dialout group (already done during setup)
sudo usermod -a -G dialout scanner

# Check permissions
ls -la /dev/ttyACM*
```

### Multiple Devices Conflict

The scanner identifies devices by:
1. **Arduino**: Firmware handshake (sends `?`, expects `Position:` response)
2. **ScanLight**: Raspberry Pi Pico VID (0x2E8A)

They use different identification, so no conflicts.

### USB Hub Power Issues

If devices disconnect randomly:
1. Use a powered USB hub
2. Check hub power supply (should be ≥2A per port)
3. Avoid daisy-chaining unpowered hubs

## Advanced: Custom Commands

### Example: Set ScanLight for Ektar 100

```python
# Optimize for Kodak Ektar's dye characteristics
light.set_rgb(255, 190, 210)  # Slightly cooler, more blue
light.set_brightness(200)      # Not full brightness
```

### Example: Preset System

```python
FILM_PRESETS = {
    'ektar100': (255, 190, 210),
    'portra400': (255, 200, 200),
    'fuji200': (240, 200, 255),
}
```

## References

- [ScanLight Project](https://jackw01.github.io/scanlight/)
- [ScanLight GitHub](https://github.com/jackw01/scanlight)
- [USB Hub Best Practices](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#power-supplies)
