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
    inverted: false,
    autoRefresh: false,
    refreshInterval: 1000,
    refreshTimer: null
};

let settingsState = {
    fineStep: 8,
    coarseStep: 192
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

// API helper with better error handling
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

// Button state management to prevent double-clicks
const buttonStates = new Map();

function setButtonProcessing(btn, processing) {
    if (processing) {
        btn.classList.add('processing');
        btn.disabled = true;
        buttonStates.set(btn, true);
    } else {
        btn.classList.remove('processing');
        btn.disabled = false;
        buttonStates.delete(btn);
    }
}

// Button handlers
async function connectArduino() {
    const btn = event.target;
    setButtonProcessing(btn, true);
    
    const result = await apiCall('connect_arduino');
    
    setButtonProcessing(btn, false);
    
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
    setButtonProcessing(btn, true);
    
    const result = await apiCall('new_roll', { roll_name: rollName });
    
    setButtonProcessing(btn, false);
    
    if (result.success) {
        document.getElementById('roll-name-input').value = '';
    } else {
        alert(result.message || 'Failed to create roll');
    }
}

// Optimized motor control with better responsiveness
let motorHoldState = {
    holding: false,
    interval: null,
    button: null,
    lastMoveTime: 0
};

async function moveMotor(direction, size) {
    // Prevent too-frequent calls
    const now = Date.now();
    if (now - motorHoldState.lastMoveTime < 50) {
        return;
    }
    motorHoldState.lastMoveTime = now;
    
    await apiCall('move', { direction, size });
}

function startMotorHold(button, direction, size) {
    if (motorHoldState.holding) return;
    
    motorHoldState.holding = true;
    motorHoldState.button = button;
    button.classList.add('holding');
    
    // Immediate first move
    moveMotor(direction, size);
    
    // Continue moving while held (reduced interval for better responsiveness)
    motorHoldState.interval = setInterval(() => {
        if (motorHoldState.holding) {
            moveMotor(direction, size);
        }
    }, 100); // Faster interval for snappier response
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
    setButtonProcessing(btn, true);
    
    const result = await apiCall('advance_frame');
    
    setButtonProcessing(btn, false);
    
    if (!result.success) {
        alert('Cannot advance frame. Calibrate first.');
    }
}

async function backupFrame() {
    const btn = event.target;
    setButtonProcessing(btn, true);
    
    const result = await apiCall('backup_frame');
    
    setButtonProcessing(btn, false);
    
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

async function testCapture() {
    const btn = event.target;
    setButtonProcessing(btn, true);
    
    const result = await apiCall('test_capture');
    
    setButtonProcessing(btn, false);
    
    if (result.success) {
        alert('✓ Test capture successful!\n\nCamera is working. Check camera SD card for test image.\n\n(Frame count was NOT incremented)');
    } else {
        alert('✗ Test capture failed\n\n' + (result.message || 'Check console for details'));
    }
}

async function capture() {
    const btn = event.target;
    setButtonProcessing(btn, true);
    
    const result = await apiCall('capture');
    
    setButtonProcessing(btn, false);
    
    if (!result.success) {
        alert(result.message || 'Capture failed');
    }
    
    // Auto-refresh preview after capture if enabled
    if (previewState.autoRefresh) {
        setTimeout(() => capturePreview(), 500);
    }
}

// Camera Preview Functions
async function capturePreview() {
    const btn = document.getElementById('preview-btn');
    setButtonProcessing(btn, true);
    
    const result = await apiCall('get_preview');
    
    setButtonProcessing(btn, false);
    
    if (result.success && result.image) {
        const previewImg = document.getElementById('preview-image');
        const previewContainer = document.getElementById('preview-container');
        const timestamp = document.getElementById('preview-timestamp');
        
        previewImg.src = 'data:image/jpeg;base64,' + result.image;
        previewContainer.style.display = 'block';
        
        const now = new Date();
        timestamp.textContent = 'Updated at ' + now.toLocaleTimeString();
    } else {
        alert('Failed to get preview: ' + (result.message || 'Unknown error'));
    }
}

// Auto-refresh preview
function toggleAutoRefresh() {
    const checkbox = document.getElementById('auto-refresh-toggle');
    previewState.autoRefresh = checkbox.checked;
    
    if (previewState.autoRefresh) {
        startAutoRefresh();
    } else {
        stopAutoRefresh();
    }
}

function startAutoRefresh() {
    stopAutoRefresh(); // Clear any existing timer
    
    previewState.refreshTimer = setInterval(() => {
        if (previewState.autoRefresh) {
            capturePreview();
        }
    }, previewState.refreshInterval);
    
    // Get initial preview
    capturePreview();
}

function stopAutoRefresh() {
    if (previewState.refreshTimer) {
        clearInterval(previewState.refreshTimer);
        previewState.refreshTimer = null;
    }
}

// Update refresh interval display
document.getElementById('refresh-interval')?.addEventListener('input', (e) => {
    previewState.refreshInterval = parseInt(e.target.value);
    document.getElementById('refresh-interval-display').textContent = previewState.refreshInterval + ' ms';
    
    // Restart auto-refresh if active
    if (previewState.autoRefresh) {
        startAutoRefresh();
    }
});

// Settings Functions
async function updateStepSizes() {
    const fineStep = parseInt(document.getElementById('fine-step-input').value);
    const coarseStep = parseInt(document.getElementById('coarse-step-input').value);
    
    if (fineStep < 1 || coarseStep < 1) {
        alert('Step sizes must be at least 1');
        return;
    }
    
    settingsState.fineStep = fineStep;
    settingsState.coarseStep = coarseStep;
    
    const result = await apiCall('update_step_sizes', {
        fine_step: fineStep,
        coarse_step: coarseStep
    });
    
    if (result.success) {
        alert('Step sizes updated successfully!');
    } else {
        alert('Failed to update step sizes: ' + (result.message || 'Unknown error'));
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
    setButtonProcessing(btn, true);
    
    const result = await apiCall('calibrate', { action: 'capture_frame1' });
    
    setButtonProcessing(btn, false);
    
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
    setButtonProcessing(btn, true);
    
    const result = await apiCall('calibrate', { 
        action: 'capture_frame2',
        frame1_pos: calibrationState.frame1Position
    });
    
    setButtonProcessing(btn, false);
    
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
    setButtonProcessing(btn, true);
    
    // Start the new strip first
    await apiCall('new_strip', { action: 'start' });
    
    // Then capture the first frame
    const result = await apiCall('new_strip', { action: 'capture_first' });
    
    setButtonProcessing(btn, false);
    
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
        case 'p':
        case 'P':
            e.preventDefault();
            capturePreview();
            break;
    }
});

// Optimized status updates - less frequent for better performance
setInterval(() => {
    socket.emit('request_status');
}, 2000); // Every 2 seconds instead of 1

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
        
        // Mouse events (desktop) - with passive false for better control
        button.addEventListener('mousedown', (e) => {
            e.preventDefault();
            startMotorHold(button, direction, size);
        }, { passive: false });
        
        button.addEventListener('mouseup', (e) => {
            e.preventDefault();
            stopMotorHold();
        }, { passive: false });
        
        button.addEventListener('mouseleave', (e) => {
            stopMotorHold();
        });
        
        // Touch events (mobile) - with passive false for better responsiveness
        button.addEventListener('touchstart', (e) => {
            e.preventDefault();
            startMotorHold(button, direction, size);
        }, { passive: false });
        
        button.addEventListener('touchend', (e) => {
            e.preventDefault();
            stopMotorHold();
        }, { passive: false });
        
        button.addEventListener('touchcancel', (e) => {
            e.preventDefault();
            stopMotorHold();
        }, { passive: false });
    });
    
    // Global safety: stop on any mouse/touch up anywhere on page
    document.addEventListener('mouseup', () => {
        stopMotorHold();
    });
    
    document.addEventListener('touchend', () => {
        stopMotorHold();
    });
});
