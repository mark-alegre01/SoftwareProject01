/*
  ESP32 Example: Provisioning + Token storage + RFID scan POST

  Features demonstrated:
  - Store / retrieve credentials & API token in NVS (Preferences)
  - Simple AP + /apply-config endpoint to accept JSON config when unprovisioned
  - Connect to configured Wi-Fi and POST RFID scans to server with X-Device-Token
  - Simple serial helper to set/update token or show stored config

  Notes:
  - Requires ArduinoJson (https://arduinojson.org/) and MFRC522 library
  - For HTTPS servers, this sketch sets WiFiClientSecure::setInsecure() for simplicity
    (do certificate pinning in production)
*/

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <Preferences.h>
#include <SPI.h>
#include <MFRC522.h>
#include <ArduinoJson.h>

// RFID pins (adjust to your wiring)
#define RST_PIN  22
#define SS_PIN   5
MFRC522 rfid(SS_PIN, RST_PIN);

Preferences prefs;
WebServer server(80);

// Config keys in NVS
const char* PREF_NAMESPACE = "device";
const char* KEY_SSID = "ssid";
const char* KEY_PASS = "pass";
const char* KEY_SERVER = "server";
const char* KEY_TOKEN = "token";

void startAP() {
  WiFi.mode(WIFI_AP);
  const char* ap_ssid = "ESP32-Setup-";
  // Append last 4 chars of MAC to make SSID slightly unique
  uint8_t mac[6];
  esp_read_mac(mac, ESP_MAC_WIFI_STA);
  char mactail[8];
  snprintf(mactail, sizeof(mactail), "%02X%02X", mac[4], mac[5]);
  String ss = String(ap_ssid) + mactail;
  WiFi.softAP(ss.c_str());

  // Simple endpoint to receive JSON { api_host, ssid, password, api_token (optional) }
  server.on("/apply-config", HTTP_POST, []() {
    String body = server.arg("plain");
    DynamicJsonDocument doc(512);
    DeserializationError err = deserializeJson(doc, body);
    if (err) {
      server.send(400, "application/json", "{\"detail\":\"invalid json\"}");
      return;
    }
    const char* api_host = doc.containsKey("api_host") ? doc["api_host"] : "";
    const char* ssid = doc.containsKey("ssid") ? doc["ssid"] : "";
    const char* password = doc.containsKey("password") ? doc["password"] : "";
    const char* token = doc.containsKey("api_token") ? doc["api_token"] : "";

    prefs.begin(PREF_NAMESPACE, false);
    if (ssid && strlen(ssid)) prefs.putString(KEY_SSID, ssid);
    if (password && strlen(password)) prefs.putString(KEY_PASS, password);
    if (api_host && strlen(api_host)) prefs.putString(KEY_SERVER, api_host);
    if (token && strlen(token)) prefs.putString(KEY_TOKEN, token);
    prefs.end();

    // optional: respond with current config
    DynamicJsonDocument resp(256);
    resp["status"] = "ok";
    String out;
    serializeJson(resp, out);
    server.send(200, "application/json", out);

    // Attempt to apply network changes (in main loop we will reconnect when AP stops)
  });

  server.onNotFound([](){ server.send(404, "text/plain", "Not found"); });
  server.begin();
  Serial.println("AP started. Connect to the hotspot and POST /apply-config with JSON payload.");
}

void stopAP() {
  server.stop();
  WiFi.softAPdisconnect(true);
  delay(200);
}

bool connectToWifi(const String &ssid, const String &pass, uint32_t timeoutMs = 15000) {
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid.c_str(), pass.c_str());
  Serial.printf("Connecting to %s ...\n", ssid.c_str());
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < timeoutMs) {
    delay(200);
    Serial.print('.');
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("Connected, IP: %s\n", WiFi.localIP().toString().c_str());
    return true;
  }
  Serial.println("Failed to connect");
  return false;
}

bool postScan(const String &serverUrl, const String &token, const String &uid) {
  if (!serverUrl.length() || !token.length()) {
    Serial.println("Missing server or token");
    return false;
  }
  String url = serverUrl;
  if (url.endsWith('/')) url += "api/rfid-scans";
  else url += "/api/rfid-scans";

  WiFiClientSecure client;
  // WARNING: setInsecure skips cert verification. For production, do certificate pinning.
  client.setInsecure();

  HTTPClient http;
  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Token", token);
  DynamicJsonDocument j(256);
  j["uid"] = uid;
  String body;
  serializeJson(j, body);
  int code = http.POST(body);
  Serial.printf("POST %s -> %d\n", url.c_str(), code);
  bool ok = (code >= 200 && code < 300);
  String resp = http.getString();
  Serial.println(resp);
  http.end();

  return ok;
}

