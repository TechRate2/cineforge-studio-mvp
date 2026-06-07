from pipeline.approval_lock import ApprovalLock
from pipeline.contracts import AssetRef, ReferenceRole, SeedanceExecutionPlan, SeedanceShotPlan
from workers.render_dry_run import RenderDryRunService


def test_dry_run_report_surfaces_reference_intelligence_blockers() -> None:
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
        reference_assets=plan.reference_assets,
        approved_by="pytest",
        approval_source="dry_run_preview",
    )

    report = RenderDryRunService().generate_dry_run_report(
        execution_plan=plan,
        approval_lock=approval_lock,
    )

    assert report.reference_intelligence["status"] == "blocked"
    assert report.hard_failures
    assert any("reference_asset_blocked:asset_product_missing_url" in item for item in report.hard_failures)
    assert report.references[0]["asset_id"] == "asset_product_missing_url"
