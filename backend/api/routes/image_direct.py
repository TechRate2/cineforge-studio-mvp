"""Image Direct endpoint — bypass agent, gọi AtlasCloud /model/generateImage trực tiếp."""

from typing import Optional
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from agent.image_specs import (
    IMAGE_MODEL_SPECS,
    get_image_spec,
    build_image_payload,
    estimate_image_cost,
    list_image_models_for_ui,
    MAX_COST_PER_IMAGE_USD,
)
from agent.model_guide import get_image_guide, NICHE_TAGS
from agent.model_demos import get_demos

router = APIRouter()
IMAGE_JOBS: dict[str, dict] = {}


class DirectImageRequest(BaseModel):
    model_key: str
    prompt: str = Field("", min_length=0)
    images: Optional[list[str]] = None
    size: Optional[str] = None
    aspect_ratio: Optional[str] = None
    resolution: Optional[str] = None
    negative_prompt: Optional[str] = None
    seed: Optional[int] = None
    n: Optional[int] = None
    output_format: Optional[str] = None
    media_resolution: Optional[str] = None
    thinking_level: Optional[str] = None
    thinking_mode: Optional[bool] = None
    enable_web_search: Optional[bool] = None
    enable_image_search: Optional[bool] = None
    enable_base64_output: Optional[bool] = None
    enable_sync_mode: Optional[bool] = None


@router.get("/models")
async def list_models():
    models = list_image_models_for_ui()
    for m in models:
        m["guide"] = get_image_guide(m["key"])
        m["demos"] = get_demos(m["key"])
    return {"models": models, "available_niches": sorted(NICHE_TAGS)}


@router.get("/models/{model_key}/spec")
async def get_model_spec(model_key: str):
    try:
        spec = get_image_spec(model_key)
        return {"key": model_key, **spec}
    except ValueError as e:
        raise HTTPException(404, detail=str(e))


@router.post("/preview-payload")
async def preview_payload(request: DirectImageRequest):
    try:
        payload = build_image_payload(**request.model_dump(exclude_none=False))
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    n = request.n or 1
    cost = estimate_image_cost(request.model_key, n)
    spec = get_image_spec(request.model_key)
    return {
        "payload": payload,
        "cost_usd": round(cost, 4),
        "cost_vnd": round(cost * 24500),
        "exceeds_budget": cost > MAX_COST_PER_IMAGE_USD,
        "endpoint": spec["endpoint"],
    }


@router.post("/generate")
async def generate(request: DirectImageRequest):
    try:
        payload = build_image_payload(**request.model_dump(exclude_none=False))
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    cost = estimate_image_cost(request.model_key, request.n or 1)
    if cost > MAX_COST_PER_IMAGE_USD:
        raise HTTPException(400, detail=f"Cost ${cost:.3f} > cap ${MAX_COST_PER_IMAGE_USD}")

    from vendors.atlascloud import atlas_client
    if atlas_client is None:
        raise HTTPException(500, detail="ATLASCLOUD_API_KEY chưa set")

    job_id = str(uuid4())
    spec = get_image_spec(request.model_key)
    # Per-model endpoint override (Seedream uses /generateVideo + /result, others /generateImage + /prediction)
    submit_path = spec.get("submit_path", "/model/generateImage")
    poll_path = spec.get("poll_path", "/model/prediction")
    logger.info(
        f"[Image Direct] {request.model_key} job {job_id} cost=${cost:.3f} submit={submit_path}"
    )

    from vendors.atlascloud import _unwrap

    try:
        response = atlas_client.client.post(
            f"{atlas_client.base_url}{submit_path}",
            json=payload,
        )
        response.raise_for_status()
        body = _unwrap(response.json())
        prediction_id = body.get("id") or body.get("prediction_id") or body.get("request_id")
        if not prediction_id:
            raise RuntimeError(f"AtlasCloud không trả prediction_id. Body: {body}")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[Image Direct] Submit failed: {e}")
        raise HTTPException(502, detail=f"AtlasCloud error: {e}")

    IMAGE_JOBS[job_id] = {
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
        "polling_url": f"/api/v1/image/direct/{job_id}",
    }


@router.delete("/{job_id}")
async def cancel_image_job(job_id: str):
    """Cancel job + cancel AtlasCloud prediction để khỏi charge tiếp."""
    job = IMAGE_JOBS.get(job_id)
    if not job:
        raise HTTPException(404, f"Image job {job_id} không tồn tại")

    from vendors.atlascloud import atlas_client
    if atlas_client is None:
        raise HTTPException(500, "AtlasCloud key chưa set")

    result = atlas_client.cancel_prediction(job["prediction_id"])
    job["status"] = "cancelled"
    return {"job_id": job_id, **result}


@router.get("/{job_id}")
async def poll(job_id: str):
    job = IMAGE_JOBS.get(job_id)
    if not job:
        raise HTTPException(404, f"Image job {job_id} không tồn tại")

    from vendors.atlascloud import atlas_client, _unwrap
    if atlas_client is None:
        raise HTTPException(500, "AtlasCloud key chưa set")

    poll_path = job.get("poll_path", "/model/prediction")
    try:
        r = atlas_client.client.get(
            f"{atlas_client.base_url}{poll_path}/{job['prediction_id']}"
        )
        r.raise_for_status()
        data = _unwrap(r.json())
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
        out["image_urls"] = outputs
        out["image_url"] = outputs[0] if outputs else data.get("output_url")
    elif status == "failed":
        out["error"] = data.get("error")
    job["status"] = status
    return out
