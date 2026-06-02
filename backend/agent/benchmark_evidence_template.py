"""Template for paid benchmark evidence collection."""
from __future__ import annotations

from typing import Any

from agent.benchmark_evidence_validator import REQUIRED_EVIDENCE_KEYS


def build_benchmark_evidence_template(
    *,
    case: dict[str, Any],
    model_key: str,
) -> dict[str, Any]:
    """Return a non-promotional checklist for filling benchmark evidence.

    This intentionally lives under `promotion_evidence_template`; it must not
    populate the real evidence keys until a paid render has actually produced
    artifacts and QA/reviewer data.
    """
    runtime_class = str(case.get("runtime_class") or "")
    dialogue_required = bool(
        (case.get("recommended_route") or {}).get("requires_dialogue_candidate_benchmark")
    )
    return {
        "schema_version": "cinejelly.benchmark_evidence_template.v1",
        "case_id": case.get("case_id"),
        "niche": case.get("niche"),
        "model_key": model_key,
        "required_output_fields": [
            "output_url",
            "cost_usd",
            "latency_s",
            "qa_score",
            "reviewer_decision",
        ],
        "required_evidence_keys": REQUIRED_EVIDENCE_KEYS,
        "field_guidance": {
            "per_shot_prompts": "List every rendered shot/chunk with final model prompt, negative prompt, duration, ratio, and seed if available.",
            "seedance_prompt_formula": "Attach the exact Seedance prompt formula contract used by the production plan, including formula order, niche template, reference job policy, and rewrite rules.",
            "reference_manifest": "List every @image_N, @video_N, @audio_N and pinned asset role actually used by each shot.",
            "model_route_per_shot": "Record model_key, route role, render mode, and fallback/retry reason per shot.",
            "production_graph_snapshot": "Attach graph id, scene/shot nodes, dependency edges, node status summary, retry/resume checkpoint, and final assembly metadata.",
            "scene_memory_pack": "Attach character, product, location, style, and accepted keyframe memory; use a clear not_applicable note only for single-shot no-reference routes.",
            "continuity_handoff_report": "Attach previous-frame, reference, and narrative handoff checks per adjacent scene/shot, especially for 60s+ jobs.",
            "seedance_segment_inspector": "Attach the production-decision segment inspector showing every Seedance unit is 4-15s, split strategy, and prompt-density warnings.",
            "qa_frames": "Attach sampled frame URLs or frame timestamps that prove identity/product/style/caption quality.",
            "visual_reference_similarity_report": "Attach visual_reference_probe avg/max similarity, sampled frame matches, and warnings for each reference-bound shot.",
            "semantic_quality_report": "Attach semantic QA for idea/niche alignment, hook clarity, story/proof coherence, and market fit.",
            "text_artifact_report": "Attach OCR/caption artifact probe; use not_applicable_no_text_overlay only when no text/caption is rendered.",
            "audio_report": "Attach loudness, silence, speech/lip-sync or SFX timing notes; use 'not_applicable' only for silent jobs.",
            "identity_product_notes": "Reviewer or model-backed notes on face, character, product geometry, outfit, location, and style adherence.",
            "benchmark_review_score": "Attach cinejelly.benchmark_review_score.v1 computed from the rubric dimensions, including hard failures and below-bar dimensions.",
            "accepted_minute_cost": "Attach actual accepted cost per finished minute, including retries and discarded failed shots.",
            "reviewer_notes": "Human acceptance notes; must say whether final video needs no structural edits.",
            "retry_count": "Integer count of failed/retried shot/chunk renders before final acceptance.",
        },
        "qa_focus": _qa_focus(case, dialogue_required=dialogue_required),
        "long_form_required": runtime_class in {"short_film", "episode"},
        "promotion_note": (
            "Do not copy this template into the evidence keys as proof. Fill the real keys only after paid render artifacts, QA, and reviewer approval exist."
        ),
    }


def _qa_focus(case: dict[str, Any], *, dialogue_required: bool) -> list[str]:
    focus = [
        "first_3s_hook_visible",
        "reference_identity_or_product_adherence",
        "per_shot_seedance_duration_4_to_15s",
        "caption_hashtag_market_fit",
    ]
    if int(case.get("duration_hint_s") or 0) > 180:
        focus.extend([
            "scene_handoff_continuity",
            "graph_resume_or_retry_scope",
            "final_assembly_duration_and_pacing",
        ])
    if dialogue_required:
        focus.extend(["localized_dialogue_fit", "lip_sync_or_speech_insert_quality"])
    if str(case.get("niche") or "") in {"documentary", "finance_education", "kids_family", "medical_wellness"}:
        focus.append("safety_claim_review")
    return focus


__all__ = ["build_benchmark_evidence_template"]
