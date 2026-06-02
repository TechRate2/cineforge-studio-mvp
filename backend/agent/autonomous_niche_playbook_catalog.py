"""Inspectable niche playbook catalog for autonomous video production.

The runtime decision path already builds a recipe for one job. This catalog is
the product/admin view: every supported niche, its best use, reference contract,
script pattern, duration scaling, Seedance prompt rules, and launch posture.
"""
from __future__ import annotations

from typing import Any

from agent.niche_runtime_director import build_niche_runtime_director_contract
from skills.niche_playbooks import get_niche_playbook, list_niche_keys
from skills.niche_readiness import build_niche_readiness_matrix


_DURATION_PROFILES = [
    ("short", 30, "15-30s viral proof"),
    ("micro_film", 180, "1-3m micro film"),
    ("short_film", 300, "5m short film"),
    ("episode", 1800, "30m episode"),
]


def build_autonomous_niche_playbook_catalog() -> dict[str, Any]:
    """Return a compact production playbook for all supported niches."""
    readiness = build_niche_readiness_matrix()
    readiness_by_niche = {row["niche"]: row for row in readiness.get("niches", [])}
    rows = [
        _catalog_row(niche, readiness_by_niche.get(niche, {}))
        for niche in list_niche_keys()
    ]
    return {
        "schema_version": "cinejelly.autonomous_niche_playbook_catalog.v1",
        "summary": {
            "niche_count": len(rows),
            "high_readiness": len([r for r in rows if r["readiness"] == "high"]),
            "medium_readiness": len([r for r in rows if r["readiness"] == "medium"]),
            "review_required": len([r for r in rows if r["readiness"] == "review_required"]),
            "default_duration_policy": "short-form first; long-form requires graph, scene memory, handoffs, and benchmark evidence",
        },
        "global_doctrine": [
            "Keep the UI one-click; the agent decides niche, runtime, treatment, model route, and QA gates.",
            "Use Seedance 2.0 as the core visual director with explicit reference roles.",
            "For 5-30m videos, write screenplay scenes first and render only 4-15s units.",
            "Every long-form scene needs purpose, conflict/turn, continuity anchor, and final-frame handoff.",
            "Dialogue/lip-sync models are inserts or repair lanes, not replacements for Seedance visual coverage.",
            "Top-tier claims require real benchmark evidence, reviewer notes, cost/latency, and QA artifacts.",
        ],
        "duration_templates": _duration_templates(),
        "rows": rows,
    }


def _catalog_row(niche: str, readiness_row: dict[str, Any]) -> dict[str, Any]:
    playbook = get_niche_playbook(niche)
    runtime_examples = [
        _runtime_example(niche=niche, duration_s=duration_s, label=label)
        for _, duration_s, label in _DURATION_PROFILES
    ]
    return {
        "niche": niche,
        "readiness": readiness_row.get("readiness") or "medium",
        "best_for": playbook.get("best_for"),
        "script_pattern": {
            "hook_moves": playbook.get("hook_moves", [])[:4],
            "beat_flow": playbook.get("beat_flow", []),
            "opening_rule": _opening_rule(playbook),
            "payoff_rule": "payoff must be visible in the video, not only described by text or voice",
        },
        "visual_language": {
            "camera": playbook.get("camera", [])[:5],
            "audio": playbook.get("audio"),
            "quality_bar": playbook.get("quality_bar", []),
            "safety_rules": playbook.get("safety_rules", []),
        },
        "reference_contract": _reference_contract_for(niche),
        "duration_scaling": runtime_examples,
        "seedance_prompt_contract": {
            "structure": [
                "reference jobs",
                "timeline",
                "environment",
                "visual style",
                "subject/action",
                "camera/sound",
                "shot contract",
                "constraints",
            ],
            "rules": playbook.get("seedance_notes", []),
            "avoid": playbook.get("avoid", []),
        },
        "operator_posture": _operator_posture(readiness_row.get("readiness") or "medium"),
    }


