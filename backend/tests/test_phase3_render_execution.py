"""Phase 3 tests for safe render execution and dry-run reporting."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


class RecordingRenderClient:
    """Deterministic no-network vendor client used only by render safety tests."""

    def __init__(
        self,
        *,
        fail_video_url: bool = False,
        video_url: str | None = None,
        last_frame_url: str | None = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self.fail_video_url = fail_video_url
        self.video_url = video_url
        self.last_frame_url = last_frame_url

    def generate_video(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(dict(kwargs))
        index = len(self.calls)
        return {
            "prediction_id": f"pred_{index}",
            "video_url": None if self.fail_video_url else (self.video_url or f"https://cdn.test/video_{index}.mp4"),
            "last_frame_url": self.last_frame_url or f"https://cdn.test/last_{index}.jpg",
            "duration_s": kwargs.get("duration_s"),
            "model": kwargs.get("model_key"),
        }


class QARecordingRenderClient(RecordingRenderClient):
    """Render client returning deterministic post-render QA signals."""

    def __init__(self, *, qa_signals: dict[str, Any]) -> None:
        super().__init__()
        self.qa_signals = qa_signals

    def generate_video(self, **kwargs: Any) -> dict[str, Any]:
        result = super().generate_video(**kwargs)
        result["qa_signals"] = dict(self.qa_signals)
        return result


class RaisingRenderClient:
    """Vendor client that raises on every call to verify retry/error mapping."""

    def __init__(self, message: str = "429 rate limit") -> None:
        self.calls: list[dict[str, Any]] = []
        self.message = message

    def generate_video(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(dict(kwargs))
        raise RuntimeError(self.message)


class CompletedLocalOutputRenderer:
    """Renderer test double that tries to mark a local path as completed output."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def render_segment(self, **kwargs: Any):
        from workers.segment_renderer import SegmentRenderResult

        self.calls.append(dict(kwargs))
        shot = kwargs["shot"]
        return SegmentRenderResult(
            shot_id=shot.shot_id,
            index=shot.index,
            status="completed",
            video_url="file:///tmp/local-output.mp4",
            last_frame_url="stub://local-frame.jpg",
            duration_s=shot.duration_s,
            model=shot.model,
            payload={"resolution": shot.resolution},
        )


class SequenceQAService:
    """Deterministic QA service for short-form repair orchestration tests."""

    def __init__(self, statuses: list[str]) -> None:
        self.statuses = statuses
        self.calls: list[dict[str, Any]] = []

    def evaluate_segment(self, *, shot: Any, result: Any):
        from workers.render_qa_service import SegmentQAReport

        index = len(self.calls)
        status = self.statuses[min(index, len(self.statuses) - 1)]
        self.calls.append({"shot": shot, "result": result, "status": status})
        errors = ["product_visibility_below_threshold"] if status == "fail" else []
        warnings = ["product_visibility_repaired"] if status == "warn" else []
        return SegmentQAReport(
            shot_id=shot.shot_id,
            status=status,
            warnings=warnings,
            errors=errors,
            expected_duration_s=shot.duration_s,
            actual_duration_s=result.duration_s,
            expected_resolution=shot.resolution,
            actual_resolution=str(result.payload.get("resolution") or "") or None,
        )


def test_phase3_dry_run_report_contains_payloads_and_provenance() -> None:
    """Dry-run should expose render payloads without calling a vendor."""
    from pipeline.render_execution import RenderExecutor
    from workers.segment_renderer import SegmentRenderer

    idea, plan, lock = _execution_plan_and_lock()
    render_client = RecordingRenderClient()
    result = RenderExecutor(segment_renderer=SegmentRenderer(render_client)).execute(
        execution_plan=plan,
        approval_lock=lock,
        idea=idea,
        dry_run_only=True,
    )

    assert result.status == "dry_run"
    assert render_client.calls == []
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
    render_client = RecordingRenderClient()

    result = RenderExecutor(segment_renderer=SegmentRenderer(render_client)).execute(
        execution_plan=tampered,
        approval_lock=lock,
        idea=idea,
    )

    assert result.status == "rejected"
    assert "compiled_prompt_hash" in result.approval_verification.mismatched_fields
    assert render_client.calls == []


