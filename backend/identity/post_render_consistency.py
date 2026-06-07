"""Post-render visual consistency evaluation.

This layer is deterministic and probe-agnostic. It consumes `qa_signals` from
vendor payloads or local CV probes and turns them into a stable delivery policy.
The evaluator intentionally avoids paid model calls so it can run for every
rendered segment, including long-form retries and final assembly gates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
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
    signal_confidence: dict[str, float] = Field(default_factory=dict)
    signal_quality: dict[str, Any] = Field(default_factory=dict)
    quality_flags: list[str] = Field(default_factory=list)
    retry_recommendations: list[str] = Field(default_factory=list)
    decision_factors: dict[str, Any] = Field(default_factory=dict)
    required_checks: list[str] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    thresholds: dict[str, Any] = Field(default_factory=dict)
    signal_actions: dict[str, PostRenderConsistencyAction] = Field(default_factory=dict)
    rules_applied: list[str] = Field(default_factory=list)


@dataclass(slots=True)
class _QualityDiagnostics:
    """Derived reliability guardrails for CV/vendor QA payloads."""

    flags: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    retry_recommendations: list[str] = field(default_factory=list)
    score_penalty: float = 0.0
    requires_review: bool = False


class PostRenderConsistencyEvaluator:
    """Evaluate post-render visual consistency signals into score and action."""

    def __init__(
        self,
        *,
        thresholds: PostRenderConsistencyThresholds | None = None,
        low_confidence_threshold: float = 0.35,
        strict_low_confidence_threshold: float = 0.18,
    ) -> None:
        self.thresholds = thresholds or PostRenderConsistencyThresholds()
        self.low_confidence_threshold = max(0.0, min(1.0, float(low_confidence_threshold)))
        self.strict_low_confidence_threshold = max(
            0.0,
            min(self.low_confidence_threshold, float(strict_low_confidence_threshold)),
        )

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
        signal_confidence = _extract_signal_confidence(signal_payload)
        signal_quality = _extract_signal_quality(signal_payload)
        quality = _diagnose_signal_quality(
            required_checks=required_checks,
            metrics=metrics,
            signal_confidence=signal_confidence,
            signal_quality=signal_quality,
            low_confidence_threshold=self.low_confidence_threshold,
            strict_low_confidence_threshold=self.strict_low_confidence_threshold,
        )
        warnings: list[str] = list(quality.warnings)
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
            confidence = signal_confidence.get(metric_name)
            if confidence is None:
                confidence = _fallback_confidence_from_quality(
                    metric_name=metric_name,
                    signal_quality=signal_quality,
                )
                if confidence is not None:
                    signal_confidence[metric_name] = confidence
            if confidence is not None:
                if confidence < self.strict_low_confidence_threshold:
                    warnings.append(f"very_low_confidence_{metric_name}")
                    if signal_action == "allow":
                        signal_action = "requires_review"
                    elif signal_action == "warn":
                        signal_action = "requires_review"
                elif confidence < self.low_confidence_threshold:
                    warnings.append(f"low_confidence_{metric_name}")
                    if signal_action == "allow":
                        signal_action = "warn"

            signal_actions[metric_name] = signal_action
            if signal_action == "block":
                errors.append(f"{metric_name}_below_threshold")
            elif signal_action == "requires_review":
                warnings.append(f"{metric_name}_requires_review")
            elif signal_action == "warn":
                warnings.append(f"{metric_name}_low")

        overall_score = _overall_score(
            required_checks=required_checks,
            metrics=metrics,
            signal_confidence=signal_confidence,
            quality_penalty=quality.score_penalty,
        )
        raw_action = _aggregate_action(signal_actions.values())
        action = raw_action
        if action in {"allow", "warn"} and quality.requires_review:
            action = "requires_review"
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
            signal_confidence=signal_confidence,
            signal_quality=signal_quality,
            quality_flags=list(dict.fromkeys(quality.flags)),
            retry_recommendations=list(dict.fromkeys(quality.retry_recommendations)),
            decision_factors={
                "required_check_count": len(required_checks),
                "metric_count": len(metrics),
                "missing_count": len(missing),
                "quality_penalty": round(quality.score_penalty, 2),
                "low_confidence_threshold": self.low_confidence_threshold,
                "strict_low_confidence_threshold": self.strict_low_confidence_threshold,
                "quality_requires_review": quality.requires_review,
                "aggregate_signal_action": raw_action,
            },
            required_checks=required_checks,
            missing_signals=missing,
            thresholds=self.thresholds.model_dump(mode="json"),
            signal_actions=signal_actions,
            rules_applied=[
                "post_render_consistency.signal_thresholds",
                "post_render_consistency.overall_score",
                "post_render_consistency.policy_action",
                "post_render_consistency.missing_signal_guardrail",
                "post_render_consistency.signal_confidence_guardrail",
                "post_render_consistency.signal_quality_guardrail",
                "post_render_consistency.retry_recommendation_policy",
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


def _overall_score(
    *,
    required_checks: list[str],
    metrics: dict[str, float],
    signal_confidence: dict[str, float],
    quality_penalty: float,
) -> float | None:
    """Compute a compact 0-100 score with bounded missing and reliability penalties."""
    metric_names = [_metric_name_for_check(check) for check in required_checks]
    present: list[float] = []
    for name in metric_names:
        if name not in metrics:
            continue
        value = metrics[name]
        confidence = signal_confidence.get(name)
        if confidence is not None:
            # Keep the metric meaningful while penalizing weak probe confidence.
            value *= 0.72 + (0.28 * confidence)
        present.append(value)

    if not present:
        return None
    missing_count = len([name for name in metric_names if name not in metrics])
    missing_penalty = min(30.0, float(missing_count * 10))
    return round(max(0.0, (sum(present) / len(present) * 100.0) - missing_penalty - quality_penalty), 2)


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
    payloads = _nested_payloads(qa_signals)
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


def _extract_signal_confidence(qa_signals: dict[str, Any]) -> dict[str, float]:
    confidence: dict[str, float] = {}
    payloads = _nested_payloads(qa_signals)
    for payload in payloads:
        for confidence_key in ("signal_confidence", "metric_confidence", "confidence"):
            nested = payload.get(confidence_key)
            if not isinstance(nested, dict):
                continue
            for key in (
                "face_similarity",
                "product_visibility",
                "logo_label_similarity",
                "style_similarity",
                "emotion_similarity",
                "body_outfit_similarity",
            ):
                value = _coerce_float(nested.get(key))
                if value is not None and key not in confidence:
                    confidence[key] = value
    return confidence


def _extract_signal_quality(qa_signals: dict[str, Any]) -> dict[str, Any]:
    quality: dict[str, Any] = {}
    for payload in _nested_payloads(qa_signals):
        nested = payload.get("signal_quality")
        if isinstance(nested, dict):
            quality.update(nested)
    return quality


def _nested_payloads(qa_signals: dict[str, Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for nested_key in ("cv_probe", "visual_consistency", "consistency_metrics", "metrics", "signals"):
        nested = qa_signals.get(nested_key)
        if isinstance(nested, dict):
            payloads.append(nested)
    payloads.append(qa_signals)
    return payloads


def _diagnose_signal_quality(
    *,
    required_checks: list[str],
    metrics: dict[str, float],
    signal_confidence: dict[str, float],
    signal_quality: dict[str, Any],
    low_confidence_threshold: float,
    strict_low_confidence_threshold: float,
) -> _QualityDiagnostics:
    diagnostics = _QualityDiagnostics()
    required_metrics = {_metric_name_for_check(check) for check in required_checks}

    frame_count = _coerce_int(signal_quality.get("frame_count"))
    reference_count = _coerce_int(signal_quality.get("reference_count"))
    if frame_count is not None and frame_count < 2 and required_checks:
        diagnostics.flags.append("cv_probe_insufficient_render_frames")
        diagnostics.warnings.append("cv_probe_insufficient_render_frames")
        diagnostics.retry_recommendations.append("rerender_segment_with_clearer_subject_and_more_stable_camera")
        diagnostics.score_penalty += 14.0
        diagnostics.requires_review = True
    elif frame_count is not None and frame_count < 4 and required_checks:
        diagnostics.flags.append("cv_probe_low_frame_sample_count")
        diagnostics.warnings.append("cv_probe_low_frame_sample_count")
        diagnostics.retry_recommendations.append("increase_sampled_frames_or_verify_video_decode")
        diagnostics.score_penalty += 5.0

    if reference_count == 0 and required_metrics:
        diagnostics.flags.append("cv_probe_no_reference_assets")
        diagnostics.warnings.append("cv_probe_no_reference_assets")
        diagnostics.retry_recommendations.append("attach_or_confirm_character_product_style_references")
        diagnostics.score_penalty += 10.0

    face_quality = signal_quality.get("face") if isinstance(signal_quality.get("face"), dict) else {}
    if "face_similarity" in required_metrics:
        if _coerce_int(face_quality.get("reference_faces")) == 0:
            diagnostics.flags.append("character_reference_face_not_detected")
            diagnostics.warnings.append("character_reference_face_not_detected")
            diagnostics.retry_recommendations.append("use_front_facing_character_reference_with_visible_face")
            diagnostics.score_penalty += 12.0
            diagnostics.requires_review = True
        if _coerce_int(face_quality.get("frame_faces")) == 0:
            diagnostics.flags.append("rendered_character_face_not_detected")
            diagnostics.warnings.append("rendered_character_face_not_detected")
            diagnostics.retry_recommendations.append("repair_prompt_with_visible_face_closeup_and_identity_anchor")
            diagnostics.score_penalty += 12.0
            diagnostics.requires_review = True

    product_quality = signal_quality.get("product") if isinstance(signal_quality.get("product"), dict) else {}
    if "product_visibility" in required_metrics:
        regions = _coerce_float(product_quality.get("regions_per_frame"))
        if regions is not None and regions < 0.35:
            diagnostics.flags.append("product_probe_low_region_evidence")
            diagnostics.warnings.append("product_probe_low_region_evidence")
            diagnostics.retry_recommendations.append("repair_prompt_with_larger_product_hero_frame_and_clean_background")
            diagnostics.score_penalty += 8.0

    style_quality = signal_quality.get("style") if isinstance(signal_quality.get("style"), dict) else {}
    style_components = style_quality.get("components") if isinstance(style_quality.get("components"), dict) else {}
    temporal_stability = _coerce_float(style_components.get("temporal"))
    if "style_similarity" in required_metrics and temporal_stability is not None and temporal_stability < 0.50:
        diagnostics.flags.append("temporal_style_instability")
        diagnostics.warnings.append("temporal_style_instability")
        diagnostics.retry_recommendations.append("repair_prompt_with_fixed_lighting_color_grade_and_handoff_frame")
        diagnostics.score_penalty += 9.0

    for metric_name in required_metrics:
        confidence = signal_confidence.get(metric_name)
        if confidence is None:
            continue
        if confidence < strict_low_confidence_threshold:
            diagnostics.flags.append(f"{metric_name}_very_low_probe_confidence")
            diagnostics.retry_recommendations.append("rerender_or_route_to_manual_review_due_to_unreliable_probe_signal")
            diagnostics.score_penalty += 8.0
            diagnostics.requires_review = True
        elif confidence < low_confidence_threshold:
            diagnostics.flags.append(f"{metric_name}_low_probe_confidence")
            diagnostics.retry_recommendations.append("rerun_probe_or_collect_stronger_reference_evidence")
            diagnostics.score_penalty += 4.0

    if required_metrics and not metrics:
        diagnostics.flags.append("no_required_visual_consistency_metrics")
        diagnostics.retry_recommendations.append("run_post_render_cv_probe_or_block_delivery_until_manual_review")
        diagnostics.score_penalty += 20.0
        diagnostics.requires_review = True

    return diagnostics


def _fallback_confidence_from_quality(
    *,
    metric_name: str,
    signal_quality: dict[str, Any],
) -> float | None:
    if metric_name == "face_similarity":
        quality = signal_quality.get("face")
        if isinstance(quality, dict):
            ref_faces = _coerce_int(quality.get("reference_faces"))
            frame_faces = _coerce_int(quality.get("frame_faces"))
            if ref_faces is not None and frame_faces is not None:
                if ref_faces == 0 or frame_faces == 0:
                    return 0.08
                return min(0.95, 0.35 + (0.10 * min(ref_faces, 3)) + (0.06 * min(frame_faces, 6)))
    if metric_name == "product_visibility":
        quality = signal_quality.get("product")
        if isinstance(quality, dict):
            regions = _coerce_float(quality.get("regions_per_frame"))
            if regions is not None:
                return max(0.10, min(0.90, 0.25 + regions))
    if metric_name == "style_similarity":
        quality = signal_quality.get("style")
        if isinstance(quality, dict):
            components = quality.get("components")
            if isinstance(components, dict):
                values = [_coerce_float(value) for value in components.values()]
                values = [value for value in values if value is not None]
                if values:
                    return max(0.10, min(0.95, sum(values) / len(values)))
    return None


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
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
