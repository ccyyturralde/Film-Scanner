/**
 * Canon Camera WebUSB Controller
 * 
 * Uses WebUSB API to directly control Canon cameras via PTP protocol
 * No server-side code needed - all runs in the browser!
 * 
 * Supported: Chrome, Edge, Opera (browsers with WebUSB support)
 */

class CanonWebUSBCamera {
    constructor() {
        this.device = null;
        this.sessionId = null;
        this.transactionId = 1;
        this.connected = false;
        this.cameraModel = 'Unknown';
        
        // Canon vendor ID
        this.CANON_VENDOR_ID = 0x04a9;
        
        // PTP Operation Codes (subset needed for basic control)
        this.PTP_OC = {
            GetDeviceInfo: 0x1001,
            OpenSession: 0x1002,
            CloseSession: 0x1003,
            InitiateCapture: 0x100E,
            GetStorageIDs: 0x1004,
            GetObjectHandles: 0x1007,
            GetObject: 0x1009,
            // Canon-specific extensions
            EOS_SetRemoteMode: 0x9114,
            EOS_SetEventMode: 0x9115,
            EOS_RemoteRelease: 0x9128,
            EOS_RemoteReleaseOn: 0x9128,
            EOS_RemoteReleaseOff: 0x9129,
            EOS_DoAf: 0x9155,
            EOS_DriveLens: 0x9155,
            EOS_GetLiveViewPicture: 0x9153,
            EOS_SetLiveViewMode: 0x9151
        };
        
        // PTP Response Codes
        this.PTP_RC = {
            OK: 0x2001,
            GeneralError: 0x2002,
            SessionAlreadyOpen: 0x201E,
            InvalidParameter: 0x201D
        };
    }
    
    /**
     * Check if WebUSB is supported in this browser
     */
    static isSupported() {
        return 'usb' in navigator;
    }
    
    /**
     * Request user to select camera and grant permission
     */
    async requestDevice() {
        try {
            console.log('🔌 Requesting USB device...');
            
            // Request device with Canon filter
            this.device = await navigator.usb.requestDevice({
                filters: [
                    { vendorId: this.CANON_VENDOR_ID }
                ]
            });
            
            console.log('✓ Device selected:', this.device.productName);
            return this.device;
            
        } catch (error) {
            console.error('❌ Failed to request device:', error);
            throw new Error('Camera selection cancelled or failed');
        }
    }
    
    /**
     * Connect to previously authorized device
     */
    async connectToAuthorizedDevice() {
        try {
            const devices = await navigator.usb.getDevices();
            const canonDevices = devices.filter(d => d.vendorId === this.CANON_VENDOR_ID);
            
            if (canonDevices.length === 0) {
                throw new Error('No authorized Canon cameras found');
            }
            
            this.device = canonDevices[0];
            console.log('✓ Found authorized device:', this.device.productName);
            return this.device;
            
        } catch (error) {
            console.error('❌ Failed to connect to authorized device:', error);
            throw error;
        }
    }
    
    /**
     * Open connection to camera
     */
    async connect() {
        try {
            if (!this.device) {
                throw new Error('No device selected');
            }
            
            console.log('📷 Opening camera connection...');
            
            // Open device
            await this.device.open();
            console.log('  • Device opened');
            
            // Select configuration
            if (this.device.configuration === null) {
                await this.device.selectConfiguration(1);
                console.log('  • Configuration selected');
            }
            
            // Claim interface (usually interface 0 for PTP)
            await this.device.claimInterface(0);
            console.log('  • Interface claimed');
            
            // Open PTP session
            const sessionOpened = await this.openSession();
            if (!sessionOpened) {
                throw new Error('Failed to open PTP session');
            }
            
            // Get device info
            await this.getDeviceInfo();
            
            // Set Canon EOS remote mode
            await this.setEOSRemoteMode();
            
            this.connected = true;
            console.log('✓ Camera connected successfully!');
            
            return true;
            
        } catch (error) {
            console.error('❌ Connection failed:', error);
            this.connected = false;
            throw error;
        }
    }
    
    /**
     * Disconnect from camera
     */
    async disconnect() {
        try {
            if (!this.device) return;
            
            console.log('👋 Disconnecting camera...');
            
            // Close PTP session
            if (this.sessionId) {
                await this.closeSession();
            }
            
            // Release interface
            try {
                await this.device.releaseInterface(0);
            } catch (e) {
                // Ignore if already released
            }
            
            // Close device
            await this.device.close();
            
            this.device = null;
            this.sessionId = null;
            this.connected = false;
            
            console.log('✓ Camera disconnected');
            
        } catch (error) {
            console.error('❌ Disconnect error:', error);
        }
    }
    
    /**
     * Send PTP command to camera
     */
    async sendPTPCommand(opCode, params = []) {
        if (!this.device) {
            throw new Error('Device not connected');
        }
        
        const transactionId = this.transactionId++;
        
        // Build PTP command packet
        const packet = this.buildPTPCommandPacket(opCode, transactionId, params);
        
        // Send command (bulk out endpoint, usually endpoint 1 or 2)
        const endpointOut = 0x02;  // Typical bulk out endpoint
        await this.device.transferOut(endpointOut, packet);
        
        // Read response
        const endpointIn = 0x81;  // Typical bulk in endpoint
        const response = await this.device.transferIn(endpointIn, 512);
        
        return this.parsePTPResponse(response.data);
    }
    
