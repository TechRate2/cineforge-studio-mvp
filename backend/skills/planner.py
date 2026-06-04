"""AutoPlanner — Skill 1/5: niche analysis + viral hook 3-second + mood/style direction.

Input: ý tưởng ngắn của user (1-3 câu) + optional reference assets.
Output: niche category + viral hook + mood + suggested duration + aspect ratio.

Skill này là entrypoint của Autonomous Director chain — output của nó feed
xuống Storyboard skill + Director skill để build full plan.

═══════════════════════════════════════════════════════════════════════════
DESIGN NOTES (Vi/En):
  - Viral hook 3s ĐẦU TIÊN là điểm scroll-stop quan trọng nhất trên TikTok/Reels
    → planner gen explicit hook_pattern + first 3-second action description.
  - Niche detection (beauty/food/tech/lifestyle/drama/...) ảnh hưởng tone của
    Storyboard và Editor (caption + hashtag) downstream.
  - Mood + style_direction là free-form string mà Director Agent V3 đã hiểu —
    chỉ cần feed vào ContinuityBible.visual_style.
═══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from vendors.llm_router import llm
from skills.niche_playbooks import list_niche_keys


# ============================================================
# Pydantic schemas — I/O contract
# ============================================================

class PlannerInput(BaseModel):
    """User idea + optional context for the planner."""

    user_idea: str = Field(..., min_length=5, description="1-3 câu tóm tắt ý tưởng video")
    reference_image_urls: list[str] = Field(default_factory=list)
    reference_video_urls: list[str] = Field(default_factory=list, max_length=3)
    reference_audio_urls: list[str] = Field(default_factory=list, max_length=3)
    target_platform: str = Field(
        "tiktok",
        description="tiktok | reels | youtube_short | youtube_long | facebook | universal",
    )
    target_market: str = Field(
        "auto",
        description="auto | vn | us | sea | jp | kr | global. Guides localization, culture, dialogue, claims, captions.",
    )
    market_playbook: dict = Field(default_factory=dict)
    duration_hint_s: Optional[int] = Field(
        None, ge=4, le=1800,
        description="Optional user hint — None thì planner tự quyết theo niche + platform",
    )


class PlannerOutput(BaseModel):
    """Niche + viral hook + mood + suggested settings."""

    niche: str = Field(..., description="One supported niche key from niche_playbooks.py")
    primary_emotion: str = Field(..., description="vd: curiosity / desire / surprise / nostalgia")

    # Hook 3-second — điểm scroll-stop
    hook_pattern: str = Field(
        ...,
        description=(
            "EXACTLY 1 of: pattern_interrupt | direct_question | bold_statement | "
            "visual_paradox | action_reveal | before_after | time_compression | "
            "sensory_overload | expectation_subvert | character_intro"
        ),
    )
    hook_first_3s: str = Field(
        ...,
        description="Mô tả CỤ THỂ 3 giây đầu (visual + action) — phải scroll-stop",
    )

    # Mood / Style — feed vào ContinuityBible
    mood: str = Field(..., description="vd: 'intimate warm afternoon' | 'energetic playful'")
    style_direction: str = Field(
        ...,
        description="cinematography + color_grading + lighting trong 1-2 câu",
    )

    # Settings hints — Director skill final decide
    suggested_duration_s: int = Field(..., ge=4, le=1800)
    suggested_aspect_ratio: str = Field(..., description="9:16 | 16:9 | 1:1")
    suggested_audio_mode: str = Field(
        ..., description="silent_native | dialogue_vo | asmr_macro"
    )

    # Free-form Director hint
    director_notes: str = Field(
        "", description="Free-form gợi ý cho Director skill (ex: 'open with extreme close-up')"
    )


# ============================================================
# System prompt
# ============================================================

_SUPPORTED_NICHES = ", ".join(list_niche_keys())


_PLANNER_SYSTEM_PROMPT = """Bạn là Senior Creative Director cho viral short video AI generation.

NHIỆM VỤ: Từ ý tưởng ngắn của user → output 1 JSON object với niche/hook/mood/style.

QUY TẮC SẮT:
1. HOOK 3-SECOND: scroll-stop là KEY. Mô tả EXACT visual + action 3 giây đầu, không vague.
   - Bad:  "show character speaking"
   - Good: "extreme close-up of trembling hand opening package, golden light spill, no face yet"
