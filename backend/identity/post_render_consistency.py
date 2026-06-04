"""Post-render visual consistency evaluation.

This layer is deterministic and probe-agnostic. Today it consumes `qa_signals`
from a vendor or test client; later the same evaluator can consume signals from
face, product, logo/OCR, style, and emotion CV probes without changing
RenderQAService.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


PostRenderConsistencyAction = Literal["allow", "warn", "requires_review", "block"]
PostRenderRiskLevel = Literal["low", "medium", "high", "critical", "unknown"]


class ConsistencySignalThreshold(BaseModel):
    """Review/block thresholds for one 0-1 consistency signal."""

    model_config = ConfigDict(extra="forbid")

    review: float = Field(..., ge=0.0, le=1.0)
    block: float | None = Field(None, ge=0.0, le=1.0)
    warn: float | None = Field(None, ge=0.0, le=1.0)
    missing_action: PostRenderConsistencyAction = "requires_review"


class PostRenderConsistencyThresholds(BaseModel):
    """Thresholds grouped by character, product, style, and emotion locks."""

    model_config = ConfigDict(extra="forbid")

    face_similarity: ConsistencySignalThreshold = Field(
        default_factory=lambda: ConsistencySignalThreshold(warn=0.78, review=0.72, block=0.55)
    )
    product_visibility: ConsistencySignalThreshold = Field(
        default_factory=lambda: ConsistencySignalThreshold(warn=0.68, review=0.60, block=0.45)
    )
    logo_label_similarity: ConsistencySignalThreshold = Field(
        default_factory=lambda: ConsistencySignalThreshold(warn=0.65, review=0.58, block=None)
    )
    style_similarity: ConsistencySignalThreshold = Field(
        default_factory=lambda: ConsistencySignalThreshold(warn=0.68, review=0.62, block=0.45, missing_action="warn")
    )
    emotion_similarity: ConsistencySignalThreshold = Field(
        default_factory=lambda: ConsistencySignalThreshold(warn=0.62, review=0.55, block=None, missing_action="warn")
    )


class VisualConsistencyQAReport(BaseModel):
    """Post-render consistency result for one rendered segment."""

    model_config = ConfigDict(extra="forbid")

    status: str
    action: PostRenderConsistencyAction = "allow"
    risk_level: PostRenderRiskLevel = "unknown"
    overall_score: float | None = Field(None, ge=0.0, le=100.0)
    signal_source: str = "missing"
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    required_checks: list[str] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    thresholds: dict[str, Any] = Field(default_factory=dict)
    signal_actions: dict[str, PostRenderConsistencyAction] = Field(default_factory=dict)
    rules_applied: list[str] = Field(default_factory=list)


class PostRenderConsistencyEvaluator:
    """Evaluate post-render visual consistency signals into score and action."""

    def __init__(self, *, thresholds: PostRenderConsistencyThresholds | None = None) -> None:
        self.thresholds = thresholds or PostRenderConsistencyThresholds()

    def evaluate(
        self,
        *,
        shot_metadata: dict[str, Any],
        qa_signals: dict[str, Any] | None,
    ) -> VisualConsistencyQAReport:
        """Return deterministic consistency score, warnings, errors, and action."""
        required_checks = _required_checks(shot_metadata)
        signal_payload = qa_signals if isinstance(qa_signals, dict) else {}
        metrics = _extract_metrics(signal_payload)
        warnings: list[str] = []
        errors: list[str] = []
        missing: list[str] = []
        signal_actions: dict[str, PostRenderConsistencyAction] = {}

        if qa_signals is not None and not isinstance(qa_signals, dict):
            warnings.append("qa_signals_invalid_payload")

        for check in required_checks:
            metric_name = _metric_name_for_check(check)
            threshold = _threshold_for_metric(self.thresholds, metric_name)
            value = metrics.get(metric_name)
            if value is None:
                missing.append(metric_name)
                warnings.append(f"missing_{metric_name}")
                signal_actions[metric_name] = threshold.missing_action
                continue
            signal_action = _action_for_metric(value=value, threshold=threshold)
            signal_actions[metric_name] = signal_action
            if signal_action == "block":
                errors.append(f"{metric_name}_below_threshold")
            elif signal_action == "requires_review":
                warnings.append(f"{metric_name}_requires_review")
            elif signal_action == "warn":
                warnings.append(f"{metric_name}_low")

        overall_score = _overall_score(required_checks, metrics)
        action = _aggregate_action(signal_actions.values())
        if action == "allow" and warnings:
            action = "warn"
        risk_level = _risk_level(action=action, overall_score=overall_score, missing_signals=missing)
        status = "fail" if action == "block" or errors else ("warn" if action in {"warn", "requires_review"} or warnings else "pass")

        return VisualConsistencyQAReport(
            status=status,
            action=action,
            risk_level=risk_level,
            overall_score=overall_score,
            signal_source=_signal_source(signal_payload, metrics),
            warnings=list(dict.fromkeys(warnings)),
            errors=list(dict.fromkeys(errors)),
            metrics=metrics,
            required_checks=required_checks,
            missing_signals=missing,
            thresholds=self.thresholds.model_dump(mode="json"),
            signal_actions=signal_actions,
            rules_applied=[
                "post_render_consistency.signal_thresholds",
                "post_render_consistency.overall_score",
                "post_render_consistency.policy_action",
                "post_render_consistency.missing_signal_guardrail",
            ],
        )


class PostRenderConsistencyQA(PostRenderConsistencyEvaluator):
    """Backward-compatible facade used by existing render QA code."""


def _required_checks(metadata: dict[str, Any]) -> list[str]:
    checks: list[str] = []
    if metadata.get("needs_identity_consistency") or _policy_reason_contains(metadata, "character"):
        checks.append("character_identity")
    if metadata.get("needs_product_consistency") or _policy_reason_contains(metadata, "product"):
        checks.append("product_identity")
        checks.append("logo_label")
    if metadata.get("needs_style_consistency") or metadata.get("creative_strategy_id") or metadata.get("consistency_score") is not None:
        checks.append("style")
    if metadata.get("needs_emotion_consistency") or "emotion" in str(metadata.get("consistency_policy_reasons") or ""):
        checks.append("emotion")
    return list(dict.fromkeys(checks))


def _policy_reason_contains(metadata: dict[str, Any], needle: str) -> bool:
    text = " ".join(str(item) for item in metadata.get("consistency_policy_reasons") or [])
    text += " " + " ".join(str(item) for item in metadata.get("consistency_risk_flags") or [])
    return needle in text.lower()


def _metric_name_for_check(check: str) -> str:
    return {
        "character_identity": "face_similarity",
        "product_identity": "product_visibility",
        "logo_label": "logo_label_similarity",
        "style": "style_similarity",
        "emotion": "emotion_similarity",
    }[check]


def _threshold_for_metric(
    thresholds: PostRenderConsistencyThresholds,
    metric_name: str,
) -> ConsistencySignalThreshold:
    return getattr(thresholds, metric_name)


def _action_for_metric(
    *,
    value: float,
    threshold: ConsistencySignalThreshold,
) -> PostRenderConsistencyAction:
    if threshold.block is not None and value < threshold.block:
        return "block"
    if value < threshold.review:
        return "requires_review"
    if threshold.warn is not None and value < threshold.warn:
        return "warn"
    return "allow"


def _aggregate_action(actions: Any) -> PostRenderConsistencyAction:
    ordered: list[PostRenderConsistencyAction] = ["block", "requires_review", "warn", "allow"]
    values = set(actions)
    for action in ordered:
        if action in values:
            return action
    return "allow"


def _risk_level(
    *,
    action: PostRenderConsistencyAction,
    overall_score: float | None,
    missing_signals: list[str],
) -> PostRenderRiskLevel:
    if action == "block":
        return "critical"
    if action == "requires_review":
        return "high"
    if missing_signals:
        return "medium"
    if overall_score is None:
        return "unknown"
    if overall_score < 70:
        return "medium"
    return "low"


def _overall_score(required_checks: list[str], metrics: dict[str, float]) -> float | None:
    """Compute a compact 0-100 score with a bounded missing-signal penalty."""
    metric_names = [_metric_name_for_check(check) for check in required_checks]
    present = [metrics[name] for name in metric_names if name in metrics]
    if not present:
        return None
    missing_count = len([name for name in metric_names if name not in metrics])
    missing_penalty = min(30.0, float(missing_count * 10))
    return round(max(0.0, (sum(present) / len(present) * 100.0) - missing_penalty), 2)


def _signal_source(qa_signals: dict[str, Any], metrics: dict[str, float]) -> str:
    explicit_source = str(qa_signals.get("signal_source") or qa_signals.get("source") or "").strip()
    if explicit_source:
        return explicit_source[:80]
    for nested_key in ("cv_probe", "visual_consistency", "consistency_metrics", "metrics", "signals"):
        nested = qa_signals.get(nested_key)
        if isinstance(nested, dict):
            nested_source = str(nested.get("signal_source") or nested.get("source") or "").strip()
            if nested_source:
                return nested_source[:80]
    if metrics:
        return "external_qa_signals"
    return "missing"


def _extract_metrics(qa_signals: dict[str, Any]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    payloads = []
    for nested_key in ("cv_probe", "visual_consistency", "consistency_metrics", "metrics", "signals"):
        nested = qa_signals.get(nested_key)
        if isinstance(nested, dict):
            payloads.append(nested)
    payloads.append(qa_signals)
    for key in (
        "face_similarity",
        "product_visibility",
        "logo_label_similarity",
        "style_similarity",
        "emotion_similarity",
    ):
        for payload in payloads:
            value = _coerce_float(payload.get(key))
            if value is not None:
                metrics[key] = value
                break
    return metrics


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


__all__ = [
    "ConsistencySignalThreshold",
    "PostRenderConsistencyAction",
    "PostRenderConsistencyEvaluator",
    "PostRenderConsistencyQA",
    "PostRenderConsistencyThresholds",
    "PostRenderRiskLevel",
    "VisualConsistencyQAReport",
]
