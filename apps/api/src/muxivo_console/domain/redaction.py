"""Small, framework-free helpers for keeping secrets out of observability."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

REDACTED_SECRET = "[REDACTED]"

_SENSITIVE_KEY_MARKERS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
)

_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_AUTHORIZATION_HEADER_PATTERN = re.compile(r"(?i)(authorization\s*[:=]\s*)([^,;\s]+)")
_KEY_VALUE_SECRET_PATTERN = re.compile(
    r"(?i)\b([A-Za-z0-9_.-]*(?:password|secret|token)[A-Za-z0-9_.-]*)"
    r"(\s*[:=]\s*)"
    r"([\"']?)([^\"'\s,;&}]+)([\"']?)"
)


def is_sensitive_key(key: object) -> bool:
    """Return True when a mapping/log-extra key conventionally carries a secret."""
    normalized = str(key).lower().replace("-", "_")
    return any(marker in normalized for marker in _SENSITIVE_KEY_MARKERS)


def redact_secret(value: Any) -> Any:
    """Recursively redact values that are likely to contain credentials or tokens."""
    if isinstance(value, Mapping):
        return {
            key: REDACTED_SECRET if is_sensitive_key(key) else redact_secret(item)
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return tuple(redact_secret(item) for item in value)
    if isinstance(value, list):
        return [redact_secret(item) for item in value]
    if isinstance(value, set):
        return {redact_secret(item) for item in value}
    if isinstance(value, str):
        return redact_secret_text(value)
    return value


def redact_secret_text(text: str) -> str:
    """Redact common bearer/header/query/body credential shapes from free text."""
    redacted = _BEARER_PATTERN.sub(f"Bearer {REDACTED_SECRET}", text)
    redacted = _AUTHORIZATION_HEADER_PATTERN.sub(
        rf"\1{REDACTED_SECRET}",
        redacted,
    )
    return _KEY_VALUE_SECRET_PATTERN.sub(
        rf"\1\2\3{REDACTED_SECRET}\5",
        redacted,
    )
