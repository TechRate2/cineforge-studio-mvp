"""Per-segment Seedance render worker."""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from core.deliverable_url import first_deliverable_http_url
from pipeline.contracts import SeedanceExecutionPlan, SeedanceShotPlan
from workers.render_dry_run import build_seedance_payload

logger = logging.getLogger(__name__)
_DEFAULT_MAX_ATTEMPTS = 3
_DEFAULT_BACKOFF_INITIAL_S = 0.5
_DEFAULT_BACKOFF_MAX_S = 4.0
_VENDOR_SEMAPHORE = threading.BoundedSemaphore(
    max(1, int(os.getenv("SEEDANCE_RENDER_MAX_CONCURRENCY", "2")))
)


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
    qa_signals: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    error_code: str | None = None
    attempts: int = 1


class SegmentRenderer:
    """Render individual Seedance shots through an injected vendor client."""

    def __init__(
        self,
        client: VideoRenderClient | None = None,
        *,
        max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
        backoff_initial_s: float = _DEFAULT_BACKOFF_INITIAL_S,
        backoff_max_s: float = _DEFAULT_BACKOFF_MAX_S,
    ) -> None:
        self.client = client
        self.max_attempts = max(1, int(max_attempts))
        self.backoff_initial_s = max(0.0, float(backoff_initial_s))
        self.backoff_max_s = max(self.backoff_initial_s, float(backoff_max_s))

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

        logger.info(
            "seedance_segment_render_start",
            extra={
                "execution_plan_id": execution_plan.execution_plan_id,
                "shot_id": shot.shot_id,
                "shot_index": shot.index,
                "model": payload.get("model_key"),
                "duration_s": payload.get("duration_s"),
                "has_previous_last_frame": bool(previous_last_frame_url),
            },
        )
        result: dict[str, Any] | None = None
        last_error: Exception | None = None
        attempts_used = 0
        for attempt in range(1, self.max_attempts + 1):
            attempts_used = attempt
            try:
                with _VENDOR_SEMAPHORE:
                    result = self.client.generate_video(**payload)
                logger.info(
                    "seedance_segment_render_completed",
                    extra={
                        "execution_plan_id": execution_plan.execution_plan_id,
                        "shot_id": shot.shot_id,
                        "attempt": attempt,
                        "prediction_id": result.get("prediction_id"),
                    },
                )
                break
            except Exception as exc:  # vendor SDKs vary widely; normalize below.
                last_error = exc
                error_code = _map_vendor_error(exc)
                logger.warning(
                    "seedance_segment_render_attempt_failed",
                    extra={
                        "execution_plan_id": execution_plan.execution_plan_id,
                        "shot_id": shot.shot_id,
                        "attempt": attempt,
                        "max_attempts": self.max_attempts,
                        "error_code": error_code,
                        "error": _safe_error(exc),
                    },
                )
                if attempt >= self.max_attempts or not _is_retryable_vendor_error(error_code):
                    break
                time.sleep(min(self.backoff_initial_s * (2 ** (attempt - 1)), self.backoff_max_s))

        if result is None:
            error_code = _map_vendor_error(last_error) if last_error else "vendor_render_error"
            logger.error(
                "seedance_segment_render_failed",
                extra={
                    "execution_plan_id": execution_plan.execution_plan_id,
                    "shot_id": shot.shot_id,
                    "attempts": attempts_used,
                    "error_code": error_code,
                },
            )
            return SegmentRenderResult(
                shot_id=shot.shot_id,
                index=shot.index,
                status="failed",
                duration_s=shot.duration_s,
                model=str(payload.get("model_key") or shot.model),
                payload=payload,
                qa_signals={},
                error=_safe_error(last_error) if last_error else "vendor render failed",
                error_code=error_code,
                attempts=attempts_used,
            )

        video_url = first_deliverable_http_url(
            result.get("outputs"),
            result.get("video_url"),
            result.get("output_url"),
            result.get("url"),
        )
        last_frame_url = first_deliverable_http_url(
            result.get("last_frame_url"),
            result.get("lastFrameUrl"),
            result.get("last_frame"),
            (result.get("extra") or {}).get("last_frame_url") if isinstance(result.get("extra"), dict) else None,
        )
        if not video_url:
            logger.error(
                "seedance_segment_render_missing_deliverable_url",
                extra={
                    "execution_plan_id": execution_plan.execution_plan_id,
                    "shot_id": shot.shot_id,
                    "attempts": attempts_used,
                    "prediction_id": result.get("prediction_id"),
                },
            )
            return SegmentRenderResult(
                shot_id=shot.shot_id,
                index=shot.index,
                status="failed",
                video_url=None,
                last_frame_url=last_frame_url,
                prediction_id=result.get("prediction_id"),
                duration_s=int(result.get("duration_s") or shot.duration_s),
                model=str(result.get("model") or payload.get("model_key") or shot.model),
                payload=payload,
                qa_signals=_qa_signals_from_result(result),
                error="Vendor completed without a deliverable HTTP(S) video URL.",
                error_code="missing_deliverable_video_url",
                attempts=attempts_used,
            )

        return SegmentRenderResult(
            shot_id=shot.shot_id,
            index=shot.index,
            status="completed",
            video_url=video_url,
            last_frame_url=last_frame_url,
            prediction_id=result.get("prediction_id"),
            duration_s=int(result.get("duration_s") or shot.duration_s),
            model=str(result.get("model") or payload.get("model_key") or shot.model),
            payload=payload,
            qa_signals=_qa_signals_from_result(result),
            attempts=attempts_used,
        )


def _map_vendor_error(exc: Exception | None) -> str:
    """Map vendor exceptions to stable render error codes."""
    if exc is None:
        return "vendor_render_error"
    text = f"{type(exc).__name__} {exc}".lower()
    if "429" in text or "rate" in text:
        return "vendor_rate_limited"
    if "timeout" in text or "timed out" in text:
        return "vendor_timeout"
    if "401" in text or "403" in text or "auth" in text or "permission" in text:
        return "vendor_auth_error"
    if "quota" in text or "billing" in text or "insufficient" in text:
        return "vendor_quota_error"
    if "400" in text or "invalid" in text:
        return "vendor_invalid_request"
    return "vendor_render_error"


def _is_retryable_vendor_error(error_code: str) -> bool:
    """Return whether a mapped vendor error should be retried."""
    return error_code in {"vendor_rate_limited", "vendor_timeout", "vendor_render_error"}


def _safe_error(exc: Exception | None) -> str:
    """Return a bounded error string suitable for logs and job metadata."""
    if exc is None:
        return ""
    return str(exc).replace("\n", " ")[:500]


def _qa_signals_from_result(result: dict[str, Any]) -> dict[str, Any]:
    """Extract optional post-render QA signals without mutating vendor payloads."""
    for key in ("qa_signals", "visual_consistency", "consistency_metrics"):
        value = result.get(key)
        if isinstance(value, dict):
            return dict(value)
    return {}


__all__ = ["SegmentRenderer", "SegmentRenderResult", "VideoRenderClient"]
