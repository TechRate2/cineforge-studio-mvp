"""Platform distribution package for autonomous video outputs.

Rendering a good clip is not enough for a production-grade agent. The final
editor should package the same video differently for TikTok, Reels, Shorts,
Xiaohongshu, Bilibili, or long-form channels.
"""
from __future__ import annotations

from typing import Any


_PLATFORM_RULES: dict[str, dict[str, Any]] = {
    "tiktok": {
        "caption_max_chars": 150,
        "hashtag_count": [6, 10],
        "cover_text_max_words": 6,
        "cta_style": "soft comment/save/share prompt after proof",
        "posting_hint": "evening local time; test 19:00-22:00 for VN/social-commerce content",
        "packaging_notes": ["front-load visible proof", "avoid long setup", "cover frame should show result or tension"],
    },
    "reels": {
        "caption_max_chars": 180,
        "hashtag_count": [5, 8],
        "cover_text_max_words": 5,
        "cta_style": "save/share prompt with polished creator tone",
        "posting_hint": "local evening; test 18:00-21:00",
        "packaging_notes": ["clean cover image", "caption can be slightly more editorial", "avoid spam hashtags"],
    },
    "youtube_shorts": {
        "caption_max_chars": 100,
        "hashtag_count": [3, 5],
        "cover_text_max_words": 5,
        "cta_style": "question or part-2 prompt, no hard sell",
        "posting_hint": "early afternoon or creator analytics window",
        "packaging_notes": ["title must carry the hook", "first frame should be readable without sound"],
    },
    "youtube_long": {
        "caption_max_chars": 320,
        "hashtag_count": [3, 6],
        "cover_text_max_words": 7,
        "cta_style": "chapter-aware description and subscribe prompt near value payoff",
        "posting_hint": "publish on a consistent weekly slot; optimize thumbnail/title",
        "packaging_notes": ["include chapter summary", "description should promise the payoff", "thumbnail must show central conflict"],
    },
    "xhs": {
        "caption_max_chars": 220,
        "hashtag_count": [4, 8],
        "cover_text_max_words": 6,
        "cta_style": "save-note style, practical and tasteful",
        "posting_hint": "evening local time; polished cover and clear benefit",
        "packaging_notes": ["aesthetic cover frame", "practical title", "avoid overhype"],
    },
    "bilibili": {
        "caption_max_chars": 260,
        "hashtag_count": [3, 6],
        "cover_text_max_words": 8,
        "cta_style": "episode/series prompt and value summary",
        "posting_hint": "consistent release cadence; title and cover matter heavily",
        "packaging_notes": ["strong title", "series continuity cue", "clear genre signal"],
    },
}


def build_distribution_package(
    *,
    target_platform: str,
    target_market: str,
    niche: str,
    duration_s: int,
    caption_vn: str,
    caption_en: str,
    hashtags_vn: list[str],
    hashtags_en: list[str],
    market_playbook: dict[str, Any] | None = None,
) -> dict[str, Any]:
    platform = _normalize_platform(target_platform)
    market = (target_market or "auto").strip().lower() or "auto"
    rules = _PLATFORM_RULES[platform]
    caption_primary = _primary_caption(market, caption_vn, caption_en)
    tags_primary = _primary_tags(market, hashtags_vn, hashtags_en)
    title = _title_hint(caption_primary, niche)
    return {
        "schema_version": "cinejelly.distribution_package.v1",
        "target_platform": platform,
        "target_market": market,
        "niche": niche or "auto",
        "runtime_bucket": _runtime_bucket(duration_s),
        "caption_primary": caption_primary,
        "caption_secondary": caption_en if caption_primary == caption_vn else caption_vn,
        "title_hint": title,
        "description_hint": _description_hint(platform, caption_primary, market_playbook or {}),
        "cover_frame_cue": _cover_frame_cue(niche, duration_s),
        "cover_text_max_words": rules["cover_text_max_words"],
        "hashtag_primary": _trim_tags(tags_primary, rules["hashtag_count"][1]),
        "hashtag_count_range": rules["hashtag_count"],
        "cta_style": rules["cta_style"],
        "posting_hint": (market_playbook or {}).get("posting_hint") or rules["posting_hint"],
        "platform_notes": rules["packaging_notes"],
        "checks": _checks(caption_primary, tags_primary, rules),
    }


