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
// Using renderBitmap for clearer pattern definition
// ============================================================================
#ifdef HAS_LED_MATRIX

// Status codes for LED display
enum LEDStatus {
  LED_OK,           // Happy face - all good
  LED_MOTOR_ERROR,  // "!" error
  LED_ERROR,        // "!" - general error
  LED_COMM_ERROR,   // "X" - communication/WiFi error
  LED_UNKNOWN_CMD,  // "?" - unknown command
  LED_LOCKED,       // Square - motion locked
  LED_MOVING,       // Spinning animation frame
  LED_IDLE,         // Dim/standby pattern
  LED_WIFI_CONNECTING  // Blinking - connecting to WiFi
};

// LED patterns as byte arrays [8 rows][12 columns] - much easier to visualize!
// Note: NOT const because renderBitmap doesn't accept const pointers

// Happy face :)
byte PATTERN_OK[8][12] = {
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0 },
  { 0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0 },
  { 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 }
};

// X pattern - error
byte PATTERN_ERROR[8][12] = {
  { 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1 },
  { 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0 },
  { 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0 },
  { 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0 },
  { 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0 },
  { 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0 }
};

// Single dot - idle
byte PATTERN_IDLE[8][12] = {
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 }
};

// Square - locked
byte PATTERN_LOCKED[8][12] = {
  { 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0 },
  { 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0 },
  { 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0 },
  { 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0 },
  { 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0 },
  { 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0 },
  { 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0 },
  { 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0 }
};

// All on - WiFi connecting indicator
byte PATTERN_WIFI_ON[8][12] = {
  { 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1 },
  { 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1 },
  { 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1 },
  { 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1 },
  { 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1 },
  { 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1 },
  { 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1 },
  { 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1 }
};

// Spin animation frames
byte PATTERN_SPIN_0[8][12] = {
  { 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0 }
};

byte PATTERN_SPIN_1[8][12] = {
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 }
};

byte PATTERN_SPIN_2[8][12] = {
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1 },
  { 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 }
};

byte PATTERN_SPIN_3[8][12] = {
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0 },
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 }
};

// Current status and animation state
LEDStatus currentLEDStatus = LED_IDLE;
int spinFrame = 0;
unsigned long lastSpinUpdate = 0;
const int SPIN_INTERVAL = 100; // ms between animation frames

void showPattern(byte pattern[8][12]) {
  matrix.renderBitmap(pattern, 8, 12);
}

void updateLEDStatus(LEDStatus status) {
  currentLEDStatus = status;
  switch (status) {
    case LED_OK:
      showPattern(PATTERN_OK);
      break;
    case LED_MOTOR_ERROR:
    case LED_ERROR:
    case LED_COMM_ERROR:
    case LED_UNKNOWN_CMD:
      showPattern(PATTERN_ERROR);
      break;
    case LED_LOCKED:
      showPattern(PATTERN_LOCKED);
      break;
    case LED_IDLE:
      showPattern(PATTERN_IDLE);
      break;
    case LED_WIFI_CONNECTING:
      showPattern(PATTERN_WIFI_ON);
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
      case 0: showPattern(PATTERN_SPIN_0); break;
      case 1: showPattern(PATTERN_SPIN_1); break;
      case 2: showPattern(PATTERN_SPIN_2); break;
      case 3: showPattern(PATTERN_SPIN_3); break;
    }
  }
}

