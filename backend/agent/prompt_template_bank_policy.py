"""Benchmark-winning Seedance prompt template bank policy.

The prompt compiler already creates good per-job formulas. This module defines
how those formulas should become reusable production assets after real paid
benchmarks prove that a specific formula/model/reference mix works for a niche.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def build_prompt_template_bank_policy(
    *,
    niche: str,
    runtime_payload: dict[str, Any],
    target_market: str,
    target_platform: str,
    seedance_prompt_formula: dict[str, Any],
    model_route_strategy: dict[str, Any],
    route_quality_scorecard: dict[str, Any],
) -> dict[str, Any]:
    """Return the prompt-template learning contract for one production route."""
    runtime_class = str(runtime_payload.get("runtime_class") or "short")
    route_key = (route_quality_scorecard or {}).get("route_key") or {}
    model_key = str(
        route_key.get("model_key")
        or ((model_route_strategy.get("summary") or {}).get("primary_visual_model"))
        or "seedance_2_0_fast_ref"
    )
    formula = seedance_prompt_formula or {}
    fingerprint = _fingerprint(
        niche=niche,
        runtime_class=runtime_class,
        target_market=target_market,
        model_key=model_key,
        formula=formula,
    )
    exact_promoted = bool(((route_quality_scorecard or {}).get("evidence_status") or {}).get("exact_route_promoted"))
    blocking_reasons = list((route_quality_scorecard or {}).get("blocking_reasons") or [])
    status = "promoted_template_candidate" if exact_promoted else "baseline_template_needs_benchmark"
    if runtime_class in {"short_film", "episode"}:
        status = "long_form_template_benchmark_required"

    return {
        "schema_version": "cinejelly.prompt_template_bank_policy.v1",
        "status": status,
        "template_key": {
            "fingerprint": fingerprint,
            "niche": niche,
            "runtime_class": runtime_class,
            "target_market": target_market,
            "target_platform": target_platform,
            "model_key": model_key,
        },
        "source_formula": {
            "formula_order": list(formula.get("formula") or []),
            "source_pattern": formula.get("source_pattern"),
            "niche_template": formula.get("niche_template") or {},
            "rewrite_rules": list(formula.get("rewrite_rules") or [])[:8],
            "reference_job_policy": formula.get("reference_job_policy") or {},
        },
        "template_slots": _template_slots(formula),
        "benchmark_learning_plan": {
            "variant_count": 3,
            "variants": [
                "baseline_formula_current",
                "reference_first_tighter_constraints",
                "camera_and_action_simplified",
            ],
            "compare_on": [
                "reference adherence",
                "hook clarity",
                "camera and motion quality",
                "story/proof clarity",
                "technical artifacts",
                "accepted-minute cost",
                "retry count",
            ],
            "minimum_passing_outputs_per_variant": 2,
        },
        "evidence_to_store": [
            "template_fingerprint",
            "compiled_prompt_text",
            "seedance_prompt_formula",
            "reference_role_mix",
            "model_key",
            "niche",
            "runtime_class",
            "target_market",
            "output_url",
            "qa_score",
            "reviewer_notes",
            "cost_usd",
            "latency_s",
            "retry_count",
        ],
        "selection_policy": {
            "current_route_promoted": exact_promoted,
            "blocking_reasons": blocking_reasons,
            "default_behavior": (
                "use deterministic baseline formula until benchmark evidence promotes a winning template"
            ),
            "promotion_rule": (
                "reuse the winning template only for the same niche/runtime/model/market family, "
                "and demote it if later benchmark rows show drift or higher accepted-minute cost"
            ),
        },
    }


def _template_slots(formula: dict[str, Any]) -> list[dict[str, str]]:
    order = list(formula.get("formula") or [])
    template = formula.get("niche_template") if isinstance(formula.get("niche_template"), dict) else {}
    slots: list[dict[str, str]] = []
    for item in order:
        key = str(item)
        slots.append({
            "slot": key,
            "purpose": _slot_purpose(key, template),
        })
    return slots


def _slot_purpose(slot: str, template: dict[str, Any]) -> str:
    if slot == "reference_jobs":
        return "bind every image/video/audio to one production job"
    if slot == "story_intent":
        return str(template.get("story_intent") or "state the visual promise of the unit")
    if slot == "action":
        return str(template.get("action") or "one physically filmable action")
    if slot == "camera":
        return str(template.get("camera") or "shot size, movement, and continuity purpose")
    if slot == "sound":
        return str(template.get("sound") or "foley/music/dialogue intent")
    if slot == "constraints":
        return "negative constraints for identity/product/text/artifact drift"
    return slot.replace("_", " ")


def _fingerprint(
    *,
    niche: str,
    runtime_class: str,
    target_market: str,
    model_key: str,
    formula: dict[str, Any],
) -> str:
    payload = {
        "niche": niche,
        "runtime_class": runtime_class,
        "target_market": target_market,
        "model_key": model_key,
        "formula": formula.get("formula") or [],
        "niche_template": formula.get("niche_template") or {},
        "rewrite_rules": formula.get("rewrite_rules") or [],
        "reference_job_policy": formula.get("reference_job_policy") or {},
    }
    raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


__all__ = ["build_prompt_template_bank_policy"]
