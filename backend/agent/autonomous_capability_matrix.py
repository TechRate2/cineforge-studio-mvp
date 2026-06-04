"""Runtime x niche capability matrix for CineJelly Autonomous Agent.

This module answers the product question that a static readiness count cannot:
which niches are strong today, how they should be routed across 15s-30m
outputs, and what evidence is still required before claiming top-tier quality.
It is deterministic and vendor-free, so it can run in admin/UI previews.
"""
from __future__ import annotations

from typing import Any

from agent.benchmark_evidence_validator import REQUIRED_EVIDENCE_KEYS
from agent.autonomous_production_decision import build_autonomous_production_decision
from skills.niche_readiness import build_niche_readiness_matrix


_RUNTIME_PROBES = [
    ("short", 30),
    ("micro_film", 180),
    ("short_film", 300),
    ("episode", 1800),
]

_REFERENCE_CONTRACTS: dict[str, dict[str, Any]] = {
    "high": {
        "minimum": {"images": 1, "videos": 0, "audios": 0},
        "optimal": {"images": 3, "videos": 1, "audios": 1},
        "policy": "Direct autonomous render is reasonable for short-form if preflight passes.",
    },
    "medium": {
        "minimum": {"images": 2, "videos": 1, "audios": 0},
        "optimal": {"images": 4, "videos": 1, "audios": 1},
        "policy": "Use autonomous planning, but require stronger QA and benchmark evidence before premium claims.",
    },
    "review_required": {
        "minimum": {"images": 2, "videos": 1, "audios": 1},
        "optimal": {"images": 4, "videos": 2, "audios": 1},
        "policy": "Allow planning, but keep safety/claims review before public production use.",
    },
}


def build_autonomous_capability_matrix() -> dict[str, Any]:
    """Return source-backed capability guidance for every supported niche."""
    readiness = build_niche_readiness_matrix()
    rows = [_build_row(row) for row in readiness["niches"]]
    high = [row["niche"] for row in rows if row["readiness"] == "high"]
    medium = [row["niche"] for row in rows if row["readiness"] == "medium"]
    review = [row["niche"] for row in rows if row["readiness"] == "review_required"]
    return {
        "schema_version": "cinejelly.autonomous_capability_matrix.v1",
        "verdict": {
            "current_level": "strong_autonomous_short_form_foundation",
            "top_tier_claim_allowed": False,
            "why": (
                "Architecture covers autonomous planning, niche playbooks, Seedance 2.0 reference routing, "
                "long-form graph primitives, preflight, QA, and benchmark storage; real paid AtlasCloud "
                "outputs still need to promote routes per niche/runtime/model."
            ),
        },
        "market_policy": {
            "ui_default": "auto",
            "recommendation": (
                "Keep optional market selection. Auto should infer from idea/ref context, but user override "
                "matters for language, dialogue, props, local proof style, safety tone, CTA, caption, and hashtag."
            ),
            "supported": readiness["market_support"],
        },
        "runtime_policy": [
            {
                "class": "short",
                "duration_s": "4-30",
                "route": "Seedance 2.0 Fast Reference or premium Reference",
                "production_status": "best_today",
                "rule": "Use one tightly structured prompt or a small shot list; keep references role-bound.",
            },
            {
                "class": "sequence",
                "duration_s": "31-60",
                "route": "Seedance 2.0 units chained by previous-frame/keyframe handoff",
                "production_status": "strong_candidate",
                "rule": "Split into 4-15s filmable shots; do not overload one generation.",
            },
            {
                "class": "micro_film",
                "duration_s": "61-180",
                "route": "scene planner + shot graph + Seedance i2v/ref units",
                "production_status": "qa_required",
                "rule": "Use scene memory, act beats, previous-shot anchors, and post-render QA before assembly.",
            },
            {
                "class": "short_film",
                "duration_s": "181-600",
                "route": "production graph executor behind benchmark flag",
                "production_status": "needs_paid_benchmarks",
                "rule": "Write screenplay scenes first, render only 4-15s units, preserve last-frame handoffs.",
            },
            {
                "class": "episode",
                "duration_s": "601-1800",
                "route": "episode graph with scene memory, dialogue inserts, and staged QA",
                "production_status": "experimental_until_benchmarked",
                "rule": "Never send a 5-30m film as one prompt; treat it as many verified scenes and shots.",
            },
        ],
        "seedance_2_best_practices": [
            "Use explicit reference roles: image for identity/product/style, video for motion/camera, audio for rhythm/SFX.",
            "Compile prompts as subject/environment/style/shot-list blocks, not one vague paragraph.",
            "Each Seedance unit should contain one filmable action with concrete camera shot, movement, setting, and SFX cues.",
            "For long-form, chain by scene memory, previous final frame, reference priorities, and retry only failed units.",
            "Use Fast Reference for draft/default, premium Reference for hero shots, i2v for previous-frame continuity.",
            "Benchmark dialogue routes separately; exact Vietnamese lip-sync should not rely on unproven visual routes.",
        ],
        "best_today": high,
        "usable_with_more_qa": medium,
        "review_required": review,
        "niches": rows,
        "evidence_required_before_top_tier": [
            "real AtlasCloud output URLs per canonical benchmark case",
            "Seedance prompt formula used for the accepted route",
            "per-shot prompts, reference manifest, and model route per shot",
            "production graph snapshot, scene memory, and continuity handoff report",
            "cost and latency per finished minute",
            "accepted-minute cost including retries",
            "human reviewer rating and notes",
            "identity/product/reference adherence QA",
            "visual reference similarity, semantic QA, and text artifact reports",
            "lip-sync and audio loudness/silence checks for dialogue routes",
            "retry count and final accepted artifact pack",
        ],
        "required_evidence_keys": REQUIRED_EVIDENCE_KEYS,
    }


