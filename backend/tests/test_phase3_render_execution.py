"""Phase 3 tests for safe render execution and dry-run reporting."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


class FakeRenderClient:
    """No-network AtlasCloud stand-in for Phase 3 tests."""

    def __init__(self, *, fail_video_url: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self.fail_video_url = fail_video_url

    def generate_video(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(dict(kwargs))
        index = len(self.calls)
        return {
            "prediction_id": f"pred_{index}",
            "video_url": None if self.fail_video_url else f"https://cdn.test/video_{index}.mp4",
            "last_frame_url": f"https://cdn.test/last_{index}.jpg",
            "duration_s": kwargs.get("duration_s"),
            "model": kwargs.get("model_key"),
        }


def test_phase3_dry_run_report_contains_payloads_and_provenance() -> None:
    """Dry-run should expose render payloads without calling a vendor."""
    from pipeline.render_execution import RenderExecutor
    from workers.segment_renderer import SegmentRenderer

    idea, plan, lock = _execution_plan_and_lock()
    fake = FakeRenderClient()
    result = RenderExecutor(segment_renderer=SegmentRenderer(fake)).execute(
        execution_plan=plan,
        approval_lock=lock,
        idea=idea,
        dry_run_only=True,
    )

    assert result.status == "dry_run"
    assert fake.calls == []
    assert result.dry_run_report.approval_valid is True
    assert len(result.dry_run_report.shot_payloads) == 2
    assert "phase2.storyboard.reference_bindings" in result.dry_run_report.knowledge_rule_ids
    assert "zerolu_perfume_multiref_ad_15s" in result.dry_run_report.curated_example_ids
    assert result.dry_run_report.shot_payloads[0].payload["model_key"] == "seedance_2_0"


def test_phase3_approval_lock_mismatch_rejects_before_vendor_call() -> None:
    """ApprovalLock mismatch must prevent every paid render call."""
    from pipeline.render_execution import RenderExecutor
    from workers.segment_renderer import SegmentRenderer

    idea, plan, lock = _execution_plan_and_lock()
    tampered = plan.model_copy(update={"compiled_prompt": plan.compiled_prompt + "\nextra unapproved prompt"})
    fake = FakeRenderClient()

    result = RenderExecutor(segment_renderer=SegmentRenderer(fake)).execute(
        execution_plan=tampered,
        approval_lock=lock,
        idea=idea,
    )

    assert result.status == "rejected"
    assert "compiled_prompt_hash" in result.approval_verification.mismatched_fields
    assert fake.calls == []


def test_phase3_cost_gate_can_reject_before_vendor_call() -> None:
    """CostControlService should block render before vendor spend when over budget."""
    from pipeline.render_execution import RenderExecutor
    from workers.segment_renderer import SegmentRenderer

    idea, plan, lock = _execution_plan_and_lock()
    fake = FakeRenderClient()
    result = RenderExecutor(segment_renderer=SegmentRenderer(fake)).execute(
        execution_plan=plan,
        approval_lock=lock,
        idea=idea,
        max_total_cost_usd=0.01,
    )

    assert result.status == "cost_rejected"
    assert result.cost_gate is not None
    assert result.cost_gate.should_render is False
    assert fake.calls == []


def test_phase3_draft_first_renders_then_chains_last_frame() -> None:
    """Draft-first should render a draft, then full segments with last-frame chaining."""
    from pipeline.render_execution import RenderExecutor
    from workers.segment_renderer import SegmentRenderer

    idea, plan, lock = _execution_plan_and_lock()
    fake = FakeRenderClient()
    result = RenderExecutor(segment_renderer=SegmentRenderer(fake)).execute(
        execution_plan=plan,
        approval_lock=lock,
        idea=idea,
        cost_gate_mode="draft_first",
    )

    assert result.status == "completed"
    assert result.cost_gate is not None
    assert result.cost_gate.draft_shot_id == "shot_1"
    assert len(fake.calls) == 3
    assert fake.calls[0]["model_key"] == "seedance_2_0_fast"
    assert fake.calls[2]["image"] == "https://cdn.test/last_2.jpg"
    assert all(report.status == "pass" for report in result.qa_reports)


def _execution_plan_and_lock():
    from pipeline.approval_lock import ApprovalLock
    from pipeline.contracts import AssetRef, ReferenceRole, SeedanceExecutionPlan, SeedanceShotPlan

    idea = "Create a 12s perfume product ad"
    product_ref = AssetRef(
        asset_id="asset_product",
        kind="image",
        url="https://cdn.test/perfume.png",
        tag="@Image1",
        role=ReferenceRole.PRODUCT_HERO,
        name="Perfume hero",
    )
    shots = [
        SeedanceShotPlan(
            shot_id="shot_1",
            index=0,
            duration_s=6,
            compiled_prompt="Subject: glass perfume bottle\nAction: macro reveal\nCamera: static macro",
            model="seedance_2_0",
            resolution="1080p",
            references=[product_ref],
            rules_applied=["phase2.storyboard.reference_bindings"],
            examples_used=["zerolu_perfume_multiref_ad_15s"],
        ),
        SeedanceShotPlan(
            shot_id="shot_2",
            index=1,
            duration_s=6,
            compiled_prompt="Subject: glass perfume bottle\nAction: hero product payoff\nCamera: slow push-in",
            model="seedance_2_0",
            resolution="1080p",
            references=[product_ref],
            rules_applied=["phase2.storyboard.continuity_notes"],
            examples_used=["zerolu_perfume_multiref_ad_15s"],
        ),
    ]
    plan = SeedanceExecutionPlan(
        model="seedance_2_0",
        duration_s=12,
        aspect_ratio="9:16",
        resolution="1080p",
        compiled_prompt="\n\n".join(shot.compiled_prompt for shot in shots),
        shots=shots,
        reference_assets=[product_ref],
        cost_estimate={"render_cost_usd": 0.72, "total_cost_usd": 0.72},
        rules_applied=["phase2.storyboard.reference_bindings"],
        examples_used=["zerolu_perfume_multiref_ad_15s"],
        metadata={"approved_idea": idea},
    )
    lock = ApprovalLock.from_execution_plan(
        idea=idea,
        execution_plan=plan,
        approved_by="tester",
        approval_source="dry_run_preview",
        metadata={"approved_idea": idea},
    )
    return idea, plan, lock
