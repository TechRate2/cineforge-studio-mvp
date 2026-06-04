"""AutoDirector — Skill 3/5: quyết shot count + duration mỗi shot + camera moves
+ long-form chain decision.

Input: PlannerOutput + StoryboardOutput + ref counts + target model.
Output: DirectorOutput chứa shot specs (compatible với Shot pydantic của repo
+ render_strategy) và chunk_plan cho long-form.

Skill này KHÔNG gọi LLM — pure deterministic logic dựa trên storyboard panels.
Lý do: storyboard đã có panel list từ LLM, chỉ cần map sang shot specs đúng
model constraint (Seedance 2.0 max 15s/shot, multi-shot inline ≤6 shots/call,
Wan 2.7 discrete [5,10]s).

═══════════════════════════════════════════════════════════════════════════
DECISION TREE:
  1. Map mỗi panel → 1 shot (1:1) — đơn giản & predictable
  2. Pick render_strategy:
     - Seedance 2.0 + total ≤15s + shots ≤6        → single_call_multi_shot
     - >15s OR >6 shots                            → per_shot_chain (last_frame chain)
     - Wan 2.7                                     → per_shot_chain (i2v only)
  3. Long-form: render as 4-15s shots/scene chunks and chain via last_frame.
═══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

from typing import Literal

from loguru import logger
from pydantic import BaseModel, Field

from skills.planner import PlannerOutput
from skills.storyboard import StoryboardOutput, StoryboardPanel


# ============================================================
# Pydantic schemas
# ============================================================

RenderStrategy = Literal["single_call_multi_shot", "per_shot_chain"]


class DirectorShotSpec(BaseModel):
    """1 shot spec — compatible với agent/schemas.py:Shot.

    KHÔNG dùng trực tiếp pydantic Shot vì Shot có required fields cụ thể
    (shot_id, start_s, end_s, visual, audio, continuity) — DirectorOutput
    chỉ chứa tối thiểu cần thiết để adapter (`from_skill_output()`) convert
    sang Shot full.
    """

    shot_id: str
    index: int
    duration_s: int = Field(..., ge=1, le=15)
    purpose: str
    subject: str
    action: str
    camera_shot: str = Field(..., description="ECU / CU / MS / WS / drone / POV")
    camera_movement: str = "static"
    lighting_override: str = ""
    emotion_beat: str = ""
    # Long-form support
    chunk_id: int = 0
    # Chain hint — set by Director when prev shot in same chunk
    previous_shot_id: str | None = None


class DirectorInput(BaseModel):
    planner: PlannerOutput
    storyboard: StoryboardOutput
    user_model: str = Field("seedance_2_0", description="seedance_2_0 / seedance_2_0_fast / wan_2_7 / auto")


class DirectorOutput(BaseModel):
    """Final shot list + render strategy + chunk plan."""

    shots: list[DirectorShotSpec]
    total_duration_s: int
    render_strategy: RenderStrategy
    user_model: str
    n_chunks: int = 1
    chunk_shot_ids: list[list[str]] = Field(
        default_factory=list,
        description="Per-chunk list of shot_ids — for long-form chain orchestration",
    )
    reasoning: str = ""


# ============================================================
# Skill class — pure-function, no LLM
# ============================================================

# Wan 2.7 discrete duration constraint
_WAN_DISCRETE = [5, 10]

# Seedance 2.0 limits
_SEEDANCE_MAX_SHOT_S = 15           # per-shot in multi-shot inline
_SEEDANCE_MAX_TOTAL_SINGLE_CALL = 15  # current Seedance/Atlas generation cap
_SEEDANCE_MAX_SHOTS_SINGLE_CALL = 6   # practical cap for prompt readability


class AutoDirector:
    """Skill 3/5 — Auto Director (deterministic, no LLM)."""

    name = "director"
    description = "Quyết shot count + duration + camera + chain strategy"

    async def run(self, inp: DirectorInput) -> DirectorOutput:
        """Map storyboard panels → shot specs + decide render strategy.

        Deterministic — no LLM call. Async for orchestrator consistency.
        """
        is_seedance = inp.user_model.startswith("seedance_2_0") or inp.user_model == "auto"
        is_wan = inp.user_model == "wan_2_7"

        shots: list[DirectorShotSpec] = []
        chunk_shot_ids: dict[int, list[str]] = {}

        for i, panel in enumerate(inp.storyboard.panels):
            shot_id = f"S{i + 1}"

            # Clamp duration to model constraints
            dur = int(round(panel.duration_s))
            if is_wan:
                # Wan 2.7 discrete [5,10] — snap to nearest
                dur = min(_WAN_DISCRETE, key=lambda v: abs(v - dur))
            else:
                dur = max(1, min(_SEEDANCE_MAX_SHOT_S, dur))

            # Subject + action — split visual_description heuristically.
            # If LLM wrote 1 sentence, use as both. If multi-sentence, first = subject,
            # rest = action context.
            visual = panel.visual_description.strip()
            subject, action = _split_subject_action(visual)

            # Chain hint — connect to previous shot in SAME chunk
            prev_id = None
            if i > 0:
                prev_panel = inp.storyboard.panels[i - 1]
                if prev_panel.chunk_id == panel.chunk_id:
                    prev_id = f"S{i}"

            shot_spec = DirectorShotSpec(
                shot_id=shot_id,
                index=i,
                duration_s=dur,
                purpose=panel.purpose,
                subject=subject,
                action=action,
                camera_shot=_extract_camera_shot(panel.suggested_camera),
                camera_movement=_extract_camera_movement(panel.suggested_camera),
                lighting_override=panel.suggested_lighting,
                emotion_beat=panel.emotion_beat,
                chunk_id=panel.chunk_id,
                previous_shot_id=prev_id,
            )
            shots.append(shot_spec)
            chunk_shot_ids.setdefault(panel.chunk_id, []).append(shot_id)

        total_dur = sum(s.duration_s for s in shots)
        n_chunks = len(chunk_shot_ids)

        # Pick render strategy
        strategy: RenderStrategy
        reasoning_parts: list[str] = []

        if is_wan:
            strategy = "per_shot_chain"
            reasoning_parts.append("Wan 2.7 is i2v only → per_shot_chain")
        elif is_seedance and n_chunks == 1 and len(shots) <= _SEEDANCE_MAX_SHOTS_SINGLE_CALL and total_dur <= _SEEDANCE_MAX_TOTAL_SINGLE_CALL:
            strategy = "single_call_multi_shot"
            reasoning_parts.append(
                f"Seedance 2.0 single-call: {len(shots)} shots, {total_dur}s total"
            )
        else:
            strategy = "per_shot_chain"
            if n_chunks > 1:
                reasoning_parts.append(f"Long-form {n_chunks} chunks → chain via last_frame")
            elif len(shots) > _SEEDANCE_MAX_SHOTS_SINGLE_CALL:
                reasoning_parts.append(f"{len(shots)} shots > {_SEEDANCE_MAX_SHOTS_SINGLE_CALL} cap")
            elif total_dur > _SEEDANCE_MAX_TOTAL_SINGLE_CALL:
                reasoning_parts.append(f"{total_dur}s > {_SEEDANCE_MAX_TOTAL_SINGLE_CALL}s single-call cap")

        # Resolve "auto" model based on dialogue + duration signals
        resolved_model = inp.user_model
        if resolved_model == "auto":
            has_dialogue = inp.planner.suggested_audio_mode == "dialogue_vo"
            if has_dialogue and total_dur in (5, 10):
                resolved_model = "wan_2_7"
                reasoning_parts.append("auto→wan_2_7 (lip-sync VN + discrete dur)")
            elif total_dur <= 15:
                resolved_model = "seedance_2_0_fast"
                reasoning_parts.append("auto→seedance_2_0_fast (short, cost-optimized)")
            else:
                resolved_model = "seedance_2_0"
                reasoning_parts.append("auto→seedance_2_0 (premium for >15s)")

        out = DirectorOutput(
            shots=shots,
            total_duration_s=total_dur,
            render_strategy=strategy,
            user_model=resolved_model,
            n_chunks=n_chunks,
            chunk_shot_ids=[chunk_shot_ids[k] for k in sorted(chunk_shot_ids.keys())],
            reasoning="; ".join(reasoning_parts),
        )
        logger.info(
            f"[AutoDirector] shots={len(shots)} dur={total_dur}s strategy={strategy} "
            f"model={resolved_model} chunks={n_chunks}"
        )
        return out


# ============================================================
# Helpers — parse storyboard hints
# ============================================================

def _split_subject_action(visual: str) -> tuple[str, str]:
    """Split visual_description thành (subject, action).

    Heuristic: first sentence = subject + context, rest = action progression.
    If only 1 sentence, subject = full text, action = "".
    """
    sentences = [s.strip() for s in visual.replace("?", ".").replace("!", ".").split(".") if s.strip()]
    if not sentences:
        return (visual, "")
    if len(sentences) == 1:
        return (sentences[0], "")
    return (sentences[0], ". ".join(sentences[1:]))


_CAMERA_SHOTS = {"ECU", "CU", "MCU", "MS", "MLS", "WS", "EWS", "POV", "drone", "OTS"}


def _extract_camera_shot(hint: str) -> str:
    """Pull canonical shot size from free-form hint."""
    if not hint:
        return "MS"
    upper = hint.upper()
    for shot in _CAMERA_SHOTS:
        if shot in upper:
            return shot
    return "MS"  # safe default


_CAMERA_MOVES = {
    "static", "push-in", "pull-out", "dolly", "tracking", "pan", "tilt",
    "whip", "handheld", "drone", "crane", "orbit", "zoom",
}


def _extract_camera_movement(hint: str) -> str:
    """Pull canonical camera movement from free-form hint."""
    if not hint:
        return "static"
    lower = hint.lower()
    for mv in _CAMERA_MOVES:
        if mv in lower:
            return mv
    return "static"


__all__ = [
    "AutoDirector", "DirectorInput", "DirectorOutput",
    "DirectorShotSpec", "RenderStrategy",
]
