// WebSocket connection
const socket = io();

// WebUSB Camera instance
let webusbCamera = null;
let liveViewCapture = null;

// State variables
let calibrationState = {
    active: false,
    frame1Captured: false,
    frame1Position: null
};

let stripState = {
    active: false,
    firstFrameCaptured: false
};

let previewState = {
    active: false,
    inverted: false
};

let cameraState = {
    connected: false,
    model: 'Unknown',
    liveViewActive: false
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Check browser compatibility
    checkBrowserCompatibility();
    
    // Initialize WebUSB camera
    if (CanonWebUSBCamera.isSupported()) {
        webusbCamera = new CanonWebUSBCamera();
        liveViewCapture = new LiveViewCapture();
    }
    
    // Try to reconnect to previously authorized camera
    tryAutoConnectCamera();
});

// Connect to WebSocket
socket.on('connect', () => {
    console.log('Connected to server');
    socket.emit('request_status');
});

// Handle status updates
socket.on('status_update', (status) => {
    updateUI(status);
});

// Handle preview frames
socket.on('preview_frame', (data) => {
    const previewImg = document.getElementById('preview-image');
    previewImg.src = 'data:image/jpeg;base64,' + data.image;
});

// Update UI with status
function updateUI(status) {
    // Connection status
    document.getElementById('arduino-status').className = 
        status.arduino_connected ? 'status-badge connected' : 'status-badge disconnected';
    document.getElementById('camera-status').className = 
        status.camera_connected ? 'status-badge connected' : 'status-badge disconnected';
    
    // Status values
    document.getElementById('roll-name').textContent = status.roll_name || 'Not set';
    document.getElementById('strip-count').textContent = status.strip_count;
    document.getElementById('frame-count').textContent = status.frame_count;
    document.getElementById('position').textContent = status.position;
    document.getElementById('mode').textContent = status.mode.toUpperCase();
    document.getElementById('frame-advance').textContent = 
        status.frame_advance ? `${status.frame_advance} steps` : 'Not set';
    document.getElementById('status-msg').textContent = status.status_msg;
    
    // Mode and auto-advance displays
    document.getElementById('mode-display').textContent = status.mode.toUpperCase();
    document.getElementById('auto-advance').textContent = status.auto_advance ? 'ON' : 'OFF';
    
    // Show/hide calibration panel based on strip count
    if (status.strip_count === 0 && status.roll_name) {
        document.getElementById('calibration-panel').style.display = 'block';
        document.getElementById('strip-panel').style.display = 'none';
    } else if (status.strip_count > 0) {
        document.getElementById('calibration-panel').style.display = 'none';
        document.getElementById('strip-panel').style.display = 'block';
    } else {
        document.getElementById('calibration-panel').style.display = 'none';
        document.getElementById('strip-panel').style.display = 'none';
    }
}

