"""Reassemble Worker — V3 Timeline Editor re-concat từ existing clips.

Khi user chỉnh Timeline (reorder shots, swap clip refined, drop shot...),
caller gửi danh sách clip URL theo thứ tự mới → worker download → FFmpeg concat
→ color consistency pass (Bible-driven) → upload R2.

KHÔNG re-render từ AtlasCloud. Chỉ thao tác clips đã có (refined or original).
Chi phí: chỉ FFmpeg + R2 upload (~$0).
"""
from __future__ import annotations

import asyncio
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Any

import httpx
from loguru import logger

from vendors import r2_storage
from workers.assemble_worker import AssembleWorker
from workers.video_worker import _apply_color_consistency
from core import director_history


async def reassemble(
    *,
    job_id: str,
    parent_job_id: str,
    clip_urls_in_order: list[str],
    aspect_ratio: str = "9:16",
    resolution: str = "720p",
    color_grading: str = "",
    audio_plan: Optional[dict] = None,
    jobs_store: Optional[dict] = None,
) -> dict:
    """Concat clips theo thứ tự đã sắp xếp → final MP4 mới.

    Args:
        job_id:           ID cho reassemble job mới (status tracking)
        parent_job_id:    ID của job render gốc (để link history)
        clip_urls_in_order: clip URLs sorted theo Timeline order user chỉnh
        aspect_ratio:     '9:16' / '16:9' / '1:1' (cho FFmpeg scale target)
        resolution:       '720p' / '1080p' / …
        color_grading:    Bible.visual_style.color_grading string (apply lại
                          consistency pass cho final reassembled video)
        audio_plan:       optional {mode, voice_audio_url, sfx_audio_url, ...}
        jobs_store:       optional in-memory dict cho progress polling

    Returns:
        {output_path, output_url, scene_count, parent_job_id}
    """
    if not clip_urls_in_order:
        raise ValueError("clip_urls_in_order rỗng — không có gì để concat")

    _update(jobs_store, job_id, status="downloading", progress=10, current_step="download_clips")
    work_dir = Path(tempfile.gettempdir()) / f"cineforge_reassemble_{job_id}"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Download tất cả clip vào local
    local_paths: list[Path] = []
    for i, url in enumerate(clip_urls_in_order):
        dest = work_dir / f"clip_{i:02d}.mp4"
        try:
            await _download_clip(url, dest)
            local_paths.append(dest)
            _update(
                jobs_store, job_id,
                progress=10 + int(40 * (i + 1) / len(clip_urls_in_order)),
                current_step=f"downloaded_{i + 1}/{len(clip_urls_in_order)}",
            )
        except Exception as e:
            logger.exception(f"[reassemble] {job_id} download fail for {url}: {e}")
            raise RuntimeError(f"Tải clip {i+1} thất bại: {e}") from e

    # FFmpeg concat via AssembleWorker
    _update(jobs_store, job_id, status="assembling", progress=60, current_step="ffmpeg_concat")
    target_resolution = _resolution_for_aspect(aspect_ratio, resolution)
    final_mp4 = work_dir / "final.mp4"
    assembler = AssembleWorker(work_dir=str(work_dir))
    await asyncio.to_thread(
        assembler.assemble,
        video_paths=[str(p) for p in local_paths],
        audio_plan=audio_plan or {"mode": "silent_native"},
        output_path=str(final_mp4),
        bgm_path=(audio_plan or {}).get("bgm_path"),
        target_resolution=target_resolution,
    )

    # Color consistency pass (Bible-driven, reuse video_worker helper)
    _update(jobs_store, job_id, status="grading", progress=85, current_step="color_pass")
    graded_mp4 = work_dir / "final_graded.mp4"
    await asyncio.to_thread(
        _apply_color_consistency,
        str(final_mp4), str(graded_mp4), color_grading,
    )

    # Upload R2
    _update(jobs_store, job_id, status="uploading", progress=92, current_step="r2_upload")
    r2_key = f"reassemble/{parent_job_id}/{job_id}.mp4"
    output_url = await r2_storage.upload_with_fallback(
        graded_mp4, key=r2_key, content_type="video/mp4",
    )

    _update(
        jobs_store, job_id,
        status="done", progress=100, current_step="done",
        output_path=str(graded_mp4),
        output_url=output_url,
        parent_job_id=parent_job_id,
    )
    logger.info(
        f"[reassemble] {job_id} DONE — {len(clip_urls_in_order)} clips → {output_url}"
    )

    # Record vào history (riêng row, mode='reassemble', link parent_job_id qua title)
    try:
        parent = director_history.get_job(parent_job_id, include_plan=True)
        parent_title = (parent or {}).get("title") or "(reassembled)"
        director_history.record_job(
            job_id=job_id,
            plan_id=(parent or {}).get("plan_id"),
            mode="reassemble",
            status="done",
            output_url=output_url,
            title=f"{parent_title} (edit)",
            duration_s=None,  # computed from FFmpeg metadata if needed later
            cost_estimate_usd=0.0,
            plan=(parent or {}).get("plan"),
            chain=None,
        )
    except Exception as e:
        logger.warning(f"[reassemble] history record fail (non-fatal): {e}")

    # Cleanup workdir
    try:
        shutil.rmtree(work_dir)
    except OSError:
        pass

    return {
        "output_path": str(graded_mp4),
        "output_url": output_url,
        "scene_count": len(clip_urls_in_order),
        "parent_job_id": parent_job_id,
    }


# ============================================================
# Helpers
# ============================================================
def _update(store: Optional[dict], job_id: str, **fields: Any) -> None:
    if store is None:
        return
    if job_id not in store:
        store[job_id] = {}
    store[job_id].update(fields)


async def _download_clip(url: str, dest: Path) -> None:
    # Handle file:// URLs (dev mode fallback)
    if url.startswith("file://"):
        local = url.removeprefix("file://").lstrip("/")
        if ":" in local:  # Windows C:/path
            local = local.replace("/", "\\")
        src = Path(local)
        if not src.exists():
            raise FileNotFoundError(f"Local clip not found: {src}")
        shutil.copy(src, dest)
        return
    async with httpx.AsyncClient(timeout=180.0) as c:
        async with c.stream("GET", url) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                async for chunk in r.aiter_bytes(64 * 1024):
                    f.write(chunk)


def _resolution_for_aspect(aspect: str, resolution: str) -> tuple[int, int]:
    short = {
        "480p": 480, "540p": 540, "720p": 720, "720P": 720,
        "1080p": 1080, "1080P": 1080,
    }.get(resolution, 720)
    if aspect == "9:16":
        return (short * 9 // 16, short)
    if aspect == "16:9":
        return (short * 16 // 9, short)
    if aspect == "1:1":
        return (short, short)
    return (1080, 1920)
