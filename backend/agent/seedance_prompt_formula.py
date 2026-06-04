"""Niche-aware Seedance prompt formula contract.

Seedance 2.0 creator reports and vendor docs converge on one practical rule:
uploaded references only help when each asset has a job and the prompt names
timing, action, camera, sound, and constraints. This module turns that rule
into structured data that production decision, UI inspectors, and benchmark
reviews can use without exposing manual model controls to end users.
"""
from __future__ import annotations

from typing import Any


_PRODUCT_NICHES = {
    "beauty",
    "food",
    "fashion",
    "ecommerce_catalog",
    "tech",
    "app_saas",
    "automotive",
    "restaurant_hospitality",
}

_HUMAN_NICHES = {
    "ugc_review",
    "drama",
    "documentary",
    "education",
    "finance_education",
    "medical_wellness",
    "kids_family",
    "fitness",
    "music_video",
    "anime_comic",
}

_LOCATION_NICHES = {"real_estate", "travel", "restaurant_hospitality", "documentary"}
_SENSORY_NICHES = {"food", "asmr", "beauty", "restaurant_hospitality", "travel"}


def build_seedance_prompt_formula(
    *,
    niche: str,
    runtime_payload: dict[str, Any],
    target_market: str,
    target_platform: str,
    has_dialogue: bool,
    reference_allocation: dict[str, Any],
    niche_production_recipe: dict[str, Any],
) -> dict[str, Any]:
    """Return the prompt formula that should govern Seedance segments."""
    niche_key = (niche or "ugc_review").strip().lower()
    runtime_class = str(runtime_payload.get("runtime_class") or "short")
    duration_s = int(runtime_payload.get("target_duration_s") or 30)
    ref_jobs = _reference_jobs(reference_allocation)
    recipe = niche_production_recipe or {}
    prompt_recipe = recipe.get("seedance_prompt_recipe") or {}
    return {
        "schema_version": "cinejelly.seedance_prompt_formula.v1",
        "source_pattern": "asset job -> timeline -> action -> camera -> sound -> constraints",
        "niche": niche_key,
        "runtime_class": runtime_class,
        "target_duration_s": duration_s,
        "target_market": target_market or "auto",
        "target_platform": target_platform or "tiktok",
        "formula": [
            "reference_jobs",
            "timeline",
            "environment",
            "story_intent",
            "action",
            "camera",
            "sound",
            "shot_contract",
            "constraints",
        ],
        "reference_job_policy": _reference_job_policy(
            niche=niche_key,
            runtime_class=runtime_class,
            has_dialogue=has_dialogue,
            ref_jobs=ref_jobs,
        ),
        "niche_template": _niche_template(
            niche=niche_key,
            runtime_class=runtime_class,
            has_dialogue=has_dialogue,
        ),
        "unit_prompt_skeleton": _unit_prompt_skeleton(
            niche=niche_key,
            runtime_class=runtime_class,
            has_dialogue=has_dialogue,
            ref_jobs=ref_jobs,
        ),
        "rewrite_rules": _rewrite_rules(
            niche=niche_key,
            runtime_class=runtime_class,
            has_dialogue=has_dialogue,
            prompt_recipe=prompt_recipe,
        ),
        "benchmark_policy": [
            "A formula is allowed for preview/planning immediately.",
            "A formula becomes promoted only after paid outputs pass route-specific benchmark review.",
            "Store winning formula, model route, reference mix, QA score, cost, latency, and reviewer notes together.",
        ],
    }


def _reference_jobs(allocation: dict[str, Any]) -> list[dict[str, str]]:
    jobs: list[dict[str, str]] = []
    for key in ("image_role_plan", "video_role_plan", "audio_role_plan"):
        for item in allocation.get(key) or []:
            tag = str(item.get("tag") or "").strip()
            role = str(item.get("role") or "").strip()
            job = str(item.get("job") or "").strip()
            if tag:
                jobs.append({"tag": tag, "role": role, "job": job})
    if (allocation.get("long_form_handoff_policy") or {}).get("enabled"):
        jobs.append({
            "tag": "previous_scene_final_frame",
            "role": "continuity_anchor",
            "job": "match accepted final frame pose, lighting, layout, and scene state",
        })
    return jobs[:12]


def _reference_job_policy(
    *,
    niche: str,
    runtime_class: str,
    has_dialogue: bool,
    ref_jobs: list[dict[str, str]],
) -> dict[str, Any]:
    required = ["style_or_lighting_reference"]
    if niche in _HUMAN_NICHES:
        required.insert(0, "character_identity_reference")
    if niche in _PRODUCT_NICHES:
        required.insert(0, "product_or_subject_reference")
    if niche in _LOCATION_NICHES or runtime_class in {"short_film", "episode"}:
        required.append("location_or_motion_reference")
    if has_dialogue:
        required.append("voice_or_dialogue_audio_reference")
    return {
        "required_reference_jobs": list(dict.fromkeys(required)),
        "current_reference_jobs": ref_jobs,
        "assignment_rule": (
            "Every @image/@video/@audio reference must have exactly one primary job. "
            "Do not let identity, product, camera, and audio roles compete inside the same segment."
        ),
        "slot_priority": _slot_priority(niche=niche, runtime_class=runtime_class, has_dialogue=has_dialogue),
    }


