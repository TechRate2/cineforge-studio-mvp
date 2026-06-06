from identity.post_render_consistency import PostRenderConsistencyEvaluator
from pipeline.contracts import SeedanceExecutionPlan, SeedanceShotPlan
from pipeline.render_execution import _seedance_preflight_decision
from workers.render_qa_service import SegmentQAReport
from workers.segment_renderer import SegmentRenderResult
from workers.segment_repair_policy import apply_segment_repair, build_segment_repair_plan


def test_post_render_consistency_allows_high_confidence_required_signals() -> None:
    evaluator = PostRenderConsistencyEvaluator()

    report = evaluator.evaluate(
        shot_metadata={
            "needs_identity_consistency": True,
            "needs_product_consistency": True,
            "needs_style_consistency": True,
        },
        qa_signals={
            "cv_probe": {
                "face_similarity": 0.91,
                "product_visibility": 0.82,
                "logo_label_similarity": 0.72,
                "style_similarity": 0.84,
                "signal_confidence": {
                    "face_similarity": 0.88,
                    "product_visibility": 0.80,
                    "logo_label_similarity": 0.78,
                    "style_similarity": 0.82,
                },
                "signal_quality": {
                    "frame_count": 8,
                    "reference_count": 2,
                    "face": {"reference_faces": 1, "frame_faces": 4},
                    "product": {"regions_per_frame": 0.70},
                    "style": {"components": {"temporal": 0.82, "color": 0.80}},
                },
                "signal_source": "opencv_probe",
            }
        },
    )

    assert report.action == "allow"
    assert report.status == "pass"
    assert report.overall_score is not None and report.overall_score > 80
    assert report.missing_signals == []


def test_post_render_consistency_requires_review_when_required_signals_missing() -> None:
    evaluator = PostRenderConsistencyEvaluator()

    report = evaluator.evaluate(
        shot_metadata={"needs_product_consistency": True},
        qa_signals={"cv_probe": {"signal_quality": {"frame_count": 6, "reference_count": 1}}},
    )

    assert report.action == "requires_review"
    assert report.status == "warn"
    assert "product_visibility" in report.missing_signals
    assert "logo_label_similarity" in report.missing_signals
    assert "run_post_render_cv_probe_or_block_delivery_until_manual_review" in report.retry_recommendations


def test_post_render_consistency_escalates_low_confidence_face_probe() -> None:
    evaluator = PostRenderConsistencyEvaluator()

    report = evaluator.evaluate(
        shot_metadata={"needs_identity_consistency": True},
        qa_signals={
            "cv_probe": {
                "face_similarity": 0.86,
                "signal_quality": {
                    "frame_count": 1,
                    "reference_count": 1,
                    "face": {"reference_faces": 0, "frame_faces": 0},
                },
            }
        },
    )

    assert report.action == "requires_review"
    assert "character_reference_face_not_detected" in report.quality_flags
    assert "rendered_character_face_not_detected" in report.quality_flags
    assert "rerender_or_route_to_manual_review_due_to_unreliable_probe_signal" in report.retry_recommendations


def test_seedance_preflight_decision_rejects_hard_failure_before_vendor_call() -> None:
    plan = SeedanceExecutionPlan(
        execution_plan_id="seedance_exec_preflight_fail",
        duration_s=8,
        compiled_prompt="Subject: product\nAction: demo\nCamera: static\nTiming: Duration: 8s",
        shots=[],
        metadata={
            "seedance_preflight": {
                "status": "fail",
                "hard_failures": ["seedance.basic.missing_camera: Prompt is missing a clear Camera field."],
                "warnings": [],
            }
        },
    )

    decision = _seedance_preflight_decision(plan)

    assert decision["should_render"] is False
    assert decision["status"] == "fail"
    assert "missing_camera" in decision["message"]


def test_seedance_preflight_decision_allows_warning_only_payload() -> None:
    plan = SeedanceExecutionPlan(
        execution_plan_id="seedance_exec_preflight_warn",
        duration_s=8,
        compiled_prompt="Subject: product\nAction: demo\nCamera: static\nTiming: Duration: 8s",
        shots=[
            SeedanceShotPlan(
                shot_id="shot_1",
                index=0,
                duration_s=8,
                compiled_prompt="Subject: product\nAction: demo\nCamera: static\nTiming: Duration: 8s",
                metadata={
                    "seedance_preflight": {
                        "status": "warn",
                        "hard_failures": [],
                        "warnings": ["lanshu.subject.insufficient_stable_traits: add stable product traits"],
                    }
                },
            )
        ],
    )

    decision = _seedance_preflight_decision(plan)

    assert decision["should_render"] is True
    assert decision["status"] == "warn"
    assert decision["warnings"]


def test_segment_repair_policy_builds_product_repair_without_swapping_refs_or_model() -> None:
    shot = SeedanceShotPlan(
        shot_id="shot_product",
        index=0,
        duration_s=8,
        compiled_prompt="Subject: hero serum bottle\nAction: show product\nCamera: static\nTiming: Duration: 8s",
        negative_prompt="no watermark",
        model="seedance_2_0",
        metadata={"needs_product_consistency": True},
    )
    execution_plan = SeedanceExecutionPlan(
        execution_plan_id="seedance_exec_repair",
        duration_s=8,
        compiled_prompt=shot.compiled_prompt,
        model="seedance_2_0",
        shots=[shot],
    )
    result = SegmentRenderResult(
        shot_id=shot.shot_id,
        index=shot.index,
        status="completed",
        video_url="https://cdn.example.com/shot.mp4",
        duration_s=8,
        model="seedance_2_0",
    )
    qa_report = SegmentQAReport(
        shot_id=shot.shot_id,
        status="fail",
        warnings=["product_visibility_requires_review"],
        errors=["product_visibility_below_threshold"],
        expected_duration_s=8,
        expected_resolution="1080p",
        consistency_warnings=["post_render_consistency_action:requires_review"],
    )

    repair_plan = build_segment_repair_plan(
        shot=shot,
        result=result,
        qa_report=qa_report,
        attempt_index=0,
        max_attempts=2,
    )
    repaired_plan, repaired_shot = apply_segment_repair(
        execution_plan=execution_plan,
        shot=shot,
        repair_plan=repair_plan,
        repair_attempt=1,
    )

    assert repair_plan.should_retry is True
    assert "product_repair" in repair_plan.repair_tags
    assert "hero product" in repaired_shot.compiled_prompt.lower()
    assert "no product redesign" in repaired_shot.negative_prompt
    assert repaired_shot.model == shot.model
    assert repaired_shot.references == shot.references
    assert repaired_plan.shots[0].metadata["auto_repair"]["attempt"] == 1
