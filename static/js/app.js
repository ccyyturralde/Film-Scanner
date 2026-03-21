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
    refreshTimer: null,
    videoActive: false,
    crosshair: {
        xNorm: null,
        yNorm: null,
        visible: false
    }
};

let settingsState = {
    fineStep: 8,
    coarseStep: 192
};

let scannerState = {
    mode: '35mm',  // '35mm' or '120'
    autoAlignmentEnabled: true,
    autoCaptureEnabled: false,
    autoCaptureDelay: 3.0,
    isAutoCapturing: false  // Track if auto-capture loop is active
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
    // Update scanner mode state
    if (status.scanner_mode) {
        scannerState.mode = status.scanner_mode;
    }
    if (status.auto_alignment_enabled !== undefined) {
        scannerState.autoAlignmentEnabled = status.auto_alignment_enabled;
    }
    if (status.auto_capture_enabled !== undefined) {
        scannerState.autoCaptureEnabled = status.auto_capture_enabled;
    }
    if (status.auto_capture_delay !== undefined) {
        scannerState.autoCaptureDelay = status.auto_capture_delay;
    }
    
    // Handle scanner mode (35mm vs 120)
    const is120Mode = scannerState.mode === '120';
    
    // Update mode buttons
    const mode35mmBtn = document.getElementById('mode-35mm-btn');
    const mode120Btn = document.getElementById('mode-120-btn');
    const settingsMode35mm = document.getElementById('settings-mode-35mm');
    const settingsMode120 = document.getElementById('settings-mode-120');
    
    if (mode35mmBtn) mode35mmBtn.classList.toggle('active', !is120Mode);
    if (mode120Btn) mode120Btn.classList.toggle('active', is120Mode);
    if (settingsMode35mm) settingsMode35mm.classList.toggle('active', !is120Mode);
    if (settingsMode120) settingsMode120.classList.toggle('active', is120Mode);
    
    // Update title based on mode
    const appTitle = document.getElementById('app-title');
    if (appTitle) {
        appTitle.textContent = is120Mode ? '📷 120 Film Scanner' : '📷 35mm Film Scanner';
    }
    
    // Update scanner mode display
    const scannerModeDisplay = document.getElementById('scanner-mode-display');
    if (scannerModeDisplay) {
        scannerModeDisplay.textContent = `Mode: ${scannerState.mode}`;
    }
    
    // Hide/show Arduino-only elements based on scanner mode
    const arduinoOnlyElements = document.querySelectorAll('.arduino-only');
    arduinoOnlyElements.forEach(el => {
        el.style.display = is120Mode ? 'none' : '';
    });
    
    // Update auto-alignment toggle
    const autoAlignmentToggle = document.getElementById('auto-alignment-toggle');
    if (autoAlignmentToggle) {
        autoAlignmentToggle.checked = scannerState.autoAlignmentEnabled;
    }
    
    // Update auto-capture toggle (both locations)
    const autoCaptureToggle = document.getElementById('auto-capture-toggle');
    const autoCaptureSettingsToggle = document.getElementById('auto-capture-settings-toggle');
    if (autoCaptureToggle) {
        autoCaptureToggle.checked = scannerState.autoCaptureEnabled;
    }
    if (autoCaptureSettingsToggle) {
        autoCaptureSettingsToggle.checked = scannerState.autoCaptureEnabled;
    }

    // Update motor direction (reverse auto-advance) toggle
    const motorDirectionCheckbox = document.getElementById('motor-direction-reversed');
    if (motorDirectionCheckbox && status.motor_advance_reversed !== undefined) {
        motorDirectionCheckbox.checked = status.motor_advance_reversed;
    }
    
    // Update auto-capture delay display and input
    const autoCaptureDelayDisplay = document.getElementById('auto-capture-delay-value');
    const autoCaptureDelayInput = document.getElementById('auto-capture-delay-input');
    if (autoCaptureDelayDisplay) {
        autoCaptureDelayDisplay.textContent = scannerState.autoCaptureDelay.toFixed(1) + 's';
    }
    if (autoCaptureDelayInput) {
        autoCaptureDelayInput.value = scannerState.autoCaptureDelay;
    }
    
    // Connection status (only show Arduino status in 35mm mode)
    const arduinoStatus = document.getElementById('arduino-status');
    if (arduinoStatus) {
        arduinoStatus.className = status.arduino_connected ? 'status-badge connected' : 'status-badge disconnected';
        arduinoStatus.style.display = is120Mode ? 'none' : '';
    }
    document.getElementById('camera-status').className = 
        status.camera_connected ? 'status-badge connected' : 'status-badge disconnected';
    
    // Status values
    document.getElementById('frame-count').textContent = status.frame_count;
    document.getElementById('position').textContent = status.position;
    document.getElementById('status-msg').textContent = status.status_msg;
    const alignModeEl = document.getElementById('alignment-mode-display');
    if (alignModeEl && status.alignment_mode) {
        const modeLabel = status.alignment_mode === 'stream' ? 'Auto (Gap Detection)' : 'Auto (Sprocket Holes)';
        alignModeEl.textContent = `Mode: ${modeLabel}`;
    }
    
    // Auto-align controls (hidden in 120 mode via arduino-only class)
    const autoAlignBtn = document.getElementById('auto-align-btn');
    const autoAlignCheckbox = document.getElementById('auto-align-before-capture');
    const autoAlignCheckboxWrap = document.getElementById('auto-align-checkbox-wrapper');
    const isStreamMode = status.alignment_mode === 'stream' && !is120Mode;
    const alignEnabled = scannerState.autoAlignmentEnabled && !is120Mode;
    
    if (autoAlignBtn) autoAlignBtn.style.display = isStreamMode && alignEnabled ? 'inline-block' : 'none';
    if (autoAlignCheckboxWrap) autoAlignCheckboxWrap.style.display = isStreamMode ? 'inline-block' : 'none';
    if (autoAlignCheckbox) autoAlignCheckbox.disabled = !isStreamMode || !alignEnabled;
    
    // Auto-align status
    const alignText = document.getElementById('auto-align-status');
    if (alignText) {
        if (is120Mode) {
            alignText.textContent = 'Manual film feed mode';
        } else if (!scannerState.autoAlignmentEnabled) {
            alignText.textContent = 'Auto-alignment disabled';
        } else if (status.alignment_confidence > 0 && status.last_gap_px != null) {
            const conf = (status.alignment_confidence * 100).toFixed(0);
            const pxPerStep = (status.px_per_step && !isNaN(status.px_per_step)) ? status.px_per_step.toFixed(2) : 'n/a';
            alignText.textContent = `Gap px: ${status.last_gap_px} | Confidence: ${conf}% | px/step: ${pxPerStep}`;
        } else {
            alignText.textContent = 'Auto-align not run yet.';
        }
    }
    
    // Show/hide calibration and strip panels based on alignment mode (only in 35mm mode)
    // In "stream" (auto-align) mode, hide both - no calibration or strip management needed
    const calibrationPanel = document.getElementById('calibration-panel');
    const stripPanel = document.getElementById('strip-panel');
    
    if (is120Mode) {
        // 120 mode: Hide all calibration/strip panels
        if (calibrationPanel) calibrationPanel.style.display = 'none';
        if (stripPanel) stripPanel.style.display = 'none';
    } else if (isStreamMode) {
        // Auto-align mode: hide calibration and strip management entirely
        if (calibrationPanel) calibrationPanel.style.display = 'none';
        if (stripPanel) stripPanel.style.display = 'none';
    } else {
        // Calibration mode: show appropriate panel
        const needsCalibration = status.strip_count === 0;
        if (needsCalibration) {
            if (calibrationPanel) calibrationPanel.style.display = 'block';
            if (stripPanel) stripPanel.style.display = 'none';
        } else if (status.strip_count > 0) {
            if (calibrationPanel) calibrationPanel.style.display = 'none';
            if (stripPanel) stripPanel.style.display = 'block';
        } else {
            if (calibrationPanel) calibrationPanel.style.display = 'none';
            if (stripPanel) stripPanel.style.display = 'none';
        }
    }
}

