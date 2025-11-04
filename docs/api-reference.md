# Arduino API Documentation

## Serial Communication Protocol

**Settings**: 115200 baud, 8N1  
**Line ending**: `\n` (newline)  
**Response format**: Text with newline termination

## Command Reference

### Movement Commands

| Command | Description | Example | Response |
|---------|-------------|---------|----------|
| `f` | Forward fine step | `f\n` | `POS:1208` |
| `b` | Backward fine step | `b\n` | `POS:1200` |
| `F` | Forward coarse step | `F\n` | `POS:1264` |
| `B` | Backward coarse step | `B\n` | `POS:1200` |
| `N` | Next frame (calibrated) | `N\n` | `POS:2400` |
| `R` | Previous frame (calibrated) | `R\n` | `POS:1200` |
| `H[n]` | Forward exact steps | `H100\n` | `POS:1300` |
| `h[n]` | Backward exact steps | `h50\n` | `POS:1250` |

### Configuration Commands

| Command | Description | Example | Response |
|---------|-------------|---------|----------|
| `S[n]` | Set steps per frame | `S1200\n` | `SPF:1200` |
| `m[n]` | Set fine step size | `m8\n` | `FINE:8` |
| `l[n]` | Set coarse step size | `l64\n` | `COARSE:64` |
| `v[n]` | Set step delay (μs) | `v800\n` | `DELAY:800` |
| `d[n]` | Set backlash compensation | `d20\n` | `BACKLASH:20` |

### Control Commands

| Command | Description | Example | Response |
|---------|-------------|---------|----------|
| `X` | Lock motion | `X\n` | `LOCKED` |
| `U` | Unlock motion | `U\n` | `UNLOCKED` |
| `M` | Motor off (disable) | `M\n` | `MOTOR OFF` |
| `E` | Motor on (enable) | `E\n` | `MOTOR ON` |
| `P` | Get position | `P\n` | `POS:1200` |
| `Z` | Zero position | `Z\n` | `ZEROED` |
| `?` | Status report | `?\n` | (see below) |

### Status Report Format

Command: `?`

Response:
```
=== STATUS ===
Position: 1200
Steps/frame: 1200
Fine: 8 | Coarse: 64
Delay: 800us | Backlash: 20
Locked: NO | Motor: ON
```

## Variable Ranges

| Parameter | Min | Max | Default | Unit |
|-----------|-----|-----|---------|------|
| Steps per frame | 1 | 10000 | 1200 | steps |
| Fine step | 1 | 200 | 8 | steps |
| Coarse step | 1 | 500 | 64 | steps |
| Step delay | 200 | 5000 | 800 | microseconds |
| Backlash | 0 | 200 | 20 | steps |
| Exact movement | 1 | 10000 | - | steps |

## Arduino Pin Configuration

```c
const int STEP_PIN = 2;    // Digital pin 2 → A4988 STEP
const int DIR_PIN = 3;     // Digital pin 3 → A4988 DIR
const int ENABLE_PIN = 4;  // Digital pin 4 → A4988 ENABLE
```

## Internal Variables

```c
// Movement settings
int steps_per_frame = 1200;  // Calibrated frame advance
int fine_step = 8;           // Fine adjustment steps
int coarse_step = 64;        // Coarse adjustment steps
int step_delay_us = 800;     // Microseconds between steps
int backlash_steps = 20;     // Backlash compensation

// State tracking
int last_direction = 0;      // -1=back, 0=none, 1=forward
bool motion_locked = false;  // Safety lock
long position = 0;           // Current position counter
```

## Motion Control Logic

### Basic Movement
```c
void move_steps(int steps, int direction) {
    // Set direction
    digitalWrite(DIR_PIN, direction == 1 ? HIGH : LOW);
    
    // Backlash compensation if changing direction
    if (last_direction != 0 && last_direction != direction) {
        steps += backlash_steps;
    }
    
    // Execute steps
    for (int i = 0; i < steps; i++) {
        digitalWrite(STEP_PIN, HIGH);
        delayMicroseconds(step_delay_us);
        digitalWrite(STEP_PIN, LOW);
        delayMicroseconds(step_delay_us);
        
        position += direction;
    }
}
```

