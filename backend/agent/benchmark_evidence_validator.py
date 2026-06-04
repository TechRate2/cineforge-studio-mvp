"""Validation for benchmark evidence rows.

Promotion policy should not infer production readiness from a nice-looking
output URL alone. A benchmark row must carry the operational evidence needed to
debug and reproduce the result: prompts, references, model route, QA frames,
audio/identity review, cost, latency, and retry count.
"""
from __future__ import annotations

from typing import Any


REQUIRED_EVIDENCE_KEYS = [
    "per_shot_prompts",
    "seedance_prompt_formula",
    "reference_manifest",
    "model_route_per_shot",
    "production_graph_snapshot",
    "scene_memory_pack",
    "continuity_handoff_report",
    "seedance_segment_inspector",
    "qa_frames",
    "visual_reference_similarity_report",
    "semantic_quality_report",
    "text_artifact_report",
    "audio_report",
    "identity_product_notes",
    "benchmark_review_score",
    "accepted_minute_cost",
    "reviewer_notes",
    "retry_count",
]


def validate_benchmark_result_evidence(
    item: dict[str, Any],
    *,
    min_qa_score: float = 8.0,
) -> dict[str, Any]:
    """Return a deterministic promotion-readiness validation for one row."""
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    present_keys = [
        key for key in REQUIRED_EVIDENCE_KEYS
        if _evidence_value_present(evidence.get(key))
    ]
    missing_keys = [
        key for key in REQUIRED_EVIDENCE_KEYS
        if key not in present_keys
    ]
    missing_reasons: list[str] = []
    if item.get("status") != "passed":
        missing_reasons.append("status_not_passed")
    if item.get("reviewer_decision") != "approved":
        missing_reasons.append("reviewer_not_approved")
    if float(item.get("qa_score") or 0) < min_qa_score:
        missing_reasons.append("qa_score_below_threshold")
    if not has_real_output_url(item):
        missing_reasons.append("missing_real_output_url")
    if item.get("cost_usd") is None:
        missing_reasons.append("missing_cost_usd")
    if item.get("latency_s") is None:
        missing_reasons.append("missing_latency_s")
    if missing_keys:
        missing_reasons.append("missing_required_evidence_pack")

    return {
        "schema_version": "cinejelly.benchmark_evidence_validation.v1",
        "promotion_ready": not missing_reasons,
        "min_qa_score": min_qa_score,
        "missing_reasons": missing_reasons,
        "required_evidence_keys": REQUIRED_EVIDENCE_KEYS,
        "present_evidence_keys": present_keys,
        "missing_evidence_keys": missing_keys,
    }


def is_promotion_grade(
    item: dict[str, Any],
    *,
    min_qa_score: float = 8.0,
) -> bool:
    return validate_benchmark_result_evidence(
        item,
        min_qa_score=min_qa_score,
    )["promotion_ready"]


def has_required_evidence_pack(item: dict[str, Any]) -> bool:
    evidence = item.get("evidence") or {}
    if not isinstance(evidence, dict):
        return False
    return all(_evidence_value_present(evidence.get(key)) for key in REQUIRED_EVIDENCE_KEYS)


def has_real_output_url(item: dict[str, Any]) -> bool:
    url = str(item.get("output_url") or "")
    return bool(url and not url.startswith("stub://"))


def _evidence_value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


__all__ = [
    "REQUIRED_EVIDENCE_KEYS",
    "has_real_output_url",
    "has_required_evidence_pack",
    "is_promotion_grade",
    "validate_benchmark_result_evidence",
]
