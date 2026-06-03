"""Creative reasoning orchestration for Phase 6A MVP."""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from agent.creative_strategy_contracts import (
    CreativeRiskProfile,
    CreativeStrategyContract,
    LLMGuardrailConfig,
    LLMStrategyPolicyResult,
    LLMStrategySelection,
    ReasoningMode,
    StrategyCandidate,
)
from agent.creative_strategy_engine import CreativeStrategyEngine
from identity.identity_contracts import ConsistencyScore, IdentityBibleBundle


LOGGER = logging.getLogger(__name__)

LLMStrategySelector = Callable[
    [Any, list[StrategyCandidate], IdentityBibleBundle | None, ConsistencyScore | None],
    LLMStrategySelection | str | dict[str, Any] | None,
]


class CreativeReasoningEngine:
    """Select one strategy using rule-first reasoning with guarded LLM override."""

    def __init__(
        self,
        *,
        strategy_engine: CreativeStrategyEngine | None = None,
        llm_selector: LLMStrategySelector | None = None,
        llm_guardrail_config: LLMGuardrailConfig | None = None,
    ) -> None:
        self.strategy_engine = strategy_engine or CreativeStrategyEngine()
        self.llm_selector = llm_selector
        self.llm_guardrail_config = llm_guardrail_config or LLMGuardrailConfig()

    def select_strategy(
        self,
        *,
        analyzed_input: Any,
        identity_bible: IdentityBibleBundle | None = None,
        consistency_score: ConsistencyScore | None = None,
    ) -> CreativeStrategyContract:
        """Return the selected creative strategy with auditable decision factors."""
        _validate_analyzed_input(analyzed_input)
        candidates = self.strategy_engine.generate_candidates(
            analyzed_input=analyzed_input,
            identity_bible=identity_bible,
            consistency_score=consistency_score,
        )
        if not candidates:
            candidates = self.strategy_engine.generate_fallback_candidates(analyzed_input=analyzed_input)
            LOGGER.warning(
                "creative_reasoning_fallback_candidates_used",
                extra={
                    "analysis_id": getattr(analyzed_input, "analysis_id", None),
                    "candidate_count": len(candidates),
                },
            )
        if not candidates:
            raise ValueError("CreativeStrategyEngine returned no candidates and no fallback candidate.")

        top = candidates[0]
        llm_recommended, llm_reasons = _should_use_llm(
            analyzed_input=analyzed_input,
            candidates=candidates,
            consistency_score=consistency_score,
        )
        selected = top
        reasoning_mode: ReasoningMode = "rule_only"
        warnings: list[str] = []
        llm_policy_result: LLMStrategyPolicyResult | None = None

        if llm_recommended and self.llm_selector:
            effective_guardrail = _effective_guardrail_config(
                self.llm_guardrail_config,
                analyzed_input=analyzed_input,
            )
            try:
                started_at = time.monotonic()
                llm_output = self.llm_selector(analyzed_input, candidates, identity_bible, consistency_score)
                selector_elapsed_ms = round((time.monotonic() - started_at) * 1000.0, 3)
                llm_selection, pre_rejected = _coerce_llm_selection(
                    llm_output,
                    guardrail_config=effective_guardrail,
                )
                if selector_elapsed_ms > effective_guardrail.selector_timeout_s * 1000.0:
                    pre_rejected.append("llm_selector_timeout")
                llm_policy_result = _evaluate_llm_override(
                    selection=llm_selection,
                    candidates=candidates,
                    fallback_candidate=top,
                    analyzed_input=analyzed_input,
                    consistency_score=consistency_score,
                    guardrail_config=effective_guardrail,
                    pre_rejected_reason_ids=pre_rejected,
                    selector_elapsed_ms=selector_elapsed_ms,
                )
                if llm_policy_result.allowed:
                    selected = _candidate_by_id(candidates, llm_policy_result.final_strategy_id) or top
                    reasoning_mode = "llm_assisted"
                    warnings.extend(llm_policy_result.policy_warning_ids)
                    _log_llm_policy_result(
                        event="creative_reasoning_llm_override_accepted",
                        analyzed_input=analyzed_input,
                        policy_result=llm_policy_result,
                    )
                else:
                    reasoning_mode = (
                        "rule_fallback_after_invalid_llm"
                        if "llm_selected_strategy_not_found" in llm_policy_result.rejected_reason_ids
                        or "llm_selector_returned_no_selection" in llm_policy_result.rejected_reason_ids
                        or "llm_selector_legacy_string_missing_confidence" in llm_policy_result.rejected_reason_ids
                        or "llm_selector_invalid_response_schema" in llm_policy_result.rejected_reason_ids
                        or "llm_selector_invalid_response_type" in llm_policy_result.rejected_reason_ids
                        else "rule_fallback_after_selector_timeout"
                        if "llm_selector_timeout" in llm_policy_result.rejected_reason_ids
                        else "rule_fallback_after_rejected_llm"
                    )
                    warnings.extend(llm_policy_result.rejected_reason_ids + llm_policy_result.policy_warning_ids)
                    _log_llm_policy_result(
                        event="creative_reasoning_llm_override_rejected",
                        analyzed_input=analyzed_input,
                        policy_result=llm_policy_result,
                    )
            except Exception as exc:  # pragma: no cover - defensive production guard
                llm_policy_result = LLMStrategyPolicyResult(
                    allowed=False,
                    requested_strategy_id=None,
                    final_strategy_id=top.strategy_id,
                    fallback_strategy_id=top.strategy_id,
                    rejected_reason_ids=["llm_selector_exception"],
                    guardrail_rule_ids=_llm_guardrail_rule_ids(),
                    rationale_summary=f"LLM selector failed safely: {type(exc).__name__}.",
                )
                reasoning_mode = "rule_fallback_after_selector_error"
                warnings.append("llm_selector_exception")
                LOGGER.exception(
                    "creative_reasoning_llm_selector_exception",
                    extra={
                        "analysis_id": getattr(analyzed_input, "analysis_id", None),
                        "fallback_strategy_id": top.strategy_id,
                        "exception_type": type(exc).__name__,
                    },
                )
        elif llm_recommended:
            reasoning_mode = "llm_recommended_no_selector"
            warnings.append("llm_tiebreak_recommended_but_no_selector_configured")
            llm_policy_result = LLMStrategyPolicyResult(
                allowed=False,
                requested_strategy_id=None,
                final_strategy_id=top.strategy_id,
                fallback_strategy_id=top.strategy_id,
                rejected_reason_ids=["llm_tiebreak_recommended_but_no_selector_configured"],
                guardrail_rule_ids=_llm_guardrail_rule_ids(),
                rationale_summary="No LLM selector was configured; deterministic top strategy was used.",
            )
            _log_llm_policy_result(
                event="creative_reasoning_llm_recommended_without_selector",
                analyzed_input=analyzed_input,
                policy_result=llm_policy_result,
            )

        risk_profile = _risk_profile(
            analyzed_input=analyzed_input,
            selected=selected,
            identity_bible=identity_bible,
            consistency_score=consistency_score,
        )
        rules_applied = _dedupe(
            ["phase6a.reasoning.rule_first_strategy_selection"]
            + selected.rules_applied
            + (consistency_score.rules_applied if consistency_score else [])
            + (llm_policy_result.guardrail_rule_ids if llm_policy_result else [])
        )
        score_gap = _score_gap(candidates)
        candidate_rankings = _candidate_rankings(candidates)
        return CreativeStrategyContract(
            analysis_id=analyzed_input.analysis_id,
            selected_strategy=selected,
            candidates=candidates,
            reasoning_mode=reasoning_mode,
            reasoning_summary=_summary(
                selected=selected,
                analyzed_input=analyzed_input,
                reasoning_mode=reasoning_mode,
                llm_reasons=llm_reasons,
                score_gap=score_gap,
                llm_policy_result=llm_policy_result,
            ),
            decision_factors={
                "detected_niche": analyzed_input.detected_niche,
                "intent": analyzed_input.intent,
                "duration_s": analyzed_input.duration_s,
                "asset_mode": selected.metadata.get("asset_mode"),
                "candidate_count": len(candidates),
                "candidate_rankings": candidate_rankings,
                "top_score_gap": score_gap,
                "llm_recommended": llm_recommended,
                "llm_reasons": llm_reasons,
                "llm_policy_result": (
                    llm_policy_result.model_dump(mode="json", exclude_none=True)
                    if llm_policy_result
                    else None
                ),
                "llm_guardrail_config": _effective_guardrail_config(
                    self.llm_guardrail_config,
                    analyzed_input=analyzed_input,
                ).model_dump(mode="json"),
                "consistency_overall_score": consistency_score.overall_score if consistency_score else None,
                "reference_sufficiency": analyzed_input.asset_summary.get("reference_sufficiency"),
            },
            evidence=_evidence(selected, analyzed_input, consistency_score, llm_policy_result),
            identity_requirements=_identity_requirements(analyzed_input, identity_bible),
            llm_policy_result=llm_policy_result,
            risk_profile=risk_profile,
            rules_applied=rules_applied,
            warnings=_dedupe(warnings + risk_profile.risk_flags),
            confidence_score=selected.confidence_score,
        )