def test_phase3_cost_gate_can_reject_before_vendor_call() -> None:
    """CostControlService should block render before vendor spend when over budget."""
    from pipeline.render_execution import RenderExecutor
    from workers.segment_renderer import SegmentRenderer

    idea, plan, lock = _execution_plan_and_lock()
    render_client = RecordingRenderClient()
    result = RenderExecutor(segment_renderer=SegmentRenderer(render_client)).execute(
        execution_plan=plan,
        approval_lock=lock,
        idea=idea,
        max_total_cost_usd=0.01,
    )

    assert result.status == "cost_rejected"
    assert result.cost_gate is not None
    assert result.cost_gate.should_render is False
    assert render_client.calls == []


def test_phase3_draft_first_renders_then_chains_last_frame() -> None:
    """Draft-first should render a draft, then full segments with last-frame chaining."""
    from pipeline.render_execution import RenderExecutor
    from workers.segment_renderer import SegmentRenderer

    idea, plan, lock = _execution_plan_and_lock()
    render_client = RecordingRenderClient()
    result = RenderExecutor(segment_renderer=SegmentRenderer(render_client)).execute(
        execution_plan=plan,
        approval_lock=lock,
        idea=idea,
        cost_gate_mode="draft_first",
    )

    assert result.status == "completed"
    assert result.cost_gate is not None
    assert result.cost_gate.draft_shot_id == "shot_1"
    assert len(render_client.calls) == 3
    assert render_client.calls[0]["model_key"] == "seedance_2_0_fast"
    assert render_client.calls[2]["image"] == "https://cdn.test/last_2.jpg"
    assert all(report.status == "pass" for report in result.qa_reports)


def test_phase3_vendor_errors_return_render_failed_after_retry() -> None:
    """Vendor exceptions should be retried and normalized, not leak as raw errors."""
    from pipeline.render_execution import RenderExecutor
    from workers.segment_renderer import SegmentRenderer

    idea, plan, lock = _execution_plan_and_lock()
    render_client = RaisingRenderClient("429 rate limit")
    result = RenderExecutor(
        segment_renderer=SegmentRenderer(render_client, max_attempts=2, backoff_initial_s=0.0),
    ).execute(
        execution_plan=plan,
        approval_lock=lock,
        idea=idea,
    )

    assert result.status == "render_failed"
    assert len(render_client.calls) == 2
    assert result.rendered_segments[0].status == "failed"
    assert result.rendered_segments[0].error_code == "vendor_rate_limited"
    assert result.rendered_segments[0].attempts == 2
    assert result.qa_reports[0].status == "fail"


def test_segment_renderer_rejects_completed_vendor_result_without_http_output() -> None:
    """A vendor success payload is not a completed segment unless it has HTTP(S) video."""
    from workers.segment_renderer import SegmentRenderer

    _, plan, _ = _single_shot_plan_and_lock()
    render_client = RecordingRenderClient(
        video_url="file:///tmp/local-output.mp4",
        last_frame_url="stub://local-frame.jpg",
    )

    result = SegmentRenderer(render_client, max_attempts=1, backoff_initial_s=0.0).render_segment(
        execution_plan=plan,
        shot=plan.shots[0],
    )

    assert result.status == "failed"
    assert result.video_url is None
    assert result.last_frame_url is None
    assert result.error_code == "missing_deliverable_video_url"
    assert len(render_client.calls) == 1


def test_render_executor_normalizes_completed_local_segment_output_to_render_failed() -> None:
    """Executor must fail closed even when an injected renderer reports local output as completed."""
    from pipeline.render_execution import RenderExecutor

    idea, plan, lock = _single_shot_plan_and_lock()
    renderer = CompletedLocalOutputRenderer()

    result = RenderExecutor(
        segment_renderer=renderer,  # type: ignore[arg-type]
        max_auto_repair_attempts=1,
    ).execute(
        execution_plan=plan,
        approval_lock=lock,
        idea=idea,
    )

    assert result.status == "render_failed"
    assert result.rendered_segments[0].status == "failed"
    assert result.rendered_segments[0].video_url is None
    assert result.rendered_segments[0].last_frame_url is None
    assert result.rendered_segments[0].error_code == "missing_deliverable_video_url"
    assert result.repair_attempts_by_shot == {"shot_repair": 0}
    assert len(renderer.calls) == 1


