"""Auto-mode model picker — heuristic routing dựa trên DirectorPlan.

V6 — chỉ còn 3 candidate:
    seedance_2_0       — premium tier ($0.096/s)
    seedance_2_0_fast  — mid tier ($0.076/s, default cho hầu hết job)
    wan_2_7            — fallback chuyên cho talking-head VN lip-sync

Quy tắc đơn giản — Seedance 2.0 luôn thắng trừ khi job yêu cầu driven-audio
lip-sync (chỉ Wan 2.7 có) hoặc budget cực thấp (Fast tier).

Pure-function, không LLM call. Trả về tuple (user_model, reasoning).
"""
from __future__ import annotations

from typing import Tuple

from agent.schemas import DirectorPlan
from agent.model_capabilities import capabilities_for, validate_shot_against_model


# SEEDANCE 2.0 CORE PATH + FALLBACK PATH (Wan 2.7)
_CANDIDATES = ["seedance_2_0", "seedance_2_0_fast", "wan_2_7"]


def pick_model_for_plan(
    plan: DirectorPlan,
    budget_tier: str = "balanced",
) -> Tuple[str, str]:
    """Score 3 candidate models against the plan; return (user_model, reasoning).

    `budget_tier`:
        - "cheap"     → bias toward seedance_2_0_fast
        - "balanced"  → default, picks seedance_2_0_fast for most jobs
        - "premium"   → bias toward seedance_2_0 (full tier)
    """
    bible = plan.continuity_bible
    shots = plan.shot_list
    n_shots = len(shots)
    total_dur = sum(s.duration_s for s in shots)
    max_refs_needed = max(
        (len(s.continuity.reference_indices) for s in shots),
        default=0,
    )
    has_dialogue = any(s.audio.dialogue_vn for s in shots)
    has_lip_sync_intent = (
        bible.audio_design.dialogue_style.lower() in ("conversational", "monologue")
        and has_dialogue
        and bible.intent in ("talking_head", "presenter", "interview", "demo")
    )
    needs_1080p = (
        bible.intent in ("brand_story", "product_demo", "premium_ad")
        or budget_tier == "premium"
    )

    scores: dict[str, tuple[float, list[str]]] = {}

    for m in _CANDIDATES:
        cap = capabilities_for(m)
        score = 5.0
        notes: list[str] = []

        # Rule 1 — lip-sync hard requirement (only Wan satisfies)
        if has_lip_sync_intent:
            if cap.audio_mode == "driven":
                score += 4.0
                notes.append("driven lip-sync (talking-head VN)")
            else:
                score -= 2.0
                notes.append("không hỗ trợ driven lip-sync")

        # Rule 2 — ref count fit (Seedance 9 vs Wan 1)
        if max_refs_needed > cap.max_refs:
            score -= 3.0
            notes.append(f"shots cần {max_refs_needed} refs > model max {cap.max_refs}")
        elif max_refs_needed >= 4 and cap.max_refs >= 9:
            score += 1.5
            notes.append("9 refs đủ chỗ multi-subject")

        # Rule 3 — duration fit (Wan discrete [5,10])
        if cap.duration_discrete:
            non_discrete = [
                s.duration_s for s in shots if s.duration_s not in cap.duration_discrete
            ]
            if non_discrete:
                score -= 1.5
                notes.append(
                    f"{len(non_discrete)} shot ngoài discrete {cap.duration_discrete}"
                )

        if total_dur > cap.duration_max_s * max(1, n_shots) and n_shots <= 2:
            score -= 1.0
            notes.append("total duration vượt model max")

        # Rule 4 — multi-shot inline bonus (Seedance 2.0 only)
        if n_shots >= 4 and cap.supports_multi_shot_prompting:
            score += 1.0
            notes.append("multi-shot inline")

        # Rule 5 — quad-modal bonus when user supplied video/audio refs
        # (signal: ContinuityBible.reference_assets has multiple high-priority roles)
        if cap.supports_quad_modal:
            score += 0.5
            notes.append("quad-modal (img+vid+aud)")

        # Rule 6 — 1080p / premium bias
        if needs_1080p and m == "seedance_2_0":
            score += 1.0
            notes.append("premium tier match (full 1080p)")

        # Rule 7 — budget bias
        if budget_tier == "cheap" and cap.cost_per_second_usd <= 0.08:
            score += 1.5
            notes.append("budget cheap match")
        elif budget_tier == "premium" and cap.cost_per_second_usd >= 0.09:
            score += 0.5

        # Hard validation — crater score if model literally cannot execute
        critical = 0
        for s in shots:
            for v in validate_shot_against_model(s.model_dump(), cap):
                if "discrete" in v or "max " in v or "out of range" in v:
                    critical += 1
        if critical > 0:
            score -= 10.0 * critical
            notes.append(f"{critical} hard spec violation(s)")

        scores[m] = (round(score, 2), notes)

    picked = max(scores.items(), key=lambda kv: kv[1][0])
    user_model, (final_score, picked_notes) = picked
    reasoning = (
        f"Picked {user_model} (score {final_score}) — "
        f"{'; '.join(picked_notes) or 'best default fit'}"
    )
    return user_model, reasoning


def explain_scores(plan: DirectorPlan, budget_tier: str = "balanced") -> dict:
    """Debug helper — return full score breakdown for all candidates."""
    out: dict = {}
    bible = plan.continuity_bible
    out["_context"] = {
        "n_shots": len(plan.shot_list),
        "total_dur": sum(s.duration_s for s in plan.shot_list),
        "has_dialogue": any(s.audio.dialogue_vn for s in plan.shot_list),
        "intent": bible.intent,
        "n_characters": len(bible.characters),
        "max_refs_needed": max(
            (len(s.continuity.reference_indices) for s in plan.shot_list), default=0
        ),
        "budget_tier": budget_tier,
    }
    picked, reasoning = pick_model_for_plan(plan, budget_tier)
    out["picked"] = picked
    out["reasoning"] = reasoning
    return out
