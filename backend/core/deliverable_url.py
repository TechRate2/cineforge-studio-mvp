"""Helpers for URLs that are safe to expose as delivered media."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


_LOOPBACK_HOSTS = {"localhost", "0.0.0.0", "::1", "[::1]"}


def deliverable_http_url(value: Any) -> str | None:
    """Return a trimmed non-loopback HTTP(S) URL, or None for local/stub/empty values."""
    text = str(value or "").strip()
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    host = (parsed.hostname or "").strip().lower()
    if host in _LOOPBACK_HOSTS or host.endswith(".localhost"):
        return None
    if host.startswith("127."):
        return None
    return text


def deliverable_http_urls(values: Any) -> list[str]:
    """Filter a list-like payload down to deliverable HTTP(S) URLs."""
    if not isinstance(values, list):
        return []
    urls: list[str] = []
    for value in values:
        url = deliverable_http_url(value)
        if url:
            urls.append(url)
    return urls


def first_deliverable_http_url(*values: Any) -> str | None:
    """Return the first deliverable URL from scalar or list payload fields."""
    for value in values:
        if isinstance(value, list):
            urls = deliverable_http_urls(value)
            if urls:
                return urls[0]
            continue
        url = deliverable_http_url(value)
        if url:
            return url
    return None


__all__ = ["deliverable_http_url", "deliverable_http_urls", "first_deliverable_http_url"]
