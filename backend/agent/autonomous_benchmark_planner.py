"""Prioritized benchmark plan for CineJelly Autonomous Director.

The benchmark contract says what must be proven. This planner answers what to
run first so paid AtlasCloud credits are spent on the routes that unlock the
most product confidence: launch niches, long-form graph paths, dialogue lanes,
and current Atlas model challengers.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

from agent.autonomous_benchmark_suite import build_autonomous_benchmark_contract
from agent.benchmark_promotion_policy import build_benchmark_promotion_policy
from agent.benchmark_evidence_template import build_benchmark_evidence_template
from core import autonomous_benchmark_store


_LAUNCH_NICHES = {
    "beauty",
    "food",
    "fashion",
    "ugc_review",
    "ecommerce_catalog",
    "app_saas",
    "tech",
    "restaurant_hospitality",
    "travel",
    "real_estate",
}

_SAFETY_NICHES = {
    "documentary",
    "finance_education",
    "kids_family",
    "medical_wellness",
}

_CANDIDATE_PRIORITY = {
    "atlascloud/infinitetalk": 100,
    "atlascloud/multitalk": 95,
    "bytedance/lipsync/audio-to-video": 90,
    "atlascloud/mmaudio-v2": 82,
    "atlascloud_catalog:vidu_q3_reference_to_video": 78,
    "atlascloud/wan-2.2-turbo/image-to-video": 72,
    "atlascloud_catalog:veo_3_1_lite": 68,
    "bytedance/avatar-omni-human": 60,
    "atlascloud/instant-character": 52,
    "atlascloud/video-upscaler": 45,
}


def build_autonomous_benchmark_plan(
    *,
    limit: int = 12,
    focus: str = "launch",
    results: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Return priority benchmark work for route promotion.

    `focus`:
      - launch: short-form/product/social + first long-form/dialogue proof
      - long_form: prioritize graph, scene continuity, dialogue inserts
      - model_candidates: prioritize locked AtlasCloud challenger models
      - all: balanced full queue
    """
    contract = build_autonomous_benchmark_contract()
    rows = results if results is not None else autonomous_benchmark_store.list_results(limit=500)
    promotion = build_benchmark_promotion_policy(results=rows)
    normalized_focus = (focus or "launch").strip().lower()
    cap = max(1, min(int(limit or 12), 100))

    case_runs = _prioritized_case_runs(contract["cases"], rows, focus=normalized_focus)
    candidate_runs = _prioritized_candidate_runs(
        contract["model_candidate_tests"],
        promotion,
        focus=normalized_focus,
    )
    if normalized_focus == "model_candidates":
        selected = candidate_runs[:cap]
    elif normalized_focus == "long_form":
        long_cases = [item for item in case_runs if item["runtime_class"] in {"short_film", "episode"}]
        selected = [*long_cases, *candidate_runs, *case_runs][:cap]
    elif normalized_focus == "all":
        selected = [*case_runs, *candidate_runs][:cap]
    else:
        launch_cases = [
            item for item in case_runs
            if item["niche"] in _LAUNCH_NICHES or item["runtime_class"] in {"short_film", "episode"}
        ]
        selected = [*launch_cases, *candidate_runs, *case_runs][:cap]

    seen: set[tuple[str, str, str]] = set()
    unique_selected: list[dict[str, Any]] = []
    for item in selected:
        key = (
            str(item.get("kind")),
            str(item.get("case_id") or item.get("model_key")),
            str(item.get("model_key") or item.get("recommended_model_key")),
        )
        if key in seen:
            continue
        seen.add(key)
        unique_selected.append(item)
        if len(unique_selected) >= cap:
            break

    return {
        "schema_version": "cinejelly.autonomous_benchmark_plan.v1",
        "focus": normalized_focus,
        "summary": {
            "selected_count": len(unique_selected),
            "case_candidates": len(case_runs),
            "model_candidate_runs": len(candidate_runs),
            "stored_results_considered": len(rows),
            "promoted_route_count": promotion["summary"]["promoted_route_count"],
            "locked_candidate_models": [
                m["model_key"]
                for m in promotion.get("candidate_models", [])
                if not m.get("eligible_for_auto_routing")
            ],
        },
        "selected_runs": unique_selected,
        "priority_case_runs": case_runs[:cap],
        "priority_model_candidate_runs": candidate_runs[:cap],
        "evidence_policy": contract["global_pass_policy"],
        "runbook": [
            "Create planned rows with POST /api/v1/director/autonomous/benchmarks/run using each run_request.",
            "Render the selected cases with paid AtlasCloud routes and store final output_url, cost_usd, latency_s, QA frames, and reviewer_decision.",
            "Patch benchmark rows to status=passed only after qa_score >= 8 and human approval.",
            "Allow benchmark_promotion_policy to unlock a model/niche/runtime/market route only after two real approved outputs.",
        ],
    }