def _normalize_platform(platform: str) -> str:
    key = (platform or "tiktok").strip().lower()
    aliases = {
        "youtube_short": "youtube_shorts",
        "shorts": "youtube_shorts",
        "yt_shorts": "youtube_shorts",
        "xiaohongshu": "xhs",
        "rednote": "xhs",
        "universal": "tiktok",
        "auto": "tiktok",
    }
    key = aliases.get(key, key)
    return key if key in _PLATFORM_RULES else "tiktok"


def _primary_caption(market: str, caption_vn: str, caption_en: str) -> str:
    if market == "vn":
        return caption_vn or caption_en
    if market in {"us", "global", "sea"}:
        return caption_en or caption_vn
    return caption_vn or caption_en


def _primary_tags(market: str, tags_vn: list[str], tags_en: list[str]) -> list[str]:
    return tags_vn if market == "vn" or not tags_en else tags_en


def _title_hint(caption: str, niche: str) -> str:
    clean = " ".join((caption or "").replace("\n", " ").split())
    title = clean.split(".")[0].strip()
    if len(title) > 70:
        title = title[:67].rstrip() + "..."
    if title:
        return title
    return f"{(niche or 'video').replace('_', ' ').title()} result"


def _description_hint(platform: str, caption: str, market_playbook: dict[str, Any]) -> str:
    claim_style = market_playbook.get("claim_style") or "show proof visually"
    if platform == "youtube_long":
        return f"{caption} Include chapters, proof points, and source/claim notes. Claim style: {claim_style}."
    return f"{caption} Claim style: {claim_style}."


def _cover_frame_cue(niche: str, duration_s: int) -> str:
    if niche in {"ugc_review", "ecommerce_catalog", "tech", "app_saas"}:
        return "frame with product/result visible before explanation"
    if niche in {"beauty", "food", "fashion", "asmr"}:
        return "macro sensory frame with texture, result, or transformation"
    if niche in {"drama", "anime_comic"}:
        return "emotion close-up or object clue that implies conflict"
    if duration_s > 180:
        return "scene-defining frame with protagonist, stakes, and location"
    return "strongest hook frame from first 3 seconds"


def _runtime_bucket(duration_s: int) -> str:
    duration = int(duration_s or 0)
    if duration <= 30:
        return "short"
    if duration <= 60:
        return "sequence"
    if duration <= 180:
        return "micro_film"
    if duration <= 600:
        return "short_film"
    return "episode"


def _trim_tags(tags: list[str], limit: int) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        t = str(tag or "").strip().lstrip("#")
        key = t.lower()
        if not key or key in seen:
            continue
        cleaned.append(t)
        seen.add(key)
        if len(cleaned) >= limit:
            break
    return cleaned


def _checks(caption: str, tags: list[str], rules: dict[str, Any]) -> list[dict[str, Any]]:
    max_chars = int(rules["caption_max_chars"])
    min_tags, max_tags = rules["hashtag_count"]
    return [
        {
            "name": "caption_length",
            "status": "pass" if len(caption or "") <= max_chars else "warn",
            "detail": f"{len(caption or '')}/{max_chars} chars",
        },
        {
            "name": "hashtag_count",
            "status": "pass" if min_tags <= len(tags) <= max_tags else "warn",
            "detail": f"{len(tags)} tags; target {min_tags}-{max_tags}",
        },
        {
            "name": "cover_cue",
            "status": "pass",
            "detail": "cover frame cue generated",
        },
    ]


__all__ = ["build_distribution_package"]
