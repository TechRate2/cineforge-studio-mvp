"""AutoEditor — Skill 5/5: transition cues + caption + viral hashtag.

V6.1 Medium scope (per user Q3=b):
  - Generate caption VN + EN (1 LLM call, returns both)
  - Generate hashtag set (niche-aware, 5-10 tags VN + 5-10 EN)
  - Generate transition cues cho per_shot_chain mode (FFmpeg can apply
    crossfade / dip-to-black between clips)
  - NOT generate: text overlay burned-in (would need video filter pass —
    FE can handle as CapCut-style overlay)

═══════════════════════════════════════════════════════════════════════════
INTEGRATION:
  - Output `transition_plan` → workers/assemble_worker.py reads to apply
    FFmpeg filter_complex (xfade / fade / cut).
  - Output `caption_vn` / `caption_en` / `hashtags_vn` / `hashtags_en` →
    FE shows trong post-render screen, user copy-paste khi đăng TikTok/Reels.
═══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Literal, Optional

from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from vendors.llm_router import llm
from agent.distribution_package import build_distribution_package
from skills.planner import PlannerOutput
from skills.storyboard import StoryboardOutput


# ============================================================
# Pydantic schemas
# ============================================================

TransitionType = Literal["cut", "crossfade", "fade_black", "dip_white", "whip_pan"]


class TransitionCue(BaseModel):
    """1 transition between shot i and shot i+1."""

    from_shot_index: int = Field(..., ge=0)
    to_shot_index: int = Field(..., ge=1)
    transition_type: TransitionType
    duration_ms: int = Field(300, ge=0, le=1500)
    reasoning: str = ""


class EditorInput(BaseModel):
    planner: PlannerOutput
    storyboard: StoryboardOutput
    user_idea: str
    target_platform: str = Field("tiktok")
    target_market: str = Field("auto")
    market_playbook: dict = Field(default_factory=dict)
    niche_playbook: dict = Field(default_factory=dict)
    n_shots_rendered: int = Field(1, ge=1, description="Số clip thực tế đã render")


class EditorOutput(BaseModel):
    """Caption + hashtag + transition cues."""

    # Caption — 1-3 sentences, hook đầu, CTA cuối
    caption_vn: str
    caption_en: str

    # Hashtags — list of strings WITHOUT # prefix
    hashtags_vn: list[str] = Field(default_factory=list, max_length=15)
    hashtags_en: list[str] = Field(default_factory=list, max_length=15)

    # Transitions — only used when render_strategy is per_shot_chain
    # (single_call_multi_shot doesn't need transitions, Seedance handles cuts)
    transitions: list[TransitionCue] = Field(default_factory=list)

    # Posting hint
    best_posting_time_vn: str = Field(
        "",
        description="vd: 'TikTok VN sweet spot 19:00-22:00, weekday'",
    )
    distribution_package: dict = Field(default_factory=dict)


# ============================================================
# System prompts
# ============================================================

_EDITOR_SYSTEM_PROMPT = """Bạn là Senior Social Media Editor cho viral international content.

NHIỆM VỤ: Từ planner + storyboard + user_idea → output JSON với caption + hashtag +
posting hint.

QUY TẮC CAPTION:
1. caption_vn:
   - 1-3 câu, MAX ~150 ký tự.
   - Câu đầu = HOOK (curiosity gap / direct address / shock).
   - Câu cuối = MILD CTA (không bán hàng aggressive).
   - Có 0-2 emoji phù hợp niche (KHÔNG spam).
   - Nếu target_market=vn hoặc auto+brief tiếng Việt: viết tiếng Việt tự nhiên.
   - Nếu target_market không phải VN: vẫn trả field này, nhưng có thể là localized primary caption.
2. caption_en: English version for international reach, giữ hook structure.

