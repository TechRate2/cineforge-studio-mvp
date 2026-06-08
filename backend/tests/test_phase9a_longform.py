"""Phase 9A tests for long-form segmented rendering MVP."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


class LongFormRecordingClient:
    """No-network render client with one configurable segment-2 QA failure."""

    def __init__(self, *, fail_segment_2_once: bool = False, force_video_url: str | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.fail_segment_2_once = fail_segment_2_once
        self.force_video_url = force_video_url
        self.segment_2_failed = False

    def generate_video(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(dict(kwargs))
        prompt = str(kwargs.get("prompt") or "").lower()
        call_index = len(self.calls)
        is_segment_2 = "segment 2/" in prompt
        if self.fail_segment_2_once and is_segment_2 and not self.segment_2_failed:
            self.segment_2_failed = True
            return {
                "prediction_id": f"pred_{call_index}",
                "video_url": f"https://cdn.test/video_{call_index}.mp4",
                "last_frame_url": f"https://cdn.test/last_{call_index}.jpg",
                "duration_s": kwargs.get("duration_s"),
                "model": kwargs.get("model_key"),
                "qa_signals": {"force_fail": True},
            }
        return {
            "prediction_id": f"pred_{call_index}",
            "video_url": self.force_video_url or f"https://cdn.test/video_{call_index}.mp4",
            "last_frame_url": f"https://cdn.test/last_{call_index}.jpg",
            "duration_s": kwargs.get("duration_s"),
            "model": kwargs.get("model_key"),
            "qa_signals": {"product_visibility": 0.9, "logo_label_similarity": 0.9, "style_similarity": 0.9},
        }


def test_phase9a_longform_planner_splits_45s_into_linear_segments() -> None:
    """LongFormPlanner should create 10-12s linear segments with handoff state."""
    longform_plan, _, _, _ = _compiled_longform_plan(duration_s=45)

    assert longform_plan.total_duration_s == 45
    assert [segment.duration_s for segment in longform_plan.segments] == [12, 11, 11, 11]
    assert len(longform_plan.segment_graph) == 4
    assert longform_plan.segment_graph[0].previous_segment_id is None
    assert longform_plan.segment_graph[1].previous_segment_id == longform_plan.segments[0].segment_id
    for segment in longform_plan.segments:
        assert segment.entry_state
        assert segment.exit_state
        assert segment.last_frame_anchor
        assert segment.identity_bible_snapshot
        assert segment.handoff_requirements


def test_phase9a_segment_prompt_compiler_builds_master_approval_plan() -> None:
    """Compiled long-form plans should carry one master plan for ApprovalLock."""
    longform_plan, _, _, _ = _compiled_longform_plan(duration_s=60)

    assert longform_plan.master_execution_plan is not None
    assert longform_plan.master_execution_plan.duration_s == 60
    assert len(longform_plan.master_execution_plan.shots) == 5
    assert longform_plan.master_execution_plan.metadata["segment_graph_hash"] == longform_plan.segment_graph_hash
    assert (
        longform_plan.master_execution_plan.metadata["continuity_bible_hash"]
        == longform_plan.continuity_bible.continuity_hash
    )


def test_phase9a_longform_approval_lock_rejects_tampered_graph_before_vendor_call() -> None:
    """One ApprovalLock should protect the graph hash and continuity bible hash."""
    from workers.longform_render_executor import LongFormRenderExecutor
    from workers.segment_renderer import SegmentRenderer

    longform_plan, idea, lock, _ = _compiled_longform_plan(duration_s=45)
    assert longform_plan.master_execution_plan is not None
    tampered_master = longform_plan.master_execution_plan.model_copy(update={
        "metadata": {
            **longform_plan.master_execution_plan.metadata,
            "segment_graph_hash": "tampered",
        }
    })
    tampered_plan = longform_plan.model_copy(update={"master_execution_plan": tampered_master})
    client = LongFormRecordingClient()

    result = LongFormRenderExecutor(
        render_executor=_render_executor_for_client(client),
    ).execute(
        longform_plan=tampered_plan,
        approval_lock=lock,
        idea=idea,
        dry_run_approved=True,
    )

    assert result.status == "rejected"
    assert "execution_plan_hash" in result.approval_verification.mismatched_fields
    assert client.calls == []


def test_phase9a_longform_auto_repair_rerenders_only_failed_segment() -> None:
    """Auto-repair should retry the failed segment without rerendering earlier segments."""
    from workers.longform_render_executor import LongFormRenderExecutor

    longform_plan, idea, lock, _ = _compiled_longform_plan(duration_s=45)
    client = LongFormRecordingClient(fail_segment_2_once=True)

    result = LongFormRenderExecutor(
        render_executor=_render_executor_for_client(client),
        max_auto_repair_attempts=1,
    ).execute(
        longform_plan=longform_plan,
        approval_lock=lock,
        idea=idea,
        dry_run_approved=True,
    )

    assert result.status == "completed"
    assert result.repair_attempts_by_segment["segment_02"] == 1
    assert len(client.calls) == len(longform_plan.segments) + 1
    segment_1_calls = [call for call in client.calls if "segment 1/" in str(call.get("prompt") or "").lower()]
    segment_2_calls = [call for call in client.calls if "segment 2/" in str(call.get("prompt") or "").lower()]
    assert len(segment_1_calls) == 1
    assert len(segment_2_calls) == 2
    assert client.calls[0]["model_key"] == "seedance_2_0_fast"
    assert client.calls[2]["images"] == ["https://cdn.test/last_1.jpg"]


def test_phase9a_longform_requires_dry_run_approval_before_paid_render() -> None:
    """Paid segmented render should be blocked until dry-run approval is explicit."""
    from workers.longform_render_executor import LongFormRenderExecutor

    longform_plan, idea, lock, _ = _compiled_longform_plan(duration_s=30, dry_run_approved=False)
    client = LongFormRecordingClient()

    result = LongFormRenderExecutor(
        render_executor=_render_executor_for_client(client),
    ).execute(
        longform_plan=longform_plan,
        approval_lock=lock,
        idea=idea,
    )

    assert result.status == "rejected"
    assert "dry-run approval" in result.message.lower()
    assert client.calls == []


def test_phase9a_longform_rejects_dry_run_hard_failures_before_vendor_call() -> None:
    """Reference Intelligence blockers from dry-run should stop long-form paid render."""
    from workers.longform_render_executor import LongFormRenderExecutor

    longform_plan, idea, _, _ = _compiled_longform_plan(duration_s=30)
    assert longform_plan.master_execution_plan is not None
    master_plan = longform_plan.master_execution_plan
    blocked_asset = master_plan.reference_assets[0].model_copy(update={"url": ""})
    assets = [blocked_asset, *master_plan.reference_assets[1:]]
    shots = [
        shot.model_copy(update={
            "references": [
                blocked_asset if ref.asset_id == blocked_asset.asset_id else ref
                for ref in shot.references
            ]
        })
        for shot in master_plan.shots
    ]
    blocked_master = master_plan.model_copy(update={"reference_assets": assets, "shots": shots})
    blocked_plan = longform_plan.model_copy(update={"master_execution_plan": blocked_master})
    lock = _approval_lock_for_longform_plan(blocked_plan, idea)
    client = LongFormRecordingClient()

    result = LongFormRenderExecutor(
        render_executor=_render_executor_for_client(client),
    ).execute(
        longform_plan=blocked_plan,
        approval_lock=lock,
        idea=idea,
        dry_run_approved=True,
    )

    assert result.status == "rejected"
    assert result.approval_verification.valid is True
    assert result.dry_run_report.hard_failures
    assert "Dry-run hard failures rejected paid render" in result.message
    assert client.calls == []


def test_phase9a_longform_rejects_seedance_preflight_before_vendor_call() -> None:
    """Compiler hard failures should stop long-form paid render before any segment call."""
    from workers.longform_render_executor import LongFormRenderExecutor

    longform_plan, idea, _, _ = _compiled_longform_plan(duration_s=30)
    assert longform_plan.master_execution_plan is not None
    master_plan = longform_plan.master_execution_plan
    rejected_master = master_plan.model_copy(update={
        "metadata": {
            **master_plan.metadata,
            "seedance_preflight": {
                "status": "fail",
                "hard_failures": ["seedance.basic.missing_camera: Prompt is missing a clear Camera field."],
                "warnings": [],
            },
        }
    })
    rejected_plan = longform_plan.model_copy(update={"master_execution_plan": rejected_master})
    lock = _approval_lock_for_longform_plan(rejected_plan, idea)
    client = LongFormRecordingClient()

    result = LongFormRenderExecutor(
        render_executor=_render_executor_for_client(client),
    ).execute(
        longform_plan=rejected_plan,
        approval_lock=lock,
        idea=idea,
        dry_run_approved=True,
    )

    assert result.status == "rejected"
    assert result.approval_verification.valid is True
    assert "Seedance preflight rejected paid render" in result.message
    assert client.calls == []


def test_phase9a_longform_cost_gate_rejects_before_vendor_call() -> None:
    """Long-form render should honor the same budget cap before segmented vendor spend."""
    from workers.longform_render_executor import LongFormRenderExecutor

    longform_plan, idea, lock, _ = _compiled_longform_plan(duration_s=30)
    client = LongFormRecordingClient()

    result = LongFormRenderExecutor(
        render_executor=_render_executor_for_client(client),
    ).execute(
        longform_plan=longform_plan,
        approval_lock=lock,
        idea=idea,
        dry_run_approved=True,
        max_total_cost_usd=0.01,
    )

    assert result.status == "cost_rejected"
    assert result.cost_gate is not None
    assert result.cost_gate.should_render is False
    assert client.calls == []


def test_phase9a_longform_rejects_completed_segment_without_http_output() -> None:
    """Segmented render should not treat local/stub outputs as completed video."""
    from workers.longform_render_executor import LongFormRenderExecutor

    longform_plan, idea, lock, _ = _compiled_longform_plan(duration_s=30)
    client = LongFormRecordingClient(force_video_url="file:///tmp/local-segment.mp4")

    result = LongFormRenderExecutor(
        render_executor=_render_executor_for_client(client),
        max_auto_repair_attempts=1,
    ).execute(
        longform_plan=longform_plan,
        approval_lock=lock,
        idea=idea,
        dry_run_approved=True,
    )

    assert result.status == "render_failed"
    assert result.rendered_segments[0].status == "failed"
    assert result.rendered_segments[0].error_code == "missing_deliverable_video_url"
    assert result.repair_attempts_by_segment == {"segment_01": 0}
    assert len(client.calls) == 1


def _compiled_longform_plan(*, duration_s: int, dry_run_approved: bool = True):
    from longform.longform_planner import LongFormPlanner
    from longform.segment_prompt_compiler import SegmentPromptCompiler
    from pipeline.approval_lock import ApprovalLock
    from pipeline.contracts import AssetRef, InputContract, ReferenceRole
    from pipeline.creative_planning import CreativePlanner
    from pipeline.input_analysis import InputAnalyzer

    idea = f"Create a {duration_s}s beauty serum product film with macro hook, proof sequence, and payoff."
    analyzed = InputAnalyzer().analyze(InputContract(
        user_idea=idea,
        duration_hint_s=duration_s,
        assets=[
            AssetRef(
                asset_id="asset_serum_hero",
                kind="image",
                url="https://cdn.test/serum.png",
                tag="@Image1",
                role=ReferenceRole.PRODUCT_HERO,
                notes="serum bottle product packaging label hero",
            ),
            AssetRef(
                asset_id="asset_serum_detail",
                kind="image",
                url="https://cdn.test/serum_detail.png",
                tag="@Image2",
                role=ReferenceRole.PRODUCT_DETAIL,
                notes="serum bottle label detail package shape",
            ),
        ],
    ))
    creative_plan = CreativePlanner().plan(analyzed)
    longform_plan = LongFormPlanner().plan(creative_plan=creative_plan, analyzed_input=analyzed)
    longform_plan = SegmentPromptCompiler().compile(
        longform_plan=longform_plan,
        creative_plan=creative_plan,
        analyzed_input=analyzed,
    )
    assert longform_plan.master_execution_plan is not None
    action = str(longform_plan.master_execution_plan.metadata.get("consistency_policy_action") or "")
    metadata: dict[str, Any] = {
        "approved_idea": analyzed.normalized_idea,
        "longform_plan_id": longform_plan.longform_plan_id,
        "longform_dry_run_approved": dry_run_approved,
        "segment_graph_hash": longform_plan.segment_graph_hash,
        "continuity_bible_hash": longform_plan.continuity_bible.continuity_hash,
    }
    if action == "requires_review":
        metadata.update({
            "consistency_review_approved": True,
            "consistency_review_approved_policy_action": "requires_review",
        })
    lock = ApprovalLock.from_execution_plan(
        idea=analyzed.normalized_idea,
        execution_plan=longform_plan.master_execution_plan,
        reference_assets=longform_plan.master_execution_plan.reference_assets,
        cost_estimate=longform_plan.master_execution_plan.cost_estimate,
        approved_by="tester",
        approval_source="longform_dry_run_preview",
        metadata=metadata,
    )
    return longform_plan, analyzed.normalized_idea, lock, creative_plan


def _approval_lock_for_longform_plan(longform_plan, idea: str, *, dry_run_approved: bool = True):
    from pipeline.approval_lock import ApprovalLock

    assert longform_plan.master_execution_plan is not None
    action = str(longform_plan.master_execution_plan.metadata.get("consistency_policy_action") or "")
    metadata: dict[str, Any] = {
        "approved_idea": idea,
        "longform_plan_id": longform_plan.longform_plan_id,
        "longform_dry_run_approved": dry_run_approved,
        "segment_graph_hash": longform_plan.segment_graph_hash,
        "continuity_bible_hash": longform_plan.continuity_bible.continuity_hash,
    }
    if action == "requires_review":
        metadata.update({
            "consistency_review_approved": True,
            "consistency_review_approved_policy_action": "requires_review",
        })
    return ApprovalLock.from_execution_plan(
        idea=idea,
        execution_plan=longform_plan.master_execution_plan,
        reference_assets=longform_plan.master_execution_plan.reference_assets,
        cost_estimate=longform_plan.master_execution_plan.cost_estimate,
        approved_by="tester",
        approval_source="longform_dry_run_preview",
        metadata=metadata,
    )


def _render_executor_for_client(client: LongFormRecordingClient):
    from pipeline.render_execution import RenderExecutor
    from workers.segment_renderer import SegmentRenderer

    return RenderExecutor(
        segment_renderer=SegmentRenderer(client, max_attempts=1, backoff_initial_s=0.0),
        qa_service=_NoProbeQAService(),
    )


class _NoProbeQAService:
    """Keep long-form render tests focused on retry orchestration, not CV probing."""

    def evaluate_segment(self, *, shot: Any, result: Any):
        from workers.render_qa_service import SegmentQAReport

        errors: list[str] = []
        warnings: list[str] = []
        if result.status != "completed":
            errors.append(result.error_code or "segment_render_failed")
        if not result.video_url:
            errors.append("missing_video_url")
        if (result.qa_signals or {}).get("force_fail"):
            errors.append("forced_segment_qa_failure")
        if result.duration_s is None:
            warnings.append("missing_duration_metadata")
        return SegmentQAReport(
            shot_id=shot.shot_id,
            status="fail" if errors else ("warn" if warnings else "pass"),
            warnings=warnings,
            errors=errors,
            expected_duration_s=shot.duration_s,
            actual_duration_s=result.duration_s,
            expected_resolution=shot.resolution,
            actual_resolution=None,
        )
