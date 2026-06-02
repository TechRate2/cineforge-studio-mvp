"""Basic QA checks for rendered Seedance segments."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

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


class RenderQAService:
    """Run deterministic post-render checks before assembly."""

    def evaluate_segment(
        self,
        *,
        shot: SeedanceShotPlan,
        result: SegmentRenderResult,
    ) -> SegmentQAReport:
        """Check URL presence, duration drift, and known resolution metadata."""
        warnings: list[str] = []
        errors: list[str] = []
        if not result.video_url:
            errors.append("missing_video_url")
        if result.duration_s is None:
            warnings.append("missing_duration_metadata")
        elif abs(int(result.duration_s) - int(shot.duration_s)) > 1:
            warnings.append("duration_mismatch_gt_1s")
        actual_resolution = str(result.payload.get("resolution") or "")
        if actual_resolution and actual_resolution != shot.resolution:
            warnings.append("resolution_payload_differs_from_shot")
        return SegmentQAReport(
            shot_id=shot.shot_id,
            status="fail" if errors else ("warn" if warnings else "pass"),
            warnings=warnings,
            errors=errors,
            expected_duration_s=shot.duration_s,
            actual_duration_s=result.duration_s,
            expected_resolution=shot.resolution,
            actual_resolution=actual_resolution or None,
        )


__all__ = ["RenderQAService", "SegmentQAReport"]
