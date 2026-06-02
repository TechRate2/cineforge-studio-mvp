"""Paid benchmark execution manifest for CineJelly.

The planner says what to prioritize. This manifest turns that priority into a
concrete paid-run batch: two real AtlasCloud outputs per route, render payload
blueprints, evidence fields to collect, and the promotion target that each run
can unlock.
"""
from __future__ import annotations

from math import ceil
from typing import Any

from agent.autonomous_benchmark_planner import build_autonomous_benchmark_plan
from agent.autonomous_niche_launch_matrix import build_autonomous_niche_launch_matrix
from agent.benchmark_evidence_validator import REQUIRED_EVIDENCE_KEYS
from agent.benchmark_review_rubric import build_benchmark_review_rubric
from agent.model_specs import VIDEO_MODEL_SPECS


def build_autonomous_paid_benchmark_manifest(
    *,
    focus: str = "sell_first",
    outputs_per_route: int = 2,
    limit: int = 18,
) -> dict[str, Any]:
    """Return a vendor-call manifest for the next real benchmark batch."""
    launch = build_autonomous_niche_launch_matrix()
    sell_first = set((launch.get("tiers") or {}).get("sell_first") or [])
    plan = build_autonomous_benchmark_plan(focus="launch", limit=max(limit, 24))
    selected_cases = [
        item for item in plan.get("priority_case_runs", [])
        if item.get("kind") == "canonical_case"
        and (focus != "sell_first" or item.get("niche") in sell_first)
    ][: max(1, int(limit or 18))]
    runs: list[dict[str, Any]] = []
    for case in selected_cases:
        for replicate in range(1, max(1, min(int(outputs_per_route or 2), 4)) + 1):
            runs.append(_paid_run(case, replicate=replicate))
    cost = _cost_summary(runs)

    return {
        "schema_version": "cinejelly.autonomous_paid_benchmark_manifest.v1",
        "focus": focus,
        "summary": {
            "case_count": len(selected_cases),
            "paid_run_count": len(runs),
            "outputs_per_route": max(1, min(int(outputs_per_route or 2), 4)),
            "sell_first_niches": sorted(sell_first),
            "estimated_vendor_cost_usd": cost,
            "top_tier_claim_after_manifest": False,
            "reason": "Manifest prepares real evidence collection; top-tier claim starts only after runs are completed, reviewed, and promoted.",
        },
        "operator_runbook": [
            "Create a planned benchmark row for each run before calling AtlasCloud.",
            "Submit the render_payload_blueprint through /api/v1/director/autonomous with real references attached.",
            "After render, create or patch benchmark result with output_url, cost_usd, latency_s, qa_score, reviewer_decision, reviewer_notes, retry_count, QA frames, and route metadata.",
            "Mark status=passed only if qa_score >= 8.0 and reviewer_decision=approved.",
            "Run promotion policy; only promoted routes can power top-tier/premium claims.",
        ],
        "operator_runbook_phases": _operator_runbook_phases(),
        "required_evidence_keys": REQUIRED_EVIDENCE_KEYS,
        "runs": runs,
        "next_phase_after_this_batch": [
            "premium Seedance 2.0 Reference hero-shot batch for beauty, food, fashion, ecommerce",
            "3m and 5m graph-executor batch for drama/documentary/travel",
            "Vietnamese dialogue batch for InfiniteTalk, MultiTalk, and LipSync",
            "post-render audio batch for MMAudio on food, ASMR, travel, hospitality",
        ],
    }


def _paid_run(case: dict[str, Any], *, replicate: int) -> dict[str, Any]:
    case_id = str(case.get("case_id") or "")
    niche = str(case.get("niche") or "ugc_review")
    model_key = str(case.get("recommended_model_key") or "seedance_2_0_fast_ref")
    target_market = str(case.get("target_market") or "auto")
    runtime_class = str(case.get("runtime_class") or "short")
    duration = int(case.get("duration_hint_s") or 30)
    run_id = f"{case_id}:{model_key}:r{replicate}"
    estimated_cost = _estimate_run_cost(model_key=model_key, duration_s=duration)
    return {
        "run_id": run_id,
        "case_id": case_id,
        "niche": niche,
        "target_market": target_market,
        "runtime_class": runtime_class,
        "duration_hint_s": duration,
        "model_key": model_key,
        "replicate_index": replicate,
        "estimated_vendor_cost_usd": estimated_cost,
        "priority": case.get("priority"),
        "score": case.get("score"),
        "why_now": case.get("why_now", []),
        "idea": case.get("idea"),
        "reference_requirements": case.get("reference_requirements") or {},
        "success_criteria": case.get("success_criteria") or [],
        "render_payload_blueprint": _render_payload(case, model_key=model_key, replicate=replicate),
        "benchmark_result_create_blueprint": _result_create_payload(case, model_key=model_key),
        "benchmark_result_patch_after_render": _result_patch_payload(case, replicate=replicate),
        "review_rubric": build_benchmark_review_rubric(
            niche=niche,
            runtime_class=runtime_class,
            target_market=target_market,
            has_dialogue=_case_has_dialogue(case),
        ),
        "promotion_target": {
            "model_key": model_key,
            "niche": niche,
            "runtime_class": runtime_class,
            "target_market": target_market,
            "requires_two_approved_outputs": True,
        },
        "manual_review_questions": _review_questions(case),
    }


