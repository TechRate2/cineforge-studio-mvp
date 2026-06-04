"""Script/entity to asset SOP for autonomous long-form video.

Top short-drama systems do not jump from a paragraph straight into video
generation. They first extract the production assets that must stay stable:
characters, locations, props/products, voice/dialogue anchors, and style refs.
This module provides a deterministic pre-render contract that production
decision endpoints can expose before any vendor spend.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any


_LOCATION_TERMS = {
    "sai gon": "Saigon street/city environment",
    "ho chi minh": "Ho Chi Minh City environment",
    "ha noi": "Hanoi urban environment",
    "da nang": "Da Nang coastal/city environment",
    "hoi an": "Hoi An old-town environment",
    "apartment": "apartment interior",
    "cafe": "cafe environment",
    "restaurant": "restaurant environment",
    "street": "street environment",
}

_PROP_TERMS = {
    "banh mi": "banh mi hero food prop",
    "coffee": "coffee/drink prop",
    "phone": "phone/app screen prop",
    "app": "app/product UI prop",
    "serum": "beauty serum prop",
    "lipstick": "lipstick prop",
    "camera": "camera/gadget prop",
    "car": "vehicle hero prop",
}

_CHARACTER_TERMS = {
    "co gai": "young woman main character",
    "girl": "young woman main character",
    "founder": "founder/spokesperson character",
    "creator": "creator/spokesperson character",
    "vendor": "vendor main character",
    "mother": "mother/family character",
    "father": "father/family character",
}


def build_script_asset_sop(
    *,
    user_idea: str,
    niche: str,
    runtime_payload: dict[str, Any],
    target_market: str,
    reference_counts: dict[str, int],
    has_dialogue: bool,
) -> dict[str, Any]:
    """Return required reusable production assets for a render decision."""
    text = _normalize(user_idea)
    runtime_class = str(runtime_payload.get("runtime_class") or "short")
    duration_s = int(runtime_payload.get("target_duration_s") or 30)
    long_or_story = runtime_class in {"short_film", "episode"} or duration_s > 180 or niche in {
        "drama",
        "documentary",
        "education",
    }

    characters = _character_assets(text, niche)
    locations = _location_assets(text, niche)
    props = _prop_assets(text, niche)
    style = _style_assets(text, niche, runtime_class, target_market)
    voice = _voice_assets(has_dialogue, target_market)
    current_refs = {
        "images": int(reference_counts.get("images") or 0),
        "videos": int(reference_counts.get("videos") or 0),
        "audios": int(reference_counts.get("audios") or 0),
        "pinned_assets": int(reference_counts.get("pinned_assets") or 0),
    }

    missing = _missing_assets(
        long_or_story=long_or_story,
        has_dialogue=has_dialogue,
        current_refs=current_refs,
        characters=characters,
        locations=locations,
        props=props,
    )
    return {
        "schema_version": "cinejelly.script_asset_sop.v1",
        "enabled": bool(long_or_story or characters or locations or props),
        "runtime_class": runtime_class,
        "niche": niche,
        "target_market": target_market,
        "source_pattern": "LumenX/ViMax script-to-entities-to-assets before video generation",
        "current_reference_coverage": current_refs,
        "asset_groups": {
            "characters": characters,
            "locations": locations,
            "props_or_products": props,
            "style_anchors": style,
            "voice_or_dialogue": voice,
        },
        "missing_before_top_tier": missing,
        "pre_render_steps": _pre_render_steps(long_or_story, missing),
        "policy": [
            "Use this as an autonomous production checklist, not as manual user settings.",
            "For long-form, create or approve reusable character/location/prop/style pins before graph execution.",
            "For dialogue, use consented audio or generated voices and benchmark lip-sync before top-tier claims.",
        ],
    }


def _character_assets(text: str, niche: str) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for term, label in _CHARACTER_TERMS.items():
        if term in text:
            assets.append(_asset("character_anchor", label, "high", ["face", "hair", "outfit", "body language"]))
    if niche == "drama" and not assets:
        assets.append(_asset("character_anchor", "main protagonist", "high", ["face", "outfit", "emotional range"]))
        assets.append(_asset("secondary_character", "key supporting character", "medium", ["face", "relationship role"]))
    elif niche in {"ugc_review", "app_saas", "education"} and not assets:
        assets.append(_asset("character_anchor", "presenter or creator", "medium", ["face", "wardrobe", "speaking style"]))
    return _dedupe_assets(assets)


def _location_assets(text: str, niche: str) -> list[dict[str, Any]]:
    assets = [
        _asset("environment", label, "high", ["layout", "lighting", "local props"])
        for term, label in _LOCATION_TERMS.items()
        if term in text
    ]
    if niche == "real_estate" and not assets:
        assets.append(_asset("environment", "property/location layout", "high", ["wide view", "room sequence"]))
    if niche == "travel" and not assets:
        assets.append(_asset("environment", "destination environment", "high", ["landmark", "weather", "ambience"]))
    return _dedupe_assets(assets)


def _prop_assets(text: str, niche: str) -> list[dict[str, Any]]:
    assets = [
        _asset("product_hero", label, "high", ["shape", "texture", "label/color"])
        for term, label in _PROP_TERMS.items()
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text)
    ]
    if niche in {"beauty", "fashion", "food", "ecommerce_catalog", "tech"} and not assets:
        assets.append(_asset("product_hero", f"{niche.replace('_', ' ')} hero subject", "high", ["geometry", "material", "hero angle"]))
    return _dedupe_assets(assets)


def _style_assets(text: str, niche: str, runtime_class: str, target_market: str) -> list[dict[str, Any]]:
    tags = ["color grade", "lighting", "composition"]
    if "cinematic" in text or runtime_class in {"short_film", "episode"}:
        tags.extend(["lens language", "scene mood"])
    if target_market == "vn":
        tags.append("Vietnamese local realism")
    return [_asset("style_reference", f"{niche.replace('_', ' ')} visual style", "medium", tags)]


def _voice_assets(has_dialogue: bool, target_market: str) -> list[dict[str, Any]]:
    if not has_dialogue:
        return []
    language = {
        "vn": "Vietnamese",
        "jp": "Japanese",
        "kr": "Korean",
        "us": "English",
    }.get(target_market, "localized")
    return [_asset("voice_anchor", f"{language} dialogue voice plan", "high", ["consented voice", "emotion", "lip-sync QA"])]


def _missing_assets(
    *,
    long_or_story: bool,
    has_dialogue: bool,
    current_refs: dict[str, int],
    characters: list[dict[str, Any]],
    locations: list[dict[str, Any]],
    props: list[dict[str, Any]],
) -> list[str]:
    missing: list[str] = []
    image_like = int(current_refs.get("images") or 0) + int(current_refs.get("pinned_assets") or 0)
    if characters and image_like <= 0:
        missing.append("character_visual_anchor")
    if props and image_like <= 0:
        missing.append("product_or_prop_visual_anchor")
    if locations and image_like <= 1 and long_or_story:
        missing.append("location_visual_anchor")
    if long_or_story and int(current_refs.get("videos") or 0) <= 0:
        missing.append("motion_or_camera_reference")
    if has_dialogue and int(current_refs.get("audios") or 0) <= 0:
        missing.append("consented_voice_or_tts_audio")
    return list(dict.fromkeys(missing))


def _pre_render_steps(long_or_story: bool, missing: list[str]) -> list[str]:
    steps = [
        "extract production entities from the idea/script",
        "assign each entity to character, location, prop/product, style, or voice memory",
    ]
    if missing:
        steps.append("ask for or auto-generate missing reference anchors before premium/top-tier render")
    if long_or_story:
        steps.extend([
            "approve reusable pins before graph execution",
            "bind pins into scene memory and per-shot Seedance reference jobs",
            "update dynamic keyframe memory only from QA-accepted outputs",
        ])
    return steps


def _asset(role: str, name: str, priority: str, required_views: list[str]) -> dict[str, Any]:
    return {
        "role": role,
        "name": name,
        "priority": priority,
        "required_views": required_views,
        "pin_policy": "approve_or_generate_before_render",
    }


def _dedupe_assets(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = (str(item.get("role")), str(item.get("name")))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _normalize(value: str) -> str:
    raw = (value or "").strip().lower()
    decomposed = unicodedata.normalize("NFD", raw)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.replace("đ", "d")


__all__ = ["build_script_asset_sop"]
