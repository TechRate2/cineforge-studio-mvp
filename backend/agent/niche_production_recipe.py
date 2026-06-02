"""Per-niche production recipe for autonomous Seedance workflows.

The basic playbook says what a niche is good for. This recipe turns it into a
production-ready directing contract: what to show first, how to frame it, which
references matter most, how to scale from 15s to 30m, and what failures the QA
loop should watch for.
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

_HUMAN_IDENTITY_NICHES = {
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
_DIALOGUE_HEAVY_NICHES = {"education", "finance_education", "medical_wellness", "documentary", "drama", "app_saas", "tech"}


def build_niche_production_recipe(
    *,
    niche: str,
    runtime_payload: dict[str, Any],
    target_market: str,
    target_platform: str,
    niche_playbook: dict[str, Any],
    reference_counts: dict[str, int],
    has_dialogue: bool,
    selected_creative_treatment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a concise, inspectable recipe for the selected niche/runtime."""
    niche_key = (niche or "ugc_review").strip().lower()
    runtime_class = str(runtime_payload.get("runtime_class") or "short")
    duration_s = int(runtime_payload.get("target_duration_s") or 30)
    refs = {
        "images": int(reference_counts.get("images") or 0),
        "videos": int(reference_counts.get("videos") or 0),
        "audios": int(reference_counts.get("audios") or 0),
        "pinned_assets": int(reference_counts.get("pinned_assets") or 0),
    }
    treatment = selected_creative_treatment or {}
    return {
        "schema_version": "cinejelly.niche_production_recipe.v1",
        "niche": niche_key,
        "runtime_class": runtime_class,
        "target_duration_s": duration_s,
        "target_market": target_market or "auto",
        "target_platform": target_platform or "tiktok",
        "director_recipe": {
            "opening_move": _opening_move(niche_key, niche_playbook, runtime_class),
            "story_engine": _story_engine(niche_key, runtime_class, treatment),
            "framing_language": _framing_language(niche_key, niche_playbook),
            "edit_shape": _edit_shape(niche_key, runtime_class, target_platform),
            "sound_shape": _sound_shape(niche_key, niche_playbook, has_dialogue),
        },
        "reference_recipe": {
            "priority_order": _reference_priority_order(niche_key, runtime_class, has_dialogue),
            "current_refs": refs,
            "minimum_to_attempt": _minimum_refs(niche_key, runtime_class, has_dialogue),
            "best_quality_refs": _best_refs(niche_key, runtime_class, has_dialogue),
            "assignment_rule": _assignment_rule(niche_key, runtime_class),
        },
        "duration_recipe": _duration_recipe(
            runtime_payload=runtime_payload,
            niche=niche_key,
            duration_s=duration_s,
        ),
        "seedance_prompt_recipe": {
            "block_order": [
                "reference jobs",
                "timeline",
                "environment",
                "visual style",
                "shot direction",
                "camera and sound",
                "shot contract",
                "director intent",
                "constraints",
            ],
            "must_include": _prompt_must_include(niche_key, runtime_class, has_dialogue),
            "avoid": _prompt_avoid(niche_key, runtime_class),
            "shot_unit_rule": "one physically filmable action per 4-15s Seedance unit",
            "multi_shot_rule": (
                "single prompt only for compact <=15s or very small coherent shot lists; "
                "longer videos use graph/chunk/shot execution"
            ),
        },
        "qa_recipe": {
            "hard_checks": _hard_checks(niche_key, runtime_class, has_dialogue),
            "review_checks": _review_checks(niche_key, runtime_class),
            "common_failure_modes": _failure_modes(niche_key, runtime_class),
            "retry_scope": "failed shot only; rerender downstream chained shots only when a previous final-frame anchor changes",
        },
        "operator_note": _operator_note(niche_key, runtime_class),
    }


def _opening_move(niche: str, playbook: dict[str, Any], runtime_class: str) -> str:
    hook = (playbook.get("hook_moves") or ["visual proof"])[0]
    if runtime_class in {"short_film", "episode"}:
        return f"cold-open with {hook}, then leave one unresolved question that motivates the next scene"
    return f"show {hook} before context; make the first 3 seconds visually understandable without narration"


def _story_engine(niche: str, runtime_class: str, treatment: dict[str, Any]) -> str:
    if treatment.get("director_intent"):
        base = str(treatment["director_intent"])
    elif niche in _PRODUCT_NICHES:
        base = "proof-first commercial story: result, need, tactile demo, visible payoff"
    elif niche in _DIALOGUE_HEAVY_NICHES:
        base = "question-first explainer: contradiction, simple model, example, remembered takeaway"
    elif niche == "drama":
        base = "tension-first narrative: incident, stakes, escalation, reveal, aftermath"
    else:
        base = "sensory/emotional arc: immediate hook, context, action, payoff, final image"
    if runtime_class in {"short_film", "episode"}:
        return f"{base}; scale it into acts/scenes where every scene has conflict, turn, and handoff image"
    return base


