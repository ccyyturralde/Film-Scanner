#!/bin/bash
# Update Film-Scanner Repository with Corrected Detection
# Run this script to deploy the new two-gap detection code

set -e

echo "======================================================================="
echo "Film Scanner - Repository Update Script"
echo "======================================================================="
echo ""
echo "This will update your Film-Scanner repository with:"
echo "  ✓ Proper two-gap frame detection"
echo "  ✓ Calibration system"
echo "  ✓ Smart auto-advance"
echo ""

# Find your film-scanner directory
SCANNER_DIR=""

if [ -d "$HOME/Film-Scanner" ]; then
    SCANNER_DIR="$HOME/Film-Scanner"
elif [ -d "$HOME/film-scanner" ]; then
    SCANNER_DIR="$HOME/film-scanner"
else
    echo "ERROR: Cannot find Film-Scanner directory"
    echo "Please specify the path:"
    read -r SCANNER_DIR
fi

if [ ! -d "$SCANNER_DIR" ]; then
    echo "ERROR: Directory not found: $SCANNER_DIR"
    exit 1
fi

echo "Scanner directory: $SCANNER_DIR"
echo ""

# Check if we have the new files
if [ ! -f "/mnt/user-data/outputs/optimized_edge_detect.py" ]; then
    echo "ERROR: New files not found in /mnt/user-data/outputs/"
    echo "Make sure you have the latest files from Claude"
    exit 1
fi

# Backup existing files
echo "Creating backups..."
cd "$SCANNER_DIR"

if [ -f "optimized_edge_detect.py" ]; then
    cp optimized_edge_detect.py optimized_edge_detect.py.old
    echo "  ✓ Backed up optimized_edge_detect.py"
fi

if [ -f "scanner_app_improved.py" ]; then
    cp scanner_app_improved.py scanner_app_improved.py.old
    echo "  ✓ Backed up scanner_app_improved.py"
fi

echo ""

# Copy new files
echo "Copying new files..."
cp /mnt/user-data/outputs/optimized_edge_detect.py .
echo "  ✓ Updated optimized_edge_detect.py (two-gap detection)"

cp /mnt/user-data/outputs/scanner_app_improved.py .
echo "  ✓ Updated scanner_app_improved.py (with calibration)"

echo ""

# Show what changed
echo "======================================================================="
echo "Changes Summary"
echo "======================================================================="
echo ""
echo "optimized_edge_detect.py:"
echo "  OLD: Single gap detection, position at 75-90%"
echo "  NEW: Two-gap detection, center frame content"
echo ""
echo "scanner_app_improved.py:"
echo "  OLD: Basic alignment"
echo "  NEW: Calibration system + smart auto-advance"
echo ""

# Git status
echo "Git status:"
if command -v git &> /dev/null; then
    git status --short
    echo ""
fi

# Next steps
echo "======================================================================="
echo "Next Steps"
echo "======================================================================="
echo ""
echo "1. Test locally:"
echo "   python3 optimized_edge_detect.py /path/to/test/image.jpg --debug"
echo ""
echo "2. Commit to Git:"
echo "   git add optimized_edge_detect.py scanner_app_improved.py"
echo "   git commit -m 'Implement proper two-gap frame detection'"
echo "   git push"
echo ""
echo "3. Deploy to Raspberry Pi:"
echo "   ssh pi@your-pi-ip"
echo "   cd ~/Film-Scanner"
echo "   git pull"
echo ""
echo "4. Test on Pi:"
echo "   python3 scanner_app_improved.py"
echo ""
echo "Backup files saved with .old extension"
echo "Original files can be restored if needed"
echo ""
echo "======================================================================="
echo "✓ Update Complete!"
echo "======================================================================="