def _evaluate_llm_override(
    *,
    selection: LLMStrategySelection | None,
    candidates: list[StrategyCandidate],
    fallback_candidate: StrategyCandidate,
    analyzed_input: Any,
    consistency_score: ConsistencyScore | None,
    guardrail_config: LLMGuardrailConfig,
    pre_rejected_reason_ids: list[str] | None = None,
    selector_elapsed_ms: float | None = None,
) -> LLMStrategyPolicyResult:
    requested_id = selection.selected_strategy_id if selection else None
    selected_candidate = _candidate_by_id(candidates, requested_id)
    selected_rank = _candidate_rank(candidates, requested_id)
    rejected: list[str] = list(pre_rejected_reason_ids or [])
    warnings: list[str] = []
    if selection is None:
        rejected.append("llm_selector_returned_no_selection")
    if selection and "llm_selector_legacy_string_missing_confidence" in selection.safety_warnings:
        rejected.append("llm_selector_legacy_string_missing_confidence")
    if selection and "llm_selector_rationale_truncated" in selection.safety_warnings:
        warnings.append("llm_selector_rationale_truncated")
    if selection and selection.confidence_score < guardrail_config.min_confidence:
        rejected.append("llm_confidence_below_threshold")
    if requested_id and selected_candidate is None:
        rejected.append("llm_selected_strategy_not_found")
    if selected_candidate and selected_rank and selected_rank > guardrail_config.top_n:
        rejected.append("llm_selected_strategy_outside_top_n")
    if selected_candidate and selected_candidate.risk_score > guardrail_config.max_candidate_risk:
        rejected.append("llm_selected_strategy_risk_too_high")
    if consistency_score and consistency_score.overall_score < guardrail_config.min_consistency_score:
        rejected.append("consistency_score_below_llm_override_floor")
    if selected_candidate and _has_missing_required_assets(selected_candidate, analyzed_input):
        rejected.append("llm_selected_strategy_missing_required_assets")
    allowed = not rejected and selected_candidate is not None and selection is not None
    return LLMStrategyPolicyResult(
        allowed=allowed,
        requested_strategy_id=requested_id,
        final_strategy_id=selected_candidate.strategy_id if allowed and selected_candidate else fallback_candidate.strategy_id,
        fallback_strategy_id=fallback_candidate.strategy_id,
        selector_confidence_score=selection.confidence_score if selection else None,
        selector_elapsed_ms=selector_elapsed_ms,
        selected_candidate_rank=selected_rank,
        rejected_reason_ids=_dedupe(rejected),
        policy_warning_ids=_dedupe(warnings),
        guardrail_rule_ids=_llm_guardrail_rule_ids(),
        rationale_summary=selection.rationale_summary if selection else "",
    )


