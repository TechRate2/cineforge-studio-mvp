"""Long-form segmented render executor for Phase 9A MVP."""
from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from longform.contracts import LongFormExecutionPlan, SegmentPlan
from pipeline.approval_lock import ApprovalLock, ApprovalLockVerification
from pipeline.render_execution import RenderExecutor
from pipeline.trace import PipelineTrace
from workers.render_dry_run import RenderDryRunReport
from workers.render_qa_service import SegmentQAReport
from workers.segment_renderer import SegmentRenderResult

logger = logging.getLogger(__name__)

LongFormRenderStatus = Literal[
    "dry_run",
    "rejected",
    "draft_failed",
    "render_failed",
    "qa_failed",
    "completed",
]


class LongFormRenderResult(BaseModel):
    """Result of a Phase 9A long-form render attempt."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "cineforge.longform.render_result.v1"
    status: LongFormRenderStatus
    longform_plan_id: str
    approval_lock_id: str
    approval_verification: ApprovalLockVerification
    dry_run_report: RenderDryRunReport
    rendered_segments: list[SegmentRenderResult] = Field(default_factory=list)
    qa_reports: list[SegmentQAReport] = Field(default_factory=list)
    repair_attempts_by_segment: dict[str, int] = Field(default_factory=dict)
    updated_plan: LongFormExecutionPlan | None = None
    message: str = ""


class LongFormRenderExecutor:
    """Render a long-form plan segment by segment using existing render services."""

    def __init__(
        self,
        *,
        render_executor: RenderExecutor | None = None,
        max_auto_repair_attempts: int = 1,
    ) -> None:
        self.render_executor = render_executor or RenderExecutor()
        self.max_auto_repair_attempts = max(0, int(max_auto_repair_attempts))

    def dry_run(
        self,
        *,
        longform_plan: LongFormExecutionPlan,
        approval_lock: ApprovalLock,
        idea: str,
        trace: PipelineTrace | None = None,
    ) -> LongFormRenderResult:
        """Generate the mandatory dry-run report without vendor calls."""
        master_plan = _require_master_plan(longform_plan)
        verification = approval_lock.verify_against(
            idea=idea,
            execution_plan=master_plan,
            reference_assets=master_plan.reference_assets,
            cost_estimate=master_plan.cost_estimate,
        )
        report = self.render_executor.dry_run_service.generate_dry_run_report(
            master_plan,
            approval_lock,
            approval_verification=verification,
        )
        if trace is not None:
            trace.append_stage(
                stage="longform_dry_run",
                stage_input=longform_plan,
                stage_output=report,
                decision="long-form dry-run generated" if verification.valid else "long-form dry-run lock mismatch",
                reasoning_summary="Phase 9A dry-run previews every segment payload before any paid render.",
                rules_applied=["phase9a.render.dry_run_required", "phase9a.render.single_approval_lock"],
                warnings=verification.mismatched_fields,
                cost_estimate=master_plan.cost_estimate,
            )
        return LongFormRenderResult(
            status="dry_run" if verification.valid else "rejected",
            longform_plan_id=longform_plan.longform_plan_id,
            approval_lock_id=approval_lock.lock_id,
            approval_verification=verification,
            dry_run_report=report,
            updated_plan=longform_plan,
            message="Long-form dry-run generated; no paid vendor call was made."
            if verification.valid
            else "ApprovalLock mismatch during long-form dry-run.",
        )

    def execute(
        self,
        *,
        longform_plan: LongFormExecutionPlan,
        approval_lock: ApprovalLock,
        idea: str,
        dry_run_approved: bool = False,
        trace: PipelineTrace | None = None,
    ) -> LongFormRenderResult:
        """Render every segment in order after dry-run approval and lock verification."""
        master_plan = _require_master_plan(longform_plan)
        verification = approval_lock.verify_against(
            idea=idea,
            execution_plan=master_plan,
            reference_assets=master_plan.reference_assets,
            cost_estimate=master_plan.cost_estimate,
        )
        dry_run_report = self.render_executor.dry_run_service.generate_dry_run_report(
            master_plan,
            approval_lock,
            approval_verification=verification,
        )
        if not verification.valid:
            logger.warning(
                "longform_render_approval_rejected",
                extra={
                    "longform_plan_id": longform_plan.longform_plan_id,
                    "approval_lock_id": approval_lock.lock_id,
                    "mismatched_fields": verification.mismatched_fields,
                },
            )
            return _result(
                status="rejected",
                longform_plan=longform_plan,
                approval_lock=approval_lock,
                verification=verification,
                dry_run_report=dry_run_report,
                message="ApprovalLock mismatch; long-form render was refused before vendor calls.",
            )
        if not _dry_run_approved(approval_lock=approval_lock, explicit=dry_run_approved):
            return _result(
                status="rejected",
                longform_plan=longform_plan,
                approval_lock=approval_lock,
                verification=verification,
                dry_run_report=dry_run_report,
                message="Long-form dry-run approval is required before paid segmented render.",
            )
        consistency_decision = _consistency_policy_decision(master_plan, approval_lock)
        if not consistency_decision["should_render"]:
            logger.warning(
                "longform_render_consistency_rejected",
                extra={
                    "longform_plan_id": longform_plan.longform_plan_id,
                    "approval_lock_id": approval_lock.lock_id,
                    "consistency_policy_action": consistency_decision["action"],
                    "reason_ids": consistency_decision["reason_ids"],
                },
            )
            return _result(
                status="rejected",
                longform_plan=longform_plan,
                approval_lock=approval_lock,
                verification=verification,
                dry_run_report=dry_run_report,
                message=str(consistency_decision["message"]),
            )

        logger.info(
            "longform_render_started",
            extra={
                "longform_plan_id": longform_plan.longform_plan_id,
                "segment_count": len(longform_plan.segments),
                "approval_lock_id": approval_lock.lock_id,
            },
        )
        rendered: list[SegmentRenderResult] = []
        qa_reports: list[SegmentQAReport] = []
        repair_attempts: dict[str, int] = {}
        updated_segments: list[SegmentPlan] = []
        previous_last_frame_url: str | None = None
        for segment in longform_plan.segments:
            segment_result, segment_qa, repair_count = self._render_segment_with_repair(
                longform_plan=longform_plan,
                segment=segment,
                previous_last_frame_url=previous_last_frame_url,
            )
            rendered.extend(segment_result)
            qa_reports.extend(segment_qa)
            repair_attempts[segment.segment_id] = repair_count
            final_render = segment_result[-1]
            final_qa = segment_qa[-1]
            status = "completed" if final_qa.status != "fail" and final_render.status == "completed" else "failed"
            updated_segment = segment.model_copy(update={
                "status": status,
                "repair_attempts": repair_count,
                "last_frame_anchor": {
                    **segment.last_frame_anchor,
                    "url": final_render.last_frame_url,
                    "source": "rendered_segment_last_frame",
                },
            })
            updated_segments.append(updated_segment)
            if final_render.status != "completed":
                return _result(
                    status="render_failed",
                    longform_plan=longform_plan.model_copy(update={"segments": updated_segments + longform_plan.segments[len(updated_segments):]}),
                    approval_lock=approval_lock,
                    verification=verification,
                    dry_run_report=dry_run_report,
                    rendered_segments=rendered,
                    qa_reports=qa_reports,
                    repair_attempts_by_segment=repair_attempts,
                    message=f"Long-form render failed at {segment.segment_id}.",
                )
            if final_qa.status == "fail":
                return _result(
                    status="qa_failed",
                    longform_plan=longform_plan.model_copy(update={"segments": updated_segments + longform_plan.segments[len(updated_segments):]}),
                    approval_lock=approval_lock,
                    verification=verification,
                    dry_run_report=dry_run_report,
                    rendered_segments=rendered,
                    qa_reports=qa_reports,
                    repair_attempts_by_segment=repair_attempts,
                    message=f"Long-form QA failed at {segment.segment_id}.",
                )
            previous_last_frame_url = final_render.last_frame_url
            if trace is not None:
                trace.append_stage(
                    stage="longform_segment_render",
                    stage_input=segment,
                    stage_output={"render": final_render, "qa": final_qa},
                    decision=f"rendered {segment.segment_id}",
                    reasoning_summary="Segment rendered after verifying the master long-form ApprovalLock.",
                    rules_applied=["phase9a.render.linear_segment_order", "phase9a.render.last_frame_handoff"],
                    warnings=final_qa.warnings,
                )

        updated_plan = longform_plan.model_copy(update={"segments": updated_segments, "status": "completed"})
        logger.info(
            "longform_render_completed",
            extra={
                "longform_plan_id": longform_plan.longform_plan_id,
                "rendered_segments": len(updated_segments),
                "repair_attempts": repair_attempts,
            },
        )
        return _result(
            status="completed",
            longform_plan=updated_plan,
            approval_lock=approval_lock,
            verification=verification,
            dry_run_report=dry_run_report,
            rendered_segments=rendered,
            qa_reports=qa_reports,
            repair_attempts_by_segment=repair_attempts,
            message="Long-form render completed safely.",
        )

    def _render_segment_with_repair(
        self,
        *,
        longform_plan: LongFormExecutionPlan,
        segment: SegmentPlan,
        previous_last_frame_url: str | None,
    ) -> tuple[list[SegmentRenderResult], list[SegmentQAReport], int]:
        """Render one segment and retry only that segment when repair is allowed."""
        execution_plan = _require_segment_execution_plan(segment)
        shot = execution_plan.shots[0]
        results: list[SegmentRenderResult] = []
        qa_reports: list[SegmentQAReport] = []
        repair_count = 0
        max_attempts = self.max_auto_repair_attempts + 1
        for attempt in range(max_attempts):
            result = self.render_executor.segment_renderer.render_segment(
                execution_plan=execution_plan,
                shot=shot,
                previous_last_frame_url=previous_last_frame_url,
                override_model="seedance_2_0_fast" if segment.index == 0 and attempt == 0 else None,
            )
            qa_report = self.render_executor.qa_service.evaluate_segment(shot=shot, result=result)
            results.append(result)
            qa_reports.append(qa_report)
            if result.status == "completed" and qa_report.status != "fail":
                return results, qa_reports, repair_count
            if attempt >= max_attempts - 1:
                return results, qa_reports, repair_count
            repair_count += 1
            logger.warning(
                "longform_segment_auto_repair",
                extra={
                    "longform_plan_id": longform_plan.longform_plan_id,
                    "segment_id": segment.segment_id,
                    "repair_attempt": repair_count,
                    "render_status": result.status,
                    "qa_status": qa_report.status,
                    "qa_errors": qa_report.errors,
                },
            )
        return results, qa_reports, repair_count


def _require_master_plan(longform_plan: LongFormExecutionPlan):
    if longform_plan.master_execution_plan is None:
        raise ValueError("LongFormExecutionPlan must be compiled before render.")
    return longform_plan.master_execution_plan


def _require_segment_execution_plan(segment: SegmentPlan):
    if segment.seedance_execution_plan is None or not segment.seedance_execution_plan.shots:
        raise ValueError(f"{segment.segment_id} is missing a compiled SeedanceExecutionPlan.")
    return segment.seedance_execution_plan


def _dry_run_approved(*, approval_lock: ApprovalLock, explicit: bool) -> bool:
    return bool(explicit or approval_lock.metadata.get("longform_dry_run_approved"))


def _consistency_policy_decision(master_plan, approval_lock: ApprovalLock) -> dict[str, object]:
    action = str(master_plan.metadata.get("consistency_policy_action") or "").strip()
    reasons = [str(item) for item in master_plan.metadata.get("consistency_policy_reasons") or [] if str(item).strip()]
    if action in {"", "allow", "warn"}:
        return {
            "should_render": True,
            "action": action or "allow",
            "reason_ids": reasons,
            "message": "Consistency policy allows long-form render.",
        }
    if action == "block":
        return {
            "should_render": False,
            "action": action,
            "reason_ids": reasons,
            "message": "Consistency policy blocked long-form paid render before vendor calls.",
        }
    if action == "requires_review":
        approved = bool(
            approval_lock.metadata.get("consistency_review_approved")
            and str(approval_lock.metadata.get("consistency_review_approved_policy_action") or "").strip() == action
        )
        return {
            "should_render": approved,
            "action": action,
            "reason_ids": reasons,
            "message": "Consistency review was approved; long-form render may proceed."
            if approved
            else "Consistency policy requires review approval before long-form paid render.",
        }
    return {
        "should_render": False,
        "action": action,
        "reason_ids": reasons + ["unknown_consistency_policy_action"],
        "message": f"Unknown consistency policy action '{action}' blocked long-form paid render.",
    }


def _result(
    *,
    status: LongFormRenderStatus,
    longform_plan: LongFormExecutionPlan,
    approval_lock: ApprovalLock,
    verification: ApprovalLockVerification,
    dry_run_report: RenderDryRunReport,
    rendered_segments: list[SegmentRenderResult] | None = None,
    qa_reports: list[SegmentQAReport] | None = None,
    repair_attempts_by_segment: dict[str, int] | None = None,
    message: str,
) -> LongFormRenderResult:
    return LongFormRenderResult(
        status=status,
        longform_plan_id=longform_plan.longform_plan_id,
        approval_lock_id=approval_lock.lock_id,
        approval_verification=verification,
        dry_run_report=dry_run_report,
        rendered_segments=rendered_segments or [],
        qa_reports=qa_reports or [],
        repair_attempts_by_segment=repair_attempts_by_segment or {},
        updated_plan=longform_plan,
        message=message,
    )


__all__ = ["LongFormRenderExecutor", "LongFormRenderResult", "LongFormRenderStatus"]
