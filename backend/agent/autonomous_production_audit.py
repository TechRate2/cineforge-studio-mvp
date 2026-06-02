"""Source-backed production audit for CineJelly Autonomous Agent.

This is the compact answer to: "Is the project top-tier yet, how does the
workflow work, which niches are strong, and what must improve next?"  It
composes existing contracts instead of inventing a separate truth.
"""
from __future__ import annotations

from typing import Any

from agent.autonomous_capability_matrix import build_autonomous_capability_matrix
from agent.autonomous_competitive_research import build_autonomous_competitive_research
from agent.autonomous_niche_launch_matrix import build_autonomous_niche_launch_matrix
from agent.autonomous_niche_playbook_catalog import build_autonomous_niche_playbook_catalog
from agent.autonomous_paid_benchmark_manifest import build_autonomous_paid_benchmark_manifest
from agent.autonomous_readiness_report import build_autonomous_readiness_report
from agent.autonomous_top_tier_completion_gate import build_autonomous_top_tier_completion_gate
from agent.autonomous_upgrade_recommendations import build_autonomous_upgrade_recommendations
from agent.autonomous_workflow_contract import build_autonomous_workflow_contract
from agent.atlas_model_integration_matrix import build_atlas_model_integration_matrix
from agent.benchmark_review_rubric import build_benchmark_review_rubric