// Flash pattern on/off
void flashError(LEDStatus errorType, int flashCount = 3) {
  LEDStatus previousStatus = currentLEDStatus;
  for (int i = 0; i < flashCount; i++) {
    updateLEDStatus(errorType);
    delay(200);
    showPattern(PATTERN_IDLE);
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
  Serial.println("\n=== WiFi Setup ===");
  Serial.print("Hostname: ");
  Serial.println(DEVICE_HOSTNAME);
  Serial.print("SSID: ");
  Serial.println(WIFI_SSID);
  
  #ifdef HAS_LED_MATRIX
  updateLEDStatus(LED_WIFI_CONNECTING);
  #endif
  
  // Set hostname BEFORE connecting - this shows up in router's device list
  WiFi.setHostname(DEVICE_HOSTNAME);
  
  // Connect to WiFi
  Serial.print("Connecting");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < WIFI_MAX_RETRIES) {
    delay(WIFI_RETRY_DELAY);
    Serial.print(".");
    // Blink the LED to show we're trying to connect
    #ifdef HAS_LED_MATRIX
    if (attempts % 2 == 0) {
      showPattern(PATTERN_WIFI_ON);
    } else {
      showPattern(PATTERN_IDLE);
    }
    #endif
    attempts++;
  }
  
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\nWiFi FAILED!");
    Serial.println("Check SSID and password in wifi_config.h");
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
  
  // Wait for DHCP to assign a valid IP (up to 10 seconds)
  Serial.print("Waiting for IP");
  int ip_attempts = 0;
  while (WiFi.localIP() == IPAddress(0, 0, 0, 0) && ip_attempts < 20) {
    delay(500);
    Serial.print(".");
    ip_attempts++;
  }
  Serial.println();
  
  if (WiFi.localIP() == IPAddress(0, 0, 0, 0)) {
    Serial.println("DHCP FAILED - no IP assigned");
    #ifdef HAS_LED_MATRIX
    updateLEDStatus(LED_COMM_ERROR);
    #endif
    return false;
  }
  
  // Give the network stack time to fully initialize
  Serial.print("Stabilizing network");
  for (int i = 0; i < 5; i++) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" done");
  
  wifi_connected = true;
  
  // Always print connection info
  Serial.println("");
  Serial.println("==================================");
  Serial.println("       WiFi CONNECTED!");
  Serial.println("==================================");
  Serial.print("Hostname: ");
  Serial.println(DEVICE_HOSTNAME);
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
  Serial.print("Port: ");
  Serial.println(TCP_PORT);
  Serial.println("==================================");
  Serial.println("");
  
  // Show success pattern (happy face)
  #ifdef HAS_LED_MATRIX
  updateLEDStatus(LED_OK);
  #endif
  
  return true;
}

// Send response to both Serial (always) and WiFi client
void sendResponse(const String& msg) {
  Serial.println(msg);
  if (client && client.connected()) {
    client.println(msg);
    last_client_activity = millis();
  }
}

void sendResponseNoNewline(const String& msg) {
  Serial.print(msg);
  if (client && client.connected()) {
    client.print(msg);
  }
}

#endif // HAS_WIFI

