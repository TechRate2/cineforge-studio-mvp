from pipeline.approval_lock import ApprovalLock
from pipeline.contracts import AssetRef, ReferenceRole, SeedanceExecutionPlan, SeedanceShotPlan
from workers.render_dry_run import RenderDryRunService


class _FailingRenderer:
    """Renderer spy that fails if the paid vendor path is reached."""

    def __init__(self) -> None:
        self.called = False

    def render_segment(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        self.called = True
        raise AssertionError("Segment renderer must not be called when Reference Intelligence blocks render.")


def test_dry_run_report_surfaces_reference_intelligence_blockers() -> None:
    plan, approval_lock = _blocked_reference_plan_and_lock()

    report = RenderDryRunService().generate_dry_run_report(
        execution_plan=plan,
        approval_lock=approval_lock,
    )

    assert report.reference_intelligence["status"] == "blocked"
    assert report.hard_failures
    assert any("reference_asset_blocked:asset_product_missing_url" in item for item in report.hard_failures)
    assert report.references[0]["asset_id"] == "asset_product_missing_url"


def test_render_executor_rejects_reference_hard_failures_before_paid_vendor_call() -> None:
    from pipeline.render_execution import RenderExecutor

    plan, approval_lock = _blocked_reference_plan_and_lock()
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
    assert result.dry_run_report.hard_failures
    assert "Dry-run hard failures rejected paid render" in result.message
    assert any("reference_asset_blocked:asset_product_missing_url" in item for item in result.dry_run_report.hard_failures)
    assert renderer.called is False


def _blocked_reference_plan_and_lock() -> tuple[SeedanceExecutionPlan, ApprovalLock]:
    product_ref = AssetRef(
        asset_id="asset_product_missing_url",
        kind="image",
        url="",
        tag="@image_1",
        role=ReferenceRole.PRODUCT_HERO,
        role_locked=True,
        role_confidence=0.95,
    )
    shot = SeedanceShotPlan(
        shot_id="shot_1",
        index=0,
        duration_s=8,
        compiled_prompt="Subject: product\nAction: demo\nCamera: static\nTiming: Duration: 8s",
        model="seedance_2_0",
        references=[product_ref],
        metadata={"needs_product_consistency": True},
    )
    plan = SeedanceExecutionPlan(
        execution_plan_id="exec_dry_run_reference_intelligence",
        duration_s=8,
        compiled_prompt=shot.compiled_prompt,
        model="seedance_2_0",
        shots=[shot],
        reference_assets=[product_ref],
        metadata={"approved_idea": "show the product clearly", "needs_product_consistency": True},
    )
    approval_lock = ApprovalLock.from_execution_plan(
        idea="show the product clearly",
        execution_plan=plan,
        approved_by="pytest",
        approval_source="dry_run_preview",
    )
    return plan, approval_lock
