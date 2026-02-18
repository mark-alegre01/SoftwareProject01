from __future__ import annotations

from django.db import models
import secrets


def _default_api_token():
    return secrets.token_hex(32)


class Borrower(models.Model):
    name = models.CharField(max_length=120)
    rfid_uid = models.CharField(max_length=64, unique=True)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.rfid_uid})"


class Item(models.Model):
    name = models.CharField(max_length=200)
    qr_code = models.CharField(max_length=128, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.qr_code})"


class BorrowTransaction(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        RETURNED = "RETURNED", "Returned"

    borrower = models.ForeignKey(Borrower, on_delete=models.PROTECT, related_name="transactions")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="transactions")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    borrowed_at = models.DateTimeField(auto_now_add=True)
    returned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "item"]),
            models.Index(fields=["borrower", "status"]),
        ]
        ordering = ["-borrowed_at"]

    def __str__(self) -> str:
        return f"{self.item} -> {self.borrower} [{self.status}]"


class RFIDScan(models.Model):
    uid = models.CharField(max_length=64)
    name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.uid} @ {self.created_at}"


class DeviceConfig(models.Model):
    """Singleton-like model to store ESP32 / device credentials visible to the web app.

    NOTE: passwords are stored encrypted in `encrypted_password`. The legacy `password` field
    is still present for migration compatibility but is no longer returned by the API.
    """
    ssid = models.CharField(max_length=128, blank=True, default='')
    # Legacy plaintext field (kept to avoid migration complexity). New code should use
    # `encrypted_password` via `set_password` / `get_password` helpers.
    password = models.CharField(max_length=128, blank=True, default='')
    encrypted_password = models.TextField(blank=True, default='')
    api_host = models.CharField(max_length=256, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Device Configuration"
        verbose_name_plural = "Device Configuration"

    def __str__(self) -> str:
        return f"DeviceConfig (api_host={self.api_host})"

    def set_password(self, raw: str):
        """Encrypt and store a password, clearing legacy plaintext field."""
        from .crypto import encrypt_text
        if not raw:
            self.encrypted_password = ''
            self.password = ''
        else:
            self.encrypted_password = encrypt_text(raw)
            self.password = ''

    def get_password(self) -> str:
        """Return decrypted password if available, else return legacy plaintext field or empty string."""
        from .crypto import decrypt_text
        if self.encrypted_password:
            return decrypt_text(self.encrypted_password) or ''
        return self.password or ''


class DeviceInstance(models.Model):
    """Represents a discovered ESP device that periodically registers itself with the server."""
    ip = models.CharField(max_length=64)
    api_host = models.CharField(max_length=256, blank=True, default='')
    ssid = models.CharField(max_length=128, blank=True, default='')
    firmware = models.CharField(max_length=64, blank=True, default='')
    # Short pairing code shown by device's captive portal or serial for claiming ownership
    pairing_code = models.CharField(max_length=32, blank=True, default='')
    # Optional claim ownership by a user/admin
    claimed_by = models.ForeignKey(
        'auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='claimed_devices'
    )
    claimed_at = models.DateTimeField(null=True, blank=True)

    # Per-device API token (used by the ESP to authenticate requests)
    api_token = models.CharField(max_length=64, unique=True, default=_default_api_token)

    # Extended telemetry from device heartbeats
    last_wifi_event = models.CharField(max_length=64, blank=True, default='')
    last_rssi = models.IntegerField(null=True, blank=True)
    last_disconnect_reason = models.CharField(max_length=128, blank=True, default='')
    server_reachable = models.BooleanField(default=False)

    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_seen"]

    def __str__(self) -> str:
        owner = self.claimed_by.username if self.claimed_by else 'unclaimed'
        return f"{self.ip} ({self.firmware}) @ {self.last_seen} [{owner}]"

    def regenerate_token(self) -> str:
        """Generate and persist a new api_token, returning it."""
        import secrets
        self.api_token = secrets.token_hex(32)
        self.save(update_fields=["api_token"])
        return self.api_token


