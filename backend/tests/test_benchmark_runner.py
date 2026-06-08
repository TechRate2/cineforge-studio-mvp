from benchmark.runner import BenchmarkRenderCase, BenchmarkRenderRunner
from pipeline.approval_lock import ApprovalLockVerification
from pipeline.contracts import SeedanceExecutionPlan, SeedanceShotPlan
from pipeline.render_execution import RenderExecutionResult
from workers.render_dry_run import RenderDryRunReport
from workers.segment_renderer import SegmentRenderResult


class _CompletedRenderExecutor:
    def execute(self, *, execution_plan, approval_lock, idea=None, dry_run_only=False, cost_gate_mode="off", max_total_cost_usd=None):  # noqa: ANN001, ANN201
        return RenderExecutionResult(
            status="completed",
            execution_plan_id=execution_plan.execution_plan_id,
            approval_lock_id=approval_lock.lock_id,
            approval_verification=ApprovalLockVerification(valid=True),
            dry_run_report=RenderDryRunReport(
                execution_plan_id=execution_plan.execution_plan_id,
                approval_lock_id=approval_lock.lock_id,
                approval_valid=True,
                model=execution_plan.model,
                duration_s=execution_plan.duration_s,
                aspect_ratio=execution_plan.aspect_ratio,
                resolution=execution_plan.resolution,
            ),
            rendered_segments=[
                SegmentRenderResult(
                    shot_id="shot_1",
                    index=0,
                    status="completed",
                    video_url="https://cdn.example.com/output.mp4",
                    duration_s=8,
                    model=execution_plan.model,
                )
            ],
            qa_reports=[],
            message="Render completed safely.",
        )


class _CompletedLocalOutputRenderExecutor:
    def execute(self, *, execution_plan, approval_lock, idea=None, dry_run_only=False, cost_gate_mode="off", max_total_cost_usd=None):  # noqa: ANN001, ANN201
        return RenderExecutionResult(
            status="completed",
            execution_plan_id=execution_plan.execution_plan_id,
            approval_lock_id=approval_lock.lock_id,
            approval_verification=ApprovalLockVerification(valid=True),
            dry_run_report=RenderDryRunReport(
                execution_plan_id=execution_plan.execution_plan_id,
                approval_lock_id=approval_lock.lock_id,
                approval_valid=True,
                model=execution_plan.model,
                duration_s=execution_plan.duration_s,
                aspect_ratio=execution_plan.aspect_ratio,
                resolution=execution_plan.resolution,
            ),
            rendered_segments=[
                SegmentRenderResult(
                    shot_id="shot_1",
                    index=0,
                    status="completed",
                    video_url="file:///tmp/output.mp4",
                    duration_s=8,
                    model=execution_plan.model,
                )
            ],
            qa_reports=[],
            message="Render completed safely.",
        )


class _CompletedLoopbackOutputRenderExecutor:
    def execute(self, *, execution_plan, approval_lock, idea=None, dry_run_only=False, cost_gate_mode="off", max_total_cost_usd=None):  # noqa: ANN001, ANN201
        return RenderExecutionResult(
            status="completed",
            execution_plan_id=execution_plan.execution_plan_id,
            approval_lock_id=approval_lock.lock_id,
            approval_verification=ApprovalLockVerification(valid=True),
            dry_run_report=RenderDryRunReport(
                execution_plan_id=execution_plan.execution_plan_id,
                approval_lock_id=approval_lock.lock_id,
                approval_valid=True,
                model=execution_plan.model,
                duration_s=execution_plan.duration_s,
                aspect_ratio=execution_plan.aspect_ratio,
                resolution=execution_plan.resolution,
            ),
            rendered_segments=[
                SegmentRenderResult(
                    shot_id="shot_1",
                    index=0,
                    status="completed",
                    video_url="http://127.0.0.1:3000/output.mp4",
                    duration_s=8,
                    model=execution_plan.model,
                )
            ],
            qa_reports=[],
            message="Render completed safely.",
        )


def test_benchmark_runner_records_completed_render_evidence() -> None:
    plan = SeedanceExecutionPlan(
        execution_plan_id="exec_benchmark_runner",
        duration_s=8,
        compiled_prompt="Subject: product\nAction: demo\nCamera: static\nTiming: Duration: 8s",
        model="seedance_2_0",
        shots=[
            SeedanceShotPlan(
                shot_id="shot_1",
                index=0,
                duration_s=8,
                compiled_prompt="Subject: product\nAction: demo\nCamera: static\nTiming: Duration: 8s",
                model="seedance_2_0",
            )
        ],
    )
    case = BenchmarkRenderCase(
        case_id="case_beauty_001",
        idea="show the product clearly",
        niche="beauty",
        runtime_class="short",
        execution_plan=plan,
    )

    result = BenchmarkRenderRunner(render_executor=_CompletedRenderExecutor()).run_case(case)  # type: ignore[arg-type]

    assert result.render_status == "completed"
    assert result.evidence.verdict == "usable"
    assert result.evidence.output_url == "https://cdn.example.com/output.mp4"
    assert result.evidence.niche == "beauty"
    assert result.evidence.model == "seedance_2_0"


def test_benchmark_runner_marks_completed_local_output_as_failed_evidence() -> None:
    plan = SeedanceExecutionPlan(
        execution_plan_id="exec_benchmark_local_output",
        duration_s=8,
        compiled_prompt="Subject: product\nAction: demo\nCamera: static\nTiming: Duration: 8s",
        model="seedance_2_0",
        shots=[
            SeedanceShotPlan(
                shot_id="shot_1",
                index=0,
                duration_s=8,
                compiled_prompt="Subject: product\nAction: demo\nCamera: static\nTiming: Duration: 8s",
                model="seedance_2_0",
            )
        ],
    )
    case = BenchmarkRenderCase(
        case_id="case_beauty_local_output",
        idea="show the product clearly",
        niche="beauty",
        runtime_class="short",
        execution_plan=plan,
    )

    result = BenchmarkRenderRunner(render_executor=_CompletedLocalOutputRenderExecutor()).run_case(case)  # type: ignore[arg-type]

    assert result.render_status == "completed"
    assert result.evidence.verdict == "failed"
    assert result.evidence.output_url is None
    assert "HTTP(S) output URL" in (result.evidence.failure_reason or "")


def test_benchmark_runner_marks_completed_loopback_output_as_failed_evidence() -> None:
    plan = SeedanceExecutionPlan(
        execution_plan_id="exec_benchmark_loopback_output",
        duration_s=8,
        compiled_prompt="Subject: product\nAction: demo\nCamera: static\nTiming: Duration: 8s",
        model="seedance_2_0",
        shots=[
            SeedanceShotPlan(
                shot_id="shot_1",
                index=0,
                duration_s=8,
                compiled_prompt="Subject: product\nAction: demo\nCamera: static\nTiming: Duration: 8s",
                model="seedance_2_0",
            )
        ],
    )
    case = BenchmarkRenderCase(
        case_id="case_beauty_loopback_output",
        idea="show the product clearly",
        niche="beauty",
        runtime_class="short",
        execution_plan=plan,
    )

    result = BenchmarkRenderRunner(render_executor=_CompletedLoopbackOutputRenderExecutor()).run_case(case)  # type: ignore[arg-type]

    assert result.render_status == "completed"
    assert result.evidence.verdict == "failed"
    assert result.evidence.output_url is None
    assert "HTTP(S) output URL" in (result.evidence.failure_reason or "")