def _prioritized_case_runs(
    cases: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    *,
    focus: str,
) -> list[dict[str, Any]]:
    evidence = _evidence_index(rows)
    out: list[dict[str, Any]] = []
    for case in cases:
        route = case.get("recommended_route") or {}
        model_key = str(route.get("primary_model_key") or "seedance_2_0_fast_ref")
        case_id = str(case.get("case_id"))
        niche = str(case.get("niche"))
        runtime_class = str(case.get("runtime_class"))
        target_market = str(case.get("target_market") or "auto")
        key = (case_id, model_key)
        ev = evidence.get(key, {})
        score, reasons = _case_priority_score(
            niche=niche,
            runtime_class=runtime_class,
            route=route,
            evidence=ev,
            focus=focus,
        )
        out.append({
            "kind": "canonical_case",
            "priority": _priority_label(score),
            "score": score,
            "case_id": case_id,
            "niche": niche,
            "target_market": target_market,
            "runtime_class": runtime_class,
            "duration_hint_s": case.get("duration_hint_s"),
            "recommended_model_key": model_key,
            "idea": case.get("idea"),
            "reference_requirements": case.get("reference_requirements") or {},
            "required_gates": case.get("required_gates") or [],
            "success_criteria": case.get("success_criteria") or [],
            "current_evidence": ev,
            "why_now": reasons,
            "run_request": {
                "case_ids": [case_id],
                "model_key": model_key,
                "mode": "dry_run",
                "limit": 1,
            },
            "paid_render_note": _paid_render_note(case, route),
            "promotion_evidence_template": build_benchmark_evidence_template(
                case=case,
                model_key=model_key,
            ),
        })
    return sorted(out, key=lambda item: (-int(item["score"]), str(item["case_id"])))


def _prioritized_candidate_runs(
    candidates: list[dict[str, Any]],
    promotion: dict[str, Any],
    *,
    focus: str,
) -> list[dict[str, Any]]:
    promotion_by_model = {
        item["model_key"]: item
        for item in promotion.get("candidate_models", [])
    }
    out: list[dict[str, Any]] = []
    for candidate in candidates:
        model = str(candidate.get("model") or "")
        promo = promotion_by_model.get(model, {})
        base = _CANDIDATE_PRIORITY.get(model, 40)
        if focus == "model_candidates":
            base += 30
        if model in {"atlascloud/infinitetalk", "atlascloud/multitalk", "bytedance/lipsync/audio-to-video"}:
            base += 12
        if promo.get("eligible_for_auto_routing"):
            base -= 50
        missing = list(promo.get("missing_reasons") or [])
        sample_niches = list(candidate.get("sample_niches") or ["ugc_review"])
        sample_markets = list(candidate.get("sample_markets") or ["global"])
        out.append({
            "kind": "model_candidate",
            "priority": _priority_label(base),
            "score": base,
            "model_key": model,
            "role": candidate.get("role"),
            "sample_niches": sample_niches,
            "sample_markets": sample_markets,
            "required_inputs": candidate.get("required_inputs") or [],
            "benchmark_needed": candidate.get("benchmark_needed") or [],
            "route_policy_after_pass": candidate.get("route_policy_after_pass"),
            "must_not_replace": candidate.get("must_not_replace") or [],
            "promotion_status": {
                "eligible_for_auto_routing": bool(promo.get("eligible_for_auto_routing")),
                "missing_reasons": missing,
                "promotion_grade_results": promo.get("promotion_grade_results", 0),
                "best_qa_score": promo.get("best_qa_score", 0),
            },
            "why_now": _candidate_reasons(model, candidate, missing),
            "run_request": {
                "niches": sample_niches[:2],
                "model_key": model,
                "mode": "dry_run",
                "limit": min(2, max(1, len(sample_niches))),
            },
        })
    return sorted(out, key=lambda item: (-int(item["score"]), str(item["model_key"])))