def _build_row(readiness_row: dict[str, Any]) -> dict[str, Any]:
    niche = str(readiness_row["niche"])
    readiness = str(readiness_row["readiness"])
    contract = _REFERENCE_CONTRACTS.get(readiness, _REFERENCE_CONTRACTS["medium"])
    probes = [_probe_runtime(niche, duration_s, contract["optimal"]) for _, duration_s in _RUNTIME_PROBES]
    graph_required_after = min(
        [item["duration_s"] for item in probes if item.get("graph_required")],
        default=None,
    )
    return {
        "niche": niche,
        "readiness": readiness,
        "best_for": readiness_row.get("best_for"),
        "direct_render_fit": _direct_render_fit(readiness),
        "recommended_reference_contract": contract,
        "hook_moves": readiness_row.get("hook_moves", []),
        "camera": readiness_row.get("camera", []),
        "audio": readiness_row.get("audio"),
        "runtime_routes": probes,
        "long_form_policy": {
            "graph_required_after_s": graph_required_after,
            "needs_scene_memory": True,
            "needs_previous_frame_handoffs": bool(graph_required_after),
            "needs_paid_benchmark_before_default": bool(graph_required_after),
        },
        "operator_note": _operator_note(readiness),
    }


def _probe_runtime(niche: str, duration_s: int, refs: dict[str, int]) -> dict[str, Any]:
    decision = build_autonomous_production_decision(
        user_idea=f"{niche.replace('_', ' ')} autonomous benchmark production",
        target_market="auto",
        target_platform="tiktok" if duration_s <= 60 else "youtube_long",
        duration_hint_s=duration_s,
        reference_counts=refs,
        niche_hint=niche,
    )
    d = decision.get("decision") or {}
    sufficiency = decision.get("reference_sufficiency") or {}
    route = d.get("primary_model_route") or {}
    return {
        "duration_s": duration_s,
        "runtime_class": d.get("runtime_class"),
        "execution_mode": d.get("execution_mode"),
        "graph_required": bool(d.get("graph_required")),
        "primary_visual_model": route.get("primary_visual_model"),
        "continuity_model": route.get("continuity_model"),
        "reference_status": sufficiency.get("status"),
        "reference_score": sufficiency.get("score"),
    }


def _direct_render_fit(readiness: str) -> str:
    if readiness == "high":
        return "strong_for_short_form"
    if readiness == "review_required":
        return "planning_only_until_review"
    return "usable_with_extra_qa"


def _operator_note(readiness: str) -> str:
    if readiness == "high":
        return "Prioritize this niche for launch demos and first paid benchmarks."
    if readiness == "review_required":
        return "Keep safety/claims review and do not market as fully autonomous until benchmarked."
    return "Good planning coverage, but needs more real output evidence before premium positioning."


__all__ = ["build_autonomous_capability_matrix"]
