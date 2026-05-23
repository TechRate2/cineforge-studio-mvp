"""Auto-mode model picker — heuristic routing dựa trên DirectorPlan.

Mục đích: khi user chọn `settings.model="auto"`, không chỉ default cứng về
Seedance 2.0 — đọc Continuity Bible + Shot List → chấm fit từng model rồi
pick best.

Pure-function, không LLM call. Quy tắc đơn giản dựa trên model capabilities
đã verified ở `model_capabilities.py`.

Trả về tuple (picked_user_model, reasoning) để caller log + show user.
"""
from __future__ import annotations

from typing import Tuple

from agent.schemas import DirectorPlan
from agent.model_capabilities import capabilities_for


def pick_model_for_plan(
    plan: DirectorPlan,
    budget_tier: str = "balanced",
) -> Tuple[str, str]:
    """Score 5 candidate models against the plan; return (user_model, reasoning).

    `budget_tier`:
        - "cheap"     → bias toward Seedance 2.0 Fast / Vidu Q3
        - "balanced"  → default, fits most plans
        - "premium"   → bias toward Seedance 2.0 Standard / Vidu Q3 Mix
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
    is_multi_character = len(bible.characters) >= 2
    needs_1080p = (
        bible.intent in ("brand_story", "product_demo", "premium_ad")
        or budget_tier == "premium"
    )

    candidates = [
        "seedance_2_0", "seedance_2_0_fast", "vidu_q3", "vidu_q3_mix", "wan_2_7",
    ]
    scores: dict[str, tuple[float, list[str]]] = {}

    for m in candidates:
        cap = capabilities_for(m)
        score = 5.0
        notes: list[str] = []

        # Rule 1 — dialogue lip-sync hard requirement
        if has_lip_sync_intent and cap.audio_mode != "driven":
            score -= 2.0
            notes.append("không lip-sync driven")
        if has_lip_sync_intent and cap.audio_mode == "driven":
            score += 4.0
            notes.append("lip-sync driven ưu thế")

        # Rule 2 — ref count fit
        if max_refs_needed > cap.max_refs:
            score -= 3.0
            notes.append(f"shots cần {max_refs_needed} refs > model max {cap.max_refs}")
        elif max_refs_needed >= 4:
            if cap.max_refs >= 9:
                score += 1.5
                notes.append("9 refs đủ chỗ multi-subject")

        # Rule 3 — duration fit (discrete?)
        if cap.duration_discrete:
            non_discrete_shots = [
                s.duration_s for s in shots if s.duration_s not in cap.duration_discrete
            ]
            if non_discrete_shots:
                score -= 1.5
                notes.append(
                    f"{len(non_discrete_shots)} shot ngoài discrete {cap.duration_discrete}"
                )

        if total_dur > cap.duration_max_s * max(1, n_shots) and n_shots <= 2:
            # Single chain blow past model's max — penalize
            score -= 1.0
            notes.append("total duration vượt model max")

        # Rule 4 — multi-shot inline pattern bonus
        if n_shots >= 4 and cap.supports_multi_shot_prompting:
            score += 1.0
            notes.append("multi-shot inline")

        # Rule 5 — premium / 1080p bias
        if needs_1080p:
            if m in ("seedance_2_0", "vidu_q3_mix"):
                score += 1.0
                notes.append("premium tier match")
            if m == "vidu_q3":
                score -= 0.5
                notes.append("Vidu Q3 base — chất lượng thấp hơn premium")

        # Rule 6 — multi-character — Vidu Q3 Mix tốt cho multi-subject với @image tags
        if is_multi_character and cap.supports_image_tags:
            score += 0.7
            notes.append("hỗ trợ @image tags cho multi-character")

        # Rule 7 — budget bias
        if budget_tier == "cheap":
            if cap.cost_per_second_usd <= 0.05:
                score += 1.5
                notes.append("budget cheap match")
            elif cap.cost_per_second_usd > 0.09:
                score -= 1.0
                notes.append("budget cheap nhưng model đắt")
        elif budget_tier == "premium":
            if cap.cost_per_second_usd >= 0.09:
                score += 0.5

        # Sprint2 M4 — Hard validation pass: if the picked model literally
        # cannot execute the plan (refs overflow / non-discrete duration),
        # crater the score so the picker won't choose it. Without this guard,
        # the picker might select a model that scores well on aesthetic
        # criteria but causes mid-render 400 from AtlasCloud spec violation.
        from agent.model_capabilities import validate_shot_against_model
        critical_violations = 0
        for s in shots:
            for v in validate_shot_against_model(s.model_dump(), cap):
                # Count only hard violations (matches /director/generate logic)
                if "discrete" in v or "max " in v or "out of range" in v:
                    critical_violations += 1
        if critical_violations > 0:
            score -= 10.0 * critical_violations  # blow well below any positive
            notes.append(f"{critical_violations} hard spec violation(s) — pick will fail")

        scores[m] = (round(score, 2), notes)

    # Pick highest score
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
    n_shots = len(plan.shot_list)
    out["_context"] = {
        "n_shots": n_shots,
        "total_dur": sum(s.duration_s for s in plan.shot_list),
        "has_dialogue": any(s.audio.dialogue_vn for s in plan.shot_list),
        "intent": bible.intent,
        "n_characters": len(bible.characters),
        "max_refs_needed": max(
            (len(s.continuity.reference_indices) for s in plan.shot_list), default=0
        ),
        "budget_tier": budget_tier,
    }
    for m in ["seedance_2_0", "seedance_2_0_fast", "vidu_q3", "vidu_q3_mix", "wan_2_7"]:
        # Run pick logic with isolated single-candidate evaluation
        out[m] = None  # filled below
    picked, reasoning = pick_model_for_plan(plan, budget_tier)
    out["picked"] = picked
    out["reasoning"] = reasoning
    return out