2. NICHE: pick chính xác 1 supported niche key:
   {{SUPPORTED_NICHES}}
   Nếu brief mơ hồ, chọn ugc_review cho product/creator proof hoặc lifestyle cho daily/emotional content.
3. MOOD: 1 cụm 2-4 từ giàu hình ảnh.
4. STYLE: cinematography + color_grading + lighting trong 1-2 câu.
5. DURATION:
   - tiktok / reels / youtube_short → 15-30s sweet spot
   - youtube_long → 60-180s
   - universal → 15s default
   Nếu user có duration_hint_s → tôn trọng, chỉ khuyên khác khi quá lệch niche.
6. ASPECT: tiktok/reels/short → 9:16. youtube_long/facebook → 16:9.
7. TARGET MARKET:
   - auto: infer from user language, product context, references, and platform.
   - vn: Vietnamese culture, natural Vietnamese dialogue/caption, local social proof, avoid US-only idioms.
   - us/global: direct English hook, faster claim clarity, broad platform-native phrasing.
   - jp/kr/sea: localize manners, pacing, beauty/food/lifestyle cues, and safe cultural references.
   Put market-specific guidance in director_notes. Do not stereotype; make the story feel local and real.

OUTPUT: DUY NHẤT 1 JSON object, không markdown fence, không text trước/sau.

JSON SCHEMA (mọi field BẮT BUỘC):
{
  "niche": "<string>",
  "primary_emotion": "<string>",
  "hook_pattern": "<EXACTLY 1 of 10 patterns>",
  "hook_first_3s": "<concrete visual + action description>",
  "mood": "<2-4 word phrase>",
  "style_direction": "<1-2 sentence cinematography + color + lighting>",
  "suggested_duration_s": <int 4-1800>,
  "suggested_aspect_ratio": "<9:16|16:9|1:1>",
  "suggested_audio_mode": "<silent_native|dialogue_vo|asmr_macro>",
  "director_notes": "<free-form, 0-2 sentences>"
}
""".replace("{{SUPPORTED_NICHES}}", _SUPPORTED_NICHES)


# ============================================================
# Skill class
# ============================================================

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _safe_parse_json(raw: str) -> dict:
    cleaned = _FENCE_RE.sub("", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        s, e = cleaned.find("{"), cleaned.rfind("}")
        if s >= 0 and e > s:
            return json.loads(cleaned[s:e + 1])
        raise


class AutoPlanner:
    """Skill 1/5 — Auto Planner.

    Usage:
        planner = AutoPlanner()
        result = await planner.run(PlannerInput(user_idea="...", target_platform="tiktok"))
    """

    name = "planner"
    description = "Niche analysis + viral hook 3-second + mood/style direction"

    async def run(self, inp: PlannerInput, *, max_attempts: int = 2) -> PlannerOutput:
        """Build planner output via 1 LLM call. Retry once on parse/validation fail."""
        user_msg = json.dumps({
            "user_idea": inp.user_idea,
            "target_platform": inp.target_platform,
            "target_market": inp.target_market,
            "market_playbook": inp.market_playbook,
            "duration_hint_s": inp.duration_hint_s,
            "n_reference_images": len(inp.reference_image_urls),
            "n_reference_videos": len(inp.reference_video_urls),
            "n_reference_audios": len(inp.reference_audio_urls),
        }, ensure_ascii=False)

        last_err: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            try:
                # llm.complete is sync → wrap with to_thread for async fit
                raw = await asyncio.to_thread(
                    llm.complete,
                    system_prompt=_PLANNER_SYSTEM_PROMPT,
                    user_message=user_msg,
                    task="generator",
                    max_tokens=800,
                    temperature=0.7 if attempt == 1 else 0.4,
                )
                data = _safe_parse_json(raw)
                out = PlannerOutput(**data)
                logger.info(
                    f"[AutoPlanner] niche={out.niche} hook={out.hook_pattern} "
                    f"dur={out.suggested_duration_s}s ar={out.suggested_aspect_ratio}"
                )
                return out
            except (json.JSONDecodeError, ValidationError, ValueError) as e:
                last_err = e
                logger.warning(
                    f"[AutoPlanner] parse fail attempt {attempt}/{max_attempts}: "
                    f"{type(e).__name__}: {str(e)[:120]}"
                )

        # All attempts failed — raise with context
        assert last_err is not None
        raise RuntimeError(
            f"AutoPlanner LLM build failed after {max_attempts} attempts: {last_err}"
        )


__all__ = ["AutoPlanner", "PlannerInput", "PlannerOutput"]
