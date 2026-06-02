"""Phase 5 regression tests for render dry-run reporting."""
from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_render_dry_run_report_contains_payload_references_and_provenance() -> None:
    """Dry-run should expose the exact non-vendor payload review surface."""
    from workers.render_dry_run import RenderDryRunService

    idea, execution_plan, approval_lock = _plan_and_lock()
    verification = approval_lock.verify_against(idea=idea, execution_plan=execution_plan)

    report = RenderDryRunService().generate_dry_run_report(
        execution_plan=execution_plan,
        approval_lock=approval_lock,
        approval_verification=verification,
    )

    assert report.approval_valid is True
    assert report.model == "seedance_2_0"
    assert report.duration_s == 12
    assert report.aspect_ratio == "9:16"
    assert report.resolution == "1080p"
    assert report.cost_estimate["total_cost_usd"] == 0.72
    assert len(report.shot_payloads) == 2
    assert report.shot_payloads[0].payload["images"] == ["https://cdn.test/serum.png"]
    assert report.shot_payloads[0].payload["return_last_frame"] is True
    assert report.references[0]["role"] == "product_hero"
    assert "lanshu.storyboard_3_5_shot.v1" in report.knowledge_rule_ids
    assert "zerolu_perfume_multiref_ad_15s" in report.curated_example_ids


def test_render_dry_run_report_can_show_approval_mismatch_without_rendering() -> None:
    """A mismatch verification should be visible in the dry-run report."""
    from workers.render_dry_run import RenderDryRunService

    idea, execution_plan, approval_lock = _plan_and_lock()
    tampered = execution_plan.model_copy(update={
        "compiled_prompt": execution_plan.compiled_prompt + "\nUnapproved extra instruction.",
    })
    verification = approval_lock.verify_against(idea=idea, execution_plan=tampered)

    report = RenderDryRunService().generate_dry_run_report(
        execution_plan=tampered,
        approval_lock=approval_lock,
        approval_verification=verification,
    )

    assert report.approval_valid is False
    assert report.approval_verification is not None
    assert "compiled_prompt_hash" in report.approval_verification.mismatched_fields
    assert report.shot_payloads


def _plan_and_lock():
    from pipeline.approval_lock import ApprovalLock
    from pipeline.contracts import AssetRef, ReferenceRole, SeedanceExecutionPlan, SeedanceShotPlan

    idea = "Create a 12s serum product ad"
    product_ref = AssetRef(
        asset_id="asset_serum",
        kind="image",
        url="https://cdn.test/serum.png",
        tag="@Image1",
        role=ReferenceRole.PRODUCT_HERO,
        name="Serum bottle",
    )
    shots = [
        SeedanceShotPlan(
            shot_id="shot_0",
            index=0,
            duration_s=6,
            compiled_prompt="Subject: serum bottle with pearl cap\nAction: macro reveal\nCamera: static macro",
            model="seedance_2_0",
            resolution="1080p",
            references=[product_ref],
            rules_applied=["lanshu.storyboard_3_5_shot.v1"],
            examples_used=["zerolu_perfume_multiref_ad_15s"],
        ),
        SeedanceShotPlan(
            shot_id="shot_1",
            index=1,
            duration_s=6,
            compiled_prompt="Subject: serum bottle with pearl cap\nAction: hero payoff\nCamera: slow push-in",
            model="seedance_2_0",
            resolution="1080p",
            references=[product_ref],
            rules_applied=["lanshu.negative_constraints.v1"],
            examples_used=["zerolu_perfume_multiref_ad_15s"],
        ),
    ]
    execution_plan = SeedanceExecutionPlan(
        model="seedance_2_0",
        duration_s=12,
        aspect_ratio="9:16",
        resolution="1080p",
        compiled_prompt="\n\n".join(shot.compiled_prompt for shot in shots),
        shots=shots,
        reference_assets=[product_ref],
        cost_estimate={"total_cost_usd": 0.72, "render_cost_usd": 0.72},
        rules_applied=["lanshu.storyboard_3_5_shot.v1"],
        examples_used=["zerolu_perfume_multiref_ad_15s"],
        linter_warnings=[],
        metadata={
            "knowledge_rule_ids": ["dexhunter.reference_role_assignment.v1"],
            "curated_example_ids": ["zerolu_perfume_multiref_ad_15s"],
        },
    )
    approval_lock = ApprovalLock.from_execution_plan(
        idea=idea,
        execution_plan=execution_plan,
        approved_by="phase5-test",
        approval_source="dry_run_preview",
    )
    return idea, execution_plan, approval_lock