// API helper
async function apiCall(endpoint, data = {}) {
    try {
        const response = await fetch(`/api/${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        return { success: false, message: 'Network error' };
    }
}

// Button handlers
async function connectArduino() {
    const btn = event.target;
    btn.classList.add('processing');
    
    const result = await apiCall('connect_arduino');
    
    btn.classList.remove('processing');
    
    if (!result.success) {
        alert('Arduino not found. Check connection and try again.');
    }
}

async function createRoll() {
    const rollName = document.getElementById('roll-name-input').value.trim();
    
    if (!rollName) {
        alert('Please enter a roll name');
        return;
    }
    
    const btn = event.target;
    btn.classList.add('processing');
    
    const result = await apiCall('new_roll', { roll_name: rollName });
    
    btn.classList.remove('processing');
    
    if (result.success) {
        document.getElementById('roll-name-input').value = '';
    } else {
        alert(result.message || 'Failed to create roll');
    }
}

// Motor control with press-and-hold support
let motorHoldState = {
    holding: false,
    interval: null,
    button: null
};

async function moveMotor(direction, size) {
    await apiCall('move', { direction, size });
}

function startMotorHold(button, direction, size) {
    if (motorHoldState.holding) return;
    
    motorHoldState.holding = true;
    motorHoldState.button = button;
    button.classList.add('holding');
    
    // Immediate first move
    moveMotor(direction, size);
    
    // Continue moving while held
    motorHoldState.interval = setInterval(() => {
        if (motorHoldState.holding) {
            moveMotor(direction, size);
        }
    }, 150); // Send new command every 150ms for responsiveness
}

function stopMotorHold() {
    if (!motorHoldState.holding) return;
    
    motorHoldState.holding = false;
    
    if (motorHoldState.interval) {
        clearInterval(motorHoldState.interval);
        motorHoldState.interval = null;
    }
    
    if (motorHoldState.button) {
        motorHoldState.button.classList.remove('holding');
        motorHoldState.button = null;
    }
}

async function advanceFrame() {
    const btn = event.target;
    btn.classList.add('processing');
    
    const result = await apiCall('advance_frame');
    
    btn.classList.remove('processing');
    
    if (!result.success) {
        alert('Cannot advance frame. Calibrate first.');
    }
}

async function backupFrame() {
    const btn = event.target;
    btn.classList.add('processing');
    
    const result = await apiCall('backup_frame');
    
    btn.classList.remove('processing');
    
    if (!result.success) {
        alert('Cannot backup frame. Calibrate first.');
    }
}

async function toggleMode() {
    await apiCall('toggle_mode');
}

async function toggleAutoAdvance() {
    await apiCall('toggle_auto_advance');
}

async function zeroPosition() {
    if (confirm('Zero the position counter?')) {
        await apiCall('zero_position');
    }
}

async function autofocus() {
    const btn = event.target;
    btn.classList.add('processing');
    
    const result = await apiCall('autofocus');
    
    btn.classList.remove('processing');
    
    if (!result.success) {
        alert('Autofocus failed. Check console for details.');
    }
}

async function testCapture() {
    const btn = event.target;
    btn.classList.add('processing');
    
    const result = await apiCall('test_capture');
    
    btn.classList.remove('processing');
    
    if (result.success) {
        alert('✓ Test capture successful!\n\nCamera is working. Check camera SD card for test image.\n\n(Frame count was NOT incremented)');
    } else {
        alert('✗ Test capture failed\n\n' + (result.message || 'Check console for details'));
    }
}

async function capture() {
    const btn = event.target;
    btn.classList.add('processing');
    
    const result = await apiCall('capture');
    
    btn.classList.remove('processing');
    
    if (!result.success) {
        alert(result.message || 'Capture failed');
    }
}

// Calibration workflow
function startCalibration() {
    if (calibrationState.active) {
        return;
    }
    
    calibrationState.active = true;
    calibrationState.frame1Captured = false;
    calibrationState.frame1Position = null;
    
    showCalibrationUI();
}

function showCalibrationUI() {
    const container = document.getElementById('calibration-steps');
    
    if (!calibrationState.frame1Captured) {
        container.innerHTML = `
            <div class="help-text">
                <strong>Step 1:</strong> Position the first frame in the scanning window using the motor controls above.
                When perfectly aligned, capture frame 1.
            </div>
            <button class="btn btn-large btn-success" onclick="captureFrame1()">
                📸 Capture Frame 1
            </button>
            <button class="btn btn-secondary" onclick="cancelCalibration()">
                Cancel
            </button>
        `;
    } else {
        container.innerHTML = `
            <div class="help-text">
                <strong>Step 2:</strong> Now manually advance to frame 2 using the motor controls.
                Position frame 2 perfectly, then capture. This distance will be used for all frames.
                <br><br>
                Frame 1 was at position: <strong>${calibrationState.frame1Position}</strong>
            </div>
            <button class="btn btn-large btn-success" onclick="captureFrame2()">
                📸 Capture Frame 2 (Complete Calibration)
            </button>
            <button class="btn btn-secondary" onclick="cancelCalibration()">
                Cancel
            </button>
        `;
    }
}

async function captureFrame1() {
    const btn = event.target;
    btn.classList.add('processing');
    
    const result = await apiCall('calibrate', { action: 'capture_frame1' });
    
    btn.classList.remove('processing');
    
    if (result.success) {
        calibrationState.frame1Captured = true;
        calibrationState.frame1Position = result.frame1_pos;
        showCalibrationUI();
    } else {
        alert(result.message || 'Capture failed');
        cancelCalibration();
    }
}

async function captureFrame2() {
    const btn = event.target;
    btn.classList.add('processing');
    
    const result = await apiCall('calibrate', { 
        action: 'capture_frame2',
        frame1_pos: calibrationState.frame1Position
    });
    
    btn.classList.remove('processing');
    
    if (result.success) {
        alert(`Calibration complete! Frame advance: ${result.frame_advance} steps`);
        calibrationState.active = false;
        // Reset to default button
        document.getElementById('calibration-steps').innerHTML = `
            <button class="btn btn-large btn-warning" onclick="startCalibration()">
                Start Calibration
            </button>
        `;
    } else {
        alert(result.message || 'Calibration failed');
        cancelCalibration();
    }
}

function cancelCalibration() {
    calibrationState.active = false;
    calibrationState.frame1Captured = false;
    calibrationState.frame1Position = null;
    
    document.getElementById('calibration-steps').innerHTML = `
        <button class="btn btn-large btn-warning" onclick="startCalibration()">
            Start Calibration
        </button>
    `;
}

// New Strip workflow
function startNewStrip() {
    if (stripState.active) {
        return;
    }
    
    stripState.active = true;
    stripState.firstFrameCaptured = false;
    
    showNewStripUI();
}

function showNewStripUI() {
    const container = document.getElementById('strip-steps');
    
    if (!stripState.firstFrameCaptured) {
        container.innerHTML = `
            <div class="help-text">
                <strong>New Strip:</strong> Load the new film strip and position the first frame.
                The calibrated frame advance will be used for subsequent frames.
            </div>
            <button class="btn btn-large btn-success" onclick="captureFirstFrame()">
                📸 Capture First Frame of Strip
            </button>
            <button class="btn btn-secondary" onclick="cancelNewStrip()">
                Cancel
            </button>
        `;
    }
}

async function captureFirstFrame() {
    const btn = event.target;
    btn.classList.add('processing');
    
    // Start the new strip first
    await apiCall('new_strip', { action: 'start' });
    
    // Then capture the first frame
    const result = await apiCall('new_strip', { action: 'capture_first' });
    
    btn.classList.remove('processing');
    
    if (result.success) {
        stripState.active = false;
        stripState.firstFrameCaptured = false;
        
        // Reset to default button
        document.getElementById('strip-steps').innerHTML = `
            <button class="btn btn-large btn-success" onclick="startNewStrip()">
                Start New Strip
            </button>
        `;
    } else {
        alert(result.message || 'Failed to start new strip');
        cancelNewStrip();
    }
}

function cancelNewStrip() {
    stripState.active = false;
    stripState.firstFrameCaptured = false;
    
    document.getElementById('strip-steps').innerHTML = `
        <button class="btn btn-large btn-success" onclick="startNewStrip()">
            Start New Strip
        </button>
    `;
}

// Live Preview functions
async function togglePreview() {
    const btn = document.getElementById('preview-toggle');
    const invertBtn = document.getElementById('invert-toggle');
    const previewContainer = document.getElementById('preview-container');
    
    if (!previewState.active) {
        // Start preview
        btn.classList.add('processing');
        const result = await apiCall('start_preview');
        btn.classList.remove('processing');
        
        if (result.success) {
            previewState.active = true;
            btn.textContent = 'Stop Preview';
            invertBtn.disabled = false;
            previewContainer.style.display = 'block';
        } else {
            alert('Failed to start preview. Check camera connection.');
        }
    } else {
        // Stop preview
        btn.classList.add('processing');
        const result = await apiCall('stop_preview');
        btn.classList.remove('processing');
        
        if (result.success) {
            previewState.active = false;
            btn.textContent = 'Start Preview';
            invertBtn.disabled = true;
            previewContainer.style.display = 'none';
        }
    }
}

function toggleInvert() {
    const previewImg = document.getElementById('preview-image');
    const invertBtn = document.getElementById('invert-toggle');
    
    previewState.inverted = !previewState.inverted;
    
    if (previewState.inverted) {
        previewImg.classList.add('inverted');
        invertBtn.textContent = 'View as Negative';
    } else {
        previewImg.classList.remove('inverted');
        invertBtn.textContent = 'View as Positive';
    }
}

// Keyboard shortcuts (for desktop)
document.addEventListener('keydown', (e) => {
    // Ignore if typing in input field
    if (e.target.tagName === 'INPUT') {
        return;
    }
    
    switch(e.key) {
        case ' ':
            e.preventDefault();
            capture();
            break;
        case 'ArrowLeft':
            e.preventDefault();
            moveMotor('backward', e.shiftKey ? 'coarse' : 'fine');
            break;
        case 'ArrowRight':
            e.preventDefault();
            moveMotor('forward', e.shiftKey ? 'coarse' : 'fine');
            break;
        case 'f':
        case 'F':
            e.preventDefault();
            autofocus();
            break;
        case 'a':
        case 'A':
            e.preventDefault();
            toggleAutoAdvance();
            break;
        case 'm':
        case 'M':
            e.preventDefault();
            toggleMode();
            break;
    }
});

// Request status update every 1 second (improved responsiveness)
setInterval(() => {
    socket.emit('request_status');
}, 1000);

// Initial status request
window.addEventListener('load', () => {
    socket.emit('request_status');
});

// Setup motor button press-and-hold functionality
document.addEventListener('DOMContentLoaded', () => {
    const motorButtons = document.querySelectorAll('.motor-btn');
    
    motorButtons.forEach(button => {
        const direction = button.dataset.direction;
        const size = button.dataset.size;
        
        // Mouse events (desktop)
        button.addEventListener('mousedown', (e) => {
            e.preventDefault();
            startMotorHold(button, direction, size);
        });
        
        button.addEventListener('mouseup', (e) => {
            e.preventDefault();
            stopMotorHold();
        });
        
        button.addEventListener('mouseleave', (e) => {
            stopMotorHold();
        });
        
        // Touch events (mobile)
        button.addEventListener('touchstart', (e) => {
            e.preventDefault();
            startMotorHold(button, direction, size);
        });
        
        button.addEventListener('touchend', (e) => {
            e.preventDefault();
            stopMotorHold();
        });
        
        button.addEventListener('touchcancel', (e) => {
            e.preventDefault();
            stopMotorHold();
        });
    });
    
    // Global safety: stop on any mouse up anywhere on page
    document.addEventListener('mouseup', () => {
        stopMotorHold();
    });
    
    document.addEventListener('touchend', () => {
        stopMotorHold();
    });
});

//=============================================================================
// WebUSB Camera Functions
//=============================================================================

/**
 * Check browser compatibility for WebUSB
 */
function checkBrowserCompatibility() {
    const browserWarning = document.getElementById('browser-warning');
    
    if (!CanonWebUSBCamera || !CanonWebUSBCamera.isSupported()) {
        if (browserWarning) {
            browserWarning.innerHTML = `
                <strong>⚠️ WebUSB Not Supported</strong><br>
                This browser doesn't support WebUSB (required for camera control).<br>
                Please use <strong>Chrome</strong> or <strong>Edge</strong> for best experience.
            `;
            browserWarning.style.display = 'block';
        }
        return false;
    }
    
    // Check for HTTPS (required for WebUSB except localhost)
    if (location.protocol !== 'https:' && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1' && !location.hostname.endsWith('.local')) {
        if (browserWarning) {
            browserWarning.innerHTML = `
                <strong>⚠️ HTTPS Required</strong><br>
                WebUSB requires a secure connection (HTTPS).<br>
                Access via <strong>localhost</strong> or use HTTPS.
            `;
            browserWarning.style.display = 'block';
        }
        return false;
    }
    
    if (browserWarning) {
        browserWarning.style.display = 'none';
    }
    return true;
}

/**
 * Try to auto-connect to previously authorized camera
 */
async function tryAutoConnectCamera() {
    if (!webusbCamera) return;
    
    try {
        await webusbCamera.connectToAuthorizedDevice();
        await webusbCamera.connect();
        
        cameraState.connected = true;
        cameraState.model = webusbCamera.cameraModel;
        
        updateCameraUI();
        showNotification('✓ Camera reconnected automatically', 'success');
        
    } catch (error) {
        // No authorized device or connection failed
        // This is normal on first use
        console.log('No authorized camera to auto-connect');
    }
}

/**
 * Connect to camera (user initiates)
 */
async function connectCamera() {
    if (!webusbCamera) {
        alert('WebUSB not supported in this browser. Please use Chrome or Edge.');
        return;
    }
    
    const btn = document.getElementById('connect-camera-btn');
    btn.classList.add('processing');
    btn.textContent = 'Connecting...';
    
    try {
        // Step 1: Request device selection
        await webusbCamera.requestDevice();
        
        // Step 2: Connect to selected device
        await webusbCamera.connect();
        
        cameraState.connected = true;
        cameraState.model = webusbCamera.cameraModel;
        
        updateCameraUI();
        showNotification(`✓ Connected to ${cameraState.model}`, 'success');
        
    } catch (error) {
        console.error('Camera connection failed:', error);
        showNotification('❌ Camera connection failed: ' + error.message, 'error');
    } finally {
        btn.classList.remove('processing');
        updateCameraUI();
    }
}

/**
 * Disconnect camera
 */
async function disconnectCamera() {
    if (!webusbCamera) return;
    
    try {
        await webusbCamera.disconnect();
        
        cameraState.connected = false;
        cameraState.model = 'Unknown';
        cameraState.liveViewActive = false;
        
        updateCameraUI();
        showNotification('Camera disconnected', 'info');
        
    } catch (error) {
        console.error('Disconnect error:', error);
    }
}

/**
 * Update camera UI elements
 */
function updateCameraUI() {
    const connectBtn = document.getElementById('connect-camera-btn');
    const disconnectBtn = document.getElementById('disconnect-camera-btn');
    const cameraStatus = document.getElementById('webusb-camera-status');
    const cameraModel = document.getElementById('webusb-camera-model');
    const cameraControls = document.getElementById('webusb-camera-controls');
    
    if (connectBtn && cameraState.connected) {
        connectBtn.style.display = 'none';
    } else if (connectBtn) {
        connectBtn.style.display = 'inline-block';
        connectBtn.textContent = '📷 Connect Camera';
    }
    
    if (disconnectBtn) {
        disconnectBtn.style.display = cameraState.connected ? 'inline-block' : 'none';
    }
    
    if (cameraStatus) {
        cameraStatus.className = cameraState.connected ? 'status-badge connected' : 'status-badge disconnected';
        cameraStatus.textContent = cameraState.connected ? 'Connected' : 'Disconnected';
    }
    
    if (cameraModel) {
        cameraModel.textContent = cameraState.connected ? cameraState.model : 'Not connected';
    }
    
    if (cameraControls) {
        cameraControls.style.display = cameraState.connected ? 'block' : 'none';
    }
}

/**
 * Start live view from EOS Utility window
 */
async function startLiveView() {
    if (!liveViewCapture || !LiveViewCapture.isSupported()) {
        alert('Live view not supported in this browser');
        return;
    }
    
    const btn = document.getElementById('start-liveview-btn');
    if (btn) {
        btn.classList.add('processing');
        btn.textContent = 'Select Window...';
    }
    
    try {
        // Request window share (EOS Utility)
        const success = await liveViewCapture.requestWindowShare();
        
        if (!success) {
            throw new Error('Window share cancelled');
        }
        
        showNotification('✓ Select your EOS Utility window for live view', 'info');
        
        // Get video element
        const videoElement = document.getElementById('liveview-video');
        
        // Start capturing frames
        if (videoElement) {
            await liveViewCapture.startCapture(videoElement, (blob) => {
                // Frames are automatically displayed in video element
            });
        }
        
        cameraState.liveViewActive = true;
        updateLiveViewUI();
        
        showNotification('✓ Live view active', 'success');
        
    } catch (error) {
        console.error('Live view start failed:', error);
        showNotification('❌ Live view failed: ' + error.message, 'error');
    } finally {
        if (btn) {
            btn.classList.remove('processing');
        }
        updateLiveViewUI();
    }
}

/**
 * Stop live view
 */
function stopLiveView() {
    if (!liveViewCapture) return;
    
    liveViewCapture.stopCapture();
    cameraState.liveViewActive = false;
    updateLiveViewUI();
    
    showNotification('Live view stopped', 'info');
}

/**
 * Update live view UI
 */
function updateLiveViewUI() {
    const startBtn = document.getElementById('start-liveview-btn');
    const stopBtn = document.getElementById('stop-liveview-btn');
    const liveviewPanel = document.getElementById('liveview-panel');
    
    if (startBtn) {
        startBtn.style.display = cameraState.liveViewActive ? 'none' : 'inline-block';
        if (!cameraState.liveViewActive) {
            startBtn.textContent = '📹 Start Live View';
        }
    }
    
    if (stopBtn) {
        stopBtn.style.display = cameraState.liveViewActive ? 'inline-block' : 'none';
    }
    
    if (liveviewPanel) {
        liveviewPanel.style.display = cameraState.liveViewActive ? 'block' : 'none';
    }
}

/**
 * Autofocus via WebUSB
 */
async function autofocusWebUSB() {
    if (!cameraState.connected || !webusbCamera) {
        alert('Camera not connected');
        return;
    }
    
    const btn = event.target;
    btn.classList.add('processing');
    
    try {
        const success = await webusbCamera.autofocus();
        
        if (success) {
            showNotification('✓ Autofocus triggered', 'success');
        } else {
            showNotification('⚠️ Autofocus may not be supported', 'warning');
        }
        
    } catch (error) {
        console.error('Autofocus error:', error);
        showNotification('❌ Autofocus failed', 'error');
    } finally {
        btn.classList.remove('processing');
    }
}

/**
 * Capture via WebUSB
 */
async function captureWebUSB() {
    if (!cameraState.connected || !webusbCamera) {
        alert('Camera not connected');
        return;
    }
    
    const btn = event.target;
    btn.classList.add('processing');
    
    try {
        const success = await webusbCamera.capture();
        
        if (success) {
            // Update frame count on server side
            await apiCall('capture');
            showNotification('✓ Image captured', 'success');
        } else {
            showNotification('❌ Capture failed', 'error');
        }
        
    } catch (error) {
        console.error('Capture error:', error);
        showNotification('❌ Capture failed: ' + error.message, 'error');
    } finally {
        btn.classList.remove('processing');
    }
}

/**
 * Show notification
 */
function showNotification(message, type = 'info') {
    const notification = document.getElementById('notification');
    if (!notification) return;
    
    notification.textContent = message;
    notification.className = `notification ${type}`;
    notification.style.display = 'block';
    
    setTimeout(() => {
        notification.style.display = 'none';
    }, 5000);
}