def _runtime_example(*, niche: str, duration_s: int, label: str) -> dict[str, Any]:
    payload = _runtime_payload(duration_s)
    contract = build_niche_runtime_director_contract(
        niche=niche,
        runtime_payload=payload,
        target_market="auto",
        target_platform="tiktok" if duration_s <= 180 else "youtube_long",
        has_dialogue=niche in {"ugc_review", "education", "finance_education", "medical_wellness", "documentary", "drama", "app_saas", "tech"},
        reference_counts=_reference_counts_for(niche, duration_s),
    )
    scene = contract.get("scene_architecture") or {}
    seedance = contract.get("seedance_unit_doctrine") or {}
    return {
        "label": label,
        "duration_s": duration_s,
        "runtime_class": contract.get("runtime_class"),
        "director_mode": contract.get("director_mode"),
        "single_call_allowed": seedance.get("single_call_allowed"),
        "estimated_seedance_units": seedance.get("estimated_units"),
        "scene_count": scene.get("scene_count"),
        "continuity_method": seedance.get("continuity_method"),
        "long_form_method": scene.get("long_form_method"),
        "qa_focus": (contract.get("qa_focus") or [])[:5],
        "risk_register": contract.get("risk_register") or [],
    }


def _duration_templates() -> list[dict[str, Any]]:
    return [
        {
            "duration": "15-30s",
            "method": "one promise, one visible proof, one payoff",
            "seedance_units": "1-3 units",
            "default_status": "best current production fit",
        },
        {
            "duration": "60-180s",
            "method": "mini-act structure with scene memory and QA before assembly",
            "seedance_units": "5-15 units",
            "default_status": "usable with stronger QA",
        },
        {
            "duration": "5-10m",
            "method": "screenplay -> acts -> scenes -> chunks -> 4-15s render nodes",
            "seedance_units": "25-50 units",
            "default_status": "benchmark gated",
        },
        {
            "duration": "10-30m",
            "method": "episode graph with asset bible, resumable leases, dialogue inserts, and staged review",
            "seedance_units": "60-180 units",
            "default_status": "experimental until paid graph benchmarks pass",
        },
    ]


def _runtime_payload(duration_s: int) -> dict[str, Any]:
    if duration_s <= 30:
        return {"runtime_class": "short", "target_duration_s": duration_s, "scene_count": 1, "chunk_count": 1}
    if duration_s <= 180:
        return {"runtime_class": "micro_film", "target_duration_s": duration_s, "scene_count": 3, "chunk_count": 3}
    if duration_s <= 600:
        return {"runtime_class": "short_film", "target_duration_s": duration_s, "act_count": 3, "scene_count": 5, "chunk_count": 5}
    return {"runtime_class": "episode", "target_duration_s": duration_s, "act_count": 6, "scene_count": 30, "chunk_count": 30}


def _reference_counts_for(niche: str, duration_s: int) -> dict[str, int]:
    images = 3 if niche in {"beauty", "food", "fashion", "ecommerce_catalog", "ugc_review", "drama"} else 2
    videos = 1 if duration_s > 60 or niche in {"travel", "real_estate", "restaurant_hospitality", "automotive", "asmr"} else 0
    audios = 1 if niche in {"asmr", "food", "music_video", "education", "ugc_review", "drama"} else 0
    pinned = 1 if duration_s > 180 else 0
    return {"images": images, "videos": videos, "audios": audios, "pinned_assets": pinned}


def _reference_contract_for(niche: str) -> dict[str, Any]:
    counts = _reference_counts_for(niche, 300)
    priority = ["style/lighting reference"]
    if niche in {"beauty", "food", "fashion", "ecommerce_catalog", "tech", "app_saas", "automotive", "restaurant_hospitality"}:
        priority.insert(0, "product or hero object reference")
    if niche in {"ugc_review", "drama", "documentary", "education", "fitness", "kids_family", "lifestyle", "music_video"}:
        priority.insert(0, "character/creator identity reference")
    if niche in {"real_estate", "travel", "restaurant_hospitality", "documentary"}:
        priority.append("location/environment reference")
    if niche in {"education", "finance_education", "medical_wellness", "documentary", "drama", "ugc_review"}:
        priority.append("voice/dialogue audio reference")
    return {
        "best_quality_counts": counts,
        "priority_order": list(dict.fromkeys(priority)),
        "seedance_caps": {"images": 9, "videos": 3, "audios": 3, "mixed_total": 12},
        "rule": "assign every uploaded asset one job: identity, product, location, style, motion, rhythm, or dialogue",
    }


def _opening_rule(playbook: dict[str, Any]) -> str:
    hooks = playbook.get("hook_moves") or ["visual proof"]
    return f"open with {hooks[0]} before explanation; avoid slow intro or logo-first opening"


def _operator_posture(readiness: str) -> str:
    if readiness == "high":
        return "launch-first short-form candidate; run paid benchmarks before premium/top-tier claims"
    if readiness == "review_required":
        return "planning and preview only until safety, claims, or factual review passes"
    return "usable with extra QA and benchmark evidence before default commercial promise"


__all__ = ["build_autonomous_niche_playbook_catalog"]