    /**
     * Build PTP command packet
     */
    buildPTPCommandPacket(opCode, transactionId, params) {
        const paramCount = params.length;
        const packetSize = 12 + (paramCount * 4);
        
        const buffer = new ArrayBuffer(packetSize);
        const view = new DataView(buffer);
        
        // Packet structure:
        // 0-3: Length (little endian)
        // 4-5: Packet type (0x0001 for command)
        // 6-7: Operation code
        // 8-11: Transaction ID
        // 12+: Parameters (optional, 4 bytes each)
        
        view.setUint32(0, packetSize, true);  // Length
        view.setUint16(4, 0x0001, true);      // Command packet type
        view.setUint16(6, opCode, true);      // Operation code
        view.setUint32(8, transactionId, true); // Transaction ID
        
        // Add parameters
        for (let i = 0; i < paramCount; i++) {
            view.setUint32(12 + (i * 4), params[i], true);
        }
        
        return buffer;
    }
    
    /**
     * Parse PTP response packet
     */
    parsePTPResponse(dataView) {
        if (!dataView || dataView.byteLength < 12) {
            return { success: false, code: 0x2002 }; // General error
        }
        
        const length = dataView.getUint32(0, true);
        const packetType = dataView.getUint16(4, true);
        const responseCode = dataView.getUint16(6, true);
        const transactionId = dataView.getUint32(8, true);
        
        return {
            success: responseCode === this.PTP_RC.OK,
            code: responseCode,
            transactionId: transactionId,
            length: length,
            packetType: packetType
        };
    }
    
    /**
     * Open PTP session
     */
    async openSession() {
        try {
            console.log('  • Opening PTP session...');
            this.sessionId = Math.floor(Math.random() * 0xFFFFFFFF);
            
            const response = await this.sendPTPCommand(
                this.PTP_OC.OpenSession,
                [this.sessionId]
            );
            
            if (response.success || response.code === this.PTP_RC.SessionAlreadyOpen) {
                console.log('  • PTP session opened');
                return true;
            }
            
            console.error('  • Failed to open session:', response.code);
            return false;
            
        } catch (error) {
            console.error('  • Session open error:', error);
            return false;
        }
    }
    
    /**
     * Close PTP session
     */
    async closeSession() {
        try {
            if (!this.sessionId) return;
            
            await this.sendPTPCommand(this.PTP_OC.CloseSession, []);
            this.sessionId = null;
            
        } catch (error) {
            console.error('Session close error:', error);
        }
    }
    
    /**
     * Get device info
     */
    async getDeviceInfo() {
        try {
            const response = await this.sendPTPCommand(this.PTP_OC.GetDeviceInfo, []);
            
            if (response.success) {
                // Device info parsing would go here
                // For now, use the USB product name
                this.cameraModel = this.device.productName || 'Canon Camera';
                console.log('  • Camera model:', this.cameraModel);
            }
            
        } catch (error) {
            console.error('Failed to get device info:', error);
        }
    }
    
    /**
     * Set EOS remote mode (Canon specific)
     */
    async setEOSRemoteMode() {
        try {
            console.log('  • Setting Canon EOS remote mode...');
            await this.sendPTPCommand(this.PTP_OC.EOS_SetRemoteMode, [1]);
            await this.sendPTPCommand(this.PTP_OC.EOS_SetEventMode, [1]);
            console.log('  • Remote mode enabled');
        } catch (error) {
            console.log('  • Remote mode command failed (may not be needed):', error);
        }
    }
    
    /**
     * Trigger autofocus
     */
    async autofocus() {
        try {
            console.log('📷 Triggering autofocus...');
            
            // Canon EOS AF command
            const response = await this.sendPTPCommand(this.PTP_OC.EOS_DoAf, []);
            
            if (response.success) {
                console.log('✓ Autofocus triggered');
                return true;
            } else {
                console.error('✗ Autofocus failed:', response.code);
                return false;
            }
            
        } catch (error) {
            console.error('❌ Autofocus error:', error);
            return false;
        }
    }
    
    /**
     * Capture image
     */
    async capture() {
        try {
            console.log('📷 Capturing image...');
            
            // Method 1: Canon EOS remote release (full press)
            let response = await this.sendPTPCommand(this.PTP_OC.EOS_RemoteReleaseOn, [3]); // 3 = full press
            
            if (response.success) {
                // Wait a moment for camera to capture
                await new Promise(resolve => setTimeout(resolve, 500));
                
                // Release shutter
                await this.sendPTPCommand(this.PTP_OC.EOS_RemoteReleaseOff, [3]);
                
                console.log('✓ Image captured');
                return true;
            }
            
            // Method 2: Fallback to standard PTP capture
            response = await this.sendPTPCommand(this.PTP_OC.InitiateCapture, [0, 0]);
            
            if (response.success) {
                console.log('✓ Image captured (standard PTP)');
                return true;
            } else {
                console.error('✗ Capture failed:', response.code);
                return false;
            }
            
        } catch (error) {
            console.error('❌ Capture error:', error);
            return false;
        }
    }
    
    /**
     * Get camera status
     */
    getStatus() {
        return {
            connected: this.connected,
            model: this.cameraModel,
            sessionId: this.sessionId
        };
    }
}

// Make available globally
window.CanonWebUSBCamera = CanonWebUSBCamera;