void handleSerialInput() {
  static String line;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (line.length()) {
        // simple commands:
        // set token <token>
        // show config
        // clear token
        if (line.startsWith("set token ")) {
          String t = line.substring(10);
          prefs.begin(PREF_NAMESPACE, false);
          prefs.putString(KEY_TOKEN, t);
          prefs.end();
          Serial.println("Token saved");
        } else if (line == "show config") {
          prefs.begin(PREF_NAMESPACE, false);
          Serial.printf("server=%s\n", prefs.getString(KEY_SERVER, "").c_str());
          Serial.printf("ssid=%s\n", prefs.getString(KEY_SSID, "").c_str());
          Serial.printf("token=%s\n", prefs.getString(KEY_TOKEN, "").c_str());
          prefs.end();
        } else if (line == "clear token") {
          prefs.begin(PREF_NAMESPACE, false);
          prefs.remove(KEY_TOKEN);
          prefs.end();
          Serial.println("Token removed");
        } else {
          Serial.println("Unknown command. Use: set token <token> | show config | clear token");
        }
      }
      line = "";
    } else {
      line += c;
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("ESP32 Provision & RFID example starting...");

  SPI.begin();
  rfid.PCD_Init();

  prefs.begin(PREF_NAMESPACE, false);
  String ssid = prefs.getString(KEY_SSID, "");
  String pass = prefs.getString(KEY_PASS, "");
  String serverUrl = prefs.getString(KEY_SERVER, "");
  String token = prefs.getString(KEY_TOKEN, "");
  prefs.end();

  if (!ssid.length()) {
    Serial.println("No Wi-Fi configured. Starting AP for provisioning...");
    startAP();
  } else {
    if (!connectToWifi(ssid, pass)) {
      Serial.println("Wi-Fi connect failed. Starting AP for provisioning...");
      startAP();
    } else {
      Serial.println("Connected to Wi-Fi. Ready to post scans if token present.");
    }
  }

  // start serial help
  Serial.println("Serial commands: set token <token> | show config | clear token");
}

unsigned long lastRfidCheck = 0;

void loop() {
  handleSerialInput();

  // If AP is running, handle web server requests
  if (WiFi.getMode() == WIFI_AP) {
    server.handleClient();
    // If a config was applied by the web portal, stop AP and try to connect
    prefs.begin(PREF_NAMESPACE, false);
    String ssid = prefs.getString(KEY_SSID, "");
    String pass = prefs.getString(KEY_PASS, "");
    prefs.end();
    if (ssid.length()) {
      Serial.println("Config applied; stopping AP and attempting Wi-Fi connect...");
      stopAP();
      if (connectToWifi(ssid, pass)) {
        Serial.println("Connected after provisioning");
      } else {
        Serial.println("Connect failed after provisioning; restart device AP mode to reconfigure");
        startAP();
      }
    }
    delay(100);
    return;
  }

  // Normal operating mode: check RFID tag periodically
  if (millis() - lastRfidCheck > 400) {
    lastRfidCheck = millis();
    if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
      String uid;
      for (byte i = 0; i < rfid.uid.size; i++) {
        uid += String(rfid.uid.uidByte[i] < 0x10 ? "0" : "");
        uid += String(rfid.uid.uidByte[i], HEX);
      }
      uid.toUpperCase();
      Serial.printf("Read UID: %s\n", uid.c_str());

      prefs.begin(PREF_NAMESPACE, false);
      String serverUrl = prefs.getString(KEY_SERVER, "");
      String token = prefs.getString(KEY_TOKEN, "");
      prefs.end();

      if (serverUrl.length() && token.length()) {
        bool ok = postScan(serverUrl, token, uid);
        if (!ok) {
          Serial.println("POST failed; server may have rejected token. Please ensure token is valid or regenerate it from web UI.");
        }
      } else {
        Serial.println("Missing server URL or token; cannot post scan. Use AP portal or serial to configure.");
      }
      rfid.PICC_HaltA();
      rfid.PCD_StopCrypto1();
    }
  }
}
