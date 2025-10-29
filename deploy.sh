#!/bin/bash
# Quick deployment script for film scanner updates

set -e

echo "==================================="
echo "Film Scanner - Quick Deploy"
echo "==================================="
echo ""

# Check if we're in the outputs directory
if [ ! -f "optimized_edge_detect.py" ] || [ ! -f "scanner_app_improved.py" ]; then
    echo "ERROR: Run this from /mnt/user-data/outputs/"
    exit 1
fi

# Find film-scanner directory
if [ -d "$HOME/film-scanner" ]; then
    SCANNER_DIR="$HOME/film-scanner"
elif [ -d "$HOME/Film-Scanner" ]; then
    SCANNER_DIR="$HOME/Film-Scanner"
else
    echo "ERROR: Cannot find film-scanner directory"
    echo "Please specify path:"
    read -r SCANNER_DIR
fi

echo "Scanner directory: $SCANNER_DIR"
echo ""

# Backup existing files
if [ -f "$SCANNER_DIR/optimized_edge_detect.py" ]; then
    echo "Backing up existing files..."
    cp "$SCANNER_DIR/optimized_edge_detect.py" "$SCANNER_DIR/optimized_edge_detect.py.backup"
    echo "  ✓ Backed up optimized_edge_detect.py"
fi

if [ -f "$SCANNER_DIR/scanner_app_improved.py" ]; then
    cp "$SCANNER_DIR/scanner_app_improved.py" "$SCANNER_DIR/scanner_app_improved.py.backup"
    echo "  ✓ Backed up scanner_app_improved.py"
fi

echo ""

# Copy new files
echo "Copying new files..."
cp optimized_edge_detect.py "$SCANNER_DIR/"
echo "  ✓ Copied optimized_edge_detect.py"

cp scanner_app_improved.py "$SCANNER_DIR/"
echo "  ✓ Copied scanner_app_improved.py"

echo ""
echo "==================================="
echo "✓ Deployment Complete!"
echo "==================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Test detection:"
echo "   cd $SCANNER_DIR"
echo "   python3 optimized_edge_detect.py /path/to/image.jpg --debug"
echo ""
echo "2. Commit to git:"
echo "   cd $SCANNER_DIR"
echo "   git add optimized_edge_detect.py scanner_app_improved.py"
echo "   git commit -m 'Implement proper two-gap frame detection'"
echo "   git push"
echo ""
echo "3. Run scanner:"
echo "   cd $SCANNER_DIR"
echo "   python3 scanner_app_improved.py"
echo ""
echo "Backup files saved with .backup extension"
echo ""
