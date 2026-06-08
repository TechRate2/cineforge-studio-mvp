from __future__ import annotations

from typing import Any

from pipeline.approval_lock import ApprovalLock
from pipeline.contracts import AssetRef, ReferenceRole, SeedanceExecutionPlan, SeedanceShotPlan
from pipeline.render_execution import RenderExecutor


class RendererSpy:
    """Renderer spy that records whether the paid path was reached."""

    def __init__(self) -> None:
        self.called = False

    def render_segment(self, **kwargs: Any) -> Any:
        self.called = True
        raise AssertionError("renderer must not be called when dry-run hard failures exist")


def test_render_executor_rejects_dry_run_hard_failures_before_renderer() -> None:
    plan, approval_lock = _plan_with_blocked_reference()
    renderer = RendererSpy()

    result = RenderExecutor(segment_renderer=renderer).execute(  # type: ignore[arg-type]
        execution_plan=plan,
        approval_lock=approval_lock,
        idea="show the serum product clearly",
        dry_run_only=False,
    )

    assert result.status == "rejected"
    assert result.approval_verification.valid is True
    assert result.dry_run_report.hard_failures
    assert any("reference_asset_blocked" in failure for failure in result.dry_run_report.hard_failures)
    assert "Dry-run hard failures rejected paid render" in result.message
    assert renderer.called is False


def _plan_with_blocked_reference() -> tuple[SeedanceExecutionPlan, ApprovalLock]:
    asset = AssetRef(
        asset_id="asset_missing_product_url",
        kind="image",
        url="",
        tag="@image_1",
        role=ReferenceRole.PRODUCT_HERO,
        role_locked=True,
        role_confidence=0.98,
    )
    shot = SeedanceShotPlan(
        shot_id="shot_blocked_reference",
        index=0,
        duration_s=8,
        compiled_prompt="Subject: serum product\nAction: hero reveal\nScene: clean studio\nCamera: slow push in\nTiming: 8s",
        model="seedance_2_0",
        aspect_ratio="9:16",
        references=[asset],
        metadata={"needs_product_consistency": True},
    )
    plan = SeedanceExecutionPlan(
        execution_plan_id="exec_blocked_reference",
        duration_s=8,
        compiled_prompt=shot.compiled_prompt,
        model="seedance_2_0",
        aspect_ratio="9:16",
        shots=[shot],
        reference_assets=[asset],
        metadata={
            "approved_idea": "show the serum product clearly",
            "needs_product_consistency": True,
        },
    )
    lock = ApprovalLock.from_execution_plan(
        idea="show the serum product clearly",
        execution_plan=plan,
        approved_by="pytest",
        approval_source="dry_run_preview",
        metadata={"approved_idea": "show the serum product clearly"},
    )
    return plan, lock
