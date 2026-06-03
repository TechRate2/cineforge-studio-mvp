"""Post-render visual consistency QA for Phase 7A.

The MVP consumes optional QA signals from a vendor, probe, or future CV service.
When signals are missing for locked character/product/style tracks, it reports
review-needed warnings rather than pretending visual consistency was verified.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PostRenderConsistencyThresholds(BaseModel):
    """Thresholds for post-render visual consistency signals."""

    model_config = ConfigDict(extra="forbid")

    face_similarity: float = Field(0.72, ge=0.0, le=1.0)
    product_visibility: float = Field(0.60, ge=0.0, le=1.0)
    logo_label_similarity: float = Field(0.58, ge=0.0, le=1.0)
    style_similarity: float = Field(0.62, ge=0.0, le=1.0)
    emotion_similarity: float = Field(0.55, ge=0.0, le=1.0)


class VisualConsistencyQAReport(BaseModel):
    """Post-render consistency checks for one rendered segment."""

    model_config = ConfigDict(extra="forbid")

    status: str
    overall_score: float | None = Field(None, ge=0.0, le=100.0)
    signal_source: str = "missing"
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    required_checks: list[str] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    thresholds: dict[str, float] = Field(default_factory=dict)
    rules_applied: list[str] = Field(default_factory=list)


class PostRenderConsistencyQA:
    """Evaluate visual consistency from optional post-render QA signals."""

    def __init__(self, *, thresholds: PostRenderConsistencyThresholds | None = None) -> None:
        self.thresholds = thresholds or PostRenderConsistencyThresholds()

    def evaluate(self, *, shot_metadata: dict[str, Any], qa_signals: dict[str, Any]) -> VisualConsistencyQAReport:
        """Return visual consistency QA without making external calls."""
        required_checks = _required_checks(shot_metadata)
        signal_payload = qa_signals if isinstance(qa_signals, dict) else {}
        metrics = _extract_metrics(signal_payload)
        warnings: list[str] = []
        errors: list[str] = []
        missing: list[str] = []

        for check in required_checks:
            metric_name = _metric_name_for_check(check)
            if metric_name not in metrics:
                missing.append(metric_name)
                warnings.append(f"missing_{metric_name}")

        if metrics.get("face_similarity", 1.0) < self.thresholds.face_similarity:
            errors.append("face_similarity_below_threshold")
        if metrics.get("product_visibility", 1.0) < self.thresholds.product_visibility:
            errors.append("product_visibility_below_threshold")
        if metrics.get("logo_label_similarity", 1.0) < self.thresholds.logo_label_similarity:
            warnings.append("logo_label_similarity_low")
        if metrics.get("style_similarity", 1.0) < self.thresholds.style_similarity:
            warnings.append("style_similarity_low")
        if metrics.get("emotion_similarity", 1.0) < self.thresholds.emotion_similarity:
            warnings.append("emotion_similarity_low")
        if qa_signals and not isinstance(qa_signals, dict):
            warnings.append("qa_signals_invalid_payload")

        status = "fail" if errors else ("warn" if warnings else "pass")
        return VisualConsistencyQAReport(
            status=status,
            overall_score=_overall_score(required_checks, metrics),
            signal_source=_signal_source(signal_payload, metrics),
            warnings=list(dict.fromkeys(warnings)),
            errors=list(dict.fromkeys(errors)),
            metrics=metrics,
            required_checks=required_checks,
            missing_signals=missing,
            thresholds=self.thresholds.model_dump(mode="json"),
            rules_applied=[
                "phase7a.post_render_consistency.face_similarity",
                "phase7a.post_render_consistency.product_visibility",
                "phase7a.post_render_consistency.logo_label_similarity",
                "phase7a.post_render_consistency.style_similarity",
                "phase7a.post_render_consistency.emotion_similarity",
            ],
        )


def _required_checks(metadata: dict[str, Any]) -> list[str]:
    checks: list[str] = []
    if metadata.get("needs_identity_consistency") or _policy_reason_contains(metadata, "character"):
        checks.append("character_identity")
    if metadata.get("needs_product_consistency") or _policy_reason_contains(metadata, "product"):
        checks.append("product_identity")
        checks.append("logo_label")
    if metadata.get("needs_style_consistency") or metadata.get("creative_strategy_id") or metadata.get("consistency_score") is not None:
        checks.append("style")
    if "emotion" in str(metadata.get("consistency_policy_reasons") or ""):
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


def _overall_score(required_checks: list[str], metrics: dict[str, float]) -> float | None:
    """Compute a compact 0-100 score from present metrics used by required checks."""
    metric_names = [_metric_name_for_check(check) for check in required_checks]
    present = [metrics[name] for name in metric_names if name in metrics]
    if not present:
        return None
    return round(sum(present) / len(present) * 100.0, 2)


def _signal_source(qa_signals: dict[str, Any], metrics: dict[str, float]) -> str:
    explicit_source = str(qa_signals.get("signal_source") or qa_signals.get("source") or "").strip()
    if explicit_source:
        return explicit_source[:80]
    if metrics:
        return "external_qa_signals"
    return "missing"


def _extract_metrics(qa_signals: dict[str, Any]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for key in (
        "face_similarity",
        "product_visibility",
        "logo_label_similarity",
        "style_similarity",
        "emotion_similarity",
    ):
        value = _coerce_float(qa_signals.get(key))
        if value is not None:
            metrics[key] = value
    return metrics


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


__all__ = ["PostRenderConsistencyQA", "PostRenderConsistencyThresholds", "VisualConsistencyQAReport"]
