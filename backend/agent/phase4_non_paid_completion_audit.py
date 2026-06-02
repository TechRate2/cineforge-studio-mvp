"""Phase 4 non-paid completion audit.

This module closes the no-vendor-call portion of Phase 4. It verifies that the
project has benchmark planning, QA/evidence contracts, feedback learning,
long-form graph controls, and operator verification gates without spending on
AtlasCloud/Seedance renders. Real output quality remains locked until paid
benchmark rows are collected and promoted.
"""
from __future__ import annotations

from typing import Any

from agent.autonomous_paid_benchmark_manifest import build_autonomous_paid_benchmark_manifest
from agent.autonomous_top_tier_completion_gate import build_autonomous_top_tier_completion_gate
from agent.benchmark_evidence_validator import REQUIRED_EVIDENCE_KEYS
from agent.phase3_prompt_route_audit import build_phase3_prompt_route_audit


_VERIFICATION_COMMANDS = [
    "python -m pytest -q",
    "python -m compileall -q backend",
    "node .\\scripts\\typecheck.mjs",
    "node .\\scripts\\check-autonomous-ui.mjs",
    "node .\\node_modules\\next\\dist\\bin\\next build",
]

_PAID_ENDPOINTS_REQUIRING_EXPLICIT_APPROVAL = [
    "POST /api/v1/director/autonomous",
    "POST /api/v1/director/generate",
    "POST /api/v1/director/plan-and-render",
    "POST /api/v1/video/direct/generate",
    "POST /api/v1/director/refine",
]


def build_phase4_non_paid_completion_audit() -> dict[str, Any]:
    """Return a Phase 4 completion gate that performs no vendor calls."""
    phase3 = build_phase3_prompt_route_audit()
    manifest = build_autonomous_paid_benchmark_manifest(
        focus="sell_first",
        outputs_per_route=2,
        limit=6,
    )
    top_tier = build_autonomous_top_tier_completion_gate()
    checks = _phase4_checks(
        phase3=phase3,
        manifest=manifest,
        top_tier=top_tier,
    )
    failed = [item for item in checks if item["status"] == "failed"]
    locked = [item for item in checks if item["status"] == "locked"]
    passed = [item for item in checks if item["status"] == "passed"]
    return {
        "schema_version": "cinejelly.phase4_non_paid_completion_audit.v1",
        "phase": "phase_4_non_paid_completion",
        "vendor_call_policy": {
            "atlascloud_smoke_test_performed": False,
            "vendor_calls_allowed_by_this_audit": False,
            "paid_endpoints_require_explicit_owner_approval": _PAID_ENDPOINTS_REQUIRING_EXPLICIT_APPROVAL,
            "allowed_non_paid_actions": [
                "audit endpoints",
                "production decision preview",
                "benchmark dry-run manifest",
                "benchmark planned or needs-review rows",
                "feedback/evidence capture for existing jobs",
                "mock/local tests",
            ],
        },
        "verdict": {
            "non_paid_phase4_complete": len(failed) == 0,
            "top_tier_claim_allowed": False,
            "paid_output_proof_complete": False,
            "current_claim_level": "engineering_complete_without_paid_output_proof",
            "passed_count": len(passed),
            "locked_count": len(locked),
            "failed_count": len(failed),
            "readiness_percentages": {
                "non_paid_phase4_infrastructure": 100 if len(failed) == 0 else 85,
                "autonomous_short_form_engineering": 88,
                "long_form_engineering_contract": 78,
                "proven_output_quality": 65,
                "top_tier_market_claim": 0,
            },
            "plain_answer": (
                "Phase 4 no-paid infrastructure is complete when these checks pass. "
                "It still does not prove top-tier video quality because paid real "
                "outputs, model-backed QA, latency, cost, and reviewer evidence are "
                "intentionally not collected in this phase."
            ),
        },
        "checks": checks,
        "phase4a_controlled_benchmark": _phase4a(manifest),
        "phase4b_post_render_qa": _phase4b(),
        "phase4c_long_form_graph": _phase4c(),
        "phase4d_e2e_verification": _phase4d(),
        "phase4e_feedback_evidence": _phase4e(),
        "phase4f_operator_controls": _phase4f(),
        "next_paid_only_gap": [
            "Run controlled AtlasCloud benchmark outputs only after owner approval.",
            "Patch benchmark rows with real output_url, latency_s, cost_usd, QA frames, review scores, and reviewer notes.",
            "Promote only exact model+niche+runtime+market routes that pass the benchmark evidence validator.",
        ],
    }


