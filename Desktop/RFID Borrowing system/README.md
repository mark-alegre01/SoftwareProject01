# RFID Borrowing System (Django)

This is a minimal borrowing/return system designed for RFID (borrower ID) and QR (item) scanning. Intended to be used with an ESP32-CAM (for QR) and an RFID reader (MFRC522/PN532/etc.).

## Features
- Register borrowers (by RFID UID) and items (by QR code)
- Create borrow transactions when both IDs are provided
- Prevent borrowing items that are already checked out
- Return items by `item_qr` or by `transaction_id`
- Django admin and a simple dashboard page
- REST API via Django REST Framework

## Quickstart

1) Create and activate a virtual environment, then install dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\python -m ensurepip --upgrade
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

2) Create database and superuser:

```powershell
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py createsuperuser
```

3) Run the server:

```powershell
.\.venv\Scripts\python manage.py runserver 0.0.0.0:8000
```

- Admin: `http://localhost:8000/admin/`
- Dashboard: `http://localhost:8000/core/dashboard`

## API

- POST `/api/borrow`
  - Body: `{ "borrower_rfid": "RFID_UID", "item_qr": "QR_CODE" }`
  - Creates a borrow transaction if available

- POST `/api/return`
  - Body: `{ "item_qr": "QR_CODE" }` or `{ "transaction_id": 123 }`
  - Closes an open transaction

- GET/POST `/api/borrowers`
- GET/POST `/api/items`

## ESP32-CAM Example (Arduino)

Replace `WIFI_SSID`, `WIFI_PASS`, and API host/port as needed.

```cpp
#include <WiFi.h>
#include <HTTPClient.h>

const char* ssid = "WIFI_SSID";
const char* pass = "WIFI_PASS";

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, pass);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");

  // Example values collected after scanning
  String borrowerRfid = "RFID_UID_SAMPLE"; // from RFID reader
  String itemQr = "ITEM_QR_SAMPLE";       // from QR detection

  HTTPClient http;
  http.begin("http://192.168.1.100:8000/api/borrow");
  http.addHeader("Content-Type", "application/json");
  String body = String("{\"borrower_rfid\":\"") + borrowerRfid + "\",\"item_qr\":\"" + itemQr + "\"}";
  int code = http.POST(body);
  Serial.printf("Borrow response: %d\n", code);
  Serial.println(http.getString());
  http.end();
}

void loop() {}
```

Tip: You can implement a two-step scan on the ESP32 (first RFID, then QR) and only POST once both are captured.

## Notes
- Default DB is SQLite; switch to PostgreSQL/MySQL in `settings.py` for production.
- CORS is wide open for development. Restrict for production deployments.
- Use admin to pre-register borrowers and items (RFID UID and QR code values must match what devices scan).


