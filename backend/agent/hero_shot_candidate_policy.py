"""Hero-shot candidate selection policy for autonomous video jobs.

Top short-drama/product workflows do not treat every shot equally. The hook,
product close-up, character reveal, and payoff/twist carry most of the perceived
quality. This module marks those high-value beats for optional multi-candidate
generation while keeping the user UI one-click and preventing unbounded cost.
"""
from __future__ import annotations

from typing import Any


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
    "drama",
    "education",
    "fitness",
    "kids_family",
    "lifestyle",
    "music_video",
    "ugc_review",
}
_REVIEW_LOCKED_NICHES = {"documentary", "finance_education", "kids_family", "medical_wellness"}


def build_hero_shot_candidate_policy(
    *,
    niche: str,
    runtime_payload: dict[str, Any],
    target_market: str,
    reference_counts: dict[str, int],
    has_dialogue: bool,
    seedance_segment_inspector: dict[str, Any],
    route_quality_scorecard: dict[str, Any],
) -> dict[str, Any]:
    """Return which high-value beats should receive candidate generation.

    The result is intentionally a planning contract. It does not spend vendor
    credits by itself; graph/worker code can later execute it after budget and
    benchmark gates pass.
    """
    runtime_class = str(runtime_payload.get("runtime_class") or "short")
    target_duration_s = int(runtime_payload.get("target_duration_s") or 30)
    refs = {
        "images": int(reference_counts.get("images") or 0),
        "videos": int(reference_counts.get("videos") or 0),
        "audios": int(reference_counts.get("audios") or 0),
        "pinned_assets": int(reference_counts.get("pinned_assets") or 0),
    }
    scorecard = route_quality_scorecard or {}
    blocking = set(scorecard.get("blocking_reasons") or [])
    launch_tier = str(scorecard.get("launch_tier") or "")
    auto_route_allowed = bool(scorecard.get("auto_route_allowed"))
    route_key = scorecard.get("route_key") or {}
    primary_model = str(route_key.get("model_key") or "seedance_2_0_fast_ref")

    candidate_beats = _candidate_beats(
        niche=niche,
        runtime_class=runtime_class,
        target_duration_s=target_duration_s,
        refs=refs,
        has_dialogue=has_dialogue,
        seedance_segment_inspector=seedance_segment_inspector,
    )
    max_candidates = _max_candidates(
        niche=niche,
        runtime_class=runtime_class,
        refs=refs,
        launch_tier=launch_tier,
        auto_route_allowed=auto_route_allowed,
        blocking=blocking,
    )
    mode = _mode(
        niche=niche,
        runtime_class=runtime_class,
        auto_route_allowed=auto_route_allowed,
        blocking=blocking,
        max_candidates=max_candidates,
    )
    estimated_extra_units = max(0, max_candidates - 1) * len(candidate_beats)
    return {
        "schema_version": "cinejelly.hero_shot_candidate_policy.v1",
        "enabled": mode == "auto_candidate_selection",
        "mode": mode,
        "niche": niche,
        "runtime_class": runtime_class,
        "target_market": target_market,
        "primary_model": primary_model,
        "max_candidates_per_marked_beat": max_candidates,
        "candidate_beat_count": len(candidate_beats),
        "estimated_extra_seedance_units": estimated_extra_units,
        "candidate_beats": candidate_beats,
        "budget_policy": {
            "default": "do not spend extra vendor credits unless route policy allows it",
            "short_form": "2 candidates for high-value hook/product/payoff beats when references are sufficient",
            "long_form": "candidate selection applies to first frames/keyframes first; full video candidates stay benchmark-gated",
            "review_locked": "planning only; human review required before candidate renders",
        },
        "selection_criteria": [
            "reference identity/product fidelity",
            "hook clarity in first 3 seconds",
            "physical action completion",
            "camera/story beat readability",
            "OCR/text artifact absence",
            "audio/lip-sync fit when dialogue is visible",
            "accepted-minute cost and retry rate",
        ],
        "promotion_rule": (
            "A candidate-selection route becomes default only after paid outputs show better QA "
            "and accepted-minute cost than the single-candidate baseline."
        ),
    }


