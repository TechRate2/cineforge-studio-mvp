"""Per-segment Seedance render worker."""
from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from pipeline.contracts import SeedanceExecutionPlan, SeedanceShotPlan
from workers.render_dry_run import build_seedance_payload


class VideoRenderClient(Protocol):
    """Protocol implemented by AtlasCloudClient for video generation."""

    def generate_video(self, **kwargs: Any) -> dict[str, Any]:
        """Submit and poll one video generation job."""


class SegmentRenderResult(BaseModel):
    """Result for one rendered Seedance segment."""

    model_config = ConfigDict(extra="forbid")

    shot_id: str
    index: int
    status: str = "completed"
    video_url: str | None = None
    last_frame_url: str | None = None
    prediction_id: str | None = None
    duration_s: int | None = None
    model: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class SegmentRenderer:
    """Render individual Seedance shots through an injected vendor client."""

    def __init__(self, client: VideoRenderClient | None = None) -> None:
        self.client = client

    def render_segment(
        self,
        *,
        execution_plan: SeedanceExecutionPlan,
        shot: SeedanceShotPlan,
        previous_last_frame_url: str | None = None,
        override_model: str | None = None,
    ) -> SegmentRenderResult:
        """Render one shot and return a normalized segment result."""
        payload = build_seedance_payload(
            execution_plan=execution_plan,
            shot=shot,
            previous_last_frame_url=previous_last_frame_url,
        )
        if override_model:
            payload["model_key"] = override_model
        if self.client is None:
            try:
                from vendors.atlascloud import atlas_client
            except Exception:
                atlas_client = None
            self.client = atlas_client
        if self.client is None:
            raise RuntimeError("AtlasCloud client is unavailable; render cannot start.")

        result = self.client.generate_video(**payload)
        return SegmentRenderResult(
            shot_id=shot.shot_id,
            index=shot.index,
            status="completed",
            video_url=result.get("video_url") or result.get("url"),
            last_frame_url=result.get("last_frame_url"),
            prediction_id=result.get("prediction_id"),
            duration_s=int(result.get("duration_s") or shot.duration_s),
            model=str(result.get("model") or payload.get("model_key") or shot.model),
            payload=payload,
        )


__all__ = ["SegmentRenderer", "SegmentRenderResult", "VideoRenderClient"]
