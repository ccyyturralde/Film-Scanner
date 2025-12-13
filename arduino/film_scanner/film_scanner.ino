/*
 * 35mm Film Scanner - Motor Control Firmware
 * 
 * Compatible with:
 * - Arduino Uno R3 (ATmega328P)
 * - Arduino Uno R4 Minima (Renesas RA4M1)
 * - Arduino Uno R4 WiFi (Renesas RA4M1 + ESP32-S3)
 * 
 * Hardware:
 * - Motor: NEMA 17 stepper (e.g., BJ42D22-23V01 / Creality 42-40)
 * - Driver: A4988 Stepper Driver
 * 
 * Wiring (same for R3 and R4):
 * D2 -> STEP
 * D3 -> DIR  
 * D4 -> ENABLE
 * GND -> Driver GND (CRITICAL: common ground with 12V supply!)
 * 
 * Power:
 * 12V -> Driver VMOT
 * 12V GND -> Driver GND + Arduino GND
 * 5V -> Driver VDD
 * 
 * LED Matrix Status (R4 WiFi only):
 * - Happy face: All systems OK
 * - "17": Motor not detected / motor error  
 * - "!": General error
 * - "X": Communication/connection error
 * - "?": Unknown command received
 * - Spinning animation: Motor in motion
 * - "L": Motion locked
 * 
 * Upload Commands:
 * R3:        arduino-cli upload -p PORT --fqbn arduino:avr:uno
 * R4 Minima: arduino-cli upload -p PORT --fqbn arduino:renesas_uno:unor4minima
 * R4 WiFi:   arduino-cli upload -p PORT --fqbn arduino:renesas_uno:unor4wifi
 */

// LED Matrix support for Arduino Uno R4 WiFi
#if defined(ARDUINO_UNOR4_WIFI)
  #define HAS_LED_MATRIX
  #include "Arduino_LED_Matrix.h"
  ArduinoLEDMatrix matrix;
#endif

// Pin definitions
const int STEP_PIN = 2;
const int DIR_PIN = 3;
const int ENABLE_PIN = 4;

// ============================================================================
// LED Matrix Patterns (R4 WiFi only) - 12 columns x 8 rows
// Each pattern is 4 x 32-bit values representing the 96 LEDs (12x8)
// ============================================================================
#ifdef HAS_LED_MATRIX

// Status codes for LED display
enum LEDStatus {
  LED_OK,           // Happy face - all good
  LED_MOTOR_ERROR,  // "17" - motor not detected/error
  LED_ERROR,        // "!" - general error
  LED_COMM_ERROR,   // "X" - communication error
  LED_UNKNOWN_CMD,  // "?" - unknown command
  LED_LOCKED,       // "L" - motion locked
  LED_MOVING,       // Spinning animation frame
  LED_IDLE          // Dim/standby pattern
};

// Happy face :) - All systems OK
const uint32_t PATTERN_OK[] = {
  0x00000000,
  0x32043204,
  0x4040783C,
  0x00000000
};

// "17" - Motor error/not detected
const uint32_t PATTERN_MOTOR_ERROR[] = {
  0x20820820,
  0x88820FA8,
  0xF88208A8,
  0x820820A8
};

// "!" - General error (exclamation mark)
const uint32_t PATTERN_ERROR[] = {
  0x00000060,
  0x06006006,
  0x00600600,
  0x60000000
};

// "X" - Communication/connection error
const uint32_t PATTERN_COMM_ERROR[] = {
  0x00000801,
  0x20201040,
  0x80400802,
  0x01000000
};

// "?" - Unknown command
const uint32_t PATTERN_UNKNOWN[] = {
  0x00007008,
  0x80408010,
  0x20000020,
  0x00000000
};

// "L" - Motion locked
const uint32_t PATTERN_LOCKED[] = {
  0x00080008,
  0x00800080,
  0x0F800080,
  0x00000000
};

// Spinning/moving animation frames
const uint32_t PATTERN_SPIN_0[] = {
  0x00001C01,
  0xC01C01C0,
  0x1C01C01C,
  0x00000000
};

const uint32_t PATTERN_SPIN_1[] = {
  0x00000003,
  0x80380380,
  0x38038000,
  0x00000000
};

const uint32_t PATTERN_SPIN_2[] = {
  0x00000000,
  0x00700700,
  0x70070070,
  0x07000000
};

const uint32_t PATTERN_SPIN_3[] = {
  0x00000000,
  0x00E00E00,
  0xE00E00E0,
  0x0E000000
};

// Idle/standby - single dot
const uint32_t PATTERN_IDLE[] = {
  0x00000000,
  0x00000600,
  0x00000000,
  0x00000000
};

// Current status and animation state
LEDStatus currentLEDStatus = LED_IDLE;
int spinFrame = 0;
unsigned long lastSpinUpdate = 0;
const int SPIN_INTERVAL = 100; // ms between animation frames

