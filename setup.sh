#!/bin/bash
# Film Scanner - Automated Setup Script
# Run with: bash setup.sh

set -e  # Exit on error

echo "========================================="
echo "35mm Film Scanner - Setup Script"
echo "========================================="
echo ""

# Check if running on Raspberry Pi
if [ -f /proc/device-tree/model ]; then
    echo "✓ Detected Raspberry Pi: $(cat /proc/device-tree/model)"
else
    echo "⚠ Warning: Not running on Raspberry Pi"
    echo "Continue anyway? (y/n)"
    read -r response
    if [ "$response" != "y" ]; then
        exit 1
    fi
fi

echo ""
echo "Step 1: Updating system packages..."
echo "------------------------------------"
sudo apt update
sudo apt upgrade -y

echo ""
echo "Step 2: Installing required packages..."
echo "---------------------------------------"
sudo apt install -y \
    python3-pip \
    python3-serial \
    git \
    gphoto2 \
    screen \
    curl \
    wget

echo ""
echo "Step 3: Installing Python packages..."
echo "-------------------------------------"
pip3 install --break-system-packages pyserial

echo ""
echo "Step 4: Installing Arduino CLI (optional)..."
echo "--------------------------------------------"
if ! command -v arduino-cli &> /dev/null; then
    echo "Arduino CLI not found. Install? (y/n)"
    read -r response
    if [ "$response" = "y" ]; then
        curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh
        sudo mv bin/arduino-cli /usr/local/bin/
        arduino-cli core install arduino:avr
        echo "✓ Arduino CLI installed"
    fi
else
    echo "✓ Arduino CLI already installed"
fi

echo ""
echo "Step 5: Setting up directories..."
echo "---------------------------------"
mkdir -p ~/scans
mkdir -p ~/film-scanner
echo "✓ Directories created"

echo ""
echo "Step 6: Setting up permissions..."
echo "---------------------------------"
# Add user to dialout group for serial access
if ! groups | grep -q dialout; then
    sudo usermod -a -G dialout $USER
    echo "✓ Added user to dialout group"
    echo "⚠ You may need to logout and login for this to take effect"
else
    echo "✓ User already in dialout group"
fi

echo ""
echo "Step 7: Testing hardware..."
echo "---------------------------"

# Test for Arduino
echo -n "Checking for Arduino... "
if ls /dev/ttyACM* 2>/dev/null || ls /dev/ttyUSB* 2>/dev/null; then
    echo "✓ Found serial port"
else
    echo "✗ No Arduino detected"
fi

# Test for camera
echo -n "Checking for camera... "
if gphoto2 --auto-detect 2>/dev/null | grep -q Canon; then
    echo "✓ Canon camera detected"
elif gphoto2 --auto-detect 2>/dev/null | grep -q Nikon; then
    echo "✓ Nikon camera detected"
else
    echo "✗ No camera detected (check USB connection)"
fi

echo ""
echo "Step 8: Creating test script..."
echo "-------------------------------"
cat > ~/film-scanner/test_system.sh << 'EOF'
#!/bin/bash
echo "Film Scanner System Test"
echo "========================"
echo ""
echo "1. Arduino Ports:"
ls -l /dev/tty* 2>/dev/null | grep -E "ACM|USB" || echo "   No Arduino found"
echo ""
echo "2. Camera Detection:"
gphoto2 --auto-detect
echo ""
echo "3. Python Serial:"
python3 -c "import serial; print('   PySerial version:', serial.__version__)"
echo ""
echo "4. Directory Structure:"
ls -la ~/scans 2>/dev/null || echo "   ~/scans not found"
echo ""
echo "Test complete!"
EOF

chmod +x ~/film-scanner/test_system.sh
echo "✓ Test script created at ~/film-scanner/test_system.sh"

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "-----------"
echo "1. Flash Arduino with sketch:"
echo "   arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:avr:uno arduino/film_scanner/"
echo ""
echo "2. Test your system:"
echo "   ~/film-scanner/test_system.sh"
echo ""
echo "3. Run the scanner:"
echo "   cd ~/film-scanner"
echo "   python3 scanner_app_v2.py"
echo ""
echo "If you were added to dialout group, logout and login first!"
echo ""

# Check if reboot needed
if [ -f /var/run/reboot-required ]; then
    echo "⚠ System reboot required. Reboot now? (y/n)"
    read -r response
    if [ "$response" = "y" ]; then
        sudo reboot
    fi
fi
