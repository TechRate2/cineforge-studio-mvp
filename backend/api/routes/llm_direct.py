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


# V5.17.5 — Helpers cho adaptive Enhance (H1+H2+H3)

def _sentence_range_for_duration(duration_s: int) -> str:
    """H2 — số câu enhanced_brief adapt theo duration video.
    Brief ngắn không cần 7 câu, brief dài cần arc kể chuyện."""
    if duration_s <= 10:
        return "3-5 câu (single beat, focus 1 hành động chính)"
    if duration_s <= 30:
        return "5-8 câu (mở-thân-đóng, có chuyển cảnh)"
    return "8-12 câu (có arc kể chuyện: hook → tension → reveal → proof)"


def _max_tokens_for_duration(duration_s: int, mode: str) -> int:
    """H1 — max_tokens scale theo duration để không waste + không truncate.
    mode='vision' cần thêm tokens cho vision_notes detail."""
    if duration_s <= 10:
        return 800 if mode == "vision" else 700
    if duration_s <= 30:
        return 1300 if mode == "vision" else 1100
    # Long-form 30-120s needs full storytelling arc
    return 2000 if mode == "vision" else 1800


def _deduce_model_from_flags(
    flags: dict,
    duration_s: int,
    refs_count: int,
) -> str:
    """H3 — Backend Python deduce model thay vì để LLM tự apply rules trong
    prompt (đáng tin hơn, deterministic, dễ test).

    Decision tree (ưu tiên cao → thấp):
      1. needs_dialogue_lip_sync + duration ∈ {5,10} → wan_2_7 (lip-sync VN)
      2. is_multi_shot_cinematic + duration ≤15s:
         • is_budget_tier → seedance_2_0_fast (cost-optimized)
         • ngược lại → seedance_2_0 (highest quality)
      3. duration ≤12s + ≤1 ref → seedance_1_5_pro (i2v specialist)
      4. is_budget_tier → vidu_q3 (rẻ nhất)
      5. Fallback → auto (worker pick at render time)
    """
    needs_lip = bool(flags.get("needs_dialogue_lip_sync"))
    is_multi_cinematic = bool(flags.get("is_multi_shot_cinematic"))
    is_budget = bool(flags.get("is_budget_tier"))

    # Rule 1: Wan 2.7 needs discrete [5,10]s for lip-sync
    if needs_lip and duration_s in (5, 10):
        return "wan_2_7"

    # Rule 2: Multi-shot cinematic short video → Seedance 2.0 family
    if is_multi_cinematic and duration_s <= 15:
        return "seedance_2_0_fast" if is_budget else "seedance_2_0"

    # Rule 3: Single shot short with 1 ref → Seedance 1.5 Pro
    if duration_s <= 12 and not is_multi_cinematic and refs_count <= 1:
        return "seedance_1_5_pro"

    # Rule 4: Budget UGC fallback
    if is_budget:
        return "vidu_q3"

    # Rule 5: Auto worker-side
    return "auto"


