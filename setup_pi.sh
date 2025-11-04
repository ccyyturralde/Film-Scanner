#!/bin/bash
# Film Scanner Web App - Raspberry Pi Setup Script
# Automatically installs and configures the scanner web app

set -e  # Exit on any error

echo "═══════════════════════════════════════════════════════"
echo "  35mm Film Scanner - Web App Setup for Raspberry Pi"
echo "═══════════════════════════════════════════════════════"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Installation directory
INSTALL_DIR="$HOME/Scanner-Web"

echo -e "${BLUE}Installation directory: ${INSTALL_DIR}${NC}"
echo ""

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Warning: This doesn't appear to be a Raspberry Pi${NC}"
    echo "Continue anyway? (y/n)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 1
    fi
fi

# Get Pi IP address
echo -e "${BLUE}🌐 Detecting network configuration...${NC}"
PI_IP=$(hostname -I | awk '{print $1}')
PI_HOSTNAME=$(hostname)

if [ -z "$PI_IP" ]; then
    echo -e "${RED}❌ Could not detect IP address${NC}"
    echo "Please check network connection"
    exit 1
fi

echo -e "${GREEN}✓ IP Address: ${PI_IP}${NC}"
echo -e "${GREEN}✓ Hostname: ${PI_HOSTNAME}${NC}"
echo ""

# Create installation directory
echo -e "${BLUE}📁 Creating installation directory...${NC}"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"
echo -e "${GREEN}✓ Directory created: ${INSTALL_DIR}${NC}"
echo ""

# Update system
echo -e "${BLUE}📦 Updating system packages...${NC}"
sudo apt update
echo -e "${GREEN}✓ System updated${NC}"
echo ""

# Install system dependencies
echo -e "${BLUE}📦 Installing system dependencies...${NC}"
echo "This may take a few minutes..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    gphoto2 \
    git \
    libgphoto2-dev

echo -e "${GREEN}✓ System dependencies installed${NC}"
echo ""

# Add user to dialout group (for Arduino serial access)
echo -e "${BLUE}🔧 Configuring serial port permissions...${NC}"
if ! groups | grep -q dialout; then
    sudo usermod -a -G dialout "$USER"
    echo -e "${GREEN}✓ Added $USER to dialout group${NC}"
    echo -e "${YELLOW}⚠️  Note: You'll need to log out and back in for this to take effect${NC}"
else
    echo -e "${GREEN}✓ User already in dialout group${NC}"
fi
echo ""

# Check if we're in a git repository
if [ -d .git ]; then
    echo -e "${BLUE}📥 Updating existing installation...${NC}"
    git pull
    echo -e "${GREEN}✓ Repository updated${NC}"
else
    echo -e "${YELLOW}⚠️  Not in a git repository. Copying files manually...${NC}"
    echo "If you have the scanner files elsewhere, copy them to: $INSTALL_DIR"
fi
echo ""

# Create Python virtual environment
echo -e "${BLUE}🐍 Setting up Python virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
fi

# Activate virtual environment
source venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo ""

# Install Python dependencies
echo -e "${BLUE}📦 Installing Python packages...${NC}"
if [ -f "requirements.txt" ]; then
    pip install --upgrade pip
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Python packages installed${NC}"
else
    echo -e "${YELLOW}⚠️  requirements.txt not found. Installing manually...${NC}"
    pip install --upgrade pip
    pip install Flask flask-socketio pyserial python-socketio
    echo -e "${GREEN}✓ Core packages installed${NC}"
fi
echo ""

# Create necessary directories
echo -e "${BLUE}📁 Creating application directories...${NC}"
mkdir -p ~/scans
mkdir -p templates static/css static/js
echo -e "${GREEN}✓ Directories created${NC}"
echo ""

# Create systemd service file
echo -e "${BLUE}🔧 Setting up systemd service...${NC}"
SERVICE_FILE="/etc/systemd/system/film-scanner.service"

sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Film Scanner Web Application
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/web_app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}✓ Systemd service created${NC}"
echo ""

# Reload systemd
sudo systemctl daemon-reload
echo -e "${GREEN}✓ Systemd reloaded${NC}"
echo ""

# Create launcher script
echo -e "${BLUE}📝 Creating launcher script...${NC}"
cat > "$INSTALL_DIR/start_scanner.sh" <<'EOF'
#!/bin/bash
# Film Scanner Web App Launcher

cd "$(dirname "$0")"
source venv/bin/activate

# Get IP address
IP_ADDR=$(hostname -I | awk '{print $1}')
HOSTNAME=$(hostname)

echo "═══════════════════════════════════════════════════════"
echo "  35mm Film Scanner - Web Application"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Starting server..."
echo ""
echo "Access URLs:"
echo "  Local:    http://localhost:5000"
echo "  Network:  http://$IP_ADDR:5000"
echo "  Hostname: http://$HOSTNAME.local:5000"
echo ""
echo "From your phone:"
echo "  http://$IP_ADDR:5000"
echo ""
echo "Press Ctrl+C to stop the server"
echo "═══════════════════════════════════════════════════════"
echo ""