// Logs
async function fetchLogs() {
    try {
        const result = await apiCall('logs', { limit: 200 });
        if (result.success && Array.isArray(result.logs)) {
            const el = document.getElementById('log-output');
            if (el) {
                el.textContent = result.logs.join('\n');
                el.scrollTop = el.scrollHeight;
            }
        }
    } catch (e) {
        // Ignore fetch errors to avoid spamming UI
    }
}

setInterval(fetchLogs, 1500);

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
        const out = await response.json().catch(() => ({}));
        if (!response.ok) {
            out.success = out.success ?? false;
            out.httpStatus = response.status;
        }
        return out;
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

async function triggerAutofocus() {
    const btn = event && event.target ? event.target : null;
    if (btn) setButtonProcessing(btn, true);
    const result = await apiCall('autofocus', {});
    if (btn) setButtonProcessing(btn, false);
    if (!result.success) {
        alert(result.message || 'Autofocus failed');
    } else {
        alert('Autofocus triggered');
    }
}

async function refreshCameraSettings() {
    const result = await apiCall('camera_settings', {});
    if (result.success && result.settings) {
        const s = result.settings;
        const ap = document.getElementById('cam-aperture');
        const iso = document.getElementById('cam-iso');
        const sh = document.getElementById('cam-shutter');
        if (ap) ap.textContent = s.aperture || 'n/a';
        if (iso) iso.textContent = s.iso || 'n/a';
        if (sh) sh.textContent = s.shutterspeed || 'n/a';
    } else {
        alert(result.message || 'Unable to read camera settings');
    }
}

