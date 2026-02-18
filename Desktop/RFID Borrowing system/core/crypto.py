"""Simple encryption helpers for device secrets.

Uses Fernet (cryptography) when available and falls back to Django signing if not.
"""
from __future__ import annotations

import base64
import logging
from django.conf import settings

try:
    from cryptography.fernet import Fernet, InvalidToken
    HAS_FERNET = True
except Exception:
    HAS_FERNET = False

from django.core import signing

logger = logging.getLogger(__name__)


def _get_fernet() -> "Fernet | None":
    key = getattr(settings, "FERNET_KEY", None)
    if not key:
        return None
    try:
        if isinstance(key, str):
            key_b = key.encode("utf-8")
        else:
            key_b = key
        # Ensure key is urlsafe base64 32 bytes
        # If user provided raw bytes, assume correct; else accept provided base64 key
        return Fernet(key_b)
    except Exception:
        logger.exception("Invalid FERNET_KEY setting")
        return None


def encrypt_text(plaintext: str) -> str:
    """Return an encrypted string usable for storage."""
    if not plaintext:
        return ""
    if HAS_FERNET:
        f = _get_fernet()
        if f:
            try:
                return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")
            except Exception:
                logger.exception("Fernet encryption failed")
    # Fallback: use django signing (not true encryption but tamper-evident)
    return signing.dumps(plaintext)


def decrypt_text(ciphertext: str) -> str:
    """Decrypt previously-encrypted string; returns plaintext or empty string on error."""
    if not ciphertext:
        return ""
    if HAS_FERNET:
        f = _get_fernet()
        if f:
            try:
                return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
            except InvalidToken:
                logger.exception("Invalid Fernet token")
            except Exception:
                logger.exception("Fernet decryption failed")
    # Fallback: try django signing loads
    try:
        return signing.loads(ciphertext)
    except Exception:
        logger.exception("Django signing loads failed for ciphertext")
        return ""
