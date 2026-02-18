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

**Configuration note:** Do NOT hard-code Wi‑Fi credentials or the API host in the sketch. The project provides a *Device Config* in the web app (available in the sidebar modal or in the admin). Devices load persistent configuration from NVS on boot and will attempt to fetch an authoritative config from the server; you can also push config from the web UI to an online device.

Below is an example of how an already-connected device would POST a borrow request — the sketch should obtain Wi‑Fi details from Preferences or the web app rather than hard-coding them.

```cpp
// After connecting to WiFi (from prefs / server)
HTTPClient http;
http.begin("http://192.168.1.100:8000/api/borrow");
http.addHeader("Content-Type", "application/json");
String body = String("{\"borrower_rfid\":\"RFID_UID\",\"item_qr\":\"ITEM_QR\"}");
int code = http.POST(body);
Serial.printf("Borrow response: %d\n", code);
Serial.println(http.getString());
http.end();
```

Tip: You can implement a two-step scan on the ESP32 (first RFID, then QR) and only POST once both are captured.

## Notes
- Default DB is SQLite; switch to PostgreSQL/MySQL in `settings.py` for production.
- CORS is wide open for development. Restrict for production deployments.
- Use admin to pre-register borrowers and items (RFID UID and QR code values must match what devices scan).

## ESP32 Device Portal (Auto-detect)

A simple device provisioning portal is available at **Devices & Provisioning** (`/devices`). It allows administrators to set the canonical device configuration (API host, Wi‑Fi SSID/password) and to discover ESP32 devices:

- **Discover Devices**: lists devices that have previously registered themselves with the server.
- **Auto-detect (Scan LAN)**: performs a quick scan of the local /24 network to find devices that respond on port 80 and provides quick actions to register or use the discovered IP address.

Use **Push to All Discovered** or the per-device **Provision** action to push the canonical settings to devices. Only staff users can push configuration changes to devices.

Notes on provisioning workflow:
- The UI supports a **Direct Push** (browser -> ESP) which attempts to POST the config straight to the device at `http://<esp-ip>/apply-config`. This is convenient when your browser can reach the device directly, but it may fail if the device does not allow cross-origin requests (CORS) or if network isolation is in place.
- If Direct Push fails and you are an administrator or the device owner, the web app will attempt a server-side push which posts the config to the device from the server (more reliable on typical LANs).
- Use the **Auto-detect (Scan LAN)** to quickly find candidate ESP IPs on your local /24 network.

Remote control & recovery:
- **Remote Reboot**: administrators and device owners can send a remote reboot to a device from the Devices page. This is useful if a device becomes unresponsive or needs to restart networking.
- **Reboot & Retry**: a convenience action will send a reboot, wait for the device to come back online, then attempt server-side provisioning automatically (with multiple retries and polling for reachability).

AP (Hotspot) provisioning:
- **Start AP**: send a control command to the device to enter AP/hotspot mode (action `startap`). The device will create its own Wi‑Fi network (SSID typically `ESP-xxxx`) and serve a small captive portal at `http://192.168.4.1/`.
- **Open Portal / AP Config**: when connected to the device AP, use the **Open Portal** button to open the device's portal in a new tab, or use **AP Config** to open an in-page modal that checks the portal and attempts to push SSID/server settings directly to the device portal (tries several common endpoints such as `/apply-config` and `/config`). This flow is useful when your laptop cannot reach the device from your normal LAN, or when CORS prevents browser->device pushes.
- After AP provisioning, the device should connect to your Wi‑Fi and then fetch configuration from the server (or the web UI can invoke server-side provision once the device returns online).


