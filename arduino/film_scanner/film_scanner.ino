/*
 * 35mm Film Scanner - Motor Control
 * 
 * Hardware:
 * - Motor: NEMA 17 BJ42D22-23V01 (Creality 42-40)
 * - Driver: A4988 Stepper Driver
 * 
 * Arduino Connections:
 * D2 -> STEP
 * D3 -> DIR  
 * D4 -> ENABLE
 * GND -> Driver GND (CRITICAL: common ground with 12V supply!)
 * 
 * Power:
 * 12V -> Driver VMOT
 * 12V GND -> Driver GND + Arduino GND
 * 5V -> Driver VDD
 */

const int STEP_PIN = 2;
const int DIR_PIN = 3;
const int ENABLE_PIN = 4;

int steps_per_frame = 1200;
int fine_step = 8;
int coarse_step = 64;
int step_delay_us = 800;
int backlash_steps = 20;

int last_direction = 0;
bool motion_locked = false;
long position = 0;

void setup() {
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(ENABLE_PIN, OUTPUT);
  
  digitalWrite(ENABLE_PIN, LOW);
  digitalWrite(DIR_PIN, LOW);
  digitalWrite(STEP_PIN, LOW);
  
  Serial.begin(115200);
  while (!Serial) {
    ;
  }
  
  Serial.println("READY NEMA17");
  Serial.println("Film Scanner Motor Control");
}

void move_steps(int steps, int direction) {
  if (motion_locked) {
    Serial.println("LOCKED");
    return;
  }
  
  int total_steps = steps;
  if (last_direction != 0 && last_direction != direction) {
    total_steps += backlash_steps;
  }
  last_direction = direction;
  
  digitalWrite(DIR_PIN, direction == 1 ? HIGH : LOW);
  delayMicroseconds(5);
  
  for (int i = 0; i < total_steps; i++) {
    digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(step_delay_us);
    digitalWrite(STEP_PIN, LOW);
    delayMicroseconds(step_delay_us);
    
    position += direction;
  }
  
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
    case 'f':
      move_steps(fine_step, 1);
      break;
    case 'b':
      move_steps(fine_step, -1);
      break;
    case 'F':
      move_steps(coarse_step, 1);
      break;
    case 'B':
      move_steps(coarse_step, -1);
      break;
    case 'N':
      move_steps(steps_per_frame, 1);
      break;
    case 'R':
      move_steps(steps_per_frame, -1);
      break;
    case 'H':
      if (value > 0 && value < 10000) {
        move_steps(value, 1);
      }
      break;
    case 'h':
      if (value > 0 && value < 10000) {
        move_steps(value, -1);
      }
      break;
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
    case 'X':
      motion_locked = true;
      digitalWrite(ENABLE_PIN, HIGH);
      Serial.println("LOCKED");
      break;
    case 'U':
      motion_locked = false;
      digitalWrite(ENABLE_PIN, LOW);
      Serial.println("UNLOCKED");
      break;
    case 'M':
      digitalWrite(ENABLE_PIN, HIGH);
      Serial.println("MOTOR OFF");
      break;
    case 'E':
      digitalWrite(ENABLE_PIN, LOW);
      Serial.println("MOTOR ON");
      break;
    case 'P':
      Serial.print("POS:");
      Serial.println(position);
      break;
    case 'Z':
      position = 0;
      Serial.println("ZEROED");
      break;
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
      break;
    default:
      Serial.print("UNKNOWN:");
      Serial.println(command);
      break;
  }
}

void loop() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    parse_command(cmd);
  }
}
