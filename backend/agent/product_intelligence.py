"""Non-paid product/page intelligence for autonomous video briefs.

This module intentionally avoids LLM and video vendor calls. It extracts a
compact product context from a pasted URL so the Agent can build a stronger
brief before paid rendering starts.
"""
from __future__ import annotations

import html
import ipaddress
import re
import socket
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx


_URL_RE = re.compile(r"https?://[^\s<>'\"]+", re.IGNORECASE)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_META_RE = re.compile(
    r"<meta\s+([^>]*?(?:name|property)\s*=\s*['\"][^'\"]+['\"][^>]*)>",
    re.IGNORECASE | re.DOTALL,
)
_ATTR_RE = re.compile(r"([a-zA-Z_:.-]+)\s*=\s*(['\"])(.*?)\2", re.DOTALL)
_PRICE_RE = re.compile(
    r"(?:(?:₫|đ|vnd|vnđ|usd|\$)\s?[0-9][0-9.,]{2,}|[0-9][0-9.,]{2,}\s?(?:₫|đ|vnd|vnđ|usd|\$))",
    re.IGNORECASE,
)
_MAX_HTML_BYTES = 700_000


def first_url(text: str) -> str:
    match = _URL_RE.search(text or "")
    return match.group(0).rstrip(".,)") if match else ""


