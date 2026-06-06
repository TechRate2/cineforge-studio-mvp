"""Safe paid render orchestration for Phase 3."""
from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from pipeline.approval_lock import ApprovalLock, ApprovalLockVerification
from pipeline.contracts import SeedanceExecutionPlan, SeedanceShotPlan
from workers.continuity_chainer import ContinuityChainer, ContinuityChainState
from workers.cost_control import CostControlService, CostGateDecision
from workers.render_dry_run import RenderDryRunReport, RenderDryRunService
from workers.render_qa_service import RenderQAService, SegmentQAReport
from workers.segment_renderer import SegmentRenderer, SegmentRenderResult

logger = logging.getLogger(__name__)

RenderExecutionStatus = Literal[
    "dry_run",
    "rejected",
    "preflight_rejected",
    "cost_rejected",
    "consistency_rejected",
    "draft_failed",
    "render_failed",
    "qa_failed",
    "completed",
]


class RenderExecutionResult(BaseModel):
    """Result of a safe Phase 3 render execution attempt."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "cineforge.render_execution_result.v1"
    status: RenderExecutionStatus
    execution_plan_id: str
    approval_lock_id: str
    approval_verification: ApprovalLockVerification
    dry_run_report: RenderDryRunReport
    cost_gate: CostGateDecision | None = None
    rendered_segments: list[SegmentRenderResult] = Field(default_factory=list)
    qa_reports: list[SegmentQAReport] = Field(default_factory=list)
    message: str = ""


class RenderExecutor:
    """Coordinate ApprovalLock enforcement, dry-run, preflight, cost gates, render, and QA."""

    def __init__(
        self,
        *,
        dry_run_service: RenderDryRunService | None = None,
        segment_renderer: SegmentRenderer | None = None,
        continuity_chainer: ContinuityChainer | None = None,
        qa_service: RenderQAService | None = None,
        cost_control: CostControlService | None = None,
    ) -> None:
        self.dry_run_service = dry_run_service or RenderDryRunService()
        self.segment_renderer = segment_renderer or SegmentRenderer()
        self.continuity_chainer = continuity_chainer or ContinuityChainer()
        self.qa_service = qa_service or RenderQAService()
        self.cost_control = cost_control or CostControlService()

    def execute(
        self,
        *,
        execution_plan: SeedanceExecutionPlan,
        approval_lock: ApprovalLock,
        idea: str | None = None,
        dry_run_only: bool = False,
        cost_gate_mode: str = "off",
        max_total_cost_usd: float | None = None,
    ) -> RenderExecutionResult:
        """Execute a paid render only after ApprovalLock verification passes."""
        logger.info(
            "render_executor_started",
            extra={
                "execution_plan_id": execution_plan.execution_plan_id,
                "approval_lock_id": approval_lock.lock_id,
                "dry_run_only": dry_run_only,
                "cost_gate_mode": cost_gate_mode,
                "shot_count": len(execution_plan.shots),
            },
        )
        approved_idea = _resolve_approved_idea(execution_plan, approval_lock, idea)
        verification = approval_lock.verify_against(
            idea=approved_idea,
            execution_plan=execution_plan,
            cost_estimate=execution_plan.cost_estimate,
        )
        dry_run_report = self.dry_run_service.generate_dry_run_report(
            execution_plan,
            approval_lock,
            approval_verification=verification,
        )
        if not verification.valid:
            logger.warning(
                "render_executor_approval_rejected",
                extra={
                    "execution_plan_id": execution_plan.execution_plan_id,
                    "approval_lock_id": approval_lock.lock_id,
                    "mismatched_fields": verification.mismatched_fields,
                },
            )
            return RenderExecutionResult(
                status="rejected",
                execution_plan_id=execution_plan.execution_plan_id,
                approval_lock_id=approval_lock.lock_id,
                approval_verification=verification,
                dry_run_report=dry_run_report,
                message="ApprovalLock mismatch; render was refused before any paid vendor call.",
            )
        if dry_run_only:
            logger.info(
                "render_executor_dry_run_completed",
                extra={
                    "execution_plan_id": execution_plan.execution_plan_id,
                    "approval_lock_id": approval_lock.lock_id,
                },
            )
            return RenderExecutionResult(
                status="dry_run",
                execution_plan_id=execution_plan.execution_plan_id,
                approval_lock_id=approval_lock.lock_id,
                approval_verification=verification,
                dry_run_report=dry_run_report,
                message="Dry-run generated; no paid vendor call was made.",
            )

        preflight_decision = _seedance_preflight_decision(execution_plan)
        if not preflight_decision["should_render"]:
            logger.warning(
                "render_executor_preflight_rejected",
                extra={
                    "execution_plan_id": execution_plan.execution_plan_id,
                    "approval_lock_id": approval_lock.lock_id,
                    "status": preflight_decision["status"],
                    "hard_failures": preflight_decision["hard_failures"],
                },
            )
            return RenderExecutionResult(
                status="preflight_rejected",
                execution_plan_id=execution_plan.execution_plan_id,
                approval_lock_id=approval_lock.lock_id,
                approval_verification=verification,
                dry_run_report=dry_run_report,
                message=str(preflight_decision["message"]),
            )
        if preflight_decision["warnings"]:
            logger.info(
                "render_executor_preflight_warnings",
                extra={
                    "execution_plan_id": execution_plan.execution_plan_id,
                    "approval_lock_id": approval_lock.lock_id,
                    "warnings": preflight_decision["warnings"],
                },
            )

        consistency_decision = _consistency_policy_decision(execution_plan, approval_lock)
        if not consistency_decision["should_render"]:
            logger.warning(
                "render_executor_consistency_rejected",
                extra={
                    "execution_plan_id": execution_plan.execution_plan_id,
                    "approval_lock_id": approval_lock.lock_id,
                    "consistency_policy_action": consistency_decision["action"],
                    "reason_ids": consistency_decision["reason_ids"],
                },
            )
            return RenderExecutionResult(
                status="consistency_rejected",
                execution_plan_id=execution_plan.execution_plan_id,
                approval_lock_id=approval_lock.lock_id,
                approval_verification=verification,
                dry_run_report=dry_run_report,
                message=str(consistency_decision["message"]),
            )

        cost_decision = self.cost_control.evaluate_preflight(
            execution_plan,
            mode=cost_gate_mode,
            max_total_usd=max_total_cost_usd,
        )
        if not cost_decision.should_render:
            logger.warning(
                "render_executor_cost_rejected",
                extra={
                    "execution_plan_id": execution_plan.execution_plan_id,
                    "approval_lock_id": approval_lock.lock_id,
                    "estimated_total_usd": cost_decision.estimated_total_usd,
                    "max_total_usd": cost_decision.max_total_usd,
                },
            )
            return RenderExecutionResult(
                status="cost_rejected",
                execution_plan_id=execution_plan.execution_plan_id,
                approval_lock_id=approval_lock.lock_id,
                approval_verification=verification,
                dry_run_report=dry_run_report,
                cost_gate=cost_decision,
                message=cost_decision.reason,
            )

        shots = execution_plan.shots or [_single_shot_from_plan(execution_plan)]
        if cost_gate_mode == "draft_first" and shots:
            draft_result = self.segment_renderer.render_segment(
                execution_plan=execution_plan,
                shot=shots[0],
                override_model="seedance_2_0_fast",
            )
            draft_qa = self.qa_service.evaluate_segment(shot=shots[0], result=draft_result)
            if draft_qa.status == "fail":
                logger.warning(
                    "render_executor_draft_failed",
                    extra={
                        "execution_plan_id": execution_plan.execution_plan_id,
                        "approval_lock_id": approval_lock.lock_id,
                        "shot_id": shots[0].shot_id,
                        "segment_status": draft_result.status,
                        "errors": draft_qa.errors,
                    },
                )
                return RenderExecutionResult(
                    status="draft_failed",
                    execution_plan_id=execution_plan.execution_plan_id,
                    approval_lock_id=approval_lock.lock_id,
                    approval_verification=verification,
                    dry_run_report=dry_run_report,
                    cost_gate=cost_decision,
                    rendered_segments=[draft_result],
                    qa_reports=[draft_qa],
                    message="Draft-first render failed QA; full render was not started.",
                )

        rendered_segments: list[SegmentRenderResult] = []
        qa_reports: list[SegmentQAReport] = []
        chain_state = ContinuityChainState()
        for shot in shots:
            result = self.segment_renderer.render_segment(
                execution_plan=execution_plan,
                shot=shot,
                previous_last_frame_url=chain_state.previous_last_frame_url,
            )
            rendered_segments.append(result)
            qa_report = self.qa_service.evaluate_segment(shot=shot, result=result)
            qa_reports.append(qa_report)
            if result.status != "completed":
                logger.error(
                    "render_executor_segment_failed",
                    extra={
                        "execution_plan_id": execution_plan.execution_plan_id,
                        "approval_lock_id": approval_lock.lock_id,
                        "shot_id": shot.shot_id,
                        "error_code": result.error_code,
                        "attempts": result.attempts,
                    },
                )
                return RenderExecutionResult(
                    status="render_failed",
                    execution_plan_id=execution_plan.execution_plan_id,
                    approval_lock_id=approval_lock.lock_id,
                    approval_verification=verification,
                    dry_run_report=dry_run_report,
                    cost_gate=cost_decision,
                    rendered_segments=rendered_segments,
                    qa_reports=qa_reports,
                    message=f"Render failed for {shot.shot_id}: {result.error_code or result.error or 'vendor error'}",
                )
            chain_state = self.continuity_chainer.update_state(
                shot_id=shot.shot_id,
                video_url=result.video_url,
                last_frame_url=result.last_frame_url,
                previous_state=chain_state,
            )

        failed = [report for report in qa_reports if report.status == "fail"]
        if failed:
            logger.warning(
                "render_executor_qa_failed",
                extra={
                    "execution_plan_id": execution_plan.execution_plan_id,
                    "approval_lock_id": approval_lock.lock_id,
                    "failed_shots": [report.shot_id for report in failed],
                },
            )
        else:
            logger.info(
                "render_executor_completed",
                extra={
                    "execution_plan_id": execution_plan.execution_plan_id,
                    "approval_lock_id": approval_lock.lock_id,
                    "rendered_segments": len(rendered_segments),
                },
            )
        return RenderExecutionResult(
            status="qa_failed" if failed else "completed",
            execution_plan_id=execution_plan.execution_plan_id,
            approval_lock_id=approval_lock.lock_id,
            approval_verification=verification,
            dry_run_report=dry_run_report,
            cost_gate=cost_decision,
            rendered_segments=rendered_segments,
            qa_reports=qa_reports,
            message="Render completed with QA failures." if failed else "Render completed safely.",
        )


def _resolve_approved_idea(
    execution_plan: SeedanceExecutionPlan,
    approval_lock: ApprovalLock,
    explicit_idea: str | None,
) -> str:
    if explicit_idea is not None:
        return explicit_idea
    for source in (execution_plan.metadata, approval_lock.metadata):
        for key in ("approved_idea", "idea", "user_idea", "normalized_idea"):
            value = str(source.get(key) or "").strip()
            if value:
                return value
    return ""


def _single_shot_from_plan(execution_plan: SeedanceExecutionPlan) -> SeedanceShotPlan:
    return SeedanceShotPlan(
        shot_id=f"{execution_plan.execution_plan_id}_shot_0",
        index=0,
        duration_s=execution_plan.duration_s,
        compiled_prompt=execution_plan.compiled_prompt,
        model=execution_plan.model,
        aspect_ratio=execution_plan.aspect_ratio,
        resolution=execution_plan.resolution,
        references=execution_plan.reference_assets,
        rules_applied=execution_plan.rules_applied,
        examples_used=execution_plan.examples_used,
        linter_warnings=execution_plan.linter_warnings,
    )


def _seedance_preflight_decision(execution_plan: SeedanceExecutionPlan) -> dict[str, Any]:
    """Fail closed on compiler-recorded Seedance preflight hard failures."""
    hard_failures: list[str] = []
    warnings: list[str] = []
    statuses: list[str] = []
    for payload in _seedance_preflight_payloads(execution_plan):
        status = str(payload.get("status") or "").strip().lower()
        if status:
            statuses.append(status)
        hard_failures.extend(str(item) for item in payload.get("hard_failures") or [] if str(item).strip())
        warnings.extend(str(item) for item in payload.get("warnings") or [] if str(item).strip())
    hard_failures = list(dict.fromkeys(hard_failures))
    warnings = list(dict.fromkeys(warnings))
    status = "fail" if hard_failures or "fail" in statuses else ("warn" if warnings or "warn" in statuses else "pass")
    if status == "fail":
        return {
            "should_render": False,
            "status": status,
            "hard_failures": hard_failures,
            "warnings": warnings,
            "message": "Seedance preflight rejected paid render before vendor call: " + "; ".join(hard_failures[:4]),
        }
    return {
        "should_render": True,
        "status": status,
        "hard_failures": [],
        "warnings": warnings,
        "message": "Seedance preflight allows render.",
    }


def _seedance_preflight_payloads(execution_plan: SeedanceExecutionPlan) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    plan_preflight = execution_plan.metadata.get("seedance_preflight")
    if isinstance(plan_preflight, dict):
        payloads.append(plan_preflight)
    for shot in execution_plan.shots:
        shot_preflight = shot.metadata.get("seedance_preflight")
        if isinstance(shot_preflight, dict):
            payloads.append(shot_preflight)
    return payloads


def _consistency_policy_decision(
    execution_plan: SeedanceExecutionPlan,
    approval_lock: ApprovalLock,
) -> dict[str, object]:
    """Return whether consistency policy permits a paid vendor render."""
    action = _consistency_policy_action(execution_plan)
    reason_ids = _consistency_policy_reasons(execution_plan)
    if action in {"", "allow", "warn"}:
        return {
            "should_render": True,
            "action": action or "allow",
            "reason_ids": reason_ids,
            "message": "Consistency policy allows render.",
        }
    if action == "block":
        return {
            "should_render": False,
            "action": action,
            "reason_ids": reason_ids,
            "message": "Consistency policy blocked paid render before vendor call.",
        }
    if action == "requires_review":
        approved = _consistency_review_approved(execution_plan, approval_lock, action)
        return {
            "should_render": approved,
            "action": action,
            "reason_ids": reason_ids,
            "message": (
                "Consistency review was approved; render may proceed."
                if approved
                else "Consistency policy requires review approval before paid render."
            ),
        }
    return {
        "should_render": False,
        "action": action,
        "reason_ids": reason_ids + ["unknown_consistency_policy_action"],
        "message": f"Unknown consistency policy action '{action}' blocked paid render.",
    }


def _consistency_review_approved(
    execution_plan: SeedanceExecutionPlan,
    approval_lock: ApprovalLock,
    action: str,
) -> bool:
    """Return whether a review approval explicitly covers the current policy action."""
    for source in (approval_lock.metadata, execution_plan.metadata):
        if not bool(source.get("consistency_review_approved")):
            continue
        approved_action = str(source.get("consistency_review_approved_policy_action") or "").strip()
        policy_action = str(source.get("consistency_policy_action") or "").strip()
        if approved_action == action or policy_action == action:
            return True
    return False


def _consistency_policy_action(execution_plan: SeedanceExecutionPlan) -> str:
    action = str(execution_plan.metadata.get("consistency_policy_action") or "").strip()
    if action:
        return action
    policy = execution_plan.metadata.get("consistency_policy") or {}
    if isinstance(policy, dict):
        action = str(policy.get("action") or "").strip()
        if action:
            return action
    for shot in execution_plan.shots:
        action = str(shot.metadata.get("consistency_policy_action") or "").strip()
        if action:
            return action
    return ""


def _consistency_policy_reasons(execution_plan: SeedanceExecutionPlan) -> list[str]:
    reasons: list[str] = []
    for source in (execution_plan.metadata,):
        reasons.extend(str(item) for item in source.get("consistency_policy_reasons") or [])
        policy = source.get("consistency_policy") or {}
        if isinstance(policy, dict):
            reasons.extend(str(item) for item in policy.get("reason_ids") or [])
    for shot in execution_plan.shots:
        reasons.extend(str(item) for item in shot.metadata.get("consistency_policy_reasons") or [])
    return list(dict.fromkeys(reason for reason in reasons if reason.strip()))


__all__ = ["RenderExecutionResult", "RenderExecutionStatus", "RenderExecutor"]
