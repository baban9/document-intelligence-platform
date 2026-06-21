"""Encrypt tenant secrets at rest in PostgreSQL."""

from __future__ import annotations

import base64
import hashlib
import os

ENCRYPTED_PREFIX = "enc:v1:"


def encryption_enabled() -> bool:
    return bool(os.getenv("DOCINTEL_SETTINGS_ENCRYPTION_KEY", "").strip())


def _fernet_key() -> bytes | None:
    raw = os.getenv("DOCINTEL_SETTINGS_ENCRYPTION_KEY", "").strip()
    if not raw:
        return None
    try:
        decoded = base64.urlsafe_b64decode(raw.encode("ascii"))
        if len(decoded) == 32:
            return base64.urlsafe_b64encode(decoded)
    except Exception:
        pass
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(value: str) -> str:
    """Return an encrypted value or plaintext when encryption is disabled."""
    if not value:
        return ""
    key = _fernet_key()
    if key is None:
        return value
    from cryptography.fernet import Fernet

    token = Fernet(key).encrypt(value.encode("utf-8")).decode("ascii")
    return f"{ENCRYPTED_PREFIX}{token}"


def decrypt_secret(stored: str) -> str:
    """Decrypt a stored secret; pass through legacy plaintext values."""
    if not stored:
        return ""
    if not stored.startswith(ENCRYPTED_PREFIX):
        return stored
    key = _fernet_key()
    if key is None:
        raise RuntimeError(
            "DOCINTEL_SETTINGS_ENCRYPTION_KEY is required to decrypt stored API keys."
        )
    from cryptography.fernet import Fernet

    token = stored[len(ENCRYPTED_PREFIX) :]
    return Fernet(key).decrypt(token.encode("ascii")).decode("utf-8")
