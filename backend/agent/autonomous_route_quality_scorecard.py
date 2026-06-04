"""Route-level quality and promotion scorecard for autonomous jobs.

The capability matrix says what the system can generally do. A production
decision needs a narrower answer: for this niche, runtime, market, references,
and selected model route, is the path safe to auto-render, only usable with QA,
or still benchmark-locked before any top-tier claim?
"""
from __future__ import annotations

from typing import Any, Optional

from agent.benchmark_promotion_policy import build_benchmark_promotion_policy
from core import autonomous_benchmark_store


_REVIEW_REQUIRED_NICHES = {"documentary", "finance_education", "kids_family", "medical_wellness"}
_HIGH_READY_NICHES = {
    "app_saas",
    "asmr",
    "beauty",
    "ecommerce_catalog",
    "fashion",
    "food",
    "lifestyle",
    "tech",
    "ugc_review",
}


def build_route_quality_scorecard(
    *,
    decision: dict[str, Any],
    reference_sufficiency: dict[str, Any],
    niche_runtime_director: dict[str, Any],
    model_route_strategy: dict[str, Any],
    benchmark_results: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Return route promotion status for one production decision."""
    d = decision.get("decision") or decision
    niche = str(d.get("niche") or niche_runtime_director.get("niche") or "ugc_review")
    runtime_class = str(d.get("runtime_class") or niche_runtime_director.get("runtime_class") or "short")
    target_market = str(d.get("target_market") or niche_runtime_director.get("target_market") or "auto")
    primary_model = str(
        ((d.get("primary_model_route") or {}).get("primary_visual_model"))
        or ((model_route_strategy.get("summary") or {}).get("primary_visual_model"))
        or "seedance_2_0_fast_ref"
    )
    graph_required = bool(d.get("graph_required"))
    dialogue_required = bool(d.get("dialogue_required"))
    niche_resolution_review_required = bool(d.get("niche_resolution_review_required"))
    benchmark_required = bool(d.get("benchmark_required_before_top_tier_claim"))
    refs_ready = bool(reference_sufficiency.get("top_tier_ready"))
    render_blocking_refs = bool(reference_sufficiency.get("render_blocking"))
    risks = list(niche_runtime_director.get("risk_register") or [])
    evidence_rows = (
        benchmark_results
        if benchmark_results is not None
        else autonomous_benchmark_store.list_results(
            niche=niche,
            model_key=primary_model,
            limit=100,
        )
    )
    promotion = build_benchmark_promotion_policy(results=evidence_rows)
    exact_route = _exact_route(
        promotion.get("promoted_routes") or [],
        model_key=primary_model,
        niche=niche,
        runtime_class=runtime_class,
        target_market=target_market,
    )

    blocking_reasons = _blocking_reasons(
        niche=niche,
        runtime_class=runtime_class,
        graph_required=graph_required,
        dialogue_required=dialogue_required,
        niche_resolution_review_required=niche_resolution_review_required,
        benchmark_required=benchmark_required,
        refs_ready=refs_ready,
        render_blocking_refs=render_blocking_refs,
        exact_route=exact_route,
        risks=risks,
    )
    launch_tier = _launch_tier(
        niche=niche,
        runtime_class=runtime_class,
        blocking_reasons=blocking_reasons,
        graph_required=graph_required,
    )
    auto_route_allowed = _auto_route_allowed(
        launch_tier=launch_tier,
        blocking_reasons=blocking_reasons,
    )

    return {
        "schema_version": "cinejelly.route_quality_scorecard.v1",
        "route_key": {
            "model_key": primary_model,
            "niche": niche,
            "runtime_class": runtime_class,
            "target_market": target_market,
        },
        "launch_tier": launch_tier,
        "auto_route_allowed": auto_route_allowed,
        "top_tier_claim_allowed": bool(exact_route) and refs_ready and not blocking_reasons,
        "requires_human_review": niche in _REVIEW_REQUIRED_NICHES or "manual_review_required_before_top_tier_claim" in risks,
        "requires_graph_executor": graph_required,
        "requires_benchmark_before_premium_claim": bool(blocking_reasons),
        "blocking_reasons": blocking_reasons,
        "evidence_status": {
            "exact_route_promoted": bool(exact_route),
            "total_results_considered": promotion["summary"]["total_results_considered"],
            "promoted_route_count": promotion["summary"]["promoted_route_count"],
            "reference_top_tier_ready": refs_ready,
            "reference_score": reference_sufficiency.get("score"),
            "benchmark_policy": promotion["criteria"],
        },
        "next_benchmark_batch": _next_benchmark_batch(
            primary_model=primary_model,
            niche=niche,
            runtime_class=runtime_class,
            target_market=target_market,
            graph_required=graph_required,
            dialogue_required=dialogue_required,
            blocking_reasons=blocking_reasons,
        ),
        "operator_policy": _operator_policy(launch_tier),
    }


def _exact_route(
    routes: list[dict[str, Any]],
    *,
    model_key: str,
    niche: str,
    runtime_class: str,
    target_market: str,
) -> dict[str, Any] | None:
    for route in routes:
        if (
            str(route.get("model_key")) == model_key
            and str(route.get("niche")) == niche
            and str(route.get("runtime_class")) == runtime_class
            and str(route.get("target_market") or "auto") == target_market
        ):
            return route
    return None


def _blocking_reasons(
    *,
    niche: str,
    runtime_class: str,
    graph_required: bool,
    dialogue_required: bool,
    niche_resolution_review_required: bool,
    benchmark_required: bool,
    refs_ready: bool,
    render_blocking_refs: bool,
    exact_route: dict[str, Any] | None,
    risks: list[str],
) -> list[str]:
    reasons: list[str] = []
    if niche in _REVIEW_REQUIRED_NICHES:
        reasons.append("review_required_niche")
    if render_blocking_refs:
        reasons.append("reference_render_blocking")
    elif not refs_ready:
        reasons.append("references_not_top_tier_ready")
    if graph_required:
        reasons.append("long_form_graph_benchmark_required")
    if dialogue_required:
        reasons.append("dialogue_lip_sync_benchmark_required")
    if niche_resolution_review_required:
        reasons.append("niche_resolution_ambiguous")
    if benchmark_required and not exact_route:
        reasons.append("route_not_promoted_by_benchmark_policy")
    if runtime_class in {"short_film", "episode"} and not exact_route:
        reasons.append("long_form_route_missing_two_approved_outputs")
    for risk in risks:
        if risk not in {"standard_prompt_adherence_and_motion_quality"}:
            reasons.append(str(risk))
    return list(dict.fromkeys(reasons))


def _launch_tier(
    *,
    niche: str,
    runtime_class: str,
    blocking_reasons: list[str],
    graph_required: bool,
) -> str:
    if "review_required_niche" in blocking_reasons:
        return "review_locked"
    if graph_required or runtime_class in {"short_film", "episode"}:
        return "benchmark_locked_long_form" if blocking_reasons else "long_form_launch_ready"
    if set(blocking_reasons).issubset({"route_not_promoted_by_benchmark_policy"}):
        return "launch_ready" if niche in _HIGH_READY_NICHES else "short_form_candidate"
    if blocking_reasons:
        return "qa_required"
    if niche in _HIGH_READY_NICHES:
        return "launch_ready"
    return "short_form_candidate"


def _auto_route_allowed(*, launch_tier: str, blocking_reasons: list[str]) -> bool:
    if launch_tier in {"launch_ready", "short_form_candidate"}:
        return True
    non_render_blocking = {"route_not_promoted_by_benchmark_policy"}
    return launch_tier == "qa_required" and set(blocking_reasons).issubset(non_render_blocking)


def _next_benchmark_batch(
    *,
    primary_model: str,
    niche: str,
    runtime_class: str,
    target_market: str,
    graph_required: bool,
    dialogue_required: bool,
    blocking_reasons: list[str],
) -> list[dict[str, Any]]:
    batch = [
        {
            "kind": "canonical_route",
            "model_key": primary_model,
            "niche": niche,
            "runtime_class": runtime_class,
            "target_market": target_market,
            "minimum_runs": 2,
            "evidence": [
                "real_output_url",
                "qa_score",
                "human_reviewer_notes",
                "cost_usd",
                "latency_s",
                "retry_count",
            ],
        }
    ]
    if graph_required:
        batch.append({
            "kind": "long_form_graph",
            "model_key": "production_graph_executor",
            "niche": niche,
            "runtime_class": runtime_class,
            "target_market": target_market,
            "minimum_runs": 2,
            "evidence": [
                "scene_memory_pack",
                "last_frame_handoffs",
                "failed_unit_retry_log",
                "assembly_qa",
            ],
        })
    if dialogue_required or any("dialogue" in reason for reason in blocking_reasons):
        batch.append({
            "kind": "dialogue_candidate",
            "model_key": "atlascloud/infinitetalk_or_multitalk",
            "niche": niche,
            "runtime_class": runtime_class,
            "target_market": target_market,
            "minimum_runs": 2,
            "evidence": [
                "localized_script",
                "lip_sync_score",
                "identity_stability",
                "audio_loudness",
                "human_dialogue_review",
            ],
        })
    return batch


def _operator_policy(launch_tier: str) -> list[str]:
    if launch_tier == "launch_ready":
        return [
            "allow autonomous short-form render when preflight passes",
            "do not claim top-tier until benchmark policy promotes the route",
        ]
    if launch_tier == "short_form_candidate":
        return [
            "allow autonomous render with QA warnings visible",
            "prioritize this route for the next paid benchmark batch",
        ]
    if launch_tier == "qa_required":
        return [
            "render only with QA/retry enabled",
            "surface missing references and route locks before paid render",
        ]
    if launch_tier == "review_locked":
        return [
            "allow planning preview",
            "require human review before public/commercial production use",
        ]
    return [
        "keep behind benchmark gate",
        "run graph/candidate benchmarks before default-on long-form routing",
    ]


__all__ = ["build_route_quality_scorecard"]
