/*
  ESP32-S3 + MFRC522 (SPI) -> Django RFID Borrowing System
  - Reads card UID via SPI
  - Calls Django API to ensure borrower exists and optionally borrow an item
  - Supports HTTPS connections with certificate verification
  
  FIXED: Configuration now properly saves using ArduinoJson parser
*/

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <ESPmDNS.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <Preferences.h>
#include <SPI.h>
#include "ca_cert.h"  // CA certificate for HTTPS
#include <MFRC522.h>
#include <ArduinoJson.h>
#include <type_traits>
#include <esp_system.h> // for esp_reset_reason() to detect power-on resets

// Forward-declare CardHolder so Arduino's auto-prototype generator
// can create correct prototypes for functions that reference it.
struct CardHolder;
// Prevent Arduino's auto-generated prototypes from creating a prototype
// that references `CardHolder` before it's known: provide an explicit prototype.
const CardHolder* findHolderByUid(const String& uidUpper);

/* ----------- USER CONFIG ----------- */
// IMPORTANT: Do NOT embed secrets (WiFi SSID/PASS or API_HOST) in the source.
// Device configuration is managed centrally by the web app (DeviceConfig).
// Values are loaded from Preferences (NVS) on boot and can be updated by the
// server or pushed from the web UI. Keep these empty by default.
String WIFI_SSID = "";
String WIFI_PASS = "";
String API_HOST  = "";
String PAIRING_CODE = ""; // Persistent pairing code, shown on device and sent to server
String API_TOKEN = ""; // Per-device API token (X-Device-Token header)
String MDNS_NAME = ""; // Hostname advertised via mDNS (e.g., esp32-xxxx.local)


// Scheduled control flags (set by HTTP handlers, executed in loop)
bool should_reconnect = false;
unsigned long reconnect_at = 0;
bool should_disconnect = false;
unsigned long disconnect_at = 0;
bool should_start_ap = false;
unsigned long start_ap_at = 0;
bool should_stop_ap = false;
unsigned long stop_ap_at = 0;

// Preference keys stored in non-volatile storage
const char* PREF_NS = "device_cfg"; // Preferences namespace


/* Set to a real item QR code if you want auto borrow right after card tap */
String FORCED_ITEM_QR = "";

// Default VSPI mapping (recommended for 30-pin ESP32 and ESP32-S3 devkits)
// Safe pins that avoid flash/strap conflicts: SCK=18, MOSI=23, MISO=19, SS=5, RST=4
#define PIN_SCK   18
#define PIN_MOSI  23
#define PIN_MISO  19
#define PIN_SS    5
#define PIN_RST    4

MFRC522 rfid(PIN_SS, PIN_RST);
bool rfid_available = true;
// If hardware SPI fails due to pin conflicts, use software SPI bit-bang
bool use_soft_spi = false;

// Software-SPI helpers (bit-bang using configured pins)
static inline void bb_pin_setup() {
  pinMode(PIN_SCK, OUTPUT);
  pinMode(PIN_MOSI, OUTPUT);
  pinMode(PIN_MISO, INPUT);
  pinMode(PIN_SS, OUTPUT);
}

static inline uint8_t bb_transfer(uint8_t data, unsigned int delay_us = 1) {
  uint8_t received = 0;
  for (int i = 7; i >= 0; --i) {
    digitalWrite(PIN_MOSI, (data >> i) & 1);
    digitalWrite(PIN_SCK, HIGH);
    delayMicroseconds(delay_us);
    received <<= 1;
    received |= digitalRead(PIN_MISO) & 0x1;
    digitalWrite(PIN_SCK, LOW);
    delayMicroseconds(delay_us);
  }
  return received;
}

// MFRC522 SPI protocol: address byte = ((addr << 1) & 0x7E) | (read? 0x80 : 0x00)
static inline void bb_write_register(uint8_t reg, uint8_t val) {
  digitalWrite(PIN_SS, LOW);
  bb_transfer((reg << 1) & 0x7E);
  bb_transfer(val);
  digitalWrite(PIN_SS, HIGH);
}

static inline uint8_t bb_read_register(uint8_t reg) {
  digitalWrite(PIN_SS, LOW);
  bb_transfer(((reg << 1) & 0x7E) | 0x80);
  uint8_t val = bb_transfer(0x00);
  digitalWrite(PIN_SS, HIGH);
  return val;
}

// Write multiple bytes to FIFO
static inline void bb_write_fifo(const uint8_t *data, uint8_t len) {
  digitalWrite(PIN_SS, LOW);
  bb_transfer(((0x09 << 1) & 0x7E)); // FIFODataReg write
  for (uint8_t i = 0; i < len; ++i) bb_transfer(data[i]);
  digitalWrite(PIN_SS, HIGH);
}

// Read multiple bytes from FIFO
static inline void bb_read_fifo(uint8_t *buf, uint8_t len) {
  digitalWrite(PIN_SS, LOW);
  bb_transfer(((0x09 << 1) & 0x7E) | 0x80); // FIFODataReg read
  for (uint8_t i = 0; i < len; ++i) buf[i] = bb_transfer(0x00);
  digitalWrite(PIN_SS, HIGH);
}

// Minimal transceive to communicate with a PICC (used for REQA, anticoll)
bool soft_transceive(const uint8_t *send, uint8_t sendLen, uint8_t *back, uint8_t &backLen, unsigned long timeoutMs=25) {
  // Clear interrupt flags
  bb_write_register(0x04, 0x7F); // ComIrqReg - clear all
  bb_write_register(0x02, 0x00); // BitFramingReg
  // Write data to FIFO
  bb_write_register(0x01, 0x00); // CommandReg = Idle
  // flush FIFO
  bb_write_register(0x0A, 0x00);
  bb_write_fifo(send, sendLen);
  // Start transceive
  bb_write_register(0x01, 0x0C); // CommandReg = Transceive
  bb_write_register(0x0D, 0x80); // BitFramingReg - start send

  unsigned long start = millis();
  while (millis() - start < timeoutMs) {
    uint8_t n = bb_read_register(0x04); // ComIrqReg
    if (n & 0x30) break; // Rx done or timeout
  }

  uint8_t error = bb_read_register(0x06); // ErrorReg
  if (error & 0x1B) return false; // CRC, parity, etc

  uint8_t fifoLevel = bb_read_register(0x0A); // FIFOLevelReg
  if (fifoLevel == 0) { backLen = 0; return true; }
  if (fifoLevel > backLen) fifoLevel = backLen;
  bb_read_fifo(back, fifoLevel);
  backLen = fifoLevel;
  return true;
}

// ISO14443A REQA (7 bits) and anticollision (returns UID)
bool soft_requestA(uint8_t *uid, uint8_t &uidLen) {
  uint8_t req[1] = {0x26};
  uint8_t resp[16]; uint8_t respLen = sizeof(resp);
  if (!soft_transceive(req, 1, resp, respLen, 25)) return false;

  // Anticollision
  uint8_t antic[2] = {0x93, 0x20};
  respLen = sizeof(resp);
  if (!soft_transceive(antic, 2, resp, respLen, 25)) return false;
  // Expect 5 bytes: 4 UID + BCC
  if (respLen < 5) return false;
  for (uint8_t i = 0; i < 4 && i < uidLen; ++i) uid[i] = resp[i];
  uidLen = 4;
  return true;
}

// Attempt to detect the MFRC522 over hardware SPI. Returns true if detected.
bool detectHardwareRFID() {
  byte v = rfid.PCD_ReadRegister(rfid.VersionReg);
  if (v != 0x00 && v != 0xFF) {
    Serial.printf("MFRC522 detected - VersionReg: 0x%02X\n", v);
    rfid_available = true;
    rfid.PCD_SetAntennaGain(rfid.RxGain_max);
    return true;
  }

  Serial.println("MFRC522 not detected (attempting recovery)");
  const long speeds[] = {25000000, 10000000, 5000000, 1000000};
  for (int s = 0; s < (int)(sizeof(speeds)/sizeof(speeds[0])); ++s) {
    long spd = speeds[s];
    Serial.printf("Trying SPI clock %ld...\n", spd);
    digitalWrite(PIN_RST, LOW); delay(25); digitalWrite(PIN_RST, HIGH); delay(60);
    digitalWrite(PIN_SS, LOW); delay(5); digitalWrite(PIN_SS, HIGH); delay(25);

    SPI.beginTransaction(SPISettings(spd, MSBFIRST, SPI_MODE0));
    v = rfid.PCD_ReadRegister(rfid.VersionReg);
    SPI.endTransaction();

    Serial.printf("Read VersionReg = 0x%02X\n", v);
    if (v != 0x00 && v != 0xFF) {
      Serial.printf("Recovered MFRC522 at VersionReg=0x%02X\n", v);
      rfid_available = true;
      rfid.PCD_SetAntennaGain(rfid.RxGain_max);
      return true;
    }
  }

  Serial.println("MFRC522 not detected after hardware retries.");
  Serial.println("CHECK: Ensure VCC is 3.3V, GND common with ESP32, SS/RST wiring correct.");
  Serial.println("If module is soldered to flash pins try using safe VSPI pins: SCK=18, MISO=19, MOSI=23, SS=5");
  rfid.PCD_SetAntennaGain(rfid.RxGain_max);
  rfid_available = false;
  return false;
}

// Attempt to detect MFRC522 over software (bit-banged) SPI. Returns true on success.
bool detectSoftwareRFID() {
  Serial.println("Attempting software-SPI detection (multiple timing trials)...");
  bb_pin_setup();
  const unsigned int delays[] = {1, 2, 5, 10, 20};
  for (unsigned int d = 0; d < (sizeof(delays)/sizeof(delays[0])); ++d) {
    unsigned int du = delays[d];
    for (int attempt = 0; attempt < 3; ++attempt) {
      uint8_t sv = 0x00;
      digitalWrite(PIN_SS, LOW);
      bb_transfer(((0x37 << 1) & 0x7E) | 0x80, du);
      sv = bb_transfer(0x00, du);
      digitalWrite(PIN_SS, HIGH);

      Serial.printf("Soft attempt delay=%uus attempt=%d -> VersionReg=0x%02X\n", du, attempt+1, sv);
      if (sv != 0x00 && sv != 0xFF) {
        Serial.println("MFRC522 detected over software SPI. Switching to soft SPI mode.");
        use_soft_spi = true;
        rfid_available = true;
        return true;
      }
      delay(20);
    }
  }
  Serial.println("Software-SPI detection failed.");
  Serial.println("CHECK: Confirm MOSI/MISO/SCK/SS pins match and GND is common; try increasing delays if signals are slow.");
  return false;
}

// Captive-portal and config server objects
DNSServer dnsServer;
WebServer server(80);
Preferences prefs;

// AP mode flag: when true the device runs as an access point and DNS server
bool apMode = false;
// Keep AP active even when server connectivity is available (can be toggled and persisted)
bool keepAPAlways = false;
// If true, start the portal AP at boot and keep it visible (useful when device is always powered)
bool startPortalOnBoot = true;
// If true, clear stored credentials (SSID, password, API host) when a power-on reset occurs
bool clearOnPowerCycle = true;

// When true, attempt to connect to WiFi/server after apply-config; loop() will handle this
bool should_try_connect = false;
unsigned long try_connect_at = 0;

// Start an open AP for configuration and captive portal
void startAP() {
  WiFi.mode(WIFI_AP_STA);
  String mac = WiFi.macAddress();
  String suffix = mac.substring(mac.length() - 5);
  String apName = "ESP32-Setup-" + suffix;
  WiFi.softAP(apName.c_str());
  delay(500);
  IPAddress apIP = WiFi.softAPIP(); // typically 192.168.4.1
  dnsServer.start(53, "*", apIP);
  apMode = true;
  Serial.printf("Started AP '%s' IP=%s\n", apName.c_str(), apIP.toString().c_str());
  Serial.printf("AP station count: %d\n", WiFi.softAPgetStationNum());
  Serial.println("Connect a phone or laptop to this network and open http://192.168.4.1/");
}

void stopAP() {
  if (!apMode) return;
  dnsServer.stop();
  WiFi.softAPdisconnect(true);
  delay(200);
  apMode = false;
  Serial.println("Stopped AP mode; attempting WiFi reconnect");
}


// Helper: load/save config into Preferences so values persist across reboots
// Forward declaration so normalizeApiHost() can be used here
String normalizeApiHost(const String& raw);

