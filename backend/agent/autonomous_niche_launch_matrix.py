"""Launch and benchmark matrix by niche.

This answers the practical product question: which niches can CineJelly sell
first, which need QA/benchmarks, which require human review, and what duration
range/reference contract is realistic before top-tier claims.
"""
from __future__ import annotations

from typing import Any

from agent.autonomous_capability_matrix import build_autonomous_capability_matrix
from agent.autonomous_competitive_research import build_autonomous_competitive_research


_SELL_FIRST = {
    "ugc_review",
    "beauty",
    "food",
    "ecommerce_catalog",
    "fashion",
    "app_saas",
    "tech",
    "asmr",
    "lifestyle",
}

_REVIEW_LOCKED = {"finance_education", "medical_wellness", "kids_family", "documentary"}


def build_autonomous_niche_launch_matrix() -> dict[str, Any]:
    """Return source-backed launch fit, duration envelope, and proof gaps."""
    capability = build_autonomous_capability_matrix()
    research = build_autonomous_competitive_research()
    rows = [_launch_row(row) for row in capability.get("niches", [])]
    tiers = {
        "sell_first": [r["niche"] for r in rows if r["launch_tier"] == "sell_first"],
        "benchmark_next": [r["niche"] for r in rows if r["launch_tier"] == "benchmark_next"],
        "review_locked": [r["niche"] for r in rows if r["launch_tier"] == "review_locked"],
    }
    return {
        "schema_version": "cinejelly.autonomous_niche_launch_matrix.v1",
        "summary": {
            "niche_count": len(rows),
            "sell_first_count": len(tiers["sell_first"]),
            "benchmark_next_count": len(tiers["benchmark_next"]),
            "review_locked_count": len(tiers["review_locked"]),
            "top_tier_claim_allowed": False,
            "reason": (
                "Launch fit is source-backed, but top-tier claim still needs real benchmark "
                "outputs and model-backed QA evidence."
            ),
        },
        "tiers": tiers,
        "rows": rows,
        "proof_policy": {
            "can_sell_now": (
                "Only sell first-tier short-form as an autonomous production candidate; "
                "show benchmark-gate status honestly."
            ),
            "can_claim_top_tier_when": [
                "two approved real AtlasCloud outputs per niche/runtime/model route",
                "reviewer notes and QA score stored",
                "cost/latency/retry count stored",
                "identity/product/audio/lip-sync evidence passes route policy",
            ],
            "competitive_research_score": (research.get("implementation_score") or {}).get("score"),
        },
    }


def _launch_row(row: dict[str, Any]) -> dict[str, Any]:
    niche = str(row.get("niche") or "ugc_review")
    readiness = str(row.get("readiness") or "medium")
    runtime_routes = list(row.get("runtime_routes") or [])
    short = _route_for(runtime_routes, "short") or (runtime_routes[0] if runtime_routes else {})
    short_film = _route_for(runtime_routes, "short_film") or {}
    ref_contract = row.get("recommended_reference_contract") or {}
    tier = _launch_tier(niche, readiness)
    max_default_duration = _max_default_duration_s(tier)
    graph_after = (row.get("long_form_policy") or {}).get("graph_required_after_s")
    return {
        "niche": niche,
        "launch_tier": tier,
        "readiness": readiness,
        "best_for": row.get("best_for"),
        "default_user_promise": _user_promise(niche, tier),
        "best_runtime_today": _best_runtime_today(tier),
        "max_default_duration_s": max_default_duration,
        "long_form_status": _long_form_status(tier, graph_after),
        "primary_visual_model": short.get("primary_visual_model") or "seedance_2_0_fast_ref",
        "continuity_model": short.get("continuity_model") or "seedance_2_0_fast_i2v",
        "short_form_reference_status": short.get("reference_status"),
        "short_film_reference_status": short_film.get("reference_status"),
        "reference_contract": {
            "minimum": ref_contract.get("minimum"),
            "optimal": ref_contract.get("optimal"),
            "policy": ref_contract.get("policy"),
        },
        "hook_moves": row.get("hook_moves", [])[:3],
        "camera": row.get("camera", [])[:4],
        "audio": row.get("audio"),
        "benchmark_before": _benchmark_before(niche, tier),
        "risk_controls": _risk_controls(niche, tier),
        "operator_action": _operator_action(tier),
    }


def _route_for(routes: list[dict[str, Any]], runtime_class: str) -> dict[str, Any] | None:
    for route in routes:
        if route.get("runtime_class") == runtime_class:
            return route
    return None


def _launch_tier(niche: str, readiness: str) -> str:
    if niche in _REVIEW_LOCKED or readiness == "review_required":
        return "review_locked"
    if niche in _SELL_FIRST and readiness == "high":
        return "sell_first"
    return "benchmark_next"


def _best_runtime_today(tier: str) -> str:
    if tier == "sell_first":
        return "15-60s autonomous short-form"
    if tier == "benchmark_next":
        return "15-180s with visible QA and benchmark plan"
    return "planning preview only until review"


def _max_default_duration_s(tier: str) -> int:
    if tier == "sell_first":
        return 60
    if tier == "benchmark_next":
        return 180
    return 0


def _long_form_status(tier: str, graph_after: Any) -> str:
    if tier == "review_locked":
        return "planning_only_until_safety_or_claim_review"
    if graph_after:
        return "graph_required_and_benchmark_gated"
    return "short_form_first"


def _user_promise(niche: str, tier: str) -> str:
    if tier == "sell_first":
        if niche in {"beauty", "food", "fashion", "ecommerce_catalog"}:
            return "one-click product/social video with strong visual proof and reference consistency"
        if niche in {"app_saas", "tech"}:
            return "one-click feature/demo video with clear problem-result proof"
        return "one-click short-form video with hook, refs, caption, and QA metadata"
    if tier == "benchmark_next":
        return "agent can plan and render with QA, but premium claim requires benchmark evidence"
    return "agent can draft the plan; public/commercial output needs human review"


def _benchmark_before(niche: str, tier: str) -> list[str]:
    if tier == "sell_first":
        return ["top-tier marketing claim", "long-form default routing", "new model promotion"]
    if tier == "benchmark_next":
        return ["default autonomous sale", "premium quality claim", "long-form routing"]
    checks = ["public output", "commercial claims", "automated publish"]
    if niche in {"finance_education", "medical_wellness"}:
        checks.append("claim/fact/script approval")
    if niche == "kids_family":
        checks.append("child-safety review")
    return checks


def _risk_controls(niche: str, tier: str) -> list[str]:
    controls = ["preflight", "Seedance shot lint", "reference sufficiency", "QA/retry"]
    if tier != "sell_first":
        controls.append("human or benchmark review")
    if niche in {"drama", "documentary"}:
        controls.extend(["scene memory", "handoff images", "story critic"])
    if niche in {"finance_education", "medical_wellness"}:
        controls.extend(["claims safety", "no personalized advice"])
    if niche == "kids_family":
        controls.append("child-safe framing")
    return list(dict.fromkeys(controls))


def _operator_action(tier: str) -> str:
    if tier == "sell_first":
        return "Use for launch demos and first paid benchmark runs; keep top-tier badge gated."
    if tier == "benchmark_next":
        return "Run benchmark plan first and surface QA warnings in UI."
    return "Keep in preview/review mode; do not auto-publish."


__all__ = ["build_autonomous_niche_launch_matrix"]