def _log_llm_policy_result(
    *,
    event: str,
    analyzed_input: Any,
    policy_result: LLMStrategyPolicyResult,
) -> None:
    """Emit compact structured logs for LLM selector audit without raw reasoning text."""
    payload = {
        "analysis_id": getattr(analyzed_input, "analysis_id", None),
        "requested_strategy_id": policy_result.requested_strategy_id,
        "final_strategy_id": policy_result.final_strategy_id,
        "fallback_strategy_id": policy_result.fallback_strategy_id,
        "selector_confidence_score": policy_result.selector_confidence_score,
        "selected_candidate_rank": policy_result.selected_candidate_rank,
        "selector_elapsed_ms": policy_result.selector_elapsed_ms,
        "rejected_reason_ids": list(policy_result.rejected_reason_ids),
        "policy_warning_ids": list(policy_result.policy_warning_ids),
    }
    if policy_result.allowed:
        LOGGER.info(event, extra=payload)
    else:
        LOGGER.warning(event, extra=payload)


def _coerce_llm_selection(
    value: LLMStrategySelection | str | dict[str, Any] | None,
    *,
    guardrail_config: LLMGuardrailConfig,
) -> tuple[LLMStrategySelection | None, list[str]]:
    if value is None:
        return None, []
    if isinstance(value, LLMStrategySelection):
        return _sanitize_llm_selection(value, guardrail_config), []
    if isinstance(value, str):
        selected_id = value.strip()
        if not selected_id or len(selected_id) > 120:
            return None, ["llm_selector_invalid_response_schema"]
        return LLMStrategySelection(
            selected_strategy_id=selected_id,
            confidence_score=0.0,
            rationale_summary="Legacy string selector output has no confidence score.",
            safety_warnings=["llm_selector_legacy_string_missing_confidence"],
        ), []
    if isinstance(value, dict):
        try:
            selection = LLMStrategySelection.model_validate(value)
        except ValidationError:
            return None, ["llm_selector_invalid_response_schema"]
        return _sanitize_llm_selection(selection, guardrail_config), []
    return None, ["llm_selector_invalid_response_type"]


