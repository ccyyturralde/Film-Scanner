/*
 * 35mm Film Scanner - Motor Control Firmware (WiFi Version)
 * 
 * REQUIRES: Arduino Uno R4 WiFi (Renesas RA4M1 + ESP32-S3)
 * 
 * This version uses WiFi TCP communication instead of USB Serial.
 * The Arduino can be powered from the motor's 12V supply via VIN pin.
 * 
 * Hardware:
 * - Motor: NEMA 17 stepper (e.g., BJ42D22-23V01 / Creality 42-40)
 * - Driver: A4988 or TMC2209 Stepper Driver
 * 
 * Wiring:
 * D2 -> STEP
 * D3 -> DIR  
 * D4 -> ENABLE
 * GND -> Driver GND (CRITICAL: common ground with 12V supply!)
 * 
 * Power:
 * 12V -> Driver VMOT + Arduino VIN (shared power)
 * 12V GND -> Driver GND + Arduino GND (common ground)
 * 5V -> Driver VDD
 * 
 * WiFi Configuration:
 * Edit wifi_config.h with your network settings before uploading.
 * 
 * LED Matrix Status (R4 WiFi):
 * - Happy face: All systems OK
 * - "W": Connecting to WiFi
 * - "17": Motor not detected / motor error  
 * - "!": General error
 * - "X": WiFi connection error
 * - "?": Unknown command received
 * - Spinning animation: Motor in motion
 * - "L": Motion locked
 * - IP address scroll: WiFi connected (on startup)
 * 
 * Upload Command:
 * arduino-cli upload -p PORT --fqbn arduino:renesas_uno:unor4wifi
 */

// WiFi Configuration
#include "wifi_config.h"

// LED Matrix and WiFi support for Arduino Uno R4 WiFi
#if defined(ARDUINO_UNOR4_WIFI)
  #define HAS_LED_MATRIX
  #define HAS_WIFI
  #include "Arduino_LED_Matrix.h"
  #include <WiFiS3.h>
  ArduinoLEDMatrix matrix;
  WiFiServer server(TCP_PORT);
  WiFiClient client;
#else
  #error "This firmware requires Arduino Uno R4 WiFi. Use the USB Serial version for R3/R4 Minima."
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
  LED_COMM_ERROR,   // "X" - communication/WiFi error
  LED_UNKNOWN_CMD,  // "?" - unknown command
  LED_LOCKED,       // "L" - motion locked
  LED_MOVING,       // Spinning animation frame
  LED_IDLE,         // Dim/standby pattern
  LED_WIFI_CONNECTING  // "W" - connecting to WiFi
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