def _framing_language(niche: str, playbook: dict[str, Any]) -> list[str]:
    camera = list(playbook.get("camera") or [])[:4]
    if niche in _PRODUCT_NICHES:
        camera.append("lock product geometry with hero, macro, and in-use frames")
    if niche in _HUMAN_IDENTITY_NICHES:
        camera.append("preserve face, wardrobe, posture, and screen direction across cuts")
    if niche in _LOCATION_NICHES:
        camera.append("preserve spatial layout with establishing, path, feature, and detail shots")
    return list(dict.fromkeys(camera))[:6]


def _edit_shape(niche: str, runtime_class: str, target_platform: str) -> str:
    platform = (target_platform or "tiktok").lower()
    if runtime_class == "short":
        return "hook every 2-4s; cut only on visible change or tactile payoff"
    if runtime_class == "sequence":
        return "3-6 visual beats; each cut advances proof, space, or emotion"
    if runtime_class == "micro_film":
        return "mini act structure; alternate wide/context, close proof, reaction/payoff"
    if platform == "youtube_long":
        return "scene graph pacing; each scene carries a local question and a closing handoff image"
    return "vertical short-drama pacing; scene endings must create next-scene curiosity"


def _sound_shape(niche: str, playbook: dict[str, Any], has_dialogue: bool) -> str:
    base = str(playbook.get("audio") or "natural foley and restrained music")
    if has_dialogue:
        return f"localized dialogue/VO stays concise; keep {base} under speech and validate lip-sync"
    if niche in _SENSORY_NICHES:
        return f"foreground tactile foley: {base}; timing must match visible motion"
    return base


def _reference_priority_order(niche: str, runtime_class: str, has_dialogue: bool) -> list[str]:
    order: list[str] = []
    if niche in _HUMAN_IDENTITY_NICHES:
        order.extend(["character/creator identity image", "wardrobe/style image"])
    if niche in _PRODUCT_NICHES:
        order.extend(["product hero image", "product detail or packaging image"])
    if niche in _LOCATION_NICHES:
        order.extend(["location/environment image", "walkthrough or camera motion video"])
    if niche in _SENSORY_NICHES:
        order.extend(["motion/texture video reference", "foley/audio rhythm reference"])
    if has_dialogue:
        order.append("clean speech audio or voice reference")
    if runtime_class in {"micro_film", "short_film", "episode"}:
        order.append("previous final frame or scene handoff image")
    order.append("style/lighting reference")
    return list(dict.fromkeys(order))


def _minimum_refs(niche: str, runtime_class: str, has_dialogue: bool) -> dict[str, int]:
    images = 1
    videos = 0
    audios = 1 if has_dialogue else 0
    if niche in _PRODUCT_NICHES or niche in _HUMAN_IDENTITY_NICHES:
        images = 2 if runtime_class in {"short_film", "episode"} else 1
    if niche in _LOCATION_NICHES or runtime_class in {"short_film", "episode"}:
        videos = 1
    return {"images": images, "videos": videos, "audios": audios, "pinned_assets": 0}


def _best_refs(niche: str, runtime_class: str, has_dialogue: bool) -> dict[str, int]:
    images = 3 if niche in (_PRODUCT_NICHES | _HUMAN_IDENTITY_NICHES) else 2
    videos = 1 if niche in (_LOCATION_NICHES | _SENSORY_NICHES) else 0
    audios = 1 if has_dialogue or niche in _SENSORY_NICHES else 0
    if runtime_class in {"short_film", "episode"}:
        images = max(images, 4)
        videos = max(videos, 1)
    return {"images": images, "videos": videos, "audios": audios, "pinned_assets": 1 if runtime_class in {"short_film", "episode"} else 0}


def _assignment_rule(niche: str, runtime_class: str) -> str:
    if runtime_class in {"short_film", "episode"}:
        return "assign stable character/product/location refs globally; add scene-specific previous-final-frame handoff refs per scene"
    if niche in _PRODUCT_NICHES:
        return "hero/detail/in-use product refs should not compete with unrelated style refs in the same shot"
    if niche in _LOCATION_NICHES:
        return "wide/path/detail refs define space before close-up feature shots"
    return "each reference gets one job: identity, product, motion, sound, style, or environment"


