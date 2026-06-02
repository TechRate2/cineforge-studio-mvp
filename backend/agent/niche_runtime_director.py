"""Niche x runtime directing contract for autonomous video jobs.

This module answers a production question the generic niche playbook cannot:
how should the agent change its story, edit rhythm, references, and QA when the
same niche is requested as a 15s short, a 5 minute short film, or a 30 minute
episode?

The output is deterministic and vendor-free so it can be shown in UI previews,
stored in artifacts, and used by tests without spending AtlasCloud credits.
"""
from __future__ import annotations

from math import ceil
from typing import Any

from skills.market_playbooks import get_market_playbook
from skills.niche_playbooks import get_niche_playbook


_PRODUCT_NICHES = {
    "app_saas",
    "automotive",
    "beauty",
    "ecommerce_catalog",
    "fashion",
    "food",
    "restaurant_hospitality",
    "tech",
    "ugc_review",
}

_CHARACTER_NICHES = {
    "anime_comic",
    "documentary",
    "drama",
    "education",
    "finance_education",
    "fitness",
    "kids_family",
    "lifestyle",
    "medical_wellness",
    "music_video",
    "travel",
    "ugc_review",
}

_LOCATION_NICHES = {
    "automotive",
    "documentary",
    "real_estate",
    "restaurant_hospitality",
    "travel",
}

_SENSORY_NICHES = {"asmr", "beauty", "food", "fashion", "restaurant_hospitality"}
_REVIEW_NICHES = {"documentary", "finance_education", "kids_family", "medical_wellness"}


