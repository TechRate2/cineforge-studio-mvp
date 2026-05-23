"""Audio Direct endpoint — TTS via GenMax (12 voices VN preset).

Mặc định ElevenLabs voice library qua GenMax aggregator.
"""

from typing import Optional
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from vendors.genmax import (
    genmax_client,
    VIETNAMESE_VOICE_PRESETS,
)

router = APIRouter()
AUDIO_JOBS: dict[str, dict] = {}


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    voice_preset: Optional[str] = Field(
        None, description="Alias: mai / ngan / tran / duc_huy / ninh_don / quan / tu_anh / ngoc_huyen / anh_khoi / nghi_luc / vui_ve / phat_phap"
    )
    voice_id: Optional[str] = Field(None, description="Override voice_id (UUID hoặc ElevenLabs ID)")
    provider: str = Field("elevenlabs", description="elevenlabs | minimax")
    stability: float = Field(0.5, ge=0.0, le=1.0)
    similarity_boost: float = Field(0.75, ge=0.0, le=1.0)
    speed: float = Field(1.0, ge=0.5, le=2.0)


@router.get("/voices")
async def list_voices():
    """List 12 voice VN preset có sẵn (6 ElevenLabs premium + 6 MiniMax budget)."""
    voices = []
    for alias, cfg in VIETNAMESE_VOICE_PRESETS.items():
        voices.append({
            "alias": alias,
            "voice_id": cfg["voice_id"],
            "provider": cfg["provider"],
            "label_vn": cfg["label_vn"],
            "gender": cfg["gender"],
            "tier": cfg.get("tier", "premium"),
        })
    return {"voices": voices, "total": len(voices)}


def _resolve_provider(req: "TTSRequest") -> str:
    """Resolve provider từ preset alias hoặc voice_id lookup, fallback request.provider."""
    if req.voice_preset:
        cfg = VIETNAMESE_VOICE_PRESETS.get(req.voice_preset)
        if cfg:
            return cfg["provider"]
    if req.voice_id:
        for cfg in VIETNAMESE_VOICE_PRESETS.values():
            if cfg["voice_id"] == req.voice_id:
                return cfg["provider"]
    return req.provider


@router.post("/preview-cost")
async def preview_cost(request: TTSRequest):
    """Dry-run cost estimate.

    GenMax pricing rough: ~1 credit / 100 chars (ElevenLabs tier) hoặc 0.5/100 (MiniMax).
    4000 credits = ~$80 USD nạp đầu.
    """
    char_count = len(request.text)
    provider = _resolve_provider(request)
    credits_per_100 = 0.5 if provider == "minimax" else 1.0
    estimated_credits = (char_count / 100) * credits_per_100
    # Rough VND: 1 credit ≈ 500đ (dựa pricing $80 / 4000 credit / 24500)
    estimated_vnd = round(estimated_credits * 500)
    return {
        "char_count": char_count,
        "estimated_credits": round(estimated_credits, 2),
        "estimated_vnd": estimated_vnd,
        "provider": provider,
    }


@router.post("/generate")
async def generate_tts(request: TTSRequest):
    """Submit TTS job (BILLABLE)."""
    if genmax_client is None:
        raise HTTPException(500, detail="GENMAX_API_KEY chưa set")

    # Resolve voice_id
    if request.voice_preset:
        cfg = VIETNAMESE_VOICE_PRESETS.get(request.voice_preset)
        if not cfg:
            raise HTTPException(400, detail=f"Voice preset '{request.voice_preset}' không tồn tại")
        voice_id = cfg["voice_id"]
        provider = cfg["provider"]
    else:
        voice_id = request.voice_id
        provider = request.provider
        if not voice_id:
            raise HTTPException(400, detail="Cần voice_preset hoặc voice_id")

    job_id = str(uuid4())
    logger.info(f"[Audio] TTS {provider}/{voice_id} text len={len(request.text)}")

    try:
        submit_resp = genmax_client.text_to_speech(
            text=request.text,
            voice_id=voice_id,
            provider=provider,
            stability=request.stability,
            similarity_boost=request.similarity_boost,
            speed=request.speed,
        )
    except Exception as e:
        logger.exception(f"[Audio] TTS submit failed: {e}")
        raise HTTPException(502, detail=f"GenMax TTS error: {e}")

    history_id = submit_resp.get("id") or submit_resp.get("history_id")
    if not history_id:
        raise HTTPException(502, detail=f"GenMax không trả task id: {submit_resp}")

    # GenMax async — poll history/{id} until completed (typical <15s)
    try:
        final = genmax_client.poll_until_done(history_id, timeout_s=60, interval_s=2.0)
    except Exception as e:
        logger.exception(f"[Audio] TTS poll failed: {e}")
        raise HTTPException(502, detail=f"GenMax poll error: {e}")

    status = final.get("status", "pending")
    audio_url = (final.get("result") or {}).get("audio_url") or final.get("audio_url")
    credits_deducted = final.get("credits_deducted")

    AUDIO_JOBS[job_id] = {
        "job_id": job_id,
        "voice_id": voice_id,
        "provider": provider,
        "text_preview": request.text[:120],
        "audio_url": audio_url,
        "history_id": history_id,
        "status": status,
        "credits_deducted": credits_deducted,
        "raw_response": final,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if status not in ("completed", "succeeded", "success") or not audio_url:
        # Trả về để frontend tiếp tục poll qua GET /{job_id}
        return {
            "job_id": job_id,
            "history_id": history_id,
            "status": status,
            "audio_url": None,
            "voice_id": voice_id,
            "provider": provider,
            "error": final.get("error") or final.get("detail_error"),
        }

    return {
        "job_id": job_id,
        "history_id": history_id,
        "status": status,
        "audio_url": audio_url,
        "credits_deducted": credits_deducted,
        "voice_id": voice_id,
        "provider": provider,
    }


@router.get("/{job_id}")
async def get_job(job_id: str):
    """Re-poll GenMax nếu job chưa completed (async TTS có thể chạy >60s)."""
    job = AUDIO_JOBS.get(job_id)
    if not job:
        raise HTTPException(404, f"Audio job {job_id} không tồn tại")

    # Nếu đã có audio_url → trả cache (không gọi GenMax thừa)
    if job.get("audio_url") and job.get("status") in ("completed", "succeeded", "success"):
        return job

    # Còn processing → re-fetch live từ GenMax
    if genmax_client and job.get("history_id"):
        try:
            d = genmax_client.get_history_detail(job["history_id"])
            job["status"] = d.get("status", job.get("status", "pending"))
            job["audio_url"] = (d.get("result") or {}).get("audio_url") or job.get("audio_url")
            job["credits_deducted"] = d.get("credits_deducted") or job.get("credits_deducted")
            job["error"] = d.get("error") or d.get("detail_error")
            job["raw_response"] = d
        except Exception as e:
            logger.warning(f"[Audio] Re-poll {job_id} failed: {e}")
    return job
