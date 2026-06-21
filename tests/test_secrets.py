"""Tests for secret redaction and git secret scanning hooks."""

import subprocess
from pathlib import Path

from docintel.ops.secrets import credential_fingerprint, redact_text


ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".githooks"


def test_redact_text_masks_openai_key():
    raw = "failed with sk-abcdefghijklmnopqrstuvwxyz1234567890"
    assert "sk-[REDACTED]" in redact_text(raw)
    assert "abcdefghijklmnopqrstuvwxyz1234567890" not in redact_text(raw)


def test_redact_text_masks_bearer_header():
    raw = "Authorization: Bearer super-secret-token-value-12345"
    redacted = redact_text(raw)
    assert "super-secret-token-value-12345" not in redacted
    assert "[REDACTED]" in redacted


def test_credential_fingerprint_is_not_reversible():
    a = credential_fingerprint("my-real-api-key-value", prefix="key")
    b = credential_fingerprint("my-real-api-key-value", prefix="key")
    c = credential_fingerprint("other-key", prefix="key")
    assert a == b
    assert a != c
    assert "my-real-api-key-value" not in a


def test_pre_commit_blocks_staged_env_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)

    scan = HOOKS / "scan-secrets.sh"
    (repo / ".env").write_text("OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz\n", encoding="utf-8")
    subprocess.run(["git", "add", ".env"], cwd=repo, check=True, capture_output=True)

    result = subprocess.run(
        ["sh", str(scan)],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "blocked file staged" in result.stderr


def test_pre_commit_blocks_openai_key_in_source(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)

    scan = HOOKS / "scan-secrets.sh"
    (repo / "config.py").write_text(
        'API_KEY = "sk-abcdefghijklmnopqrstuvwxyz1234567890"\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "config.py"], cwd=repo, check=True, capture_output=True)

    result = subprocess.run(
        ["sh", str(scan)],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "OpenAI-style API key pattern" in result.stderr
