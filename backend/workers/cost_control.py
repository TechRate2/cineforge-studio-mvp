"""Cost gates for paid render execution."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from pipeline.contracts import SeedanceExecutionPlan


_DEFAULT_RATE_USD_PER_SECOND = {
    "seedance_2_0": 0.06,
    "seedance_2_0_fast": 0.03,
    "seedance_2_0_ref": 0.06,
    "seedance_2_0_i2v": 0.06,
}


class CostGateDecision(BaseModel):
    """Decision from the draft-first cost gate."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    should_render: bool
    mode: str = "off"
    estimated_total_usd: float = 0.0
    estimated_draft_usd: float = 0.0
    max_total_usd: float | None = None
    reason: str = ""
    draft_shot_id: str | None = None


class CostControlService:
    """Estimate and enforce cost policy before paid render."""

    def estimate_plan_cost(self, execution_plan: SeedanceExecutionPlan) -> dict[str, float]:
        """Return a deterministic cost estimate when the plan omitted one."""
        if execution_plan.cost_estimate:
            numeric = {
                str(key): float(value)
                for key, value in execution_plan.cost_estimate.items()
                if isinstance(value, int | float)
            }
            if numeric:
                return numeric
        total = 0.0
        for shot in execution_plan.shots:
            model = shot.model if shot.model != "auto" else execution_plan.model
            total += _rate_for(model) * shot.duration_s
        if not execution_plan.shots:
            total = _rate_for(execution_plan.model) * execution_plan.duration_s
        return {
            "render_cost_usd": round(total, 3),
            "total_cost_usd": round(total, 3),
        }

    def evaluate_preflight(
        self,
        execution_plan: SeedanceExecutionPlan,
        *,
        mode: str = "off",
        max_total_usd: float | None = None,
    ) -> CostGateDecision:
        """Evaluate whether render can proceed under the configured cost policy."""
        estimate = self.estimate_plan_cost(execution_plan)
        total = float(estimate.get("total_cost_usd") or estimate.get("render_cost_usd") or 0.0)
        if max_total_usd is not None and total > max_total_usd:
            return CostGateDecision(
                enabled=True,
                should_render=False,
                mode=mode,
                estimated_total_usd=total,
                max_total_usd=max_total_usd,
                reason=f"estimated cost ${total:.3f} exceeds max ${max_total_usd:.3f}",
            )
        if mode == "draft_first" and execution_plan.shots:
            first = execution_plan.shots[0]
            return CostGateDecision(
                enabled=True,
                should_render=True,
                mode=mode,
                estimated_total_usd=total,
                estimated_draft_usd=round(_rate_for("seedance_2_0_fast") * first.duration_s, 3),
                max_total_usd=max_total_usd,
                reason="draft_first will render the first shot before full plan execution",
                draft_shot_id=first.shot_id,
            )
        return CostGateDecision(
            enabled=mode != "off" or max_total_usd is not None,
            should_render=True,
            mode=mode,
            estimated_total_usd=total,
            max_total_usd=max_total_usd,
            reason="cost gate passed",
        )


def _rate_for(model: str) -> float:
    return _DEFAULT_RATE_USD_PER_SECOND.get(str(model or ""), 0.06)


__all__ = ["CostControlService", "CostGateDecision"]
