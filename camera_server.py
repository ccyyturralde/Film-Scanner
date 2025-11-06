#!/usr/bin/env python3
"""
Film Scanner - Remote Camera Server

This script runs on the user's computer (Windows/Mac/Linux) where the camera
is physically connected. It provides an HTTP API for the Raspberry Pi to
control the camera remotely.

Features:
- Live view streaming (from EOS Utility window or gphoto2)
- Remote autofocus via gphoto2
- Remote capture via gphoto2
- Camera status checking
- Cross-platform support

Usage:
    python3 camera_server.py

The server will run on http://0.0.0.0:8888
Configure this URL in the Film Scanner web interface.
"""

from flask import Flask, jsonify, send_file, request
from flask_cors import CORS
import subprocess
import time
import os
import sys
import platform
import io
import json
import threading
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Enable CORS for Pi to access this server

# Configuration
PORT = 8888
HOST = '0.0.0.0'

# State
camera_connected = False
camera_model = "Unknown"
last_check_time = 0

# Live view configuration
liveview_enabled = False
liveview_source = None  # 'eos_utility', 'gphoto2', or None
eos_utility_window = None  # Window coordinates for EOS Utility

# Try to import optional dependencies for live view
try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False
    print("⚠️  'mss' not installed - EOS Utility window capture not available")
    print("   Install with: pip3 install mss")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️  'Pillow' not installed - image processing limited")
    print("   Install with: pip3 install Pillow")


def get_local_ip():
    """Get local IP address"""
    import socket
    try:
        # Create a socket to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"