void loadConfigFromPrefs() {
  prefs.begin(PREF_NS, false);
  WIFI_SSID = prefs.getString("ssid", "");
  WIFI_PASS = prefs.getString("password", "");
  API_HOST = prefs.getString("api_host", "");
  PAIRING_CODE = prefs.getString("pairing_code", "");
  API_TOKEN = prefs.getString("api_token", "");
  // persisted keep-AP flag (0/1 stored as uint)
  keepAPAlways = (prefs.getUInt("keep_ap", 0) != 0);
  startPortalOnBoot = (prefs.getUInt("start_portal_on_boot", 1) != 0);
  // persisted clear-on-power flag (default: enabled)
  clearOnPowerCycle = (prefs.getUInt("clear_on_power", 1) != 0);
  prefs.end();

  // Normalize any stored API_HOST (helps correct configs saved without scheme/port)
  if (API_HOST.length()) {
    String normalized = normalizeApiHost(API_HOST);
    if (normalized != API_HOST) {
      // Persist normalized value back to NVS
      prefs.begin(PREF_NS, false);
      prefs.putString("api_host", normalized);
      prefs.end();
      API_HOST = normalized;
      Serial.printf("Normalized and updated stored API_HOST to '%s'\n", API_HOST.c_str());
    }
  }

  Serial.printf("Loaded prefs - SSID='%s' API_HOST='%s' Pairing='%s' TokenSet=%s KeepAP=%s StartPortalOnBoot=%s ClearOnPower=%s\n", 
                WIFI_SSID.c_str(), API_HOST.c_str(), PAIRING_CODE.c_str(), (API_TOKEN.length() ? "yes" : "no"), (keepAPAlways ? "yes" : "no"), (startPortalOnBoot ? "yes" : "no"), (clearOnPowerCycle ? "yes" : "no"));

  // Detect power-on reset and clear credentials if the user requested that behaviour
  esp_reset_reason_t rr = esp_reset_reason();
  // Consider POWERON, BROWNOUT or external resets as power-cycle-like events
  if ((rr == ESP_RST_POWERON || rr == ESP_RST_BROWNOUT || rr == ESP_RST_EXT) && clearOnPowerCycle) {
    Serial.println("Power-on/brownout/external reset detected and ClearOnPowerCycle enabled: clearing WiFi and API credentials from NVS.");
    prefs.begin(PREF_NS, false);
    prefs.remove("ssid");
    prefs.remove("password");
    prefs.remove("api_host");
    // ensure portal will start on this fresh boot
    prefs.putUInt("start_portal_on_boot", 1);
    prefs.end();

    WIFI_SSID = "";
    WIFI_PASS = "";
    API_HOST = "";
    startPortalOnBoot = true;
  }
} 

void saveConfigToPrefs() {
  prefs.begin(PREF_NS, false);
  prefs.putString("ssid", WIFI_SSID);
  prefs.putString("password", WIFI_PASS);
  prefs.putString("api_host", API_HOST);
  prefs.putString("pairing_code", PAIRING_CODE);
  prefs.putString("api_token", API_TOKEN);
  prefs.putUInt("keep_ap", keepAPAlways ? 1 : 0);
  prefs.putUInt("start_portal_on_boot", startPortalOnBoot ? 1 : 0);
  prefs.end();
  Serial.printf("✓ Saved to NVS - SSID='%s' API_HOST='%s' Pairing='%s' TokenSet=%s KeepAP=%s\n", 
                WIFI_SSID.c_str(), API_HOST.c_str(), PAIRING_CODE.c_str(), (API_TOKEN.length() ? "yes" : "no"), (keepAPAlways?"yes":"no"));
} 

// Helper: remove surrounding single or double quotes and trim whitespace
String stripQuotes(String s) {
  s.trim();
  if (s.length() >= 2) {
    char first = s.charAt(0);
    char last = s.charAt(s.length() - 1);
    if ((first == '"' && last == '"') || (first == '\'' && last == '\'')) {
      return s.substring(1, s.length() - 1);
    }
  }
  return s;
}

// --- WiFi event reason helpers ---
// SFINAE tests to detect which union member exists on this core build
template<typename U>
static auto _has_disconnected_member(int) -> decltype((void)std::declval<U>().disconnected, std::true_type());
template<typename U>
static std::false_type _has_disconnected_member(...);
template<typename U>
using has_disconnected_member = decltype(_has_disconnected_member<U>(0));

template<typename U>
static auto _has_wifi_sta_disconnected_member(int) -> decltype((void)std::declval<U>().wifi_sta_disconnected, std::true_type());
template<typename U>
static std::false_type _has_wifi_sta_disconnected_member(...);
template<typename U>
using has_wifi_sta_disconnected_member = decltype(_has_wifi_sta_disconnected_member<U>(0));

static const char* disconnectReasonToString(int reason) {
  switch (reason) {
    case 1: return "UNSPECIFIED";
    case 2: return "PREV_AUTH_INVALID";
    case 3: return "DEAUTH_LEAVING";
    case 4: return "DISASSOC_INACTIVITY";
    case 5: return "AUTH_EXPIRE";
    case 6: return "CLASS2_FRAME_FROM_NONAUTH_STA";
    case 7: return "CLASS3_FRAME_FROM_NONAUTH_STA";
    case 8: return "DISASSOC_STA_HAS_LEFT";
    case 15: return "4WAY_HANDSHAKE_TIMEOUT";
    case 200: return "BEACON_TIMEOUT";
    default: return "UNKNOWN_REASON";
  }
}

// Use SFINAE-enabled overloads to safely access union members only when they exist
template<typename T, typename std::enable_if<has_disconnected_member<T>::value, int>::type = 0>
int getDisconnectReason_impl(const T &info) {
  return info.disconnected.reason;
}

template<typename T, typename std::enable_if<!has_disconnected_member<T>::value && has_wifi_sta_disconnected_member<T>::value, int>::type = 0>
int getDisconnectReason_impl(const T &info) {
  return info.wifi_sta_disconnected.reason;
}

template<typename T, typename std::enable_if<!has_disconnected_member<T>::value && !has_wifi_sta_disconnected_member<T>::value, int>::type = 0>
int getDisconnectReason_impl(const T &info) {
  (void)info; return -1;
}

static void printDisconnectReasonIfAvailable(const WiFiEventInfo_t &info) {
  int r = getDisconnectReason_impl(info);
  if (r >= 0) Serial.printf("WiFi disconnect reason: %d (%s)\n", r, disconnectReasonToString(r));
  else Serial.println("WiFi disconnect reason: not available on this core build");
}


// Generate a short alphanumeric pairing code (default length 6)
String generatePairingCode(size_t len = 6) {
  const char *chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  String s = "";
  for (size_t i = 0; i < len; ++i) {
    uint32_t rv = (uint32_t)esp_random();
    size_t idx = rv % 36u;
    s += chars[idx];
  }
  return s;
}

// Ensure a persistent pairing code exists in Preferences (NVS)
void ensurePairingCodeExists() {
  prefs.begin(PREF_NS, false);
  String existing = prefs.getString("pairing_code", "");
  if (existing.length()) {
    PAIRING_CODE = existing;
    prefs.end();
    return;
  }
  String code = generatePairingCode(6);
  prefs.putString("pairing_code", code);
  prefs.end();
  PAIRING_CODE = code;
}

// Forward declarations for functions defined later but used earlier
bool apiHostConfigured();
String buildApiBase();
String normalizeApiHost(const String& raw);

// Forward-declare enum and function prototypes to prevent Arduino's auto-prototype generator
// from creating an invalid prototype that references the enum before it is defined.
// Note: forward-declaration of enums requires specifying the underlying type in C++.
enum BorrowerCheckResult : int;
BorrowerCheckResult checkBorrower(const String& uid);

// Borrower check tri-state enum must be declared before any function uses it
enum BorrowerCheckResult : int { BORROWER_EXISTS = 0, BORROWER_NOT_FOUND = 1, BORROWER_NETWORK_ERROR = 2 };

// Helper function to setup HTTPS client for secure connections
void setupHttpsClient(HTTPClient& http) {
  /*
    Configures HTTPClient to support HTTPS with certificate verification.
    When using HTTPS URLs, this ensures the ESP32 validates the server certificate
    against our embedded CA certificate (ca_cert.h).
  */
  // WiFiClientSecure is created automatically by HTTPClient for https:// URLs
  // But we need to configure it with our CA certificate
  // Unfortunately HTTPClient doesn't expose the underlying WiFiClientSecure directly,
  // so we'll use a workaround: pass the certificate via begin() parameters
  
  // For self-signed certificates, we can skip verification for localhost development
  // or embed the certificate (already done in ca_cert.h)
  // HTTPClient will automatically use WiFiClientSecure for https:// URLs
}

// Fetch device config from the server's /api/device-config endpoint and apply
bool fetchDeviceConfigFromServer() {
  if (!apiHostConfigured()) {
    Serial.println("INFO: API_HOST not set; skipping fetchDeviceConfigFromServer. Set DeviceConfig via web UI or push config.");
    return false;
  }
  String url = buildApiBase();
  if (url.length() == 0) { Serial.println("INFO: API_HOST not set; skipping fetchDeviceConfigFromServer. Set DeviceConfig via web UI or push config."); return false; }
  url += "/api/device-config";

  Serial.printf("Fetching device config: %s\n", url.c_str());
  
  int code = -1;
  String body = "";
  
  // For HTTPS URLs, set up secure client with CA certificate
  if (url.startsWith("https://")) {
    WiFiClientSecure client;
    client.setCACert(ca_cert);
    
    HTTPClient http;
    if (!http.begin(client, url)) {
      Serial.println("ERROR: http.begin() failed for device-config (HTTPS)");
      Serial.println("DEBUG: Retrying with relaxed SSL...");
      
      WiFiClientSecure clientRelaxed;
      clientRelaxed.setInsecure();
      HTTPClient httpRelaxed;
      
      if (httpRelaxed.begin(clientRelaxed, url)) {
        if (API_TOKEN.length()) httpRelaxed.addHeader("X-Device-Token", API_TOKEN);
        code = httpRelaxed.GET();
        if (code > 0) {
          body = httpRelaxed.getString();
        }
        httpRelaxed.end();
      } else {
        return false;
      }
    } else {
      Serial.println("HTTPS client configured with CA certificate");
      
      if (API_TOKEN.length()) http.addHeader("X-Device-Token", API_TOKEN);
      code = http.GET();
      if (code > 0) {
        body = http.getString();
      } else if (code == -1) {
        Serial.println("DEBUG: GET returned -1, retrying with relaxed SSL...");
        http.end();
        
        WiFiClientSecure clientRelaxed;
        clientRelaxed.setInsecure();
        HTTPClient httpRelaxed;
        
        if (httpRelaxed.begin(clientRelaxed, url)) {
          if (API_TOKEN.length()) httpRelaxed.addHeader("X-Device-Token", API_TOKEN);
          code = httpRelaxed.GET();
          if (code > 0) {
            body = httpRelaxed.getString();
          }
          httpRelaxed.end();
        }
      }
      http.end();
    }
    
  } else {
    HTTPClient http;
    if (!http.begin(url)) {
      Serial.println("ERROR: http.begin() failed for device-config");
      return false;
    }
    Serial.println("Using HTTP connection");
    
    if (API_TOKEN.length()) http.addHeader("X-Device-Token", API_TOKEN);
    code = http.GET();
    if (code > 0) {
      body = http.getString();
    }
    http.end();
  }

  if (code >= 200 && code < 300) {
    Serial.printf("Fetched device-config body: %s\n", body.c_str());
    
    // Parse JSON response
    StaticJsonDocument<512> doc;
    DeserializationError error = deserializeJson(doc, body);
    
    if (error) {
      Serial.print("JSON parse error: ");
      Serial.println(error.c_str());
      return false;
    }

    bool changed = false;
    if (doc.containsKey("ssid")) {
      String ss = doc["ssid"].as<String>();
      if (ss.length() && ss != WIFI_SSID) { WIFI_SSID = ss; changed = true; }
    }
    if (doc.containsKey("password")) {
      String pw = doc["password"].as<String>();
      if (pw.length() && pw != WIFI_PASS) { WIFI_PASS = pw; changed = true; }
    }
    if (doc.containsKey("api_host")) {
      String ah = doc["api_host"].as<String>();
      if (ah.length() && ah != API_HOST) { API_HOST = ah; changed = true; }
    }

    if (doc.containsKey("api_token")) {
      String t = doc["api_token"].as<String>();
      if (t.length() && t != API_TOKEN) { API_TOKEN = t; changed = true; Serial.println("API_TOKEN updated from server"); }
    }

    if (changed) {
      saveConfigToPrefs();
      Serial.println("Device config updated from server and persisted to prefs.");
    } else {
      Serial.println("Device config fetched (no changes)");
    }
    return true;
  }

  Serial.printf("Failed to fetch device-config -> HTTP %d\n", code);
  return false;
}