def build_niche_runtime_director_contract(
    *,
    niche: str,
    runtime_payload: dict[str, Any],
    target_market: str = "auto",
    target_platform: str = "tiktok",
    has_dialogue: bool = False,
    reference_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Return production doctrine for one niche/runtime combination."""
    playbook = get_niche_playbook(niche)
    market = get_market_playbook(target_market)
    refs = _normalise_refs(reference_counts or {})
    runtime_class = str(runtime_payload.get("runtime_class") or "short")
    duration_s = int(runtime_payload.get("target_duration_s") or 30)
    scene_count = int(runtime_payload.get("scene_count") or 1)
    chunk_count = int(runtime_payload.get("chunk_count") or max(1, ceil(duration_s / 60)))
    estimated_units = _estimated_seedance_units(duration_s, runtime_class)

    return {
        "schema_version": "cinejelly.niche_runtime_director.v1",
        "niche": playbook.get("niche") or niche,
        "target_market": market.get("target_market") or target_market,
        "target_platform": target_platform or "tiktok",
        "runtime_class": runtime_class,
        "target_duration_s": duration_s,
        "director_mode": _director_mode(niche=niche, runtime_class=runtime_class),
        "story_shape": _story_shape(runtime_class=runtime_class, playbook=playbook),
        "opening_contract": _opening_contract(playbook=playbook, runtime_class=runtime_class),
        "scene_architecture": {
            "act_count": int(runtime_payload.get("act_count") or 1),
            "scene_count": scene_count,
            "chunk_count": chunk_count,
            "target_scene_duration_s": int(runtime_payload.get("target_scene_duration_s") or duration_s),
            "target_chunk_duration_s": int(runtime_payload.get("target_chunk_duration_s") or 60),
            "long_form_method": _long_form_method(runtime_class),
        },
        "seedance_unit_doctrine": {
            "estimated_units": estimated_units,
            "target_unit_duration_s": _target_unit_duration(duration_s, estimated_units),
            "unit_duration_contract_s": [4, 15],
            "single_call_allowed": duration_s <= 15 and runtime_class == "short",
            "single_action_rule": "one physically filmable action per Seedance unit",
            "continuity_method": _continuity_method(runtime_class),
            "retry_scope": "retry_failed_shot_or_chunk_only",
        },
        "editorial_rhythm": _editorial_rhythm(niche=niche, runtime_class=runtime_class, playbook=playbook),
        "reference_contract": _reference_contract(
            niche=niche,
            runtime_class=runtime_class,
            has_dialogue=has_dialogue,
            refs=refs,
        ),
        "market_localization": _market_localization(market=market, has_dialogue=has_dialogue),
        "qa_focus": _qa_focus(niche=niche, runtime_class=runtime_class, has_dialogue=has_dialogue, playbook=playbook),
        "risk_register": _risk_register(niche=niche, runtime_class=runtime_class, has_dialogue=has_dialogue, refs=refs),
    }


def _normalise_refs(counts: dict[str, int]) -> dict[str, int]:
    return {
        "images": max(0, int(counts.get("images") or counts.get("image") or 0)),
        "videos": max(0, int(counts.get("videos") or counts.get("video") or 0)),
        "audios": max(0, int(counts.get("audios") or counts.get("audio") or 0)),
        "pinned_assets": max(0, int(counts.get("pinned_assets") or counts.get("pinned") or 0)),
    }


def _director_mode(*, niche: str, runtime_class: str) -> str:
    if runtime_class == "short":
        return "viral_single_payoff_director"
    if runtime_class == "sequence":
        return "two_scene_proof_director"
    if runtime_class == "micro_film":
        return "three_act_microfilm_director"
    if runtime_class == "short_film":
        return "screenplay_scene_graph_director"
    return "episode_showrunner_graph_director"


def _story_shape(*, runtime_class: str, playbook: dict[str, Any]) -> dict[str, Any]:
    beat_flow = list(playbook.get("beat_flow") or ["hook", "setup", "action", "payoff"])
    if runtime_class == "short":
        structure = ["hook", "proof action", "payoff"]
        rule = "one promise, one visible proof, one memorable closing image"
    elif runtime_class == "sequence":
        structure = ["hook", "setup", "test/action", "result", "close"]
        rule = "two-scene setup/payoff; no subplot"
    elif runtime_class == "micro_film":
        structure = ["inciting visual", "escalation", "turn", "payoff"]
        rule = "3-act shape with one clear desire, obstacle, and payoff"
    elif runtime_class == "short_film":
        structure = ["cold open", "setup", "complications", "crisis", "aftertaste"]
        rule = "scene-by-scene screenplay; every scene changes the situation"
    else:
        structure = ["cold open", "setup", "rising action", "crisis", "resolution"]
        rule = "episode graph; every chunk has a local cliffhanger and handoff"
    return {
        "rule": rule,
        "niche_beat_flow": beat_flow,
        "runtime_structure": structure,
        "payoff_requirement": "payoff must be visible, not only narrated",
    }


def _opening_contract(*, playbook: dict[str, Any], runtime_class: str) -> dict[str, Any]:
    hook_moves = list(playbook.get("hook_moves") or ["visual proof first"])
    return {
        "first_3s": hook_moves[0],
        "alternate_hooks": hook_moves[1:4],
        "must_show": "viewer-facing visual incident before explanation",
        "avoid": "slow intro, logo-first opening, vague mood montage",
        "long_form_extra": (
            "open with unresolved question and final-image promise"
            if runtime_class in {"micro_film", "short_film", "episode"} else ""
        ),
    }


def _long_form_method(runtime_class: str) -> str:
    if runtime_class in {"short", "sequence"}:
        return "compact_shot_list"
    if runtime_class == "micro_film":
        return "scene_blueprint_then_seedance_units"
    if runtime_class == "short_film":
        return "screenplay_scene_graph_chunks_shots_qa_assembly"
    return "episode_graph_with_resumable_chunks_asset_pins_dialogue_lanes"


def _estimated_seedance_units(duration_s: int, runtime_class: str) -> int:
    if runtime_class == "short" and duration_s <= 15:
        return 1
    return max(1, ceil(max(4, duration_s) / 12))


def _target_unit_duration(duration_s: int, units: int) -> int:
    return max(4, min(15, ceil(max(4, duration_s) / max(1, units))))


def _continuity_method(runtime_class: str) -> str:
    if runtime_class in {"short", "sequence"}:
        return "reference_anchors_and_per_shot_style_lock"
    if runtime_class == "micro_film":
        return "scene_anchor_refs_plus_previous_shot_handoffs"
    return "scene_memory_pack_previous_final_frame_and_anchor_refs"


def _editorial_rhythm(*, niche: str, runtime_class: str, playbook: dict[str, Any]) -> dict[str, Any]:
    if niche in _SENSORY_NICHES:
        rhythm = "sensory close-ups with tactile audio and payoff cuts"
    elif niche in {"drama", "documentary", "anime_comic"}:
        rhythm = "motivated narrative cuts with reaction and object inserts"
    elif niche in {"education", "finance_education", "medical_wellness", "app_saas", "tech"}:
        rhythm = "proof-first explanatory beats with one concept per cut"
    elif niche in {"real_estate", "travel", "automotive"}:
        rhythm = "spatial continuity with establishing, detail, motion proof, and return anchor"
    else:
        rhythm = "platform-native hook, action proof, and tight payoff"
    if runtime_class in {"short_film", "episode"}:
        rhythm += "; scene endings must create a reason to continue"
    return {
        "primary_rhythm": rhythm,
        "camera_palette": list(playbook.get("camera") or [])[:5],
        "audio_texture": playbook.get("audio") or "platform-native sound design",
    }


def _reference_contract(
    *,
    niche: str,
    runtime_class: str,
    has_dialogue: bool,
    refs: dict[str, int],
) -> dict[str, Any]:
    needs: list[str] = []
    if niche in _PRODUCT_NICHES:
        needs.append("2-3 product/packaging angles for geometry and material stability")
    if niche in _CHARACTER_NICHES:
        needs.append("1-3 character or presenter identity anchors")
    if niche in _LOCATION_NICHES or runtime_class in {"short_film", "episode"}:
        needs.append("environment/location anchor for spatial continuity")
    if runtime_class in {"micro_film", "short_film", "episode"}:
        needs.append("previous-frame or scene-final-frame handoff references")
    if has_dialogue:
        needs.append("voice/audio reference and benchmarked lip-sync route")
    if niche in _SENSORY_NICHES:
        needs.append("audio/SFX reference for tactile timing")

    visual_refs = refs["images"] + refs["videos"] + refs["pinned_assets"]
    missing: list[str] = []
    if visual_refs == 0 and (niche in _PRODUCT_NICHES or niche in _CHARACTER_NICHES or runtime_class in {"micro_film", "short_film", "episode"}):
        missing.append("visual_anchor")
    if has_dialogue and refs["audios"] == 0:
        missing.append("voice_or_dialogue_audio_reference")
    if runtime_class in {"short_film", "episode"} and refs["videos"] == 0:
        missing.append("motion_or_camera_reference_recommended")

    return {
        "minimum": needs or ["clear text brief plus one stable style/product/identity anchor when available"],
        "current_refs": refs,
        "missing_for_best_quality": missing,
        "seedance_caps": {"images": 9, "videos": 3, "audios": 3, "mixed_total": 12},
        "role_rule": "image identity/product/style, video motion/camera, audio rhythm/SFX/dialogue",
    }


def _market_localization(*, market: dict[str, Any], has_dialogue: bool) -> dict[str, Any]:
    return {
        "primary_language": market.get("primary_language"),
        "caption_language": market.get("caption_language"),
        "hook_style": market.get("hook_style"),
        "dialogue_style": market.get("dialogue_style") if has_dialogue else "dialogue optional",
        "claim_style": market.get("claim_style"),
        "rule": "market changes proof style, props, caption, CTA, safety tone, and dialogue register",
    }


def _qa_focus(*, niche: str, runtime_class: str, has_dialogue: bool, playbook: dict[str, Any]) -> list[str]:
    focus = [
        "hook visible in first 3 seconds",
        "each Seedance unit has one filmable action",
        "identity/product/style continuity",
        "prompt adherence and camera intent",
        "final payoff visible",
        *list(playbook.get("quality_bar") or [])[:4],
    ]
    if runtime_class in {"micro_film", "short_film", "episode"}:
        focus.extend([
            "scene purpose changes the story state",
            "scene handoff motivates the next scene",
            "last-frame continuity across chunks",
        ])
    if has_dialogue:
        focus.append("dialogue timing, lip-sync, loudness, and silence checks")
    if niche in _REVIEW_NICHES:
        focus.append("human review for claims, safety, or factual framing")
    return list(dict.fromkeys(str(x) for x in focus if str(x).strip()))


def _risk_register(*, niche: str, runtime_class: str, has_dialogue: bool, refs: dict[str, int]) -> list[str]:
    risks: list[str] = []
    visual_refs = refs["images"] + refs["videos"] + refs["pinned_assets"]
    if visual_refs == 0 and runtime_class in {"micro_film", "short_film", "episode"}:
        risks.append("long_form_without_visual_anchor")
    if niche in _PRODUCT_NICHES and visual_refs < 2:
        risks.append("product_geometry_or_packaging_drift")
    if niche in _CHARACTER_NICHES and visual_refs < 1:
        risks.append("character_identity_drift")
    if runtime_class in {"short_film", "episode"}:
        risks.append("scene_continuity_and_pacing_need_graph_qa")
    if has_dialogue:
        risks.append("dialogue_lip_sync_requires_benchmarked_route")
    if niche in _REVIEW_NICHES:
        risks.append("manual_review_required_before_top_tier_claim")
    return risks or ["standard_prompt_adherence_and_motion_quality"]


__all__ = ["build_niche_runtime_director_contract"]