def _slot_priority(*, niche: str, runtime_class: str, has_dialogue: bool) -> list[str]:
    priority: list[str] = []
    if niche in _HUMAN_NICHES:
        priority.append("character/creator identity image")
    if niche in _PRODUCT_NICHES:
        priority.append("product or hero subject image")
    if niche in _LOCATION_NICHES:
        priority.append("location layout image or walkthrough video")
    if niche in _SENSORY_NICHES:
        priority.append("motion/texture/foley reference")
    if runtime_class in {"short_film", "episode"}:
        priority.append("previous final frame or storyboard keyframe")
    if has_dialogue:
        priority.append("clean voice/dialogue audio")
    priority.append("style and color reference")
    return list(dict.fromkeys(priority))


def _niche_template(*, niche: str, runtime_class: str, has_dialogue: bool) -> dict[str, str]:
    if niche in _PRODUCT_NICHES:
        story_intent = "prove the product or subject promise through visible tactile evidence"
        action = "show one concrete product interaction, texture change, use case, or before/after proof"
        camera = "macro/detail/hero framing that preserves shape, label, material, and geometry"
    elif niche in _LOCATION_NICHES:
        story_intent = "make the place understandable as a spatial experience"
        action = "move through one readable path or reveal one location feature per unit"
        camera = "establishing, path, feature, and detail shots with stable orientation"
    elif niche == "drama":
        story_intent = "advance one dramatic question with visible stakes and an emotional turn"
        action = "show one character decision, discovery, conflict beat, or aftermath image"
        camera = "character-centered blocking; preserve face, wardrobe, eyeline, and screen direction"
    elif niche in {"education", "finance_education", "medical_wellness", "app_saas", "tech"}:
        story_intent = "make one concept, contradiction, or product workflow visually simple"
        action = "show one example, interface step, demonstration, or remembered takeaway"
        camera = "clean explanatory framing with legible actions and no hallucinated claims"
    else:
        story_intent = "make the niche promise emotionally and visually readable"
        action = "show one sensory, emotional, or proof-driven beat"
        camera = "controlled camera with visible subject, motion, and payoff"

    if runtime_class in {"short_film", "episode"}:
        story_intent += "; close the unit with a handoff image that motivates the next scene"
    sound = "localized dialogue and lip-sync QA" if has_dialogue else "natural foley, ambience, and restrained music"
    return {
        "story_intent": story_intent,
        "action": action,
        "camera": camera,
        "sound": sound,
    }


def _unit_prompt_skeleton(
    *,
    niche: str,
    runtime_class: str,
    has_dialogue: bool,
    ref_jobs: list[dict[str, str]],
) -> list[str]:
    template = _niche_template(niche=niche, runtime_class=runtime_class, has_dialogue=has_dialogue)
    ref_line = (
        "; ".join(f"{item['tag']} as {item['role']}" for item in ref_jobs[:4])
        if ref_jobs
        else "no uploaded reference; use generated planning anchors conservatively"
    )
    return [
        f"[REFERENCE JOBS] {ref_line}",
        "[TIMELINE] 0-4s / 4-8s / 8-12s beats, adjusted to the unit duration.",
        f"[STORY INTENT] {template['story_intent']}.",
        f"[ACTION] {template['action']}.",
        f"[CAMERA] {template['camera']}.",
        f"[SOUND] {template['sound']}.",
        "[SHOT CONTRACT] one physically filmable action; preserve identity/product/location/style; no unrequested text or logos.",
    ]


def _rewrite_rules(
    *,
    niche: str,
    runtime_class: str,
    has_dialogue: bool,
    prompt_recipe: dict[str, Any],
) -> list[str]:
    rules = [
        "Reject blob prompts that do not name reference jobs.",
        "Reject shots with multiple unrelated physical actions in one 4-15s unit.",
        "Rewrite vague camera words into shot size, movement, and continuity purpose.",
        "Keep market language and captions localized, but keep visual action globally readable.",
    ]
    rules.extend(str(item) for item in (prompt_recipe.get("must_include") or [])[:4])
    if runtime_class in {"short_film", "episode"}:
        rules.append("Every long-form unit must name its scene purpose and next-scene handoff image.")
    if has_dialogue:
        rules.append("Dialogue units must include voice/lip-sync QA and avoid long monologues inside one Seedance unit.")
    if niche in {"finance_education", "medical_wellness", "kids_family", "documentary"}:
        rules.append("Claims must be factual, non-diagnostic, non-guaranteed, and review-gated before render.")
    return list(dict.fromkeys(rules))


__all__ = ["build_seedance_prompt_formula"]
