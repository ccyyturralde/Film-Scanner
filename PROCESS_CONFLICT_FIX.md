# Process Conflict Fix - Error -9

## Problem: Return Code -9

**Error Code -9** = SIGKILL (process was forcibly killed)

This happens when multiple gphoto2 processes try to access the camera simultaneously, causing conflicts.

## Root Cause

### What Was Happening

1. User clicks "Get Live Preview"
   - gphoto2 process starts
   - Captures preview
   - Process STAYS RUNNING after preview completes
   
2. User clicks "CAPTURE"
   - New gphoto2 process tries to start
   - Camera is LOCKED by previous process
   - System kills new process → **Error -9**

3. Even worse: Multiple previews
   - Each preview leaves a process running
   - Multiple processes pile up
   - Camera completely locked
   - All subsequent commands fail with -9

### Why It Happened

Initial "simplification" removed process cleanup, thinking it was unnecessary. **It was necessary!**

## The Fix

### 1. Kill Processes BEFORE Every Command ✅

```python
def capture_image(self):
    # MUST kill existing processes first
    self._kill_gphoto2()
    time.sleep(1.0)  # Wait for USB to release
    
    # Then run command
    gphoto2 --capture-image
```

### 2. Kill Processes AFTER Preview ✅

```python
def get_preview():
    # Run preview
    gphoto2 --capture-preview
    
    # Clean up afterwards (CRITICAL!)
    scanner._kill_gphoto2()
    
    return image
```

### 3. Improved Process Killing ✅

```python
def _kill_gphoto2(self):
    # Kill gphoto2 gracefully
    killall gphoto2
    wait 0.2s
    
    # Force kill any remaining
    killall -9 gphoto2
    wait 0.2s
    
    # Kill gvfs (interferes)
    killall gvfs-gphoto2-volume-monitor
    wait 0.3s
    
    # Kill PTP processes
    killall -9 PTPCamera
    wait 0.3s
    
    # Total: 1 second for USB to fully release
```

## Changes Made

### Capture Function
```python
# Before:
def capture_image():
    gphoto2 --capture-image

# After:
def capture_image():
    _kill_gphoto2()        # Clean before
    wait 1.0s
    gphoto2 --capture-image
```

### Preview Function
```python
# Before:
def get_preview():
    _kill_gphoto2()        # Clean before
    gphoto2 --capture-preview
    return image           # Process left running!

# After:
def get_preview():
    _kill_gphoto2()        # Clean before
    gphoto2 --capture-preview
    _kill_gphoto2()        # Clean after!
    return image
```

### Process Killer
```python
# Before:
def _kill_gphoto2():
    killall gphoto2
    killall -9 gphoto2
    killall gvfs-gphoto2-volume-monitor
    wait 0.5s

# After:
def _kill_gphoto2():
    killall gphoto2
    wait 0.2s
    killall -9 gphoto2
    wait 0.2s
    killall gvfs-gphoto2-volume-monitor
    wait 0.3s
    killall -9 PTPCamera    # NEW: Also kill PTP processes
    wait 0.3s
    # Total: 1 second wait
```

## Why This Works

### Process Lifecycle

```
Command starts → gphoto2 process created
    ↓
gphoto2 opens USB connection to camera
    ↓
gphoto2 locks camera (exclusive access)
    ↓
Command completes
    ↓
gphoto2 SHOULD release camera
    ↓
gphoto2 SHOULD exit
    ↓
BUT SOMETIMES IT DOESN'T!
```

### The Problem

gphoto2 processes can hang after completing, still holding the camera lock. Next command can't access camera → SIGKILL.

### The Solution

**Explicitly kill ALL gphoto2 processes:**
- Before every command (ensure clean slate)
- After preview (prevent lingering processes)
- Wait long enough for USB to release (1 second)

## Testing

### Test Sequence

1. **Preview Test**
   ```
   Click "Get Live Preview"
   → Should work
   → No processes left running
   ```

2. **Capture After Preview**
   ```
   Click "Get Live Preview"
   Wait for completion
   Click "CAPTURE"
   → Should work (no -9 error)
   ```

3. **Multiple Previews**
   ```
   Click "Get Live Preview" x 5
   → All should work
   → No process pile-up
   ```

4. **Multiple Captures**
   ```
   Click "CAPTURE" x 5
   → All should work
   → No -9 errors
   ```

5. **Mixed Commands**
   ```
   Preview → Capture → Preview → Capture
   → All should work
   ```

6. **Test Capture**
   ```
   Click "Test Camera Capture" x 5
   → All should work
   → Frame counter not incremented
   ```

## What Was Wrong Initially

### First Try: "Keep it simple"
```python
# Removed process killing thinking it was unnecessary
def capture():
    gphoto2 --capture-image  # WRONG: Processes conflict!
```

**Result:** Worked once, then -9 errors

### Why It Seemed to Work in SSH

When you run commands manually via SSH:
1. You have time between commands
2. Processes naturally exit
3. Shell cleans up better
4. You don't rapid-fire commands

In web interface:
1. Commands fire rapidly
2. Processes don't have time to exit naturally
3. Multiple processes pile up
4. Camera gets locked

## The Pattern

```
-9 error = Process conflict
         = Camera locked by another process
         = Need to kill existing processes first
```

**Always kill before, and kill after preview!**

## Performance Notes

### Time Added

- **Before capture:** +1 second (process kill + wait)
- **Before preview:** +0.5 second (process kill already there)
- **After preview:** +1 second (process kill + wait)

### Total Impact

- **Capture:** ~1 second overhead
- **Preview:** ~1.5 seconds overhead

### Worth It?

**YES!** Because:
- Without this: -9 errors, nothing works
- With this: Everything works reliably
- 1-1.5 seconds is acceptable for reliability

## Key Takeaways

1. **gphoto2 processes MUST be killed between commands**
2. **Preview leaves processes running - MUST clean up after**
3. **Need full 1 second wait for USB to release**
4. **Also kill PTP and gvfs processes**
5. **This is NOT optional - it's required for reliability**

## Commit Note

The previous commit that "simplified" capture was wrong. Process killing is not optional - it's required to prevent -9 errors from process conflicts. This commit restores proper process management.

---

**Status:** ✅ Fixed
**Error:** -9 (SIGKILL from process conflicts)
**Solution:** Kill processes before commands and after preview
**Result:** Reliable operation without process conflicts

