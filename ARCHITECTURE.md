# Web App Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENT DEVICES                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ Desktop  │  │  Tablet  │  │  Phone   │  │  Phone  │ │
│  │ Browser  │  │ Browser  │  │ Browser  │  │ Browser │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬────┘ │
│       │             │              │             │       │
│       └─────────────┴──────────────┴─────────────┘       │
│                          │                                │
│                 WebSocket + HTTP                          │
└──────────────────────────┼────────────────────────────────┘
                           │
┌──────────────────────────┼────────────────────────────────┐
│              FLASK WEB SERVER (Port 5000)                 │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Flask-SocketIO (Real-time Communication)          │  │
│  │  - Status updates                                  │  │
│  │  - Multi-client broadcast                          │  │
│  └────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────┐  │
│  │  REST API Endpoints                                │  │
│  │  - /api/capture, /api/move, /api/calibrate, etc.  │  │
│  └────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────┐  │
│  │  FilmScanner Class                                 │  │
│  │  - State management                                │  │
│  │  - Arduino communication                           │  │
│  │  - Camera control                                  │  │
│  └──────────┬──────────────────────────┬──────────────┘  │
└─────────────┼──────────────────────────┼─────────────────┘
              │                          │
        Serial (USB)              subprocess (gphoto2)
              │                          │
    ┌─────────┴──────────┐      ┌────────┴────────┐
    │     ARDUINO        │      │     CAMERA       │
    │  - Stepper motor   │      │  - DSLR/Mirrorless│
    │  - Film advance    │      │  - PTP mode      │
    └────────────────────┘      └──────────────────┘
```

## File Structure

```
Film-Scanner/
├── web_app.py                 # Flask backend server
├── requirements.txt           # Python dependencies
├── QUICKSTART.md             # Quick start guide
├── README_WEB_APP.md         # Full documentation
├── ARCHITECTURE.md           # This file
│
├── templates/                # HTML templates
│   └── index.html           # Main web interface
│
└── static/                   # Static assets
    ├── css/
    │   └── style.css        # Responsive styling
    └── js/
        └── app.js           # Frontend logic + WebSocket
```

## Communication Flow

### 1. Page Load
```
Browser → GET / → Flask → templates/index.html → Browser
Browser → Load static/css/style.css
Browser → Load static/js/app.js
Browser → Connect WebSocket
```

### 2. Real-Time Status Updates
```
Browser: socket.emit('request_status')
    ↓
Flask: Receives request
    ↓
Flask: Queries Arduino position, checks camera
    ↓
Flask: socket.emit('status_update', data)
    ↓
Browser: Updates UI (position, frame count, etc.)
```

### 3. User Action (e.g., Capture)
```
Browser: User clicks "CAPTURE" button
    ↓
Browser: POST /api/capture
    ↓
Flask: Validates (roll exists, camera connected)
    ↓
Flask: Auto-advance motor if enabled
    ↓
Flask: subprocess.run(['gphoto2', '--capture-image'])
    ↓
Flask: Updates frame_count, saves state
    ↓
Flask: Broadcasts status update to ALL clients
    ↓
All Browsers: Receive update, refresh UI
```

### 4. Motor Movement
```
Browser: User clicks "Fine Forward"
    ↓
Browser: POST /api/move {direction: 'forward', size: 'fine'}
    ↓
Flask: arduino.write(b'f\n')  # Send 'f' command
    ↓
Arduino: Moves stepper 8 steps forward
    ↓
Arduino: Returns new position
    ↓
Flask: Broadcasts position update
    ↓
