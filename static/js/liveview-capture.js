/**
 * Live View Capture via Screen Capture API
 * 
 * Captures EOS Utility (or other camera software) window
 * for smooth live view without accessing camera USB directly
 */

class LiveViewCapture {
    constructor() {
        this.stream = null;
        this.videoElement = null;
        this.canvas = null;
        this.captureInterval = null;
        this.onFrameCallback = null;
        this.isCapturing = false;
    }
    
    /**
     * Check if Screen Capture API is supported
     */
    static isSupported() {
        return 'mediaDevices' in navigator && 'getDisplayMedia' in navigator.mediaDevices;
    }
    
    /**
     * Request user to share EOS Utility (or other camera app) window
     */
    async requestWindowShare() {
        try {
            console.log('🖥️  Requesting window share...');
            
            // Request screen/window sharing
            this.stream = await navigator.mediaDevices.getDisplayMedia({
                video: {
                    cursor: 'never',  // Don't show mouse cursor
                    displaySurface: 'window'  // Prefer window over full screen
                },
                audio: false
            });
            
            console.log('✓ Window share granted');
            return true;
            
        } catch (error) {
            console.error('❌ Window share denied or failed:', error);
            return false;
        }
    }
    
    /**
     * Start capturing frames from shared window
     */
    async startCapture(videoElement, onFrameCallback) {
        try {
            if (!this.stream) {
                throw new Error('No stream available. Call requestWindowShare() first');
            }
            
            this.videoElement = videoElement;
            this.onFrameCallback = onFrameCallback;
            
            // Set video element source to the capture stream
            this.videoElement.srcObject = this.stream;
            await this.videoElement.play();
            
            // Create canvas for frame extraction
            this.canvas = document.createElement('canvas');
            this.canvas.width = this.videoElement.videoWidth || 1280;
            this.canvas.height = this.videoElement.videoHeight || 720;
            
            this.isCapturing = true;
            
            // Start frame capture loop
            this.captureLoop();
            
            console.log('✓ Live view capture started');
            return true;
            
        } catch (error) {
            console.error('❌ Failed to start capture:', error);
            return false;
        }
    }
    
    /**
     * Internal frame capture loop
     */
    captureLoop() {
        if (!this.isCapturing) return;
        
        try {
            // Update canvas size if video dimensions changed
            if (this.videoElement.videoWidth !== this.canvas.width) {
                this.canvas.width = this.videoElement.videoWidth;
                this.canvas.height = this.videoElement.videoHeight;
            }
            
            // Draw current video frame to canvas
            const ctx = this.canvas.getContext('2d');
            ctx.drawImage(this.videoElement, 0, 0, this.canvas.width, this.canvas.height);
            
            // Get frame as JPEG blob
            this.canvas.toBlob((blob) => {
                if (blob && this.onFrameCallback) {
                    this.onFrameCallback(blob);
                }
            }, 'image/jpeg', 0.85);
            
        } catch (error) {
            console.error('Frame capture error:', error);
        }
        
        // Continue loop (~10 FPS)
        setTimeout(() => this.captureLoop(), 100);
    }
    
    /**
     * Stop capturing frames
     */
    stopCapture() {
        this.isCapturing = false;
        
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        
        if (this.videoElement) {
            this.videoElement.srcObject = null;
        }
        
        console.log('✓ Live view capture stopped');
    }
    
    /**
     * Check if currently capturing
     */
    get capturing() {
        return this.isCapturing;
    }
}

// Make available globally
window.LiveViewCapture = LiveViewCapture;


