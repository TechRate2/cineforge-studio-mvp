"""Cost-gate Evaluation — per CineForge v2.1 §7.

Workflow:
    1. Render shot[0] with the cheapest tier (Seedance 2.0 Fast / Vidu Q3 Fast).
    2. Evaluate the draft clip against Bible expectations (consistency anchor +
       red_flag scan).
    3. If pass (score >= threshold) → caller proceeds with full Standard render.
       If fail → caller aborts with suggestions, saving 80-90% of credits.

This module is a *pure decision layer* — it doesn't render anything. Caller
(`workers/video_worker.render_plan`) passes a draft clip path + Bible and gets
back a `CostGateDecision`.

The actual draft render reuses the existing renderer with `model="seedance_2_0_fast"`
forced. The "pass" threshold is configurable per-job.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from loguru import logger

from agent.schemas import ContinuityBible, EvaluationReport
from agent.evaluation_layer import evaluate_plan


@dataclass
class CostGateDecision:
    pass_: bool                          # True → continue to Standard render
    score: float                          # Composite score 0-10
    threshold: float                      # The threshold this was checked against
    reasoning: str                        # 1-2 sentence summary for the user
    suggestions: list[str]                # Actionable fixes if failed
    raw_report: Optional[dict] = None    # Full sub-report for debugging


# Default model overrides for the draft stage.
DRAFT_MODEL_OVERRIDE = {
    "seedance_2_0": "seedance_2_0_fast",
    "seedance_2_0_fast": "seedance_2_0_fast",  # already fast
    "seedance_1_5_pro": "seedance_2_0_fast",   # downgrade
    "vidu_q3": "vidu_q3",                       # vidu has no fast tier — same model
    "vidu_q3_mix": "vidu_q3",
    "wan_2_7": "wan_2_7",                       # wan already cheap
    "auto": "seedance_2_0_fast",
}


def draft_model_for(user_model: str) -> str:
    """Pick the cheapest model that's quality-comparable to `user_model`."""
    return DRAFT_MODEL_OVERRIDE.get(user_model, "seedance_2_0_fast")


def evaluate_draft_clip(
    plan_dict: dict,
    draft_shot_id: str,
    threshold: float = 7.0,
) -> CostGateDecision:
    """Score a draft (shot 0) against Bible expectations.

    BUG #6 fix — we pass the FULL plan to the evaluator (so it sees the
    narrative arc, pacing curve, every shot's purpose) but tag clearly that
    only `draft_shot_id` was actually rendered. This avoids the previous bias
    where trimming the plan to 1 shot caused the LLM to undercharge pacing
    and viral scores (no arc visible).

    The evaluator is also told to weight CONSISTENCY (Bible compliance of the
    draft shot) heavily and IGNORE the unrendered shots when scoring
    cinematic / pacing aesthetics — those will be re-evaluated post final
    render.

    Why LLM and not CLIP/face-embedding? Reasoning models catch semantic drift
    (wrong outfit / wrong dialogue / wrong location) cheaper and richer than
    embeddings, which only measure visual similarity.
    """
    total_dur = sum(s["duration_s"] for s in plan_dict.get("shot_list", []))
    draft_shot = next(
        (s for s in plan_dict.get("shot_list", []) if s["shot_id"] == draft_shot_id),
        None,
    )
    if draft_shot is None:
        logger.warning(f"[cost_gate] draft_shot_id {draft_shot_id} not in plan — PASS by default")
        return CostGateDecision(
            pass_=True, score=0.0, threshold=threshold,
            reasoning=f"shot_id {draft_shot_id} not found; proceeded conservatively",
            suggestions=[],
        )

    # CRITICAL C8 — Reject drafts where shot[0] has previous_shot_id set.
    # Cost gate renders shot[0] in isolation; if Director planned shot[0] to
    # chain from a non-existent prior shot, the gate prompt would inject a
    # phantom chain anchor and the LLM evaluator would score against
    # contradictory context. Fail-fast with actionable suggestion.
    cont = draft_shot.get("continuity") or {}
    if cont.get("previous_shot_id") is not None:
        logger.error(
            f"[cost_gate] {draft_shot_id} has previous_shot_id="
            f"{cont['previous_shot_id']!r} — shot[0] cannot chain"
        )
        return CostGateDecision(
            pass_=False,
            score=0.0,
            threshold=threshold,
            reasoning=(
                f"Cost-gate aborted — shot {draft_shot_id} (the first shot to "
                f"render) declares previous_shot_id={cont['previous_shot_id']!r}. "
                f"The first shot must not chain (no prior frame exists)."
            ),
            suggestions=[
                f"Edit shot {draft_shot_id}: clear continuity.previous_shot_id (set to null).",
                "Director Agent V3 system_prompts/director.md §4 'Reset chain ONLY on intentional cuts' — apply here.",
            ],
        )

    draft_brief = (
        f"COST-GATE DRAFT EVALUATION: Only shot `{draft_shot_id}` has been rendered "
        f"as a Fast-tier draft (cost-gate stage). The remaining shots in the plan "
        f"are PLANNED, NOT yet rendered. Focus your scoring on: "
        f"(1) consistency_score — does the draft shot honor the Bible "
        f"(character face_signature, outfit, products, visual_style)? "
        f"(2) brand_safety_score — does it violate any constraint? "
        f"For cinematic / pacing / viral, score the PLAN, not the draft alone "
        f"(since only 1 of {len(plan_dict.get('shot_list', []))} shots is real). "
        f"Render decision: if consistency or brand_safety is weak, abort to save credits."
    )
    try:
        report: EvaluationReport = evaluate_plan(
            plan_dict=plan_dict,  # full plan — Bible + Shot List + Storyboard
            user_brief=draft_brief,
            tech_config={
                "duration_s": total_dur,
                "draft_only_shot_id": draft_shot_id,
                "draft_only_shot_duration_s": draft_shot["duration_s"],
            },
        )
    except Exception as e:
        logger.warning(f"[cost_gate] eval LLM fail — defaulting to PASS to not block user: {e}")
        return CostGateDecision(
            pass_=True, score=0.0, threshold=threshold,
            reasoning=f"evaluator unavailable ({e}); proceeded conservatively",
            suggestions=[],
        )

    # Cost-gate weighting — heavier on consistency + brand_safety (Bible compliance
    # is the ONLY thing the rendered draft can prove); lighter on pacing/cinematic
    # (those depend on the unrendered shots).
    score = round(
        0.50 * report.consistency_score
        + 0.30 * report.brand_safety_score
        + 0.10 * report.cinematic_score
        + 0.10 * report.pacing_score,
        2,
    )
    passed = score >= threshold and not report.red_flags

    return CostGateDecision(
        pass_=passed,
        score=score,
        threshold=threshold,
        reasoning=(
            f"Draft passed (weighted score {score} ≥ {threshold}, "
            f"consistency={report.consistency_score}, brand_safety={report.brand_safety_score})."
            if passed
            else f"Draft failed (weighted score {score} < {threshold}, "
                 f"consistency={report.consistency_score}, "
                 f"red_flags={len(report.red_flags)})."
        ),
        suggestions=report.suggestions[:5],
        raw_report=report.model_dump(),
    )
