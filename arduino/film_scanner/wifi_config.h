/*
 * WiFi Configuration for Arduino R4 WiFi
 * 
 * Configure your WiFi network settings here.
 * This file is used by the film_scanner.ino firmware.
 */

#ifndef WIFI_CONFIG_H
#define WIFI_CONFIG_H

// ============================================================================
// WiFi Network Settings
// ============================================================================

// Your WiFi network name (SSID)
const char* WIFI_SSID = "YOUR_WIFI_SSID";

// Your WiFi password
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// ============================================================================
// Network Configuration
// ============================================================================

// TCP Server Port (default: 8888)
// The Raspberry Pi will connect to this port
const uint16_t TCP_PORT = 8888;

// Static IP Configuration (optional)
// Set USE_STATIC_IP to true if you want a fixed IP address
// This makes it easier to find the Arduino on your network
const bool USE_STATIC_IP = false;

// If USE_STATIC_IP is true, configure these:
const char* STATIC_IP = "192.168.1.100";      // Arduino's IP address
const char* GATEWAY = "192.168.1.1";          // Your router's IP
const char* SUBNET = "255.255.255.0";         // Subnet mask (usually this)
const char* DNS_SERVER = "192.168.1.1";       // DNS server (usually same as gateway)

// ============================================================================
// Connection Settings
// ============================================================================

// Maximum number of WiFi connection attempts before giving up
const int WIFI_MAX_RETRIES = 20;

// Delay between WiFi connection attempts (milliseconds)
const int WIFI_RETRY_DELAY = 500;

// Client timeout (milliseconds)
// If no data received for this long, disconnect client
const unsigned long CLIENT_TIMEOUT = 5000;

// ============================================================================
// Debug Settings
// ============================================================================

// Enable verbose WiFi debugging over USB Serial
// Useful for initial setup, can disable later for performance
const bool WIFI_DEBUG = true;

#endif // WIFI_CONFIG_H
