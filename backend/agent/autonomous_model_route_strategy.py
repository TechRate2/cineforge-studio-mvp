"""Source-backed model routing strategy for CineJelly Autonomous Director.

The one-click UI should not expose a model picker. The agent still needs a
clear internal contract for when Seedance is enough, when a dialogue/audio
lane is only a benchmark candidate, and which emerging AtlasCloud catalog
models are worth testing before they can be promoted.
"""
from __future__ import annotations

from typing import Any


_PREMIUM_VISUAL_NICHES = {
    "beauty",
    "fashion",
    "food",
    "ecommerce_catalog",
    "restaurant_hospitality",
    "automotive",
}

_SAFETY_REVIEW_NICHES = {
    "documentary",
    "finance_education",
    "kids_family",
    "medical_wellness",
}


def build_model_route_strategy(
    *,
    niche: str,
    target_market: str,
    target_platform: str,
    duration_s: int,
    runtime_payload: dict[str, Any],
    reference_counts: dict[str, int],
    has_dialogue: bool,
    speaker_count: int = 1,
    creative_treatment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return internal model routing guidance for a production decision."""
    niche_key = (niche or "ugc_review").strip().lower()
    market = (target_market or "auto").strip().lower()
    platform = (target_platform or "tiktok").strip().lower()
    duration = max(4, int(duration_s or 30))
    runtime_class = str(runtime_payload.get("runtime_class") or "short")
    refs = {
        "images": max(0, int(reference_counts.get("images") or 0)),
        "videos": max(0, int(reference_counts.get("videos") or 0)),
        "audios": max(0, int(reference_counts.get("audios") or 0)),
        "pinned_assets": max(0, int(reference_counts.get("pinned_assets") or 0)),
    }
    speakers = max(1, int(speaker_count or 1))
    treatment_id = str((creative_treatment or {}).get("treatment_id") or "")
    has_visual_refs = bool(refs["images"] or refs["videos"] or refs["pinned_assets"])
    is_long_form = runtime_class in {"short_film", "episode"} or duration > 180
    is_premium_visual = niche_key in _PREMIUM_VISUAL_NICHES or treatment_id == "cinematic_premium"

    primary_visual = "seedance_2_0_fast_ref" if has_visual_refs or refs["audios"] else "seedance_2_0_fast_t2v"
    if is_premium_visual and has_visual_refs:
        primary_visual = "seedance_2_0_ref"

    strategy = {
        "schema_version": "cinejelly.model_route_strategy.v1",
        "summary": {
            "route_mode": "graph_per_shot" if is_long_form else "short_form_director",
            "primary_visual_model": primary_visual,
            "continuity_model": "seedance_2_0_fast_i2v",
            "premium_visual_model": "seedance_2_0_ref",
            "draft_visual_model": "seedance_2_0_fast_ref" if has_visual_refs else "seedance_2_0_fast_t2v",
            "target_market": market,
            "target_platform": platform,
            "runtime_class": runtime_class,
        },
        "seedance_execution": _seedance_execution(
            duration=duration,
            runtime_class=runtime_class,
            has_visual_refs=has_visual_refs,
            is_premium_visual=is_premium_visual and has_visual_refs,
        ),
        "active_routes": _active_routes(
            primary_visual=primary_visual,
            has_visual_refs=has_visual_refs,
            is_long_form=is_long_form,
            is_premium_visual=is_premium_visual,
            has_dialogue=has_dialogue,
        ),
        "benchmark_locked_candidates": _benchmark_locked_candidates(
            niche=niche_key,
            market=market,
            duration=duration,
            refs=refs,
            has_dialogue=has_dialogue,
            speaker_count=speakers,
            is_long_form=is_long_form,
            is_premium_visual=is_premium_visual,
        ),
        "route_locks": _route_locks(
            niche=niche_key,
            has_dialogue=has_dialogue,
            is_long_form=is_long_form,
            has_visual_refs=has_visual_refs,
        ),
        "promotion_policy": [
            "Keep Seedance 2.0 as the default cinematic/product/story coverage model.",
            "Do not auto-route new AtlasCloud catalog models until benchmark evidence has two real approved outputs for the same model/niche/runtime/market.",
            "For 5-30 minute videos, route per scene/shot/chunk and carry previous final frames; never submit one long Seedance prompt.",
            "Use dialogue/audio/upscale models as inserts or post passes, not replacements for the director graph.",
        ],
    }
    return strategy


def _seedance_execution(
    *,
    duration: int,
    runtime_class: str,
    has_visual_refs: bool,
    is_premium_visual: bool,
) -> dict[str, Any]:
    target_unit = 12 if duration > 60 else min(15, max(4, duration))
    estimated_units = max(1, (duration + target_unit - 1) // target_unit)
    return {
        "unit_duration_s": target_unit,
        "estimated_units": estimated_units,
        "single_call_allowed": duration <= 15,
        "requires_reference_to_video": has_visual_refs,
        "premium_ref_for_hero_shots": is_premium_visual,
        "long_form_method": (
            "scene graph -> 4-15s Seedance units -> previous-final-frame i2v handoff -> assembly QA"
            if runtime_class in {"short_film", "episode"}
            else "director shot list -> Seedance prompt compile -> QA/retry"
        ),
    }


def _active_routes(
    *,
    primary_visual: str,
    has_visual_refs: bool,
    is_long_form: bool,
    is_premium_visual: bool,
    has_dialogue: bool,
) -> list[dict[str, Any]]:
    routes = [
        {
            "model_key": primary_visual,
            "role": "primary_visual_director",
            "status": "active",
            "why": "Seedance 2.0 is the core quad-modal visual route for cinematic movement, reference binding, and multi-shot prompting.",
            "use_when": "all autonomous jobs unless a shot is a dedicated dialogue/audio/post-process insert",
        },
        {
            "model_key": "seedance_2_0_fast_i2v",
            "role": "continuity_chain",
            "status": "active",
            "why": "Use previous final frame or locked keyframe to keep long-form shots continuous.",
            "use_when": "later shots/scenes, failed-shot retry, or long-form handoff nodes",
        },
    ]
    if is_premium_visual and has_visual_refs:
        routes.append({
            "model_key": "seedance_2_0_ref",
            "role": "premium_hero_rerender",
            "status": "active",
            "why": "Premium visual niches need stronger product/skin/food/fashion fidelity.",
            "use_when": "hero shots, packaging close-ups, beauty/food/fashion final rerenders",
        })
    if not has_visual_refs:
        routes.append({
            "model_key": "seedance_2_0_fast_t2v",
            "role": "no_reference_draft",
            "status": "active",
            "why": "Only use text-to-video when the user did not supply usable anchors.",
            "use_when": "abstract b-roll, style draft, or initial motion probe",
        })
    if has_dialogue:
        routes.append({
            "model_key": "wan_2_7_i2v",
            "role": "short_driven_audio_lipsync",
            "status": "active_narrow_fallback",
            "why": "Current active driven-audio fallback for 5-10s visible speech inserts.",
            "use_when": "short localized talking-head line after visual references are locked",
        })
    if is_long_form:
        routes.append({
            "model_key": "production_graph_executor",
            "role": "orchestration",
            "status": "active",
            "why": "Long videos need resumable scene/shot graph execution, not one render call.",
            "use_when": "any requested runtime above 180 seconds",
        })
    return routes


def _benchmark_locked_candidates(
    *,
    niche: str,
    market: str,
    duration: int,
    refs: dict[str, int],
    has_dialogue: bool,
    speaker_count: int,
    is_long_form: bool,
    is_premium_visual: bool,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    if has_dialogue and speaker_count >= 2:
        out.append(_candidate(
            "atlascloud/multitalk",
            role="multi_speaker_dialogue_insert",
            fit="high",
            why="Two-speaker drama/interview scenes need turn-taking tests before auto-route.",
            benchmark_needed=["Vietnamese/English turn taking", "speaker identity stability", "120s segment stability", "cost per finished minute"],
        ))
    if has_dialogue and (duration > 10 or is_long_form):
        out.append(_candidate(
            "atlascloud/infinitetalk",
            role="long_talking_head_or_presenter",
            fit="high" if duration >= 60 else "medium",
            why="Candidate for long localized presenter/dialogue inserts while Seedance keeps cinematic coverage.",
            benchmark_needed=["Vietnamese phoneme match", "10 minute identity stability", "body/hand stability", "cost per finished minute"],
        ))
    if has_dialogue:
        out.append(_candidate(
            "bytedance/lipsync/audio-to-video",
            role="post_render_lipsync_repair",
            fit="medium",
            why="Repair visible speech after visual QA instead of regenerating the whole scene.",
            benchmark_needed=["VN phoneme match", "face stability", "artifact rate", "latency"],
        ))
    if refs["audios"] or niche in {"food", "asmr", "travel", "restaurant_hospitality", "music_video"}:
        out.append(_candidate(
            "atlascloud/mmaudio-v2",
            role="post_render_audio_foley",
            fit="high" if refs["audios"] else "medium",
            why="Dedicated ambience, foley, SFX, and beat pass after visual render succeeds.",
            benchmark_needed=["sound/action sync", "loudness", "SFX realism", "music/beat timing"],
        ))
    if is_premium_visual and (refs["images"] or refs["pinned_assets"]):
        out.append(_candidate(
            "atlascloud_catalog:vidu_q3_reference_to_video",
            role="subject_consistency_challenger",
            fit="medium",
            why="Benchmark as a challenger route for character/product consistency, not as a UI model picker.",
            benchmark_needed=["identity/product adherence", "motion realism", "cost versus Seedance", "retry rate"],
        ))
    if not refs["images"] and not refs["pinned_assets"]:
        out.append(_candidate(
            "atlascloud_catalog:veo_3_1_lite",
            role="text_to_video_draft_challenger",
            fit="medium",
            why="Potential draft route for no-reference cinematic concepts, locked until cost/quality proves value.",
            benchmark_needed=["prompt adherence", "cost per usable draft", "style controllability", "handoff compatibility"],
        ))
    if is_long_form:
        out.append(_candidate(
            "atlascloud/wan-2.2-turbo/image-to-video",
            role="cheap_keyframe_motion_or_draft_chain",
            fit="medium",
            why="Candidate for cheaper long-form keyframe motion probes before premium Seedance rerenders.",
            benchmark_needed=["previous-frame continuity", "visual quality drop", "cost savings", "retry rate"],
        ))
    if market == "vn" and has_dialogue:
        out.append(_candidate(
            "bytedance/avatar-omni-human",
            role="portrait_presenter_vn_candidate",
            fit="medium",
            why="Possible low-cost portrait presenter lane for Vietnamese education/UGC after uncanny-rate benchmark.",
            benchmark_needed=["VN voice compatibility", "identity preservation", "uncanny rate", "segment length stability"],
        ))
    return out


def _candidate(
    model_key: str,
    *,
    role: str,
    fit: str,
    why: str,
    benchmark_needed: list[str],
) -> dict[str, Any]:
    return {
        "model_key": model_key,
        "role": role,
        "fit": fit,
        "status": "benchmark_locked",
        "why": why,
        "benchmark_needed": benchmark_needed,
    }


def _route_locks(
    *,
    niche: str,
    has_dialogue: bool,
    is_long_form: bool,
    has_visual_refs: bool,
) -> list[str]:
    locks = []
    if has_dialogue:
        locks.append("dialogue candidates require real lip-sync/identity benchmark before default routing")
    if is_long_form:
        locks.append("long-form routes require graph resume and scene handoff evidence")
    if not has_visual_refs:
        locks.append("no-reference jobs cannot claim identity/product consistency")
    if niche in _SAFETY_REVIEW_NICHES:
        locks.append("safety-sensitive niche requires claim/fact/child-safety review")
    return locks


__all__ = ["build_model_route_strategy"]