void showLEDPattern(const uint32_t* pattern) {
  matrix.loadFrame(pattern);
}

void updateLEDStatus(LEDStatus status) {
  currentLEDStatus = status;
  switch (status) {
    case LED_OK:
      showLEDPattern(PATTERN_OK);
      break;
    case LED_MOTOR_ERROR:
      showLEDPattern(PATTERN_MOTOR_ERROR);
      break;
    case LED_ERROR:
      showLEDPattern(PATTERN_ERROR);
      break;
    case LED_COMM_ERROR:
      showLEDPattern(PATTERN_COMM_ERROR);
      break;
    case LED_UNKNOWN_CMD:
      showLEDPattern(PATTERN_UNKNOWN);
      break;
    case LED_LOCKED:
      showLEDPattern(PATTERN_LOCKED);
      break;
    case LED_IDLE:
      showLEDPattern(PATTERN_IDLE);
      break;
    case LED_MOVING:
      // Handled by animation update
      break;
  }
}

void updateSpinAnimation() {
  if (currentLEDStatus != LED_MOVING) return;
  
  unsigned long now = millis();
  if (now - lastSpinUpdate >= SPIN_INTERVAL) {
    lastSpinUpdate = now;
    spinFrame = (spinFrame + 1) % 4;
    
    switch (spinFrame) {
      case 0: showLEDPattern(PATTERN_SPIN_0); break;
      case 1: showLEDPattern(PATTERN_SPIN_1); break;
      case 2: showLEDPattern(PATTERN_SPIN_2); break;
      case 3: showLEDPattern(PATTERN_SPIN_3); break;
    }
  }
}

// Flash an error pattern briefly then return to previous state
void flashError(LEDStatus errorType, int flashCount = 3) {
  LEDStatus previousStatus = currentLEDStatus;
  for (int i = 0; i < flashCount; i++) {
    updateLEDStatus(errorType);
    delay(200);
    showLEDPattern(PATTERN_IDLE);
    delay(100);
  }
  updateLEDStatus(previousStatus);
}

#endif // HAS_LED_MATRIX

// Motor parameters (configurable via serial commands)
int steps_per_frame = 1200;
int fine_step = 8;
int coarse_step = 192;
int step_delay_us = 800;
int backlash_steps = 20;

// State tracking
int last_direction = 0;
bool motion_locked = false;
long position = 0;

void setup() {
  // Configure pins
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(ENABLE_PIN, OUTPUT);
  
  // Initialize to known state
  digitalWrite(ENABLE_PIN, LOW);  // Motor enabled (active LOW)
  digitalWrite(DIR_PIN, LOW);
  digitalWrite(STEP_PIN, LOW);
  
  // Initialize LED matrix (R4 WiFi only)
  #ifdef HAS_LED_MATRIX
  matrix.begin();
  updateLEDStatus(LED_IDLE);
  #endif
  
  // Initialize serial
  Serial.begin(115200);
  while (!Serial) {
    ; // Wait for serial port
  }
  
  // Ready signal - show happy face on successful init
  Serial.println("READY NEMA17");
  Serial.println("Film Scanner Motor Control");
  
  #ifdef HAS_LED_MATRIX
  updateLEDStatus(LED_OK);
  #endif
}

void move_steps(int steps, int direction) {
  if (motion_locked) {
    Serial.println("LOCKED");
    #ifdef HAS_LED_MATRIX
    flashError(LED_LOCKED, 2);
    #endif
    return;
  }
  
  int total_steps = steps;
  
  // Backlash compensation on direction change
  if (last_direction != 0 && last_direction != direction) {
    total_steps += backlash_steps;
  }
  last_direction = direction;
  
  // Set direction
  digitalWrite(DIR_PIN, direction == 1 ? HIGH : LOW);
  delayMicroseconds(5);
  
  // Start moving animation
  #ifdef HAS_LED_MATRIX
  currentLEDStatus = LED_MOVING;
  lastSpinUpdate = 0; // Force immediate update
  #endif
  
  // Execute steps
  for (int i = 0; i < total_steps; i++) {
    digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(step_delay_us);
    digitalWrite(STEP_PIN, LOW);
    delayMicroseconds(step_delay_us);
    position += direction;
    
    // Update spin animation periodically during long moves
    #ifdef HAS_LED_MATRIX
    if (i % 50 == 0) {
      updateSpinAnimation();
    }
    #endif
  }
  
  // Return to OK status after move
  #ifdef HAS_LED_MATRIX
  updateLEDStatus(LED_OK);
  #endif
  
  Serial.print("POS:");
  Serial.println(position);
}

