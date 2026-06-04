"""AutoStoryboard — Skill 2/5: tạo 6-9 panel (short) hoặc multi-chunk (long-form).

Input: PlannerOutput + reference URLs + target duration.
Output: list StoryboardPanel — mỗi panel mô tả 1 beat (visual + action + duration).

Storyboard này là CONTRACT giữa Planner (creative) và Director (technical):
  - Planner quyết "nói gì"
  - Storyboard quyết "thấy gì trong từng beat"
  - Director quyết "render thế nào" (camera move, model, refs)

═══════════════════════════════════════════════════════════════════════════
LONG-FORM DESIGN (>15s):
  Seedance 2.0 current generation window is 4-15s. Stories longer than one
  generation must be split into renderable shots and scene/chunk groups.

  Panel count guidance:
    ≤15s short → 3-4 panels
    16-30s    → 4-6 panels, rendered as multiple shots
    31-60s    → 6-9 panels, rendered as multiple shots
    >60s      → N scene/chunk groups × (6-9 panels each), chain via last_frame

  Storyboard skill chỉ output panels — Director skill quyết chunk split.
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
from skills.planner import PlannerOutput


# ============================================================
# Pydantic schemas
# ============================================================

class StoryboardPanel(BaseModel):
    """1 panel của storyboard — 1 visual beat trong timeline."""

    index: int = Field(..., ge=0, description="0-based position")
    duration_s: float = Field(..., gt=0, le=15, description="4-15s typical, max 15 per single shot")
    purpose: str = Field(
        ...,
        description="hook | setup | tension | reveal | proof | cta | transition",
    )
    visual_description: str = Field(
        ...,
        description="WHAT viewer sees — subject + action + composition, 1-3 sentences",
    )
    suggested_camera: str = Field(
        ..., description="vd: ECU push-in / MS handheld / WS static / drone pull-out",
    )
    suggested_lighting: str = Field(
        "", description="optional override per panel — empty = inherit from style_direction",
    )
    emotion_beat: str = Field(
        ..., description="Emotion viewer should feel at this beat",
    )
    # Long-form support
    chunk_id: int = Field(
        0, ge=0, description="Scene/chunk index for longer videos (0 = first group)",
    )


class StoryboardInput(BaseModel):
    """Inputs needed to build storyboard from planner output."""

    planner: PlannerOutput
    user_idea: str  # original idea for context
    target_duration_s: int = Field(..., ge=4, le=180)
    reference_image_urls: list[str] = Field(default_factory=list)
    niche_playbook: dict = Field(default_factory=dict)


class StoryboardOutput(BaseModel):
    """Full storyboard — panel list + meta."""

    panels: list[StoryboardPanel]
    total_duration_s: float
    n_chunks: int = Field(1, ge=1, description="1 for a short/sequence group, N for long-form")
    chunk_duration_s: list[float] = Field(default_factory=list)


# ============================================================
# System prompt
# ============================================================

_STORYBOARD_SYSTEM_PROMPT = """Bạn là Senior Storyboard Artist cho viral short video.

NHIỆM VỤ: Từ planner output → output JSON với list panels, mỗi panel = 1 visual beat.

QUY TẮC PANEL COUNT theo duration:
  - ≤15s   → 3-4 panels
  - 16-30s → 4-6 panels
  - 31-60s → 6-9 panels, rendered as multiple 4-15s shots
  - >60s   → output 6-9 panels PER SCENE/CHUNK GROUP, set chunk_id 0,1,2,...
            Tổng panels = N_chunks × (6-9).

QUY TẮC PANEL CONTENT:
1. PANEL[0] LUÔN là HOOK 3-second — visual_description PHẢI match planner.hook_first_3s.
2. Duration mỗi panel 4-15s. Hook panel có thể 3-5s (đủ scroll-stop).
3. Camera mỗi panel KHÁC NHAU — tránh same-size + same-mode consecutive (jump cut).
4. Purpose flow theo niche:
   - drama/ugc_review: hook → setup → tension → reveal → cta
   - product: hook → problem → solution → proof → cta
   - lifestyle: hook → moment_1 → moment_2 → moment_3 → close