async def build_product_intelligence(*, url: str, user_idea: str = "") -> dict[str, Any]:
    """Fetch and summarize public page metadata without paid model calls."""
    normalized_url = _normalize_url(url)
    if not normalized_url:
        return _error_payload(url=url, code="invalid_url", message="Provide a valid http(s) product URL.")
    safety = _validate_public_url(normalized_url)
    if not safety["allowed"]:
        return _error_payload(url=normalized_url, code=safety["code"], message=safety["message"])

    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            response = await client.get(
                normalized_url,
                headers={
                    "User-Agent": "CineJellyBot/1.0 (+https://cinejelly.local; product-intelligence)",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
            response.raise_for_status()
            content = response.content[:_MAX_HTML_BYTES]
            final_url = str(response.url)
            content_type = response.headers.get("content-type", "")
    except Exception as exc:  # pragma: no cover - network-dependent branch
        return _error_payload(
            url=normalized_url,
            code="fetch_failed",
            message=f"Could not fetch URL metadata: {type(exc).__name__}",
        )

    if "html" not in content_type.lower() and b"<html" not in content[:2000].lower():
        return _error_payload(
            url=normalized_url,
            code="unsupported_content",
            message="URL does not look like an HTML product/page document.",
        )

    html_text = _decode_html(content)
    meta = _extract_meta(html_text)
    title = _clean_text(meta.get("og:title") or meta.get("twitter:title") or _extract_title(html_text))
    description = _clean_text(
        meta.get("og:description")
        or meta.get("twitter:description")
        or meta.get("description")
    )
    image_url = _absolute_url(
        final_url,
        meta.get("og:image") or meta.get("twitter:image") or meta.get("image"),
    )
    price_signals = _unique(_PRICE_RE.findall(_visible_text_sample(html_text)))[:4]
    keywords = _keywords_from(title, description, user_idea)
    brief_addition = _build_brief_addition(
        title=title,
        description=description,
        url=final_url,
        price_signals=price_signals,
        keywords=keywords,
    )
    return {
        "schema_version": "cinejelly.product_intelligence.v1",
        "vendor_calls_performed": False,
        "paid_video_vendor_calls_allowed": False,
        "status": "ready" if (title or description or image_url) else "partial",
        "source_url": final_url,
        "title": title,
        "description": description,
        "primary_image_url": image_url,
        "price_signals": price_signals,
        "product_keywords": keywords,
        "brief_addition": brief_addition,
        "reference_suggestion": (
            {
                "kind": "image",
                "role": "product_hero",
                "url": image_url,
                "name": title or "Product image from URL",
                "role_confirmed": False,
                "why": "Open Graph image from pasted product/page URL.",
            }
            if image_url
            else None
        ),
        "next_actions": [
            "Confirm the imported image role before paid render.",
            "Add one creator/voice or motion reference if this needs dialogue, UGC, or cinematic pacing.",
            "Review extracted title/description because product pages can include stale metadata.",
        ],
    }


def _normalize_url(url: str) -> str:
    text = (url or "").strip()
    if not text:
        return ""
    if not text.startswith(("http://", "https://")):
        text = f"https://{text}"
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return text


def _validate_public_url(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return {"allowed": False, "code": "missing_host", "message": "URL host is missing."}
    if host in {"localhost", "127.0.0.1", "0.0.0.0"} or host.endswith(".local"):
        return {"allowed": False, "code": "private_host", "message": "Local/private URLs are not allowed."}
    try:
        addrs = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        for item in addrs[:8]:
            ip = ipaddress.ip_address(item[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                return {
                    "allowed": False,
                    "code": "private_network",
                    "message": "URL resolves to a private or non-public network address.",
                }
    except Exception:
        return {"allowed": True, "code": "dns_unverified", "message": ""}
    return {"allowed": True, "code": "ok", "message": ""}


def _decode_html(content: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return content.decode(encoding, errors="ignore")
        except Exception:
            continue
    return content.decode(errors="ignore")


def _extract_title(html_text: str) -> str:
    match = _TITLE_RE.search(html_text or "")
    return html.unescape(match.group(1)) if match else ""


def _extract_meta(html_text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for tag_match in _META_RE.finditer(html_text or ""):
        attrs = {
            key.lower(): html.unescape(value.strip())
            for key, _, value in _ATTR_RE.findall(tag_match.group(1))
        }
        key = (attrs.get("property") or attrs.get("name") or "").strip().lower()
        value = (attrs.get("content") or "").strip()
        if key and value and key not in out:
            out[key] = value
    return out


def _absolute_url(base_url: str, value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    return urljoin(base_url, html.unescape(text))


def _visible_text_sample(html_text: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", html_text or "", flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return _clean_text(text)[:60_000]


def _clean_text(value: str | None) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:600]


def _keywords_from(*values: str) -> list[str]:
    words: list[str] = []
    for value in values:
        cleaned = re.sub(r"[^0-9A-Za-zÀ-ỹ\s-]", " ", value or "").lower()
        for word in cleaned.split():
            if len(word) < 4:
                continue
            if word in {"https", "http", "www", "shop", "store", "product"}:
                continue
            words.append(word)
    return _unique(words)[:14]


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = _clean_text(str(value)).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(_clean_text(str(value)))
    return out


def _build_brief_addition(
    *,
    title: str,
    description: str,
    url: str,
    price_signals: list[str],
    keywords: list[str],
) -> str:
    parts = ["Product/page intelligence from URL:"]
    if title:
        parts.append(f"Title: {title}.")
    if description:
        parts.append(f"Description: {description}.")
    if price_signals:
        parts.append(f"Price/value signals: {', '.join(price_signals[:3])}.")
    if keywords:
        parts.append(f"Detected product keywords: {', '.join(keywords[:8])}.")
    parts.append(f"Source URL: {url}.")
    return " ".join(parts)[:1200]


def _error_payload(*, url: str, code: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": "cinejelly.product_intelligence.v1",
        "vendor_calls_performed": False,
        "paid_video_vendor_calls_allowed": False,
        "status": "error",
        "source_url": url,
        "error": {"code": code, "message": message},
        "title": "",
        "description": "",
        "primary_image_url": "",
        "price_signals": [],
        "product_keywords": [],
        "brief_addition": "",
        "reference_suggestion": None,
        "next_actions": ["Paste a public product/page URL or upload product references manually."],
    }


__all__ = ["build_product_intelligence", "first_url"]