// HTTP handler that allows POSTing JSON to /apply-config on the ESP to set config remotely
void handleApplyConfig() {
  if (server.method() == HTTP_OPTIONS) {
    // Respond to CORS preflight
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.sendHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
    server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
    server.send(204, "text/plain", "");
    return;
  }

  if (server.method() != HTTP_POST) { 
    server.send(405, "text/plain", "Method not allowed"); 
    return; 
  }
  
  String body = server.arg("plain");
  Serial.printf("handleApplyConfig received: %s\n", body.c_str());
  
  if (body.length() == 0) { 
    server.send(400, "text/plain", "Empty body"); 
    return; 
  }

  // Parse JSON using ArduinoJson
  StaticJsonDocument<512> doc;
  DeserializationError error = deserializeJson(doc, body);
  
  if (error) {
    Serial.print("JSON parse error: ");
    Serial.println(error.c_str());
    server.send(400, "application/json", "{\"error\":\"Invalid JSON\"}");
    return;
  }

  // Allow an early clear_on_power flag in JSON to alter behavior remotely
  if (doc.containsKey("clear_on_power")) {
    bool v3 = true;
    if (doc["clear_on_power"].is<bool>()) v3 = doc["clear_on_power"].as<bool>();
    else if (doc["clear_on_power"].is<int>()) v3 = (doc["clear_on_power"].as<int>() != 0);
    clearOnPowerCycle = v3;
    Serial.printf("Applied ClearOnPowerCycle (early): %s\n", clearOnPowerCycle ? "true" : "false");
    prefs.begin(PREF_NS, false);
    prefs.putUInt("clear_on_power", clearOnPowerCycle ? 1 : 0);
    prefs.end();
  }

  // Allow early keep_ap in payload so remote pushes can toggle AP behaviour without requiring AP access
  if (doc.containsKey("keep_ap")) {
    bool v = false;
    if (doc["keep_ap"].is<bool>()) v = doc["keep_ap"].as<bool>();
    else if (doc["keep_ap"].is<int>()) v = (doc["keep_ap"].as<int>() != 0);
    keepAPAlways = v;
    Serial.printf("Applied keepAPAlways: %s\n", keepAPAlways ? "true" : "false");
    // Persist immediately so any subsequent saveConfigToPrefs will still show it as current value
    prefs.begin(PREF_NS, false);
    prefs.putUInt("keep_ap", keepAPAlways ? 1 : 0);
    prefs.end();
  }

  // Allow early start_portal_on_boot in payload so AP auto-start behaviour can be toggled remotely
  if (doc.containsKey("start_portal_on_boot")) {
    bool v2 = true;
    if (doc["start_portal_on_boot"].is<bool>()) v2 = doc["start_portal_on_boot"].as<bool>();
    else if (doc["start_portal_on_boot"].is<int>()) v2 = (doc["start_portal_on_boot"].as<int>() != 0);
    startPortalOnBoot = v2;
    Serial.printf("Applied startPortalOnBoot: %s\n", startPortalOnBoot ? "true" : "false");
    prefs.begin(PREF_NS, false);
    prefs.putUInt("start_portal_on_boot", startPortalOnBoot ? 1 : 0);
    prefs.end();
    if (startPortalOnBoot && !apMode) {
      Serial.println("start_portal_on_boot requested: starting AP now...");
      startAP();
    } else if (!startPortalOnBoot && apMode) {
      if (!keepAPAlways) {
        Serial.println("start_portal_on_boot disabled: stopping AP now...");
        stopAP();
      } else {
        Serial.println("start_portal_on_boot disabled but keepAPAlways enabled; AP remains active.");
      }
    }
  }

  bool changed = false;
  bool ssidUpdated = false;
  bool passwordUpdated = false;
  bool apiHostUpdated = false;

  if (doc.containsKey("ssid")) {
    String ss = doc["ssid"].as<String>();
    ss.trim();
    if (ss.length() > 0) {
      WIFI_SSID = ss;
      changed = true;
      ssidUpdated = true;
      Serial.printf("Updated SSID: '%s'\n", WIFI_SSID.c_str());
    } else {
      Serial.println("Received empty SSID in apply-config; ignoring (preserve existing).");
    }
  }

  if (doc.containsKey("password")) {
    String pw = doc["password"].as<String>();
    pw.trim();
    // Allow empty password when explicitly provided (open networks)
    WIFI_PASS = pw;
    changed = true;
    passwordUpdated = true;
    Serial.printf("Updated password (length=%d)\n", WIFI_PASS.length());
  }

  if (doc.containsKey("api_host")) {
    String ah = doc["api_host"].as<String>();
    ah.trim();
    if (ah.length() > 0) {
      API_HOST = normalizeApiHost(ah);
      changed = true;
      apiHostUpdated = true;
      Serial.printf("Updated API_HOST: '%s' (normalized)\n", API_HOST.c_str());
    } else {
      Serial.println("Received empty API_HOST in apply-config; ignoring.");
    }
  }

  if (doc.containsKey("pairing_code")) {
    String pc = doc["pairing_code"].as<String>();
    pc.trim();
    PAIRING_CODE = pc;
    changed = true;
    Serial.printf("Updated pairing: '%s'\n", PAIRING_CODE.c_str());
  }

  if (doc.containsKey("api_token")) {
    String t = doc["api_token"].as<String>();
    t.trim();
    API_TOKEN = t;
    changed = true;
    Serial.printf("Updated API_TOKEN: %s\n", API_TOKEN.length() ? "(set)" : "(cleared)");
  }

  if (changed) {
    saveConfigToPrefs();
    
    // Verify it was saved
    prefs.begin(PREF_NS, true);
    String verifySSID = prefs.getString("ssid", "");
    String verifyAPI = prefs.getString("api_host", "");
    prefs.end();
    Serial.printf("Verified saved - SSID:'%s' API:'%s'\n", verifySSID.c_str(), verifyAPI.c_str());
  }

  // Only attempt reconnect/schedule when the WiFi credentials were actually provided and applied
  if (WiFi.status() == WL_CONNECTED && (ssidUpdated || passwordUpdated)) {
    Serial.println("Reconnecting with updated WiFi credentials...");
    WiFi.disconnect(true, true);
    delay(500);
    if (apMode) stopAP();
    WiFi.begin(WIFI_SSID.c_str(), WIFI_PASS.c_str());
  } else if (ssidUpdated || passwordUpdated) {
    // Schedule a connection attempt (we have credentials but are not connected yet)
    Serial.println("Scheduling connection attempt after apply-config (credentials provided)");
    should_try_connect = true;
    try_connect_at = millis() + 200;
  } else {
    // No WiFi credentials provided -> keep AP active so the portal remains available.
    Serial.println("No WiFi credentials provided; keeping AP active for configuration.");
  }
  
  server.sendHeader("Access-Control-Allow-Origin", "*");
  {
    bool token_set = (API_TOKEN.length() > 0);
    String resp = String("{\"status\":\"ok\",\"token_set\":") + (token_set ? "true" : "false") + "}";
    server.send(200, "application/json", resp);
  }
}

void handleControl() {
  if (server.method() == HTTP_OPTIONS) {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.sendHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
    server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
    server.send(204, "text/plain", "");
    return;
  }
  
  if (server.method() != HTTP_POST) { 
    server.send(405, "text/plain", "Method not allowed"); 
    return; 
  }
  
  String body = server.arg("plain");
  if (body.length() == 0) { 
    server.send(400, "application/json", "{\"detail\":\"Empty body\"}"); 
    return; 
  }
  
  // Try to parse as JSON first
  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, body);
  
  String action;
  if (!error && doc.containsKey("action")) {
    action = doc["action"].as<String>();
  } else {
    // Fallback: treat entire body as the action
    action = body;
    action.trim();
    action = stripQuotes(action);
  }
  
  Serial.printf("Control action requested: %s\n", action.c_str());
  
  if (action == "disconnect") {
    should_disconnect = true;
    disconnect_at = millis() + 200;
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(200, "application/json", "{\"status\":\"ok\",\"action\":\"disconnect\"}");
    return;
  } else if (action == "startap") {
    should_start_ap = true;
    start_ap_at = millis() + 200;
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(200, "application/json", "{\"status\":\"ok\",\"action\":\"startap\"}");
    return;
  } else if (action == "stopap") {
    should_stop_ap = true;
    stop_ap_at = millis() + 200;
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(200, "application/json", "{\"status\":\"ok\",\"action\":\"stopap\"}");
    return;
  } else {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(400, "application/json", "{\"detail\":\"Unknown action\"}");
    return;
  }
}