QUY TẮC HASHTAG:
1. hashtags_vn: 5-10 tag, MIX:
   - 2-3 broad niche tag (vd: #beautyvn, #lamdep, #unbox)
   - 3-5 specific tag (vd: #thuonghieuabc, #reviewmoinhat)
   - 1-2 trending VN (vd: #fyp, #xuhuong)
   KHÔNG có "#" prefix trong list — chỉ tên tag.
2. hashtags_en: 5-10 tag tương ứng cho international reach.

POSTING TIME:
- TikTok VN: 19:00-22:00 weekday, 12:00-14:00 weekend
- Reels: 18:00-21:00
- YouTube Short: 14:00-17:00
- target_market guides slang, claim style, cultural context, and posting hint.

OUTPUT: DUY NHẤT 1 JSON object, schema:
{
  "caption_vn": "<text>",
  "caption_en": "<text>",
  "hashtags_vn": ["tag1", "tag2", ...],
  "hashtags_en": ["tag1", "tag2", ...],
  "best_posting_time_vn": "<text>"
}
"""


# ============================================================
# Helper — pure-function transition planner
# ============================================================

def _plan_transitions(storyboard: StoryboardOutput, n_clips: int) -> list[TransitionCue]:
    """Pick transition type giữa mỗi cặp shot.

    Heuristic (no LLM — deterministic):
      - chunk_id boundary           → fade_black 500ms (clear scene change signal)
      - purpose: hook→setup         → cut (sharp scroll-stop continues)
      - purpose: reveal→cta         → dip_white 400ms (emphasis on product)
      - same camera_movement type   → crossfade 300ms (smooth)
      - different shot size big jump → cut (intentional editorial)
      - default                     → cut
    """
    cues: list[TransitionCue] = []
    panels = storyboard.panels

    # n_clips = số clip đã render (per_shot_chain) → n-1 transitions
    n_transitions = max(0, n_clips - 1)
    for i in range(n_transitions):
        if i + 1 >= len(panels):
            break
        cur_p = panels[i]
        next_p = panels[i + 1]

        t_type: TransitionType = "cut"
        duration_ms = 0
        reasoning = "default cut"

        if cur_p.chunk_id != next_p.chunk_id:
            t_type = "fade_black"
            duration_ms = 500
            reasoning = "chunk boundary"
        elif cur_p.purpose == "reveal" and next_p.purpose == "cta":
            t_type = "dip_white"
            duration_ms = 400
            reasoning = "reveal→cta emphasis"
        elif "static" in cur_p.suggested_camera.lower() and "static" in next_p.suggested_camera.lower():
            t_type = "crossfade"
            duration_ms = 300
            reasoning = "both static → smooth crossfade"

        cues.append(TransitionCue(
            from_shot_index=i,
            to_shot_index=i + 1,
            transition_type=t_type,
            duration_ms=duration_ms,
            reasoning=reasoning,
        ))

    return cues


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


class AutoEditor:
    """Skill 5/5 — Auto Editor (caption + hashtag + transitions)."""

    name = "editor"
    description = "Transition cues + viral caption + hashtag VN/EN"

    async def run(self, inp: EditorInput, *, max_attempts: int = 2) -> EditorOutput:
        """1 LLM call cho caption+hashtag, deterministic transitions."""

        # ---- LLM call for caption + hashtag ----
        user_msg = json.dumps({
            "user_idea": inp.user_idea,
            "target_platform": inp.target_platform,
            "target_market": inp.target_market,
            "market_playbook": inp.market_playbook,
            "planner": inp.planner.model_dump(),
            "niche_playbook": inp.niche_playbook,
            "storyboard_summary": {
                "n_panels": len(inp.storyboard.panels),
                "total_duration_s": inp.storyboard.total_duration_s,
                "hooks": [p.visual_description for p in inp.storyboard.panels if p.purpose == "hook"],
            },
        }, ensure_ascii=False)

        caption_data: dict = {}
        last_err: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            try:
                raw = await asyncio.to_thread(
                    llm.complete,
                    system_prompt=_EDITOR_SYSTEM_PROMPT,
                    user_message=user_msg,
                    task="generator",
                    max_tokens=800,
                    temperature=0.8 if attempt == 1 else 0.5,
                )
                caption_data = _safe_parse_json(raw)
                # quick sanity check before pydantic
                if not caption_data.get("caption_vn"):
                    raise ValueError("missing caption_vn")
                break
            except (json.JSONDecodeError, ValidationError, ValueError) as e:
                last_err = e
                logger.warning(
                    f"[AutoEditor] caption LLM attempt {attempt}/{max_attempts} fail: "
                    f"{type(e).__name__}: {str(e)[:120]}"
                )

        if not caption_data:
            # Last-resort fallback so render doesn't fail on editor stage
            logger.error(f"[AutoEditor] all caption attempts failed: {last_err}")
            caption_data = {
                "caption_vn": inp.user_idea[:150],
                "caption_en": inp.user_idea[:150],
                "hashtags_vn": ["fyp", "xuhuong"],
                "hashtags_en": ["fyp", "viral"],
                "best_posting_time_vn": "TikTok VN 19:00-22:00 weekday",
            }

        # ---- Transitions (deterministic) ----
        transitions = _plan_transitions(inp.storyboard, inp.n_shots_rendered)

        distribution_package = build_distribution_package(
            target_platform=inp.target_platform,
            target_market=inp.target_market,
            niche=inp.planner.niche,
            duration_s=inp.storyboard.total_duration_s,
            caption_vn=caption_data.get("caption_vn", ""),
            caption_en=caption_data.get("caption_en", ""),
            hashtags_vn=caption_data.get("hashtags_vn", []) or [],
            hashtags_en=caption_data.get("hashtags_en", []) or [],
            market_playbook=inp.market_playbook,
        )

        out = EditorOutput(
            caption_vn=caption_data.get("caption_vn", ""),
            caption_en=caption_data.get("caption_en", ""),
            hashtags_vn=caption_data.get("hashtags_vn", []) or [],
            hashtags_en=caption_data.get("hashtags_en", []) or [],
            transitions=transitions,
            best_posting_time_vn=caption_data.get("best_posting_time_vn", ""),
            distribution_package=distribution_package,
        )
        logger.info(
            f"[AutoEditor] caption_vn_len={len(out.caption_vn)} "
            f"tags_vn={len(out.hashtags_vn)} transitions={len(out.transitions)}"
        )
        return out


__all__ = [
    "AutoEditor", "EditorInput", "EditorOutput",
    "TransitionCue", "TransitionType",
]
