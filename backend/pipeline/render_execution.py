"""Safe paid render orchestration for Phase 3."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from pipeline.approval_lock import ApprovalLock, ApprovalLockVerification
from pipeline.contracts import SeedanceExecutionPlan, SeedanceShotPlan
from workers.continuity_chainer import ContinuityChainer, ContinuityChainState
from workers.cost_control import CostControlService, CostGateDecision
from workers.render_dry_run import RenderDryRunReport, RenderDryRunService
from workers.render_qa_service import RenderQAService, SegmentQAReport
from workers.segment_renderer import SegmentRenderer, SegmentRenderResult


RenderExecutionStatus = Literal[
    "dry_run",
    "rejected",
    "cost_rejected",
    "draft_failed",
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
    """Coordinate ApprovalLock enforcement, dry-run, cost gates, render, and QA."""

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
            return RenderExecutionResult(
                status="rejected",
                execution_plan_id=execution_plan.execution_plan_id,
                approval_lock_id=approval_lock.lock_id,
                approval_verification=verification,
                dry_run_report=dry_run_report,
                message="ApprovalLock mismatch; render was refused before any paid vendor call.",
            )
        if dry_run_only:
            return RenderExecutionResult(
                status="dry_run",
                execution_plan_id=execution_plan.execution_plan_id,
                approval_lock_id=approval_lock.lock_id,
                approval_verification=verification,
                dry_run_report=dry_run_report,
                message="Dry-run generated; no paid vendor call was made.",
            )

        cost_decision = self.cost_control.evaluate_preflight(
            execution_plan,
            mode=cost_gate_mode,
            max_total_usd=max_total_cost_usd,
        )
        if not cost_decision.should_render:
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
            chain_state = self.continuity_chainer.update_state(
                shot_id=shot.shot_id,
                video_url=result.video_url,
                last_frame_url=result.last_frame_url,
                previous_state=chain_state,
            )

        failed = [report for report in qa_reports if report.status == "fail"]
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


__all__ = ["RenderExecutionResult", "RenderExecutionStatus", "RenderExecutor"]