def _operator_runbook_phases() -> list[dict[str, Any]]:
    return [
        {
            "phase": "preflight",
            "goal": "Prove the run is worth vendor spend before calling AtlasCloud.",
            "steps": [
                "Open /api/v1/director/autonomous/production-decision for the benchmark idea.",
                "Confirm niche, market, runtime, model route, segment inspector, and input upgrade plan are coherent.",
                "Attach required image/video/audio refs or approved asset pins; do not run with placeholder refs.",
                "Create benchmark result row with status=planned and benchmark_manifest_version evidence.",
            ],
            "exit_gate": "No placeholder refs, no ambiguous niche, no reference cap failures, and planned row exists.",
        },
        {
            "phase": "paid_render",
            "goal": "Produce real output while preserving exact route evidence.",
            "steps": [
                "Submit /api/v1/director/autonomous with the render_payload_blueprint and real refs.",
                "Record job_id, prediction ids, resolved per-shot model route, prompts, and reference manifest.",
                "Keep production graph snapshot, Seedance segment inspector, scene memory pack, continuity handoffs, retries, and assembly metadata.",
                "Do not manually edit the output before evidence capture; post edits hide route weaknesses.",
            ],
            "exit_gate": "Final output_url exists and raw artifacts are saved before any promotion review.",
        },
        {
            "phase": "qa_review",
            "goal": "Score the output with the same rubric used for promotion.",
            "steps": [
                "Collect QA frames, visual reference similarity, semantic QA, text artifact report, audio/loudness/silence report, identity/product notes, latency_s, cost_usd, accepted minute cost, and retry_count.",
                "Apply benchmark_review_rubric dimensions and hard failures.",
                "Patch benchmark result with review_scores or qa_score, reviewer_decision, reviewer_notes, and full evidence pack.",
                "Set status=passed only when reviewer_decision=approved and qa_score meets threshold.",
            ],
            "exit_gate": "benchmark_evidence_validator returns promotion_ready=true for each approved row.",
        },
        {
            "phase": "promotion_or_rollback",
            "goal": "Promote only proven routes and convert failures into engineering work.",
            "steps": [
                "Run benchmark_promotion_policy after at least two approved outputs for the same route.",
                "Promote exact model+niche+runtime+market route only; do not generalize to all niches.",
                "If failed, store failure mode, keep route benchmark_locked, and add retry or model-candidate task.",
                "Update top-tier maturity only after promoted routes and graph/dialogue/QA gates match the claim.",
            ],
            "exit_gate": "Route promotion is evidence-backed or explicitly remains locked with failure reasons.",
        },
    ]


def _cost_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    subtotal = round(sum(float((run.get("estimated_vendor_cost_usd") or {}).get("estimated_total_usd") or 0.0) for run in runs), 4)
    contingency = round(subtotal * 1.15, 4)
    return {
        "subtotal": subtotal,
        "with_15pct_contingency": contingency,
        "currency": "USD",
        "policy": "Estimate uses current local model_specs cost_per_second and requested duration; actual AtlasCloud billing may differ by retries, SR/upscale, vendor changes, or graph unit splitting.",
    }


def _estimate_run_cost(*, model_key: str, duration_s: int) -> dict[str, Any]:
    spec = VIDEO_MODEL_SPECS.get(model_key) or {}
    rate = spec.get("cost_per_second_usd")
    if rate is None:
        return {
            "estimated_total_usd": None,
            "cost_per_second_usd": None,
            "estimated_billable_seconds": duration_s,
            "estimated_seedance_units": max(1, ceil(max(4, duration_s) / 12)),
            "note": "Unknown local model spec; use live AtlasCloud pricing before paid run.",
        }
    billable_seconds = max(int(duration_s or 0), int((spec.get("duration") or {}).get("min") or 0))
    estimated_units = max(1, ceil(max(4, duration_s) / 12))
    return {
        "estimated_total_usd": round(float(rate) * billable_seconds, 4),
        "cost_per_second_usd": float(rate),
        "estimated_billable_seconds": billable_seconds,
        "estimated_seedance_units": estimated_units,
        "note": "Use as pre-run budget only; patch actual cost_usd after AtlasCloud completes.",
    }