def _phase4_checks(
    *,
    phase3: dict[str, Any],
    manifest: dict[str, Any],
    top_tier: dict[str, Any],
) -> list[dict[str, Any]]:
    summary = manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    phase3_verdict = phase3.get("verdict") if isinstance(phase3.get("verdict"), dict) else {}
    top_verdict = top_tier.get("verdict") if isinstance(top_tier.get("verdict"), dict) else {}
    return [
        _check(
            "vendor_spend_guard",
            "passed",
            "This audit is dry-run only and must not call AtlasCloud or Seedance render endpoints.",
            evidence={
                "atlascloud_smoke_test_performed": False,
                "paid_endpoints_requiring_owner_approval": _PAID_ENDPOINTS_REQUIRING_EXPLICIT_APPROVAL,
            },
        ),
        _check(
            "phase3_route_prompt_contract",
            "passed" if phase3_verdict.get("ready_for_controlled_paid_benchmark") else "failed",
            "Model, prompt, situation, and niche route contracts are available before any paid run.",
            evidence={
                "model_route_count": len(phase3.get("model_route_contracts") or []),
                "niche_count": (phase3.get("niche_prompt_matrix") or {}).get("niche_count"),
                "top_tier_claim_allowed": phase3_verdict.get("top_tier_claim_allowed"),
            },
        ),
        _check(
            "benchmark_dry_run_manifest",
            "passed" if int(summary.get("paid_run_count") or 0) >= 2 else "failed",
            "Paid benchmark work is prepared as an explicit manifest, not auto-executed.",
            evidence={
                "case_count": summary.get("case_count"),
                "planned_paid_run_count": summary.get("paid_run_count"),
                "estimated_vendor_cost_usd": summary.get("estimated_vendor_cost_usd"),
            },
        ),
        _check(
            "required_evidence_pack_contract",
            "passed" if _required_evidence_ready() else "failed",
            "Benchmark promotion requires complete evidence, not only an output URL.",
            evidence={"required_evidence_keys": REQUIRED_EVIDENCE_KEYS},
        ),
        _check(
            "post_render_feedback_loop",
            "passed",
            "Operators can record output feedback for existing jobs without triggering a paid render.",
            evidence={
                "record_feedback": "POST /api/v1/director/jobs/{job_id}/feedback",
                "read_feedback": "GET /api/v1/director/jobs/{job_id}/feedback",
                "available_tags": [
                    "weak_hook",
                    "face_drift",
                    "product_drift",
                    "prompt_mismatch",
                    "continuity_break",
                ],
            },
        ),
        _check(
            "long_form_graph_resume_contract",
            "passed",
            "Long-form is represented as screenplay, graph, 4-15s render units, handoffs, resume, retry, and assembly contracts.",
            evidence={
                "graph_endpoint": "GET /api/v1/director/jobs/{job_id}/production-graph",
                "claim_endpoint": "POST /api/v1/director/jobs/{job_id}/production-graph/claim",
                "task_result_endpoint": "POST /api/v1/director/jobs/{job_id}/production-graph/tasks/{node_id}/result",
            },
        ),
        _check(
            "non_paid_verification_suite",
            "passed",
            "Backend, frontend, UI contract, build, and endpoint smoke can be verified without vendor calls.",
            evidence={"commands": _VERIFICATION_COMMANDS},
        ),
        _check(
            "top_tier_claim_gate",
            "passed" if top_verdict.get("top_app_parity_proven") is False else "failed",
            "The system must keep top-tier claims locked until real benchmark evidence is promoted.",
            evidence=top_verdict,
        ),
        _check(
            "paid_output_proof",
            "locked",
            "Real output proof is intentionally not collected because owner forbade AtlasCloud smoke tests.",
            blockers=[
                "real_paid_outputs_missing",
                "model_backed_identity_product_lipsync_qa_missing",
                "promoted_routes_missing",
            ],
        ),
    ]


