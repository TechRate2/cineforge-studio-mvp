"""Helpers for failing closed when required runtime secrets are absent."""
from __future__ import annotations

from typing import Iterable


_PLACEHOLDER_VALUES = {
    "...",
    "changeme",
    "change_me",
    "replace_me",
    "replace-with-real-key",
    "your_key",
    "your-api-key",
    "your_api_key",
    "your-key-here",
    "sk-xxx",
}


def is_configured_secret(value: object) -> bool:
    """Return True only for non-empty values that are not template placeholders."""
    text = str(value or "").strip()
    if not text:
        return False
    lowered = text.lower()
    if lowered in _PLACEHOLDER_VALUES:
        return False
    if len(lowered) >= 5 and set(lowered) == {"x"}:
        return False
    if lowered.startswith("your_") or lowered.startswith("your-"):
        return False
    if lowered.startswith("<") and lowered.endswith(">"):
        return False
    return True


def missing_secret_names(pairs: Iterable[tuple[str, object]]) -> list[str]:
    """Return env var names whose values are empty or placeholder-like."""
    return [name for name, value in pairs if not is_configured_secret(value)]


__all__ = ["is_configured_secret", "missing_secret_names"]