def _candidate_beats(
    *,
    niche: str,
    runtime_class: str,
    target_duration_s: int,
    refs: dict[str, int],
    has_dialogue: bool,
    seedance_segment_inspector: dict[str, Any],
) -> list[dict[str, Any]]:
    beats: list[dict[str, Any]] = [
        _beat(
            "opening_hook",
            "first frame / first 3 seconds",
            "scroll-stop visual proof",
            ["hook clarity", "subject/action readability"],
        )
    ]
    if niche in _PRODUCT_NICHES:
        beats.append(_beat(
            "product_or_hero_closeup",
            "best product/detail proof shot",
            "preserve geometry, material, label, and tactile payoff",
            ["product fidelity", "no hallucinated labels", "macro texture clarity"],
        ))
    if niche in _CHARACTER_NICHES and (refs["images"] > 0 or refs["pinned_assets"] > 0):
        beats.append(_beat(
            "character_reveal",
            "first face/body identity beat",
            "lock character appearance before later continuity handoffs",
            ["identity consistency", "outfit/face stability"],
        ))
    if (
        runtime_class in {"micro_film", "short_film", "episode"}
        or target_duration_s >= 60
        or niche == "drama"
        or niche in _PRODUCT_NICHES
    ):
        beats.append(_beat(
            "turn_or_payoff",
            "scene turn, twist, final proof, or emotional aftertaste",
            "make the promise resolve visually, not only in narration",
            ["payoff clarity", "scene causality", "handoff continuity"],
        ))
    if has_dialogue:
        beats.append(_beat(
            "dialogue_closeup",
            "visible speech insert or repair beat",
            "keep speech short and benchmark lip-sync before promotion",
            ["lip-sync", "speaker consistency", "audio loudness"],
        ))

    segment_ids = [
        str(item.get("segment_id"))
        for item in (seedance_segment_inspector.get("segments") or [])
        if isinstance(item, dict) and item.get("segment_id")
    ]
    for index, beat in enumerate(beats):
        if index < len(segment_ids):
            beat["preview_segment_id"] = segment_ids[index]
    return beats[:5]


def _beat(beat_id: str, scope: str, purpose: str, qa: list[str]) -> dict[str, Any]:
    return {
        "id": beat_id,
        "scope": scope,
        "purpose": purpose,
        "qa_focus": qa,
    }


def _max_candidates(
    *,
    niche: str,
    runtime_class: str,
    refs: dict[str, int],
    launch_tier: str,
    auto_route_allowed: bool,
    blocking: set[str],
) -> int:
    if niche in _REVIEW_LOCKED_NICHES:
        return 1
    if "reference_render_blocking" in blocking or not auto_route_allowed:
        return 1
    ref_strength = refs["images"] + refs["pinned_assets"]
    if runtime_class in {"short_film", "episode"}:
        return 2 if "long_form_route_missing_two_approved_outputs" not in blocking and ref_strength >= 2 else 1
    if launch_tier in {"launch_ready", "short_form_candidate", "qa_required"} and ref_strength >= 2:
        return 3 if niche in {"beauty", "food", "fashion", "ecommerce_catalog"} else 2
    return 1


def _mode(
    *,
    niche: str,
    runtime_class: str,
    auto_route_allowed: bool,
    blocking: set[str],
    max_candidates: int,
) -> str:
    if niche in _REVIEW_LOCKED_NICHES:
        return "review_only"
    if runtime_class in {"short_film", "episode"}:
        return "benchmark_graph_keyframes"
    if max_candidates <= 1:
        return "single_candidate_baseline"
    if auto_route_allowed and not {"reference_render_blocking", "niche_resolution_ambiguous"} & blocking:
        return "auto_candidate_selection"
    return "benchmark_only"


__all__ = ["build_hero_shot_candidate_policy"]
