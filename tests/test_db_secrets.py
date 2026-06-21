"""Tests for tenant secret encryption."""

from docintel.db.secrets import (
    decrypt_secret,
    decrypt_user_secret,
    encrypt_secret,
    encrypt_user_secret,
    encryption_enabled,
)


def test_encrypt_decrypt_roundtrip(monkeypatch):
    monkeypatch.setenv("DOCINTEL_SETTINGS_ENCRYPTION_KEY", "unit-test-encryption-key")
    plain = "sk-test-api-key-value"
    encrypted = encrypt_secret(plain)
    assert encrypted.startswith("enc:v1:")
    assert decrypt_secret(encrypted) == plain
    assert encryption_enabled() is True


def test_encrypt_user_secret_roundtrip(monkeypatch):
    monkeypatch.setenv("DOCINTEL_SETTINGS_ENCRYPTION_KEY", "unit-test-encryption-key")
    owner = "browser-user-abc"
    plain = "sk-user-bound-key"
    encrypted = encrypt_user_secret(plain, owner)
    assert encrypted.startswith("enc:u1:")
    assert owner in encrypted
    assert decrypt_user_secret(encrypted, owner_id=owner) == plain


def test_plaintext_passthrough_when_encryption_disabled(monkeypatch):
    monkeypatch.delenv("DOCINTEL_SETTINGS_ENCRYPTION_KEY", raising=False)
    plain = "legacy-plain-key"
    assert encrypt_secret(plain) == plain
    assert decrypt_secret(plain) == plain


def test_legacy_plaintext_still_readable(monkeypatch):
    monkeypatch.setenv("DOCINTEL_SETTINGS_ENCRYPTION_KEY", "unit-test-encryption-key")
    assert decrypt_secret("legacy-plain-key") == "legacy-plain-key"