def _build_enhance_system_prompt(mode: str, duration_s: int) -> str:
    """V5.17.5 — Dynamic system prompt builder.
    H2: sentence_range theo duration.
    H3: bỏ "Quy tắc model picking" trong prompt, replace với 3 flag.
    """
    sentence_range = _sentence_range_for_duration(duration_s)

    json_schema = (
        f"OUTPUT DUY NHẤT MỘT JSON OBJECT (không markdown fence, không text trước/sau). "
        f"Schema CHÍNH XÁC:\n"
        "{\n"
        f'  "enhanced_brief": "<{sentence_range} văn xuôi tiếng Việt giàu chi tiết visual + camera + lighting + mood>",\n'
        '  "vision_notes": {\n'
        '    "character": "<face / hair / outfit / expression CHÍNH XÁC từ ảnh; null nếu không ảnh người>",\n'
        '    "product": "<color / packaging / logo từ ảnh sản phẩm; null nếu không có>",\n'
        '    "style_ref": "<mood / color_grade từ ảnh phong cách; null nếu không có>"\n'
        '  },\n'
        '  "suggested_niche": "<vd: beauty | food | tech | lifestyle | fashion | drama | ugc_review | automotive | real_estate | fitness | ...>",\n'
        '  "suggested_mood": "<vd: \'intimate warm afternoon\' | \'dramatic dark cinematic\' | \'energetic playful\'>",\n'
        '  "suggested_hook_pattern": "<EXACTLY 1 of: pattern_interrupt | direct_question | bold_statement | visual_paradox | action_reveal | before_after | time_compression | sensory_overload | expectation_subvert | character_intro>",\n'
        '  "suggested_num_shots": <integer 1-6, dựa duration + brief complexity>,\n'
        '  "suggested_audio_mode": "<EXACTLY 1 of: silent_native | dialogue_vo | asmr_macro>",\n'
        '  "needs_dialogue_lip_sync": <bool — true nếu brief có lời thoại tiếng Việt nhân vật nói khớp môi>,\n'
        '  "is_multi_shot_cinematic": <bool — true nếu brief đòi hỏi 2+ cảnh chuyển có camera movement cinematic>,\n'
        '  "is_budget_tier": <bool — true nếu user mention budget/cheap/test/draft hoặc brief đơn giản UGC>\n'
        "}\n"
        "Lưu ý: 3 flag bool dùng cho backend tự deduce model — đừng tự pick model trong response."
    )

    if mode == "vision":
        body = (
            "Bạn là Director AI chuyên viết brief video tiếng Việt cho Director Agent. "
            "Người dùng cung cấp brief ngắn + 1-6 ảnh tham khảo (nhân vật, sản phẩm, mood).\n\n"
            "★ QUY TẮC TỐI THƯỢNG: enhanced_brief PHẢI BÁM CHẶT brief gốc của user. "
            "Mọi danh từ chính (sản phẩm, nhân vật, hành động, niche) user đã nêu — "
            "BẮT BUỘC xuất hiện và là TRỌNG TÂM của enhanced_brief. Vai trò của bạn "
            "là MỞ RỘNG brief gốc + KẾT HỢP chi tiết từ ảnh, KHÔNG VIẾT THÀNH BRIEF "
            "KHÁC.\n\n"
            f"Độ dài enhanced_brief mục tiêu: {sentence_range}.\n\n"
            "Nhiệm vụ:\n"
            "1. NHÌN KỸ từng ảnh — extract CHÍNH XÁC: màu trang phục, kiểu tóc, khuôn mặt, "
            "   biểu cảm; với sản phẩm: màu sắc, packaging, logo cụ thể.\n"
            "2. Viết enhanced_brief BÁM brief gốc + lồng ghép chi tiết visual từ ảnh + "
            "   thêm bối cảnh setting + ánh sáng + camera shot + mood audio.\n"
            "3. Điền vision_notes với chi tiết extract được từ ảnh (Director sẽ reuse).\n"
            "4. Set 3 flag bool chính xác để backend deduce model.\n"
            "5. KHÔNG bịa features sản phẩm KHÔNG thấy trong ảnh hoặc KHÔNG có trong "
            "   brief. KHÔNG CTA. KHÔNG emoji. KHÔNG bullet list.\n\n"
        )
    else:  # text mode
        body = (
            "Bạn là Director AI chuyên viết brief video tiếng Việt cho Director Agent.\n\n"
            "★ QUY TẮC TỐI THƯỢNG: enhanced_brief PHẢI BÁM CHẶT brief gốc của user. "
            "Mọi danh từ chính (sản phẩm, nhân vật, hành động, niche) user đã nêu — "
            "BẮT BUỘC xuất hiện và là TRỌNG TÂM của enhanced_brief. KHÔNG thay thế "
            "bằng nội dung khác. Vai trò của bạn là MỞ RỘNG brief gốc, KHÔNG VIẾT LẠI "
            "THÀNH BRIEF KHÁC.\n\n"
            f"Độ dài enhanced_brief mục tiêu: {sentence_range}.\n\n"
            "Cách mở rộng brief gốc (giữ nguyên ý) bằng cách BỔ SUNG:\n"
            "(a) bối cảnh setting cụ thể (vd: 'trong phòng ngủ ánh sáng dịu vàng buổi chiều')\n"
            "(b) ánh sáng + color grade (warm/cool/neutral, soft/hard light)\n"
            "(c) camera shot + movement (close-up push-in, medium handheld, etc.)\n"
            "(d) mood/tone audio (intimate quiet, energetic upbeat, dramatic tension).\n\n"
            "Set 3 flag bool chính xác để backend deduce model.\n"
            "KHÔNG bịa product features không có trong brief gốc. KHÔNG CTA / sale "
            "imperatives. KHÔNG emoji. KHÔNG bullet list. Vì không có ảnh ref, set "
            "vision_notes các field về null.\n\n"
        )

    return body + json_schema


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
    # V5.17.2 — User brief đặt TOP và REPEAT cuối để LLM bám chặt. Trước đó
    # brief bị "chìm" giữa system prompt JSON schema dài + user msg ngắn →
    # LLM tập trung điền JSON template thay vì mở rộng brief gốc.
    user_msg = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"★ BRIEF GỐC CỦA USER (BÁM CHẶT — đây là trọng tâm video {req.duration_s}s):\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{req.brief}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Nhiệm vụ: viết enhanced_brief BÁM CHẶT brief gốc trên, MỞ RỘNG thành "
        f"4-7 câu giàu chi tiết (bối cảnh + ánh sáng + camera + mood). Mọi "
        f"danh từ chính trong brief gốc PHẢI xuất hiện trong enhanced_brief."
    )
    if req.niche_hint:
        user_msg += f"\n\nNiche hint (gợi ý phụ): {req.niche_hint}"

    refs = [u for u in (req.reference_image_urls or []) if u and u.startswith("http")][:6]
    duration_s = int(req.duration_s or 15)
    try:
        if refs:
            user_msg += (
                f"\n\n★ User đã upload {len(refs)} ảnh tham khảo. NHÌN KỸ ảnh + "
                f"LỒNG GHÉP chi tiết visual (màu, trang phục, sản phẩm) vào "
                f"enhanced_brief — nhưng VẪN BÁM brief gốc làm trọng tâm. "
                f"KHÔNG VIẾT brief khác."
            )
            # V5.17.5 H1+H2 — dynamic prompt + max_tokens theo duration
            raw = llm.complete_with_image(
                system_prompt=_build_enhance_system_prompt("vision", duration_s),
                user_message=user_msg,
                image_urls=refs,
                task="vision",
                max_tokens=_max_tokens_for_duration(duration_s, "vision"),
            )
            mode = "vision"
        else:
            raw = llm.complete(
                system_prompt=_build_enhance_system_prompt("text", duration_s),
                user_message=user_msg,
                task="generator",
                max_tokens=_max_tokens_for_duration(duration_s, "text"),
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

    # V5.17.5 H3 — Backend deduce suggested_model từ 3 bool flags LLM trả về.
    # Trước đây LLM tự apply model-picking rules trong prompt (text rules) →
    # không deterministic. Giờ flags → Python deterministic mapping.
    flags = {
        "needs_dialogue_lip_sync": bool(parsed.get("needs_dialogue_lip_sync")),
        "is_multi_shot_cinematic": bool(parsed.get("is_multi_shot_cinematic")),
        "is_budget_tier": bool(parsed.get("is_budget_tier")),
    }
    deduced_model = _deduce_model_from_flags(flags, duration_s, len(refs))
    # Honor LLM's explicit suggested_model nếu hợp lệ (backward compat), else
    # dùng deduced. Đa số case LLM sẽ KHÔNG còn return suggested_model (new
    # prompt yêu cầu không pick) → deduced_model thắng.
    llm_picked = _safe_pick(parsed.get("suggested_model"), _ALLOWED_MODELS)
    final_model = llm_picked or deduced_model

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
        # V5.17.5 — model now deduced from flags (deterministic) instead of
        # LLM-picked. flags surfaced in response for debugging/transparency.
        "suggested_model": final_model,
        "suggested_audio_mode": _safe_pick(parsed.get("suggested_audio_mode"), _ALLOWED_AUDIO),
        "model_deduction_flags": flags,
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
