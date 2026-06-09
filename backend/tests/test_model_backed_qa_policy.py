"""Model-backed QA policy tests."""
from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_model_backed_qa_missing_required_signal_warns_without_faking_pass() -> None:
    from pipeline.contracts import SeedanceShotPlan
    from workers.render_qa_service import RenderQAService
    from workers.segment_renderer import SegmentRenderResult

    shot = SeedanceShotPlan(
        shot_id="S1",
        index=0,
        duration_s=5,
        compiled_prompt="Product hero shot",
        resolution="1080p",
        metadata={
            "requires_model_backed_qa": True,
            "needs_product_consistency": True,
            "model_backed_qa_required_checks": ["product_fidelity"],
        },
    )
    result = SegmentRenderResult(
        shot_id="S1",
        index=0,
        status="completed",
        video_url="https://cdn.example.com/render.mp4",
        duration_s=5,
        model="seedance_2_0",
        payload={"resolution": "1080p"},
    )

    report = RenderQAService().evaluate_segment(shot=shot, result=result)

    assert report.status == "warn"
    assert report.model_backed_qa is not None
    assert report.model_backed_qa.status == "needs_review"
    assert report.model_backed_qa.missing_checks == ["product_fidelity"]
    assert "model_backed_qa_missing:product_fidelity" in report.warnings


def test_model_backed_qa_passes_when_required_signal_is_available() -> None:
    from pipeline.contracts import SeedanceShotPlan
    from workers.render_qa_service import RenderQAService
    from workers.segment_renderer import SegmentRenderResult

    shot = SeedanceShotPlan(
        shot_id="S1",
        index=0,
        duration_s=5,
        compiled_prompt="Product hero shot",
        resolution="1080p",
        metadata={
            "requires_model_backed_qa": True,
            "model_backed_qa_required_checks": ["product_fidelity"],
        },
    )
    result = SegmentRenderResult(
        shot_id="S1",
        index=0,
        status="completed",
        video_url="https://cdn.example.com/render.mp4",
        duration_s=5,
        model="seedance_2_0",
        payload={"resolution": "1080p"},
        qa_signals={
            "model_backed_qa": {
                "source": "test_model_reviewer",
                "status": "pass",
                "available_checks": ["product_fidelity"],
            }
        },
    )

    report = RenderQAService().evaluate_segment(shot=shot, result=result)

    assert report.model_backed_qa is not None
    assert report.model_backed_qa.status == "pass"
    assert report.model_backed_qa.missing_checks == []
    assert not any(item.startswith("model_backed_qa_missing") for item in report.warnings)