let captureRequestInProgress = false;

async function capture() {
    if (captureRequestInProgress) {
        console.log('Capture: ignoring duplicate request (previous still in progress)');
        return;
    }
    const btn = event.target;
    setButtonProcessing(btn, true);
    captureRequestInProgress = true;

    try {
        const autoAlignCheckbox = document.getElementById('auto-align-before-capture');
        const result = await apiCall('capture', { auto_align: autoAlignCheckbox ? autoAlignCheckbox.checked : false });

        if (!result.success) {
            const msg = result.message || 'Capture failed';
            if (result.httpStatus === 409 || (msg && msg.indexOf('already in progress') !== -1)) {
                console.warn('Capture: ' + msg);
            } else {
                alert(msg);
            }
            return;
        }

    // Auto-refresh preview after capture if enabled
    if (previewState.autoRefresh) {
        setTimeout(() => capturePreview(), 500);
    }
    
        // If auto-capture is enabled, continue capturing automatically
        if (result.auto_capture_enabled && scannerState.autoCaptureEnabled) {
            scannerState.isAutoCapturing = true;
            updateAutoCaptureUI();
            // Delay before next capture so Pi can finish advance and settle
            setTimeout(() => {
                if (scannerState.isAutoCapturing) {
                    console.log('Auto-capture: triggering next frame');
                    capture();
                }
            }, 2000);
        } else {
            scannerState.isAutoCapturing = false;
            updateAutoCaptureUI();
        }
    } finally {
        setButtonProcessing(btn, false);
        captureRequestInProgress = false;
    }
}

function stopAutoCapture() {
    scannerState.isAutoCapturing = false;
    updateAutoCaptureUI();
    console.log('Auto-capture stopped by user');
}

function updateAutoCaptureUI() {
    const captureBtn = document.querySelector('button[onclick="capture()"]');
    const stopBtn = document.getElementById('stop-auto-capture-btn');
    
    if (scannerState.isAutoCapturing) {
        if (captureBtn) {
            captureBtn.disabled = true;
            captureBtn.textContent = '⏸️ Auto-Capturing...';
        }
        if (stopBtn) stopBtn.style.display = 'inline-block';
    } else {
        if (captureBtn) {
            captureBtn.disabled = false;
            captureBtn.textContent = '📸 Capture';
        }
        if (stopBtn) stopBtn.style.display = 'none';
    }
}

async function toggleAutoCapture() {
    const result = await apiCall('set_auto_capture', {});
    if (result.success) {
        scannerState.autoCaptureEnabled = result.auto_capture_enabled;
        console.log('Auto-capture:', scannerState.autoCaptureEnabled ? 'enabled' : 'disabled');
    }
}

