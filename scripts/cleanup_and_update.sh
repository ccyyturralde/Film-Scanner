#!/bin/bash
# =============================================================================
# Film Scanner - Complete Cleanup and Update Script
# =============================================================================
# This script ensures the Pi has the latest code and removes all old files
# 
# Run with: bash scripts/cleanup_and_update.sh
# =============================================================================

set -e

echo "========================================="
echo "Film Scanner - Cleanup and Update"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_step() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Find the Film Scanner directory
if [ -d "$HOME/Film-Scanner" ]; then
    SCANNER_DIR="$HOME/Film-Scanner"
elif [ -d "$HOME/film-scanner" ]; then
    SCANNER_DIR="$HOME/film-scanner"
else
    print_error "Cannot find Film-Scanner directory!"
    echo "Please run from the Film-Scanner directory"
    exit 1
fi

cd "$SCANNER_DIR"
echo "Working directory: $SCANNER_DIR"
echo ""

# Step 1: Stop all services
echo "Step 1: Stopping services..."
sudo systemctl stop film-scanner-touchscreen 2>/dev/null || true
sudo systemctl stop film-scanner-web 2>/dev/null || true
sudo systemctl stop film-scanner 2>/dev/null || true
# Kill any running Python processes related to our app
pkill -f "touchscreen_ui.py" 2>/dev/null || true
pkill -f "touchscreen_launcher.py" 2>/dev/null || true
pkill -f "web_app.py" 2>/dev/null || true
sleep 2
print_step "Services stopped"

# Step 2: Delete old touchscreen files that might exist
echo ""
echo "Step 2: Removing old touchscreen files..."
OLD_FILES=(
    "touchscreen_launcher.py"
    "touchscreen_terminal.py"
    "touchscreen_debug.py"
    "touchscreen_settings.py"
)

for file in "${OLD_FILES[@]}"; do
    if [ -f "$SCANNER_DIR/$file" ]; then
        rm -f "$SCANNER_DIR/$file"
        print_warn "Removed old file: $file"
    fi
done
print_step "Old files cleaned up"

# Step 3: Delete old config file (it may have auto_start_app: true)
echo ""
echo "Step 3: Removing old config file..."
if [ -f "$HOME/.film_scanner/touchscreen_config.json" ]; then
    rm -f "$HOME/.film_scanner/touchscreen_config.json"
    print_warn "Removed old touchscreen_config.json"
else
    echo "   (No old config file found)"
fi
print_step "Config cleaned up"

# Step 4: Uninstall eventlet (causes RLock errors)
echo ""
echo "Step 4: Removing eventlet package..."
pip3 uninstall eventlet -y --break-system-packages 2>/dev/null || true
print_step "Eventlet removed (if it was installed)"

# Step 5: Fetch and pull latest code
echo ""
echo "Step 5: Updating from git..."
git fetch --all
CURRENT_BRANCH=$(git branch --show-current)
echo "   Current branch: $CURRENT_BRANCH"

# Check if we need to switch branches
if [ "$CURRENT_BRANCH" != "Web-app-automated-edge-detection" ]; then
    print_warn "Switching to Web-app-automated-edge-detection branch..."
    git checkout Web-app-automated-edge-detection
fi

git pull origin Web-app-automated-edge-detection
print_step "Code updated"

# Step 6: Verify correct files exist
echo ""
echo "Step 6: Verifying installation..."
REQUIRED_FILES=(
    "touchscreen_ui.py"
    "touchscreen_config.py"
    "app_manager.py"
    "web_app.py"
)

all_good=true
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$SCANNER_DIR/$file" ]; then
        print_step "Found: $file"
    else
        print_error "Missing: $file"
        all_good=false
    fi
done

# Verify old files are gone
for file in "${OLD_FILES[@]}"; do
    if [ -f "$SCANNER_DIR/$file" ]; then
        print_error "Old file still exists: $file - removing..."
        rm -f "$SCANNER_DIR/$file"
    fi
done

# Step 7: Update systemd service file
echo ""
echo "Step 7: Updating systemd service..."

# Create/update the service file
cat > /tmp/film-scanner-touchscreen.service << 'EOF'
[Unit]
Description=Film Scanner Touch Screen UI
After=multi-user.target
Wants=systemd-udev-settle.service

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/Film-Scanner
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 /home/pi/Film-Scanner/touchscreen_ui.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=film-scanner-touchscreen

[Install]
WantedBy=multi-user.target
EOF

# Check if paths need adjustment
if [ "$SCANNER_DIR" != "/home/pi/Film-Scanner" ]; then
    CURRENT_USER=$(whoami)
    sed -i "s|/home/pi/Film-Scanner|$SCANNER_DIR|g" /tmp/film-scanner-touchscreen.service
    sed -i "s|User=pi|User=$CURRENT_USER|g" /tmp/film-scanner-touchscreen.service
    sed -i "s|Group=pi|Group=$CURRENT_USER|g" /tmp/film-scanner-touchscreen.service
fi

sudo cp /tmp/film-scanner-touchscreen.service /etc/systemd/system/
sudo systemctl daemon-reload
print_step "Service file updated"

# Step 8: Verify service file points to correct app
echo ""
echo "Step 8: Verifying service configuration..."
SERVICE_EXEC=$(grep "ExecStart" /etc/systemd/system/film-scanner-touchscreen.service | head -1)
if [[ "$SERVICE_EXEC" == *"touchscreen_ui.py"* ]]; then
    print_step "Service points to touchscreen_ui.py"
elif [[ "$SERVICE_EXEC" == *"touchscreen_launcher.py"* ]]; then
    print_error "Service still points to old touchscreen_launcher.py!"
    echo "   Updating service file..."
    sudo sed -i 's/touchscreen_launcher.py/touchscreen_ui.py/g' /etc/systemd/system/film-scanner-touchscreen.service
    sudo systemctl daemon-reload
    print_step "Service file corrected"
fi

# Step 9: Enable and restart service
echo ""
echo "Step 9: Starting service..."
sudo systemctl enable film-scanner-touchscreen
sudo systemctl restart film-scanner-touchscreen

sleep 3

# Check if it's running
if systemctl is-active --quiet film-scanner-touchscreen; then
    print_step "Service started successfully!"
else
    print_error "Service failed to start. Check logs with: journalctl -u film-scanner-touchscreen -n 50"
fi

# Summary
echo ""
echo "========================================="
echo "Cleanup Complete!"
echo "========================================="
echo ""
echo "What was done:"
echo "  • Stopped all services"
echo "  • Removed old touchscreen files"
echo "  • Removed old config file"
echo "  • Uninstalled eventlet"
echo "  • Updated code from git"
echo "  • Updated systemd service"
echo "  • Restarted touchscreen service"
echo ""
echo "The touchscreen UI should now:"
echo "  • Show FIX CAM button (not Exit)"
echo "  • NOT auto-start the web app"
echo "  • NOT have RLock errors"
echo ""
echo "To check logs:"
echo "  journalctl -u film-scanner-touchscreen -f"
echo ""
echo "To manually start web app, press START on touchscreen"
echo "========================================="

