"""Production readiness report for CineJelly Autonomous Director.

This report answers the product question directly: is the current source at a
top-tier autonomous video-agent level, and where is it strong or incomplete?
It composes existing contracts instead of duplicating the workflow logic.
"""
from __future__ import annotations

from typing import Any

from agent.autonomous_benchmark_suite import build_autonomous_benchmark_contract
from agent.autonomous_workflow_contract import build_autonomous_workflow_contract
from agent.benchmark_promotion_policy import build_benchmark_promotion_policy
from core import autonomous_benchmark_store, autonomous_asset_pins
from skills.niche_readiness import build_niche_readiness_matrix


def build_autonomous_readiness_report() -> dict[str, Any]:
    """Return source-backed production readiness diagnostics."""
    capabilities = build_niche_readiness_matrix()
    workflow = build_autonomous_workflow_contract()
    benchmark = build_autonomous_benchmark_contract()
    benchmark_stats = autonomous_benchmark_store.stats()
    promotion_policy = build_benchmark_promotion_policy()
    pin_stats = autonomous_asset_pins.stats()

    summary = capabilities["summary"]
    runtime_support = capabilities["runtime_support"]
    gaps = workflow["production_gaps"]
    high_niches = [
        row["niche"] for row in capabilities["niches"]
        if row.get("readiness") == "high"
    ]
    medium_niches = [
        row["niche"] for row in capabilities["niches"]
        if row.get("readiness") == "medium"
    ]
    review_niches = [
        row["niche"] for row in capabilities["niches"]
        if row.get("readiness") == "review_required"
    ]

    short_form_ready = summary["high_readiness"] >= 8 and summary["benchmark_coverage_ok"]
    long_form_ready = all(
        item.get("production_status") in {"strong_candidate", "strong_candidate_with_qa"}
        for item in workflow["runtime_strategy"]
        if item.get("class") in {"short", "sequence"}
    )
    top_tier_blockers = [
        gap["gap"]
        for gap in gaps
        if gap["gap"] in {
            "true_graph_executor",
            "real_benchmark_outputs",
            "strong_visual_audio_qa",
        }
    ]
    if int(benchmark_stats.get("total_results") or 0) == 0:
        top_tier_blockers.append("no_stored_benchmark_results")
    top_tier = not top_tier_blockers

    return {
        "schema_version": "cinejelly.autonomous_readiness.v1",
        "verdict": {
            "top_tier_production_grade": top_tier,
            "current_level": (
                "strong_autonomous_short_form_foundation"
                if short_form_ready else "autonomous_foundation_needs_more_coverage"
            ),
            "short_form_status": (
                "competitive_candidate_for_ugc_product_social"
                if short_form_ready else "needs_more_niche_benchmarking"
            ),
            "long_form_status": (
                "graph_executor_flagged_needs_paid_benchmarks"
                if long_form_ready else "needs_runtime_contract_and_executor"
            ),
            "why_not_top_tier_yet": [
                "Benchmark contract/store/runner exist, but no paid vendor outputs prove quality per niche/market/model yet.",
                "Long-form graph executor primitives, persisted DirectorPlan artifacts, paid per-shot handlers, strong graph QA, assembly handlers, and auditable continuity handoff policy exist; /director/autonomous can route long-form jobs through graph_executor_long_form when CINEJELLY_ENABLE_GRAPH_LONG_FORM=1, but default-on production still needs paid benchmarks.",
                "Approved asset pins can be created from uploaded /studio refs, selected for generation, auto-selected for render by niche/market/series/priority when enabled, and managed with active/paused/archived, role/priority, and series/campaign filtering/assignment; market/niche metadata editing, batch cleanup, and dedicated library organization are still missing.",
                "Pre-render producer story critic now scores hook clarity, story causality, payoff, niche proof, market fit, and reference intent; screenplay scene lint catches missing long-form purpose/conflict/turning point/continuity/handoff; continuity handoff policy catches missing previous-frame chains for adjacent shots that share character/product/reference anchors; Seedance shot lint catches overlong shots, generic/missing subject-action-camera-setting-audio fields, and overloaded multi-action shots before paid render; deterministic strong_quality_gate catches duration/audio presence/loudness/silence/reference/caption/semantic hard failures and can use optional OCR text-artifact plus visual reference similarity probes, but embedding/robust OCR/lip-sync gates still need model-backed validation.",
            ],
        },
        "coverage": {
            "supported_niches": summary["supported_niches"],
            "high_readiness": summary["high_readiness"],
            "medium_readiness": summary["medium_readiness"],
            "review_required": summary["review_required"],
            "benchmark_case_count": benchmark["summary"]["case_count"],
            "benchmark_vendor_outputs_required": benchmark["summary"]["vendor_render_required_for_production_claim"],
            "benchmark_result_stats": benchmark_stats,
            "benchmark_promotion_policy": promotion_policy,
            "asset_pin_stats": pin_stats,
            "markets": capabilities["market_support"],
            "runtime_support": runtime_support,
        },
        "best_current_use_cases": [
            {
                "category": "UGC/product/social ads",
                "niches": ["ugc_review", "ecommerce_catalog", "tech", "app_saas"],
                "reason": "clear proof-driven structure, strong reference use, short runtime fit.",
            },
            {
                "category": "beauty/fashion/food/lifestyle",
                "niches": ["beauty", "fashion", "food", "lifestyle", "asmr"],
                "reason": "Seedance 2.0 Reference/Fast Reference is well-suited to macro texture, product identity, and sensory hooks.",
            },
            {
                "category": "short narrative/micro-film",
                "niches": ["drama", "anime_comic", "music_video"],
                "reason": "storyboard and screenplay planning exist; needs stronger benchmark clips before premium claims.",
            },
        ],
        "niche_groups": {
            "high_readiness": high_niches,
            "medium_readiness": medium_niches,
            "review_required": review_niches,
        },
        "production_gaps": gaps,
        "next_build_order": [
            {
                "priority": "P0",
                "item": "graph_executor",
                "outcome": "Run long-form benchmark jobs with CINEJELLY_ENABLE_GRAPH_LONG_FORM=1, then promote graph executor loop as the default path after validation.",
            },
            {
                "priority": "P0",
                "item": "benchmark_result_store",
                "outcome": "Use the benchmark runner to attach real AtlasCloud video outputs, costs, latency, QA frames, and reviewer ratings to each benchmark case.",
            },
            {
                "priority": "P1",
                "item": "asset_pin_management_ui",
                "outcome": "Extend current /studio pin status/role/priority/series controls with market/niche metadata editing, batch cleanup, location/voice anchors, and dedicated Asset Library organization.",
            },
            {
                "priority": "P1",
                "item": "model_candidate_benchmarks",
                "outcome": "InfiniteTalk, MMAudio, LipSync, OmniHuman, and Instant Character route only after benchmark_promotion_policy marks the model/niche/runtime route eligible.",
            },
            {
                "priority": "P1",
                "item": "stronger_visual_audio_qa",
                "outcome": "Add embedding identity/product checks, robust multilingual visible-text artifact detection, and lip-sync alignment on top of screenplay scene lint, Seedance shot lint, and deterministic strong_quality_gate.",
            },
        ],
        "evidence_endpoints": [
            "/api/v1/director/autonomous/workflow",
            "/api/v1/director/autonomous/production-decision",
            "/api/v1/director/autonomous/benchmarks",
            "/api/v1/director/autonomous/benchmarks/plan",
            "/api/v1/director/autonomous/capabilities",
            "/api/v1/director/jobs/{job_id}/artifact",
            "/api/v1/director/jobs/{job_id}/production-graph",
        ],
    }


__all__ = ["build_autonomous_readiness_report"]