async function setAutoCaptureDelay() {
    const input = document.getElementById('auto-capture-delay-input');
    if (!input) return;
    
    const delay = parseFloat(input.value);
    if (isNaN(delay) || delay < 1.0 || delay > 30.0) {
        alert('Delay must be between 1.0 and 30.0 seconds');
        return;
    }
    
    const result = await apiCall('set_auto_capture_delay', { delay: delay });
    if (result.success) {
        scannerState.autoCaptureDelay = result.auto_capture_delay;
        console.log('Auto-capture delay set to:', scannerState.autoCaptureDelay);
    } else {
        alert(result.message || 'Failed to set delay');
    }
}

// Camera Preview Functions
async function capturePreview() {
    const btn = document.getElementById('preview-btn');
    setButtonProcessing(btn, true);
    
    const result = await apiCall('get_preview', { invert: previewState.inverted });
    
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

async function capturePreviewVideo() {
    const btn = document.getElementById('preview-video-btn');
    setButtonProcessing(btn, true);

    const result = await apiCall('get_preview_video', { invert: previewState.inverted });

    setButtonProcessing(btn, false);

    if (result.success && result.image) {
        const previewImg = document.getElementById('preview-image');
        const previewContainer = document.getElementById('preview-container');
        const timestamp = document.getElementById('preview-timestamp');

        previewImg.src = 'data:image/jpeg;base64,' + result.image;
        previewContainer.style.display = 'block';

        const now = new Date();
        timestamp.textContent = `Video frame at ${now.toLocaleTimeString()}`;
    } else {
        alert('Failed to get video frame: ' + (result.message || 'Unknown error'));
    }
}

function startVideoStream() {
    const streamImg = document.getElementById('preview-video-stream');
    const previewContainer = document.getElementById('preview-container');
    const timestamp = document.getElementById('preview-timestamp');
    const invertParam = previewState.inverted ? '1' : '0';
    // Stop auto-refresh of stills while streaming
    previewState.autoRefresh = false;
    const autoRefreshToggle = document.getElementById('auto-refresh-toggle');
    if (autoRefreshToggle) autoRefreshToggle.checked = false;
    stopAutoRefresh();

    // If stream fails to load (e.g. 503 - capture card not found), show message and allow retry
    streamImg.onerror = function() {
        previewState.videoActive = false;
        streamImg.src = '';
        streamImg.style.display = 'none';
        const stillImg = document.getElementById('preview-image');
        if (stillImg) stillImg.style.display = 'block';
        redrawPreviewCrosshair();
        if (timestamp) timestamp.textContent = 'Video preview unavailable. Checking...';
        // Get server message (triggers re-search for capture card)
        apiCall('get_preview_video', {}).then(function(result) {
            const msg = (result && !result.success && result.message)
                ? result.message
                : 'Capture card not found. Check USB connection and /dev/video* on the Pi, then try again.';
            if (timestamp) timestamp.textContent = msg;
            alert('Video preview failed: ' + msg);
        }).catch(function() {
            if (timestamp) timestamp.textContent = 'Capture card not found. Check USB and try Start Video Preview again.';
            alert('Video preview failed. Check capture card USB connection and try again.');
        });
    };

    // Show stream element, hide still image to avoid confusion
    const stillImg = document.getElementById('preview-image');
    if (stillImg) stillImg.style.display = 'none';
    streamImg.src = `/api/preview_video_stream?invert=${invertParam}&t=${Date.now()}`;
    streamImg.style.display = 'block';
    previewContainer.style.display = 'block';
    previewState.videoActive = true;
    redrawPreviewCrosshair();
    if (timestamp) timestamp.textContent = 'Video stream active...';
}

function getPreviewRGBRadius() {
    const radiusInput = document.getElementById('preview-rgb-radius');
    if (!radiusInput) return 2;
    const radius = parseInt(radiusInput.value, 10);
    if (Number.isNaN(radius)) return 2;
    return Math.max(0, Math.min(25, radius));
}

function getActivePreviewElement() {
    const streamImg = document.getElementById('preview-video-stream');
    const stillImg = document.getElementById('preview-image');
    if (previewState.videoActive && streamImg && streamImg.style.display !== 'none') {
        return streamImg;
    }
    return stillImg;
}

function hidePreviewCrosshair() {
    const crosshair = document.getElementById('preview-crosshair');
    if (!crosshair) return;
    crosshair.style.display = 'none';
    previewState.crosshair.visible = false;
}

function drawPreviewCrosshair(xNorm, yNorm) {
    const crosshair = document.getElementById('preview-crosshair');
    const imgEl = getActivePreviewElement();
    if (!crosshair || !imgEl) return;

    const rect = imgEl.getBoundingClientRect();
    const wrapperRect = (crosshair.parentElement || imgEl).getBoundingClientRect();
    if (!rect || rect.width <= 0 || rect.height <= 0) {
        hidePreviewCrosshair();
        return;
    }

    const clampedX = Math.max(0, Math.min(1, xNorm));
    const clampedY = Math.max(0, Math.min(1, yNorm));
    const xPx = rect.left - wrapperRect.left + (clampedX * rect.width);
    const yPx = rect.top - wrapperRect.top + (clampedY * rect.height);

    crosshair.style.left = `${xPx}px`;
    crosshair.style.top = `${yPx}px`;
    crosshair.style.display = 'block';

    previewState.crosshair.xNorm = clampedX;
    previewState.crosshair.yNorm = clampedY;
    previewState.crosshair.visible = true;
}

function redrawPreviewCrosshair() {
    if (!previewState.crosshair.visible) return;
    if (previewState.crosshair.xNorm == null || previewState.crosshair.yNorm == null) return;
    drawPreviewCrosshair(previewState.crosshair.xNorm, previewState.crosshair.yNorm);
}

function updatePreviewRGBReadout(result) {
    const readout = document.getElementById('preview-rgb-readout');
    const meta = document.getElementById('preview-rgb-meta');
    if (!readout || !meta) return;

    if (!result || !result.success || !result.rgb) {
        readout.textContent = 'R -, G -, B -';
        meta.textContent = (result && result.message) ? result.message : 'Sampling failed';
        return;
    }

    const r = result.rgb.r;
    const g = result.rgb.g;
    const b = result.rgb.b;
    readout.textContent = `R ${r}, G ${g}, B ${b}`;

    const px = result.pixel || {};
    const src = result.source || 'preview';
    meta.textContent = `${src} @ x:${px.x ?? '-'} y:${px.y ?? '-'}`;
}

async function samplePreviewRGBAtNormalized(xNorm, yNorm) {
    drawPreviewCrosshair(xNorm, yNorm);
    const result = await apiCall('preview_rgb', {
        x_norm: Math.max(0, Math.min(1, xNorm)),
        y_norm: Math.max(0, Math.min(1, yNorm)),
        radius: getPreviewRGBRadius(),
    });
    if (!(result && result.success)) {
        hidePreviewCrosshair();
    }
    updatePreviewRGBReadout(result);
}

function normalizedPointFromEvent(imgEl, evt) {
    if (!imgEl) return null;
    const rect = imgEl.getBoundingClientRect();
    if (!rect || rect.width <= 0 || rect.height <= 0) return null;

    let clientX = evt.clientX;
    let clientY = evt.clientY;
    if ((clientX === undefined || clientY === undefined) && evt.touches && evt.touches.length > 0) {
        clientX = evt.touches[0].clientX;
        clientY = evt.touches[0].clientY;
    }
    if (clientX === undefined || clientY === undefined) return null;

    const xNorm = (clientX - rect.left) / rect.width;
    const yNorm = (clientY - rect.top) / rect.height;
    return {
        x: Math.max(0, Math.min(1, xNorm)),
        y: Math.max(0, Math.min(1, yNorm)),
    };
}

function samplePreviewRGBFromEvent(evt) {
    const target = evt.currentTarget || evt.target;
    if (!target) return;
    const p = normalizedPointFromEvent(target, evt);
    if (!p) return;
    samplePreviewRGBAtNormalized(p.x, p.y);
}

function attachPreviewRGBSampling() {
    const stillImg = document.getElementById('preview-image');
    const streamImg = document.getElementById('preview-video-stream');

    if (stillImg) {
        stillImg.style.cursor = 'crosshair';
        stillImg.addEventListener('click', samplePreviewRGBFromEvent);
        stillImg.addEventListener('touchstart', samplePreviewRGBFromEvent, { passive: true });
        stillImg.addEventListener('load', redrawPreviewCrosshair);
    }
    if (streamImg) {
        streamImg.style.cursor = 'crosshair';
        streamImg.addEventListener('click', samplePreviewRGBFromEvent);
        streamImg.addEventListener('touchstart', samplePreviewRGBFromEvent, { passive: true });
        streamImg.addEventListener('load', redrawPreviewCrosshair);
    }
}

async function samplePreviewRGBAtCenter() {
    await samplePreviewRGBAtNormalized(0.5, 0.5);
}

function stopVideoStream() {
    const streamImg = document.getElementById('preview-video-stream');
    streamImg.src = '';
    streamImg.style.display = 'none';
    previewState.videoActive = false;
    const stillImg = document.getElementById('preview-image');
    if (stillImg) stillImg.style.display = 'block';
    redrawPreviewCrosshair();
}

async function restartVideoStreamIfFrozen() {
    const btn = document.getElementById('preview-video-restart-btn');
    if (btn) btn.disabled = true;
    const result = await apiCall('stream/restart', { full: true });
    if (btn) btn.disabled = false;
    if (!result.success) {
        alert('Restart failed: ' + (result.message || 'Unknown error'));
        return;
    }
    const timestamp = document.getElementById('preview-timestamp');
    if (timestamp) timestamp.textContent = result.message || 'Restarting...';
    // Server does full restart in background (~3s). Reload stream after delay so new connection gets fresh stream.
    if (previewState.videoActive) {
        const streamImg = document.getElementById('preview-video-stream');
        const invertParam = previewState.inverted ? '1' : '0';
        streamImg.src = '';
        setTimeout(() => {
            if (previewState.videoActive && streamImg) {
                streamImg.src = `/api/preview_video_stream?invert=${invertParam}&t=${Date.now()}`;
            }
            if (timestamp) timestamp.textContent = 'Preview restarted.';
        }, 3500);
    }
}

async function autoAlign() {
    const btn = event.target;
    setButtonProcessing(btn, true);

    const result = await apiCall('auto_align');

    setButtonProcessing(btn, false);

    if (!result.success) {
        alert('Auto-align failed: ' + (result.message || 'Unknown error'));
    } else {
        const info = result.info || {};
        const conf = info.confidence !== undefined ? (info.confidence * 100).toFixed(0) + '%' : 'n/a';
        alert(`Auto-align OK\nConfidence: ${conf}\nOffset px: ${info.offset_px ?? 'n/a'}`);
    }
}

async function setAlignmentMode(mode) {
    const result = await apiCall('set_alignment_mode', { mode });
    if (!result.success) {
        alert('Failed to set alignment mode: ' + (result.message || 'Unknown error'));
    } else {
        const alignModeEl = document.getElementById('alignment-mode-display');
        if (alignModeEl) {
            const modeLabel = result.alignment_mode === 'stream' ? 'Auto (Gap Detection)' : 'Auto (Sprocket Holes)';
            alignModeEl.textContent = `Mode: ${modeLabel}`;
        }
        // If switching back to stream and video preview active, restart stream to ensure viewfinder is on
        if (mode === 'stream' && previewState.videoActive) {
            startVideoStream();
        }
    }
}

async function setScannerMode(mode) {
    const result = await apiCall('set_scanner_mode', { mode });
    if (!result.success) {
        alert('Failed to set scanner mode: ' + (result.message || 'Unknown error'));
    } else {
        scannerState.mode = result.scanner_mode;
        // Request full status update to refresh UI
        socket.emit('request_status');
    }
}

async function toggleAutoAlignment() {
    const checkbox = document.getElementById('auto-alignment-toggle');
    const enabled = checkbox ? checkbox.checked : !scannerState.autoAlignmentEnabled;
    
    const result = await apiCall('set_auto_alignment', { enabled });
    if (!result.success) {
        alert('Failed to toggle auto-alignment: ' + (result.message || 'Unknown error'));
        // Revert checkbox on failure
        if (checkbox) checkbox.checked = scannerState.autoAlignmentEnabled;
    } else {
        scannerState.autoAlignmentEnabled = result.auto_alignment_enabled;
        // Request full status update to refresh UI
        socket.emit('request_status');
    }
}

async function setMotorDirectionReversed() {
    const checkbox = document.getElementById('motor-direction-reversed');
    const reversed = checkbox ? checkbox.checked : false;
    const result = await apiCall('motor_direction', { reversed });
    if (!result.success) {
        alert('Failed to set motor direction: ' + (result.message || 'Unknown error'));
        if (checkbox) checkbox.checked = !reversed;
    } else {
        socket.emit('request_status');
    }
}

async function setFrameMode(mode) {
    const btn = event && event.target;
    if (btn) setButtonProcessing(btn, true);
    const result = await apiCall('set_frame_mode', { mode });
    if (btn) setButtonProcessing(btn, false);
    if (!result.success) {
        alert('Failed to set frame mode: ' + (result.message || 'Unknown error'));
        return;
    }
    const frameModeEl = document.getElementById('frame-mode-display');
    if (frameModeEl && result.frame_mode) {
        frameModeEl.textContent = `Frame: ${result.frame_mode.toUpperCase()}`;
    }
}

function togglePreviewInvert() {
    const checkbox = document.getElementById('preview-invert-toggle');
    previewState.inverted = (checkbox && checkbox.checked) || false;
    // Restart video stream with new invert state if active
    if (previewState.videoActive) {
        startVideoStream();
    }
}

function toggleAutoRefresh() {
    const checkbox = document.getElementById('auto-refresh-toggle');
    previewState.autoRefresh = checkbox.checked;

    // If streaming, don't auto-refresh stills
    if (previewState.videoActive && previewState.autoRefresh) {
        previewState.autoRefresh = false;
        checkbox.checked = false;
        return;
    }

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
const refreshIntervalEl = document.getElementById('refresh-interval');
if (refreshIntervalEl) {
    refreshIntervalEl.addEventListener('input', (e) => {
        previewState.refreshInterval = parseInt(e.target.value);
        const displayEl = document.getElementById('refresh-interval-display');
        if (displayEl) displayEl.textContent = previewState.refreshInterval + ' ms';
        
        // Restart auto-refresh if active
        if (previewState.autoRefresh) {
            startAutoRefresh();
        }
    });
}

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
    // Best-effort fetch camera settings on load (non-blocking)
    refreshCameraSettings();
    fetchLogs();
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

// ============================================================================
// ScanLight RGB Backlight Control
// ============================================================================

let scanlightState = {
    connected: false,
    rgb: { r: 255, g: 255, b: 255 },
    profiles: {},
    currentProfile: 'Color'
};

function updateScanlightVisibility() {
    const controls = document.getElementById('scanlight-controls');
    const disconnectedNote = document.getElementById('scanlight-disconnected-note');
    if (controls) {
        controls.style.display = scanlightState.connected ? 'block' : 'none';
    }
    if (disconnectedNote) {
        disconnectedNote.style.display = scanlightState.connected ? 'none' : 'block';
    }
}

// Fetch ScanLight status on page load
async function fetchScanlightStatus() {
    try {
        const response = await fetch('/api/scanlight/status');
        const data = await response.json();
        
        if (data.success) {
            scanlightState.connected = data.connected;
            scanlightState.rgb = data.rgb || { r: 255, g: 255, b: 255 };
            scanlightState.profiles = data.profiles || {};
            scanlightState.currentProfile = data.current_profile || 'Color';
            
            updateScanlightUI();
            updateScanlightProfileList();
            updateScanlightVisibility();
        }
    } catch (error) {
        console.error('Error fetching ScanLight status:', error);
    }
}

// Update ScanLight RGB sliders and preview
function updateScanlightUI() {
    const { r, g, b } = scanlightState.rgb;
    
    // Update sliders
    document.getElementById('scanlight-r-slider').value = r;
    document.getElementById('scanlight-g-slider').value = g;
    document.getElementById('scanlight-b-slider').value = b;
    
    // Update value displays
    document.getElementById('scanlight-r-value').textContent = r;
    document.getElementById('scanlight-g-value').textContent = g;
    document.getElementById('scanlight-b-value').textContent = b;
    
    // Update preview box
    document.getElementById('scanlight-color-preview').style.background = `rgb(${r}, ${g}, ${b})`;
    document.getElementById('scanlight-rgb-text').textContent = `RGB(${r}, ${g}, ${b})`;
    
    // Update connection status
    const statusEl = document.getElementById('scanlight-connection-status');
    if (statusEl) {
        statusEl.textContent = scanlightState.connected ? 'Connected' : 'Disconnected';
        statusEl.className = scanlightState.connected ? 'status-badge connected' : 'status-badge disconnected';
    }
    updateScanlightVisibility();
}

// Update profile dropdown list
function updateScanlightProfileList() {
    const select = document.getElementById('scanlight-profile-select');
    if (!select) return;
    
    // Clear existing options except first
    select.innerHTML = '<option value="">-- Select Profile --</option>';
    
    // Add all profiles
    Object.keys(scanlightState.profiles).forEach(name => {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        if (name === scanlightState.currentProfile) {
            option.selected = true;
        }
        select.appendChild(option);
    });
}

// Debounce helper for performance optimization
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Update RGB values from sliders (optimized with debouncing)
async function updateScanlightRGB() {
    const r = parseInt(document.getElementById('scanlight-r-slider').value);
    const g = parseInt(document.getElementById('scanlight-g-slider').value);
    const b = parseInt(document.getElementById('scanlight-b-slider').value);
    
    // Update local state and UI immediately for responsiveness
    scanlightState.rgb = { r, g, b };
    updateScanlightUI();
    
    // Debounced backend update (only send after user stops moving slider)
    debouncedUpdateScanlightBackend(r, g, b);
}

// Debounced backend update (300ms delay)
const debouncedUpdateScanlightBackend = debounce(async (r, g, b) => {
    try {
        const response = await fetch('/api/scanlight/set_rgb', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ r, g, b })
        });
        
        const data = await response.json();
        if (data.success) {
            scanlightState.connected = data.connected;
            scanlightState.rgb = data.rgb;
        } else {
            console.error('ScanLight error:', data.message);
        }
    } catch (error) {
        console.error('Error setting ScanLight RGB:', error);
    }
}, 300);

