"""Real OpenCV post-render consistency probe tests."""
from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_render_qa_service_derives_cv_probe_signals_from_video_and_reference(tmp_path) -> None:
    """RenderQAService should compute real CV signals, not only vendor payloads."""
    import cv2  # type: ignore
    import numpy as np

    from pipeline.contracts import AssetRef, ReferenceRole, SeedanceShotPlan
    from workers.render_qa_service import RenderQAService
    from workers.segment_renderer import SegmentRenderResult

    ref_path = tmp_path / "product_ref.png"
    video_path = tmp_path / "rendered_segment.mp4"
    product = _product_frame()
    cv2.imwrite(str(ref_path), product)

    writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        6.0,
        (product.shape[1], product.shape[0]),
    )
    assert writer.isOpened()
    for _ in range(8):
        writer.write(product)
    writer.release()
    assert video_path.exists()

    shot = SeedanceShotPlan(
        shot_id="shot_cv_probe",
        index=0,
        duration_s=4,
        compiled_prompt="Subject: product bottle. Action: hero reveal. Camera: static.",
        references=[
            AssetRef(
                asset_id="asset_product_ref",
                kind="image",
                url=str(ref_path),
                role=ReferenceRole.PRODUCT_HERO,
                tag="@Image1",
            )
        ],
        metadata={
            "needs_product_consistency": True,
            "needs_style_consistency": True,
            "consistency_policy_action": "warn",
        },
    )
    result = SegmentRenderResult(
        shot_id=shot.shot_id,
        index=0,
        status="completed",
        video_url=str(video_path),
        duration_s=4,
        payload={"resolution": shot.resolution},
    )

    report = RenderQAService().evaluate_segment(shot=shot, result=result)

    assert report.visual_consistency is not None
    assert report.visual_consistency.signal_source == "opencv_post_render_probe"
    assert report.visual_consistency.metrics["product_visibility"] >= 0.5
    assert report.visual_consistency.metrics["style_similarity"] >= 0.5
    assert report.visual_consistency.signal_confidence["product_visibility"] > 0
    assert report.visual_consistency.signal_quality["probe_version"] == "opencv_hybrid_v2"
    assert report.cv_probe_signals["probe_version"] == "opencv_hybrid_v2"
    assert "cv_probe_failed" not in report.warnings


def test_hybrid_cv_probe_scores_matching_product_above_mismatched_reference(tmp_path) -> None:
    """The hybrid descriptor should reduce false positives versus color-only checks."""
    import cv2  # type: ignore

    from identity.post_render_cv_probe import OpenCVPostRenderProbe
    from pipeline.contracts import AssetRef, ReferenceRole, SeedanceShotPlan
    from workers.segment_renderer import SegmentRenderResult

    match_ref = tmp_path / "match_ref.png"
    mismatch_ref = tmp_path / "mismatch_ref.png"
    video_path = tmp_path / "rendered_segment.mp4"
    frame = _product_frame()
    cv2.imwrite(str(match_ref), frame)
    cv2.imwrite(str(mismatch_ref), _mismatched_product_frame())
    _write_video(cv2, video_path, frame)

    probe = OpenCVPostRenderProbe(max_frames=4, max_regions=6)
    match_payload = probe.probe(
        shot=_shot_with_product_reference(str(match_ref)),
        result=SegmentRenderResult(
            shot_id="shot_match",
            index=0,
            status="completed",
            video_url=str(video_path),
            duration_s=4,
            payload={"resolution": "1080p"},
        ),
    )
    mismatch_payload = probe.probe(
        shot=_shot_with_product_reference(str(mismatch_ref)),
        result=SegmentRenderResult(
            shot_id="shot_mismatch",
            index=0,
            status="completed",
            video_url=str(video_path),
            duration_s=4,
            payload={"resolution": "1080p"},
        ),
    )

    assert match_payload["metrics"]["product_visibility"] > mismatch_payload["metrics"]["product_visibility"]
    assert match_payload["signal_confidence"]["product_visibility"] > 0
    assert match_payload["signal_quality"]["product"]["pair_count"] > 0


def test_consistency_evaluator_warns_on_low_confidence_signal() -> None:
    """High score with weak evidence should not pass silently."""
    from identity.post_render_consistency import PostRenderConsistencyQA

    report = PostRenderConsistencyQA().evaluate(
        shot_metadata={"needs_identity_consistency": True},
        qa_signals={
            "cv_probe": {
                "signal_source": "opencv_post_render_probe",
                "face_similarity": 0.92,
                "signal_confidence": {"face_similarity": 0.2},
                "signal_quality": {"probe_version": "opencv_hybrid_v2"},
            }
        },
    )

    assert report.action == "warn"
    assert "low_confidence_face_similarity" in report.warnings
    assert report.signal_confidence["face_similarity"] == 0.2


def _product_frame():
    import cv2  # type: ignore
    import numpy as np

    frame = np.zeros((180, 240, 3), dtype=np.uint8)
    frame[:, :] = (24, 34, 48)
    cv2.rectangle(frame, (70, 30), (170, 150), (30, 30, 210), -1)
    cv2.rectangle(frame, (88, 48), (152, 132), (230, 230, 245), 3)
    cv2.circle(frame, (120, 90), 24, (220, 220, 255), -1)
    cv2.putText(frame, "CF", (96, 98), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 120), 2, cv2.LINE_AA)
    return frame


def _mismatched_product_frame():
    import cv2  # type: ignore
    import numpy as np

    frame = np.zeros((180, 240, 3), dtype=np.uint8)
    frame[:, :] = (235, 230, 210)
    pts = np.array([[40, 150], [120, 20], [205, 150]], dtype=np.int32)
    cv2.fillPoly(frame, [pts], (60, 170, 40))
    cv2.circle(frame, (78, 72), 18, (20, 90, 230), -1)
    cv2.putText(frame, "XY", (136, 106), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 60, 40), 2, cv2.LINE_AA)
    return frame


def _write_video(cv2, video_path: Path, frame) -> None:
    writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        6.0,
        (frame.shape[1], frame.shape[0]),
    )
    assert writer.isOpened()
    for _ in range(8):
        writer.write(frame)
    writer.release()


def _shot_with_product_reference(url: str):
    from pipeline.contracts import AssetRef, ReferenceRole, SeedanceShotPlan

    return SeedanceShotPlan(
        shot_id="shot_product_probe",
        index=0,
        duration_s=4,
        compiled_prompt="Subject: product bottle. Action: hero reveal. Camera: static.",
        references=[
            AssetRef(
                asset_id="asset_product_ref",
                kind="image",
                url=url,
                role=ReferenceRole.PRODUCT_HERO,
                tag="@Image1",
            )
        ],
        metadata={"needs_product_consistency": True},
    )
