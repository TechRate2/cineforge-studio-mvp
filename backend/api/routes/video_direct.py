"""Direct Video Generation Endpoint — bypass agent, gọi AtlasCloud trực tiếp.

User chỉnh full settings per-model spec. KHÔNG có analyzer/generator.
Spec source of truth: agent/model_specs.py
"""

from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from agent.model_specs import (
    VIDEO_MODEL_SPECS,
    get_spec,
    build_payload,
    estimate_cost,
    list_models_for_ui,
    MAX_COST_PER_VIDEO_USD,
)
from agent.model_guide import get_video_guide, recommend_for_use_case, NICHE_TAGS
from agent.model_demos import get_demos

router = APIRouter()

# In-memory job store (TODO: Postgres)
DIRECT_JOBS: dict[str, dict] = {}


class DirectVideoRequest(BaseModel):
    """Request gen video direct — pass-through đúng spec per-model.

    Frontend gửi tất cả field; backend build payload đúng cho từng model.
    """
    model_key: str = Field(..., description="Key trong VIDEO_MODEL_SPECS, e.g. 'vidu_q3_ref'")
    prompt: str = Field("", description="Text prompt")

    # Images (per-model có thể là single string hoặc list)
    images: Optional[list[str]] = Field(None, description="Reference images list (Vidu / Seedance ref)")
    image: Optional[str] = Field(None, description="First-frame URL (Wan / Seedance i2v)")
    last_image: Optional[str] = None

    # Common
    duration_s: Optional[int] = None
    resolution: Optional[str] = None
    aspect_ratio: Optional[str] = None
    negative_prompt: Optional[str] = None
    seed: Optional[int] = None

    # Per-model extras
    generate_audio: Optional[bool] = None
    movement_amplitude: Optional[str] = None
    audio_url: Optional[str] = Field(None, description="Driving audio (Wan) hoặc soundtrack")
    prompt_extend: Optional[bool] = None
    watermark: Optional[bool] = None
    return_last_frame: Optional[bool] = None
    camera_fixed: Optional[bool] = Field(None, description="Seedance v1.5 Pro — lock camera position")


@router.get("/models")
async def list_models():
    """Liệt model + UI metadata + guide curated từ feedback thực tế."""
    models = list_models_for_ui()
    # Enrich với guide + demo media URLs
    for m in models:
        m["guide"] = get_video_guide(m["key"])
        m["demos"] = get_demos(m["key"])
    return {"models": models, "available_niches": sorted(NICHE_TAGS)}


@router.get("/recommend")
async def recommend(use_case: str):
    """Recommend model phù hợp use case.

    Query: ?use_case=talking%20head%20VN
    """
    return {"use_case": use_case, "recommendations": recommend_for_use_case(use_case)}


@router.get("/models/{model_key}/spec")
async def get_model_spec(model_key: str):
    """Get full spec 1 model."""
    try:
        spec = get_spec(model_key)
        # Trả về deep dict ready cho UI render
        return {
            "key": model_key,
            **spec,
        }
    except ValueError as e:
        raise HTTPException(404, detail=str(e))


