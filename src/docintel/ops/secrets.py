"""Secret redaction and credential fingerprinting (never log raw API keys)."""

from __future__ import annotations

import hashlib
import re
from typing import Iterable

# Patterns for values that must never appear in logs or error responses.
_REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "sk-[REDACTED]"),
    (re.compile(r"gsk_[A-Za-z0-9]{20,}"), "gsk_[REDACTED]"),
    (re.compile(r"AIzaSy[A-Za-z0-9_-]{20,}"), "AIzaSy[REDACTED]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA[REDACTED]"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "ghp_[REDACTED]"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "github_pat_[REDACTED]"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "xox[REDACTED]"),
    (
        re.compile(
            r"(?i)(Authorization:\s*Bearer\s+)[A-Za-z0-9._\-~+/=]{8,}",
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"(?i)((?:api[_-]?key|token|secret|password)\s*[=:]\s*)['\"]?[^'\"\s]{12,}['\"]?",
        ),
        r"\1[REDACTED]",
    ),
)

_SENSITIVE_ENV_NAMES = frozenset(
    {
        "DOCINTEL_API_KEYS",
        "DOCINTEL_API_KEY",
        "DOCINTEL_LLM_API_KEY",
        "DOCINTEL_WEBHOOK_SECRET",
        "GROQ_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_ACCESS_KEY_ID",
    }
)


def credential_fingerprint(value: str, *, prefix: str = "cred") -> str:
    """Stable non-reversible id for rate limits and audit fields."""
    cleaned = value.strip()
    if not cleaned:
        return f"{prefix}:anonymous"
    digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def redact_text(text: str) -> str:
    """Remove likely secrets from free-form text."""
    if not text:
        return text
    redacted = text
    for pattern, replacement in _REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def redact_mapping(values: dict[str, object]) -> dict[str, object]:
    """Redact sensitive env-style keys in a dict (for safe debug payloads)."""
    out: dict[str, object] = {}
    for key, value in values.items():
        if key in _SENSITIVE_ENV_NAMES:
            out[key] = "[REDACTED]" if value else ""
        elif isinstance(value, str):
            out[key] = redact_text(value)
        else:
            out[key] = value
    return out


def sensitive_config_keys() -> Iterable[str]:
    """Flask config keys that must not be exposed via app.config."""
    return ("API_KEYS", "WEBHOOK_SECRET")