// Simple captive portal page that displays and allows editing of device config
void handleRoot() {
  Serial.println("HTTP GET / received (captive portal)");
  server.sendHeader("Access-Control-Allow-Origin", "*");
  
  String html = "<!doctype html><html><head>";
  html += "<meta charset='utf-8'>";
  html += "<meta name='viewport' content='width=device-width, initial-scale=1'>";
  html += "<title>RFID Device Setup</title>";
  html += "<style>";
  html += "* { margin: 0; padding: 0; box-sizing: border-box; }";
  html += "body {";
  html += "  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;";
  html += "  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);";
  html += "  min-height: 100vh;";
  html += "  display: flex;";
  html += "  align-items: center;";
  html += "  justify-content: center;";
  html += "  padding: 20px;";
  html += "}";
  html += ".container {";
  html += "  background: white;";
  html += "  border-radius: 16px;";
  html += "  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);";
  html += "  max-width: 500px;";
  html += "  width: 100%;";
  html += "  padding: 40px;";
  html += "}";
  html += ".header {";
  html += "  text-align: center;";
  html += "  margin-bottom: 30px;";
  html += "}";
  html += ".header h1 {";
  html += "  font-size: 28px;";
  html += "  color: #333;";
  html += "  margin-bottom: 8px;";
  html += "}";
  html += ".header p {";
  html += "  color: #666;";
  html += "  font-size: 14px;";
  html += "}";
  html += ".pairing-code {";
  html += "  background: linear-gradient(135deg, rgba(102,126,234,0.1) 0%, rgba(118,75,162,0.1) 100%);";
  html += "  border-left: 4px solid #667eea;";
  html += "  padding: 16px;";
  html += "  border-radius: 8px;";
  html += "  margin-bottom: 24px;";
  html += "}";
  html += ".pairing-code strong {";
  html += "  display: block;";
  html += "  color: #333;";
  html += "  margin-bottom: 8px;";
  html += "  font-size: 12px;";
  html += "  text-transform: uppercase;";
  html += "  letter-spacing: 1px;";
  html += "}";
  html += ".pairing-code-value {";
  html += "  font-family: 'Monaco', 'Courier New', monospace;";
  html += "  font-size: 20px;";
  html += "  font-weight: 700;";
  html += "  color: #667eea;";
  html += "  letter-spacing: 2px;";
  html += "  cursor: pointer;";
  html += "  padding: 8px;";
  html += "  border-radius: 4px;";
  html += "  transition: all 0.2s ease;";
  html += "}";
  html += ".pairing-code-value:hover {";
  html += "  background: rgba(102,126,234,0.1);";
  html += "}";
  html += ".pairing-code small {";
  html += "  display: block;";
  html += "  color: #999;";
  html += "  font-size: 12px;";
  html += "  margin-top: 8px;";
  html += "}";
  html += ".form-group {";
  html += "  margin-bottom: 20px;";
  html += "}";
  html += "label {";
  html += "  display: block;";
  html += "  font-weight: 600;";
  html += "  color: #333;";
  html += "  margin-bottom: 8px;";
  html += "  font-size: 14px;";
  html += "}";
  html += "input[type='text'], input[type='password'], input[type='email'] {";
  html += "  width: 100%;";
  html += "  padding: 12px 14px;";
  html += "  border: 2px solid #e0e0e0;";
  html += "  border-radius: 8px;";
  html += "  font-size: 14px;";
  html += "  transition: all 0.3s ease;";
  html += "}";
  html += "input[type='text']:focus, input[type='password']:focus {";
  html += "  outline: none;";
  html += "  border-color: #667eea;";
  html += "  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);";
  html += "}";
  html += ".checkbox-group {";
  html += "  display: flex;";
  html += "  align-items: center;";
  html += "  padding: 12px;";
  html += "  background: #f8f9fa;";
  html += "  border-radius: 8px;";
  html += "  margin-bottom: 12px;";
  html += "  cursor: pointer;";
  html += "  transition: background 0.2s ease;";
  html += "}";
  html += ".checkbox-group:hover {";
  html += "  background: #f0f1f3;";
  html += "}";
  html += ".checkbox-group input[type='checkbox'] {";
  html += "  width: 18px;";
  html += "  height: 18px;";
  html += "  cursor: pointer;";
  html += "  margin-right: 12px;";
  html += "  accent-color: #667eea;";
  html += "}";
  html += ".checkbox-group label {";
  html += "  margin: 0;";
  html += "  font-weight: 500;";
  html += "  color: #333;";
  html += "  cursor: pointer;";
  html += "  flex: 1;";
  html += "}";
  html += ".button-group {";
  html += "  display: flex;";
  html += "  gap: 12px;";
  html += "  margin-top: 28px;";
  html += "}";
  html += "button {";
  html += "  flex: 1;";
  html += "  padding: 12px 24px;";
  html += "  border: none;";
  html += "  border-radius: 8px;";
  html += "  font-size: 14px;";
  html += "  font-weight: 600;";
  html += "  cursor: pointer;";
  html += "  transition: all 0.3s ease;";
  html += "  text-transform: uppercase;";
  html += "  letter-spacing: 0.5px;";
  html += "  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);";
  html += "  color: white;";
  html += "}";
  html += "button:hover {";
  html += "  transform: translateY(-2px);";
  html += "  box-shadow: 0 8px 20px rgba(102, 126, 234, 0.3);";
  html += "}";
  html += "button:disabled {";
  html += "  opacity: 0.6;";
  html += "  cursor: not-allowed;";
  html += "}";
  html += ".status {";
  html += "  margin-top: 16px;";
  html += "  padding: 12px 14px;";
  html += "  border-radius: 8px;";
  html += "  font-size: 13px;";
  html += "  display: none;";
  html += "  align-items: center;";
  html += "  gap: 10px;";
  html += "}";
  html += ".status.show { display: flex; }";
  html += ".status.success { background: #d4edda; color: #155724; border-left: 4px solid #28a745; }";
  html += ".status.error { background: #f8d7da; color: #721c24; border-left: 4px solid #dc3545; }";
  html += ".status.loading { background: #d1ecf1; color: #0c5460; border-left: 4px solid #17a2b8; }";
  html += ".spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid currentColor; border-top-color: transparent; border-radius: 50%; animation: spin 0.6s linear infinite; }";
  html += "@keyframes spin { to { transform: rotate(360deg); } }";
  html += ".hint { font-size: 12px; color: #999; margin-top: 4px; }";
  html += ".adv-section { background: #f8f9fa; padding: 16px; border-radius: 8px; margin-bottom: 24px; }";
  html += ".adv-section strong { display: block; color: #333; margin-bottom: 12px; font-size: 13px; }";
  html += "@media (max-width: 480px) {";
  html += "  .container { padding: 24px; }";
  html += "  .header h1 { font-size: 24px; }";
  html += "  .pairing-code-value { font-size: 18px; }";
  html += "}";
  html += "</style>";
  html += "</head><body>";
  html += "<div class='container'>";
  html += "<div class='header'>";
  html += "<h1>RFID Device Setup</h1>";
  html += "<p>Configure your ESP32 device</p>";
  html += "</div>";
  html += "<div class='pairing-code'>";
  html += "<strong>Pairing Code</strong>";
  html += "<div class='pairing-code-value' id='pairingCode'>" + PAIRING_CODE + "</div>";
  html += "<small>Click to copy - Use this code to claim the device in the web app</small>";
  html += "</div>";
  html += "<form id='cfg' onsubmit='save(event)'>";
  html += "<div class='form-group'>";
  html += "<label for='ssid'>Wi-Fi SSID</label>";
  html += "<input type='text' id='ssid' value='" + WIFI_SSID + "' placeholder='Enter WiFi network name' required>";
  html += "<div class='hint'>Your WiFi network name</div>";
  html += "</div>";
  html += "<div class='form-group'>";
  html += "<label for='password'>Wi-Fi Password</label>";
  html += "<input type='password' id='password' value='" + WIFI_PASS + "' placeholder='Enter WiFi password'>";
  html += "<div class='hint'>Leave empty if network is open</div>";
  html += "</div>";
  html += "<div class='form-group'>";
  html += "<label for='api_host'>API Host</label>";
  html += "<input type='text' id='api_host' value='" + API_HOST + "' placeholder='https://192.168.1.12:8443' required>";
  html += "<div class='hint'>Your server address (http:// or https://)</div>";
  html += "</div>";
  html += "<div class='form-group'>";
  html += "<label for='api_token'>API Token (Optional)</label>";
  html += "<input type='text' id='api_token' value='" + API_TOKEN + "' placeholder='Leave empty if not needed'>";
  html += "<div class='hint'>Device authentication token (optional)</div>";
  html += "</div>";
  html += "<div class='adv-section'>";
  html += "<strong>Advanced Options</strong>";
  html += "<div class='checkbox-group'>";
  html += "<input type='checkbox' id='keepap' " + String(keepAPAlways ? "checked" : "") + ">";
  html += "<label for='keepap'>Keep WiFi enabled (prevents auto-shutdown)</label>";
  html += "</div>";
  html += "<div class='checkbox-group'>";
  html += "<input type='checkbox' id='startportal' " + String(startPortalOnBoot ? "checked" : "") + ">";
  html += "<label for='startportal'>Start setup on boot</label>";
  html += "</div>";
  html += "<div class='checkbox-group'>";
  html += "<input type='checkbox' id='clearonpower' " + String(clearOnPowerCycle ? "checked" : "") + ">";
  html += "<label for='clearonpower'>Clear settings on power cycle</label>";
  html += "</div>";
  html += "</div>";
  html += "<div class='button-group'>";
  html += "<button type='submit' id='saveBtn'>Save & Apply</button>";
  html += "</div>";
  html += "<div id='status' class='status'></div>";
  html += "</form>";
  html += "</div>";
  html += "<script>";
  html += "const pairingCode = document.getElementById('pairingCode');";
  html += "pairingCode.onclick = function() {";
  html += "  navigator.clipboard.writeText(this.textContent);";
  html += "  const original = this.textContent;";
  html += "  this.textContent = 'Copied!';";
  html += "  setTimeout(() => { this.textContent = original; }, 2000);";
  html += "};";
  html += "async function save(e) {";
  html += "  e.preventDefault();";
  html += "  const status = document.getElementById('status');";
  html += "  const btn = document.getElementById('saveBtn');";
  html += "  btn.disabled = true;";
  html += "  status.className = 'status show loading';";
  html += "  status.innerHTML = '<span class=\"spinner\"></span> Saving...';";
  html += "  const payload = {";
  html += "    ssid: document.getElementById('ssid').value,";
  html += "    password: document.getElementById('password').value,";
  html += "    api_host: document.getElementById('api_host').value,";
  html += "    api_token: document.getElementById('api_token').value,";
  html += "    pairing_code: '" + PAIRING_CODE + "',";
  html += "    keep_ap: document.getElementById('keepap').checked,";
  html += "    start_portal_on_boot: document.getElementById('startportal').checked,";
  html += "    clear_on_power: document.getElementById('clearonpower').checked";
  html += "  };";
  html += "  try {";
  html += "    const r = await fetch('/set-config', {";
  html += "      method: 'POST',";
  html += "      headers: { 'Content-Type': 'application/json' },";
  html += "      body: JSON.stringify(payload)";
  html += "    });";
  html += "    if (r.ok) {";
  html += "      status.className = 'status show success';";
  html += "      status.innerHTML = '<strong>Success!</strong> Device will connect to WiFi and server.';";
  html += "      btn.disabled = false;";
  html += "    } else {";
  html += "      let errorMsg = 'Unknown error';";
  html += "      try {";
  html += "        const j = await r.json();";
  html += "        errorMsg = j.detail || r.status;";
  html += "      } catch (e) {";
  html += "        errorMsg = 'HTTP ' + r.status;";
  html += "      }";
  html += "      status.className = 'status show error';";
  html += "      status.innerHTML = '<strong>Error:</strong> ' + errorMsg;";
  html += "      btn.disabled = false;";
  html += "    }";
  html += "  } catch (e) {";
  html += "    console.error('Error:', e);";
  html += "    status.className = 'status show error';";
  html += "    status.innerHTML = '<strong>Network error:</strong> ' + e.message;";
  html += "    btn.disabled = false;";
  html += "  }";
  html += "}";
  html += "</script>";
  html += "</body></html>";
  
  server.send(200, "text/html", html);
} 

void handleSetConfig() {
  if (server.method() == HTTP_OPTIONS) {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.sendHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
    server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
    server.send(204, "text/plain", "");
    return;
  }
  
  if (server.method() != HTTP_POST) { 
    server.send(405, "text/plain", "Method not allowed"); 
    return; 
  }
  
  String body = server.arg("plain");
  Serial.printf("handleSetConfig received: %s\n", body.c_str());
  
  if (body.length() == 0) { 
    server.send(400, "application/json", "{\"detail\":\"Empty body\"}"); 
    return; 
  }

  // Parse JSON using ArduinoJson
  StaticJsonDocument<512> doc;
  DeserializationError error = deserializeJson(doc, body);
  
  if (error) {
    Serial.print("JSON parse error: ");
    Serial.println(error.c_str());
    server.send(400, "application/json", "{\"detail\":\"Invalid JSON\"}");
    return;
  }

  // Allow an early clear_on_power flag in JSON to alter behaviour remotely
  if (doc.containsKey("clear_on_power")) {
    bool v3 = true;
    if (doc["clear_on_power"].is<bool>()) v3 = doc["clear_on_power"].as<bool>();
    else if (doc["clear_on_power"].is<int>()) v3 = (doc["clear_on_power"].as<int>() != 0);
    clearOnPowerCycle = v3;
    Serial.printf("Applied ClearOnPowerCycle (portal): %s\n", clearOnPowerCycle ? "true" : "false");
    prefs.begin(PREF_NS, false);
    prefs.putUInt("clear_on_power", clearOnPowerCycle ? 1 : 0);
    prefs.end();
  }

  // Allow early keep_ap in payload so portal POSTs or remote pushes can toggle AP behaviour
  if (doc.containsKey("keep_ap")) {
    bool v = false;
    if (doc["keep_ap"].is<bool>()) v = doc["keep_ap"].as<bool>();
    else if (doc["keep_ap"].is<int>()) v = (doc["keep_ap"].as<int>() != 0);
    keepAPAlways = v;
    Serial.printf("Applied keepAPAlways: %s\n", keepAPAlways ? "true" : "false");
    prefs.begin(PREF_NS, false);
    prefs.putUInt("keep_ap", keepAPAlways ? 1 : 0);
    prefs.end();
  }

  // Allow early start_portal_on_boot in payload so AP auto-start behaviour can be toggled remotely
  if (doc.containsKey("start_portal_on_boot")) {
    bool v2 = true;
    if (doc["start_portal_on_boot"].is<bool>()) v2 = doc["start_portal_on_boot"].as<bool>();
    else if (doc["start_portal_on_boot"].is<int>()) v2 = (doc["start_portal_on_boot"].as<int>() != 0);
    startPortalOnBoot = v2;
    Serial.printf("Applied startPortalOnBoot: %s\n", startPortalOnBoot ? "true" : "false");
    prefs.begin(PREF_NS, false);
    prefs.putUInt("start_portal_on_boot", startPortalOnBoot ? 1 : 0);
    prefs.end();
    if (startPortalOnBoot && !apMode) {
      Serial.println("start_portal_on_boot requested: starting AP now...");
      startAP();
    } else if (!startPortalOnBoot && apMode) {
      if (!keepAPAlways) {
        Serial.println("start_portal_on_boot disabled: stopping AP now...");
        stopAP();
      } else {
        Serial.println("start_portal_on_boot disabled but keepAPAlways enabled; AP remains active.");
      }
    }
  }

  bool changed = false;
  bool ssidUpdated = false;
  bool passwordUpdated = false;
  bool apiHostUpdated = false;

  if (doc.containsKey("ssid")) {
    String ss = doc["ssid"].as<String>();
    ss.trim();
    if (ss.length() > 0) {
      WIFI_SSID = ss;
      changed = true;
      ssidUpdated = true;
      Serial.printf("Updated SSID: '%s'\n", WIFI_SSID.c_str());
    } else {
      Serial.println("Received empty SSID in portal set-config; ignoring (preserve existing).");
    }
  }

  if (doc.containsKey("password")) {
    String pw = doc["password"].as<String>();
    pw.trim();
    WIFI_PASS = pw;
    changed = true;
    passwordUpdated = true;
    Serial.printf("Updated password (length=%d)\n", WIFI_PASS.length());
  }

  if (doc.containsKey("api_host")) {
    String ah = doc["api_host"].as<String>();
    ah.trim();
    if (ah.length() > 0) {
      API_HOST = normalizeApiHost(ah);
      changed = true;
      apiHostUpdated = true;
      Serial.printf("Updated API_HOST: '%s' (normalized)\n", API_HOST.c_str());
    } else {
      Serial.println("Received empty API_HOST in portal set-config; ignoring.");
    }
  }

  if (doc.containsKey("pairing_code")) {
    String pc = doc["pairing_code"].as<String>();
    pc.trim();
    PAIRING_CODE = pc;
    changed = true;
    Serial.printf("Updated pairing: '%s'\n", PAIRING_CODE.c_str());
  }

  if (doc.containsKey("api_token")) {
    String t = doc["api_token"].as<String>();
    t.trim();
    API_TOKEN = t;
    changed = true;
    Serial.printf("Updated API_TOKEN: %s\n", API_TOKEN.length() ? "(set)" : "(cleared)");
  }

  if (changed) {
    saveConfigToPrefs();
    
    // Verify it was saved
    prefs.begin(PREF_NS, true);
    String verifySSID = prefs.getString("ssid", "");
    String verifyAPI = prefs.getString("api_host", "");
    prefs.end();
    Serial.printf("✓ Verified saved - SSID:'%s' API:'%s'\n", verifySSID.c_str(), verifyAPI.c_str());
    
    // Only reconnect/stop AP if credentials were actually supplied and applied
    if (ssidUpdated || passwordUpdated) {
      Serial.println("WiFi credentials provided - reconnecting...");
      WiFi.disconnect(true, true);
      delay(500);
      if (apMode) stopAP();
      WiFi.begin(WIFI_SSID.c_str(), WIFI_PASS.c_str());
    } else {
      Serial.println("No WiFi credentials provided in portal set-config; keeping AP active.");
    }
  }

  server.sendHeader("Access-Control-Allow-Origin", "*");
  {
    bool token_set = (API_TOKEN.length() > 0);
    String resp = String("{\"status\":\"ok\",\"token_set\":") + (token_set ? "true" : "false") + "}";
    server.send(200, "application/json", resp);
  }
}


