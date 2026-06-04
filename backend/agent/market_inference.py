"""Lightweight target-market inference for autonomous runs.

The UI can stay one-click with target_market="auto", but the production chain
still needs a concrete localization contract for language, culture, captions,
asset memory, dialogue routing, and benchmark lookup.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any


_SUPPORTED_MARKETS = {"auto", "vn", "us", "sea", "jp", "kr", "global"}

_VN_TOKENS = {
    "viet", "viet nam", "vietnam", "sai gon", "ha noi", "da nang", "hoi an", "phu quoc",
    "thi truong viet", "creator viet", "nguoi viet", "nguoi noi tieng viet", "tieng viet", "quan cafe", "ca phe",
    "son moi", "my pham", "du lich", "can ho", "bat dong san",
}
_SEA_TOKENS = {
    "southeast asia", "sea market", "thailand", "thai", "indonesia", "jakarta",
    "malaysia", "singapore", "philippines", "manila",
}
_US_TOKENS = {
    "united states", "usa", "u.s.", "american", "new york", "los angeles",
    "california", "texas",
}
_GLOBAL_TOKENS = {"global", "international", "worldwide", "english audience"}


def infer_target_market(user_idea: str, requested_market: str = "auto") -> dict[str, Any]:
    """Return requested/effective market plus simple evidence.

    Explicit user selection always wins. Auto uses script detection first, then
    market/location/product-language tokens. The result intentionally remains
    deterministic and cheap so it can run before any LLM/vendor call.
    """
    requested = (requested_market or "auto").strip().lower()
    if requested not in _SUPPORTED_MARKETS:
        requested = "auto"
    if requested != "auto":
        return {
            "requested_target_market": requested,
            "effective_target_market": requested,
            "confidence": 1.0,
            "source": "explicit",
            "reasons": [f"explicit:{requested}"],
        }

    text = _normalize_match_text(user_idea)
    reasons: list[str] = []
    scores = {"vn": 0, "us": 0, "sea": 0, "jp": 0, "kr": 0, "global": 0}

    if _contains_japanese(user_idea):
        scores["jp"] += 8
        reasons.append("script:japanese")
    if _contains_korean(user_idea):
        scores["kr"] += 8
        reasons.append("script:korean")
    if _contains_vietnamese_diacritics(user_idea):
        scores["vn"] += 8
        reasons.append("script:vietnamese_diacritics")

    for token in _VN_TOKENS:
        if token in text:
            scores["vn"] += 3
            reasons.append(f"vn:{token}")
    for token in _US_TOKENS:
        if token in text:
            scores["us"] += 3
            reasons.append(f"us:{token}")
    for token in _SEA_TOKENS:
        if token in text:
            scores["sea"] += 3
            reasons.append(f"sea:{token}")
    for token in _GLOBAL_TOKENS:
        if token in text:
            scores["global"] += 3
            reasons.append(f"global:{token}")

    market, score = max(scores.items(), key=lambda item: item[1])
    if score <= 0:
        market = "global"
        confidence = 0.45
        reasons.append("fallback:global")
    else:
        confidence = min(0.95, 0.55 + score / 20)

    return {
        "requested_target_market": "auto",
        "effective_target_market": market,
        "confidence": round(confidence, 2),
        "source": "inferred",
        "reasons": reasons[:8],
    }


def _normalize_match_text(value: str) -> str:
    text = (value or "").strip().lower()
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.replace("đ", "d")


def _contains_vietnamese_diacritics(value: str) -> bool:
    return bool(re.search(r"[ăâêôơưđáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]", value.lower()))


def _contains_japanese(value: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff\u3400-\u4dbf]", value))


def _contains_korean(value: str) -> bool:
    return bool(re.search(r"[\uac00-\ud7af]", value))


__all__ = ["infer_target_market"]
