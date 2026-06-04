"""Responsible content gate for realistic autonomous video generation.

Seedance-class models can make highly realistic people, voices, and known
characters. A production agent should catch high-risk likeness, voice-cloning,
and known-IP prompts before vendor spend. This module is intentionally
deterministic: it is a pre-render safety contract, not a policy model.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any


_PUBLIC_FIGURE_TERMS = {
    "celebrity", "famous actor", "famous singer", "public figure", "politician",
    "elon musk", "donald trump", "joe biden", "barack obama", "vladimir putin",
    "taylor swift", "beyonce", "cristiano ronaldo", "lionel messi", "mrbeast",
    "blackpink", "bts", "son tung", "son tung mtp", "tran thanh", "truong giang",
}

_KNOWN_IP_TERMS = {
    "disney", "pixar", "marvel", "dc comics", "batman", "superman", "spider-man",
    "spiderman", "pokemon", "pikachu", "harry potter", "hogwarts", "naruto",
    "one piece", "luffy", "dragon ball", "goku", "doraemon", "mickey mouse",
    "minions", "star wars", "jedi", "avatar the last airbender",
}

_VOICE_CLONE_TERMS = {
    "clone voice", "voice clone", "deepfake voice", "sound exactly like",
    "use the voice of", "clone her voice", "clone his voice", "copy her voice", "copy his voice", "impersonate",
    "giong cua", "nhai giong", "bat chuoc giong", "clone giong",
}

_HIGH_RISK_ACTION_TERMS = {
    "deepfake", "fake endorsement", "endorse", "testimonial", "political ad",
    "campaign ad", "scam", "investment pitch", "medical claim", "adult",
    "quang cao chinh tri", "loi chung thuc", "keu goi dau tu",
}

_SOFT_STYLE_TERMS = {
    "inspired by", "style of", "vibe of", "cinematic like", "similar energy",
    "lay cam hung", "phong cach", "giong vibe",
}


def build_responsible_content_gate(
    *,
    user_idea: str,
    target_market: str = "auto",
    has_dialogue: bool = False,
    reference_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Return pre-render responsible generation guidance."""
    text = _normalize(user_idea)
    refs = reference_counts or {}
    matches = {
        "public_figure_or_celebrity": _matches(text, _PUBLIC_FIGURE_TERMS),
        "known_ip_or_character": _matches(text, _KNOWN_IP_TERMS),
        "voice_or_likeness_clone": _matches(text, _VOICE_CLONE_TERMS),
        "high_risk_action": _matches(text, _HIGH_RISK_ACTION_TERMS),
        "soft_style_reference": _matches(text, _SOFT_STYLE_TERMS),
    }
    hard_blockers: list[str] = []
    review_flags: list[str] = []

    if matches["voice_or_likeness_clone"] and (
        matches["public_figure_or_celebrity"] or has_dialogue or int(refs.get("audios") or 0) > 0
    ):
        hard_blockers.append("unverified_voice_or_likeness_clone")
    if matches["public_figure_or_celebrity"] and matches["high_risk_action"]:
        hard_blockers.append("public_figure_high_risk_use")
    if matches["known_ip_or_character"] and not matches["soft_style_reference"]:
        hard_blockers.append("known_ip_or_character_requires_rights_review")

    if matches["public_figure_or_celebrity"] and not hard_blockers:
        review_flags.append("public_figure_or_celebrity_review")
    if matches["known_ip_or_character"] and matches["soft_style_reference"]:
        review_flags.append("known_ip_style_reference_review")
    if matches["voice_or_likeness_clone"] and not hard_blockers:
        review_flags.append("voice_or_likeness_review")
    if has_dialogue and int(refs.get("audios") or 0) > 0:
        review_flags.append("dialogue_audio_consent_check")

    status = "fail" if hard_blockers else ("warn" if review_flags else "pass")
    return {
        "schema_version": "cinejelly.responsible_content_gate.v1",
        "status": status,
        "render_allowed": not hard_blockers,
        "manual_review_required": bool(hard_blockers or review_flags),
        "target_market": target_market or "auto",
        "hard_blockers": hard_blockers,
        "review_flags": review_flags,
        "matches": matches,
        "policy": [
            "Do not generate unverified celebrity/public-figure likeness, endorsement, or voice-clone content.",
            "Do not generate known IP/character content for commercial use without rights review.",
            "Style inspiration can be reviewed, but the agent should rewrite toward original characters and original brands.",
            "Audio references used for visible speech require consent and lip-sync QA before promotion.",
        ],
        "rewrite_guidance": _rewrite_guidance(matches, hard_blockers, review_flags),
    }


def _rewrite_guidance(matches: dict[str, list[str]], hard_blockers: list[str], review_flags: list[str]) -> list[str]:
    guidance: list[str] = []
    if matches["public_figure_or_celebrity"]:
        guidance.append("Replace named celebrity/public figure with an original fictional person or user-owned spokesperson.")
    if matches["known_ip_or_character"]:
        guidance.append("Replace protected character/franchise with an original character, costume, color language, and world.")
    if matches["voice_or_likeness_clone"]:
        guidance.append("Use user-provided consented voice/audio or generate a new neutral voice; do not mimic a real person.")
    if not guidance and not hard_blockers and not review_flags:
        guidance.append("No likeness/IP blocker detected; continue normal autonomous planning.")
    return guidance


def _matches(text: str, terms: set[str]) -> list[str]:
    hits: list[str] = []
    for term in sorted(terms):
        normalized = _normalize(term)
        if re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", text):
            hits.append(term)
    return hits


def _normalize(value: str) -> str:
    raw = (value or "").strip().lower()
    decomposed = unicodedata.normalize("NFD", raw)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.replace("đ", "d")


__all__ = ["build_responsible_content_gate"]