def _render_payload(case: dict[str, Any], *, model_key: str, replicate: int) -> dict[str, Any]:
    duration = int(case.get("duration_hint_s") or 30)
    target_platform = "youtube_long" if duration > 180 else "tiktok"
    return {
        "user_idea": case.get("idea"),
        "target_market": case.get("target_market") or "auto",
        "target_platform": target_platform,
        "duration_hint_s": duration,
        "user_model": "auto",
        "resolution": "720p",
        "series_key": f"benchmark_{case.get('case_id')}_r{replicate}",
        "auto_select_asset_pins": True,
        "reference_image_urls": ["<attach required image refs before paid render>"],
        "reference_video_urls": ["<attach motion/camera refs if required>"],
        "reference_audio_urls": ["<attach audio/voice/SFX refs if required>"],
        "internal_expected_model_route": model_key,
        "internal_seed_or_reference_order_note": (
            "Use a distinct seed/reference ordering for each replicate if vendor supports it; otherwise vary only safe reference ordering."
        ),
    }


def _result_create_payload(case: dict[str, Any], *, model_key: str) -> dict[str, Any]:
    return {
        "case_id": case.get("case_id"),
        "niche": case.get("niche"),
        "target_market": case.get("target_market") or "auto",
        "runtime_class": case.get("runtime_class"),
        "model_key": model_key,
        "status": "planned",
        "evidence": {
            "benchmark_manifest_version": "cinejelly.autonomous_paid_benchmark_manifest.v1",
            "success_criteria": case.get("success_criteria") or [],
            "required_gates": case.get("required_gates") or [],
            "reference_requirements": case.get("reference_requirements") or {},
        },
    }


def _result_patch_payload(case: dict[str, Any], *, replicate: int) -> dict[str, Any]:
    return {
        "status": "passed | failed | needs_review",
        "output_url": "<final AtlasCloud video URL>",
        "cost_usd": "<actual vendor cost>",
        "latency_s": "<submit-to-final latency>",
        "qa_score": "<0-10 reviewer/QA score>",
        "reviewer_decision": "approved | rejected | needs_review",
        "evidence": {
            "per_shot_prompts": "<final prompts per shot/unit>",
            "seedance_prompt_formula": "<final Seedance prompt formula contract from production decision>",
            "reference_manifest": "<image/video/audio refs and their jobs>",
            "model_route_per_shot": "<resolved model per shot/unit>",
            "production_graph_snapshot": "<graph id, scene/shot nodes, dependency edges, node status summary, resume checkpoint>",
            "scene_memory_pack": "<character/product/location/style memory and accepted keyframe anchors; use not_applicable only for single-shot no-reference jobs>",
            "continuity_handoff_report": "<previous-frame, reference, and narrative handoff checks per scene/shot>",
            "seedance_segment_inspector": "<segment durations, per-shot 4-15s compliance, split strategy, prompt density warnings>",
            "qa_frames": ["<sampled frame URLs or local artifact refs>"],
            "visual_reference_similarity_report": "<visual reference probe report with avg/max similarity and warnings>",
            "semantic_quality_report": "<semantic QA report: prompt/idea/niche alignment, hook clarity, story/proof score>",
            "text_artifact_report": "<OCR/caption artifact report or not_applicable_no_text_overlay>",
            "audio_report": "<loudness/silence/sync/lip-sync notes>",
            "identity_product_notes": "<identity/product/style adherence notes>",
            "benchmark_review_score": "<cinejelly.benchmark_review_score.v1 result produced from review_scores>",
            "accepted_minute_cost": "<actual accepted cost per finished minute, including retries>",
            "reviewer_notes": "<human reviewer notes>",
            "retry_count": "<integer retry count>",
            "replicate_index": replicate,
            "required_gates": case.get("required_gates") or [],
            "success_criteria": case.get("success_criteria") or [],
        },
    }


def _review_questions(case: dict[str, Any]) -> list[str]:
    questions = [
        "Is the first 3 seconds visually understandable without explanation?",
        "Did the output follow the reference roles without identity/product drift?",
        "Would this clip be usable without structural manual editing?",
        "Are captions, hashtags, and local proof style appropriate for the target market?",
    ]
    if str(case.get("runtime_class")) in {"short_film", "episode"}:
        questions.append("Does the scene/chunk continuity feel like one film rather than disconnected clips?")
    if any("audio" in str(item).lower() or "voice" in str(item).lower() for item in case.get("reference_requirements", {}).values()):
        questions.append("Is audio/voice/lip-sync aligned enough for public release?")
    return questions


def _case_has_dialogue(case: dict[str, Any]) -> bool:
    text = " ".join([
        str(case.get("idea") or ""),
        " ".join(str(item) for item in case.get("reference_strategy") or []),
        " ".join(str(item) for item in (case.get("reference_requirements") or {}).values()),
    ]).lower()
    return any(token in text for token in ("voice", "dialogue", "speaker", "creator", "educator", "audio", "talk", "interview"))


__all__ = ["build_autonomous_paid_benchmark_manifest"]
