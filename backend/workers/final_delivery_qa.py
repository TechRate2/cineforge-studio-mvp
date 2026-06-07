"""Final MP4 and delivery metadata QA for production renders.

This module validates the assembled file before upload and the returned storage
metadata after upload. It is intentionally local and deterministic: it does not
invent quality scores, does not call paid services, and does not accept a missing
or unreadable final video as success.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from vendors.r2_storage import R2UploadResult


class FinalVideoQAReport(BaseModel):
    """File-level QA result for a final assembled video."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "cineforge.final_video_qa.v1"
    status: str
    path: str | None = None
    expected_duration_s: float | None = None
    actual_duration_s: float | None = None
    width: int | None = None
    height: int | None = None
    file_size_bytes: int | None = None
    video_stream_count: int = 0
    audio_stream_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    rules_applied: list[str] = Field(default_factory=list)


class FinalDeliveryQAReport(BaseModel):
    """Storage delivery QA for the uploaded final video."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "cineforge.final_delivery_qa.v1"
    status: str
    delivery_url: str | None = None
    storage_key: str | None = None
    storage_bucket: str | None = None
    storage_type: str | None = None
    access_strategy: str | None = None
    is_public: bool = False
    refresh_supported: bool = False
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    rules_applied: list[str] = Field(default_factory=list)


class FinalVideoDeliveryQAService:
    """Validate final assembled MP4 files and delivery metadata."""

    def __init__(
        self,
        *,
        ffprobe_bin: str | None = None,
        min_file_size_bytes: int = 64_000,
        duration_tolerance_s: float = 2.0,
    ) -> None:
        self.ffprobe_bin = ffprobe_bin or shutil.which("ffprobe")
        self.min_file_size_bytes = max(1, int(min_file_size_bytes))
        self.duration_tolerance_s = max(0.25, float(duration_tolerance_s))

    def probe_file(
        self,
        *,
        video_path: str | Path,
        expected_duration_s: float | None = None,
        require_audio: bool = False,
    ) -> FinalVideoQAReport:
        """Return QA for a local final MP4 path before upload."""
        path = Path(video_path)
        warnings: list[str] = []
        errors: list[str] = []
        duration: float | None = None
        width: int | None = None
        height: int | None = None
        video_stream_count = 0
        audio_stream_count = 0
        size = path.stat().st_size if path.exists() else None

        if not path.exists():
            errors.append("final_video_file_missing")
        elif not path.is_file():
            errors.append("final_video_path_not_file")
        elif size is not None and size < self.min_file_size_bytes:
            errors.append("final_video_file_too_small")

        if path.suffix.lower() != ".mp4":
            warnings.append("final_video_extension_not_mp4")

        if self.ffprobe_bin is None:
            errors.append("ffprobe_unavailable_for_final_video_qa")
        elif not errors:
            try:
                payload = _ffprobe(self.ffprobe_bin, path)
                duration = _coerce_float((payload.get("format") or {}).get("duration"))
                streams = payload.get("streams") if isinstance(payload.get("streams"), list) else []
                for stream in streams:
                    if not isinstance(stream, dict):
                        continue
                    codec_type = str(stream.get("codec_type") or "").lower()
                    if codec_type == "video":
                        video_stream_count += 1
                        width = width or _coerce_int(stream.get("width"))
                        height = height or _coerce_int(stream.get("height"))
                    elif codec_type == "audio":
                        audio_stream_count += 1
            except Exception as exc:
                errors.append("ffprobe_final_video_failed")
                warnings.append(_safe_error(exc))

        if video_stream_count <= 0:
            errors.append("final_video_missing_video_stream")
        if require_audio and audio_stream_count <= 0:
            errors.append("final_video_missing_required_audio_stream")
        if width is not None and width < 320:
            errors.append("final_video_width_too_small")
        if height is not None and height < 320:
            errors.append("final_video_height_too_small")
        if expected_duration_s is not None and duration is not None:
            if duration <= 0:
                errors.append("final_video_duration_invalid")
            elif abs(duration - float(expected_duration_s)) > self.duration_tolerance_s:
                warnings.append("final_video_duration_outside_tolerance")
        elif expected_duration_s is not None:
            warnings.append("final_video_duration_unavailable")

        return FinalVideoQAReport(
            status="fail" if errors else ("warn" if warnings else "pass"),
            path=_redact_path(path),
            expected_duration_s=expected_duration_s,
            actual_duration_s=round(duration, 3) if duration is not None else None,
            width=width,
            height=height,
            file_size_bytes=size,
            video_stream_count=video_stream_count,
            audio_stream_count=audio_stream_count,
            warnings=list(dict.fromkeys(warnings)),
            errors=list(dict.fromkeys(errors)),
            rules_applied=[
                "final_video_qa.file_exists",
                "final_video_qa.ffprobe_streams",
                "final_video_qa.duration_tolerance",
                "final_video_qa.minimum_file_size",
            ],
        )

    def verify_delivery(
        self,
        *,
        upload_result: R2UploadResult,
        final_video_url: str | None,
    ) -> FinalDeliveryQAReport:
        """Validate object-storage metadata returned by the real upload path."""
        warnings: list[str] = []
        errors: list[str] = []
        delivery_url = str(final_video_url or upload_result.delivery_url or upload_result.presigned_url or upload_result.public_url or "").strip()
        if not delivery_url:
            errors.append("final_delivery_url_missing")
        elif not delivery_url.lower().startswith(("http://", "https://", "file://")):
            errors.append("final_delivery_url_invalid_scheme")
        if not str(upload_result.key or "").strip():
            errors.append("final_delivery_storage_key_missing")
        if not str(upload_result.storage_type or "").strip():
            warnings.append("final_delivery_storage_type_missing")
        if not upload_result.is_public and not upload_result.presigned_url and not upload_result.delivery_url:
            errors.append("final_delivery_not_public_and_no_presigned_url")
        if upload_result.presigned_url and not upload_result.presigned_expires_at:
            warnings.append("final_delivery_presigned_expiry_missing")

        return FinalDeliveryQAReport(
            status="fail" if errors else ("warn" if warnings else "pass"),
            delivery_url=delivery_url or None,
            storage_key=upload_result.key,
            storage_bucket=upload_result.bucket,
            storage_type=upload_result.storage_type,
            access_strategy=upload_result.access_strategy,
            is_public=bool(upload_result.is_public),
            refresh_supported=bool(upload_result.refresh_supported),
            warnings=list(dict.fromkeys(warnings)),
            errors=list(dict.fromkeys(errors)),
            rules_applied=[
                "final_delivery_qa.delivery_url_present",
                "final_delivery_qa.storage_key_present",
                "final_delivery_qa.access_strategy_valid",
            ],
        )


def _ffprobe(ffprobe_bin: str, path: Path) -> dict[str, Any]:
    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    completed = subprocess.run(cmd, check=True, capture_output=True, timeout=60, text=True)
    return json.loads(completed.stdout or "{}")


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_error(exc: Exception) -> str:
    return str(exc).replace("\n", " ").replace("\r", " ")[:240]


def _redact_path(path: Path) -> str:
    return path.name


__all__ = [
    "FinalDeliveryQAReport",
    "FinalVideoDeliveryQAService",
    "FinalVideoQAReport",
]
