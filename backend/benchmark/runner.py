"""Benchmark runner for already-compiled Seedance execution plans.

The runner does not generate, mock, or fake videos. It creates an ApprovalLock,
passes the compiled plan into the real RenderExecutor, then records evidence from
that result. Paid benchmark runs require real vendor/storage environment setup.
"""
from __future__ import annotations

from time import perf_counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from benchmark.evidence_store import BenchmarkEvidenceRecord, BenchmarkEvidenceStore
from core.deliverable_url import deliverable_http_url
from pipeline.approval_lock import ApprovalLock
from pipeline.contracts import SeedanceExecutionPlan
from pipeline.render_execution import RenderExecutionResult, RenderExecutor


class BenchmarkRenderCase(BaseModel):
    """One executable benchmark case with a frozen compiled plan."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    idea: str
    niche: str
    runtime_class: str = "short"
    target_platform: str = "tiktok"
    target_market: str = "auto"
    creative_treatment_id: str | None = None
    execution_plan: SeedanceExecutionPlan
    max_total_cost_usd: float | None = Field(None, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkRunResult(BaseModel):
    """Benchmark runner output and evidence row."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    render_status: str
    evidence: BenchmarkEvidenceRecord
    render_message: str = ""


class BenchmarkRenderRunner:
    """Run benchmark cases through RenderExecutor and optionally persist evidence."""

    def __init__(
        self,
        *,
        render_executor: RenderExecutor | None = None,
        evidence_store: BenchmarkEvidenceStore | None = None,
    ) -> None:
        self.render_executor = render_executor or RenderExecutor()
        self.evidence_store = evidence_store

    def run_case(
        self,
        case: BenchmarkRenderCase,
        *,
        approved_by: str = "benchmark_runner",
        cost_gate_mode: str = "off",
        dry_run_only: bool = False,
    ) -> BenchmarkRunResult:
        """Execute one benchmark case and persist its evidence when configured."""
        lock = ApprovalLock.from_execution_plan(
            idea=case.idea,
            execution_plan=case.execution_plan,
            cost_estimate=case.execution_plan.cost_estimate,
            approved_by=approved_by,
            approval_source="benchmark_case",
            metadata={"benchmark_case_id": case.case_id, "benchmark_niche": case.niche},
        )
        started = perf_counter()
        result = self.render_executor.execute(
            execution_plan=case.execution_plan,
            approval_lock=lock,
            idea=case.idea,
            dry_run_only=dry_run_only,
            cost_gate_mode=cost_gate_mode,
            max_total_cost_usd=case.max_total_cost_usd,
        )
        evidence = _evidence_from_result(case=case, result=result, latency_s=perf_counter() - started)
        if self.evidence_store is not None:
            self.evidence_store.append(evidence)
        return BenchmarkRunResult(
            case_id=case.case_id,
            render_status=result.status,
            evidence=evidence,
            render_message=result.message,
        )


def _evidence_from_result(
    *,
    case: BenchmarkRenderCase,
    result: RenderExecutionResult,
    latency_s: float,
) -> BenchmarkEvidenceRecord:
    output_url = _first_output_url(result)
    qa_status = _aggregate_qa_status(result)
    qa_score = _average_visual_score(result)
    cost_usd = result.cost_gate.estimated_total_usd if result.cost_gate is not None else _cost_from_plan(case.execution_plan)
    verdict = (
        "usable"
        if result.status == "completed" and output_url
        else "failed"
        if result.status in {"completed", "rejected", "cost_rejected", "consistency_rejected", "render_failed", "qa_failed"}
        else "unreviewed"
    )
    failure_reason = None
    if verdict == "failed":
        failure_reason = (
            "Completed render did not provide a real HTTP(S) output URL."
            if result.status == "completed" and not output_url
            else result.message
        )
    return BenchmarkEvidenceRecord(
        project_id=case.metadata.get("project_id"),
        job_id=case.metadata.get("job_id"),
        niche=case.niche,
        runtime_class=case.runtime_class,
        target_platform=case.target_platform,
        target_market=case.target_market,
        creative_treatment_id=case.creative_treatment_id,
        model=case.execution_plan.model,
        output_url=output_url,
        cost_usd=cost_usd,
        latency_s=round(latency_s, 3),
        qa_status=qa_status,
        qa_score=qa_score,
        repair_count=sum(result.repair_attempts_by_shot.values()) if hasattr(result, "repair_attempts_by_shot") else 0,
        verdict=verdict,
        failure_reason=failure_reason,
        metadata={
            **case.metadata,
            "case_id": case.case_id,
            "render_status": result.status,
            "render_message": result.message,
            "shot_count": len(case.execution_plan.shots),
        },
    )


def _first_output_url(result: RenderExecutionResult) -> str | None:
    for segment in result.rendered_segments:
        url = deliverable_http_url(segment.video_url)
        if url:
            return url
    return None


def _aggregate_qa_status(result: RenderExecutionResult) -> str | None:
    if not result.qa_reports:
        return None
    if any(report.status == "fail" for report in result.qa_reports):
        return "fail"
    if any(report.status == "warn" for report in result.qa_reports):
        return "warn"
    return "pass"


def _average_visual_score(result: RenderExecutionResult) -> float | None:
    scores: list[float] = []
    for report in result.qa_reports:
        visual = report.visual_consistency
        if visual is not None and visual.overall_score is not None:
            scores.append(float(visual.overall_score))
    if not scores:
        return None
    return round(sum(scores) / len(scores), 2)


def _cost_from_plan(plan: SeedanceExecutionPlan) -> float | None:
    estimate = plan.cost_estimate or {}
    for key in ("estimated_total_usd", "total_usd", "high_usd", "low_usd"):
        value = estimate.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


__all__ = ["BenchmarkRenderCase", "BenchmarkRenderRunner", "BenchmarkRunResult"]