### Backlash Compensation

The Arduino automatically adds compensation steps when changing direction:
- Default: 20 steps
- Applied on direction reversal
- Configurable with `d` command

## Communication Examples

### Python Control
```python
import serial
import time

# Connect
arduino = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
time.sleep(2)  # Arduino reset time

# Initialize
arduino.write(b'U\n')  # Unlock
arduino.write(b'E\n')  # Enable motor

# Configure
arduino.write(b'S1200\n')  # Set frame advance
arduino.write(b'm8\n')     # Set fine step
arduino.write(b'v800\n')   # Set step delay

# Move
arduino.write(b'F\n')      # Forward coarse
time.sleep(0.5)
arduino.write(b'H100\n')   # Forward 100 steps

# Read response
response = arduino.readline().decode('utf-8').strip()
print(response)  # POS:164

# Get status
arduino.write(b'?\n')
while arduino.in_waiting:
    print(arduino.readline().decode('utf-8').strip())
```

### Manual Testing
```bash
# Connect via screen
screen /dev/ttyACM0 115200

# Test commands
?          # Show status
F          # Move forward
B          # Move backward
H100       # Forward 100 steps
Z          # Zero position
?          # Check new position

# Exit: Ctrl-A, K
```

## Error Handling

| Response | Meaning | Action |
|----------|---------|--------|
| `LOCKED` | Motion is locked | Send `U` to unlock |
| `UNKNOWN:[cmd]` | Invalid command | Check command format |
| No response | Connection issue | Check USB/power |
| Garbled text | Baud rate mismatch | Verify 115200 baud |

## Timing Specifications

### Step Generation
- **Minimum pulse width**: 2μs (A4988 requirement)
- **Default step delay**: 800μs (625 Hz)
- **Maximum reliable rate**: 2000 steps/second

### Motor Speed Calculation
```
Speed (mm/s) = (steps/second) × (mm/step)

Example:
- Steps/second: 1000
- Roller circumference: 31.4mm
- Steps/revolution: 3200 (with 16× microstepping)
- mm/step: 31.4 / 3200 = 0.0098mm

Speed = 1000 × 0.0098 = 9.8mm/s
```

## Power Management

### Enable Pin Logic
- **LOW (0V)**: Motor enabled (holding torque)
- **HIGH (5V)**: Motor disabled (free-spinning)

### Power States
| Command | Enable Pin | Motor State | Power Draw |
|---------|------------|-------------|------------|
| `E` | LOW | Holding | Full |
| `M` | HIGH | Free | None |
| `X` | HIGH | Locked (software) | None |

## Startup Sequence

On power-up or reset:
1. Sets all pins to OUTPUT
2. Enables motor (ENABLE = LOW)
3. Sets direction forward (DIR = LOW)
4. Sends `READY NEMA17` message
5. Waits for commands

## Safety Features

1. **Motion lock** (`X` command)
   - Prevents all movement
   - Must unlock (`U`) to resume

2. **Position tracking**
   - Maintains position counter
   - Survives direction changes
   - Reset with `Z` command

3. **Backlash compensation**
   - Automatic on direction change
   - Adjustable compensation amount
   - Improves repeatability

## Troubleshooting Commands

```bash
# Test sequence
?          # Check initial state
E          # Enable motor
F          # Test forward
B          # Test backward
P          # Check position
Z          # Zero position
H100       # Precise forward
h100       # Should return to zero
P          # Verify position = 0
```

## Performance Optimization

### Recommended Settings

**For 35mm film with 16× microstepping:**
```
S1200  # Steps per frame
m8     # Fine step (0.1mm movement)
l64    # Coarse step (0.8mm movement)
v800   # Step delay (smooth, reliable)
d20    # Backlash compensation
```

### Speed vs Reliability Trade-off

| Step Delay | Speed | Reliability | Use Case |
|------------|-------|-------------|----------|
| 2000μs | Slow | Excellent | High torque needs |
| 800μs | Medium | Very Good | **Recommended** |
| 400μs | Fast | Good | Light loads |
| 200μs | Very Fast | Fair | Risk of missed steps |

---

**Note**: All commands must be terminated with newline (`\n`). The Arduino echoes position after movement commands to confirm execution.
