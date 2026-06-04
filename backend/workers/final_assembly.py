"""Final video assembly for long-form segmented renders.

The service is intentionally narrow: it concatenates already-rendered segment
MP4 files into one final MP4, uploads that artifact to object storage, and
returns only object-storage delivery metadata. Remote segment URLs are
downloaded to a temporary assembly folder before FFmpeg runs.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from core.config import settings
from workers.longform_render_executor import LongFormRenderResult
from vendors import r2_storage
from vendors.r2_storage import R2UploadResult

logger = logging.getLogger(__name__)

FinalAssemblyStatus = Literal["completed", "failed"]


class FinalAssemblySegment(BaseModel):
    """One source segment consumed by the final assembly step."""

    model_config = ConfigDict(extra="forbid")

    shot_id: str
    index: int
    source_url: str | None = None
    local_path: str | None = None


class FinalVideoAssemblyResult(BaseModel):
    """Normalized result of the final long-form MP4 assembly step."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "cineforge.final_video_assembly_result.v1"
    status: FinalAssemblyStatus
    job_id: str
    longform_plan_id: str
    # Kept for legacy schema compatibility only. Production delivery uses
    # storage_delivery_url/final_video_url; local assembly files are temporary.
    final_video_path: str | None = None
    final_video_url: str | None = None
    storage_bucket: str | None = None
    storage_key: str | None = None
    storage_type: str | None = None
    storage_access_strategy: str | None = None
    storage_delivery_url: str | None = None
    storage_cdn_url: str | None = None
    storage_is_public: bool = False
    storage_public_url: str | None = None
    storage_presigned_url: str | None = None
    storage_presigned_expires_s: int | None = None
    storage_presigned_expires_at: str | None = None
    storage_refresh_supported: bool = False
    # Legacy schema compatibility only. Production delivery metadata is stored
    # on the job record; no local sidecar path is exposed.
    metadata_path: str | None = None
    segments: list[FinalAssemblySegment] = Field(default_factory=list)
    title: str | None = None
    caption: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    error: str | None = None


class FinalVideoAssemblyService:
    """Concatenate rendered long-form segments into a final MP4."""

    def __init__(
        self,
        *,
        output_root: str | Path | None = None,
        ffmpeg_bin: str | None = None,
        upload_result_sync: Callable[..., R2UploadResult] | None = None,
    ) -> None:
        self.output_root = Path(output_root or Path("backend") / "data" / "final_assembly")
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.ffmpeg_bin = ffmpeg_bin or shutil.which("ffmpeg")
        self.upload_result_sync = upload_result_sync or r2_storage.upload_file_result_sync

    def assemble(
        self,
        *,
        job_id: str,
        longform_plan_id: str,
        render_result: LongFormRenderResult,
        editor_preview: dict[str, Any] | None = None,
    ) -> FinalVideoAssemblyResult:
        """Create the final MP4, upload it, and return delivery metadata."""
        segments = _segments_from_render_result(render_result)
        if not segments:
            return FinalVideoAssemblyResult(
                status="failed",
                job_id=job_id,
                longform_plan_id=longform_plan_id,
                error="No completed segment videos were available for final assembly.",
            )
        if not self.ffmpeg_bin:
            return FinalVideoAssemblyResult(
                status="failed",
                job_id=job_id,
                longform_plan_id=longform_plan_id,
                segments=segments,
                error="FFmpeg is not installed or not available on PATH.",
            )

        work_dir = Path(tempfile.mkdtemp(prefix=f"cineforge_{job_id}_assembly_"))
        final_path = work_dir / "final.mp4"
        try:
            materialized = [
                segment.model_copy(update={"local_path": str(_materialize_source(segment.source_url, work_dir, segment.index))})
                for segment in segments
            ]
            concat_file = work_dir / "concat.txt"
            concat_file.write_text(
                "\n".join(f"file '{Path(segment.local_path or '').as_posix()}'" for segment in materialized),
                encoding="utf-8",
            )
            metadata = _metadata_from_editor_preview(editor_preview or {})
            cmd = [
                self.ffmpeg_bin,
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                *_ffmpeg_metadata_args(metadata),
                "-y",
                str(final_path),
            ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=600)
            storage_key = f"longform/{job_id}/final.mp4"
            upload_result = self.upload_result_sync(
                final_path,
                storage_key,
                content_type="video/mp4",
                presign=True,
                presigned_expires_s=int(settings.r2_final_video_presigned_expires_s or settings.r2_presigned_url_expires_s or 3600),
                access_mode=settings.r2_final_video_access_mode,
            )
            final_video_url = upload_result.delivery_url or upload_result.presigned_url or upload_result.public_url
            if not final_video_url:
                raise RuntimeError("R2 upload succeeded but did not return a URL.")
            delivered_segments = [
                segment.model_copy(update={"source_url": _delivery_segment_source(segment.source_url), "local_path": None})
                for segment in materialized
            ]
            logger.info(
                "final_video_assembly_completed",
                extra={
                    "job_id": job_id,
                    "longform_plan_id": longform_plan_id,
                    "segment_count": len(materialized),
                    "storage_key": upload_result.key,
                    "storage_bucket": upload_result.bucket,
                    "storage_access_strategy": upload_result.access_strategy,
                    "storage_type": upload_result.storage_type,
                    "is_public": upload_result.is_public,
                },
            )
            try:
                final_path.unlink(missing_ok=True)
            except OSError:
                logger.warning(
                    "final_video_local_cleanup_failed",
                    extra={"job_id": job_id},
                    exc_info=True,
                )
            return FinalVideoAssemblyResult(
                status="completed",
                job_id=job_id,
                longform_plan_id=longform_plan_id,
                final_video_path=None,
                final_video_url=final_video_url,
                storage_bucket=upload_result.bucket,
                storage_key=upload_result.key,
                storage_type=upload_result.storage_type,
                storage_access_strategy=upload_result.access_strategy,
                storage_delivery_url=upload_result.delivery_url,
                storage_cdn_url=upload_result.cdn_url,
                storage_is_public=upload_result.is_public,
                storage_public_url=upload_result.public_url,
                storage_presigned_url=upload_result.presigned_url,
                storage_presigned_expires_s=upload_result.presigned_expires_s,
                storage_presigned_expires_at=upload_result.presigned_expires_at,
                storage_refresh_supported=upload_result.refresh_supported,
                metadata_path=None,
                segments=delivered_segments,
                title=metadata.get("title"),
                caption=metadata.get("caption"),
                hashtags=list(metadata.get("hashtags") or []),
            )
        except Exception as exc:
            logger.exception(
                "final_video_assembly_failed",
                extra={"job_id": job_id, "longform_plan_id": longform_plan_id},
            )
            return FinalVideoAssemblyResult(
                status="failed",
                job_id=job_id,
                longform_plan_id=longform_plan_id,
                segments=segments,
                error=_sanitize_assembly_error(exc, work_dir=work_dir),
            )
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


