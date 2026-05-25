"""LLM Direct routes — audit + cost preview cho LLM provider router.

GET  /api/v1/llm/status           → provider config + available models
POST /api/v1/llm/preview-cost     → ước tính cost call
POST /api/v1/llm/test-call        → smoke test gọi 1 LLM (charge thật ~$0.0001)
POST /api/v1/llm/enhance-brief    → V5.17 Smart Enhance: brief → structured JSON
                                    with suggestions + vision_notes (reused by Director)
"""

from typing import Optional, Literal, Any
import json
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from core.config import settings
from vendors.atlascloud_llm import PRICING_PER_1M, estimate_cost_usd, atlas_llm
from vendors.llm_router import llm


_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _safe_parse_json_or_none(text: str) -> Optional[dict]:
    """Best-effort JSON parse — strip fences, brace-trim fallback, return None on fail."""
    stripped = _JSON_FENCE_RE.sub("", text).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(stripped[start:end + 1])
            except json.JSONDecodeError:
                return None
        return None

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
    Director-friendly description with concrete visual/audio/camera details.

    V5.12 — accept `reference_image_urls` so when user has uploaded refs,
    Enhance uses vision LLM (Qwen3-VL) to ACTUALLY LOOK at the images and
    describe what's in them (e.g. "cô gái mặc áo đỏ basic" instead of
    auto-generic "cô gái áo trắng"). Cost: ~$0.002/call via Qwen3-VL.
    """
    brief: str = Field(..., min_length=4, max_length=2000)
    niche_hint: Optional[str] = Field(None, max_length=80)
    duration_s: Optional[int] = Field(15, ge=3, le=120)
    reference_image_urls: list[str] = Field(default_factory=list, max_length=6)


# V5.17 Smart Enhance — structured JSON output for FE auto-apply +
# Director-reusable vision notes. Both prompts request the SAME schema so
# FE has one consistent contract regardless of text/vision mode.
_ENHANCE_JSON_SCHEMA_INSTRUCTION = (
    "OUTPUT DUY NHẤT MỘT JSON OBJECT (không markdown fence, không text trước/sau). "
    "Schema CHÍNH XÁC:\n"
    "{\n"
    '  "enhanced_brief": "<4-7 câu văn xuôi tiếng Việt giàu chi tiết visual + camera + lighting + mood>",\n'
    '  "vision_notes": {\n'
    '    "character": "<face / hair / outfit / expression CHÍNH XÁC từ ảnh; null nếu không ảnh người>",\n'
    '    "product": "<color / packaging / logo từ ảnh sản phẩm; null nếu không có>",\n'
    '    "style_ref": "<mood / color_grade từ ảnh phong cách; null nếu không có>"\n'
    '  },\n'
    '  "suggested_niche": "<beauty | food | tech | lifestyle | fashion | drama | ugc_review | ...>",\n'
    '  "suggested_mood": "<vd: \'intimate warm afternoon\' | \'dramatic dark cinematic\' | \'energetic playful\'>",\n'
    '  "suggested_hook_pattern": "<EXACTLY 1 of: pattern_interrupt | direct_question | bold_statement | visual_paradox | action_reveal | before_after | time_compression | sensory_overload | expectation_subvert | character_intro>",\n'
    '  "suggested_num_shots": <integer 1-6, dựa duration + brief complexity>,\n'
    '  "suggested_model": "<EXACTLY 1 of: auto | seedance_2_0 | seedance_2_0_fast | seedance_1_5_pro | vidu_q3 | wan_2_7>",\n'
    '  "suggested_audio_mode": "<EXACTLY 1 of: silent_native | dialogue_vo | asmr_macro>"\n'
    "}\n"
    "Quy tắc model picking: brief có lời thoại tiếng Việt → wan_2_7 (lip-sync). "
    "Multi-cảnh cinematic ≤15s → seedance_2_0 hoặc seedance_2_0_fast. "
    "Đơn cảnh i2v ≤12s → seedance_1_5_pro. Budget UGC → vidu_q3. Không chắc → auto."
)

_ENHANCE_SYSTEM_PROMPT_TEXT = (
    "Bạn là Director AI chuyên viết brief video tiếng Việt cho Director Agent. "
    "Người dùng đưa brief ngắn (vd 'review son môi'). Nhiệm vụ: viết lại brief "
    "thành mô tả 4-7 câu tiếng Việt giàu chi tiết visual + camera + lighting + "
    "mood + audio, KHÔNG bịa product features, KHÔNG CTA / sale imperatives, "
    "KHÔNG emoji, KHÔNG bullet list. Giữ ý gốc user nhưng bổ sung: "
    "(a) bối cảnh setting cụ thể, (b) ánh sáng + color grade, (c) camera shot "
    "+ movement, (d) mood/tone audio. Vì không có ảnh ref, set vision_notes "
    "các field về null.\n\n"
    + _ENHANCE_JSON_SCHEMA_INSTRUCTION
)

_ENHANCE_SYSTEM_PROMPT_VISION = (
    "Bạn là Director AI chuyên viết brief video tiếng Việt cho Director Agent. "
    "Người dùng cung cấp brief ngắn + 1-6 ảnh tham khảo (nhân vật, sản phẩm, mood). "
    "Nhiệm vụ:\n"
    "1. NHÌN KỸ từng ảnh — note CHÍNH XÁC những gì thấy: màu trang phục, kiểu tóc, "
    "   khuôn mặt, biểu cảm; với sản phẩm: màu sắc, packaging, logo cụ thể.\n"
    "2. Viết enhanced_brief 4-7 câu tiếng Việt KHỚP CHÍNH XÁC ảnh, KHÔNG mô tả KHÁC.\n"
    "3. Điền vision_notes với chi tiết extract được từ ảnh (Director sẽ reuse).\n"
    "4. KHÔNG bịa features sản phẩm KHÔNG thấy. KHÔNG CTA. KHÔNG emoji.\n\n"
    + _ENHANCE_JSON_SCHEMA_INSTRUCTION
)


@router.post("/enhance-brief")
async def enhance_brief(req: EnhanceBriefRequest):
    """V5.17 Smart Enhance — brief → structured JSON with suggestions.

    Modes:
      - vision (when refs uploaded): Qwen3-VL extracts character/product/style
        details + returns enhanced brief + 6 suggested settings.
      - text-only: DeepSeek V4 Flash returns same JSON shape with null
        vision_notes.

    FE auto-applies `suggested_*` fields to settings (user can override).
    Director Agent reads `vision_notes` from context_injection to SKIP its
    own vision pass — saves ~$0.0004 per /plan call.
    """
    user_msg = (
        f"Brief gốc của user (giữ ý chính, viết lại giàu chi tiết hơn cho video {req.duration_s}s):\n"
        f"---\n{req.brief}\n---"
    )
    if req.niche_hint:
        user_msg += f"\n\nNiche hint: {req.niche_hint}"

    refs = [u for u in (req.reference_image_urls or []) if u and u.startswith("http")][:6]
    try:
        if refs:
            user_msg += (
                f"\n\nQUAN TRỌNG: User đã upload {len(refs)} ảnh tham khảo. "
                f"Hãy nhìn kỹ và mô tả CHÍNH XÁC những gì thấy — viết lại brief "
                f"khớp với ảnh thực, KHÔNG bịa khác."
            )
            raw = llm.complete_with_image(
                system_prompt=_ENHANCE_SYSTEM_PROMPT_VISION,
                user_message=user_msg,
                image_urls=refs,
                task="vision",
                max_tokens=1200,  # V5.17 — bigger cap for structured JSON
            )
            mode = "vision"
        else:
            raw = llm.complete(
                system_prompt=_ENHANCE_SYSTEM_PROMPT_TEXT,
                user_message=user_msg,
                task="generator",
                max_tokens=1000,  # V5.17 — bigger cap for structured JSON
                temperature=0.5,  # V5.17 — lowered for consistent JSON output
            )
            mode = "text"
    except Exception as e:
        logger.exception(f"enhance-brief LLM call failed: {e}")
        raise HTTPException(502, detail=f"Enhance LLM failed: {e}")

    # V5.17 — Parse structured JSON. On parse fail, gracefully fall back to
    # legacy shape (enhanced_brief only) so existing FE doesn't crash.
    parsed = _safe_parse_json_or_none(raw)
    if parsed is None or not isinstance(parsed, dict):
        logger.warning(
            f"[enhance-brief] LLM returned non-JSON (mode={mode}), "
            f"falling back to legacy text. Head: {raw[:200]}"
        )
        return {
            "original_brief": req.brief,
            "enhanced_brief": raw.strip(),
            "char_count": len(raw.strip()),
            "mode": mode,
            "refs_seen": len(refs),
            "suggested_niche": None,
            "suggested_mood": None,
            "suggested_hook_pattern": None,
            "suggested_num_shots": None,
            "suggested_model": None,
            "suggested_audio_mode": None,
            "vision_notes": None,
        }

    enhanced_brief = str(parsed.get("enhanced_brief", "")).strip() or req.brief

    # Whitelist validate suggested_model so we never send a typo back to FE
    _ALLOWED_MODELS = {
        "auto", "seedance_2_0", "seedance_2_0_fast", "seedance_1_5_pro",
        "vidu_q3", "vidu_q3_mix", "wan_2_7",
    }
    _ALLOWED_AUDIO = {"silent_native", "dialogue_vo", "asmr_macro"}
    _ALLOWED_HOOKS = {
        "pattern_interrupt", "direct_question", "bold_statement", "visual_paradox",
        "action_reveal", "before_after", "time_compression", "sensory_overload",
        "expectation_subvert", "character_intro",
    }

    def _safe_pick(value: Any, allowed: set) -> Optional[str]:
        if isinstance(value, str) and value in allowed:
            return value
        return None

    def _safe_int(value: Any, lo: int, hi: int) -> Optional[int]:
        try:
            n = int(value)
            if lo <= n <= hi:
                return n
        except (TypeError, ValueError):
            pass
        return None

    return {
        "original_brief": req.brief,
        "enhanced_brief": enhanced_brief,
        "char_count": len(enhanced_brief),
        "mode": mode,
        "refs_seen": len(refs),
        # V5.17 — Smart suggestions (FE auto-applies; user can override)
        "suggested_niche": (
            str(parsed.get("suggested_niche", "")).strip()[:40] or None
        ),
        "suggested_mood": (
            str(parsed.get("suggested_mood", "")).strip()[:120] or None
        ),
        "suggested_hook_pattern": _safe_pick(parsed.get("suggested_hook_pattern"), _ALLOWED_HOOKS),
        "suggested_num_shots": _safe_int(parsed.get("suggested_num_shots"), 1, 6),
        "suggested_model": _safe_pick(parsed.get("suggested_model"), _ALLOWED_MODELS),
        "suggested_audio_mode": _safe_pick(parsed.get("suggested_audio_mode"), _ALLOWED_AUDIO),
        # V5.17 — Vision notes for Director Agent to reuse (skip its own vision pass)
        "vision_notes": (
            parsed.get("vision_notes") if isinstance(parsed.get("vision_notes"), dict) else None
        ),
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
