# Migration Guide: Terminal → Web Version

This guide helps you transition from the terminal-based scanner to the web version.

## What Stays the Same ✅

- **Hardware setup** - Same Arduino, same camera, same motor
- **Calibration process** - Still learn frame spacing on Strip 1
- **Workflow** - Calibrate → scan frames → new strip → repeat
- **State files** - Same JSON format, same location
- **Image storage** - Still saves to camera SD card
- **Frame advance logic** - Identical motor control

## What Changed 🔄

### Access Method
**Before:** 
```bash
ssh pi@raspberrypi.local
cd Film-Scanner
python scanner_app_v3.py
```

**Now:**
```
Open browser → http://raspberrypi.local:5000
```

### Interface
| Terminal | Web |
|----------|-----|
| Curses text UI | HTML visual UI |
| Arrow keys | Buttons or arrow keys |
| Text status | Visual badges |
| Single user | Multi-user viewing |

### Controls Mapping

| Terminal Key | Web Equivalent | Notes |
|-------------|----------------|-------|
| `N` | "New Roll" button | Type name in text box first |
| `C` | "Start Calibration" | Guided workflow |
| `S` | "Start New Strip" | Guided workflow |
| `SPACE` | "CAPTURE" button | Large green button |
| `←` `→` | "Fine Back/Forward" | Also arrow keys |
| `Shift+←` `Shift+→` | "Full Frame Back/Forward" | Dedicated buttons |
| `F` | "Autofocus" button | Also `F` key |
| `G` | "Toggle Step Size" | Also `G` key |
| `A` | "Toggle Auto-Advance" | Also `A` key |
| `M` | "Mode" button | Also `M` key |
| `Z` | "Zero Position" | Button only |
| `Q` | Close browser tab | No quit needed |

## Step-by-Step Migration

### 1. Install Web Version
```bash
# In your Film-Scanner directory
git checkout web-mobile-version
pip install -r requirements.txt
```

### 2. Test It Out
```bash
python web_app.py
```

Open browser to `http://localhost:5000`

### 3. Resume Existing Roll (Optional)

If you have a roll in progress:
1. Note your roll name from terminal version
2. In web version, click "New Roll"
3. Enter the EXACT same roll name
4. System will ask "Resume existing roll?"
5. Click "Yes"
6. All your progress is restored!

### 4. Use from Phone

Find your computer's IP:
```bash
# Linux/Mac
hostname -I
# or
ifconfig | grep inet

# Windows
ipconfig
```

On phone, go to: `http://[YOUR-IP]:5000`

Example: `http://192.168.1.100:5000`

## Common Questions

### Q: Can I still use the terminal version?
**A:** Yes! Switch branches:
```bash
git checkout main              # Terminal version
git checkout web-mobile-version  # Web version
```

### Q: Will my old scans work with the web version?
**A:** Yes! Same state file format, same directory structure.

### Q: Can I use both versions at the same time?
**A:** No - only one can control the Arduino at a time.

### Q: Do I need to recalibrate?
**A:** No! If resuming an existing roll, calibration data is preserved.

### Q: What about keyboard shortcuts?
**A:** Most work the same on desktop! Space, arrows, F, G, A, M all work.

### Q: Can multiple people control it?
**A:** Technically yes, but not recommended. Best for one operator, multiple viewers.

### Q: Does it work offline?
**A:** Server must be running, but no internet needed. Local network only.

### Q: My phone browser times out / screen turns off
**A:** Set your phone to "keep screen on" or increase screen timeout in settings.

### Q: Can I use it over the internet (away from home)?
**A:** Possible with port forwarding or VPN, but requires network setup. See README_WEB_APP.md.

## Troubleshooting Migration Issues

### "Arduino not found" in web version but worked in terminal
**Solution:**
```bash
# Check if terminal version is still running
ps aux | grep scanner_app
kill [PID]  # Kill the terminal version

# Check port permissions
sudo usermod -a -G dialout $USER
# Log out and back in
```

### Web page loads but controls don't work
**Check:**
1. Browser console for errors (F12)
2. WebSocket connected (should see green badges)
3. Flask server running without errors

### Can't access from phone
**Check:**
1. Phone on same WiFi network
2. Computer firewall allows port 5000
3. Using http:// not https://
4. Correct IP address

### State file not loading
**Verify:**
```bash
# Check state file exists
ls ~/scans/[DATE]/[ROLL-NAME]/.scan_state.json

# Check it's valid JSON
cat ~/scans/[DATE]/[ROLL-NAME]/.scan_state.json | python -m json.tool
```

## Performance Comparison

| Metric | Terminal | Web |
|--------|----------|-----|
| Startup time | ~2 sec | ~3 sec |
| Response to button | Instant | ~100ms |
| Camera capture | Same | Same |
| Motor move | Same | Same |
| CPU usage | Minimal | Minimal |
| Memory usage | ~20MB | ~50MB |
| Network | None | Local only |

## Learning Curve

**Terminal version:**
- Must remember key bindings
- SSH knowledge helpful
- Comfortable with command line

**Web version:**
- Visual/intuitive interface
- No SSH needed
- Point and click
- Easier for beginners

## When to Use Which Version

### Use Terminal Version When:
- SSH is already open
- You prefer keyboard-only control
- You like text interfaces
- Minimal resource usage critical

### Use Web Version When:
- You want mobile access
- Non-technical users need access
- Multiple people want to monitor progress
- You prefer visual interfaces
- You're away from computer (on couch, etc.)

## Example: Switching Mid-Roll

Let's say you started with terminal version:

```bash
# Terminal version - scan 10 frames
python scanner_app_v3.py
# ... scan frames 1-10 ...
# Press Q to quit
```

Now switch to web:
```bash
git checkout web-mobile-version
pip install -r requirements.txt
python web_app.py
```

In browser:
1. Click "New Roll"
2. Enter same roll name: "My Roll"
3. System detects existing state
4. Click "Resume"
5. Continue from frame 11!

## Cheat Sheet: Side-by-Side

```
TERMINAL VERSION              WEB VERSION
═══════════════════════════   ═══════════════════════════
ssh user@pi                   Open browser
cd Film-Scanner              Go to http://pi:5000
python scanner_app_v3.py     (Already running)
Press N                      Click "New Roll" button
Type roll name               Type roll name
Press C                      Click "Start Calibration"
Arrow keys to position       Click motor buttons or arrows
Press SPACE                  Click "CAPTURE" button
...scan frames...            ...scan frames...
Press S                      Click "Start New Strip"
Press Q                      Close browser tab
```

## Tips for Web Version Newcomers

1. **Add to Home Screen** (Mobile)
   - Safari: Share → Add to Home Screen
   - Chrome: Menu → Add to Home Screen
   - Launches like an app!

2. **Landscape Mode** (Tablet)
   - More controls visible at once
   - Better layout

3. **Status Always Visible**
   - No need to remember current state
   - Everything displayed at top

4. **Button Feedback**
   - Buttons show "processing" state
   - Visual confirmation of actions

5. **Real-time Updates**
   - Open on multiple devices
   - All show same status
   - Great for monitoring while multitasking

## Backup Your Data First! 

Before switching versions:
```bash
# Backup your scans folder
cp -r ~/scans ~/scans_backup_$(date +%Y%m%d)

# Your scans are safe - both versions use same format
```

## Need Help?

- **Quick Start**: See `QUICKSTART.md`
- **Full Docs**: See `README_WEB_APP.md`
- **Architecture**: See `ARCHITECTURE.md`
- **Terminal Version**: See `README.md`

---

**Welcome to the web version! Enjoy scanning from your couch! 🛋️📸**