// "W" - WiFi connecting
const uint32_t PATTERN_WIFI[] = {
  0x00001001,
  0x90289028,
  0xA850A850,
  0x54405440
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
    case LED_WIFI_CONNECTING:
      showLEDPattern(PATTERN_WIFI);
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

// Motor parameters (configurable via commands)
int steps_per_frame = 1200;
int fine_step = 8;
int coarse_step = 192;
int step_delay_us = 800;
int backlash_steps = 20;

// State tracking
int last_direction = 0;
bool motion_locked = false;
long position = 0;

// WiFi state
bool wifi_connected = false;
unsigned long last_client_activity = 0;

// ============================================================================
// WiFi Helper Functions
// ============================================================================

#ifdef HAS_WIFI

bool connectWiFi() {
  if (WIFI_DEBUG) {
    Serial.println("\n=== WiFi Setup ===");
    Serial.print("Hostname: ");
    Serial.println(DEVICE_HOSTNAME);
    Serial.print("Connecting to: ");
    Serial.println(WIFI_SSID);
  }
  
  #ifdef HAS_LED_MATRIX
  updateLEDStatus(LED_WIFI_CONNECTING);
  #endif
  
  // Set hostname BEFORE connecting - this shows up in router's device list
  WiFi.setHostname(DEVICE_HOSTNAME);
  
  // Connect to WiFi
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < WIFI_MAX_RETRIES) {
    delay(WIFI_RETRY_DELAY);
    if (WIFI_DEBUG) {
      Serial.print(".");
    }
    // Blink the LED to show we're trying to connect
    #ifdef HAS_LED_MATRIX
    if (attempts % 2 == 0) {
      showLEDPattern(PATTERN_WIFI);
    } else {
      showLEDPattern(PATTERN_IDLE);
    }
    #endif
    attempts++;
  }
  
  if (WiFi.status() != WL_CONNECTED) {
    if (WIFI_DEBUG) {
      Serial.println("\n❌ WiFi connection failed!");
      Serial.println("Check SSID and password in wifi_config.h");
    }
    #ifdef HAS_LED_MATRIX
    updateLEDStatus(LED_COMM_ERROR);
    #endif
    return false;
  }
  
  // Configure static IP if requested (otherwise uses DHCP)
  if (USE_STATIC_IP) {
    IPAddress ip, gateway, subnet, dns;
    ip.fromString(STATIC_IP);
    gateway.fromString(GATEWAY);
    subnet.fromString(SUBNET);
    dns.fromString(DNS_SERVER);
    WiFi.config(ip, dns, gateway, subnet);
  }
  
  wifi_connected = true;
  
  if (WIFI_DEBUG) {
    Serial.println("\n✓ WiFi connected!");
    Serial.print("Hostname: ");
    Serial.println(DEVICE_HOSTNAME);
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("TCP Port: ");
    Serial.println(TCP_PORT);
    Serial.println("\nFind this device in your router's device list as:");
    Serial.print("  → ");
    Serial.println(DEVICE_HOSTNAME);
  }
  
  // Show success pattern (happy face)
  #ifdef HAS_LED_MATRIX
  updateLEDStatus(LED_OK);
  #endif
  
  return true;
}

// Send response to both Serial (debug) and WiFi client
void sendResponse(const String& msg) {
  if (WIFI_DEBUG) {
    Serial.println(msg);
  }
  if (client && client.connected()) {
    client.println(msg);
    last_client_activity = millis();
  }
}

void sendResponseNoNewline(const String& msg) {
  if (WIFI_DEBUG) {
    Serial.print(msg);
  }
  if (client && client.connected()) {
    client.print(msg);
  }
}

#endif // HAS_WIFI

void setup() {
  // Configure pins
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(ENABLE_PIN, OUTPUT);
  
  // Initialize to known state
  digitalWrite(ENABLE_PIN, LOW);  // Motor enabled (active LOW)
  digitalWrite(DIR_PIN, LOW);
  digitalWrite(STEP_PIN, LOW);
  
  // Initialize LED matrix
  #ifdef HAS_LED_MATRIX
  matrix.begin();
  updateLEDStatus(LED_IDLE);
  #endif
  
  // Initialize USB Serial for debugging (optional)
  #ifdef HAS_WIFI
  if (WIFI_DEBUG) {
    Serial.begin(115200);
    delay(2000);  // Give serial time to initialize
    Serial.println("\n=== Film Scanner Motor Control (WiFi) ===");
    Serial.println("Version: WiFi TCP Server");
  }
  #endif
  
  // Connect to WiFi
  #ifdef HAS_WIFI
  if (!connectWiFi()) {
    // WiFi failed - halt and show error
    while (true) {
      #ifdef HAS_LED_MATRIX
      flashError(LED_COMM_ERROR, 1);
      #endif
      delay(1000);
    }
  }
  
  // Start TCP server
  server.begin();
  if (WIFI_DEBUG) {
    Serial.println("✓ TCP server started");
    Serial.println("Waiting for client connection...");
  }
  #endif
  
  // Ready
  #ifdef HAS_LED_MATRIX
  updateLEDStatus(LED_OK);
  #endif
}

