"""Smart Picker — chấm điểm 6 strategies → pick model fit script nhất.

Logic:
    1. User chọn model explicit → respect, không pick lại
    2. User chọn "auto" → score 6 strategies, pick highest
    3. Budget tier influence (fast → favor Fast variants)
    4. Return reasoning string cho UI badge
"""

from typing import Literal, Optional

from loguru import logger

from agent.strategies import ALL_STRATEGIES, WorkflowStrategy, get_strategy_for_model
from agent.strategies.base import Script


BudgetTier = Literal["fast", "balanced", "premium"]


def pick_strategy(
    script: Script,
    user_preference: Optional[str] = None,
    budget_tier: BudgetTier = "balanced",
) -> tuple[WorkflowStrategy, list[dict]]:
    """Pick best strategy + return full ranking cho UI hiển thị "why".

    Args:
        script: parsed Script object.
        user_preference: user_model key user chọn explicit (vd 'seedance_2_0').
            Nếu None hoặc "auto" → smart pick.
        budget_tier: ảnh hưởng scoring khi auto-pick.

    Returns:
        (chosen_strategy, ranking) — ranking là list dict
        [{user_model, display_name, score, reasoning}, ...] sorted desc.
    """
    # Explicit user choice
    if user_preference and user_preference != "auto":
        try:
            chosen = get_strategy_for_model(user_preference)
            ranking = [{
                "user_model": chosen.user_model,
                "display_name": chosen.display_name_vn,
                "score": 1.0,
                "reasoning": f"User chọn explicit: {chosen.reasoning_for_script(script)}",
                "selected": True,
            }]
            return chosen, ranking
        except ValueError as e:
            logger.warning(f"[picker] user_preference '{user_preference}' invalid: {e}")

    # Smart pick — score all
    scored: list[tuple[WorkflowStrategy, float]] = []
    for s in ALL_STRATEGIES:
        raw_score = s.suitability_score(script)
        weighted = _apply_budget_weight(raw_score, s.user_model, budget_tier)
        scored.append((s, weighted))

    scored.sort(key=lambda x: x[1], reverse=True)
    chosen = scored[0][0]

    # Build ranking dict cho UI
    ranking = [
        {
            "user_model": s.user_model,
            "display_name": s.display_name_vn,
            "score": round(score, 3),
            "reasoning": s.reasoning_for_script(script),
            "selected": s.user_model == chosen.user_model,
        }
        for s, score in scored
    ]

    logger.info(
        f"[picker] smart-pick: {chosen.user_model} (score={scored[0][1]:.2f}, "
        f"tier={budget_tier}) — top 3: {[r['user_model'] for r in ranking[:3]]}"
    )
    return chosen, ranking


def _apply_budget_weight(score: float, user_model: str, tier: BudgetTier) -> float:
    """Adjust score theo budget tier user pick."""
    if tier == "fast":
        # Ưu ái Fast variants + Seedance 1.5 Pro (rẻ hơn)
        if user_model == "seedance_2_0_fast":
            return min(score * 1.5, 1.0)
        if user_model == "seedance_1_5_pro":
            return min(score * 1.3, 1.0)
        if user_model == "vidu_q3_mix":
            return score * 0.5  # premium quá đắt
        return score

    if tier == "premium":
        # Ưu ái Vidu Q3 Mix + Seedance 2.0 (chất lượng cao hơn)
        if user_model in ("vidu_q3_mix",):
            return min(score * 1.4, 1.0)
        if user_model == "seedance_2_0":
            return min(score * 1.2, 1.0)
        if user_model == "seedance_2_0_fast":
            return score * 0.6
        return score

    # balanced — no weighting
    return score
