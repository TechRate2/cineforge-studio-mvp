"""LLM Direct routes — audit + cost preview cho LLM provider router.

GET  /api/v1/llm/status           → provider config + available models
POST /api/v1/llm/preview-cost     → ước tính cost call
POST /api/v1/llm/test-call        → smoke test gọi 1 LLM (charge thật ~$0.0001)
"""

from typing import Optional, Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from core.config import settings
from vendors.atlascloud_llm import PRICING_PER_1M, estimate_cost_usd, atlas_llm
from vendors.llm_router import llm

router = APIRouter()


@router.get("/status")
async def llm_status():
    """Trả config + pricing snapshot + provider availability."""
    return {
        "provider": settings.llm_provider,
        "routing": {
            "analyzer": settings.llm_model_analyzer,
            "generator": settings.llm_model_generator,
            "vision": settings.llm_model_vision,
            "premium": settings.claude_model,
        },
        "keys": {
            "atlascloud_pay_as_you_go": bool(settings.atlascloud_api_key),
            "atlascloud_coding_plan": bool(settings.atlascloud_llm_api_key),
            "anthropic": bool(settings.anthropic_api_key),
        },
        "atlascloud_llm_available": atlas_llm is not None,
        "anthropic_available": bool(settings.anthropic_api_key),
        "pricing_per_1m_tokens_usd": {
            model: {"input": rates[0], "output": rates[1]}
            for model, rates in PRICING_PER_1M.items()
        },
        "available_models": list(PRICING_PER_1M.keys()),
    }


class PreviewCostRequest(BaseModel):
    model: str
    prompt_tokens: int = Field(..., ge=0)
    completion_tokens: int = Field(..., ge=0)


@router.post("/preview-cost")
async def preview_llm_cost(req: PreviewCostRequest):
    """Ước tính cost USD + VND cho call LLM."""
    if req.model not in PRICING_PER_1M:
        raise HTTPException(400, detail=f"Model '{req.model}' chưa có pricing")
    cost_usd = estimate_cost_usd(req.model, req.prompt_tokens, req.completion_tokens)
    return {
        "model": req.model,
        "prompt_tokens": req.prompt_tokens,
        "completion_tokens": req.completion_tokens,
        "cost_usd": round(cost_usd, 6),
        "cost_vnd": round(cost_usd * 24500, 2),
        "rates_per_1m": PRICING_PER_1M[req.model],
    }


class TestCallRequest(BaseModel):
    task: Literal["analyzer", "generator", "vision", "premium"] = "analyzer"
    model: Optional[str] = None
    prompt: str = Field("Trả về đúng chữ 'OK_LLM_ROUTER' và không gì khác.", min_length=1)
    max_tokens: int = Field(20, ge=1, le=200)


class EnhanceBriefRequest(BaseModel):
    """V5.2 — Magic prompt enhance: rewrite a short user brief into a richer,
    Director-friendly description with concrete visual/audio/camera details."""
    brief: str = Field(..., min_length=4, max_length=2000)
    niche_hint: Optional[str] = Field(None, max_length=80)
    duration_s: Optional[int] = Field(15, ge=3, le=120)


_ENHANCE_SYSTEM_PROMPT = (
    "Bạn là Director AI chuyên viết brief video tiếng Việt cho Director Agent. "
    "Người dùng đưa brief ngắn (vd 'review son môi'). Nhiệm vụ: viết lại brief "
    "thành mô tả 4-7 câu tiếng Việt giàu chi tiết visual + camera + lighting + "
    "mood + audio, KHÔNG bịa product features, KHÔNG thêm CTA / sale imperatives, "
    "KHÔNG dùng emoji, KHÔNG bullet list. Giữ ý gốc user nhưng bổ sung: "
    "(a) bối cảnh setting cụ thể, (b) ánh sáng + color grade, (c) camera shot "
    "+ movement, (d) mood/tone từ audio_design. Chỉ output brief văn xuôi, "
    "không prefix 'Brief:' hay markdown."
)


@router.post("/enhance-brief")
async def enhance_brief(req: EnhanceBriefRequest):
    """Magic prompt — rewrite short brief → cinematic 4-7 sentence brief."""
    user_msg = (
        f"Brief gốc của user (giữ ý chính, viết lại giàu chi tiết hơn cho video {req.duration_s}s):\n"
        f"---\n{req.brief}\n---"
    )
    if req.niche_hint:
        user_msg += f"\n\nNiche hint: {req.niche_hint}"
    try:
        text = llm.complete(
            system_prompt=_ENHANCE_SYSTEM_PROMPT,
            user_message=user_msg,
            task="generator",
            max_tokens=600,
            temperature=0.7,
        )
    except Exception as e:
        logger.exception(f"enhance-brief LLM call failed: {e}")
        raise HTTPException(502, detail=f"Enhance LLM failed: {e}")
    return {
        "original_brief": req.brief,
        "enhanced_brief": text.strip(),
        "char_count": len(text.strip()),
    }


@router.post("/test-call")
async def test_llm_call(req: TestCallRequest):
    """Smoke test gọi LLM — charge real $0.00001-$0.001 tùy model.

    ⚠️ Endpoint billable. Dùng để verify provider routing + fallback chain.
    """
    try:
        text = llm.complete(
            system_prompt="You are a strict test bot. Reply only what user asks.",
            user_message=req.prompt,
            task=req.task,
            model=req.model,
            max_tokens=req.max_tokens,
            temperature=0.0,
        )
        return {"task": req.task, "model": req.model or "default", "response": text.strip()}
    except Exception as e:
        logger.exception(f"LLM test-call failed: {e}")
        raise HTTPException(502, detail=f"LLM test failed: {e}")