def test_phase7a_consistency_policy_requires_review_before_paid_render() -> None:
    """requires_review consistency policy should block paid render unless explicitly acknowledged."""
    from pipeline.render_execution import RenderExecutor
    from workers.segment_renderer import SegmentRenderer

    idea, plan, lock = _execution_plan_and_lock(consistency_policy_action="requires_review")
    render_client = RecordingRenderClient()

    result = RenderExecutor(segment_renderer=SegmentRenderer(render_client)).execute(
        execution_plan=plan,
        approval_lock=lock,
        idea=idea,
    )

    assert result.status == "consistency_rejected"
    assert render_client.calls == []
    assert "requires review" in result.message.lower()


def test_phase7a_consistency_review_ack_allows_requires_review_render() -> None:
    """A reviewed ApprovalLock can allow requires_review plans to proceed."""
    from pipeline.approval_lock import ApprovalLock
    from pipeline.render_execution import RenderExecutor
    from workers.segment_renderer import SegmentRenderer

    idea, plan, _ = _execution_plan_and_lock(consistency_policy_action="requires_review")
    lock = ApprovalLock.from_execution_plan(
        idea=idea,
        execution_plan=plan,
        approved_by="tester",
        approval_source="dry_run_preview",
        metadata={
            "approved_idea": idea,
            "consistency_review_approved": True,
            "consistency_review_approved_policy_action": "requires_review",
        },
    )
    render_client = QARecordingRenderClient(qa_signals={"product_visibility": 0.9, "style_similarity": 0.9})

    result = RenderExecutor(segment_renderer=SegmentRenderer(render_client)).execute(
        execution_plan=plan,
        approval_lock=lock,
        idea=idea,
    )

    assert result.status == "completed"
    assert len(render_client.calls) == 2


def test_phase7a_stale_consistency_review_ack_is_rejected() -> None:
    """Review approvals must explicitly match the policy action being rendered."""
    from pipeline.approval_lock import ApprovalLock
    from pipeline.render_execution import RenderExecutor
    from workers.segment_renderer import SegmentRenderer

    idea, plan, _ = _execution_plan_and_lock(consistency_policy_action="requires_review")
    lock = ApprovalLock.from_execution_plan(
        idea=idea,
        execution_plan=plan,
        approved_by="tester",
        approval_source="dry_run_preview",
        metadata={
            "approved_idea": idea,
            "consistency_review_approved": True,
            "consistency_review_approved_policy_action": "warn",
        },
    )
    render_client = RecordingRenderClient()

    result = RenderExecutor(segment_renderer=SegmentRenderer(render_client)).execute(
        execution_plan=plan,
        approval_lock=lock,
        idea=idea,
    )

    assert result.status == "consistency_rejected"
    assert render_client.calls == []


def test_phase7a_post_render_visual_consistency_can_fail_segment_qa() -> None:
    """Low post-render visual signals should fail QA after the vendor returns output."""
    from pipeline.render_execution import RenderExecutor
    from workers.segment_renderer import SegmentRenderer

    idea, plan, lock = _execution_plan_and_lock(consistency_policy_action="warn")
    render_client = QARecordingRenderClient(qa_signals={"product_visibility": 0.4, "style_similarity": 0.9})

    result = RenderExecutor(segment_renderer=SegmentRenderer(render_client)).execute(
        execution_plan=plan,
        approval_lock=lock,
        idea=idea,
    )

    assert result.status == "qa_failed"
    assert result.qa_reports[0].visual_consistency is not None
    assert result.qa_reports[0].visual_consistency.action == "block"
    assert result.qa_reports[0].visual_consistency.risk_level == "critical"
    assert result.qa_reports[0].consistency_score == result.qa_reports[0].visual_consistency.overall_score
    assert "product_visibility_below_threshold" in result.qa_reports[0].errors