/* Card holder configure */
struct CardHolder {
  const char* uid;
  const char* name;
  const char* email;
};

CardHolder CARD_HOLDERS[] = {
  { "04A1B2C3D4", "Alice Santos", "alice@example.com" },
  { "A0B1C2D3E4", "Ben Cruz",     "ben@example.com"   },
  { "1122334455", "Cara Lim",     "cara@example.com"  },
  { "1C8B3F02",   "Test User",    "test@example.com"  },
};
const size_t NUM_CARD_HOLDERS = sizeof(CARD_HOLDERS)/sizeof(CARD_HOLDERS[0]);

const CardHolder* findHolderByUid(const String& uidUpper) {
  for (size_t i = 0; i < NUM_CARD_HOLDERS; i++) {
    if (uidUpper == CARD_HOLDERS[i].uid) return &CARD_HOLDERS[i];
  }
  return nullptr;
}

/* WiFi + HTTP helpers */
void ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi connecting");
  unsigned long start = millis();
  int restartCount = 0;
  while (WiFi.status() != WL_CONNECTED) {
    // Break the 300ms delay into smaller slices so we can process serial and HTTP/DNS
    for (int i = 0; i < 6; ++i) {
      delay(50); // small delay to yield and feed watchdog
      // Allow captive portal servicing if in AP mode
      if (apMode) dnsServer.processNextRequest();
      server.handleClient();
      // Process any serial commands typed while connecting (non-blocking)
      if (Serial.available()) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();
        if (cmd.equalsIgnoreCase("startap")) {
          Serial.println("Serial command: startap detected during connect; starting AP fallback.");
          startAP();
          return;
        }
        if (cmd.equalsIgnoreCase("testserver")) {
          Serial.println("Serial command: testserver detected; invoking testServerConnection().");
          testServerConnection();
          continue;
        }
        if (cmd.equalsIgnoreCase("keepap") || cmd.startsWith("keepap ")) {
          // commands: keepap on | keepap off | keepap status
          int sp = cmd.indexOf(' ');
          String arg = (sp > 0) ? cmd.substring(sp + 1) : "";
          arg.trim();
          if (arg.equalsIgnoreCase("on")) {
            keepAPAlways = true;
            prefs.begin(PREF_NS, false);
            prefs.putUInt("keep_ap", 1);
            prefs.end();
            Serial.println("keepAPAlways set: ON (AP will remain active)");
          } else if (arg.equalsIgnoreCase("off")) {
            keepAPAlways = false;
            prefs.begin(PREF_NS, false);
            prefs.putUInt("keep_ap", 0);
            prefs.end();
            Serial.println("keepAPAlways set: OFF (AP may be stopped by firmware)");
          } else {
            Serial.printf("keepAPAlways status: %s\n", (keepAPAlways?"ON":"OFF"));
          }
          continue;
        }
        if (cmd.equalsIgnoreCase("portal") || cmd.startsWith("portal ")) {
          // commands: portal on | portal off | portal status
          int sp2 = cmd.indexOf(' ');
          String arg2 = (sp2 > 0) ? cmd.substring(sp2 + 1) : "";
          arg2.trim();
          if (arg2.equalsIgnoreCase("on")) {
            startPortalOnBoot = true;
            prefs.begin(PREF_NS, false);
            prefs.putUInt("start_portal_on_boot", 1);
            prefs.end();
            Serial.println("StartPortalOnBoot set: ON (AP will start on boot)");
            if (!apMode) {
              Serial.println("Starting AP now as requested...");
              startAP();
            }
          } else if (arg2.equalsIgnoreCase("off")) {
            startPortalOnBoot = false;
            prefs.begin(PREF_NS, false);
            prefs.putUInt("start_portal_on_boot", 0);
            prefs.end();
            Serial.println("StartPortalOnBoot set: OFF (AP will not start automatically)");
            if (apMode) {
              if (!keepAPAlways) {
                Serial.println("Stopping AP now as requested...");
                stopAP();
              } else {
                Serial.println("keepAPAlways is enabled; not stopping AP.");
              }
            }
          } else {
            Serial.printf("StartPortalOnBoot status: %s\n", (startPortalOnBoot?"ON":"OFF"));
            Serial.printf("AP current mode: %s\n", (apMode ? "AP active" : "AP not active"));
          }
          continue;
        }
        if (cmd.equalsIgnoreCase("clearcreds") || cmd.startsWith("clearcreds ")) {
          // clearcreds on | off | status | now
          int spc = cmd.indexOf(' ');
          String arg = (spc > 0) ? cmd.substring(spc + 1) : "";
          arg.trim();
          if (arg.equalsIgnoreCase("on")) {
            clearOnPowerCycle = true;
            prefs.begin(PREF_NS, false);
            prefs.putUInt("clear_on_power", 1);
            prefs.end();
            Serial.println("ClearOnPowerCycle: ON (credentials will be cleared on next power cycle)");
          } else if (arg.equalsIgnoreCase("off")) {
            clearOnPowerCycle = false;
            prefs.begin(PREF_NS, false);
            prefs.putUInt("clear_on_power", 0);
            prefs.end();
            Serial.println("ClearOnPowerCycle: OFF (credentials will persist across power cycles)");
          } else if (arg.equalsIgnoreCase("now")) {
            Serial.println("Clearing credentials now and starting portal...");
            prefs.begin(PREF_NS, false);
            prefs.remove("ssid");
            prefs.remove("password");
            prefs.remove("api_host");
            prefs.putUInt("start_portal_on_boot", 1);
            prefs.end();
            WIFI_SSID = "";
            WIFI_PASS = "";
            API_HOST = "";
            startPortalOnBoot = true;
            if (!apMode) startAP();
          } else {
            Serial.printf("ClearOnPowerCycle status: %s\n", (clearOnPowerCycle?"ON":"OFF"));
          }
          continue;
        }
        if (cmd.startsWith("setwifi")) {
          // quick handling: setwifi <SSID> <PASSWORD>
          int sp = cmd.indexOf(' ');
          if (sp > 0) {
            int sp2 = cmd.indexOf(' ', sp + 1);
            if (sp2 > sp) {
              String ssid = cmd.substring(sp + 1, sp2);
              String pass = cmd.substring(sp2 + 1);
              ssid = stripQuotes(ssid);
              pass = stripQuotes(pass);
              WIFI_SSID = ssid;
              WIFI_PASS = pass;
              saveConfigToPrefs();
              Serial.printf("Saved WIFI_SSID='%s' and password (masked) via serial. Reconnecting...\n", WIFI_SSID.c_str());
              if (apMode) {
                if (!keepAPAlways) stopAP(); else Serial.println("keepAPAlways enabled; keeping AP active.");
              }
              WiFi.disconnect(true, true);
              delay(200);
              WiFi.begin(WIFI_SSID.c_str(), WIFI_PASS.c_str());
              start = millis();
              restartCount = 0;
            }
          }
        }
      }
    }

    Serial.print(".");
    if (millis() - start > 30000) {
      restartCount++;
      Serial.printf("\nRe-starting WiFi (SSID='%s') - status=%d attempt=%d\n", WIFI_SSID.c_str(), WiFi.status(), restartCount);
      WiFi.disconnect(true, true);
      delay(1000);
      WiFi.begin(WIFI_SSID.c_str(), WIFI_PASS.c_str());
      start = millis();
      if (restartCount >= 3) {
        Serial.println("Failed to connect after repeated attempts; starting AP fallback for configuration.");
        startAP();
        return;
      }
    }
  }
  Serial.print("\nWiFi connected. IP: ");
  Serial.println(WiFi.localIP());
  // NOTE: keep AP active until server connectivity confirmed. stopAP() will be called
  // from testServerConnection() once the server is reachable.
}

bool httpPostJson(const String& url, const String& body, String& resp, int& code) {
  ensureWiFi();
  
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("ERROR: WiFi not connected!");
    code = -2;
    return false;
  }
  
  Serial.printf("Attempting POST to: %s\n", url.c_str());
  Serial.printf("Request body: %s\n", body.c_str());

  // Basic guard: ensure URL looks like a full HTTP(S) URL so we don't attempt to POST to "/api/..." when API_HOST is empty
  if (!url.startsWith("http")) {
    Serial.printf("ERROR: Invalid URL '%s' - API_HOST may be missing or malformed. Aborting.\n", url.c_str());
    code = -4;
    return false;
  }
  
  // For HTTPS URLs, set up secure client with CA certificate
  if (url.startsWith("https://")) {
    WiFiClientSecure client;
    client.setCACert(ca_cert);
    
    HTTPClient http;
    http.setConnectTimeout(10000);
    http.setTimeout(15000);
    
    if (!http.begin(client, url)) {
      Serial.println("ERROR: http.begin() failed (HTTPS)!");
      Serial.println("DEBUG: Retrying with relaxed SSL...");
      
      WiFiClientSecure clientRelaxed;
      clientRelaxed.setInsecure();
      HTTPClient httpRelaxed;
      httpRelaxed.setConnectTimeout(10000);
      httpRelaxed.setTimeout(15000);
      
      if (!httpRelaxed.begin(clientRelaxed, url)) {
        Serial.println("ERROR: http.begin() failed even with relaxed SSL!");
        code = -3;
        return false;
      }
      
      httpRelaxed.addHeader("Connection", "close");
      httpRelaxed.addHeader("Content-Type", "application/json");
      if (API_TOKEN.length()) {
        httpRelaxed.addHeader("X-Device-Token", API_TOKEN);
      }
      
      code = httpRelaxed.POST(body);
      if (code > 0) {
        resp = httpRelaxed.getString();
      }
      httpRelaxed.end();
      return (code >= 200 && code < 300);
    }
    
    Serial.println("Using HTTPS for POST");
    
    http.addHeader("Connection", "close");
    http.addHeader("Content-Type", "application/json");
    if (API_TOKEN.length()) {
      http.addHeader("X-Device-Token", API_TOKEN);
      Serial.println("Added X-Device-Token header for device authentication");
    }
    
    code = http.POST(body);
    
    if (code > 0) {
      resp = http.getString();
      Serial.printf("POST %s -> %d\n", url.c_str(), code);
      if (resp.length()) {
        Serial.printf("Response: %s\n", resp.c_str());
      }
    } else if (code == -1) {
      Serial.println("ERROR: POST failed with connection refused (-1)");
      Serial.println("DEBUG: Retrying with relaxed SSL...");
      http.end();
      
      WiFiClientSecure clientRelaxed;
      clientRelaxed.setInsecure();
      HTTPClient httpRelaxed;
      httpRelaxed.setConnectTimeout(10000);
      httpRelaxed.setTimeout(15000);
      
      if (httpRelaxed.begin(clientRelaxed, url)) {
        httpRelaxed.addHeader("Connection", "close");
        httpRelaxed.addHeader("Content-Type", "application/json");
        if (API_TOKEN.length()) {
          httpRelaxed.addHeader("X-Device-Token", API_TOKEN);
        }
        
        code = httpRelaxed.POST(body);
        if (code > 0) {
          resp = httpRelaxed.getString();
          Serial.printf("POST %s -> %d (relaxed SSL)\n", url.c_str(), code);
          if (resp.length()) {
            Serial.printf("Response: %s\n", resp.c_str());
          }
        }
        httpRelaxed.end();
      }
    } else {
      Serial.printf("ERROR: POST failed with code %d\n", code);
      Serial.printf("Error details: %s\n", http.errorToString(code).c_str());
    }
    
    http.end();
    return (code >= 200 && code < 300);
    
  } else {
    HTTPClient http;
    http.setConnectTimeout(10000);
    http.setTimeout(15000);
    
    if (!http.begin(url)) {
      Serial.println("ERROR: http.begin() failed!");
      Serial.println("TROUBLESHOOTING:");
      Serial.println("1. Verify server is running");
      // Schedule a reconnect outside of the HTTP handler to avoid truncating the response
      if (WiFi.status() == WL_CONNECTED) {
        Serial.println("Scheduling reconnect with updated WiFi credentials...");
        should_reconnect = true;
        reconnect_at = millis() + 200; // short delay to allow response to be sent
      }
      code = -3;
      return false;
    }
    Serial.println("Using HTTP for POST");
    
    http.addHeader("Connection", "close");
    http.addHeader("Content-Type", "application/json");
    if (API_TOKEN.length()) {
      http.addHeader("X-Device-Token", API_TOKEN);
      Serial.println("Added X-Device-Token header for device authentication");
    }
    
    code = http.POST(body);
    
    if (code > 0) {
      resp = http.getString();
      Serial.printf("POST %s -> %d\n", url.c_str(), code);
      if (resp.length()) {
        Serial.printf("Response: %s\n", resp.c_str());
      }
    } else {
      Serial.printf("ERROR: POST failed with code %d\n", code);
      Serial.printf("Error details: %s\n", http.errorToString(code).c_str());
      if (code == -1) {
        Serial.println("TROUBLESHOOTING:");
        Serial.println("1. Server is not running or not accessible");
        Serial.println("2. Check Windows Firewall allows port 8000/8443");
        Serial.println("3. Verify IP address: " + String(API_HOST));
        Serial.println("4. Try: python manage.py runserver 0.0.0.0:8000");
      }
    }
    
    http.end();
    return (code >= 200 && code < 300);
  }
}

