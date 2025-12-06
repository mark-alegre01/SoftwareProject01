/*
  ESP32-S3 + MFRC522 (SPI) -> Django RFID Borrowing System
  - Reads card UID via SPI
  - Calls Django API to ensure borrower exists and optionally borrow an item
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <MFRC522.h>

/* ----------- USER CONFIG ----------- */
const char* WIFI_SSID = "LadyJune";
const char* WIFI_PASS = "TwinStar@2025";
const char* API_HOST  = "http://192.168.1.34:8000";

/* Set to a real item QR code if you want auto borrow right after card tap */
String FORCED_ITEM_QR = "";

/* SPI Pin mapping (adjust if needed) */
#define PIN_SCK   12
#define PIN_MOSI  11
#define PIN_MISO  13
#define PIN_SS    10
#define PIN_RST    4

MFRC522 rfid(PIN_SS, PIN_RST);

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
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
    if (millis() - start > 30000) {
      Serial.println("\nRe-starting WiFi...");
      WiFi.disconnect(true, true);
      delay(1000);
      WiFi.begin(WIFI_SSID, WIFI_PASS);
      start = millis();
    }
  }
  Serial.print("\nWiFi connected. IP: ");
  Serial.println(WiFi.localIP());
}

bool httpPostJson(const String& url, const String& body, String& resp, int& code) {
  ensureWiFi();
  
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("ERROR: WiFi not connected!");
    code = -2;
    return false;
  }
  
  HTTPClient http;
  http.setConnectTimeout(10000);
  http.setTimeout(15000);
  
  Serial.printf("Attempting POST to: %s\n", url.c_str());
  Serial.printf("Request body: %s\n", body.c_str());
  
  if (!http.begin(url)) {
    Serial.println("ERROR: http.begin() failed!");
    Serial.println("TROUBLESHOOTING:");
    Serial.println("1. Verify server is running");
    Serial.println("2. Check IP address: " + String(API_HOST));
    Serial.println("3. Ensure firewall allows port 8000");
    code = -3;
    return false;
  }
  
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Connection", "close");
  
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
      Serial.println("2. Check Windows Firewall allows port 8000");
      Serial.println("3. Verify IP address: " + String(API_HOST));
      Serial.println("4. Try: python manage.py runserver 0.0.0.0:8000");
    }
  }
  
  http.end();
  return (code >= 200 && code < 300);
}

String buildApiBase() {
  String baseUrl = String(API_HOST);
  if (baseUrl.endsWith("/")) {
    baseUrl.remove(baseUrl.length() - 1);
  }
  return baseUrl;
}

bool borrowerExists(const String& uid) {
  ensureWiFi();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("ERROR: WiFi not connected, cannot check borrower registration!");
    return false;
  }

  HTTPClient http;
  http.setConnectTimeout(10000);  // Increased timeout
  http.setTimeout(10000);

  String url = buildApiBase() + "/api/borrowers?q=" + uid;
  Serial.printf("Checking borrower registration: %s\n", url.c_str());

  if (!http.begin(url)) {
    Serial.println("ERROR: http.begin() failed during borrower lookup!");
    Serial.println("TROUBLESHOOTING:");
    Serial.println("1. Verify server is running: python manage.py runserver 0.0.0.0:8000");
    Serial.println("2. Check IP address matches your computer's LAN IP");
    Serial.println("3. Ensure ESP32 and computer are on same Wi-Fi network");
    return false;
  }

  int code = http.GET();
  bool exists = false;

  if (code >= 200 && code < 300) {
    String resp = http.getString();
    // Check for exact match (case-insensitive search in response)
    String searchPattern = String("\"rfid_uid\":\"") + uid + "\"";
    String searchPatternLower = searchPattern;
    searchPatternLower.toLowerCase();
    String respLower = resp;
    respLower.toLowerCase();
    
    exists = respLower.indexOf(searchPatternLower) != -1;
    Serial.printf("Borrower lookup -> %d (exists=%s)\n", code, exists ? "yes" : "no");
    if (!exists && resp.length() > 0) {
      Serial.printf("Response preview: %s\n", resp.substring(0, min(200, (int)resp.length())).c_str());
    }
  } else if (code == -1) {
    Serial.printf("Borrower lookup failed -> Connection refused (code %d)\n", code);
    Serial.println("TROUBLESHOOTING:");
    Serial.println("1. Server is not running or not accessible");
    Serial.println("2. Check Windows Firewall allows port 8000");
    Serial.println("3. Verify IP address: " + String(API_HOST));
    Serial.println("4. Try: python manage.py runserver 0.0.0.0:8000");
  } else {
    Serial.printf("Borrower lookup failed -> %d (%s)\n", code, http.errorToString(code).c_str());
  }

  http.end();
  return exists;
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
  String baseUrl = String(API_HOST);
  if (baseUrl.endsWith("/")) {
    baseUrl.remove(baseUrl.length() - 1);
  }
  
  HTTPClient http;
  http.setConnectTimeout(5000);
  http.setTimeout(5000);
  
  String testUrl = baseUrl + "/api/borrowers";
  Serial.printf("Testing connection to: %s\n", testUrl.c_str());
  
  if (http.begin(testUrl)) {
    http.addHeader("Content-Type", "application/json");
    int code = http.GET();
    Serial.printf("Test GET -> %d\n", code);
    if (code > 0) {
      Serial.println("Server is reachable!");
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

void setup() {
  Serial.begin(115200);
  delay(800);
  Serial.println("\nBooting...");

  ensureWiFi();

  SPI.begin(PIN_SCK, PIN_MISO, PIN_MOSI, PIN_SS);
  rfid.PCD_Init();

  delay(50);
  Serial.print("MFRC522 version: ");
  byte v = rfid.PCD_ReadRegister(rfid.VersionReg);
  if (v == 0x00 || v == 0xFF) {
    Serial.println("Not detected (check wiring and power).");
  } else {
    Serial.printf("0x%02X\n", v);
    rfid.PCD_SetAntennaGain(rfid.RxGain_max);
  }

  Serial.println("\nTesting server connectivity...");
  testServerConnection();
  
  Serial.println("Ready. Tap a card...");
}

void loop() {
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

  const CardHolder* holder = findHolderByUid(uid);
  String name  = holder ? String(holder->name)  : ("RFID " + uid);
  String email = holder ? String(holder->email) : "";

  if (!borrowerExists(uid)) {
    logRegistrationScan(uid, name.c_str(), email.c_str());
    Serial.println("Borrower not registered on server. Please register in the web app before borrowing.");
  } else {
    logRegistrationScan(uid, name.c_str(), email.c_str());
    if (logBorrowTap(uid, name.c_str(), email.c_str()) && !FORCED_ITEM_QR.isEmpty()) {
      Serial.printf("Auto-borrowing item: %s\n", FORCED_ITEM_QR.c_str());
      postBorrow(uid, FORCED_ITEM_QR);
    }
  }

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  delay(1200);
}