def build_autonomous_production_audit() -> dict[str, Any]:
    """Return an audit suitable for UI/admin review and regression tests."""
    readiness = build_autonomous_readiness_report()
    workflow = build_autonomous_workflow_contract()
    recommendations = build_autonomous_upgrade_recommendations()
    matrix = build_autonomous_capability_matrix()
    research = build_autonomous_competitive_research()
    launch_matrix = build_autonomous_niche_launch_matrix()
    playbook_catalog = build_autonomous_niche_playbook_catalog()
    paid_manifest = build_autonomous_paid_benchmark_manifest(limit=9)
    atlas_models = build_atlas_model_integration_matrix()
    review_rubric = build_benchmark_review_rubric(niche="ugc_review", runtime_class="short", target_market="vn", has_dialogue=True)
    top_tier_gate = build_autonomous_top_tier_completion_gate()
    verdict = readiness.get("verdict") or {}
    coverage = readiness.get("coverage") or {}
    pipeline = workflow.get("pipeline") or []
    return {
        "schema_version": "cinejelly.autonomous_production_audit.v1",
        "executive_verdict": {
            "top_tier_production_grade": bool(verdict.get("top_tier_production_grade")),
            "current_level": verdict.get("current_level"),
            "short_form_status": verdict.get("short_form_status"),
            "long_form_status": verdict.get("long_form_status"),
            "plain_answer": (
                "Strong autonomous short-form foundation with credible long-form architecture, "
                "but not top-tier proven until real AtlasCloud benchmark outputs are stored and promoted."
            ),
        },
        "what_the_agent_does_today": [
            _stage_summary(stage)
            for stage in pipeline
        ],
        "operator_summary": _operator_summary(
            verdict=verdict,
            matrix=matrix,
            launch_matrix=launch_matrix,
            recommendations=recommendations,
        ),
        "workflow_in_one_run": [
            "ingest idea, target market/runtime, image/video/audio refs, and approved memory pins",
            "infer market, niche, hook, runtime class, and creative treatment",
            "assign image/video/audio references to Seedance-compatible production jobs",
            "write storyboard, screenplay scenes for long-form, and director shot list",
            "run preflight gates for story, niche fit, Seedance shot contract, references, scenes, continuity, and safety",
            "route internally across Seedance 2.0 Fast/Reference/i2v/t2v and benchmark-locked dialogue candidates",
            "render 4-15s shots, preserve last-frame/scene memory handoffs, QA clips, retry failed shots, assemble final MP4",
            "return final video, captions, hashtags, production graph, QA, benchmark evidence draft, and result modal metadata",
        ],
        "best_niches_now": matrix.get("best_today", []),
        "usable_with_more_qa": matrix.get("usable_with_more_qa", []),
        "review_required_niches": matrix.get("review_required", []),
        "niche_launch_matrix": {
            "summary": launch_matrix.get("summary", {}),
            "tiers": launch_matrix.get("tiers", {}),
            "proof_policy": launch_matrix.get("proof_policy", {}),
        },
        "niche_playbook_catalog": {
            "summary": playbook_catalog.get("summary", {}),
            "duration_templates": playbook_catalog.get("duration_templates", []),
            "global_doctrine": playbook_catalog.get("global_doctrine", []),
        },
        "long_form_doctrine": {
            "rule": "Never ask one video model to produce a 5-30 minute film in one call.",
            "source_status": recommendations.get("long_form_rule", {}).get("source_status", []),
            "implementation": [
                "screenplay first",
                "act/scene/chunk decomposition",
                "4-15s Seedance render units",
                "scene memory pack",
                "dynamic keyframe memory bank from accepted outputs",
                "previous-frame handoffs",
                "production graph leases/retries",
                "QA before assembly",
            ],
            "memory_contract": {
                "schema_version": "cinejelly.dynamic_keyframe_memory.v1",
                "write_after": "shot QA passes or is explicitly accepted",
                "read_into": "later shot prompts, scene bridge prompts, and retry prompts",
                "claim_status": "planned_contract_needs_paid_render_population",
            },
        },
        "input_upgrade_policy": workflow.get("input_upgrade_policy", {}),
        "seedance_2_optimization_contract": matrix.get("seedance_2_best_practices", []),
        "market_policy": matrix.get("market_policy", {}),
        "evidence_blocking_top_tier_claim": {
            "benchmark_results": (coverage.get("benchmark_result_stats") or {}).get("total_results"),
            "promoted_routes": ((coverage.get("benchmark_promotion_policy") or {}).get("summary") or {}).get("promoted_route_count"),
            "required_evidence": matrix.get("evidence_required_before_top_tier", []),
            "why_not_top_tier_yet": verdict.get("why_not_top_tier_yet", []),
        },
        "competitive_research": {
            "implementation_score": research.get("implementation_score"),
            "closest_strength_today": (research.get("research_position") or {}).get("closest_strength_today"),
            "largest_remaining_gap": (research.get("research_position") or {}).get("largest_remaining_gap"),
            "best_patterns_to_apply_next": research.get("best_patterns_to_apply_next", []),
        },
        "top_tier_maturity_ladder": recommendations.get("top_tier_maturity_ladder", []),
        "atlas_model_integration": {
            "verdict": atlas_models.get("verdict", {}),
            "recommendation": atlas_models.get("recommendation", {}),
            "lane_policy": atlas_models.get("lane_policy", {}),
            "promotion_gate": atlas_models.get("promotion_gate", {}),
        },
        "top_tier_completion_gate": {
            "verdict": top_tier_gate.get("verdict", {}),
            "next_proof_order": top_tier_gate.get("next_proof_order", []),
        },
        "paid_benchmark_manifest": {
            "summary": paid_manifest.get("summary", {}),
            "first_run": (paid_manifest.get("runs") or [None])[0],
        },
        "benchmark_review_rubric": {
            "schema_version": review_rubric.get("schema_version"),
            "promotion_thresholds": review_rubric.get("promotion_thresholds", {}),
            "dimension_count": len(review_rubric.get("dimensions") or []),
            "reviewer_note_template": review_rubric.get("reviewer_note_template"),
        },
        "external_patterns_to_keep_matching": research.get("patterns", []),
        "external_sources_reviewed": research.get("sources", []),
        "next_build_order": readiness.get("next_build_order", []),
        "acceptance_gates": [
            "Each canonical niche has at least one real vendor output URL attached to benchmark storage.",
            "Routes are promoted only when human reviewer notes, QA score, cost, latency, and retry count are present.",
            "Long-form graph executor is benchmarked with paid handlers before default-on production routing.",
            "Identity/product/reference adherence and lip-sync checks are model-backed, not just deterministic placeholders.",
            "User-facing UI remains autonomous-only; experimental model selection stays internal/admin-only.",
        ],
    }


