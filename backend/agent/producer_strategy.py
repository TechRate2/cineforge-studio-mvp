"""Cost-aware producer strategy for autonomous renders.

The creative chain can plan 5-30 minute videos, but the render worker should not
blindly spend credits with the same policy as a 15 second short. This module is
a deterministic producer layer: estimate risk, choose cost-gate behavior, and
attach user-visible warnings without blocking the autonomous flow.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class ProducerStrategy:
    tier: str
    cost_gate_mode: str
    cost_gate_threshold: float
    estimated_cost_usd: float
    estimated_duration_s: int
    risk_level: str
    long_form_mode: bool
    execution_note: str
    warnings: list[str]
    recommended_next: list[str]

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def build_producer_strategy(
    *,
    estimated_cost_usd: float,
    estimated_duration_s: int,
    n_shots: int,
    n_chunks: int,
    render_strategy: str,
    resolved_model: str,
) -> ProducerStrategy:
    """Return render/cost policy for an autonomous job."""
    cost = float(estimated_cost_usd or 0.0)
    duration = int(estimated_duration_s or 0)
    long_form = duration > 180 or n_chunks > 3

    risk = "low"
    warnings: list[str] = []
    recommended_next: list[str] = []

    if cost >= 25 or duration >= 900:
        risk = "very_high"
    elif cost >= 10 or duration >= 300:
        risk = "high"
    elif cost >= 3 or duration > 60 or n_shots > 6:
        risk = "medium"

    cost_gate_mode = "off"
    threshold = 7.0
    tier = "direct_render"

    if risk in ("medium", "high", "very_high"):
        cost_gate_mode = "draft_first"
        threshold = 7.2 if risk == "medium" else 7.6
        tier = "draft_first_producer_gate"

    if long_form:
        warnings.append(
            "Long-form render has a resumable production graph path; keep it behind CINEJELLY_ENABLE_GRAPH_LONG_FORM=1 until paid benchmarks validate default-on production use."
        )
        recommended_next.append("Run paid long-form benchmarks, then promote graph executor mode as the default for 5-30 minute jobs.")
    if risk in ("high", "very_high"):
        warnings.append(
            "Estimated render cost is high; use draft-first gate and retry only failed shots."
        )
        recommended_next.append("Add user-visible cost confirmation or project budget cap before full 5-30m renders.")
    if resolved_model == "wan_2_7" and duration > 60:
        warnings.append(
            "Wan 2.7 is best for driven-audio/lip-sync shots, not long full-film rendering."
        )
        recommended_next.append("Route only dialogue close-ups to Wan 2.7 and keep cinematic coverage on Seedance 2.0.")
    if "single_call" in (render_strategy or "") and duration > 15:
        warnings.append(
            "Single-call Seedance generations are capped per request; long videos must be split into chained shots/chunks."
        )

    if not warnings:
        warnings.append("Direct autonomous render is appropriate for this short-form job.")

    return ProducerStrategy(
        tier=tier,
        cost_gate_mode=cost_gate_mode,
        cost_gate_threshold=threshold,
        estimated_cost_usd=round(cost, 3),
        estimated_duration_s=duration,
        risk_level=risk,
        long_form_mode=long_form,
        execution_note=(
            "draft-first quality gate enabled before full render"
            if cost_gate_mode == "draft_first" else
            "direct render; post-render QA still records retry recommendations"
        ),
        warnings=warnings,
        recommended_next=recommended_next,
    )


__all__ = ["ProducerStrategy", "build_producer_strategy"]