// Save current RGB as a profile
async function saveScanlightProfile() {
    const nameInput = document.getElementById('scanlight-profile-name');
    const name = nameInput.value.trim();
    
    if (!name) {
        alert('Please enter a profile name');
        return;
    }
    
    try {
        const response = await fetch('/api/scanlight/save_profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                description: `Custom profile: RGB(${scanlightState.rgb.r}, ${scanlightState.rgb.g}, ${scanlightState.rgb.b})`
            })
        });
        
        const data = await response.json();
        if (data.success) {
            scanlightState.profiles = data.profiles;
            scanlightState.currentProfile = name;
            updateScanlightProfileList();
            alert(`Profile "${name}" saved`);
            nameInput.value = '';
        } else {
            alert('Failed to save profile: ' + (data.message || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error saving ScanLight profile:', error);
        alert('Failed to save profile');
    }
}

// Load a saved profile
async function loadScanlightProfile() {
    const select = document.getElementById('scanlight-profile-select');
    const name = select.value;
    
    if (!name) {
        alert('Please select a profile');
        return;
    }
    
    try {
        const response = await fetch('/api/scanlight/load_profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        
        const data = await response.json();
        if (data.success) {
            scanlightState.rgb = data.rgb;
            scanlightState.currentProfile = data.current_profile;
            updateScanlightUI();
        } else {
            alert('Failed to load profile: ' + (data.message || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error loading ScanLight profile:', error);
        alert('Failed to load profile');
    }
}

// Delete a saved profile
async function deleteScanlightProfile() {
    const select = document.getElementById('scanlight-profile-select');
    const name = select.value;
    
    if (!name) {
        alert('Please select a profile to delete');
        return;
    }
    
    if (name === 'Color' || name === 'B&W') {
        alert('Cannot delete default profiles');
        return;
    }
    
    if (!confirm(`Delete profile "${name}"?`)) {
        return;
    }
    
    try {
        const response = await fetch('/api/scanlight/delete_profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        
        const data = await response.json();
        if (data.success) {
            scanlightState.profiles = data.profiles;
            updateScanlightProfileList();
            alert(`Profile "${name}" deleted`);
        } else {
            alert('Failed to delete profile: ' + (data.message || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error deleting ScanLight profile:', error);
        alert('Failed to delete profile');
    }
}

// Initialize ScanLight on page load
window.addEventListener('load', () => {
    attachPreviewRGBSampling();
    fetchScanlightStatus();
    window.addEventListener('resize', redrawPreviewCrosshair);
});
