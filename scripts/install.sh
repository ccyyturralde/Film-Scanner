#!/bin/bash
# Film Scanner - One-Line Installer
# 
# Run with:
#   curl -sSL https://raw.githubusercontent.com/YOUR_USERNAME/Film-Scanner/Web-app-automated-edge-detection/scripts/install.sh | bash
#
# Or with wget:
#   wget -qO- https://raw.githubusercontent.com/YOUR_USERNAME/Film-Scanner/Web-app-automated-edge-detection/scripts/install.sh | bash
#
# Supports: Raspberry Pi OS Lite/Desktop (32/64-bit), Pi 3/4/5

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}  Film Scanner - Auto Installer${NC}"
echo -e "${BLUE}  Branch: Web-app-automated-edge-detection${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""

# Check if running on Raspberry Pi
if [ -f /proc/device-tree/model ]; then
    PI_MODEL=$(cat /proc/device-tree/model)
    echo -e "${GREEN}✓ Detected: ${PI_MODEL}${NC}"
else
    echo -e "${YELLOW}⚠ Warning: Not running on Raspberry Pi${NC}"
    read -p "Continue anyway? (y/n): " response
    if [ "$response" != "y" ]; then
        exit 1
    fi
fi

# Check architecture
ARCH=$(uname -m)
echo -e "${GREEN}✓ Architecture: ${ARCH}${NC}"

# Check OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo -e "${GREEN}✓ OS: ${PRETTY_NAME}${NC}"
fi

# Check if we have a display (for informational purposes)
if [ -z "$DISPLAY" ] && [ ! -e /dev/fb1 ]; then
    echo -e "${YELLOW}ℹ Running headless (no display detected yet)${NC}"
    echo -e "${YELLOW}  Touch screen will be configured during setup${NC}"
fi

echo ""

# Installation directory
INSTALL_DIR="$HOME/Film-Scanner"
BRANCH="Web-app-automated-edge-detection"
REPO_URL="https://github.com/YOUR_USERNAME/Film-Scanner.git"

# Check for existing installation
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}⚠ Existing installation found at: ${INSTALL_DIR}${NC}"
    echo ""
    echo "Options:"
    echo "  1. Update existing installation (git pull)"
    echo "  2. Fresh install (backup & replace)"
    echo "  3. Cancel"
    echo ""
    read -p "Enter choice (1-3): " install_choice
    
    case $install_choice in
        1)
            echo ""
            echo -e "${BLUE}Updating existing installation...${NC}"
            cd "$INSTALL_DIR"
            git fetch origin
            git checkout "$BRANCH"
            git pull origin "$BRANCH"
            echo -e "${GREEN}✓ Updated to latest version${NC}"
            ;;
        2)
            echo ""
            echo -e "${BLUE}Creating backup and fresh install...${NC}"
            BACKUP_DIR="${INSTALL_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
            mv "$INSTALL_DIR" "$BACKUP_DIR"
            echo -e "${GREEN}✓ Backup created: ${BACKUP_DIR}${NC}"
            
            echo -e "${BLUE}Cloning repository...${NC}"
            git clone -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
            echo -e "${GREEN}✓ Repository cloned${NC}"
            ;;
        3)
            echo "Installation cancelled."
            exit 0
            ;;
        *)
            echo "Invalid choice. Exiting."
            exit 1
            ;;
    esac
else
    # Fresh installation
    echo -e "${BLUE}Installing to: ${INSTALL_DIR}${NC}"
    echo ""
    
    # Ensure git is installed
    if ! command -v git &> /dev/null; then
        echo -e "${BLUE}Installing git...${NC}"
        sudo apt update
        sudo apt install -y git
    fi
    
    # Clone repository
    echo -e "${BLUE}Cloning repository...${NC}"
    git clone -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
    echo -e "${GREEN}✓ Repository cloned${NC}"
fi

echo ""
cd "$INSTALL_DIR"

# Make scripts executable
chmod +x scripts/*.sh

echo ""
echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}  Running Setup Script${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""

# Run the main setup script
./scripts/setup.sh

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  Installation Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Installation location: $INSTALL_DIR"
echo ""
echo "Quick commands:"
echo "  cd $INSTALL_DIR"
echo "  python3 web_app.py              # Start web app"
echo "  python3 touchscreen_ui.py       # Start touch screen UI"
echo "  python3 touchscreen_ui.py --windowed  # Test mode"
echo ""
echo "Touch screen setup (if not done):"
echo "  sudo ./scripts/setup_touchscreen.sh"
echo ""