def test_shortform_auto_repair_retries_failed_qa_once_and_completes() -> None:
    """A completed render that fails QA can be repaired once without ref/model drift."""
    from pipeline.render_execution import RenderExecutor
    from workers.segment_renderer import SegmentRenderer

    idea, plan, lock = _single_shot_plan_and_lock()
    render_client = RecordingRenderClient()
    qa_service = SequenceQAService(["fail", "pass"])

    result = RenderExecutor(
        segment_renderer=SegmentRenderer(render_client),
        qa_service=qa_service,  # type: ignore[arg-type]
        max_auto_repair_attempts=1,
    ).execute(
        execution_plan=plan,
        approval_lock=lock,
        idea=idea,
    )

    assert result.status == "completed"
    assert result.repair_attempts_by_shot == {"shot_repair": 1}
    assert len(render_client.calls) == 2
    assert render_client.calls[0]["model_key"] == render_client.calls[1]["model_key"] == "seedance_2_0"
    assert render_client.calls[0]["duration_s"] == render_client.calls[1]["duration_s"] == 8
    assert render_client.calls[0]["images"] == render_client.calls[1]["images"] == ["https://cdn.test/product.png"]
    assert "AUTO-REPAIR INSTRUCTIONS" in render_client.calls[1]["prompt"]


def test_shortform_auto_repair_returns_qa_failed_when_repair_still_fails() -> None:
    """Repair should stop at the configured budget and return qa_failed."""
    from pipeline.render_execution import RenderExecutor
    from workers.segment_renderer import SegmentRenderer

    idea, plan, lock = _single_shot_plan_and_lock()
    render_client = RecordingRenderClient()

    result = RenderExecutor(
        segment_renderer=SegmentRenderer(render_client),
        qa_service=SequenceQAService(["fail", "fail"]),  # type: ignore[arg-type]
        max_auto_repair_attempts=1,
    ).execute(
        execution_plan=plan,
        approval_lock=lock,
        idea=idea,
    )

    assert result.status == "qa_failed"
    assert result.repair_attempts_by_shot == {"shot_repair": 1}
    assert len(render_client.calls) == 2


def test_shortform_auto_repair_budget_zero_does_not_retry() -> None:
    """A zero repair budget should preserve the old single-attempt QA failure path."""
    from pipeline.render_execution import RenderExecutor
    from workers.segment_renderer import SegmentRenderer

    idea, plan, lock = _single_shot_plan_and_lock()
    render_client = RecordingRenderClient()

    result = RenderExecutor(
        segment_renderer=SegmentRenderer(render_client),
        qa_service=SequenceQAService(["fail"]),  # type: ignore[arg-type]
        max_auto_repair_attempts=0,
    ).execute(
        execution_plan=plan,
        approval_lock=lock,
        idea=idea,
    )

    assert result.status == "qa_failed"
    assert result.repair_attempts_by_shot == {"shot_repair": 0}
    assert len(render_client.calls) == 1


def test_shortform_render_failure_does_not_enter_repair_loop() -> None:
    """Transport/vendor failures are normalized by SegmentRenderer and are not auto-prompt repaired."""
    from pipeline.render_execution import RenderExecutor
    from workers.segment_renderer import SegmentRenderer

    idea, plan, lock = _single_shot_plan_and_lock()
    render_client = RaisingRenderClient("vendor down")

    result = RenderExecutor(
        segment_renderer=SegmentRenderer(render_client, max_attempts=1, backoff_initial_s=0.0),
        qa_service=SequenceQAService(["fail"]),  # type: ignore[arg-type]
        max_auto_repair_attempts=1,
    ).execute(
        execution_plan=plan,
        approval_lock=lock,
        idea=idea,
    )

    assert result.status == "render_failed"
    assert result.repair_attempts_by_shot == {"shot_repair": 0}
    assert len(render_client.calls) == 1


def test_phase7a_post_render_visual_consistency_warns_on_missing_required_signals() -> None:
    """Locked product/style tracks should surface missing post-render probe signals."""
    from identity.post_render_consistency import PostRenderConsistencyQA

    report = PostRenderConsistencyQA().evaluate(
        shot_metadata=_consistency_metadata("warn"),
        qa_signals={"product_visibility": 0.9, "style_similarity": 0.9, "signal_source": "unit_probe"},
    )

    assert report.status == "warn"
    assert report.signal_source == "unit_probe"
    assert report.overall_score is not None
    assert report.overall_score <= 80
    assert "logo_label_similarity" in report.missing_signals
    assert "missing_logo_label_similarity" in report.warnings
    assert report.action == "requires_review"