def check_gphoto2():
    """Check if gphoto2 is installed"""
    try:
        result = subprocess.run(
            ["gphoto2", "--version"],
            capture_output=True,
            timeout=2,
            text=True
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def kill_gphoto2_processes():
    """Kill any existing gphoto2 processes"""
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.run(["taskkill", "/F", "/IM", "gphoto2.exe"], 
                         capture_output=True, timeout=2)
        else:
            subprocess.run(["killall", "gphoto2"], 
                         capture_output=True, timeout=1)
            subprocess.run(["killall", "-9", "gphoto2"], 
                         capture_output=True, timeout=1)
            # Also kill gvfs which can interfere
            subprocess.run(["killall", "gvfs-gphoto2-volume-monitor"], 
                         capture_output=True, timeout=1)
        time.sleep(0.5)
    except:
        pass


def check_camera_connection():
    """Check if camera is connected via USB"""
    global camera_connected, camera_model, last_check_time
    
    current_time = time.time()
    if current_time - last_check_time < 5:
        return camera_connected
    
    last_check_time = current_time
    
    try:
        kill_gphoto2_processes()
        
        result = subprocess.run(
            ["gphoto2", "--auto-detect"],
            capture_output=True,
            timeout=10,
            text=True
        )
        
        if result.returncode == 0 and "usb" in result.stdout.lower():
            lines = result.stdout.strip().split('\n')
            for line in lines[2:]:  # Skip header lines
                if 'usb' in line.lower():
                    camera_model = line.split('usb')[0].strip()
                    camera_connected = True
                    return True
        
        camera_connected = False
        camera_model = "Not detected"
        return False
        
    except subprocess.TimeoutExpired:
        camera_connected = False
        camera_model = "Check timeout"
        return False
    except Exception as e:
        camera_connected = False
        camera_model = f"Error: {e}"
        return False


def capture_eos_utility_window():
    """Capture EOS Utility window as JPEG"""
    if not MSS_AVAILABLE:
        return None
    
    # TODO: Implement window detection and capture
    # This requires finding the EOS Utility window and grabbing its contents
    # For now, return None (will use gphoto2 fallback)
    return None


def capture_gphoto2_preview():
    """Capture preview image using gphoto2"""
    try:
        kill_gphoto2_processes()
        
        # Create temp file
        temp_file = os.path.join(os.path.dirname(__file__), "temp_preview.jpg")
        
        result = subprocess.run(
            ["gphoto2", "--capture-preview", f"--filename={temp_file}"],
            capture_output=True,
            timeout=10
        )
        
        if result.returncode == 0 and os.path.exists(temp_file):
            with open(temp_file, 'rb') as f:
                data = f.read()
            
            # Cleanup
            try:
                os.remove(temp_file)
            except:
                pass
            
            return data
        
        return None
        
    except Exception as e:
        print(f"Preview capture error: {e}")
        return None


# API Routes

@app.route('/')
def index():
    """Server info page"""
    return jsonify({
        "name": "Film Scanner Camera Server",
        "version": "1.0.0",
        "status": "running",
        "camera_connected": camera_connected,
        "camera_model": camera_model,
        "endpoints": {
            "status": "/api/status",
            "live_view": "/api/live-view",
            "autofocus": "/api/autofocus",
            "capture": "/api/capture",
            "check_camera": "/api/check-camera"
        }
    })


@app.route('/api/status')
def get_status():
    """Get camera server status"""
    return jsonify({
        "server_running": True,
        "camera_connected": camera_connected,
        "camera_model": camera_model,
        "gphoto2_available": check_gphoto2(),
        "liveview_enabled": liveview_enabled,
        "liveview_source": liveview_source,
        "mss_available": MSS_AVAILABLE,
        "pil_available": PIL_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    })


@app.route('/api/check-camera')
def api_check_camera():
    """Force camera connection check"""
    connected = check_camera_connection()
    return jsonify({
        "connected": connected,
        "model": camera_model
    })


@app.route('/api/live-view')
def live_view():
    """Get live view frame"""
    if not camera_connected:
        return jsonify({"error": "Camera not connected"}), 503
    
    # Try EOS Utility window capture first
    frame_data = capture_eos_utility_window()
    
    # Fallback to gphoto2 preview
    if frame_data is None:
        frame_data = capture_gphoto2_preview()
    
    if frame_data is None:
        return jsonify({"error": "Failed to capture live view"}), 500
    
    return send_file(
        io.BytesIO(frame_data),
        mimetype='image/jpeg',
        as_attachment=False
    )


@app.route('/api/autofocus', methods=['POST'])
def autofocus():
    """Trigger camera autofocus"""
    if not camera_connected:
        return jsonify({"error": "Camera not connected"}), 503
    
    try:
        kill_gphoto2_processes()
        
        result = subprocess.run(
            ["gphoto2", "--set-config", "autofocus=1"],
            capture_output=True,
            timeout=10,
            text=True
        )
        
        if result.returncode == 0:
            return jsonify({
                "success": True,
                "message": "Autofocus triggered"
            })
        else:
            return jsonify({
                "success": False,
                "error": result.stderr
            }), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({
            "success": False,
            "error": "Autofocus timeout"
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/capture', methods=['POST'])
def capture():
    """Capture image"""
    if not camera_connected:
        return jsonify({"error": "Camera not connected"}), 503
    
    try:
        kill_gphoto2_processes()
        
        # Get parameters
        data = request.get_json() or {}
        download = data.get('download', False)
        
        if download:
            # Capture and download
            result = subprocess.run(
                ["gphoto2", "--capture-image-and-download"],
                capture_output=True,
                timeout=30,
                text=True
            )
        else:
            # Just capture (stays on camera)
            result = subprocess.run(
                ["gphoto2", "--capture-image"],
                capture_output=True,
                timeout=30,
                text=True
            )
        
        if result.returncode == 0:
            return jsonify({
                "success": True,
                "message": "Image captured",
                "output": result.stdout
            })
        else:
            return jsonify({
                "success": False,
                "error": result.stderr
            }), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({
            "success": False,
            "error": "Capture timeout"
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/configure-liveview', methods=['POST'])
def configure_liveview():
    """Configure live view source"""
    global liveview_enabled, liveview_source, eos_utility_window
    
    data = request.get_json()
    liveview_enabled = data.get('enabled', False)
    liveview_source = data.get('source', 'gphoto2')  # 'eos_utility' or 'gphoto2'
    
    if liveview_source == 'eos_utility' and data.get('window_coords'):
        eos_utility_window = data.get('window_coords')
    
    return jsonify({
        "success": True,
        "liveview_enabled": liveview_enabled,
        "liveview_source": liveview_source
    })


def main():
    """Start the camera server"""
    print("\n" + "="*60)
    print("   FILM SCANNER - REMOTE CAMERA SERVER")
    print("="*60 + "\n")
    
    # Check gphoto2
    if not check_gphoto2():
        print("❌ gphoto2 not found!")
        print("\nPlease install gphoto2:")
        print("  • macOS:   brew install gphoto2")
        print("  • Ubuntu:  sudo apt install gphoto2")
        print("  • Windows: Download from gphoto.org\n")
        return
    
    print("✓ gphoto2 found")
    
    # Check camera
    print("\n🔌 Checking for camera...")
    if check_camera_connection():
        print(f"✓ Camera detected: {camera_model}")
    else:
        print("⚠️  No camera detected (you can connect later)")
    
    # Show optional features
    print(f"\n📦 Optional Features:")
    print(f"  • EOS Utility window capture: {'✓' if MSS_AVAILABLE else '✗'} (mss)")
    print(f"  • Image processing: {'✓' if PIL_AVAILABLE else '✗'} (Pillow)")
    
    if not MSS_AVAILABLE:
        print("\n💡 For EOS Utility window capture, install:")
        print("   pip3 install mss Pillow")
    
    # Get server info
    local_ip = get_local_ip()
    
    print("\n" + "="*60)
    print("   SERVER STARTING")
    print("="*60)
    print(f"\n🌐 Camera Server URLs:")
    print(f"   • Local:   http://localhost:{PORT}")
    print(f"   • Network: http://{local_ip}:{PORT}")
    print(f"\n📝 Enter this URL in Film Scanner web interface:")
    print(f"   http://{local_ip}:{PORT}")
    print("\n💡 Keep this window open while using Film Scanner")
    print("="*60 + "\n")
    
    # Start server
    try:
        app.run(host=HOST, port=PORT, debug=False)
    except KeyboardInterrupt:
        print("\n\n👋 Camera server stopped\n")
    except Exception as e:
        print(f"\n❌ Server error: {e}\n")


if __name__ == '__main__':
    main()

