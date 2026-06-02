"""Autonomous niche readiness matrix.

This turns the creative playbooks and benchmark cases into a compact product
capability report. It is deterministic and vendor-free, so UI/admin routes can
show what CineJelly is currently strong at and what still needs safety or
production work before claiming top-tier performance.
"""
from __future__ import annotations

from typing import Any

from agent.model_scorecard import build_autonomous_model_scorecard

from .niche_benchmarks import get_benchmark_case, validate_benchmark_coverage
from .niche_playbooks import get_niche_playbook, list_niche_keys


_HIGH_READY = {
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

_REVIEW_REQUIRED = {
    "documentary",
    "finance_education",
    "kids_family",
    "medical_wellness",
}


def build_niche_readiness_matrix() -> dict[str, Any]:
    """Return supported niches with readiness, benchmark, and routing notes."""
    from agent.autonomous_benchmark_suite import build_autonomous_benchmark_contract

    coverage = validate_benchmark_coverage()
    rows = [_niche_row(niche) for niche in list_niche_keys()]
    summary = {
        "supported_niches": len(rows),
        "high_readiness": len([r for r in rows if r["readiness"] == "high"]),
        "medium_readiness": len([r for r in rows if r["readiness"] == "medium"]),
        "review_required": len([r for r in rows if r["readiness"] == "review_required"]),
        "benchmark_coverage_ok": coverage["ok"],
        "benchmark_missing": coverage["missing"],
    }
    return {
        "schema_version": "cinejelly.autonomous_capabilities.v1",
        "summary": summary,
        "runtime_support": [
            {"class": "short", "duration_s": "4-30", "status": "production_candidate"},
            {"class": "sequence", "duration_s": "31-60", "status": "production_candidate"},
            {"class": "micro_film", "duration_s": "61-180", "status": "needs_stronger_qa"},
            {"class": "short_film", "duration_s": "181-600", "status": "graph_executor_available_behind_benchmark_flag"},
            {"class": "episode", "duration_s": "601-1800", "status": "graph_executor_available_needs_paid_benchmarks"},
        ],
        "market_support": ["auto", "vn", "us", "sea", "jp", "kr", "global"],
        "niches": rows,
        "model_strategy": {
            "primary": "Seedance 2.0 Fast/Reference for most autonomous short-form and quad-modal jobs.",
            "premium": "Seedance 2.0 Reference for highest-fidelity product, beauty, fashion, and cinematic shots.",
            "dialogue_fallback": "Wan 2.7 i2v for driven-audio lip-sync/talking-head shots.",
            "future_candidates": [
                "atlascloud/infinitetalk for long multilingual talking-head/dialogue clips",
                "atlascloud/multitalk for lower-cost multi-person dialogue inserts after benchmark",
                "atlascloud/mmaudio-v2 for ambience/SFX pass",
                "bytedance/lipsync/audio-to-video for post-render lip sync",
                "bytedance/avatar-omni-human for portrait dialogue clips",
                "atlascloud/instant-character for character anchor generation",
                "atlascloud/video-upscaler for premium final polish after QA",
            ],
        },
        "model_scorecard": build_autonomous_model_scorecard(),
        "benchmark_contract": build_autonomous_benchmark_contract(),
        "next_required_upgrades": [
            "Run paid long-form graph executor benchmarks, then promote it as the default path.",
            "Real visual/audio QA with frame identity, product, caption, silence/loudness, and sync checks.",
            "Dedicated Asset Library for recurring characters, products, locations, voice, and style; /studio already supports image memory pins, status, role, priority, and series filtering.",
            "Per-niche benchmark runs with actual vendor output, cost, QA failures, and user ratings.",
            "Dialogue benchmark lane for Vietnamese and English using Wan 2.7, InfiniteTalk, MultiTalk, and lip-sync repair models.",
            "Dialogue route policy that chooses Seedance cinematic coverage versus Wan/InfiniteTalk/MultiTalk insert candidates by market, duration, and speaker count.",
        ],
    }


def _niche_row(niche: str) -> dict[str, Any]:
    playbook = get_niche_playbook(niche)
    benchmark = get_benchmark_case(niche)
    readiness = _readiness(niche)
    return {
        "niche": niche,
        "readiness": readiness,
        "best_for": playbook.get("best_for"),
        "hook_moves": playbook.get("hook_moves", [])[:3],
        "camera": playbook.get("camera", [])[:4],
        "audio": playbook.get("audio"),
        "safety_rules": playbook.get("safety_rules", []),
        "benchmark": {
            "idea": benchmark.get("idea"),
            "target_market": benchmark.get("target_market"),
            "duration_hint_s": benchmark.get("duration_hint_s"),
            "reference_strategy": benchmark.get("reference_strategy", []),
            "success_criteria": benchmark.get("success_criteria", []),
        },
        "recommendation": _recommendation(readiness),
    }


def _readiness(niche: str) -> str:
    if niche in _REVIEW_REQUIRED:
        return "review_required"
    if niche in _HIGH_READY:
        return "high"
    return "medium"


def _recommendation(readiness: str) -> str:
    if readiness == "high":
        return "Good candidate for autonomous direct render with standard post-render QA."
    if readiness == "review_required":
        return "Keep autonomous planning, but add safety/claims review before broad production use."
    return "Usable with autonomous planning; needs stronger visual QA and more benchmark cases before top-tier claims."


__all__ = ["build_niche_readiness_matrix"]