@router.post("/preview-payload")
async def preview_payload(request: DirectVideoRequest):
    """Dry-run: build payload + estimate cost, KHÔNG submit AtlasCloud.

    Frontend gọi mỗi khi user đổi setting → show cost preview + validate.
    """
    try:
        payload = build_payload(
            model_key=request.model_key,
            prompt=request.prompt,
            images=request.images,
            image=request.image,
            duration_s=request.duration_s,
            resolution=request.resolution,
            aspect_ratio=request.aspect_ratio,
            negative_prompt=request.negative_prompt,
            seed=request.seed,
            generate_audio=request.generate_audio,
            movement_amplitude=request.movement_amplitude,
            audio_url=request.audio_url,
            last_image=request.last_image,
            prompt_extend=request.prompt_extend,
            watermark=request.watermark,
            return_last_frame=request.return_last_frame,
            camera_fixed=request.camera_fixed,
        )
        spec = get_spec(request.model_key)
        duration = request.duration_s or spec["duration"]["default"]
        cost = estimate_cost(request.model_key, duration)
        return {
            "payload": payload,
            "cost_usd": round(cost, 4),
            "cost_vnd": round(cost * 24500),
            "exceeds_budget": cost > MAX_COST_PER_VIDEO_USD,
            "endpoint": spec["endpoint"],
        }
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.post("/generate")
async def generate_direct(request: DirectVideoRequest):
    """Submit job AtlasCloud (BILLABLE — gọi thật tốn tiền).

    Frontend phải confirm với user trước khi gọi endpoint này.
    """
    # 1. Build payload — validate per-spec
    try:
        payload = build_payload(
            model_key=request.model_key,
            prompt=request.prompt,
            images=request.images,
            image=request.image,
            duration_s=request.duration_s,
            resolution=request.resolution,
            aspect_ratio=request.aspect_ratio,
            negative_prompt=request.negative_prompt,
            seed=request.seed,
            generate_audio=request.generate_audio,
            movement_amplitude=request.movement_amplitude,
            audio_url=request.audio_url,
            last_image=request.last_image,
            prompt_extend=request.prompt_extend,
            watermark=request.watermark,
            return_last_frame=request.return_last_frame,
            camera_fixed=request.camera_fixed,
        )
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    # 2. Cost guard
    spec = get_spec(request.model_key)
    duration = request.duration_s or spec["duration"]["default"]
    cost = estimate_cost(request.model_key, duration)
    if cost > MAX_COST_PER_VIDEO_USD:
        raise HTTPException(
            400,
            detail=f"Job ${cost:.3f} > hard cap ${MAX_COST_PER_VIDEO_USD}. Giảm duration/đổi model.",
        )

    # 3. Submit AtlasCloud — lazy import vì atlas_client là singleton
    from vendors.atlascloud import atlas_client

    if atlas_client is None:
        raise HTTPException(
            500,
            detail="ATLASCLOUD_API_KEY chưa set trong .env.local",
        )

    job_id = str(uuid4())
    spec = get_spec(request.model_key)
    # Per-model endpoint override — Wan 2.7 video dùng /generateImage, Seedance v1.5 poll /result
    submit_path = spec.get("submit_path", "/model/generateVideo")
    poll_path = spec.get("poll_path", "/model/prediction")
    logger.info(
        f"[Direct] Submit {request.model_key} job {job_id} cost=${cost:.3f} submit={submit_path}"
    )

    try:
        from vendors.atlascloud import _unwrap
        response = atlas_client.client.post(
            f"{atlas_client.base_url}{submit_path}",
            json=payload,
        )
        response.raise_for_status()
        body = _unwrap(response.json())
        prediction_id = body.get("id") or body.get("prediction_id") or body.get("request_id")
        if not prediction_id:
            raise RuntimeError(f"AtlasCloud không trả prediction_id. Body: {body}")
    except Exception as e:
        logger.exception(f"[Direct] Submit failed: {e}")
        raise HTTPException(502, detail=f"AtlasCloud submit error: {e}")

    DIRECT_JOBS[job_id] = {
        "job_id": job_id,
        "prediction_id": prediction_id,
        "model_key": request.model_key,
        "payload": payload,
        "cost_estimate_usd": cost,
        "poll_path": poll_path,
        "status": "submitted",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "job_id": job_id,
        "prediction_id": prediction_id,
        "status": "submitted",
        "estimated_cost_usd": round(cost, 4),
        "estimated_cost_vnd": round(cost * 24500),
        "polling_url": f"/api/v1/video/direct/{job_id}",
    }


@router.delete("/{job_id}")
async def cancel_direct_job(job_id: str):
    """Cancel job + cố gắng cancel AtlasCloud để tránh charge tiếp."""
    job = DIRECT_JOBS.get(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} không tồn tại")

    from vendors.atlascloud import atlas_client
    if atlas_client is None:
        raise HTTPException(500, "AtlasCloud key chưa set")

    result = atlas_client.cancel_prediction(job["prediction_id"])
    job["status"] = "cancelled"
    return {"job_id": job_id, **result}


@router.get("/{job_id}")
async def poll_direct_job(job_id: str):
    """Poll status từ AtlasCloud, return URL khi xong.

    Doc response: { "data": { "status": "...", "outputs": [...], "error": ... } }
    """
    job = DIRECT_JOBS.get(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} không tồn tại")

    from vendors.atlascloud import atlas_client, _unwrap
    if atlas_client is None:
        raise HTTPException(500, "AtlasCloud key chưa set")

    poll_path = job.get("poll_path", "/model/prediction")
    try:
        response = atlas_client.client.get(
            f"{atlas_client.base_url}{poll_path}/{job['prediction_id']}"
        )
        response.raise_for_status()
        data = _unwrap(response.json())
    except Exception as e:
        raise HTTPException(502, detail=f"Poll error: {e}")

    status = data.get("status", "pending")
    out = {
        "job_id": job_id,
        "prediction_id": job["prediction_id"],
        "status": status,
        "model_key": job["model_key"],
    }
    if status in ("completed", "succeeded"):
        outputs = data.get("outputs", [])
        out["video_url"] = outputs[0] if outputs else data.get("output_url")
    elif status == "failed":
        out["error"] = data.get("error")

    # Update store
    job["status"] = status
    job["last_polled_at"] = datetime.now(timezone.utc).isoformat()

    return out
