from pipeline.approval_lock import ApprovalLock
from pipeline.contracts import SeedanceExecutionPlan, SeedanceShotPlan
from pipeline.render_execution import RenderExecutor


class _FailingRenderer:
    """Renderer spy that fails the test if a vendor render path is reached."""

    def __init__(self) -> None:
        self.called = False

    def render_segment(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        self.called = True
        raise AssertionError("Segment renderer must not be called when Seedance preflight fails.")


def test_render_executor_rejects_failed_seedance_preflight_before_vendor_call() -> None:
    shot = SeedanceShotPlan(
        shot_id="shot_preflight_fail",
        index=0,
        duration_s=8,
        compiled_prompt="Subject: product\nAction: demo\nCamera: static\nTiming: Duration: 8s",
        model="seedance_2_0",
        metadata={
            "seedance_preflight": {
                "status": "fail",
                "hard_failures": ["seedance.basic.missing_camera: Prompt is missing a clear Camera field."],
                "warnings": [],
            }
        },
    )
    plan = SeedanceExecutionPlan(
        execution_plan_id="seedance_exec_preflight_fail_full_path",
        duration_s=8,
        compiled_prompt=shot.compiled_prompt,
        model="seedance_2_0",
        shots=[shot],
        metadata={
            "approved_idea": "show the product clearly",
            "seedance_preflight": {
                "status": "fail",
                "hard_failures": ["seedance.basic.missing_camera: Prompt is missing a clear Camera field."],
                "warnings": [],
            },
        },
    )
    approval_lock = ApprovalLock.from_execution_plan(
        idea="show the product clearly",
        execution_plan=plan,
        approved_by="pytest",
        approval_source="dry_run_preview",
    )
    renderer = _FailingRenderer()
    executor = RenderExecutor(segment_renderer=renderer)  # type: ignore[arg-type]

    result = executor.execute(
        execution_plan=plan,
        approval_lock=approval_lock,
        idea="show the product clearly",
        dry_run_only=False,
    )

    assert result.status == "rejected"
    assert result.approval_verification.valid is True
    assert "Seedance preflight rejected paid render" in result.message
    assert renderer.called is False
