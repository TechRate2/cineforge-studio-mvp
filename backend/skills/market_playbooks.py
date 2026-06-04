"""Market localization playbooks for CineJelly Autonomous Director.

Target market should stay lightweight in the UI, but it must be explicit in the
agent chain. These deterministic playbooks give the planner, editor, and
production bible the same localization contract: language, cultural texture,
claim style, posting rhythm, and what to avoid.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


_COMMON = {
    "avoid": [
        "forced stereotypes",
        "slang that does not match the user idea",
        "claims that would need proof but are shown only as narration",
        "region-specific idioms when target_market is auto or global",
    ],
    "seedance_notes": [
        "Localize through setting, behavior, props, pacing, dialogue, and caption, not flags or text overlays.",
        "Keep dialogue short enough to fit the shot duration and visual action.",
        "Use market cues only when they help the idea feel real.",
    ],
}


_PLAYBOOKS: dict[str, dict[str, Any]] = {
    "auto": {
        "label": "Auto-detect",
        "primary_language": "infer from brief and references",
        "caption_language": "infer primary caption language; also provide English reach caption",
        "hook_style": "match the user's language and platform; prefer concrete visual proof over generic hype",
        "dialogue_style": "natural speech in the inferred audience language",
        "visual_cues": ["infer city, home, creator, product, and cultural context from the brief"],
        "claim_style": "show the proof visually before asking the audience to believe the claim",
        "posting_hint": "pick platform-native timing for the inferred market",
    },
    "vn": {
        "label": "Vietnam",
        "primary_language": "Vietnamese",
        "caption_language": "Vietnamese first, English second",
        "hook_style": "direct, curiosity-driven, mobile-commerce aware, but not spammy",
        "dialogue_style": "natural Vietnamese creator voice; short spoken lines; avoid stiff translation",
        "visual_cues": ["Saigon/Hanoi/Da Nang realism", "coffee shop/home/shop/street context", "phone-first creator framing"],
        "claim_style": "local social proof, visible before-after, test-in-hand, soft CTA",
        "posting_hint": "TikTok VN 19:00-22:00 weekday, 12:00-14:00 weekend",
    },
    "us": {
        "label": "United States",
        "primary_language": "English",
        "caption_language": "English first, optional localized secondary caption",
        "hook_style": "clear benefit or tension in the first sentence; fast proof; creator-native phrasing",
        "dialogue_style": "casual English with concise claims and minimal filler",
        "visual_cues": ["clean home/desk/car/street realism", "UGC creator lighting", "platform-native product proof"],
        "claim_style": "avoid exaggerated medical/financial promises; show comparison or demonstration",
        "posting_hint": "Reels/TikTok local evenings and lunch breaks; test multiple time zones",
    },
    "sea": {
        "label": "Southeast Asia",
        "primary_language": "English or local-language cues based on brief",
        "caption_language": "simple English or inferred local language; avoid hard slang",
        "hook_style": "warm, practical, price/value-aware, high sensory clarity",
        "dialogue_style": "simple conversational phrasing; clear product/benefit proof",
        "visual_cues": ["warm daylight", "urban apartment/shop/cafe", "mobile-first commerce and creator POV"],
        "claim_style": "value, convenience, everyday proof, before-after when visual",
        "posting_hint": "evenings and weekends; optimize for mobile social commerce",
    },
    "jp": {
        "label": "Japan",
        "primary_language": "Japanese or clean English if brief is English",
        "caption_language": "localized primary caption plus English reach caption",
        "hook_style": "restrained curiosity, precise visual detail, quality/ritual over loud hype",
        "dialogue_style": "polite concise phrasing; avoid overclaiming",
        "visual_cues": ["clean composition", "quiet ritual", "packaging/detail shots", "natural indoor light"],
        "claim_style": "specific sensory/quality proof, subtle social proof, no aggressive CTA",
        "posting_hint": "evenings after work; concise captions and polished thumbnails",
    },
    "kr": {
        "label": "Korea",
        "primary_language": "Korean or clean English if brief is English",
        "caption_language": "localized primary caption plus English reach caption",
        "hook_style": "polished trend-aware reveal, beauty/lifestyle rhythm, concise payoff",
        "dialogue_style": "short natural lines; polished creator tone",
        "visual_cues": ["clean lifestyle setting", "beauty/fashion detail shots", "soft polished lighting"],
        "claim_style": "trend proof, visible texture/result, restrained but stylish CTA",
        "posting_hint": "evening social windows; high thumbnail polish",
    },
    "global": {
        "label": "Global",
        "primary_language": "English",
        "caption_language": "English first; avoid hard regional slang",
        "hook_style": "universal visual question, transformation, conflict, or proof",
        "dialogue_style": "simple globally understandable speech; minimal idioms",
        "visual_cues": ["internationally readable settings", "clear product/action geography", "minimal text dependency"],
        "claim_style": "show don't tell; avoid local legal/medical/financial specifics",
        "posting_hint": "platform analytics driven; caption should travel across markets",
    },
}


def get_market_playbook(target_market: str) -> dict[str, Any]:
    """Return a copy-safe localization playbook."""
    key = (target_market or "auto").strip().lower()
    data = deepcopy(_PLAYBOOKS.get(key) or _PLAYBOOKS["auto"])
    data["target_market"] = key if key in _PLAYBOOKS else "auto"
    data["avoid"] = [*data.get("avoid", []), *_COMMON["avoid"]]
    data["seedance_notes"] = [*data.get("seedance_notes", []), *_COMMON["seedance_notes"]]
    return data


__all__ = ["get_market_playbook"]