python web_app.py
EOF

chmod +x "$INSTALL_DIR/start_scanner.sh"
echo -e "${GREEN}✓ Launcher script created${NC}"
echo ""

# Create desktop shortcut (if running desktop environment)
if [ -n "$DISPLAY" ]; then
    echo -e "${BLUE}🖥️  Creating desktop shortcut...${NC}"
    DESKTOP_FILE="$HOME/Desktop/FilmScanner.desktop"
    
    cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=Film Scanner
Comment=Start Film Scanner Web App
Exec=lxterminal -e $INSTALL_DIR/start_scanner.sh
Icon=camera
Terminal=true
Type=Application
Categories=Application;
EOF
    
    chmod +x "$DESKTOP_FILE"
    echo -e "${GREEN}✓ Desktop shortcut created${NC}"
    echo ""
fi

# Test gphoto2
echo -e "${BLUE}📷 Testing camera connection...${NC}"
if gphoto2 --auto-detect | grep -q "usb"; then
    echo -e "${GREEN}✓ Camera detected!${NC}"
    gphoto2 --auto-detect
else
    echo -e "${YELLOW}⚠️  No camera detected (you can connect it later)${NC}"
fi
echo ""

# Test Arduino connection
echo -e "${BLUE}🔌 Checking for Arduino...${NC}"
if ls /dev/ttyACM* 2>/dev/null || ls /dev/ttyUSB* 2>/dev/null; then
    echo -e "${GREEN}✓ Serial device detected${NC}"
    ls /dev/tty{ACM,USB}* 2>/dev/null || true
else
    echo -e "${YELLOW}⚠️  No Arduino detected (you can connect it later)${NC}"
fi
echo ""

# Create info file
cat > "$INSTALL_DIR/connection_info.txt" <<EOF
═══════════════════════════════════════════════════════
  Film Scanner Web App - Connection Information
═══════════════════════════════════════════════════════

Your Raspberry Pi Network Information:
  IP Address: $PI_IP
  Hostname:   $PI_HOSTNAME

Access the Scanner:
  From this computer:
    http://localhost:5000
  
  From your phone/tablet:
    http://$PI_IP:5000
    
  Alternative (hostname):
    http://$PI_HOSTNAME.local:5000

QR Code for Mobile:
  Scan this URL in your phone's browser:
  http://$PI_IP:5000

Installation Directory:
  $INSTALL_DIR

Start Scanner:
  Method 1: ./start_scanner.sh
  Method 2: python web_app.py
  Method 3: sudo systemctl start film-scanner

Enable Auto-Start on Boot:
  sudo systemctl enable film-scanner

View Scanner Status:
  sudo systemctl status film-scanner

View Scanner Logs:
  sudo journalctl -u film-scanner -f

Stop Scanner:
  sudo systemctl stop film-scanner

═══════════════════════════════════════════════════════
EOF

# Display setup complete message
clear
echo ""
echo "═══════════════════════════════════════════════════════"
echo -e "  ${GREEN}✓ Setup Complete!${NC}"
echo "═══════════════════════════════════════════════════════"
echo ""
echo -e "${GREEN}Installation Directory:${NC}"
echo "  $INSTALL_DIR"
echo ""
echo -e "${GREEN}Your Network Information:${NC}"
echo "  IP Address: ${BLUE}$PI_IP${NC}"
echo "  Hostname:   ${BLUE}$PI_HOSTNAME${NC}"
echo ""
echo -e "${GREEN}Access the Scanner:${NC}"
echo "  ${BLUE}http://$PI_IP:5000${NC}"
echo "  ${BLUE}http://$HOSTNAME.local:5000${NC}"
echo ""
echo -e "${GREEN}Quick Start Commands:${NC}"
echo "  Start:  ${BLUE}cd $INSTALL_DIR && ./start_scanner.sh${NC}"
echo "  Auto:   ${BLUE}sudo systemctl enable film-scanner${NC}"
echo "  Status: ${BLUE}sudo systemctl status film-scanner${NC}"
echo ""
echo -e "${YELLOW}Important Notes:${NC}"
echo "  • Connect Arduino and Camera via USB"
echo "  • Camera must be in PTP/PC mode (not mass storage)"
echo "  • If you added dialout group, log out and back in"
echo "  • Access from phone: http://$PI_IP:5000"
echo ""
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Connection info saved to: $INSTALL_DIR/connection_info.txt"
echo ""
echo -e "${BLUE}Ready to start?${NC} Run: ${GREEN}./start_scanner.sh${NC}"
echo ""

# Ask if user wants to start now
echo "Start the scanner now? (y/n)"
read -r response
if [[ "$response" =~ ^[Yy]$ ]]; then
    echo ""
    echo "Starting Film Scanner Web App..."
    echo ""
    ./start_scanner.sh
fi

