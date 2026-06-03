"""Basic QA checks for rendered Seedance segments."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from identity.post_render_consistency import PostRenderConsistencyQA, VisualConsistencyQAReport
from pipeline.contracts import SeedanceShotPlan
from workers.segment_renderer import SegmentRenderResult


class SegmentQAReport(BaseModel):
    """Basic QA result for one rendered segment."""

    model_config = ConfigDict(extra="forbid")

    shot_id: str
    status: str
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    expected_duration_s: int
    actual_duration_s: int | None = None
    expected_resolution: str
    actual_resolution: str | None = None
    consistency_score: float | None = None
    consistency_policy_action: str | None = None
    consistency_warnings: list[str] = Field(default_factory=list)
    visual_consistency: VisualConsistencyQAReport | None = None


class RenderQAService:
    """Run deterministic post-render checks before assembly."""

    def __init__(self, *, visual_consistency_qa: PostRenderConsistencyQA | None = None) -> None:
        self.visual_consistency_qa = visual_consistency_qa or PostRenderConsistencyQA()

    def evaluate_segment(
        self,
        *,
        shot: SeedanceShotPlan,
        result: SegmentRenderResult,
    ) -> SegmentQAReport:
        """Check URL presence, duration drift, and known resolution metadata."""
        warnings: list[str] = []
        errors: list[str] = []
        if result.status != "completed":
            errors.append(result.error_code or "segment_render_failed")
        if not result.video_url:
            errors.append("missing_video_url")
        if result.duration_s is None:
            warnings.append("missing_duration_metadata")
        elif abs(int(result.duration_s) - int(shot.duration_s)) > 1:
            warnings.append("duration_mismatch_gt_1s")
        actual_resolution = str(result.payload.get("resolution") or "")
        if actual_resolution and actual_resolution != shot.resolution:
            warnings.append("resolution_payload_differs_from_shot")
        consistency_score = _coerce_float(shot.metadata.get("consistency_score"))
        consistency_warnings = [
            str(item)
            for item in (shot.metadata.get("consistency_risk_flags") or [])
            if str(item).strip()
        ]
        visual_report = self.visual_consistency_qa.evaluate(
            shot_metadata=shot.metadata,
            qa_signals=result.qa_signals,
        )
        warnings.extend(visual_report.warnings)
        errors.extend(visual_report.errors)
        return SegmentQAReport(
            shot_id=shot.shot_id,
            status="fail" if errors else ("warn" if warnings else "pass"),
            warnings=warnings,
            errors=errors,
            expected_duration_s=shot.duration_s,
            actual_duration_s=result.duration_s,
            expected_resolution=shot.resolution,
            actual_resolution=actual_resolution or None,
            consistency_score=consistency_score,
            consistency_policy_action=_optional_str(shot.metadata.get("consistency_policy_action")),
            consistency_warnings=consistency_warnings,
            visual_consistency=visual_report,
        )


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = ["RenderQAService", "SegmentQAReport"]
