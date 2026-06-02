"""Asset bible completion policy for autonomous video jobs.

Script asset SOP extracts characters, locations, props, style, and voice anchors.
This module turns that extraction into a measurable gate: which groups exist,
which are missing before top-tier claims, and how the autonomous system should
use pins or generated anchors without exposing manual controls.
"""
from __future__ import annotations

from typing import Any


_GROUP_KEYS = {
    "characters": "character_visual_anchor",
    "locations": "location_visual_anchor",
    "props_or_products": "product_or_prop_visual_anchor",
    "style_anchors": "style_reference_anchor",
    "voice_or_dialogue": "consented_voice_or_tts_audio",
}


def build_asset_bible_completion_policy(
    *,
    script_asset_sop: dict[str, Any],
    runtime_payload: dict[str, Any],
    reference_counts: dict[str, int],
    route_quality_scorecard: dict[str, Any],
) -> dict[str, Any]:
    """Return asset bible readiness for the selected route."""
    sop = script_asset_sop or {}
    groups = sop.get("asset_groups") if isinstance(sop.get("asset_groups"), dict) else {}
    runtime_class = str(runtime_payload.get("runtime_class") or sop.get("runtime_class") or "short")
    duration_s = int(runtime_payload.get("target_duration_s") or 30)
    refs = {
        "images": int(reference_counts.get("images") or 0),
        "videos": int(reference_counts.get("videos") or 0),
        "audios": int(reference_counts.get("audios") or 0),
        "pinned_assets": int(reference_counts.get("pinned_assets") or 0),
    }
    missing_before_top_tier = list(sop.get("missing_before_top_tier") or [])
    required_groups = _required_groups(
        groups=groups,
        runtime_class=runtime_class,
        duration_s=duration_s,
    )
    group_status = [
        _group_status(key, groups.get(key) or [], missing_before_top_tier)
        for key in ["characters", "locations", "props_or_products", "style_anchors", "voice_or_dialogue"]
    ]
    total_required = max(1, len(required_groups))
    passed_required = len([
        item for item in group_status
        if item["group"] in required_groups and item["status"] == "ready"
    ])
    completion_score = round((passed_required / total_required) * 100)
    status = _status(
        completion_score=completion_score,
        missing=missing_before_top_tier,
        runtime_class=runtime_class,
        route_quality_scorecard=route_quality_scorecard,
    )
    return {
        "schema_version": "cinejelly.asset_bible_completion_policy.v1",
        "status": status,
        "completion_score": completion_score,
        "runtime_class": runtime_class,
        "target_duration_s": duration_s,
        "required_groups": required_groups,
        "group_status": group_status,
        "current_reference_counts": refs,
        "missing_before_top_tier": missing_before_top_tier,
        "auto_pin_plan": _auto_pin_plan(
            group_status=group_status,
            refs=refs,
            runtime_class=runtime_class,
        ),
        "render_policy": {
            "can_render_baseline": status != "blocked_missing_minimum_asset_bible",
            "top_tier_claim_allowed": False,
            "rule": (
                "Short-form may render with warnings, but long-form/top-tier routes need "
                "approved character/product/location/style/voice anchors and benchmark evidence."
            ),
        },
        "promotion_rule": (
            "Asset bible is promoted only when required groups have approved pins or generated anchors "
            "and paid outputs prove identity/product/location continuity."
        ),
    }


def _required_groups(*, groups: dict[str, Any], runtime_class: str, duration_s: int) -> list[str]:
    required = ["style_anchors"]
    if groups.get("characters"):
        required.append("characters")
    if groups.get("props_or_products"):
        required.append("props_or_products")
    if groups.get("voice_or_dialogue"):
        required.append("voice_or_dialogue")
    if groups.get("locations") or runtime_class in {"micro_film", "short_film", "episode"} or duration_s > 60:
        required.append("locations")
    if runtime_class in {"short_film", "episode"}:
        required.extend(["characters", "locations"])
    return list(dict.fromkeys(required))


def _group_status(group: str, items: list[dict[str, Any]], missing: list[str]) -> dict[str, Any]:
    missing_key = _GROUP_KEYS[group]
    if missing_key in missing:
        status = "missing_anchor"
    elif items:
        status = "ready"
    else:
        status = "not_required_or_implicit"
    return {
        "group": group,
        "status": status,
        "item_count": len(items),
        "high_priority_count": len([item for item in items if item.get("priority") == "high"]),
        "missing_key": missing_key if status == "missing_anchor" else None,
        "first_item": (items[0].get("name") if items else None),
    }


def _status(
    *,
    completion_score: int,
    missing: list[str],
    runtime_class: str,
    route_quality_scorecard: dict[str, Any],
) -> str:
    if "reference_render_blocking" in set((route_quality_scorecard or {}).get("blocking_reasons") or []):
        return "blocked_missing_minimum_asset_bible"
    if runtime_class in {"short_film", "episode"} and missing:
        return "long_form_asset_bible_incomplete"
    if completion_score >= 90 and not missing:
        return "asset_bible_ready_for_benchmark"
    if missing:
        return "renderable_with_asset_warnings"
    return "asset_bible_baseline_ready"


def _auto_pin_plan(*, group_status: list[dict[str, Any]], refs: dict[str, int], runtime_class: str) -> dict[str, Any]:
    missing_groups = [
        item["group"]
        for item in group_status
        if item["status"] == "missing_anchor"
    ]
    return {
        "auto_select_existing_pins": True,
        "generate_missing_anchor_candidates": bool(missing_groups),
        "candidate_groups": missing_groups,
        "priority_order": [
            "characters",
            "props_or_products",
            "locations",
            "style_anchors",
            "voice_or_dialogue",
        ],
        "reference_budget_note": (
            f"Current visual anchors: {refs['images']} images + {refs['pinned_assets']} pins; "
            f"runtime={runtime_class}."
        ),
    }


__all__ = ["build_asset_bible_completion_policy"]
