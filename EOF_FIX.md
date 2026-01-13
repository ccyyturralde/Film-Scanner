# EOF Error Fix

## Problem
When starting the Film Scanner app non-interactively (via systemd service, subprocess, or SSH without TTY), you would get an **EOFError** because `config_manager.py` tried to call `input()` during first-time setup.

## Root Cause
- `web_app.py` calls `config_mgr.get_config()` on startup
- If no config file exists, it calls `interactive_setup()`
- `interactive_setup()` uses `input()` to prompt the user
- When running without a TTY, `input()` raises `EOFError`

## Solution
Modified `config_manager.py` to:

1. **Detect interactive mode**: Added `is_interactive()` method that checks:
   - If running under systemd (`SYSTEMD_EXEC_PID` env var)
   - If `TERM` is not set or is 'dumb'
   - If stdin and stdout are both TTYs
   - This catches systemd services, subprocesses, pipe redirection, etc.

2. **Auto-setup for non-interactive**: Added `auto_setup()` method that:
   - Detects if running on Raspberry Pi
   - Creates sensible default configuration without user input
   - On Pi: Uses local IP, hostname, and port 5000
   - Not on Pi: Uses localhost (127.0.0.1) for testing

3. **Fixed interactive setup for Pi**: Updated `interactive_setup()` to:
   - Immediately save config and return when on Raspberry Pi
   - No port prompt for Pi (uses default 5000)
   - Prevents any `input()` calls when on Pi

4. **Smart config loading**: Updated `get_config()` to:
   - Run interactive setup when TTY is available
   - Run auto-setup when no TTY (non-interactive)

## Testing

### On Raspberry Pi (SSH or touchscreen)
```bash
# Remove existing config to test
rm ~/.film_scanner/scanner_config.json

# Start the app - should auto-configure
python3 web_app.py
```

### On development machine
```bash
# Remove existing config
rm ~/.film_scanner/scanner_config.json

# Test interactive mode (should prompt)
python3 web_app.py

# Test non-interactive mode (should auto-configure)
echo "" | python3 web_app.py
```

### Via systemd service
```bash
sudo systemctl restart film-scanner-web
sudo systemctl status film-scanner-web
```

## Configuration File
The auto-generated config is saved to: `~/.film_scanner/scanner_config.json`

To run interactive setup manually:
```bash
python3 config_manager.py --setup
```

To reset and start over:
```bash
python3 config_manager.py --reset
# Or manually:
rm ~/.film_scanner/scanner_config.json
```

## Changes Made
- Modified `config_manager.py`:
  - Added `is_interactive()` method
  - Added `is_raspberry_pi()` method  
  - Added `auto_setup()` method
  - Updated `get_config()` to handle both interactive and non-interactive modes