def _segments_from_render_result(render_result: LongFormRenderResult) -> list[FinalAssemblySegment]:
    out: list[FinalAssemblySegment] = []
    seen: set[str] = set()
    for segment in render_result.rendered_segments:
        if segment.status != "completed" or not segment.video_url:
            continue
        key = segment.shot_id
        if key in seen:
            out = [item for item in out if item.shot_id != key]
        seen.add(key)
        out.append(FinalAssemblySegment(
            shot_id=segment.shot_id,
            index=segment.index,
            source_url=str(segment.video_url),
        ))
    return sorted(out, key=lambda item: item.index)


def _materialize_source(source_url: str | None, work_dir: Path, index: int) -> Path:
    source = str(source_url or "").strip()
    if not source:
        raise ValueError("Segment source URL is empty.")
    local = Path(source)
    if local.exists():
        return local.resolve()
    if not source.lower().startswith(("http://", "https://")):
        raise ValueError("Segment source is neither a readable local file nor an HTTP URL.")
    target = work_dir / f"segment_{index:02d}.mp4"
    with urllib.request.urlopen(source, timeout=60) as response:
        with target.open("wb") as fh:
            shutil.copyfileobj(response, fh)
    return target


def _delivery_segment_source(source_url: str | None) -> str | None:
    """Preserve public segment URLs but never expose local assembly paths."""
    source = str(source_url or "").strip()
    if source.lower().startswith(("http://", "https://")):
        return source
    return None


def _sanitize_assembly_error(exc: Exception, *, work_dir: Path) -> str:
    """Return an API-safe assembly error without local temporary paths."""
    text = str(exc).replace("\n", " ").replace("\r", " ")
    for value in {str(work_dir), work_dir.as_posix(), tempfile.gettempdir(), Path(tempfile.gettempdir()).as_posix()}:
        if value:
            text = text.replace(value, "<assembly_temp_dir>")
    return text[:500]


def _metadata_from_editor_preview(editor_preview: dict[str, Any]) -> dict[str, Any]:
    package = editor_preview.get("distribution_package") if isinstance(editor_preview, dict) else {}
    if not isinstance(package, dict):
        package = {}
    title = str(package.get("title_en") or package.get("title_vn") or package.get("title_hint") or "").strip()
    caption = str(
        package.get("caption_en")
        or package.get("caption_vn")
        or editor_preview.get("caption_en")
        or editor_preview.get("caption_vn")
        or ""
    ).strip()
    hashtags = package.get("hashtags_en") or package.get("hashtags_vn") or editor_preview.get("hashtags_en") or editor_preview.get("hashtags_vn") or []
    return {
        "title": title or None,
        "caption": caption or None,
        "hashtags": [str(tag) for tag in hashtags if str(tag).strip()],
    }


def _ffmpeg_metadata_args(metadata: dict[str, Any]) -> list[str]:
    """Convert editor metadata to conservative MP4 metadata flags."""
    args: list[str] = []
    if metadata.get("title"):
        args.extend(["-metadata", f"title={str(metadata['title'])[:120]}"])
    if metadata.get("caption"):
        args.extend(["-metadata", f"comment={str(metadata['caption'])[:500]}"])
    hashtags = [str(tag).replace("#", "").strip() for tag in metadata.get("hashtags") or [] if str(tag).strip()]
    if hashtags:
        args.extend(["-metadata", f"keywords={','.join(hashtags[:16])}"])
    return args


__all__ = [
    "FinalAssemblySegment",
    "FinalVideoAssemblyResult",
    "FinalVideoAssemblyService",
    "FinalAssemblyStatus",
]
