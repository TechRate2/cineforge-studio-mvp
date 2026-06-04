"""Phase 6A tests for Creative Reasoning Engine MVP."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_creative_reasoning_selects_product_proof_for_beauty_ad() -> None:
    """Beauty/product ads should prefer a product-proof strategy with clear evidence."""
    from agent.creative_reasoning_engine import CreativeReasoningEngine
    from identity.consistency_scorer import ConsistencyScorer
    from identity.identity_bible import IdentityBibleBuilder
    from pipeline.contracts import AssetRef, InputContract, ReferenceRole
    from pipeline.input_analysis import InputAnalyzer

    analyzed = InputAnalyzer().analyze(InputContract(
        user_idea="Create a 15s beauty serum ad with macro texture hook, hero product reveal, and payoff.",
        duration_hint_s=15,
        assets=[
            AssetRef(
                kind="image",
                tag="@Image1",
                role=ReferenceRole.PRODUCT_HERO,
                notes="serum product bottle packaging label product hero",
            )
        ],
    ))
    bible = IdentityBibleBuilder().build(analyzed)
    consistency = ConsistencyScorer().score(analyzed_input=analyzed, identity_bible=bible)
    strategy = CreativeReasoningEngine().select_strategy(
        analyzed_input=analyzed,
        identity_bible=bible,
        consistency_score=consistency,
    )

    assert strategy.selected_strategy.strategy_id == "product_proof_reveal"
    assert strategy.reasoning_mode == "rule_only"
    assert strategy.decision_factors["llm_recommended"] is False
    assert strategy.decision_factors["candidate_count"] >= 3
    assert strategy.identity_requirements["needs_product_anchor"] is True
    assert any(item.startswith("strategy_score=") for item in strategy.evidence)


def test_creative_reasoning_marks_uncertain_niche_as_llm_recommended_without_selector() -> None:
    """MVP should be deterministic but explicit when an LLM tie-break would help."""
    from agent.creative_reasoning_engine import CreativeReasoningEngine
    from identity.consistency_scorer import ConsistencyScorer
    from identity.identity_bible import IdentityBibleBuilder
    from pipeline.contracts import InputContract
    from pipeline.input_analysis import InputAnalyzer

    analyzed = InputAnalyzer().analyze(InputContract(
        user_idea="Create a 12s education science explainer with concept setup, cause effect, and final learning frame.",
        duration_hint_s=12,
    ))
    bible = IdentityBibleBuilder().build(analyzed)
    consistency = ConsistencyScorer().score(analyzed_input=analyzed, identity_bible=bible)
    strategy = CreativeReasoningEngine().select_strategy(
        analyzed_input=analyzed,
        identity_bible=bible,
        consistency_score=consistency,
    )

    assert analyzed.detected_niche == "unknown"
    assert strategy.selected_strategy.strategy_id == "educational_cause_effect"
    assert strategy.reasoning_mode == "llm_recommended_no_selector"
    assert "niche_uncertain" in strategy.decision_factors["llm_reasons"]
    assert strategy.llm_policy_result is not None
    assert strategy.llm_policy_result.allowed is False
    assert "raw_chain_of_thought" not in strategy.model_dump(mode="json")


def test_creative_reasoning_rejects_invalid_llm_strategy_id() -> None:
    """Invalid LLM strategy ids should fall back to deterministic top strategy."""
    from agent.creative_reasoning_engine import CreativeReasoningEngine
    from agent.creative_strategy_contracts import LLMStrategySelection
    from identity.consistency_scorer import ConsistencyScorer
    from identity.identity_bible import IdentityBibleBuilder
    from pipeline.contracts import InputContract
    from pipeline.input_analysis import InputAnalyzer

    analyzed = InputAnalyzer().analyze(InputContract(
        user_idea="Create a 12s education science explainer with concept setup and final learning frame.",
        duration_hint_s=12,
    ))
    bible = IdentityBibleBuilder().build(analyzed)
    consistency = ConsistencyScorer().score(analyzed_input=analyzed, identity_bible=bible)

    def invalid_selector(*args: object, **kwargs: object) -> LLMStrategySelection:
        return LLMStrategySelection(
            selected_strategy_id="not_a_real_strategy",
            confidence_score=0.95,
            rationale_summary="Invalid selector output for guardrail test.",
        )

    strategy = CreativeReasoningEngine(llm_selector=invalid_selector).select_strategy(
        analyzed_input=analyzed,
        identity_bible=bible,
        consistency_score=consistency,
    )

    assert strategy.reasoning_mode == "rule_fallback_after_invalid_llm"
    assert strategy.selected_strategy.strategy_id == "educational_cause_effect"
    assert strategy.llm_policy_result is not None
    assert strategy.llm_policy_result.allowed is False
    assert "llm_selected_strategy_not_found" in strategy.llm_policy_result.rejected_reason_ids


def test_creative_reasoning_rejects_llm_override_missing_required_assets() -> None:
    """LLM cannot override to a strategy whose required anchors are absent."""
    from agent.creative_reasoning_engine import CreativeReasoningEngine
    from agent.creative_strategy_contracts import LLMStrategySelection
    from identity.consistency_scorer import ConsistencyScorer
    from identity.identity_bible import IdentityBibleBuilder
    from pipeline.contracts import InputContract
    from pipeline.input_analysis import InputAnalyzer

    analyzed = InputAnalyzer().analyze(InputContract(
        user_idea="Create a 12s education science explainer with concept setup and final learning frame.",
        duration_hint_s=12,
    ))
    bible = IdentityBibleBuilder().build(analyzed)
    consistency = ConsistencyScorer().score(analyzed_input=analyzed, identity_bible=bible)

    def unsafe_selector(*args: object, **kwargs: object) -> LLMStrategySelection:
        return LLMStrategySelection(
            selected_strategy_id="product_proof_reveal",
            confidence_score=0.95,
            rationale_summary="Tries to force product proof without product reference.",
        )

    strategy = CreativeReasoningEngine(llm_selector=unsafe_selector).select_strategy(
        analyzed_input=analyzed,
        identity_bible=bible,
        consistency_score=consistency,
    )

    assert strategy.reasoning_mode == "rule_fallback_after_rejected_llm"
    assert strategy.selected_strategy.strategy_id == "educational_cause_effect"
    assert strategy.llm_policy_result is not None
    assert "llm_selected_strategy_missing_required_assets" in strategy.llm_policy_result.rejected_reason_ids


def test_creative_reasoning_rejects_invalid_llm_response_schema() -> None:
    """Malformed selector payloads should produce a specific guardrail reason."""
    from agent.creative_reasoning_engine import CreativeReasoningEngine
    from identity.consistency_scorer import ConsistencyScorer
    from identity.identity_bible import IdentityBibleBuilder
    from pipeline.contracts import InputContract
    from pipeline.input_analysis import InputAnalyzer

    analyzed = InputAnalyzer().analyze(InputContract(
        user_idea="Create a 12s education science explainer with concept setup and final learning frame.",
        duration_hint_s=12,
    ))
    bible = IdentityBibleBuilder().build(analyzed)
    consistency = ConsistencyScorer().score(analyzed_input=analyzed, identity_bible=bible)

    def invalid_selector(*args: object, **kwargs: object) -> dict[str, object]:
        return {"selected_strategy_id": "", "confidence_score": 1.2}

    strategy = CreativeReasoningEngine(llm_selector=invalid_selector).select_strategy(
        analyzed_input=analyzed,
        identity_bible=bible,
        consistency_score=consistency,
    )

    assert strategy.reasoning_mode == "rule_fallback_after_invalid_llm"
    assert strategy.llm_policy_result is not None
    assert "llm_selector_invalid_response_schema" in strategy.llm_policy_result.rejected_reason_ids


def test_creative_reasoning_rejects_slow_llm_selector() -> None:
    """Slow selector responses should be rejected even if their strategy id is valid."""
    from agent.creative_reasoning_engine import CreativeReasoningEngine
    from agent.creative_strategy_contracts import LLMGuardrailConfig, LLMStrategySelection
    from identity.consistency_scorer import ConsistencyScorer
    from identity.identity_bible import IdentityBibleBuilder
    from pipeline.contracts import InputContract
    from pipeline.input_analysis import InputAnalyzer

    analyzed = InputAnalyzer().analyze(InputContract(
        user_idea="Create a 12s education science explainer with concept setup and final learning frame.",
        duration_hint_s=12,
    ))
    bible = IdentityBibleBuilder().build(analyzed)
    consistency = ConsistencyScorer().score(analyzed_input=analyzed, identity_bible=bible)

    def slow_selector(*args: object, **kwargs: object) -> LLMStrategySelection:
        time.sleep(0.02)
        return LLMStrategySelection(
            selected_strategy_id="hook_first_cinematic_reveal",
            confidence_score=0.95,
            rationale_summary="Valid but too slow for the configured selector budget.",
        )

    strategy = CreativeReasoningEngine(
        llm_selector=slow_selector,
        llm_guardrail_config=LLMGuardrailConfig(selector_timeout_s=0.1),
    ).select_strategy(
        analyzed_input=analyzed,
        identity_bible=bible,
        consistency_score=consistency,
    )

    assert strategy.reasoning_mode == "llm_assisted"
    strategy = CreativeReasoningEngine(
        llm_selector=slow_selector,
        llm_guardrail_config=LLMGuardrailConfig(selector_timeout_s=0.001),
    ).select_strategy(
        analyzed_input=analyzed,
        identity_bible=bible,
        consistency_score=consistency,
    )

    assert strategy.reasoning_mode == "rule_fallback_after_selector_timeout"
    assert strategy.llm_policy_result is not None
    assert "llm_selector_timeout" in strategy.llm_policy_result.rejected_reason_ids
    assert strategy.llm_policy_result.selector_elapsed_ms is not None


def test_creative_reasoning_truncates_long_llm_rationale_without_storing_raw_cot() -> None:
    """Long selector rationales should be bounded before they enter traceable contracts."""
    from agent.creative_reasoning_engine import CreativeReasoningEngine
    from agent.creative_strategy_contracts import LLMGuardrailConfig, LLMStrategySelection
    from identity.consistency_scorer import ConsistencyScorer
    from identity.identity_bible import IdentityBibleBuilder
    from pipeline.contracts import InputContract
    from pipeline.input_analysis import InputAnalyzer

    analyzed = InputAnalyzer().analyze(InputContract(
        user_idea="Create a 12s education science explainer with concept setup and final learning frame.",
        duration_hint_s=12,
    ))
    bible = IdentityBibleBuilder().build(analyzed)
    consistency = ConsistencyScorer().score(analyzed_input=analyzed, identity_bible=bible)

    def verbose_selector(*args: object, **kwargs: object) -> LLMStrategySelection:
        return LLMStrategySelection(
            selected_strategy_id="hook_first_cinematic_reveal",
            confidence_score=0.95,
            rationale_summary="x" * 1000,
        )

    strategy = CreativeReasoningEngine(
        llm_selector=verbose_selector,
        llm_guardrail_config=LLMGuardrailConfig(max_rationale_chars=120),
    ).select_strategy(
        analyzed_input=analyzed,
        identity_bible=bible,
        consistency_score=consistency,
    )

    assert strategy.llm_policy_result is not None
    assert strategy.llm_policy_result.allowed is True
    assert len(strategy.llm_policy_result.rationale_summary) == 120
    assert "llm_selector_rationale_truncated" in strategy.llm_policy_result.policy_warning_ids


def test_creative_reasoning_allows_configured_niche_guardrail_override() -> None:
    """LLM thresholds should be configurable by niche without changing code constants."""
    from agent.creative_reasoning_engine import CreativeReasoningEngine
    from agent.creative_strategy_contracts import LLMGuardrailConfig, LLMStrategySelection
    from identity.consistency_scorer import ConsistencyScorer
    from identity.identity_bible import IdentityBibleBuilder
    from pipeline.contracts import InputContract
    from pipeline.input_analysis import InputAnalyzer

    analyzed = InputAnalyzer().analyze(InputContract(
        user_idea="Create a 12s education science explainer with concept setup and final learning frame.",
        duration_hint_s=12,
    ))
    bible = IdentityBibleBuilder().build(analyzed)
    consistency = ConsistencyScorer().score(analyzed_input=analyzed, identity_bible=bible)

    def selector(*args: object, **kwargs: object) -> LLMStrategySelection:
        return LLMStrategySelection(
            selected_strategy_id="hook_first_cinematic_reveal",
            confidence_score=0.62,
            rationale_summary="Configured niche override accepts a close safe cinematic option.",
        )

    strategy = CreativeReasoningEngine(
        llm_selector=selector,
        llm_guardrail_config=LLMGuardrailConfig(
            niche_overrides={
                "unknown": {
                    "min_confidence": 0.60,
                    "max_candidate_risk": 0.70,
                    "min_consistency_score": 60,
                    "top_n": 3,
                }
            }
        ),
    ).select_strategy(
        analyzed_input=analyzed,
        identity_bible=bible,
        consistency_score=consistency,
    )

    assert strategy.reasoning_mode == "llm_assisted"
    assert strategy.selected_strategy.strategy_id == "hook_first_cinematic_reveal"
    assert strategy.llm_policy_result is not None
    assert strategy.llm_policy_result.allowed is True
    assert strategy.decision_factors["llm_guardrail_config"]["min_confidence"] == 0.60


def test_llm_guardrail_config_rejects_unknown_override_keys() -> None:
    """Dynamic guardrail config should fail fast when an override cannot be enforced."""
    from agent.creative_strategy_contracts import LLMGuardrailConfig

    with pytest.raises(ValueError, match="unsupported keys"):
        LLMGuardrailConfig(niche_overrides={"beauty": {"unknown_threshold": 0.5}})


def test_creative_strategy_engine_uses_built_in_fallback_when_playbook_is_malformed(tmp_path: Path) -> None:
    """Malformed playbooks should not produce an empty strategy list in production."""
    from agent.creative_strategy_engine import CreativeStrategyEngine
    from pipeline.contracts import InputContract
    from pipeline.input_analysis import InputAnalyzer

    malformed_path = tmp_path / "bad_playbook.jsonl"
    malformed_path.write_text("{not valid json}\n{}\n", encoding="utf-8")
    analyzed = InputAnalyzer().analyze(InputContract(
        user_idea="Create an 8s cinematic sunrise shot.",
        duration_hint_s=8,
    ))

    candidates = CreativeStrategyEngine(playbook_path=malformed_path).generate_candidates(
        analyzed_input=analyzed,
    )

    assert candidates
    assert candidates[0].strategy_id == "fallback_cinematic_single_unit"
    assert candidates[0].metadata["playbook_source"] == "built_in_fallback"


def test_creative_planner_embeds_strategy_and_consistency_metadata() -> None:
    """CreativePlanner should expose 6A/7A output through existing CreativePlan metadata."""
    from pipeline.contracts import AssetRef, InputContract, ReferenceRole
    from pipeline.creative_planning import CreativePlanner
    from pipeline.input_analysis import InputAnalyzer

    analyzed = InputAnalyzer().analyze(InputContract(
        user_idea="Create a 12s drama scene with the same woman character, emotional reveal, and consistent clothing.",
        duration_hint_s=12,
        assets=[
            AssetRef(kind="image", tag="@Image1", role=ReferenceRole.CHARACTER_ANCHOR, notes="woman face close-up portrait"),
            AssetRef(kind="image", tag="@Image2", role=ReferenceRole.CHARACTER_ANCHOR, notes="woman full-body outfit silhouette"),
        ],
    ))
    plan = CreativePlanner().plan(analyzed)

    assert plan.metadata["creative_strategy"]["selected_strategy"]["strategy_id"] == "emotion_arc_micro_story"
    assert plan.metadata["identity_bible"]["character"]["required"] is True
    assert plan.metadata["consistency_score"]["overall_score"] >= 80
    assert "baseline_consistency_score" in plan.metadata
    assert "strategy_adjusted_consistency_score" in plan.metadata
    assert isinstance(plan.metadata["consistency_delta"], float)
    assert plan.metadata["consistency_policy"]["action"] in {"allow", "warn", "requires_review", "block"}
    assert "phase6a.reasoning.rule_first_strategy_selection" in plan.metadata["planning_rules"]
    assert "phase7a.consistency.pre_render_score" in plan.metadata["planning_rules"]
