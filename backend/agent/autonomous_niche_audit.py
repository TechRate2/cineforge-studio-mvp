"""All-niche autonomous routing audit.

This turns the per-idea production-decision contract into a catalog-level
answer: which niches can run short-form automatically, which long-form routes
require graph execution, and where review/benchmark gates remain active.
"""
from __future__ import annotations

from typing import Any

from agent.autonomous_production_decision import build_autonomous_production_decision
from skills.niche_playbooks import list_niche_keys
from skills.niche_readiness import build_niche_readiness_matrix


_REFS_BY_READINESS: dict[str, dict[str, int]] = {
    "high": {"images": 3, "videos": 1, "audios": 1},
    "medium": {"images": 4, "videos": 1, "audios": 1},
    "review_required": {"images": 4, "videos": 2, "audios": 1},
}

_DIALOGUE_NICHES = {
    "documentary",
    "drama",
    "education",
    "finance_education",
    "medical_wellness",
}


def build_autonomous_niche_audit(
    *,
    include_long_form: bool = True,
    limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic niche x runtime audit without vendor calls."""
    readiness = build_niche_readiness_matrix()
    readiness_by_niche = {
        str(row.get("niche")): str(row.get("readiness") or "medium")
        for row in readiness.get("niches", [])
    }
    niches = list_niche_keys()
    if limit is not None:
        niches = niches[: max(1, int(limit))]

    short_rows = [
        _audit_one(niche=niche, duration_s=30, readiness=readiness_by_niche.get(niche, "medium"))
        for niche in niches
    ]
    long_rows = [
        _audit_one(niche=niche, duration_s=300, readiness=readiness_by_niche.get(niche, "medium"))
        for niche in niches
    ] if include_long_form else []
    all_rows = [*short_rows, *long_rows]

    return {
        "schema_version": "cinejelly.autonomous_niche_audit.v1",
        "summary": {
            "niche_count": len(niches),
            "short_auto_allowed": len([row for row in short_rows if row["auto_route_allowed"] and not row["blocked"]]),
            "short_review_required": len([row for row in short_rows if row["manual_review_required"]]),
            "long_graph_required": len([row for row in long_rows if row["graph_required"]]),
            "long_auto_allowed": len([row for row in long_rows if row["auto_route_allowed"] and not row["blocked"]]),
            "blocked": len([row for row in all_rows if row["blocked"]]),
            "top_tier_claim_allowed": any(row["top_tier_claim_allowed"] for row in all_rows),
        },
        "policy": {
            "short_rule": "30s routes may auto-route when refs, safety, and benchmark posture pass.",
            "long_rule": "5m routes must require graph execution and remain benchmark-gated until paid evidence is promoted.",
            "top_tier_rule": "No niche audit row may claim top-tier without promoted benchmark evidence.",
        },
        "short_30s": short_rows,
        "long_5m": long_rows,
    }


def _audit_one(*, niche: str, duration_s: int, readiness: str) -> dict[str, Any]:
    refs = dict(_REFS_BY_READINESS.get(readiness, _REFS_BY_READINESS["medium"]))
    if duration_s > 180:
        refs["pinned_assets"] = 1
    decision = build_autonomous_production_decision(
        user_idea=(
            f"{niche.replace('_', ' ')} autonomous benchmark production "
            "with clear visual proof and platform-native pacing"
        ),
        target_market="auto",
        target_platform="youtube_long" if duration_s > 180 else "tiktok",
        duration_hint_s=duration_s,
        reference_counts=refs,
        niche_hint=niche,
        speaker_count=2 if niche in _DIALOGUE_NICHES else 1,
    )
    d = decision.get("decision") or {}
    route = d.get("primary_model_route") or {}
    dialogue = d.get("dialogue_route_policy") or {}
    refs_report = decision.get("reference_sufficiency") or {}
    score = decision.get("route_quality_scorecard") or {}
    safety = decision.get("responsible_content_gate") or {}
    segment = decision.get("seedance_segment_inspector") or {}
    return {
        "niche": d.get("niche") or niche,
        "readiness": readiness,
        "duration_s": duration_s,
        "runtime_class": d.get("runtime_class"),
        "target_market": d.get("target_market"),
        "primary_visual_model": route.get("primary_visual_model"),
        "continuity_model": route.get("continuity_model"),
        "dialogue_route": dialogue.get("route_type"),
        "dialogue_candidate": dialogue.get("dialogue_candidate"),
        "post_process_candidate": dialogue.get("post_process_candidate"),
        "graph_required": bool(d.get("graph_required")),
        "dialogue_required": bool(d.get("dialogue_required")),
        "reference_status": refs_report.get("status"),
        "reference_score": refs_report.get("score"),
        "estimated_seedance_units": segment.get("estimated_total_units"),
        "auto_route_allowed": bool(score.get("auto_route_allowed")),
        "top_tier_claim_allowed": bool(score.get("top_tier_claim_allowed")),
        "manual_review_required": bool(
            safety.get("manual_review_required")
            or d.get("responsible_review_required")
        ),
        "blocked": bool(
            safety.get("render_allowed") is False
            or d.get("render_blocked_by_responsible_gate")
        ),
    }


__all__ = ["build_autonomous_niche_audit"]
