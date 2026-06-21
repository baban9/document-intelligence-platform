"""Encrypt tenant secrets at rest in PostgreSQL."""

from __future__ import annotations

import base64
import hashlib
import os

ENCRYPTED_PREFIX = "enc:v1:"
USER_ENCRYPTED_PREFIX = "enc:u1:"


def encryption_enabled() -> bool:
    return bool(os.getenv("DOCINTEL_SETTINGS_ENCRYPTION_KEY", "").strip())


def _master_material() -> bytes:
    raw = os.getenv("DOCINTEL_SETTINGS_ENCRYPTION_KEY", "").strip()
    if raw:
        return hashlib.sha256(raw.encode("utf-8")).digest()
    return hashlib.sha256(b"docintel-dev-settings-key").digest()


def _fernet_key() -> bytes:
    raw = os.getenv("DOCINTEL_SETTINGS_ENCRYPTION_KEY", "").strip()
    if not raw:
        return base64.urlsafe_b64encode(_master_material())
    try:
        decoded = base64.urlsafe_b64decode(raw.encode("ascii"))
        if len(decoded) == 32:
            return base64.urlsafe_b64encode(decoded)
    except Exception:
        pass
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _user_fernet_key(owner_id: str) -> bytes:
    owner = owner_id.strip()
    if not owner:
        raise ValueError("owner_id is required for user-bound encryption.")
    material = hashlib.sha256(_master_material() + b":" + owner.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(material)


def encrypt_secret(value: str) -> str:
    """Return an encrypted value or plaintext when encryption is disabled."""
    if not value:
        return ""
    if not encryption_enabled():
        return value
    from cryptography.fernet import Fernet

    token = Fernet(_fernet_key()).encrypt(value.encode("utf-8")).decode("ascii")
    return f"{ENCRYPTED_PREFIX}{token}"


def encrypt_user_secret(value: str, owner_id: str) -> str:
    """Encrypt a secret bound to the settings user who owns it."""
    if not value:
        return ""
    owner = owner_id.strip()
    if not owner:
        return encrypt_secret(value)
    from cryptography.fernet import Fernet

    token = Fernet(_user_fernet_key(owner)).encrypt(value.encode("utf-8")).decode("ascii")
    return f"{USER_ENCRYPTED_PREFIX}{owner}:{token}"


def decrypt_secret(stored: str) -> str:
    """Decrypt a stored secret; pass through legacy plaintext values."""
    if not stored:
        return ""
    if stored.startswith(USER_ENCRYPTED_PREFIX):
        return decrypt_user_secret(stored)
    if not stored.startswith(ENCRYPTED_PREFIX):
        return stored
    from cryptography.fernet import Fernet

    token = stored[len(ENCRYPTED_PREFIX) :]
    return Fernet(_fernet_key()).decrypt(token.encode("ascii")).decode("utf-8")


def decrypt_user_secret(stored: str, owner_id: str | None = None) -> str:
    """Decrypt a user-bound secret using the owner id embedded in the payload."""
    if not stored:
        return ""
    if not stored.startswith(USER_ENCRYPTED_PREFIX):
        return decrypt_secret(stored)

    payload = stored[len(USER_ENCRYPTED_PREFIX) :]
    embedded_owner, _, token = payload.partition(":")
    resolved_owner = (owner_id or embedded_owner).strip()
    if not resolved_owner or resolved_owner != embedded_owner:
        raise RuntimeError("API key owner mismatch.")

    from cryptography.fernet import Fernet

    return Fernet(_user_fernet_key(resolved_owner)).decrypt(token.encode("ascii")).decode("utf-8")
