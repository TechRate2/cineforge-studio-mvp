from identity.post_render_consistency import PostRenderConsistencyEvaluator


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