5. Tổng duration_s phải GẦN target_duration_s (±2s tolerance).
6. visual_description 1-3 câu CỤ THỂ (KHÔNG generic "person doing thing").

OUTPUT: DUY NHẤT 1 JSON object, schema chính xác:
{
  "panels": [
    {
      "index": 0,
      "duration_s": 3.0,
      "purpose": "hook",
      "visual_description": "<concrete visual + action>",
      "suggested_camera": "<shot + movement>",
      "suggested_lighting": "<optional or empty>",
      "emotion_beat": "<feeling>",
      "chunk_id": 0
    },
    ...
  ],
  "total_duration_s": <sum of panels>,
  "n_chunks": <int 1 for short/sequence, N for long-form>,
  "chunk_duration_s": [<duration of each chunk>]
}
"""


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


class AutoStoryboard:
    """Skill 2/5 — Auto Storyboard.

    Usage:
        sb = AutoStoryboard()
        out = await sb.run(StoryboardInput(planner=..., target_duration_s=15))
    """

    name = "storyboard"
    description = "6-9 panel layout (short) hoặc multi-chunk (long-form)"

    async def run(self, inp: StoryboardInput, *, max_attempts: int = 2) -> StoryboardOutput:
        """Build storyboard. Retry on parse fail. Auto-normalize duration drift."""
        user_msg = json.dumps({
            "user_idea": inp.user_idea,
            "target_duration_s": inp.target_duration_s,
            "n_reference_images": len(inp.reference_image_urls),
            "planner": inp.planner.model_dump(),
            "niche_playbook": inp.niche_playbook,
        }, ensure_ascii=False)

        last_err: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            try:
                raw = await asyncio.to_thread(
                    llm.complete,
                    system_prompt=_STORYBOARD_SYSTEM_PROMPT,
                    user_message=user_msg,
                    task="generator",
                    max_tokens=2500,
                    temperature=0.7 if attempt == 1 else 0.4,
                )
                data = _safe_parse_json(raw)
                out = StoryboardOutput(**data)

                # Post-validate: ensure total_duration matches sum
                computed = sum(p.duration_s for p in out.panels)
                if abs(computed - out.total_duration_s) > 0.5:
                    logger.warning(
                        f"[AutoStoryboard] total_duration drift {out.total_duration_s} → "
                        f"computed {computed} — using computed"
                    )
                    out.total_duration_s = computed

                # Ensure n_chunks consistent with chunk_duration_s
                if out.n_chunks > 1 and len(out.chunk_duration_s) != out.n_chunks:
                    logger.warning(
                        f"[AutoStoryboard] n_chunks={out.n_chunks} but chunk_duration_s "
                        f"has {len(out.chunk_duration_s)} entries — auto-rebuild"
                    )
                    # Group panels by chunk_id to rebuild
                    by_chunk: dict[int, float] = {}
                    for p in out.panels:
                        by_chunk[p.chunk_id] = by_chunk.get(p.chunk_id, 0.0) + p.duration_s
                    out.chunk_duration_s = [by_chunk[i] for i in sorted(by_chunk.keys())]
                    out.n_chunks = len(out.chunk_duration_s)

                logger.info(
                    f"[AutoStoryboard] panels={len(out.panels)} dur={out.total_duration_s}s "
                    f"chunks={out.n_chunks}"
                )
                return out
            except (json.JSONDecodeError, ValidationError, ValueError) as e:
                last_err = e
                logger.warning(
                    f"[AutoStoryboard] parse fail attempt {attempt}/{max_attempts}: "
                    f"{type(e).__name__}: {str(e)[:120]}"
                )

        assert last_err is not None
        raise RuntimeError(
            f"AutoStoryboard LLM build failed after {max_attempts} attempts: {last_err}"
        )


__all__ = ["AutoStoryboard", "StoryboardInput", "StoryboardOutput", "StoryboardPanel"]
