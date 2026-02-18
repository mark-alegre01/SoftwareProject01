ESP32 Provisioning & Scan Example

This folder contains an example Arduino sketch `esp32_provision_and_scan.ino` that demonstrates:

- Starting an AP and exposing `/apply-config` to accept JSON `{ api_host, ssid, password, api_token }` when the device is unconfigured.
- Storing `server`, `ssid`, `password`, and `api_token` in NVS using `Preferences`.
- Connecting to configured Wi-Fi and POSTing RFID scans to `<server>/api/rfid-scans` using header `X-Device-Token: <api_token>`.
- A minimal serial interface for manual token entry (`set token <token>`) and viewing/clearing config.

Provisioning flows supported (examples):

1) AP / Device Portal (recommended for initial setup)
   - Put ESP into AP mode (the sketch starts AP if no SSID is configured).
   - Connect laptop to the ESP's hotspot (SSID `ESP32-Setup-XXXX`).
   - POST JSON to `http://192.168.4.1/apply-config` with fields: `api_host`, `ssid`, `password`, optionally `api_token`.
   - Example curl (from laptop connected to AP):
     ```
     curl -X POST http://192.168.4.1/apply-config \
       -H "Content-Type: application/json" \
       -d '{"api_host":"https://your.server","ssid":"MyWiFi","password":"MyPass","api_token":"<token>"}'
     ```
   - After successful apply-config, the device will stop AP and attempt to connect to the configured Wi‑Fi.

2) Web app -> Push config
   - As an admin in the web app, you can use the Devices page's "Push To ESP" (direct push) function to post the same JSON to the device's `/apply-config` endpoint.

3) Manual / Serial (quick)
   - If you already have Wi‑Fi set but need to add a token, connect via USB serial and send:
     - `set token <token>` to store the token
     - `show config` to view stored server/ssid/token
     - `clear token` to remove token

Notes and security tips
- The sketch uses `WiFiClientSecure::setInsecure()` in order to work with arbitrary HTTPS test servers without certificate pinning; in production you should pin certificates or verify server identity.
- Tokens are stored in NVS plaintext (Preferences). If you need higher security, store secrets encrypted or protect device physical access.
- The server endpoints that the sketch interacts with are:
  - GET `/api/device-config` (UI uses to display config; devices may request this after token is set)
  - POST `/api/rfid-scans` to send scans (requires `X-Device-Token` header)
  - POST `/apply-config` on the device (used by the web app push and AP portal)

How to get a token
- Use the web app Devices page: claim the device and then "Show Token" or "Regenerate Token". Copy that token and paste into the device via the AP portal (include `api_token` in `/apply-config`) or via USB serial "set token".

Example server command to push config (server-side):

  curl -X POST https://your.server/api/device-instances/push-config \
    -H "Content-Type: application/json" -H "X-CSRFToken: <csrf>" \
    -d '{"ip":"192.168.1.42"}'

(When you use the web UI "Push To ESP" button it will make the same request from the server.)

This sketch is intended as a clear, minimal example — adapt to your hardware pinout and production security requirements.