All Browsers: Update position display
```

## Key Components

### Backend (web_app.py)

**FilmScanner Class**
- Maintains all state (position, frame count, calibration)
- Communicates with Arduino via pyserial
- Controls camera via gphoto2 subprocess calls
- Thread-safe with locks for concurrent access

**Flask Routes**
- `GET /` - Serve main page
- `POST /api/*` - Handle actions (capture, move, calibrate, etc.)
- Returns JSON responses

**WebSocket Events**
- `connect` - Send initial status when client connects
- `request_status` - Client requests status update
- `status_update` - Broadcast to all clients (server → clients)

### Frontend (templates/index.html + static/)

**HTML Structure**
- Status panel (roll, strip, frame, position)
- Motor controls (fine, coarse, full frame)
- Camera controls (focus, capture)
- Calibration workflow UI
- Strip management

**CSS (style.css)**
- CSS Grid for responsive layouts
- Mobile-first design
- Touch-friendly button sizes (min 44px)
- Dark theme optimized for dim scanning environment
- Viewport units for scaling

**JavaScript (app.js)**
- Socket.IO client for WebSocket
- Event handlers for all buttons
- Calibration state machine
- Strip workflow state machine
- Keyboard shortcut handling
- Real-time UI updates

## State Management

### Server-Side State
```python
{
    'roll_name': str,
    'frame_count': int,
    'strip_count': int,
    'frames_in_strip': int,
    'position': int,
    'frame_advance': int,  # Calibrated distance
    'mode': 'manual' | 'calibrated',
    'auto_advance': bool,
    'is_large_step': bool
}
```

Persisted to: `~/scans/YYYY-MM-DD/roll-name/.scan_state.json`

### Client-Side State
```javascript
{
    calibrationState: {
        active: bool,
        frame1Captured: bool,
        frame1Position: int
    },
    stripState: {
        active: bool,
        firstFrameCaptured: bool
    }
}
```

Only UI workflow state - actual data comes from server.

## Network Architecture

### Local Network Access
```
Phone (192.168.1.50)
  ↓ WiFi
Router (192.168.1.1)
  ↓ WiFi/Ethernet
Server (192.168.1.100:5000)
  ↓ USB
Arduino + Camera
```

### Port Configuration
- **5000** - Web server (HTTP + WebSocket)
- Configurable in web_app.py

### Security Considerations
- ⚠️ No authentication implemented
- Assumes trusted local network
- All clients can control scanner
- Don't expose to public internet without adding auth

## Scalability

### Multiple Clients
- ✅ Multiple viewers supported
- ✅ All receive real-time updates
- ⚠️ No conflict resolution if multiple users send commands
- Recommended: One operator, multiple monitors

### Performance
- WebSocket reduces polling overhead
- Status broadcast only when changed
- Camera check cached for 5 seconds
- Minimal server resources needed

## Mobile Optimizations

### Responsive Breakpoints
- `< 640px` - Mobile portrait
- `< 900px landscape` - Mobile landscape
- `> 640px` - Tablet/Desktop

### Touch Optimizations
- Button min-size: 44×44px (Apple HIG guideline)
- Generous padding and gaps
- No hover states (touch has no hover)
- Active state feedback (scale down on tap)
- Disabled text selection on buttons

### Network Efficiency
- Single WebSocket connection
- Status updates only when changed
- Minimal JavaScript bundle (vanilla JS, no frameworks)
- CSS loaded once, cached

## Comparison to Terminal Version

| Aspect | Terminal | Web |
|--------|----------|-----|
| **UI Framework** | Python curses | HTML/CSS/JS |
| **Server** | None (direct) | Flask |
| **Communication** | Direct serial/subprocess | Proxy via Flask |
| **Clients** | 1 (terminal) | Unlimited browsers |
| **Real-time updates** | Local only | Broadcast to all |
| **Input** | Keyboard only | Touch + keyboard |
| **Accessibility** | SSH required | Browser only |
| **State display** | Text | Visual + icons |
| **Mobile support** | Poor (SSH on mobile) | Native |

## Development Workflow

### Testing Locally
```bash
python web_app.py
# Access at http://localhost:5000
```

### Testing on Mobile
1. Get computer IP: `ipconfig` / `ifconfig`
2. Start server: `python web_app.py`
3. On phone: `http://192.168.1.XXX:5000`

### Debugging
- Flask debug mode enabled
- Browser DevTools Console for JS errors
- Flask console for Python errors
- Network tab to inspect WebSocket traffic

## Future Enhancement Ideas

### Short-term
- [ ] Add authentication (username/password)
- [ ] Image gallery/preview
- [ ] Download images from camera automatically
- [ ] Progress indicators during long operations

### Medium-term
- [ ] PWA manifest for "Add to Home Screen"
- [ ] Offline capability (Service Worker)
- [ ] Push notifications for scan completion
- [ ] Statistics dashboard (scans per day, etc.)

### Long-term
- [ ] Multi-scanner support
- [ ] Cloud sync of scan metadata
- [ ] AI-powered frame detection
- [ ] Remote collaboration (share session URL)

## Dependencies

### Python Packages
- **Flask** (3.0.0) - Web framework
- **flask-socketio** (5.3.5) - WebSocket support
- **pyserial** (3.5) - Arduino communication
- **python-socketio** (5.10.0) - SocketIO protocol

### System Requirements
- **gphoto2** - Camera control (system package)
- **Python 3.7+** - Backend runtime
- **Modern browser** - Chrome/Safari/Firefox (WebSocket support)

### Frontend Libraries (CDN)
- **Socket.IO client** (4.5.4) - WebSocket client

## License
Same as main project.

---

**This architecture enables smooth, real-time control of the film scanner from any device on your network!** 🚀

