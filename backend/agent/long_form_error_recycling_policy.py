"""Long-form error recycling policy for autonomous Seedance graph jobs.

For 5-30 minute work, retries should not simply resubmit the same prompt.
Accepted outputs become positive keyframe memory; failed outputs become negative
constraints that the next retry and the next scene can avoid.
"""
from __future__ import annotations

from typing import Any


_DRIFT_FAILURES = [
    "identity_drift",
    "product_or_logo_drift",
    "location_layout_drift",
    "wardrobe_or_prop_drift",
    "style_or_color_grade_reset",
    "fake_text_or_logo_artifact",
    "audio_or_lipsync_desync",
]


def build_long_form_error_recycling_policy(
    *,
    runtime_payload: dict[str, Any],
    target_market: str,
    has_dialogue: bool,
    seedance_segment_inspector: dict[str, Any],
    hero_shot_candidate_policy: dict[str, Any],
    route_quality_scorecard: dict[str, Any],
) -> dict[str, Any]:
    """Return the retry/memory policy for long-form and multi-scene jobs."""
    runtime_class = str(runtime_payload.get("runtime_class") or "short")
    target_duration_s = int(runtime_payload.get("target_duration_s") or 30)
    is_long_form = runtime_class in {"micro_film", "short_film", "episode"} or target_duration_s > 60
    scorecard = route_quality_scorecard or {}
    blocking = list(scorecard.get("blocking_reasons") or [])
    graph_required = bool(scorecard.get("requires_graph_executor")) or runtime_class in {"short_film", "episode"}
    segments = [
        item for item in (seedance_segment_inspector.get("segments") or [])
        if isinstance(item, dict)
    ]
    selected_segments = segments[:6]
    memory_updates = _memory_updates(selected_segments)
    negative_memory = _negative_memory_templates(
        has_dialogue=has_dialogue,
        blocking_reasons=blocking,
        hero_shot_candidate_policy=hero_shot_candidate_policy,
    )
    mode = _mode(
        is_long_form=is_long_form,
        graph_required=graph_required,
        blocking_reasons=blocking,
    )
    return {
        "schema_version": "cinejelly.long_form_error_recycling_policy.v1",
        "enabled": mode in {"graph_required", "micro_film_recommended"},
        "mode": mode,
        "runtime_class": runtime_class,
        "target_duration_s": target_duration_s,
        "target_market": target_market,
        "graph_required": graph_required,
        "segment_count_previewed": len(selected_segments),
        "memory_update_plan": memory_updates,
        "negative_memory_templates": negative_memory,
        "retry_feedback_loop": [
            "sample frames and QA report after every rendered unit",
            "write accepted first/last/key frames into positive memory",
            "write failed drift/artifact reasons into negative memory",
            "retry only the failed shot/keyframe unless screenplay or scene purpose is structurally wrong",
            "inject nearest accepted keyframe plus negative constraints into the retry prompt",
            "do not promote long-form route until two paid graph runs pass continuity/cost thresholds",
        ],
        "graph_node_patch_contract": {
            "on_success": [
                "accepted_keyframe_url",
                "first_frame_url",
                "last_frame_url",
                "qa_score",
                "continuity_tags",
            ],
            "on_failure": [
                "failure_code",
                "failed_frame_samples",
                "negative_prompt_constraints",
                "retry_repair_hint",
                "do_not_reuse_as_anchor",
            ],
        },
        "promotion_rule": (
            "Long-form error recycling becomes default only after paid graph benchmarks "
            "show fewer drift retries and acceptable accepted-minute cost."
        ),
    }


def _mode(*, is_long_form: bool, graph_required: bool, blocking_reasons: list[str]) -> str:
    if graph_required:
        return "graph_required"
    if is_long_form:
        return "micro_film_recommended"
    if any("dialogue" in reason for reason in blocking_reasons):
        return "dialogue_retry_only"
    return "short_form_optional"


def _memory_updates(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    updates: list[dict[str, Any]] = []
    for item in segments:
        segment_id = str(item.get("segment_id") or "")
        if not segment_id:
            continue
        qa = list(item.get("qa_checks") or [])
        updates.append({
            "segment_id": segment_id,
            "source_scene_id": item.get("source_scene_id"),
            "positive_memory_on_pass": [
                "first_frame_url",
                "last_frame_url",
                "accepted_keyframe_url",
                "identity/product/location tags",
            ],
            "negative_memory_on_fail": _negative_codes_for_qa(qa),
            "next_prompt_injection": (
                "reuse accepted same-scene keyframe and forbid failed drift/artifact patterns"
            ),
        })
    return updates


def _negative_memory_templates(
    *,
    has_dialogue: bool,
    blocking_reasons: list[str],
    hero_shot_candidate_policy: dict[str, Any],
) -> list[dict[str, Any]]:
    templates = [
        {
            "failure_code": code,
            "negative_constraint": _negative_constraint(code),
            "retry_scope": "shot_or_keyframe",
        }
        for code in _DRIFT_FAILURES
    ]
    if has_dialogue or any("dialogue" in reason for reason in blocking_reasons):
        templates.append({
            "failure_code": "speaker_or_phoneme_mismatch",
            "negative_constraint": "avoid long visible monologues; split dialogue into short inserts and require lip-sync review",
            "retry_scope": "dialogue_insert",
        })
    if (hero_shot_candidate_policy or {}).get("candidate_beat_count"):
        templates.append({
            "failure_code": "hero_candidate_underperforms",
            "negative_constraint": "do not reuse the weak candidate; keep the stronger hook/product/payoff frame as the next anchor",
            "retry_scope": "candidate_selection",
        })
    return templates


def _negative_codes_for_qa(qa_checks: list[str]) -> list[str]:
    text = " ".join(str(item).lower() for item in qa_checks)
    codes = ["prompt_adherence_failure"]
    if "identity" in text:
        codes.append("identity_drift")
    if "product" in text:
        codes.append("product_or_logo_drift")
    if "handoff" in text or "continuity" in text:
        codes.append("scene_handoff_drift")
    if "dialogue" in text or "lip" in text:
        codes.append("audio_or_lipsync_desync")
    if "claims" in text or "safety" in text:
        codes.append("claims_or_policy_risk")
    return list(dict.fromkeys(codes))


def _negative_constraint(code: str) -> str:
    mapping = {
        "identity_drift": "preserve the approved character face, body, outfit, age, and pose family; avoid morphing",
        "product_or_logo_drift": "preserve product geometry, material, label, logo, and color; avoid invented packaging",
        "location_layout_drift": "preserve room/location layout, lighting direction, and object positions",
        "wardrobe_or_prop_drift": "preserve wardrobe, props, and hand-held objects from the accepted keyframe",
        "style_or_color_grade_reset": "preserve color grade, lens language, and visual texture from accepted memory",
        "fake_text_or_logo_artifact": "no unintended text, watermark, logo, caption, or signage inside the generated frames",
        "audio_or_lipsync_desync": "keep visible speech short; align mouth motion to audio or route to lip-sync repair",
    }
    return mapping.get(code, "avoid repeating the failed visual artifact or story mismatch")


__all__ = ["build_long_form_error_recycling_policy"]
