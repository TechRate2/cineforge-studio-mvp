"""Autonomous benchmark runner.

The benchmark suite defines what must be proven. This runner turns those cases
into stored evidence rows. It defaults to non-vendor dry runs so CI and product
audits can prepare benchmark work without spending AtlasCloud credits.
"""
from __future__ import annotations

from typing import Any, Optional

from agent.autonomous_benchmark_suite import build_autonomous_benchmark_contract
from agent.benchmark_evidence_template import build_benchmark_evidence_template
from core import autonomous_benchmark_store


_ALLOWED_MODES = {"dry_run"}


def run_autonomous_benchmark_batch(
    *,
    case_ids: Optional[list[str]] = None,
    niches: Optional[list[str]] = None,
    model_key: Optional[str] = None,
    mode: str = "dry_run",
    limit: int = 5,
) -> dict[str, Any]:
    """Create benchmark evidence rows for selected cases.

    `dry_run` stores planned rows with exact gates and inputs needed. It does
    not call vendors, write output URLs, write cost/latency, or claim quality.
    """
    normalized_mode = (mode or "dry_run").strip().lower()
    if normalized_mode not in _ALLOWED_MODES:
        raise ValueError(
            f"unsupported benchmark mode '{mode}'. Allowed: {sorted(_ALLOWED_MODES)}"
        )

    contract = build_autonomous_benchmark_contract()
    selected = _select_cases(
        contract.get("cases") or [],
        case_ids=case_ids or [],
        niches=niches or [],
        limit=limit,
    )
    created: list[dict[str, Any]] = []
    for case in selected:
        route = case.get("recommended_route") or {}
        resolved_model = model_key or route.get("primary_model_key") or "seedance_2_0_fast_ref"
        evidence = _evidence_for_case(case, mode=normalized_mode, model_key=resolved_model)
        row = autonomous_benchmark_store.create_result(
            case_id=str(case.get("case_id")),
            niche=str(case.get("niche")),
            target_market=str(case.get("target_market") or "auto"),
            runtime_class=str(case.get("runtime_class")),
            model_key=str(resolved_model),
            status="planned",
            output_url=None,
            cost_usd=None,
            latency_s=None,
            qa_score=None,
            reviewer_decision="unknown",
            evidence=evidence,
        )
        created.append(row)

    return {
        "schema_version": "cinejelly.benchmark_runner.v1",
        "mode": normalized_mode,
        "requested": {
            "case_ids": case_ids or [],
            "niches": niches or [],
            "model_key": model_key,
            "limit": limit,
        },
        "created_count": len(created),
        "created": created,
        "stats": autonomous_benchmark_store.stats(),
        "vendor_called": False,
        "next_step": (
            "Render selected cases with AtlasCloud and PATCH each result with output_url, cost_usd, latency_s, qa_score, and reviewer_decision."
        ),
    }


def _select_cases(
    cases: list[dict[str, Any]],
    *,
    case_ids: list[str],
    niches: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    case_filter = {c.strip() for c in case_ids if c and c.strip()}
    niche_filter = {n.strip() for n in niches if n and n.strip()}
    out: list[dict[str, Any]] = []
    for case in cases:
        if case_filter and case.get("case_id") not in case_filter:
            continue
        if niche_filter and case.get("niche") not in niche_filter:
            continue
        out.append(case)
        if len(out) >= max(1, min(int(limit or 5), 100)):
            break
    return out


def _evidence_for_case(
    case: dict[str, Any],
    *,
    mode: str,
    model_key: str,
) -> dict[str, Any]:
    return {
        "evidence_schema": "cinejelly.benchmark_evidence.v1",
        "mode": mode,
        "vendor_called": False,
        "metadata_only": True,
        "case": {
            "case_id": case.get("case_id"),
            "niche": case.get("niche"),
            "target_market": case.get("target_market"),
            "duration_hint_s": case.get("duration_hint_s"),
            "runtime_class": case.get("runtime_class"),
            "idea": case.get("idea"),
        },
        "model_key": model_key,
        "reference_requirements": case.get("reference_requirements") or {},
        "required_gates": case.get("required_gates") or [],
        "success_criteria": case.get("success_criteria") or [],
        "production_ready_when": case.get("production_ready_when") or [],
        "recommended_route": case.get("recommended_route") or {},
        "missing_paid_evidence": [
            "final video URL",
            "per-shot prompts/reference manifest/model route",
            "cost and latency",
            "sampled QA frames",
            "audio loudness/silence/sync report",
            "human rating or reviewer decision",
        ],
        "required_promotion_evidence_keys": [
            "per_shot_prompts",
            "reference_manifest",
            "model_route_per_shot",
            "qa_frames",
            "audio_report",
            "identity_product_notes",
            "reviewer_notes",
            "retry_count",
        ],
        "promotion_evidence_template": build_benchmark_evidence_template(
            case=case,
            model_key=model_key,
        ),
    }


__all__ = ["run_autonomous_benchmark_batch"]