void setup() {
  // Always initialize Serial first for debugging
  Serial.begin(115200);
  
  // Wait for Serial to be ready (important for R4 WiFi USB Serial)
  // But don't wait forever in case no USB is connected
  unsigned long serialStart = millis();
  while (!Serial && millis() - serialStart < 3000) {
    delay(10);
  }
  
  Serial.println("");
  Serial.println("====================================");
  Serial.println("  Film Scanner - Arduino R4 WiFi");
  Serial.println("====================================");
  Serial.println("Initializing...");
  
  // Configure pins
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(ENABLE_PIN, OUTPUT);
  
  // Initialize to known state
  digitalWrite(ENABLE_PIN, LOW);  // Motor enabled (active LOW)
  digitalWrite(DIR_PIN, LOW);
  digitalWrite(STEP_PIN, LOW);
  Serial.println("- Motor pins configured");
  
  // Initialize LED matrix
  #ifdef HAS_LED_MATRIX
  matrix.begin();
  updateLEDStatus(LED_IDLE);
  Serial.println("- LED matrix initialized");
  #endif
  
  // Connect to WiFi
  #ifdef HAS_WIFI
  if (!connectWiFi()) {
    // WiFi failed - halt and show error
    Serial.println("HALTED: WiFi connection failed");
    while (true) {
      #ifdef HAS_LED_MATRIX
      flashError(LED_COMM_ERROR, 1);
      #endif
      delay(1000);
    }
  }
  
  // Start TCP server - try multiple times if needed
  Serial.print("Starting TCP server on port ");
  Serial.print(TCP_PORT);
  Serial.print("...");
  
  server.begin();
  delay(500);
  
  // Verify server is ready by checking if we can get our own IP
  if (WiFi.localIP() != IPAddress(0, 0, 0, 0)) {
    Serial.println(" OK");
    Serial.print("Server listening at ");
    Serial.print(WiFi.localIP());
    Serial.print(":");
    Serial.println(TCP_PORT);
  } else {
    Serial.println(" WARNING: IP is 0.0.0.0");
  }
  
  Serial.println("Waiting for connections...");
  #endif
  
  // Ready
  #ifdef HAS_LED_MATRIX
  updateLEDStatus(LED_OK);
  #endif
  
  Serial.println("");
  Serial.println("READY");
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
      {
        uint8_t mac[6];
        WiFi.macAddress(mac);
        char macStr[18];
        sprintf(macStr, "%02X:%02X:%02X:%02X:%02X:%02X", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
        sendResponse("WiFi IP: " + WiFi.localIP().toString());
        sendResponse("WiFi Gateway: " + WiFi.gatewayIP().toString());
        sendResponse("WiFi Subnet: " + WiFi.subnetMask().toString());
        sendResponse("WiFi Status: " + String(WiFi.status()) + " (3=connected)");
        sendResponse("WiFi RSSI: " + String(WiFi.RSSI()) + " dBm");
        sendResponse("WiFi MAC: " + String(macStr));
        sendResponse("TCP Port: " + String(TCP_PORT));
      }
      #endif
      #ifdef HAS_LED_MATRIX
      sendResponse("LED Status: " + String(currentLEDStatus));
      #endif
      break;
    
    // WiFi reconnect command
    case 'W':
      #ifdef HAS_WIFI
      sendResponse("Reconnecting WiFi...");
      WiFi.disconnect();
      delay(1000);
      if (connectWiFi()) {
        server.begin();
        sendResponse("WiFi reconnected: " + WiFi.localIP().toString());
      } else {
        sendResponse("WiFi reconnect FAILED");
      }
      #endif
      break;
    
    // Test outbound connectivity
    case 'T':
      #ifdef HAS_WIFI
      {
        sendResponse("Testing outbound connection to gateway...");
        WiFiClient testClient;
        // Try to connect to gateway on port 80 (most routers have web interface)
        if (testClient.connect(WiFi.gatewayIP(), 80)) {
          sendResponse("SUCCESS: Connected to gateway!");
          testClient.stop();
        } else {
          sendResponse("FAILED: Cannot connect to gateway");
        }
        
        // Also try Google DNS to test internet
        sendResponse("Testing internet (8.8.8.8:53)...");
        IPAddress googleDNS(8, 8, 8, 8);
        if (testClient.connect(googleDNS, 53)) {
          sendResponse("SUCCESS: Internet reachable!");
          testClient.stop();
        } else {
          sendResponse("FAILED: Cannot reach internet");
        }
        
        // Try to connect to our own server (loopback test)
        sendResponse("Testing self-connection (loopback)...");
        if (testClient.connect(WiFi.localIP(), TCP_PORT)) {
          sendResponse("SUCCESS: Server is accepting connections!");
          testClient.stop();
        } else {
          sendResponse("FAILED: Cannot connect to own server");
          sendResponse("This indicates the server is not listening properly");
        }
      }
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
      Serial.println("\nClient connected: " + client.remoteIP().toString());
      sendResponse("READY NEMA17");
      sendResponse("Film Scanner Motor Control (WiFi)");
      last_client_activity = millis();
    }
  }
  
  // Handle WiFi client commands
  if (client && client.connected()) {
    // Check for timeout
    if (CLIENT_TIMEOUT > 0 && (millis() - last_client_activity > CLIENT_TIMEOUT)) {
      Serial.println("Client timeout, disconnecting");
      client.stop();
    }
    
    // Read and process commands
    if (client.available() > 0) {
      String cmd = client.readStringUntil('\n');
      cmd.trim();
      if (cmd.length() > 0) {
        last_client_activity = millis();
        Serial.println("WiFi CMD: " + cmd);
        parse_command(cmd);
      }
    }
  }
  #endif
  
  // Also handle USB Serial commands (for debugging/development)
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() > 0) {
      Serial.println("USB CMD: " + cmd);
      parse_command(cmd);
    }
  }
  
  // Update LED animation if in moving state
  #ifdef HAS_LED_MATRIX
  updateSpinAnimation();
  #endif
}
