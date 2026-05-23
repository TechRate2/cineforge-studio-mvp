"""⚠️ LEGACY render queue — `/api/v1/jobs/*`.

============================================================
    DEPRECATION NOTICE — DO NOT BUILD NEW FEATURES HERE
============================================================
This module is kept ONLY for backwards-compatibility with external clients still
posting to /api/v1/jobs/ugc. The canonical render path is now:

    POST /api/v1/director/generate   (see api/routes/director.py)

Differences:
    • V3 (/director/generate)  — accepts a full DirectorPlan or a plan_request and
                                  runs `workers/video_worker.render_plan()` (Reference
                                  Chaining + color consistency).
    • Legacy (this file)       — runs `workers/render_pipeline.py` (old multi-scene /
                                  approved-script paths).

Only **Director-approved input** is accepted here. Requests without
`approved_shots` + `approved_character_sheet` are rejected with 410 Gone so users
discover the new endpoint immediately. The auto-pick fallback path was removed.

Removal target: the next major release after frontend Studio V4 fully migrates to
DirectorPlanModal (already wired in StudioMain.tsx as of V3 refactor).
"""

import asyncio
from uuid import UUID, uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, BackgroundTasks, Header
from loguru import logger

from api.schemas import (
    CreateJobRequest,
    JobCreatedResponse,
    JobStatus,
)
from agent.model_adapter import (
    estimate_total_job_cost,
    get_model_info,
    MAX_COST_PER_VIDEO_USD,
)
from workers import render_pipeline
from core.jobs_store import JOBS, create as _create_job, update as _update_job_store
from core.idempotency import hash_body as _hash_body, lookup as _idem_lookup, store as _idem_store


router = APIRouter()


# ============================================================
# Background runner — Director-approved path ONLY
# ============================================================
async def _run_director_approved_render(job_id: UUID, request_dump: dict) -> None:
    """Run legacy render pipeline against a Director-approved payload.

    Dispatch priority:
        1. approved_scenes[]    → render_pipeline.render_scenes (multi-scene queue)
        2. approved_shots[]     → render_pipeline.render_approved (V3 strategy.build_prompt)

    NOTE: any input missing both is rejected upstream (see _require_director_approved).
    """
    job_id_str = str(job_id)
    try:
        if request_dump.get("approved_scenes"):
            await render_pipeline.render_scenes(job_id_str, request_dump, JOBS)
        elif request_dump.get("approved_shots") or request_dump.get("approved_script"):
            await render_pipeline.render_approved(job_id_str, request_dump, JOBS)
        else:
            # defensive — endpoint should have rejected earlier
            raise RuntimeError("legacy /jobs/ugc requires Director-approved payload")
    except Exception as e:
        logger.exception(f"[LEGACY /jobs/ugc] Job {job_id} failed: {e}")
        _update_job_store(job_id, status="failed", error_message=str(e)[:300])


def _require_director_approved(request: CreateJobRequest) -> None:
    """Reject any request that did not come from /api/v1/director/plan approval.

    Required fields (set by frontend after user approves DirectorPlan):
        - approved_shots          : list[dict]   (from cinematic_brief / Bible)
        - approved_character_sheet: dict         (character anchor)
    OR (older Multi-Scene UI variant):
        - approved_scenes         : list[ApprovedScene]

    Raise 410 Gone with migration hint when missing.
    """
    has_v3 = bool(request.approved_shots and request.approved_character_sheet)
    has_multi_scene = bool(request.approved_scenes)
    if not (has_v3 or has_multi_scene):
        raise HTTPException(
            status_code=410,
            detail=(
                "Legacy /api/v1/jobs/ugc requires a Director-approved payload "
                "(approved_shots + approved_character_sheet, OR approved_scenes). "
                "Please migrate to POST /api/v1/director/generate which handles "
                "Continuity Bible + Shot List + Reference Chaining end-to-end."
            ),
        )