def _sanitize_llm_selection(
    selection: LLMStrategySelection,
    guardrail_config: LLMGuardrailConfig,
) -> LLMStrategySelection:
    """Bound selector text fields so audit logs never store raw long reasoning."""
    if len(selection.rationale_summary) <= guardrail_config.max_rationale_chars:
        return selection
    truncated = selection.rationale_summary[: guardrail_config.max_rationale_chars].rstrip()
    return selection.model_copy(update={
        "rationale_summary": truncated,
        "safety_warnings": _dedupe(selection.safety_warnings + ["llm_selector_rationale_truncated"]),
    })


def _effective_guardrail_config(
    config: LLMGuardrailConfig,
    *,
    analyzed_input: Any,
) -> LLMGuardrailConfig:
    data = config.model_dump(mode="json")
    niche = str(getattr(analyzed_input, "detected_niche", "") or "").lower()
    user_tier = str((getattr(analyzed_input, "metadata", {}) or {}).get("user_tier") or "").lower()
    for override in (
        config.niche_overrides.get(niche, {}),
        config.user_tier_overrides.get(user_tier, {}),
    ):
        for key, value in override.items():
            if key in {
                "min_confidence",
                "max_candidate_risk",
                "min_consistency_score",
                "top_n",
                "selector_timeout_s",
                "max_rationale_chars",
            }:
                data[key] = value
    data["niche_overrides"] = {}
    data["user_tier_overrides"] = {}
    return LLMGuardrailConfig.model_validate(data)