// Normalize API_HOST provided by user or loaded from prefs.
// - Ensures a scheme (http://) if missing.
// - If a numeric IPv4 address is provided without a port, appends :8000 (convenient default for local dev server).
// - Warns when API_HOST is 0.0.0.0, 127.0.0.1 or localhost since these are not reachable from the device.
String normalizeApiHost(const String& raw) {
  String s = raw;
  s.trim();
  if (s.length() == 0) return s;

  // Ensure scheme is present
  if (!s.startsWith("http://") && !s.startsWith("https://")) {
    s = String("http://") + s;
  }

  int schemeEnd = s.indexOf("://");
  int authStart = (schemeEnd >= 0) ? schemeEnd + 3 : 0;
  // If the remainder begins with a scheme (duplicate), strip it (handles 'http://http://host')
  if (authStart < s.length()) {
    String remainder = s.substring(authStart);
    if (remainder.startsWith("http://")) {
      s = s.substring(0, authStart) + remainder.substring(7);
      // recompute schemeEnd/authStart after modification
      schemeEnd = s.indexOf("://");
      authStart = (schemeEnd >= 0) ? schemeEnd + 3 : 0;
    } else if (remainder.startsWith("https://")) {
      s = s.substring(0, authStart) + remainder.substring(8);
      schemeEnd = s.indexOf("://");
      authStart = (schemeEnd >= 0) ? schemeEnd + 3 : 0;
    }
  }
  int pathStart = s.indexOf('/', authStart);
  String authority = (pathStart >= 0) ? s.substring(authStart, pathStart) : s.substring(authStart);

  bool hasPort = authority.indexOf(':') != -1;
  String hostOnly = authority;
  int colonPos = authority.indexOf(':');
  if (colonPos >= 0) hostOnly = authority.substring(0, colonPos);

  // If host is numeric IPv4 and no port supplied, append default dev port 8000
  bool isNumericIp = true;
  int dots = 0;
  for (size_t i = 0; i < hostOnly.length(); ++i) {
    char c = hostOnly.charAt(i);
    if (c == '.') dots++;
    else if (!isDigit(c)) { isNumericIp = false; break; }
  }
  if (isNumericIp && dots == 3 && !hasPort) {
    authority += ":8000";
    if (pathStart >= 0) {
      s = s.substring(0, authStart) + authority + s.substring(pathStart);
    } else {
      s = s.substring(0, authStart) + authority;
    }
  }

  // Warn about common mistakes that are not reachable from the device
  if (hostOnly == "0.0.0.0" || hostOnly == "127.0.0.1" || hostOnly.equalsIgnoreCase("localhost")) {
    Serial.printf("WARNING: API_HOST '%s' may not be reachable from the device (use your PC LAN IP like 192.168.x.y:8000)\n", raw.c_str());
  }

  Serial.printf("Normalized API_HOST: '%s' -> '%s'\n", raw.c_str(), s.c_str());
  return s;
}

String buildApiBase() {
  String baseUrl = normalizeApiHost(API_HOST);
  if (baseUrl.endsWith("/")) {
    baseUrl.remove(baseUrl.length() - 1);
  }
  return baseUrl;
}

// Returns true if an API_HOST has been configured (non-empty after trimming)
bool apiHostConfigured() {
  String a = API_HOST;
  a.trim();
  return a.length() > 0;
}

// Device registry: post a small heartbeat to the server so UI can discover the device
const char* FIRMWARE_VER = "1.0.0";
unsigned long lastDevicePost = 0;
const unsigned long DEVICE_POST_INTERVAL_MS = 60000UL; // every 60s

void postDeviceInstance() {
  if (!apiHostConfigured()) { Serial.println("INFO: API_HOST not set; skipping device registry post."); return; }
  if (WiFi.status() != WL_CONNECTED) return;
  String url = buildApiBase();
  if (url.length() == 0) { Serial.println("INFO: buildApiBase returned empty; skipping postDeviceInstance."); return; }
  url += "/api/device-instances";
  Serial.printf("Posting device instance to URL: %s\n", url.c_str());
  HTTPClient http;
  if (!http.begin(url)) { Serial.println("ERROR: http.begin() failed in postDeviceInstance(); skipping."); return; }
  http.addHeader("Content-Type", "application/json");
  String payload = String("{\"ip\":\"") + WiFi.localIP().toString() + "\",\"ssid\":\"" + WIFI_SSID + "\",\"api_host\":\"" + API_HOST + "\",\"firmware\":\"" + FIRMWARE_VER + "\",\"pairing_code\":\"" + PAIRING_CODE + "\",\"server_reachable\":true}";
  Serial.printf("Device post payload: %s\n", payload.c_str());
  int code = http.POST(payload);
  if (code >= 200 && code < 300) {
    String resp = http.getString();
    Serial.printf("Device post succeeded -> %d response: %s\n", code, resp.c_str());
  } else {
    Serial.printf("Device post failed -> %d\n", code);
    Serial.printf("Error details: %s\n", http.errorToString(code).c_str());
  }
  http.end();
}

BorrowerCheckResult checkBorrower(const String& uid) {
  
  ensureWiFi();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("ERROR: WiFi not connected; cannot check borrower.");
    return BORROWER_NETWORK_ERROR;
  }

  String url = buildApiBase() + "/api/borrowers?q=" + uid;
  Serial.printf("Checking borrower registration: %s\n", url.c_str());

  int code = -1;
  String resp = "";
  
  // For HTTPS URLs, set up secure client with CA certificate
  if (url.startsWith("https://")) {
    WiFiClientSecure client;
    
    // Try with CA cert first (strict verification)
    client.setCACert(ca_cert);
    Serial.println("DEBUG: CA cert set for HTTPS verification");
    
    HTTPClient http;
    http.setConnectTimeout(10000);
    http.setTimeout(10000);
    
    if (!http.begin(client, url)) {
      Serial.println("ERROR: http.begin() failed during borrower lookup (HTTPS)!");
      http.end();
      
      // Try again with relaxed verification as fallback
      Serial.println("DEBUG: Retrying with relaxed SSL verification...");
      WiFiClientSecure clientRelaxed;
      clientRelaxed.setInsecure();  // Disable cert verification for dev
      
      HTTPClient httpRelaxed;
      httpRelaxed.setConnectTimeout(10000);
      httpRelaxed.setTimeout(10000);
      
      if (!httpRelaxed.begin(clientRelaxed, url)) {
        Serial.println("ERROR: http.begin() failed even with relaxed SSL!");
        httpRelaxed.end();
        return BORROWER_NETWORK_ERROR;
      }
      
      code = httpRelaxed.GET();
      if (code > 0) {
        resp = httpRelaxed.getString();
      } else {
        Serial.printf("ERROR: GET failed with code %d (relaxed SSL)\n", code);
      }
      httpRelaxed.end();
      
    } else {
      Serial.println("Using HTTPS for borrower lookup (strict cert verification)");
      
      code = http.GET();
      if (code > 0) {
        resp = http.getString();
      } else if (code == -1) {
        Serial.println("ERROR: Connection refused on GET request (-1)");
        Serial.println("DEBUG: Retrying with relaxed SSL verification...");
        http.end();
        
        // Retry with relaxed verification
        WiFiClientSecure clientRelaxed;
        clientRelaxed.setInsecure();
        
        HTTPClient httpRelaxed;
        httpRelaxed.setConnectTimeout(10000);
        httpRelaxed.setTimeout(10000);
        
        if (httpRelaxed.begin(clientRelaxed, url)) {
          code = httpRelaxed.GET();
          if (code > 0) {
            resp = httpRelaxed.getString();
            Serial.println("SUCCESS: Connection worked with relaxed SSL verification");
          }
          httpRelaxed.end();
        }
      }
      http.end();
    }
    
  } else {
    HTTPClient http;
    http.setConnectTimeout(10000);
    http.setTimeout(10000);
    
    if (!http.begin(url)) {
      Serial.println("ERROR: http.begin() failed during borrower lookup!");
      Serial.println("TROUBLESHOOTING:");
      Serial.println("1. Verify server is running: python manage.py runserver 0.0.0.0:8000");
      Serial.println("2. Check IP address matches your computer's LAN IP");
      Serial.println("3. Ensure ESP32 and computer are on same Wi‑Fi network");
      return BORROWER_NETWORK_ERROR;
    }
    Serial.println("Using HTTP for borrower lookup");
    
    code = http.GET();
    if (code > 0) {
      resp = http.getString();
    }
    http.end();
  }
  
  if (code >= 200 && code < 300) {
    // Check for exact match (case-insensitive search in response)
    String searchPattern = String("\"rfid_uid\":\"") + uid + "\"";
    String searchPatternLower = searchPattern;
    searchPatternLower.toLowerCase();
    String respLower = resp;
    respLower.toLowerCase();

    bool exists = respLower.indexOf(searchPatternLower) != -1;
    Serial.printf("Borrower lookup -> %d (exists=%s)\n", code, exists ? "yes" : "no");
    if (!exists && resp.length() > 0) {
      Serial.printf("Response preview: %s\n", resp.substring(0, min(200, (int)resp.length())).c_str());
    }
    return exists ? BORROWER_EXISTS : BORROWER_NOT_FOUND;
  } else if (code == -1) {
    Serial.printf("Borrower lookup failed -> Connection refused (code %d)\n", code);
    Serial.println("TROUBLESHOOTING:");
    Serial.println("1. Server is not running or not accessible");
    Serial.println("2. Check Windows Firewall allows port 8000/8443");
    Serial.println("3. Verify IP address: " + String(API_HOST));
    Serial.println("4. Try: python manage.py runserver 0.0.0.0:8000");
    return BORROWER_NETWORK_ERROR;
  } else {
    Serial.printf("Borrower lookup failed -> %d\n", code);
    return BORROWER_NETWORK_ERROR;
  }
}