def _duration_recipe(*, runtime_payload: dict[str, Any], niche: str, duration_s: int) -> dict[str, Any]:
    runtime_class = str(runtime_payload.get("runtime_class") or "short")
    target_unit = 12 if duration_s > 60 else min(15, max(4, duration_s))
    return {
        "runtime_class": runtime_class,
        "target_unit_duration_s": target_unit,
        "estimated_seedance_units": max(1, (duration_s + target_unit - 1) // target_unit),
        "scene_count": runtime_payload.get("scene_count") or (1 if duration_s <= 60 else max(2, duration_s // 90)),
        "chunk_count": runtime_payload.get("chunk_count") or max(1, duration_s // 60),
        "rule": (
            "screenplay -> scenes -> chunks -> 4-15s shots -> QA/retry -> assembly"
            if runtime_class in {"short_film", "episode"}
            else "compact beat flow -> 4-15s shot units -> QA/retry"
        ),
    }


def _prompt_must_include(niche: str, runtime_class: str, has_dialogue: bool) -> list[str]:
    items = [
        "concrete subject",
        "single visible action",
        "specific environment",
        "camera shot and movement",
        "lighting and color grade",
        "reference role contract",
        "negative constraints for drift/artifacts",
    ]
    if niche in _PRODUCT_NICHES:
        items.extend(["product geometry", "texture/material proof", "in-use result"])
    if niche in _HUMAN_IDENTITY_NICHES:
        items.extend(["identity, wardrobe, and pose continuity"])
    if niche in _LOCATION_NICHES:
        items.extend(["spatial layout and screen direction"])
    if has_dialogue:
        items.extend(["speech timing", "face visibility", "lip-sync QA target"])
    if runtime_class in {"short_film", "episode"}:
        items.extend(["scene purpose", "turning point", "handoff image"])
    return list(dict.fromkeys(items))


def _prompt_avoid(niche: str, runtime_class: str) -> list[str]:
    out = [
        "abstract adjectives without visible action",
        "multiple unrelated actions in one shot",
        "random location changes",
        "unrequested text overlays or fake UI text",
    ]
    if niche in _PRODUCT_NICHES:
        out.extend(["logo/package drift", "unsupported claims"])
    if niche in _HUMAN_IDENTITY_NICHES:
        out.extend(["face morphing", "wardrobe drift"])
    if runtime_class in {"short_film", "episode"}:
        out.extend(["scene without conflict", "scene ending without handoff"])
    return list(dict.fromkeys(out))


def _hard_checks(niche: str, runtime_class: str, has_dialogue: bool) -> list[str]:
    checks = ["video_url exists", "duration close to target", "prompt action visible", "no hard safety violation"]
    if niche in _PRODUCT_NICHES:
        checks.append("product geometry/reference adherence")
    if niche in _HUMAN_IDENTITY_NICHES:
        checks.append("identity/wardrobe continuity")
    if has_dialogue:
        checks.append("speech/lip-sync alignment")
    if runtime_class in {"short_film", "episode"}:
        checks.extend(["scene bridge continuity", "previous-frame handoff integrity"])
    return checks


def _review_checks(niche: str, runtime_class: str) -> list[str]:
    checks = ["hook clarity", "camera grammar", "edit rhythm", "market localization"]
    if niche in {"finance_education", "medical_wellness", "kids_family", "documentary"}:
        checks.append("claims/facts/child-safety human review")
    if runtime_class in {"short_film", "episode"}:
        checks.append("scene causality and payoff")
    return checks


def _failure_modes(niche: str, runtime_class: str) -> list[str]:
    failures = ["generic pretty clip with weak story", "camera move not motivated", "reference roles blended"]
    if niche in _PRODUCT_NICHES:
        failures.extend(["product shape drift", "fake claim shown as fact"])
    if niche in _HUMAN_IDENTITY_NICHES:
        failures.extend(["face/outfit drift", "emotion not matching scene beat"])
    if niche in _LOCATION_NICHES:
        failures.extend(["impossible room/geography", "screen direction breaks"])
    if runtime_class in {"short_film", "episode"}:
        failures.extend(["scene feels disconnected", "handoff image missing", "too few visual beats for runtime"])
    return list(dict.fromkeys(failures))


def _operator_note(niche: str, runtime_class: str) -> str:
    if runtime_class in {"short_film", "episode"}:
        return "Treat this as a production graph, not a long prompt; promote only after graph benchmarks pass."
    if niche in _PRODUCT_NICHES:
        return "Best near-term commercial lane: keep the proof visual and product refs stable."
    if niche in {"finance_education", "medical_wellness", "kids_family", "documentary"}:
        return "Planning is useful, but public output needs review for claims, facts, or safety."
    return "Autonomous short-form is reasonable when preflight and reference sufficiency pass."


__all__ = ["build_niche_production_recipe"]