# ============================================================
# POST /api/v1/jobs/ugc — Director-approved render only
# ============================================================
@router.post("/ugc", response_model=JobCreatedResponse, deprecated=True)
async def create_ugc_job(
    request: CreateJobRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str = Header(None, alias="Idempotency-Key"),
):
    """⚠️ LEGACY — kept for back-compat. New code MUST call /api/v1/director/generate.

    This endpoint only accepts a Director-approved payload. The old AI auto-pick
    fallback has been removed.
    """
    logger.warning(
        "[LEGACY /jobs/ugc] called — please migrate to /api/v1/director/generate "
        f"(model={request.settings.model}, refs={len(request.reference_images)})"
    )

    _require_director_approved(request)

    # ---- Idempotency-Key (Stripe pattern, kept for parity) ----
    if idempotency_key:
        body_hash = _hash_body(request.model_dump())
        cached = _idem_lookup(idempotency_key, body_hash)
        if cached:
            if not cached["body_match"]:
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency-Key đã dùng với body khác. Đổi key hoặc đợi 24h.",
                )
            logger.info(
                f"[LEGACY /jobs/ugc] Idempotency cache HIT key={idempotency_key[:16]}… — replay"
            )
            return cached["response_json"]

    job_id = uuid4()
    logger.info(
        f"[LEGACY /jobs/ugc] Job {job_id} — DIRECTOR-APPROVED PATH "
        f"(proposal_id={request.proposal_id}, model={request.settings.model})"
    )

    # ---- Model + spec validation ----
    model_info = get_model_info(request.settings.model)

    if len(request.reference_images) > model_info["max_references"]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Model {request.settings.model} chỉ support tối đa "
                f"{model_info['max_references']} reference, nhận {len(request.reference_images)}."
            ),
        )

    # Min refs check (e.g. Vidu Q3 ref-to-video needs >=1)
    try:
        from agent.model_specs import VIDEO_MODEL_SPECS
        _model_to_atlas = {
            "vidu_q3": "vidu_q3_ref", "vidu_q3_mix": "vidu_q3_mix_ref",
            "wan_2_7": "wan_2_7_i2v",
            "seedance_1_5_pro": "seedance_v15_pro_i2v",
            "seedance_2_0": "seedance_2_0_ref",
            "seedance_2_0_fast": "seedance_2_0_fast_ref",
            "auto": "vidu_q3_ref",
        }
        atlas_key = _model_to_atlas.get(request.settings.model, "vidu_q3_ref")
        spec = VIDEO_MODEL_SPECS.get(atlas_key, {})
        min_refs = spec.get("min_references", 0)
        if min_refs > 0 and len(request.reference_images) < min_refs:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Model {request.settings.model} cần tối thiểu {min_refs} reference, "
                    f"nhận {len(request.reference_images)}."
                ),
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[LEGACY /jobs/ugc] min_refs validate fail (non-fatal): {e}")

    # Audio / model compat
    if request.settings.audio_mode == "dialogue_vo" and model_info.get("supports_silent_only"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Model {request.settings.model} silent-only — không thể inject voice trực tiếp. "
                "Đổi sang vidu_q3 / wan_2_7, hoặc giữ silent_native + overlay TTS post-prod."
            ),
        )

    # Cost cap
    cost = estimate_total_job_cost(
        request.settings.model, request.settings.duration_s, request.settings.audio_mode,
    )
    if cost["exceeds_budget"]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Job ước tính ${cost['total_usd']} > giới hạn ${MAX_COST_PER_VIDEO_USD}. "
                "Giảm duration hoặc đổi model rẻ hơn."
            ),
        )

    # Voice persona validation (fail-fast)
    voice_persona = request.settings.voice_persona
    if voice_persona:
        from vendors.genmax import VIETNAMESE_VOICE_PRESETS
        if voice_persona not in VIETNAMESE_VOICE_PRESETS and not _looks_like_voice_id(voice_persona):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"voice_persona '{voice_persona}' không hợp lệ. "
                    f"Preset alias: {list(VIETNAMESE_VOICE_PRESETS.keys())} hoặc UUID voice_id."
                ),
            )

    # Persist + dispatch
    _create_job(job_id, {
        "request": request.model_dump(),
        "status": "pending",
        "progress": 0,
        "current_step": None,
        "cost_estimate_usd": cost["total_usd"],
        "cost_breakdown": cost,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    background_tasks.add_task(_run_director_approved_render, job_id, request.model_dump())

    response = JobCreatedResponse(
        job_id=job_id,
        status="pending",
        estimated_duration_s=180,
        estimated_cost_usd=cost["total_usd"],
        polling_url=f"/api/v1/jobs/{job_id}",
    )

    if idempotency_key:
        _idem_store(
            idempotency_key,
            _hash_body(request.model_dump()),
            response.model_dump(),
            status_code=201,
        )

    return response


# ============================================================
# Poll / download / cancel — unchanged from V2 (legacy clients depend on these)
# ============================================================
@router.get("/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: UUID):
    """⚠️ LEGACY poll endpoint. New code: GET /api/v1/director/jobs/{id}."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} không tồn tại")

    output_url = job.get("output_url")
    if output_url and output_url.startswith("file://"):
        output_url = f"/api/v1/jobs/{job_id}/download"

    return JobStatus(
        job_id=job["job_id"],
        status=job["status"],
        progress=job["progress"],
        current_step=job.get("current_step"),
        estimated_remaining_s=job.get("estimated_remaining_s"),
        output_url=output_url,
        thumbnail_url=job.get("thumbnail_url"),
        duration_s=job.get("duration_s"),
        cost_actual_usd=job.get("cost_actual_usd"),
        error_message=job.get("error_message"),
        created_at=job["created_at"],
        updated_at=job["updated_at"],
    )


@router.get("/{job_id}/download")
async def download_job_output(job_id: UUID):
    """⚠️ LEGACY — serve final MP4 from local temp (dev mode before R2 setup).

    Sprint2 M9 — path traversal guard. The `output_url` field is set by the
    render worker and SHOULD be a tempfile path, but a malicious job record
    (or DB tampering) could insert `file:///etc/passwd`. We canonicalize the
    resolved path and reject anything outside the allowed tempfile prefix.
    """
    from fastapi.responses import FileResponse
    from pathlib import Path as _P
    import tempfile as _tempfile

    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} không tồn tại")

    raw_url = job.get("output_url") or ""
    if not raw_url.startswith("file://"):
        raise HTTPException(
            status_code=400,
            detail="Output đã upload R2 — dùng output_url trực tiếp, không cần download endpoint.",
        )

    local_path = raw_url[len("file://"):]
    if "\\" in raw_url and not local_path.startswith("/"):
        local_path = local_path.lstrip("/").replace("/", "\\")

    # CRITICAL — resolve to canonical absolute path then check whitelist.
    # Allowed prefixes: system temp dir (where renders write).
    try:
        p = _P(local_path).resolve(strict=False)
    except (OSError, RuntimeError) as e:
        raise HTTPException(400, f"Invalid path: {e}") from e

    allowed_root = _P(_tempfile.gettempdir()).resolve()
    try:
        p.relative_to(allowed_root)
    except ValueError:
        # Path is OUTSIDE the temp dir — likely traversal attempt
        raise HTTPException(
            403,
            "Refused — output path outside the allowed temp directory. "
            "If this is a legitimate render output, ensure it was written by "
            "the render worker (paths under system temp dir only).",
        )

    if not p.exists():
        raise HTTPException(status_code=404, detail=f"File không tồn tại: {p.name}")

    return FileResponse(
        path=str(p),
        media_type="video/mp4",
        filename=f"ugc_video_{job_id}.mp4",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.delete("/{job_id}")
async def cancel_job(job_id: UUID):
    """⚠️ LEGACY cancel. New code: POST /api/v1/director/jobs/{id}/cancel."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} không tồn tại")

    if job["status"] in ("done", "failed"):
        raise HTTPException(status_code=400, detail=f"Job đã terminal: {job['status']}")

    atlas_prediction_id = job.get("atlas_prediction_id")
    if atlas_prediction_id:
        try:
            from vendors.atlascloud import atlas_client
            if atlas_client:
                await asyncio.to_thread(atlas_client.cancel_prediction, atlas_prediction_id)
                logger.info(
                    f"[LEGACY /jobs/cancel] AtlasCloud prediction {atlas_prediction_id} cancelled"
                )
        except Exception as e:
            logger.warning(
                f"[LEGACY /jobs/cancel] AtlasCloud cancel fail: {e} — user có thể vẫn bị charge"
            )

    _update_job_store(job_id, status="failed", error_message="Cancelled by user")
    return {"status": "cancelled", "job_id": str(job_id)}


# ============================================================
# Helpers
# ============================================================
def _looks_like_voice_id(s: str) -> bool:
    """UUID-ish or 16+ char alphanumeric ID."""
    if not s:
        return False
    return len(s) >= 16 and all(c.isalnum() or c == "-" for c in s)