def test_phase7a_post_render_visual_consistency_reads_nested_probe_signals() -> None:
    """Future CV probes can provide nested visual consistency metrics."""
    from identity.post_render_consistency import PostRenderConsistencyEvaluator

    report = PostRenderConsistencyEvaluator().evaluate(
        shot_metadata=_consistency_metadata("warn"),
        qa_signals={
            "signal_source": "cv_probe_v1",
            "visual_consistency": {
                "product_visibility": 0.91,
                "logo_label_similarity": 0.88,
                "style_similarity": 0.84,
            },
        },
    )

    assert report.status == "pass"
    assert report.action == "allow"
    assert report.signal_source == "cv_probe_v1"
    assert report.overall_score is not None and report.overall_score > 85


def test_phase6a_7a_end_to_end_requires_review_blocks_paid_render() -> None:
    """Planner, compiler, lock, and render executor should agree on review gating."""
    from pipeline.approval_lock import ApprovalLock
    from pipeline.contracts import InputContract
    from pipeline.creative_planning import CreativePlanner
    from pipeline.input_analysis import InputAnalyzer
    from pipeline.render_execution import RenderExecutor
    from pipeline.storyboard_generation import StoryboardGenerator
    from seedance.prompt_compiler import SeedancePromptCompiler
    from workers.segment_renderer import SegmentRenderer

    idea = "Create a 12s beauty serum product ad with product proof and macro packaging reveal."
    analyzed = InputAnalyzer().analyze(InputContract(user_idea=idea, duration_hint_s=12))
    plan = CreativePlanner().plan(analyzed)
    storyboard = StoryboardGenerator().generate(plan, analyzed)
    execution_plan = SeedancePromptCompiler().compile(plan, storyboard, analyzed)
    lock = ApprovalLock.from_execution_plan(
        idea=idea,
        execution_plan=execution_plan,
        approved_by="tester",
        approval_source="prompt_preview",
        metadata={"approved_idea": idea},
    )
    render_client = RecordingRenderClient()

    result = RenderExecutor(segment_renderer=SegmentRenderer(render_client)).execute(
        execution_plan=execution_plan,
        approval_lock=lock,
        idea=idea,
    )

    assert execution_plan.metadata["consistency_policy_action"] == "requires_review"
    assert result.status == "consistency_rejected"
    assert render_client.calls == []
    assert execution_plan.metadata["long_form_readiness"]["continuity_pressure"] in {"medium", "high"}


def _execution_plan_and_lock(*, consistency_policy_action: str | None = None):
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
            metadata=_consistency_metadata(consistency_policy_action),
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
            metadata=_consistency_metadata(consistency_policy_action),
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
        metadata={
            "approved_idea": idea,
            **_consistency_metadata(consistency_policy_action),
        },
    )
    lock = ApprovalLock.from_execution_plan(
        idea=idea,
        execution_plan=plan,
        approved_by="tester",
        approval_source="dry_run_preview",
        metadata={"approved_idea": idea},
    )
    return idea, plan, lock


def _single_shot_plan_and_lock():
    from pipeline.approval_lock import ApprovalLock
    from pipeline.contracts import AssetRef, ReferenceRole, SeedanceExecutionPlan, SeedanceShotPlan

    idea = "Create an 8s product launch clip"
    product_ref = AssetRef(
        asset_id="asset_repair_product",
        kind="image",
        url="https://cdn.test/product.png",
        tag="@Image1",
        role=ReferenceRole.PRODUCT_HERO,
        role_locked=True,
        name="Product hero",
    )
    shot = SeedanceShotPlan(
        shot_id="shot_repair",
        index=0,
        duration_s=8,
        compiled_prompt="Subject: product bottle\nAction: clean hero reveal\nCamera: slow push-in\nTiming: 8s",
        negative_prompt="no watermark",
        model="seedance_2_0",
        resolution="1080p",
        references=[product_ref],
    )
    plan = SeedanceExecutionPlan(
        execution_plan_id="exec_shortform_repair",
        model="seedance_2_0",
        duration_s=8,
        aspect_ratio="9:16",
        resolution="1080p",
        compiled_prompt=shot.compiled_prompt,
        shots=[shot],
        reference_assets=[product_ref],
        cost_estimate={"total_cost_usd": 0.24},
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


def _consistency_metadata(action: str | None) -> dict[str, Any]:
    if not action:
        return {}
    return {
        "consistency_score": 72.0,
        "consistency_policy_action": action,
        "consistency_policy_reasons": ["partial_reference_sufficiency"],
        "consistency_risk_flags": ["partial_reference_sufficiency"],
        "needs_product_consistency": True,
        "needs_style_consistency": True,
    }