def _evidence_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("case_id")), str(row.get("model_key")))].append(row)
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for key, items in grouped.items():
        real_outputs = [
            item for item in items
            if item.get("output_url") and not str(item.get("output_url")).startswith("stub://")
        ]
        approved = [
            item for item in real_outputs
            if item.get("status") == "passed"
            and item.get("reviewer_decision") == "approved"
            and float(item.get("qa_score") or 0) >= 8
        ]
        out[key] = {
            "total_results": len(items),
            "real_outputs": len(real_outputs),
            "approved_outputs": len(approved),
            "best_qa_score": max([float(item.get("qa_score") or 0) for item in items], default=0.0),
        }
    return out


def _case_priority_score(
    *,
    niche: str,
    runtime_class: str,
    route: dict[str, Any],
    evidence: dict[str, Any],
    focus: str,
) -> tuple[int, list[str]]:
    score = 40
    reasons: list[str] = []
    if niche in _LAUNCH_NICHES:
        score += 25
        reasons.append("launch_niche")
    if niche in _SAFETY_NICHES:
        score += 16
        reasons.append("safety_or_claim_sensitive")
    if runtime_class in {"short_film", "episode"}:
        score += 30
        reasons.append("long_form_graph_proof")
    if route.get("requires_dialogue_candidate_benchmark"):
        score += 24
        reasons.append("dialogue_candidate_gate")
    if route.get("primary_model_key") == "seedance_2_0_ref":
        score += 10
        reasons.append("premium_seedance_reference_route")
    approved = int(evidence.get("approved_outputs") or 0)
    if approved == 0:
        score += 20
        reasons.append("no_approved_outputs")
    elif approved == 1:
        score += 10
        reasons.append("needs_second_approved_output")
    else:
        score -= 30
        reasons.append("already_has_two_approved_outputs")
    if focus == "long_form" and runtime_class in {"short_film", "episode"}:
        score += 20
    if focus == "launch" and niche in _LAUNCH_NICHES:
        score += 10
    return score, reasons


def _candidate_reasons(
    model: str,
    candidate: dict[str, Any],
    missing_reasons: list[str],
) -> list[str]:
    reasons = []
    if missing_reasons:
        reasons.extend(missing_reasons[:3])
    role = str(candidate.get("role") or "")
    if "dialogue" in role or "lipsync" in role:
        reasons.append("unlocks_localized_dialogue_lane")
    if "audio" in role:
        reasons.append("unlocks_post_render_sound_design")
    if "consistency" in role:
        reasons.append("tests_subject_consistency_challenger")
    if model.startswith("atlascloud_catalog:"):
        reasons.append("catalog_candidate_requires_real_route_evidence")
    return reasons or ["benchmark_before_auto_route"]


def _paid_render_note(case: dict[str, Any], route: dict[str, Any]) -> str:
    duration = int(case.get("duration_hint_s") or 30)
    if duration > 180:
        return "Use graph executor, render 4-15s units, preserve previous-final-frame handoffs, then patch evidence after final assembly QA."
    if route.get("requires_dialogue_candidate_benchmark"):
        return "Render Seedance visual coverage plus dialogue candidate insert; patch lip-sync and identity QA before route promotion."
    return "Render the canonical Seedance route twice with different seeds or reference ordering, then patch QA and reviewer decision."


def _priority_label(score: int) -> str:
    if score >= 100:
        return "P0"
    if score >= 78:
        return "P1"
    if score >= 58:
        return "P2"
    return "P3"


__all__ = ["build_autonomous_benchmark_plan"]
