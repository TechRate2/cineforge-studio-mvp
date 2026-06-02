"""Promotion policy for autonomous benchmark evidence.

Benchmark rows are only useful if the product has a clear rule for what they
unlock. This module turns stored vendor evidence into a deterministic decision:
which model/niche/runtime routes can be promoted, and which must stay locked
behind benchmark gates.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

from agent.benchmark_evidence_validator import (
    REQUIRED_EVIDENCE_KEYS,
    has_real_output_url,
    has_required_evidence_pack,
    is_promotion_grade,
)
from core import autonomous_benchmark_store


MIN_APPROVED_OUTPUTS = 2
MIN_QA_SCORE = 8.0

_CANDIDATE_MODELS = [
    "atlascloud/infinitetalk",
    "atlascloud/multitalk",
    "atlascloud/mmaudio-v2",
    "bytedance/lipsync/audio-to-video",
    "bytedance/avatar-omni-human",
    "atlascloud/instant-character",
    "atlascloud/video-upscaler",
    "atlascloud/wan-2.2-turbo/image-to-video",
    "atlascloud/framepack",
    "bytedance/seedream-v4/sequential",
    "atlascloud_catalog:veo_3_1_lite",
    "atlascloud_catalog:vidu_q3_reference_to_video",
]


def build_benchmark_promotion_policy(
    *,
    results: Optional[list[dict[str, Any]]] = None,
    min_approved_outputs: int = MIN_APPROVED_OUTPUTS,
    min_qa_score: float = MIN_QA_SCORE,
) -> dict[str, Any]:
    """Return route promotion status from benchmark results.

    A result counts as promotion-grade only when it has:
    - status == passed
    - reviewer_decision == approved
    - qa_score >= threshold
    - a non-stub output URL
    - a complete evidence pack for prompts, refs, routes, QA, review, and retry
    """
    rows = results if results is not None else autonomous_benchmark_store.list_results(limit=500)
    min_outputs = max(1, int(min_approved_outputs or MIN_APPROVED_OUTPUTS))
    qa_threshold = float(min_qa_score or MIN_QA_SCORE)

    route_groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    model_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        route_key = (
            str(row.get("model_key") or ""),
            str(row.get("niche") or ""),
            str(row.get("runtime_class") or ""),
            str(row.get("target_market") or "auto"),
        )
        route_groups[route_key].append(row)
        model_groups[str(row.get("model_key") or "")].append(row)

    promoted_routes = []
    locked_routes = []
    for key, items in sorted(route_groups.items()):
        model_key, niche, runtime_class, target_market = key
        evaluation = _evaluate_items(
            items,
            min_approved_outputs=min_outputs,
            min_qa_score=qa_threshold,
        )
        route = {
            "model_key": model_key,
            "niche": niche,
            "runtime_class": runtime_class,
            "target_market": target_market,
            **evaluation,
        }
        if evaluation["eligible_for_default_route"]:
            promoted_routes.append(route)
        else:
            locked_routes.append(route)

    candidate_models = []
    for model_key in _CANDIDATE_MODELS:
        evaluation = _evaluate_items(
            model_groups.get(model_key, []),
            min_approved_outputs=min_outputs,
            min_qa_score=qa_threshold,
        )
        candidate_models.append({
            "model_key": model_key,
            "eligible_for_auto_routing": evaluation["eligible_for_default_route"],
            **evaluation,
        })

    return {
        "schema_version": "cinejelly.benchmark_promotion_policy.v1",
        "criteria": {
            "min_approved_outputs": min_outputs,
            "min_qa_score": qa_threshold,
            "requires_status": "passed",
            "requires_reviewer_decision": "approved",
            "requires_real_output_url": True,
            "required_evidence_keys": REQUIRED_EVIDENCE_KEYS,
        },
        "summary": {
            "total_results_considered": len(rows),
            "promoted_route_count": len(promoted_routes),
            "locked_route_count": len(locked_routes),
            "candidate_model_count": len(candidate_models),
            "candidate_models_auto_routable": len([
                m for m in candidate_models if m["eligible_for_auto_routing"]
            ]),
        },
        "promoted_routes": promoted_routes,
        "locked_routes": locked_routes[:50],
        "candidate_models": candidate_models,
        "default_policy": (
            "Keep experimental dialogue/audio/upscale/character models locked until "
            "this policy marks the relevant model/niche/runtime route eligible."
        ),
    }


def _evaluate_items(
    items: list[dict[str, Any]],
    *,
    min_approved_outputs: int,
    min_qa_score: float,
) -> dict[str, Any]:
    passing = [item for item in items if _is_promotion_grade(item, min_qa_score=min_qa_score)]
    missing_reasons = []
    if len(passing) < min_approved_outputs:
        missing_reasons.append(
            f"needs_{min_approved_outputs}_approved_outputs_has_{len(passing)}"
        )
    if not any(has_real_output_url(item) for item in items):
        missing_reasons.append("missing_real_output_url")
    if not any(item.get("reviewer_decision") == "approved" for item in items):
        missing_reasons.append("missing_approved_human_review")
    if not any((item.get("qa_score") or 0) >= min_qa_score for item in items):
        missing_reasons.append("missing_min_qa_score")
    if not any(has_real_output_url(item) and has_required_evidence_pack(item) for item in items):
        missing_reasons.append("missing_required_evidence_pack")
    if not any(has_real_output_url(item) and item.get("cost_usd") is not None for item in items):
        missing_reasons.append("missing_cost_usd")
    if not any(has_real_output_url(item) and item.get("latency_s") is not None for item in items):
        missing_reasons.append("missing_latency_s")

    return {
        "eligible_for_default_route": len(missing_reasons) == 0,
        "total_results": len(items),
        "promotion_grade_results": len(passing),
        "best_qa_score": max([float(item.get("qa_score") or 0) for item in items], default=0.0),
        "missing_reasons": missing_reasons,
        "evidence_ids": [str(item.get("id")) for item in passing[:5] if item.get("id")],
    }


def _is_promotion_grade(item: dict[str, Any], *, min_qa_score: float) -> bool:
    return is_promotion_grade(item, min_qa_score=min_qa_score)


__all__ = [
    "build_benchmark_promotion_policy",
    "MIN_APPROVED_OUTPUTS",
    "MIN_QA_SCORE",
    "REQUIRED_EVIDENCE_KEYS",
]
