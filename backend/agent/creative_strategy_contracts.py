"""Contracts for Phase 6A creative reasoning.

The MVP stores auditable summaries and decision factors only. It deliberately
does not persist raw chain-of-thought text.
"""
from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


ReasoningMode = Literal[
    "rule_only",
    "llm_assisted",
    "llm_recommended_no_selector",
    "rule_fallback_after_invalid_llm",
    "rule_fallback_after_rejected_llm",
    "rule_fallback_after_selector_error",
    "rule_fallback_after_selector_timeout",
]
ShotBias = Literal["single_shot", "multi_shot", "adaptive"]


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp without importing pipeline contracts."""
    return datetime.now(timezone.utc)


class CreativeRiskProfile(BaseModel):
    """Risk signals considered when selecting a creative strategy."""

    model_config = ConfigDict(extra="forbid")

    identity_drift_risk: float = Field(0.0, ge=0.0, le=1.0)
    product_drift_risk: float = Field(0.0, ge=0.0, le=1.0)
    style_drift_risk: float = Field(0.0, ge=0.0, le=1.0)
    duration_complexity_risk: float = Field(0.0, ge=0.0, le=1.0)
    reference_sufficiency_risk: float = Field(0.0, ge=0.0, le=1.0)
    prompt_overload_risk: float = Field(0.0, ge=0.0, le=1.0)
    risk_flags: list[str] = Field(default_factory=list)


class StrategyCandidate(BaseModel):
    """One creative strategy option generated from deterministic playbooks."""

    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    name: str
    strategy_type: str
    fit_score: float = Field(..., ge=0.0, le=1.0)
    risk_score: float = Field(..., ge=0.0, le=1.0)
    selection_score: float = Field(..., ge=0.0, le=1.0)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    shot_bias: ShotBias = "adaptive"
    expected_shot_count: int | None = Field(None, ge=1)
    hook_pattern: str = ""
    narrative_structure: list[str] = Field(default_factory=list)
    pacing_profile: str = ""
    style_direction: str = ""
    audio_direction: str = ""
    required_assets: list[str] = Field(default_factory=list)
    prompt_implications: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)
    rules_applied: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMStrategySelection(BaseModel):
    """Structured selector output; raw chain-of-thought must not be stored here."""

    model_config = ConfigDict(extra="forbid")

    selected_strategy_id: str = Field(..., min_length=1, max_length=120)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    rationale_summary: str = ""
    evidence: list[str] = Field(default_factory=list)
    rejected_strategy_ids: list[str] = Field(default_factory=list)
    safety_warnings: list[str] = Field(default_factory=list)


class LLMStrategyPolicyResult(BaseModel):
    """Guardrail decision for an optional LLM strategy override."""

    model_config = ConfigDict(extra="forbid")

    allowed: bool
    requested_strategy_id: str | None = None
    final_strategy_id: str
    fallback_strategy_id: str
    selector_confidence_score: float | None = Field(None, ge=0.0, le=1.0)
    selector_elapsed_ms: float | None = Field(None, ge=0.0)
    selected_candidate_rank: int | None = Field(None, ge=1)
    rejected_reason_ids: list[str] = Field(default_factory=list)
    policy_warning_ids: list[str] = Field(default_factory=list)
    guardrail_rule_ids: list[str] = Field(default_factory=list)
    rationale_summary: str = ""


class LLMGuardrailConfig(BaseModel):
    """Configurable LLM override thresholds for a safe MVP selector."""

    model_config = ConfigDict(extra="forbid")

    min_confidence: float = Field(0.65, ge=0.0, le=1.0)
    max_candidate_risk: float = Field(0.60, ge=0.0, le=1.0)
    min_consistency_score: float = Field(68.0, ge=0.0, le=100.0)
    top_n: int = Field(3, ge=1, le=10)
    selector_timeout_s: float = Field(10.0, ge=0.001, le=60.0)
    max_rationale_chars: int = Field(600, ge=80, le=4000)
    niche_overrides: dict[str, dict[str, float | int]] = Field(default_factory=dict)
    user_tier_overrides: dict[str, dict[str, float | int]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_overrides(self) -> "LLMGuardrailConfig":
        """Reject malformed per-niche and per-tier overrides at config load time."""
        for override_group_name, override_group in (
            ("niche_overrides", self.niche_overrides),
            ("user_tier_overrides", self.user_tier_overrides),
        ):
            _validate_guardrail_overrides(override_group_name, override_group)
        return self


_LLM_GUARDRAIL_OVERRIDE_KEYS = {
    "min_confidence",
    "max_candidate_risk",
    "min_consistency_score",
    "top_n",
    "selector_timeout_s",
    "max_rationale_chars",
}


def _validate_guardrail_overrides(
    group_name: str,
    overrides: dict[str, dict[str, float | int]],
) -> None:
    """Validate dynamic guardrail overrides before they reach production selection."""
    for scope, values in overrides.items():
        unknown = set(values) - _LLM_GUARDRAIL_OVERRIDE_KEYS
        if unknown:
            unknown_list = ", ".join(sorted(unknown))
            raise ValueError(f"{group_name}.{scope} has unsupported keys: {unknown_list}")
        for key, value in values.items():
            if key in {"min_confidence", "max_candidate_risk"} and not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{group_name}.{scope}.{key} must be between 0 and 1")
            if key == "min_consistency_score" and not 0.0 <= float(value) <= 100.0:
                raise ValueError(f"{group_name}.{scope}.{key} must be between 0 and 100")
            if key == "top_n" and not 1 <= int(value) <= 10:
                raise ValueError(f"{group_name}.{scope}.{key} must be between 1 and 10")
            if key == "selector_timeout_s" and not 0.001 <= float(value) <= 60.0:
                raise ValueError(f"{group_name}.{scope}.{key} must be between 0.001 and 60")
            if key == "max_rationale_chars" and not 80 <= int(value) <= 4000:
                raise ValueError(f"{group_name}.{scope}.{key} must be between 80 and 4000")


class CreativeStrategyContract(BaseModel):
    """Selected strategy and the compact reasoning evidence behind it."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = "cineforge.creative_strategy.v1"
    strategy_contract_id: str = Field(default_factory=lambda: f"strategy_{uuid4().hex[:12]}")
    analysis_id: str
    selected_strategy: StrategyCandidate
    candidates: list[StrategyCandidate] = Field(default_factory=list)
    reasoning_mode: ReasoningMode = "rule_only"
    reasoning_summary: str = ""
    decision_factors: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    identity_requirements: dict[str, Any] = Field(default_factory=dict)
    llm_policy_result: LLMStrategyPolicyResult | None = None
    risk_profile: CreativeRiskProfile = Field(default_factory=CreativeRiskProfile)
    rules_applied: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=utc_now)


__all__ = [
    "CreativeRiskProfile",
    "CreativeStrategyContract",
    "LLMGuardrailConfig",
    "LLMStrategyPolicyResult",
    "LLMStrategySelection",
    "ReasoningMode",
    "ShotBias",
    "StrategyCandidate",
]