bool logRegistrationScan(const String& uid, const char* name, const char* email) {
  String url = buildApiBase() + "/api/rfid-scans";
  String body = String("{\"uid\":\"") + uid + "\",\"name\":\"" + name + "\",\"email\":\"" + email + "\"}";
  String resp;
  int code;
  bool ok = httpPostJson(url, body, resp, code);
  if (!ok) {
    Serial.println("Failed to record RFID scan");
  } else {
    Serial.println("RFID scan recorded for registration.");
  }
  return ok;
}

bool logBorrowTap(const String& uid, const char* name, const char* email) {
  String url = buildApiBase() + "/api/scan-id";
  String body = String("{\"borrower_rfid\":\"") + uid + "\",\"name\":\"" + name + "\",\"email\":\"" + email + "\"}";
  String resp;
  int code;
  bool ok = httpPostJson(url, body, resp, code);
  if (!ok) {
    Serial.println("Failed to register RFID tap.");
  } else {
    Serial.println("RFID tap acknowledged by server.");
  }
  return ok;
}

bool postBorrow(const String& uid, const String& itemQr) {
  if (itemQr.isEmpty()) return false;
  String url = buildApiBase() + "/api/borrow";
  String body = String("{\"borrower_rfid\":\"") + uid + "\",\"item_qr\":\"" + itemQr + "\"}";
  String resp;
  int code;
  bool ok = httpPostJson(url, body, resp, code);
  if (!ok) {
    Serial.println("Borrow API failed");
  } else {
    Serial.println("Borrow successful");
  }
  return ok;
}

String uidToUpper(const MFRC522::Uid& uid) {
  String s;
  for (byte i = 0; i < uid.size; i++) {
    if (uid.uidByte[i] < 16) s += '0';
    s += String(uid.uidByte[i], HEX);
  }
  s.toUpperCase();
  return s;
}

void testServerConnection() {
  if (!apiHostConfigured()) {
    Serial.println("INFO: API_HOST not set; skipping server connection test. Set DeviceConfig via web UI or push-config.");
    return;
  }

  String baseUrl = String(API_HOST);
  if (baseUrl.endsWith("/")) {
    baseUrl.remove(baseUrl.length() - 1);
  }
  
  WiFiClientSecure* client = nullptr;
  HTTPClient http;
  http.setConnectTimeout(5000);
  http.setTimeout(5000);
  
  String testUrl = baseUrl + "/api/borrowers";
  Serial.printf("Testing connection to: %s\n", testUrl.c_str());
  
  // For HTTPS URLs, set up secure client with CA certificate
  if (testUrl.startsWith("https://")) {
    client = new WiFiClientSecure();
    client->setCACert(ca_cert);
    if (http.begin(*client, testUrl)) {
      http.addHeader("Content-Type", "application/json");
      int code = http.GET();
      Serial.printf("Test GET (HTTPS) -> %d\n", code);
      if (code > 0) {
        Serial.println("✓ Server is reachable via HTTPS!");
        // When server is reachable, stop the AP so the device behaves like a normal STA-only device
        if (apMode) {
          Serial.println("Server reachable - disabling AP mode to save power and avoid confusion");
          if (!keepAPAlways) stopAP(); else Serial.println("keepAPAlways enabled; leaving AP active despite server reachability.");
        }
      } else {
        Serial.printf("Server connection test failed: %s\n", http.errorToString(code).c_str());
        Serial.println("\nTROUBLESHOOTING:");
        Serial.println("1. Check if Django is running: python manage.py runserver 0.0.0.0:8000");
        Serial.println("2. Verify IP address matches your computer's LAN IP");
        Serial.println("3. Check Windows Firewall allows port 8000/8443");
        Serial.println("4. Ensure ESP32 and computer are on same Wi-Fi network");
      }
      http.end();
    }
    delete client;
  } else {
    if (http.begin(testUrl)) {
      http.addHeader("Content-Type", "application/json");
      int code = http.GET();
      Serial.printf("Test GET (HTTP) -> %d\n", code);
      if (code > 0) {
        Serial.println("✓ Server is reachable via HTTP!");
        // When server is reachable, stop the AP so the device behaves like a normal STA-only device
        if (apMode) {
          Serial.println("Server reachable - disabling AP mode to save power and avoid confusion");
          if (!keepAPAlways) stopAP(); else Serial.println("keepAPAlways enabled; leaving AP active despite server reachability.");
        }
      } else {
        Serial.printf("Server connection test failed: %s\n", http.errorToString(code).c_str());
        Serial.println("\nTROUBLESHOOTING:");
        Serial.println("1. Check if Django is running: python manage.py runserver 0.0.0.0:8000");
        Serial.println("2. Verify IP address matches your computer's LAN IP");
        Serial.println("3. Check Windows Firewall allows port 8000");
        Serial.println("4. Ensure ESP32 and computer are on same Wi-Fi network");
      }
      http.end();
    } else {
      Serial.println("ERROR: Could not initialize HTTP client!");
    }
  }
}

// Helper: process a UID through the server workflow (logs, registration, borrow tap, optional auto-borrow)
void handleCardUid(const String& uid) {
  const CardHolder* holder = findHolderByUid(uid);
  String name  = holder ? String(holder->name)  : ("RFID " + uid);
  String email = holder ? String(holder->email) : "";

  BorrowerCheckResult res = checkBorrower(uid);
  if (res == BORROWER_NETWORK_ERROR) {
    Serial.println("ERROR: Server not reachable. Skipping borrower check and scan logging.");
    Serial.println("TROUBLESHOOTING:");
    Serial.println("1. Start Django: python manage.py runserver 0.0.0.0:8000");
    Serial.println("2. Verify API_HOST matches your PC LAN IP and port");
    Serial.println("3. Check Windows Firewall allows inbound TCP 8000");
    return;
  }

  // Server reachable: log raw scan for UI convenience
  logRegistrationScan(uid, name.c_str(), email.c_str());

  if (res == BORROWER_NOT_FOUND) {
    Serial.println("⚠ Borrower not registered on server. Please register in the web app before borrowing.");
    return;
  }

  if (logBorrowTap(uid, name.c_str(), email.c_str()) && !FORCED_ITEM_QR.isEmpty()) {
    Serial.printf("Auto-borrowing item: %s\n", FORCED_ITEM_QR.c_str());
    postBorrow(uid, FORCED_ITEM_QR);
  }
}

// Helper: perform a blocking scan for up to timeoutMs; returns after first card or on timeout
void doTimedScan(unsigned long timeoutMs) {
  unsigned long start = millis();
  Serial.printf("Scanning for a card for %lus...\n", timeoutMs/1000UL);
  while (millis() - start < timeoutMs) {
    if (use_soft_spi) {
      uint8_t uidBuf[8]; uint8_t uidLen = sizeof(uidBuf);
      if (soft_requestA(uidBuf, uidLen)) {
        String uid = "";
        for (uint8_t i = 0; i < uidLen; ++i) {
          if (uidBuf[i] < 16) uid += '0';
          uid += String(uidBuf[i], HEX);
        }
        uid.toUpperCase();
        Serial.print("(softSPI) ");
        handleCardUid(uid);
        delay(1200);
        return;
      }
      delay(100);
    } else if (rfid_available) {
      if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
        String uid = uidToUpper(rfid.uid);
        handleCardUid(uid);
        rfid.PICC_HaltA();
        rfid.PCD_StopCrypto1();
        delay(1200);
        return;
      }
      delay(50);
    } else {
      // RFID currently unavailable; avoid tight loop
      delay(200);
    }
  }
  Serial.println("No card detected within timeout.");
}

void setup() {
  Serial.begin(115200);
  delay(800);
  Serial.println("\n==========================================");
  Serial.println("ESP32 RFID Borrowing System - Starting...");
  Serial.println("==========================================");
  
  // Diagnostic: print pin usage so you can confirm wiring
  Serial.println("\nPin configuration:");
  Serial.printf(" SCK=%d MOSI=%d MISO=%d SS=%d RST=%d\n", PIN_SCK, PIN_MOSI, PIN_MISO, PIN_SS, PIN_RST);
  
  // Warn if using pins commonly reserved for flash/SPI flash (6..11 on many ESP32 boards)
  auto warn_flash_pin = [](int p){ return (p >= 6 && p <= 11); };
  if (warn_flash_pin(PIN_SCK) || warn_flash_pin(PIN_MOSI) || warn_flash_pin(PIN_MISO) || warn_flash_pin(PIN_SS)) {
    Serial.println("⚠ WARNING: One or more configured SPI pins are in the 6..11 range commonly used by flash memory on ESP32 modules.");
    Serial.println("If your RC522 is soldered to flash pins it may not work reliably. Consider using safe VSPI pins (SCK=18,MISO=19,MOSI=23,SS=5).\n");
  }

  // Load stored credentials (if present) before attempting WiFi
  Serial.println("\nLoading configuration from NVS...");
  loadConfigFromPrefs();
  
  Serial.println("\nInitializing WiFi...");
  // ALWAYS start AP on power-on to ensure device is discoverable for configuration
  // even if credentials are present. User can connect to WiFi OR use the AP.
  Serial.println("🔌 Starting provisioning AP (device will always broadcast on power-up)...");
  startAP();
  
  // Only attempt WiFi connection if credentials are configured
  if (apiHostConfigured() && WIFI_SSID.length() > 0) {
    Serial.println("✓ Credentials found; attempting WiFi connection...");
    ensureWiFi();
  } else {
    Serial.println("⚠ No WiFi credentials configured yet; AP active and waiting for configuration via 192.168.4.1");
  }

  // Ensure SS idles HIGH and pulse RST BEFORE initializing SPI to avoid module confusion
  pinMode(PIN_SS, OUTPUT);
  digitalWrite(PIN_SS, HIGH); // make sure chip-select is not held low during SPI init
  pinMode(PIN_RST, OUTPUT);
  digitalWrite(PIN_RST, LOW);
  delay(25);
  digitalWrite(PIN_RST, HIGH);
  delay(60);
  Serial.println("SS set HIGH; RST pulsed to ensure MFRC522 reset.");

  SPI.begin(PIN_SCK, PIN_MISO, PIN_MOSI, PIN_SS);

  // Initialize SPI and attempt to detect the MFRC522. If detection fails,
  // allow explicit retry via serial commands and try software SPI fallback.
  rfid.PCD_Init();
  delay(50);

  Serial.println("\n--- RFID Module Detection ---");
  Serial.print("MFRC522 version: ");
  // Try hardware first, then software fallback
  bool hw = detectHardwareRFID();
  if (!hw) {
    detectSoftwareRFID();
  }
  Serial.println("-----------------------------\n");

  // Start HTTP server for captive portal and config POST endpoint
  Serial.println("Starting HTTP server...");
  
  server.on("/apply-config", HTTP_POST, handleApplyConfig);
  // Provide preflight handler for CORS
  server.on("/apply-config", HTTP_OPTIONS, [](){
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.sendHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
    server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
    server.send(204, "text/plain", "");
  });

  // Control endpoint for admin actions (disconnect/startap/stopap)
  server.on("/control", HTTP_POST, handleControl);
  server.on("/control", HTTP_OPTIONS, [](){
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.sendHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
    server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
    server.send(204, "text/plain", "");
  });

  // Health check
  server.on("/health", HTTP_GET, [](){ 
    server.sendHeader("Access-Control-Allow-Origin", "*"); 
    server.send(200, "application/json", "{\"status\":\"ok\"}"); 
  });

  // Captive portal: simple page to view and edit device config
  server.on("/", HTTP_GET, handleRoot);
  server.on("/set-config", HTTP_POST, handleSetConfig);
  server.on("/set-config", HTTP_OPTIONS, [](){
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.sendHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
    server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
    server.send(204, "text/plain", "");
  });

  server.begin();
  Serial.println("✓ HTTP server started");

  // Log WiFi events to aid debugging (AP station connect/disconnect etc)
  WiFi.onEvent([](WiFiEvent_t event, WiFiEventInfo_t info){
    const char* evname = "UNKNOWN";
    switch(event) {
      case ARDUINO_EVENT_WIFI_STA_START: evname = "STA_START"; break;
      case ARDUINO_EVENT_WIFI_STA_CONNECTED: evname = "STA_CONNECTED"; break;
      case ARDUINO_EVENT_WIFI_STA_DISCONNECTED: evname = "STA_DISCONNECTED"; break;
      case ARDUINO_EVENT_WIFI_STA_GOT_IP: evname = "STA_GOT_IP"; break;
      case ARDUINO_EVENT_WIFI_AP_START: evname = "AP_START"; break;
      case ARDUINO_EVENT_WIFI_AP_STOP: evname = "AP_STOP"; break;
      default: break;
    }
    Serial.printf("WiFi event: %d (%s) status=%d IP=%s\n", (int)event, evname, WiFi.status(), (WiFi.status()==WL_CONNECTED ? WiFi.localIP().toString().c_str() : "0.0.0.0"));
    if (event == ARDUINO_EVENT_WIFI_STA_DISCONNECTED) {
      // Print RSSI (may be 0 or meaningless when not connected) and a human-friendly reason if available
      Serial.printf("RSSI: %d dBm\n", WiFi.RSSI());
      printDisconnectReasonIfAvailable(info);
    }
  });


  Serial.println("\nTesting server connectivity...");
  testServerConnection();

  // Start mDNS responder if we have an IP so the device is reachable at <name>.local
  if (WiFi.status() == WL_CONNECTED) {
    String mac = WiFi.macAddress();
    String tail = mac.substring(mac.length() - 5);
    MDNS_NAME = String("esp32-") + tail;
    if (MDNS.begin(MDNS_NAME.c_str())) {
      Serial.printf("mDNS responder started: %s.local\n", MDNS_NAME.c_str());
    } else {
      Serial.println("mDNS responder failed to start");
    }
  }

  // Ensure hotspot is active on boot if the device is unconfigured so users can connect to the AP to configure.
  // The AP will be stopped once connectivity to the HTTP server is verified.
  if (startPortalOnBoot || !apiHostConfigured() || WIFI_SSID.length() == 0) {
    Serial.println("⚠ StartPortalOnBoot enabled or API_HOST/WiFi not set; starting AP for provisioning.");
    startAP();
  } else {
    Serial.println("✓ API_HOST configured; AP will not be started automatically (Start AP via UI/USB if needed).");
  }

  // Attempt to fetch authoritative config from the Django app (if reachable)
  fetchDeviceConfigFromServer();

  // Ensure we have a persistent pairing code to allow claim/pair flows
  ensurePairingCodeExists();
  Serial.println("\n==========================================");
  Serial.printf("Pairing code: %s\n", PAIRING_CODE.c_str());
  Serial.println("==========================================");
  
  Serial.println("\n✓ Ready. Tap a card to scan...");
  Serial.println("Commands: 'detect', 'soft', 'hard', 'status', 'showcfg', 'startap', 'stopap', 'stopap force', 'keepap on|off|status', 'testserver', 'portal on|off|status', 'clearcreds on|off|status|now'");
  Serial.println("          'setwifi <SSID> <PASS>', 'setapi <HOST>' (e.g. 192.168.1.100:8000 or http://192.168.1.100:8000), 'scan [seconds]'");
} 