void move_steps(int steps, int direction) {
  if (motion_locked) {
    sendResponse("LOCKED");
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
  
  sendResponseNoNewline("POS:");
  sendResponse(String(position));
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
        sendResponse("SPF:" + String(steps_per_frame));
      }
      break;
    case 'm':
      if (value > 0 && value < 200) {
        fine_step = value;
        sendResponse("FINE:" + String(fine_step));
      }
      break;
    case 'l':
      if (value > 0 && value < 500) {
        coarse_step = value;
        sendResponse("COARSE:" + String(coarse_step));
      }
      break;
    case 'v':
      if (value >= 200 && value <= 5000) {
        step_delay_us = value;
        sendResponse("DELAY:" + String(step_delay_us));
      }
      break;
    case 'd':
      if (value >= 0 && value < 200) {
        backlash_steps = value;
        sendResponse("BACKLASH:" + String(backlash_steps));
      }
      break;
    
    // Lock/unlock
    case 'X':
      motion_locked = true;
      digitalWrite(ENABLE_PIN, HIGH);
      sendResponse("LOCKED");
      #ifdef HAS_LED_MATRIX
      updateLEDStatus(LED_LOCKED);
      #endif
      break;
    case 'U':
      motion_locked = false;
      digitalWrite(ENABLE_PIN, LOW);
      sendResponse("UNLOCKED");
      #ifdef HAS_LED_MATRIX
      updateLEDStatus(LED_OK);
      #endif
      break;
    
    // Motor power
    case 'M':
      digitalWrite(ENABLE_PIN, HIGH);
      sendResponse("MOTOR OFF");
      #ifdef HAS_LED_MATRIX
      updateLEDStatus(LED_MOTOR_ERROR);  // Show "17" when motor disabled
      #endif
      break;
    case 'E':
      digitalWrite(ENABLE_PIN, LOW);
      sendResponse("MOTOR ON");
      #ifdef HAS_LED_MATRIX
      updateLEDStatus(LED_OK);
      #endif
      break;
    
    // Position
    case 'P':
      sendResponse("POS:" + String(position));
      break;
    case 'Z':
      position = 0;
      sendResponse("ZEROED");
      break;
    
    // Status
    case '?':
      sendResponse("=== STATUS ===");
      sendResponse("Position: " + String(position));
      sendResponse("Steps/frame: " + String(steps_per_frame));
      sendResponse("Fine: " + String(fine_step) + " | Coarse: " + String(coarse_step));
      sendResponse("Delay: " + String(step_delay_us) + "us | Backlash: " + String(backlash_steps));
      sendResponse("Locked: " + String(motion_locked ? "YES" : "NO") + 
                   " | Motor: " + String(digitalRead(ENABLE_PIN) == LOW ? "ON" : "OFF"));
      #ifdef HAS_WIFI
      sendResponse("WiFi: " + WiFi.localIP().toString() + ":" + String(TCP_PORT));
      #endif
      #ifdef HAS_LED_MATRIX
      sendResponse("LED Status: " + String(currentLEDStatus));
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
      sendResponse("LED:" + String(value));
      break;
    #endif
    
    default:
      sendResponse("UNKNOWN:" + String(command));
      #ifdef HAS_LED_MATRIX
      flashError(LED_UNKNOWN_CMD, 2);
      #endif
      break;
  }
}

void loop() {
  #ifdef HAS_WIFI
  // Check for new client connections
  if (!client || !client.connected()) {
    client = server.available();
    if (client) {
      if (WIFI_DEBUG) {
        Serial.println("\n✓ Client connected from: " + client.remoteIP().toString());
      }
      sendResponse("READY NEMA17");
      sendResponse("Film Scanner Motor Control (WiFi)");
      last_client_activity = millis();
    }
  }
  
  // Handle client commands
  if (client && client.connected()) {
    // Check for timeout
    if (CLIENT_TIMEOUT > 0 && (millis() - last_client_activity > CLIENT_TIMEOUT)) {
      if (WIFI_DEBUG) {
        Serial.println("⚠ Client timeout, disconnecting");
      }
      client.stop();
    }
    
    // Read and process commands
    if (client.available() > 0) {
      String cmd = client.readStringUntil('\n');
      cmd.trim();
      if (cmd.length() > 0) {
        last_client_activity = millis();
        if (WIFI_DEBUG) {
          Serial.println("← " + cmd);
        }
        parse_command(cmd);
      }
    }
  }
  #endif
  
  // Update LED animation if in moving state
  #ifdef HAS_LED_MATRIX
  updateSpinAnimation();
  #endif
}
