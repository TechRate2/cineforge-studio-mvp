"""Rule-based consistency scoring for Phase 7A MVP."""
from __future__ import annotations

from typing import Any

from agent.creative_strategy_contracts import StrategyCandidate
from identity.identity_contracts import ConsistencyPolicyResult, ConsistencyScore, IdentityBibleBundle


class ConsistencyScorer:
    """Compute a pre-render consistency score from assets, bible, and strategy."""

    def score(
        self,
        *,
        analyzed_input: Any,
        identity_bible: IdentityBibleBundle,
        strategy: StrategyCandidate | None = None,
    ) -> ConsistencyScore:
        """Return a deterministic 0-100 consistency score for MVP gating."""
        character_score, character_flags = _character_score(identity_bible)
        product_score, product_flags = _product_score(identity_bible)
        style_score, style_flags = _style_score(analyzed_input, identity_bible, strategy)
        emotion_score, emotion_flags = _emotion_score(identity_bible, strategy)
        reference_score, reference_flags = _reference_sufficiency_score(analyzed_input, identity_bible)
        weights = _weights(identity_bible)
        overall = (
            character_score * weights["character"]
            + product_score * weights["product"]
            + style_score * weights["style"]
            + emotion_score * weights["emotion"]
            + reference_score * weights["reference"]
        )
        risk_flags = list(dict.fromkeys(
            character_flags + product_flags + style_flags + emotion_flags + reference_flags
        ))
        return ConsistencyScore(
            overall_score=round(overall, 2),
            character_score=round(character_score, 2),
            product_score=round(product_score, 2),
            style_score=round(style_score, 2),
            emotion_score=round(emotion_score, 2),
            reference_sufficiency_score=round(reference_score, 2),
            risk_flags=risk_flags,
            rules_applied=[
                "phase7a.consistency.character_anchor_score",
                "phase7a.consistency.product_anchor_score",
                "phase7a.consistency.style_score",
                "phase7a.consistency.reference_sufficiency_score",
            ],
            metadata={
                "phase": "7a",
                "strategy_id": strategy.strategy_id if strategy else None,
                "detected_niche": analyzed_input.detected_niche,
            },
        )

    def evaluate_policy(self, score: ConsistencyScore) -> ConsistencyPolicyResult:
        """Convert a score into an actionable consistency policy."""
        blocking: list[str] = []
        warning: list[str] = []
        if score.overall_score < 45:
            blocking.append("consistency_score_below_block_threshold")
        if "invalid_identity_bible" in score.risk_flags:
            blocking.append("invalid_identity_bible")
        if score.overall_score < 68:
            warning.append("consistency_score_below_review_threshold")
        if any(flag.startswith("missing_") for flag in score.risk_flags):
            warning.append("missing_required_consistency_anchor")
        if "partial_reference_sufficiency" in score.risk_flags:
            warning.append("partial_reference_sufficiency")
        if blocking:
            action = "block"
            threshold = 45.0
        elif warning and score.overall_score < 68:
            action = "requires_review"
            threshold = 68.0
        elif warning or score.overall_score < 82:
            action = "warn"
            threshold = 82.0
        else:
            action = "allow"
            threshold = 82.0
        return ConsistencyPolicyResult(
            action=action,
            score_id=score.score_id,
            overall_score=score.overall_score,
            threshold=threshold,
            reason_ids=list(dict.fromkeys(blocking + warning)),
            blocking_reason_ids=list(dict.fromkeys(blocking)),
            warning_reason_ids=list(dict.fromkeys(warning)),
            rules_applied=[
                "phase7a.consistency_policy.block_below_45",
                "phase7a.consistency_policy.review_below_68",
                "phase7a.consistency_policy.warn_below_82",
                "phase7a.consistency_policy.required_anchor_review",
            ],
        )


def _character_score(identity_bible: IdentityBibleBundle) -> tuple[float, list[str]]:
    bible = identity_bible.character
    if not bible.required:
        return 100.0, []
    flags = list(bible.warnings)
    if bible.face_anchor_asset_id and bible.full_body_anchor_asset_id:
        return 92.0, flags
    if bible.anchor_asset_ids:
        return 66.0, flags or ["partial_character_anchor"]
    return 35.0, flags or ["missing_character_anchor"]


def _product_score(identity_bible: IdentityBibleBundle) -> tuple[float, list[str]]:
    bible = identity_bible.product
    if not bible.required:
        return 100.0, []
    flags = list(bible.warnings)
    if bible.hero_anchor_asset_id and (bible.detail_anchor_asset_id or bible.package_shape):
        return 90.0, flags
    if bible.anchor_asset_ids:
        return 72.0, flags or ["partial_product_anchor"]
    return 38.0, flags or ["missing_product_anchor"]


def _style_score(
    analyzed_input: Any,
    identity_bible: IdentityBibleBundle,
    strategy: StrategyCandidate | None,
) -> tuple[float, list[str]]:
    flags: list[str] = []
    score = 82.0
    if analyzed_input.detected_niche == "unknown":
        score -= 10.0
        flags.append("style_niche_uncertain")
    if not identity_bible.style.visual_style:
        score -= 12.0
        flags.append("missing_style_bible")
    if strategy and strategy.style_direction and identity_bible.style.visual_style:
        strategy_style = strategy.style_direction.lower()
        bible_style = identity_bible.style.visual_style.lower()
        if not any(token in strategy_style for token in bible_style.split()[:2]):
            score -= 4.0
    return max(0.0, score), flags


def _emotion_score(
    identity_bible: IdentityBibleBundle,
    strategy: StrategyCandidate | None,
) -> tuple[float, list[str]]:
    if not identity_bible.emotion.required:
        return 100.0, []
    flags: list[str] = []
    score = 78.0
    if not identity_bible.emotion.allowed_transitions:
        score -= 18.0
        flags.append("missing_emotion_transition")
    if strategy and strategy.strategy_type in {"emotion_arc", "story_driven"}:
        score += 8.0
    return min(100.0, max(0.0, score)), flags


def _reference_sufficiency_score(
    analyzed_input: Any,
    identity_bible: IdentityBibleBundle,
) -> tuple[float, list[str]]:
    sufficiency = str(analyzed_input.asset_summary.get("reference_sufficiency") or "unknown")
    if sufficiency == "sufficient":
        return 92.0, []
    if sufficiency == "partial":
        return 68.0, ["partial_reference_sufficiency"]
    if not (identity_bible.character.required or identity_bible.product.required):
        return 88.0, []
    return 42.0, ["insufficient_reference_sufficiency"]


def _weights(identity_bible: IdentityBibleBundle) -> dict[str, float]:
    if identity_bible.character.required and identity_bible.product.required:
        return {"character": 0.26, "product": 0.26, "style": 0.18, "emotion": 0.1, "reference": 0.2}
    if identity_bible.character.required:
        return {"character": 0.36, "product": 0.1, "style": 0.2, "emotion": 0.14, "reference": 0.2}
    if identity_bible.product.required:
        return {"character": 0.1, "product": 0.38, "style": 0.2, "emotion": 0.08, "reference": 0.24}
    return {"character": 0.1, "product": 0.1, "style": 0.36, "emotion": 0.14, "reference": 0.3}


__all__ = ["ConsistencyScorer"]