void parse_command(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;
  
  char command = cmd.charAt(0);
  int value = 0;
  if (cmd.length() > 1) {
    value = cmd.substring(1).toInt();
  }
  
  switch (command) {
    // Movement commands
    case 'f': move_steps(fine_step, 1); break;
    case 'b': move_steps(fine_step, -1); break;
    case 'F': move_steps(coarse_step, 1); break;
    case 'B': move_steps(coarse_step, -1); break;
    case 'N': move_steps(steps_per_frame, 1); break;
    case 'R': move_steps(steps_per_frame, -1); break;
    
    // Step commands with value
    case 'H':
      if (value > 0 && value < 10000) move_steps(value, 1);
      break;
    case 'h':
      if (value > 0 && value < 10000) move_steps(value, -1);
      break;
    
    // Configuration commands
    case 'S':
      if (value > 0 && value < 5000) {
        steps_per_frame = value;
        Serial.print("SPF:");
        Serial.println(steps_per_frame);
      }
      break;
    case 'm':
      if (value > 0 && value < 200) {
        fine_step = value;
        Serial.print("FINE:");
        Serial.println(fine_step);
      }
      break;
    case 'l':
      if (value > 0 && value < 500) {
        coarse_step = value;
        Serial.print("COARSE:");
        Serial.println(coarse_step);
      }
      break;
    case 'v':
      if (value >= 200 && value <= 5000) {
        step_delay_us = value;
        Serial.print("DELAY:");
        Serial.println(step_delay_us);
      }
      break;
    case 'd':
      if (value >= 0 && value < 200) {
        backlash_steps = value;
        Serial.print("BACKLASH:");
        Serial.println(backlash_steps);
      }
      break;
    
    // Lock/unlock
    case 'X':
      motion_locked = true;
      digitalWrite(ENABLE_PIN, HIGH);
      Serial.println("LOCKED");
      #ifdef HAS_LED_MATRIX
      updateLEDStatus(LED_LOCKED);
      #endif
      break;
    case 'U':
      motion_locked = false;
      digitalWrite(ENABLE_PIN, LOW);
      Serial.println("UNLOCKED");
      #ifdef HAS_LED_MATRIX
      updateLEDStatus(LED_OK);
      #endif
      break;
    
    // Motor power
    case 'M':
      digitalWrite(ENABLE_PIN, HIGH);
      Serial.println("MOTOR OFF");
      #ifdef HAS_LED_MATRIX
      updateLEDStatus(LED_MOTOR_ERROR);  // Show "17" when motor disabled
      #endif
      break;
    case 'E':
      digitalWrite(ENABLE_PIN, LOW);
      Serial.println("MOTOR ON");
      #ifdef HAS_LED_MATRIX
      updateLEDStatus(LED_OK);
      #endif
      break;
    
    // Position
    case 'P':
      Serial.print("POS:");
      Serial.println(position);
      break;
    case 'Z':
      position = 0;
      Serial.println("ZEROED");
      break;
    
    // Status
    case '?':
      Serial.println("=== STATUS ===");
      Serial.print("Position: ");
      Serial.println(position);
      Serial.print("Steps/frame: ");
      Serial.println(steps_per_frame);
      Serial.print("Fine: ");
      Serial.print(fine_step);
      Serial.print(" | Coarse: ");
      Serial.println(coarse_step);
      Serial.print("Delay: ");
      Serial.print(step_delay_us);
      Serial.print("us | Backlash: ");
      Serial.println(backlash_steps);
      Serial.print("Locked: ");
      Serial.print(motion_locked ? "YES" : "NO");
      Serial.print(" | Motor: ");
      Serial.println(digitalRead(ENABLE_PIN) == LOW ? "ON" : "OFF");
      #ifdef HAS_LED_MATRIX
      Serial.print("LED Matrix: R4 WiFi | Status: ");
      Serial.println(currentLEDStatus);
      #else
      Serial.println("LED Matrix: N/A (not R4 WiFi)");
      #endif
      break;
    
    // LED Matrix control (R4 WiFi only)
    #ifdef HAS_LED_MATRIX
    case 'L':
      // Show LED status pattern: L0=OK, L1=Error, L2=MotorErr, L3=Idle
      if (value == 0) updateLEDStatus(LED_OK);
      else if (value == 1) updateLEDStatus(LED_ERROR);
      else if (value == 2) updateLEDStatus(LED_MOTOR_ERROR);
      else if (value == 3) updateLEDStatus(LED_IDLE);
      else if (value == 4) updateLEDStatus(LED_COMM_ERROR);
      else if (value == 5) updateLEDStatus(LED_LOCKED);
      Serial.print("LED:");
      Serial.println(value);
      break;
    #endif
    
    default:
      Serial.print("UNKNOWN:");
      Serial.println(command);
      #ifdef HAS_LED_MATRIX
      flashError(LED_UNKNOWN_CMD, 2);
      #endif
      break;
  }
}

void loop() {
  // Handle serial commands
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    parse_command(cmd);
  }
  
  // Update LED animation if in moving state
  #ifdef HAS_LED_MATRIX
  updateSpinAnimation();
  #endif
}
