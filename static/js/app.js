// WebSocket connection
const socket = io();

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