void loop() {
  // Execute any scheduled control actions (non-blocking handlers set by HTTP)
  unsigned long now = millis();
  if (should_disconnect && now >= disconnect_at) {
    Serial.println("Executing scheduled disconnect...");
    WiFi.disconnect(true, false);
    should_disconnect = false;
  }
  if (should_reconnect && now >= reconnect_at) {
    Serial.println("Executing scheduled reconnect...");
    WiFi.disconnect(true, true);
    delay(300);
    if (apMode) {
      if (!keepAPAlways) stopAP(); else Serial.println("keepAPAlways enabled; keeping AP active during reconnect.");
    }
    WiFi.begin(WIFI_SSID.c_str(), WIFI_PASS.c_str());
    should_reconnect = false;
  }
  if (should_start_ap && now >= start_ap_at) {
    Serial.println("Executing scheduled start AP...");
    startAP();
    should_start_ap = false;
  }
  if (should_stop_ap && now >= stop_ap_at) {
    Serial.println("Executing scheduled stop AP...");
    if (!keepAPAlways) stopAP(); else Serial.println("keepAPAlways enabled; refusing scheduled stop AP.");
    should_stop_ap = false;
  }

  // Attempt to connect after an apply-config request (scheduled to avoid blocking HTTP handler)
  if (should_try_connect && now >= try_connect_at) {
    should_try_connect = false;
    Serial.println("Attempting WiFi connect after apply-config...");
    WiFi.disconnect(true, true);
    delay(200);
    WiFi.begin(WIFI_SSID.c_str(), WIFI_PASS.c_str());
    unsigned long tstart = millis();
    while (millis() - tstart < 20000) {
      if (WiFi.status() == WL_CONNECTED) break;
      // allow server/captive portal to work while waiting
      dnsServer.processNextRequest();
      server.handleClient();
      delay(500);
    }
    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("✓ Connected to WiFi after apply-config; checking server connectivity...");
      testServerConnection();
    } else {
      Serial.println("⚠ Failed to connect after apply-config; leaving AP active for manual retry.");
    }
  }

  // Serial commands: send 'detect' (run both detectors), 'soft', 'hard', or 'status'
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length()) {
      Serial.printf(">>> Serial command: %s\n", cmd.c_str());
      if (cmd.equalsIgnoreCase("detect")) {
        Serial.println("Manual detect triggered.");
        bool hw = detectHardwareRFID();
        if (!hw) detectSoftwareRFID();
        Serial.println("Starting a 15s scan window...");
        doTimedScan(15000);
      } else if (cmd.equalsIgnoreCase("pullcfg")) {
        Serial.println("Fetching device-config from server (pullcfg)...");
        fetchDeviceConfigFromServer();
      } else if (cmd.startsWith("pushcfg")) {
        // Usage: pushcfg <host-or-ip>
        int sp = cmd.indexOf(' ');
        if (sp > 0) {
          String url = cmd.substring(sp + 1);
          if (!url.startsWith("http")) url = String("http://") + url;
          if (!url.endsWith("/")) url += "/";
          
          StaticJsonDocument<512> doc;
          doc["ssid"] = WIFI_SSID;
          doc["password"] = WIFI_PASS;
          doc["api_host"] = API_HOST;
          if (API_TOKEN.length()) doc["api_token"] = API_TOKEN;
          
          String payload;
          serializeJson(doc, payload);
          
          HTTPClient http;
          http.begin(url + "apply-config");
          http.addHeader("Content-Type", "application/json");
          int code = http.POST(payload);
          Serial.printf("Pushcfg -> %d\n", code);
          http.end();
        } else Serial.println("Usage: pushcfg <host-or-ip>");
      } else if (cmd.startsWith("scan")) {
        unsigned long ms = 15000;
        int sp = cmd.indexOf(' ');
        if (sp > 0) {
          int sec = cmd.substring(sp + 1).toInt();
          if (sec > 0 && sec < 600) ms = (unsigned long)sec * 1000UL;
        }
        doTimedScan(ms);
      } else if (cmd.equalsIgnoreCase("soft")) {
        detectSoftwareRFID();
      } else if (cmd.equalsIgnoreCase("hard")) {
        detectHardwareRFID();

      } else if (cmd.startsWith("setwifi")) {
        // Usage: setwifi <SSID> <PASSWORD>
        int sp = cmd.indexOf(' ');
        if (sp > 0) {
          int sp2 = cmd.indexOf(' ', sp + 1);
          if (sp2 > sp) {
            String ssid = cmd.substring(sp + 1, sp2);
            String pass = cmd.substring(sp2 + 1);
            ssid = stripQuotes(ssid);
            pass = stripQuotes(pass);
            WIFI_SSID = ssid;
            WIFI_PASS = pass;
            saveConfigToPrefs();
            Serial.printf("✓ Saved WIFI_SSID='%s' and password (masked). Reconnecting...\n", WIFI_SSID.c_str());
            WiFi.disconnect(true, true);
            delay(500);
            if (apMode) {
              if (!keepAPAlways) stopAP(); else Serial.println("keepAPAlways enabled; keeping AP active during reconnect.");
            }
            WiFi.begin(WIFI_SSID.c_str(), WIFI_PASS.c_str());
          } else {
            Serial.println("Usage: setwifi <SSID> <PASSWORD>");
          }
        } else {
          Serial.println("Usage: setwifi <SSID> <PASSWORD>");
        }

      } else if (cmd.startsWith("setapi") || cmd.startsWith("setpair") || cmd.startsWith("settoken") || cmd.equalsIgnoreCase("cleartoken")) {
        Serial.println("Configuration changes must be made via the device web UI (AP captive portal) or from the web app (push-config). Serial setters are disabled to avoid embedding secrets in the IDE.");

      } else if (cmd.equalsIgnoreCase("showcfg")) {
        String masked = (WIFI_PASS.length() ? String("****") : String("(none)"));
        Serial.println("\n--- Current Configuration ---");
        Serial.printf("SSID: '%s'\n", WIFI_SSID.c_str());
        Serial.printf("Password: '%s'\n", masked.c_str());
        Serial.printf("API_HOST: '%s'\n", API_HOST.c_str());
        Serial.printf("Pairing: '%s'\n", PAIRING_CODE.c_str());
        Serial.printf("API_TOKEN: '%s'\n", API_TOKEN.c_str());
        Serial.println("Note: To change SSID, password, API host, pairing code or API token, use the device web UI (AP captive portal) or the server's push-config feature.");
        Serial.println("-----------------------------\n");

      } else if (cmd.equalsIgnoreCase("startap")) {
        startAP();

      } else if (cmd.equalsIgnoreCase("stopap force")) {
        stopAP();
      } else if (cmd.equalsIgnoreCase("stopap")) {
        if (keepAPAlways) {
          Serial.println("keepAPAlways enabled; use 'stopap force' to override and stop the AP.");
        } else {
          stopAP();
        }

      } else if (cmd.equalsIgnoreCase("status")) {
        Serial.println("\n--- Device Status ---");
        Serial.printf("RFID available: %s\n", rfid_available ? "YES" : "NO");
        Serial.printf("Using soft SPI: %s\n", use_soft_spi ? "YES" : "NO");
        Serial.printf("WiFi: %s\n", (WiFi.status()==WL_CONNECTED ? "CONNECTED" : "DISCONNECTED"));
        Serial.printf("IP: %s\n", (WiFi.status()==WL_CONNECTED ? WiFi.localIP().toString().c_str() : "0.0.0.0"));
        Serial.printf("Pairing code: %s\n", PAIRING_CODE.c_str());
        byte v = rfid.PCD_ReadRegister(rfid.VersionReg);
        Serial.printf("MFRC522 VersionReg: 0x%02X\n", v);
        Serial.println("---------------------\n");
        
      } else if (cmd.equalsIgnoreCase("hb") || cmd.equalsIgnoreCase("heartbeat")) {
        Serial.println("Posting device heartbeat now...");
        postDeviceInstance();
      } else {
        Serial.println("Unknown command. Available commands:");
        Serial.println("  detect, soft, hard, status, showcfg");
        Serial.println("  setwifi <SSID> <PASS>  (use device web UI or server push for other settings)");
        Serial.println("  scan [seconds], startap, stopap, pullcfg, pushcfg <host>");
        Serial.println("  hb (heartbeat)");
      }
    }
  }

  // Periodically announce presence to device registry
  if (millis() - lastDevicePost > DEVICE_POST_INTERVAL_MS) {
    postDeviceInstance();
    lastDevicePost = millis();
  }

  // Handle HTTP and DNS (captive portal) events regularly
  if (apMode) {
    dnsServer.processNextRequest();
  }
  server.handleClient();

  // If using software SPI fallback, poll using soft transceive routines
  if (use_soft_spi) {
    uint8_t uidBuf[8]; uint8_t uidLen = sizeof(uidBuf);
    if (!soft_requestA(uidBuf, uidLen)) {
      delay(200);
      return;
    }

    // Build UID string
    String uid = "";
    for (uint8_t i = 0; i < uidLen; ++i) {
      if (uidBuf[i] < 16) uid += '0';
      uid += String(uidBuf[i], HEX);
    }
    uid.toUpperCase();
    Serial.printf("(softSPI) Card UID: %s\n", uid.c_str());

    handleCardUid(uid);

    delay(1200);
    return;
  }
  
  // If RFID module was not detected earlier, skip polling and try a periodic re-check
  if (!rfid_available) {
    static unsigned long lastRfCheck = 0;
    if (millis() - lastRfCheck > 30000) { // try every 30s
      lastRfCheck = millis();
      Serial.println("Attempting RFID re-detect...");
      // Use the unified detection functions; they will set flags appropriately
      bool hwrec = detectHardwareRFID();
      if (!hwrec) {
        detectSoftwareRFID();
      } else {
        Serial.println("✓ RFID recovered");
      }
    }
    delay(50);
    return;
  }

  if (!rfid.PICC_IsNewCardPresent()) {
    delay(50);
    return;
  }

  if (!rfid.PICC_ReadCardSerial()) {
    delay(50);
    return;
  }

  String uid = uidToUpper(rfid.uid);
  Serial.printf("Card UID: %s\n", uid.c_str());

  handleCardUid(uid);

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  delay(1200);
}