def _should_use_llm(
    *,
    analyzed_input: Any,
    candidates: list[StrategyCandidate],
    consistency_score: ConsistencyScore | None,
) -> tuple[bool, list[str]]:
    """Return whether an LLM selector should be used when available."""
    reasons: list[str] = []
    if "niche_uncertain" in analyzed_input.warnings or analyzed_input.detected_niche == "unknown":
        reasons.append("niche_uncertain")
    if len(candidates) > 1 and _score_gap(candidates) <= 0.07:
        reasons.append("strategy_scores_close")
    if consistency_score and consistency_score.overall_score < 68:
        reasons.append("low_consistency_score")
    if candidates[0].risk_score >= 0.55:
        reasons.append("top_strategy_high_risk")
    if int(analyzed_input.duration_s or 8) >= 12 and len(candidates[0].narrative_structure) >= 3:
        if candidates[0].risk_score >= 0.42:
            reasons.append("longer_clip_with_multi_beat_risk")
    return bool(reasons), reasons


def _risk_profile(
    *,
    analyzed_input: Any,
    selected: StrategyCandidate,
    identity_bible: IdentityBibleBundle | None,
    consistency_score: ConsistencyScore | None,
) -> CreativeRiskProfile:
    flags: list[str] = []
    identity_risk = 0.0
    product_risk = 0.0
    style_risk = 0.0
    if consistency_score:
        identity_risk = max(0.0, (100.0 - consistency_score.character_score) / 100.0)
        product_risk = max(0.0, (100.0 - consistency_score.product_score) / 100.0)
        style_risk = max(0.0, (100.0 - consistency_score.style_score) / 100.0)
        flags.extend(consistency_score.risk_flags)
    if identity_bible and identity_bible.character.risk_level == "high":
        flags.append("character_identity_high_risk")
    if identity_bible and identity_bible.product.risk_level == "high":
        flags.append("product_identity_high_risk")
    duration_s = int(analyzed_input.duration_s or 8)
    duration_risk = 0.2 if duration_s <= 8 else 0.42 if duration_s <= 12 else 0.58
    prompt_overload = min(1.0, 0.14 * max(0, len(selected.narrative_structure) - 1))
    reference_sufficiency = str(analyzed_input.asset_summary.get("reference_sufficiency") or "")
    reference_risk = {"sufficient": 0.08, "partial": 0.34, "insufficient": 0.68}.get(reference_sufficiency, 0.3)
    return CreativeRiskProfile(
        identity_drift_risk=round(identity_risk, 3),
        product_drift_risk=round(product_risk, 3),
        style_drift_risk=round(style_risk, 3),
        duration_complexity_risk=round(duration_risk, 3),
        reference_sufficiency_risk=round(reference_risk, 3),
        prompt_overload_risk=round(prompt_overload, 3),
        risk_flags=_dedupe(flags + selected.rejection_reasons),
    )


def _identity_requirements(
    analyzed_input: Any,
    identity_bible: IdentityBibleBundle | None,
) -> dict[str, object]:
    summary = analyzed_input.asset_summary
    return {
        "needs_character_anchor": bool(summary.get("needs_character_anchor")),
        "needs_product_anchor": bool(summary.get("needs_product_anchor")),
        "style_lock": True,
        "character_anchor_asset_ids": identity_bible.character.anchor_asset_ids if identity_bible else [],
        "product_anchor_asset_ids": identity_bible.product.anchor_asset_ids if identity_bible else [],
        "style_bible_id": identity_bible.style.style_id if identity_bible else None,
    }


def _summary(
    *,
    selected: StrategyCandidate,
    analyzed_input: Any,
    reasoning_mode: str,
    llm_reasons: list[str],
    score_gap: float,
    llm_policy_result: LLMStrategyPolicyResult | None,
) -> str:
    reason = f"Selected {selected.name} for niche={analyzed_input.detected_niche}, intent={analyzed_input.intent}."
    if reasoning_mode == "rule_only":
        return f"{reason} Top candidate was clear with score gap {score_gap:.2f}."
    if reasoning_mode == "llm_assisted":
        return f"{reason} Guarded LLM selector was accepted because: {', '.join(llm_reasons)}."
    if reasoning_mode == "llm_recommended_no_selector":
        return f"{reason} LLM tie-break was recommended but no selector was configured; deterministic top score was used."
    if llm_policy_result:
        rejected = ", ".join(llm_policy_result.rejected_reason_ids) or "unknown"
        return f"{reason} LLM override was rejected by guardrails: {rejected}."
    return f"{reason} Deterministic fallback was used after LLM selector failure."


