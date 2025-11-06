#!/bin/bash
# Film Scanner - Camera Server Startup Script (macOS/Linux)

echo ""
echo "============================================================"
echo "   FILM SCANNER - Camera Server for macOS/Linux"
echo "============================================================"
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ ERROR: Python 3 is not installed"
    echo ""
    echo "Please install Python 3.7+:"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  • macOS: brew install python3"
    else
        echo "  • Ubuntu/Debian: sudo apt install python3 python3-pip"
    fi
    echo ""
    exit 1
fi

# Check if gphoto2 is installed
echo "Checking for gphoto2..."
if ! command -v gphoto2 &> /dev/null; then
    echo "❌ ERROR: gphoto2 is not installed"
    echo ""
    echo "Please install gphoto2:"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  • macOS: brew install gphoto2"
    else
        echo "  • Ubuntu/Debian: sudo apt install gphoto2"
    fi
    echo ""
    exit 1
fi

echo "✓ gphoto2 found: $(gphoto2 --version | head -n 1)"

# Check if in correct directory
if [ ! -f "camera_server.py" ]; then
    echo "❌ ERROR: camera_server.py not found"
    echo "Please run this script from the Film-Scanner directory"
    echo ""
    exit 1
fi

# Check/install requirements
echo ""
echo "Checking Python packages..."
if ! python3 -c "import flask" &> /dev/null; then
    echo "Installing required packages..."
    pip3 install -r requirements.txt
    
    if [ $? -ne 0 ]; then
        echo ""
        echo "❌ ERROR: Failed to install requirements"
        echo "Please run: pip3 install -r requirements.txt"
        echo ""
        exit 1
    fi
fi

echo "✓ All requirements installed"

# Make sure camera_server.py is executable
chmod +x camera_server.py

echo ""
echo "Starting camera server..."
echo "Press Ctrl+C to stop"
echo ""

# Run the camera server
python3 camera_server.py

