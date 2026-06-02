"""Top-tier completion gate for CineJelly Autonomous Agent.

This module is deliberately stricter than readiness summaries. It answers:
"Can we honestly claim parity with the best autonomous video/short-drama apps?"
The answer must be evidence-backed, not based on architecture alone.
"""
from __future__ import annotations

from typing import Any

from agent.atlas_model_integration_matrix import build_atlas_model_integration_matrix
from agent.autonomous_niche_launch_matrix import build_autonomous_niche_launch_matrix
from agent.autonomous_niche_playbook_catalog import build_autonomous_niche_playbook_catalog
from agent.benchmark_promotion_policy import build_benchmark_promotion_policy
from core import autonomous_benchmark_store, autonomous_asset_pins


def build_autonomous_top_tier_completion_gate() -> dict[str, Any]:
    """Return a requirement-by-requirement top-tier completion audit."""
    launch = build_autonomous_niche_launch_matrix()
    playbooks = build_autonomous_niche_playbook_catalog()
    atlas = build_atlas_model_integration_matrix()
    promotion = build_benchmark_promotion_policy()
    benchmark_stats = autonomous_benchmark_store.stats()
    pin_stats = autonomous_asset_pins.stats()

    requirements = [
        _req(
            "autonomous_only_user_experience",
            "User can stay in one-click autonomous mode; model/manual knobs are internal.",
            "passed",
            [
                "Studio is autonomous-only after manual Video Agent cleanup.",
                "Atlas model matrix recommends keep_ui_model_picker=false.",
            ],
            evidence={
                "default_route": (atlas.get("recommendation") or {}).get("default_route"),
                "keep_ui_model_picker": (atlas.get("recommendation") or {}).get("keep_ui_model_picker"),
            },
        ),
        _req(
            "all_niche_directing_system",
            "Every supported niche has script, visual, reference, duration, prompt, QA, and launch guidance.",
            "passed" if (playbooks.get("summary") or {}).get("niche_count", 0) >= 20 else "failed",
            [
                "Niche playbook catalog covers 23 niches and short through episode durations.",
                "Launch matrix separates sell-first, benchmark-next, and review-locked niches.",
            ],
            evidence={
                "niche_count": (playbooks.get("summary") or {}).get("niche_count"),
                "sell_first_count": (launch.get("summary") or {}).get("sell_first_count"),
                "review_locked_count": (launch.get("summary") or {}).get("review_locked_count"),
            },
        ),
        _req(
            "seedance_2_quad_modal_workflow",
            "Seedance is used as a reference-first visual director with image/video/audio roles.",
            "passed",
            [
                "Prompt contracts use reference jobs, timeline, environment, style, subject/action, camera/sound, and constraints.",
                "Reference caps and roles are explicit: images for identity/product/style, videos for motion/camera, audio for rhythm/SFX/dialogue.",
            ],
            evidence={
                "seedance_caps": {"images": 9, "videos": 3, "audios": 3, "mixed_total": 12},
                "default_route": (atlas.get("recommendation") or {}).get("default_route"),
                "premium_route": (atlas.get("recommendation") or {}).get("premium_route"),
            },
        ),
        _req(
            "long_form_scene_graph_execution",
            "5-30m videos are decomposed into screenplay, scenes, chunks, 4-15s units, handoffs, QA, and assembly.",
            "partial",
            [
                "Scene graph, scene memory, previous-frame handoff, and graph executor contracts exist.",
                "Default long-form claim is still benchmark-gated until paid graph runs prove continuity, retry, and assembly quality.",
            ],
            blockers=["paid_graph_executor_benchmark_missing", "default_long_form_route_not_promoted"],
            evidence={
                "duration_templates": playbooks.get("duration_templates", []),
                "long_form_policy": "graph_required_and_benchmark_gated",
            },
        ),
        _req(
            "real_benchmark_evidence",
            "Routes have real AtlasCloud outputs, cost, latency, QA score, reviewer notes, and retry evidence.",
            "passed" if int(benchmark_stats.get("total_results") or 0) > 0 and int((promotion.get("summary") or {}).get("promoted_route_count") or 0) > 0 else "failed",
            [
                "Benchmark store, evidence validator, runner, planner, and promotion policy exist.",
                "Current local evidence does not prove top-tier unless real outputs have been stored and routes promoted.",
            ],
            blockers=["no_promoted_routes"] if int((promotion.get("summary") or {}).get("promoted_route_count") or 0) == 0 else [],
            evidence={
                "benchmark_results": benchmark_stats.get("total_results"),
                "promoted_routes": (promotion.get("summary") or {}).get("promoted_route_count"),
                "required_fields": (promotion.get("criteria") or {}).get("required_evidence_keys"),
            },
        ),
        _req(
            "model_backed_quality_control",
            "Identity, product, visual coherence, text artifacts, audio, and lip-sync are checked after render.",
            "partial",
            [
                "Deterministic preflight, Seedance shot lint, screenplay lint, story critic, strong quality gate, and artifact evidence draft exist.",
                "Robust model-backed identity/product/lip-sync/video critique still needs to run on real outputs before top-tier claims.",
            ],
            blockers=["model_backed_identity_product_lipsync_qa_missing"],
            evidence={
                "qa_needed": [
                    "visual embedding identity/product checks",
                    "lip-sync/phoneme scoring",
                    "multilingual OCR/text artifact detection",
                    "model-backed story and thumbnail critique",
                ]
            },
        ),
        _req(
            "dialogue_and_vietnamese_route",
            "Vietnamese/global dialogue can be routed through benchmarked speech/lip-sync lanes.",
            "partial",
            [
                "Wan 2.7 narrow fallback exists for short driven-audio inserts.",
                "InfiniteTalk, MultiTalk, and LipSync are prioritized but benchmark-locked.",
            ],
            blockers=["infinitetalk_multitalk_lipsync_benchmarks_missing"],
            evidence={
                "vn_dialogue_priority": (atlas.get("recommendation") or {}).get("vn_dialogue_priority"),
            },
        ),
        _req(
            "asset_memory_for_series_consistency",
            "Reusable characters, products, locations, voice, and style can persist across jobs.",
            "partial",
            [
                "Approved image asset pins, roles, priorities, market/series filtering, and auto-selection exist.",
                "Dedicated library UX and richer metadata for location/voice/style still need expansion.",
            ],
            blockers=["location_voice_style_library_incomplete"],
            evidence={
                "asset_pin_stats": pin_stats,
            },
        ),
        _req(
            "competitive_research_alignment",
            "Architecture follows current best patterns: storyboard, scene graph, shot-list prompting, references, and benchmark promotion.",
            "passed",
            [
                "External research pattern is aligned with Jellyfish, storyboard-driven long video papers, Seedance prompt guides, and event/scene graph systems.",
                "Source now exposes workflow, launch matrix, playbook catalog, Atlas model matrix, readiness, and production audit endpoints.",
            ],
            evidence={
                "source_backed_endpoints": [
                    "/api/v1/director/autonomous/workflow",
                    "/api/v1/director/autonomous/readiness",
                    "/api/v1/director/autonomous/niche-launch-matrix",
                    "/api/v1/director/autonomous/niche-playbook-catalog",
                    "/api/v1/director/autonomous/atlas-model-matrix",
                    "/api/v1/director/autonomous/production-audit",
                ],
            },
        ),
    ]

    failed = [r for r in requirements if r["status"] == "failed"]
    partial = [r for r in requirements if r["status"] == "partial"]
    return {
        "schema_version": "cinejelly.autonomous_top_tier_completion_gate.v1",
        "verdict": {
            "top_app_parity_proven": not failed and not partial,
            "current_level": "strong_architecture_not_yet_evidence_proven",
            "plain_answer": (
                "The source now has a strong autonomous director architecture, but it is not proven "
                "top-tier until paid AtlasCloud benchmark outputs, model-backed QA, dialogue evidence, "
                "and long-form graph runs are stored and promoted."
            ),
            "passed_count": len([r for r in requirements if r["status"] == "passed"]),
            "partial_count": len(partial),
            "failed_count": len(failed),
        },
        "requirements": requirements,
        "next_proof_order": [
            "Run two paid AtlasCloud outputs for each sell-first niche on Seedance 2.0 Fast Reference.",
            "Run premium Seedance 2.0 Reference hero-shot benchmarks for beauty, food, fashion, and ecommerce.",
            "Run one 3m and one 5m graph-executor benchmark with scene memory, handoffs, QA/retry, and assembly evidence.",
            "Benchmark InfiniteTalk, MultiTalk, and LipSync on Vietnamese and English dialogue inserts.",
            "Attach model-backed identity/product/lip-sync QA evidence and reviewer notes to benchmark rows.",
            "Promote only routes that pass benchmark_promotion_policy for the same model/niche/runtime/market.",
        ],
        "external_research_alignment": [
            {
                "source": "Seedance 2.0 prompt/reference guides",
                "pattern": "structured shot prompts plus image/video/audio reference roles",
                "source_url": "https://www.seedance.tv/blog/seedance-2-0-prompt-guide",
            },
            {
                "source": "Jellyfish AI Short Drama Studio",
                "pattern": "script to storyboard to consistency management to shot generation/export",
                "source_url": "https://github.com/Forget-C/Jellyfish",
            },
            {
                "source": "DrawVideo",
                "pattern": "storyboard/keyframe-guided long-video generation",
                "source_url": "https://arxiv.org/abs/2605.23508",
            },
            {
                "source": "Agentic Video Generation / GEST",
                "pattern": "director builds executable event/scene graph instead of one pixel-generation prompt",
                "source_url": "https://arxiv.org/abs/2604.10383",
            },
            {
                "source": "DreamShot",
                "pattern": "multi-shot storyboard synthesis with improved role/scene consistency",
                "source_url": "https://arxiv.org/abs/2604.17195",
            },
        ],
    }


def _req(
    key: str,
    requirement: str,
    status: str,
    evidence_summary: list[str],
    *,
    evidence: dict[str, Any] | None = None,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "requirement": requirement,
        "status": status,
        "evidence_summary": evidence_summary,
        "evidence": evidence or {},
        "blockers": blockers or [],
    }


__all__ = ["build_autonomous_top_tier_completion_gate"]