def _stage_summary(stage: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": stage.get("id"),
        "agent_role": stage.get("agent_role"),
        "output": stage.get("output", []),
        "quality_gate": stage.get("quality_gate", []),
        "status": stage.get("status"),
    }


def _operator_summary(
    *,
    verdict: dict[str, Any],
    matrix: dict[str, Any],
    launch_matrix: dict[str, Any],
    recommendations: dict[str, Any],
) -> dict[str, Any]:
    return {
        "plain_answer": (
            "CineJelly is architecturally close to a top autonomous Seedance 2.0 "
            "production agent for short-form work, but it is not evidence-proven "
            "at the level of the strongest production apps until paid benchmark "
            "outputs, graph long-form runs, and model-backed QA are promoted."
        ),
        "current_strength": {
            "level": verdict.get("current_level"),
            "best_fit": "15-60s autonomous UGC/product/social videos with clear visual references",
            "why": [
                "one-click UI hides model and shot settings",
                "niche/market/playbook routing is deterministic before vendor spend",
                "Seedance 2.0 refs are assigned explicit image/video/audio jobs",
                "segment inspector previews 4-15s Seedance units before render",
                "input upgrade plan tells users what improves quality without manual controls",
            ],
        },
        "duration_policy": [
            {
                "duration": "15-60s",
                "status": "strongest_current_fit",
                "method": "1-5 Seedance units with hook, proof/demo, payoff, QA, and assembly",
            },
            {
                "duration": "60-180s",
                "status": "usable_with_more_qa",
                "method": "micro-film structure with scene memory, reference handoffs, and retryable shots",
            },
            {
                "duration": "5-10m",
                "status": "benchmark_gated",
                "method": "screenplay -> acts -> scenes -> chunks -> 4-15s graph nodes -> QA -> assembly",
            },
            {
                "duration": "10-30m",
                "status": "research_gated",
                "method": "episode graph with asset library, act checkpoints, dialogue lanes, cost ceilings, and resumable leases",
            },
        ],
        "niche_answer": {
            "sell_first": (launch_matrix.get("tiers") or {}).get("sell_first", []),
            "benchmark_next": (launch_matrix.get("tiers") or {}).get("benchmark_next", []),
            "review_locked": (launch_matrix.get("tiers") or {}).get("review_locked", []),
            "best_today": matrix.get("best_today", []),
            "usable_with_more_qa": matrix.get("usable_with_more_qa", []),
            "review_required": matrix.get("review_required", []),
        },
        "what_user_should_provide": [
            {
                "case": "short_product_or_ugc",
                "ideal_inputs": ["one product/creator image", "one product detail/style image", "optional motion/audio ref"],
            },
            {
                "case": "beauty_food_fashion",
                "ideal_inputs": ["macro/product image refs", "style/lighting image", "SFX/beat ref for sensory timing"],
            },
            {
                "case": "real_estate_travel_restaurant",
                "ideal_inputs": ["environment/location images", "walkthrough or camera-motion video", "ambience audio if available"],
            },
            {
                "case": "drama_or_long_form",
                "ideal_inputs": ["character face/outfit image", "location/style image", "approved pins", "voice/dialogue sample when speech matters"],
            },
            {
                "case": "localized_vietnamese_dialogue",
                "ideal_inputs": ["short clean voice sample", "speaker count", "market VN", "benchmark/review before top-tier claim"],
            },
        ],
        "market_answer": {
            "default": "Auto should remain the default.",
            "why": "The agent can infer market from idea/refs, while optional VN/US/JP/KR/Global override helps script, proof style, dialogue, captions, props, and safety tone.",
            "ui_rule": "Expose market as a light override only; do not make users pick model, aspect, shot count, or Seedance parameters.",
        },
        "next_proof_order": recommendations.get("top_tier_maturity_ladder", []),
    }


__all__ = ["build_autonomous_production_audit"]