def _evidence(
    selected: StrategyCandidate,
    analyzed_input: Any,
    consistency_score: ConsistencyScore | None,
    llm_policy_result: LLMStrategyPolicyResult | None,
) -> list[str]:
    evidence = [
        f"strategy_score={selected.selection_score}",
        f"strategy_risk={selected.risk_score}",
        f"niche={analyzed_input.detected_niche}",
        f"intent={analyzed_input.intent}",
        f"asset_mode={selected.metadata.get('asset_mode')}",
    ]
    if consistency_score:
        evidence.append(f"consistency_score={consistency_score.overall_score}")
    if llm_policy_result:
        evidence.append(f"llm_guardrail_allowed={llm_policy_result.allowed}")
    return evidence


def _candidate_rankings(candidates: list[StrategyCandidate]) -> list[dict[str, object]]:
    return [
        {
            "rank": index + 1,
            "strategy_id": candidate.strategy_id,
            "fit_score": candidate.fit_score,
            "risk_score": candidate.risk_score,
            "selection_score": candidate.selection_score,
            "confidence_score": candidate.confidence_score,
        }
        for index, candidate in enumerate(candidates)
    ]


def _candidate_by_id(candidates: list[StrategyCandidate], strategy_id: str | None) -> StrategyCandidate | None:
    if not strategy_id:
        return None
    for candidate in candidates:
        if candidate.strategy_id == strategy_id:
            return candidate
    return None


def _candidate_rank(candidates: list[StrategyCandidate], strategy_id: str | None) -> int | None:
    if not strategy_id:
        return None
    for index, candidate in enumerate(candidates):
        if candidate.strategy_id == strategy_id:
            return index + 1
    return None


def _has_missing_required_assets(candidate: StrategyCandidate, analyzed_input: Any) -> bool:
    required = set(candidate.required_assets)
    summary = analyzed_input.asset_summary
    return (
        ("character_anchor" in required and not summary.get("has_character_anchor"))
        or ("product_hero" in required and not summary.get("has_product_anchor"))
    )


def _score_gap(candidates: list[StrategyCandidate]) -> float:
    if len(candidates) < 2:
        return 1.0
    return round(candidates[0].selection_score - candidates[1].selection_score, 3)


def _llm_guardrail_rule_ids() -> list[str]:
    return [
        "phase6a.llm_guardrail.top_n_only",
        "phase6a.llm_guardrail.min_confidence",
        "phase6a.llm_guardrail.max_candidate_risk",
        "phase6a.llm_guardrail.min_consistency_score",
        "phase6a.llm_guardrail.required_assets_present",
        "phase6a.llm_guardrail.selector_timeout",
        "phase6a.llm_guardrail.valid_selector_schema",
        "phase6a.llm_guardrail.bounded_rationale_summary",
    ]


def _validate_analyzed_input(analyzed_input: Any) -> None:
    required = ["analysis_id", "detected_niche", "intent", "duration_s", "asset_summary", "warnings"]
    missing = [field for field in required if not hasattr(analyzed_input, field)]
    if missing:
        raise TypeError(f"analyzed_input is missing required fields: {', '.join(missing)}")
    if not isinstance(analyzed_input.asset_summary, dict):
        raise TypeError("analyzed_input.asset_summary must be a dict")
    if not isinstance(analyzed_input.warnings, list):
        raise TypeError("analyzed_input.warnings must be a list")


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value).strip()))


__all__ = ["CreativeReasoningEngine", "LLMStrategySelector"]
