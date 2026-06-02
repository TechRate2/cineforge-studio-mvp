"""Compact operator brief for the autonomous video agent.

This module intentionally composes the larger production audit instead of
inventing a second source of truth. It is the API-friendly answer to: what does
the system do today, where is it strong, and what still blocks top-tier claims?
"""
from __future__ import annotations

from typing import Any

from agent.atlas_model_integration_matrix import build_atlas_model_integration_matrix
from agent.autonomous_market_audit import build_autonomous_market_audit
from agent.autonomous_niche_audit import build_autonomous_niche_audit
from agent.autonomous_production_audit import build_autonomous_production_audit
from agent.autonomous_workflow_niche_guide import build_autonomous_workflow_niche_guide


def build_autonomous_operator_brief() -> dict[str, Any]:
    """Return the concise source-backed product/operator answer."""
    audit = build_autonomous_production_audit()
    operator = audit.get("operator_summary") or {}
    verdict = audit.get("executive_verdict") or {}
    launch = audit.get("niche_launch_matrix") or {}
    launch_tiers = launch.get("tiers") or {}
    atlas = build_atlas_model_integration_matrix()
    competitive = audit.get("competitive_research") or {}
    niche_audit = build_autonomous_niche_audit()
    market_audit = build_autonomous_market_audit()
    workflow_guide = build_autonomous_workflow_niche_guide()
    return {
        "schema_version": "cinejelly.autonomous_operator_brief.v1",
        "plain_answer": operator.get("plain_answer") or verdict.get("plain_answer"),
        "current_level": verdict.get("current_level"),
        "top_tier_proven": bool(verdict.get("top_tier_production_grade")),
        "top_app_comparison": {
            "verdict": "architecture_shape_close_but_not_output_proven",
            "matches_top_apps_on": [
                "autonomous-only intake",
                "planner/storyboard/director/editor skill chain",
                "Seedance 2.0 quad-modal reference routing",
                "niche and market playbook routing",
                "long-form graph and scene-memory architecture",
                "benchmark and promotion gates",
            ],
            "still_behind_top_apps_until": [
                "paid AtlasCloud outputs are attached for canonical niches",
                "5-10 minute graph-mode short films are accepted by reviewers",
                "model-backed identity, product, OCR, audio, and lip-sync QA gates pass",
                "dialogue/lipsync routes are benchmarked for VN and global markets",
                "asset library proves recurring character/product/location continuity",
            ],
            "claim_rule": "Do not market as top-tier parity until benchmark promotion evidence passes.",
        },
        "why_not_top_tier_yet": (audit.get("evidence_blocking_top_tier_claim") or {}).get(
            "why_not_top_tier_yet",
            [],
        ),
        "workflow": audit.get("workflow_in_one_run", []),
        "workflow_guide_summary": {
            "schema_version": workflow_guide.get("schema_version"),
            "current_position": workflow_guide.get("current_position", {}),
            "duration_strategy_count": len(workflow_guide.get("duration_strategy") or []),
            "workflow_step_count": len(workflow_guide.get("workflow_steps") or []),
        },
        "production_workflow_steps": audit.get("what_the_agent_does_today", []),
        "duration_policy": operator.get("duration_policy", []),
        "best_niches_now": audit.get("best_niches_now", []),
        "usable_with_more_qa": audit.get("usable_with_more_qa", []),
        "review_required_niches": audit.get("review_required_niches", []),
        "niche_fit_table": {
            "sell_first": launch_tiers.get("sell_first", []),
            "benchmark_next": launch_tiers.get("benchmark_next", []),
            "review_locked": launch_tiers.get("review_locked", []),
            "rule": "Sell short-form first, benchmark longer/dialogue/fact-heavy routes, and keep regulated or child-facing niches review-locked.",
        },
        "niche_audit_summary": niche_audit.get("summary", {}),
        "market_audit_summary": market_audit.get("summary", {}),
        "market_policy": operator.get("market_answer", {}),
        "market_localization_policy": market_audit.get("policy", {}),
        "user_input_guidance": operator.get("what_user_should_provide", []),
        "seedance_rules": audit.get("seedance_2_optimization_contract", []),
        "long_form_rule": audit.get("long_form_doctrine", {}),
        "model_policy": {
            "default_user_experience": (
                (audit.get("atlas_model_integration") or {}).get("verdict") or {}
            ).get("default_user_experience"),
            "primary_family": (
                (audit.get("atlas_model_integration") or {}).get("verdict") or {}
            ).get("primary_family"),
            "vn_dialogue_priority": (atlas.get("recommendation") or {}).get("vn_dialogue_priority", []),
            "cheap_experiment_priority": (atlas.get("recommendation") or {}).get("cheap_experiment_priority", []),
            "source_backed_model_rules": atlas.get("source_backed_model_rules", []),
            "promotion_gate": atlas.get("promotion_gate", {}),
        },
        "next_upgrade_order": [
            "run paid AtlasCloud benchmark manifest for sell-first niches",
            "attach output URLs, cost, latency, retry count, QA frames, reviewer scores, and notes",
            "benchmark InfiniteTalk/MultiTalk/lipsync repair for Vietnamese and global dialogue",
            "run CINEJELLY_ENABLE_GRAPH_LONG_FORM paid 5-10 minute graph jobs",
            "add model-backed identity/product/OCR/audio/lipsync QA before final assembly",
            "expand asset pins into full character/product/location/style/voice library",
        ],
        "research_position": {
            "closest_strength_today": competitive.get("closest_strength_today"),
            "largest_remaining_gap": competitive.get("largest_remaining_gap"),
            "implementation_score": competitive.get("implementation_score"),
            "patterns_to_apply_next": competitive.get("best_patterns_to_apply_next", []),
        },
        "next_actions": audit.get("next_build_order", []),
        "evidence_endpoints": [
            "/api/v1/director/autonomous/workflow-niche-guide",
            "/api/v1/director/autonomous/production-decision",
            "/api/v1/director/autonomous/production-audit",
            "/api/v1/director/autonomous/paid-benchmark-manifest",
            "/api/v1/director/autonomous/niche-playbook-catalog",
            "/api/v1/director/autonomous/market-audit",
            "/api/v1/director/autonomous/atlas-model-matrix",
            "/api/v1/director/autonomous/top-tier-completion-gate",
            "/api/v1/director/jobs/{job_id}/production-report",
            "/api/v1/director/jobs/{job_id}/benchmark-evidence-pack",
        ],
    }


__all__ = ["build_autonomous_operator_brief"]