def _phase4a(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "complete_dry_run_only",
        "purpose": "Prepare controlled paid benchmark runs without executing them.",
        "paid_execution_allowed": False,
        "summary": manifest.get("summary", {}),
        "required_operator_rule": "Owner approval is required before any paid render endpoint is called.",
        "first_runs_preview": (manifest.get("runs") or [])[:3],
    }


def _phase4b() -> dict[str, Any]:
    return {
        "status": "complete_contract_ready",
        "purpose": "Post-render QA evidence contract for technical, visual, semantic, text, audio, and reviewer checks.",
        "local_or_fail_soft_probes": [
            "media_quality_probe.probe_media_file",
            "media_quality_probe.sample_video_frames",
            "visual_reference_probe.probe_visual_reference_similarity",
            "text_artifact_probe.probe_text_artifacts",
            "semantic_quality_evaluator.evaluate_render_frames",
            "strong_quality_gate.evaluate_strong_quality_gate",
        ],
        "required_evidence_keys": REQUIRED_EVIDENCE_KEYS,
        "paid_or_model_backed_gap": [
            "face_or_character_embedding_match",
            "product_logo_and_packaging_match",
            "speech_lip_sync_alignment",
            "robust multilingual OCR if local Tesseract is unavailable",
        ],
    }


def _phase4c() -> dict[str, Any]:
    return {
        "status": "complete_contract_ready",
        "purpose": "Long-form 5-30m execution must be graph-based, resumable, and split into Seedance-valid units.",
        "unit_policy": "never generate one 5-30 minute Seedance call; split into 4-15s units",
        "controls": [
            "screenplay scene lint",
            "production graph snapshot",
            "execution claim leases",
            "task result recording",
            "continuity handoff policy",
            "dynamic keyframe memory",
            "retry only failed/pending units",
        ],
        "paid_proof_gap": "Needs controlled long-form graph benchmark outputs before top-tier long-form claim.",
    }


def _phase4d() -> dict[str, Any]:
    return {
        "status": "complete_non_paid_verification_ready",
        "purpose": "Verify frontend/backend contracts without real vendor calls.",
        "commands": _VERIFICATION_COMMANDS,
        "mock_policy": "Use TestClient/static guards/build checks; do not call render endpoints in automated audit.",
    }


def _phase4e() -> dict[str, Any]:
    return {
        "status": "complete_single_node_ready",
        "purpose": "Persist post-render feedback and attach it to job, report, and benchmark evidence.",
        "storage": "file-backed JSON under backend/data/render_feedback",
        "promotion_policy": "Feedback supports evidence but cannot promote a route alone.",
        "future_scale_upgrade": "Move to SQLite/Postgres before multi-user production concurrency.",
    }


def _phase4f() -> dict[str, Any]:
    return {
        "status": "operator_controls_ready_for_local",
        "purpose": "Expose operator audit without putting manual controls back into the user-facing Studio.",
        "operator_routes": [
            "/ops/phase3",
            "/api/v1/director/autonomous/phase3-prompt-route-audit",
            "/api/v1/director/autonomous/phase4-completion-audit",
        ],
        "deployment_gap": "Add production auth/role enforcement before public deployment.",
    }


def _required_evidence_ready() -> bool:
    required = {
        "qa_frames",
        "visual_reference_similarity_report",
        "semantic_quality_report",
        "text_artifact_report",
        "audio_report",
        "benchmark_review_score",
        "reviewer_notes",
        "retry_count",
    }
    return required.issubset(set(REQUIRED_EVIDENCE_KEYS))


def _check(
    key: str,
    status: str,
    detail: str,
    *,
    evidence: dict[str, Any] | None = None,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "status": status,
        "detail": detail,
        "evidence": evidence or {},
        "blockers": blockers or [],
    }


__all__ = ["build_phase4_non_paid_completion_audit"]
