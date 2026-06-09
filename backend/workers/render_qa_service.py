"""Basic QA checks for rendered Seedance segments."""
from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from core.deliverable_url import deliverable_http_url
from identity.post_render_cv_probe import OpenCVPostRenderProbe
from identity.post_render_consistency import PostRenderConsistencyQA, VisualConsistencyQAReport
from pipeline.contracts import SeedanceShotPlan
from workers.segment_renderer import SegmentRenderResult

logger = logging.getLogger(__name__)


ModelBackedQAStatus = Literal["not_required", "pass", "needs_review", "fail"]


class ModelBackedQAReport(BaseModel):
    """Policy wrapper for expensive/model-backed QA signals.

    The service does not call a model by itself. It records whether required
    checks have real evidence in shot metadata or renderer QA signals.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "cinejelly.model_backed_qa.v1"
    status: ModelBackedQAStatus = "not_required"
    required_checks: list[str] = Field(default_factory=list)
    available_checks: list[str] = Field(default_factory=list)
    missing_checks: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    source: str = "not_required"
    raw: dict[str, Any] = Field(default_factory=dict)


class SegmentQAReport(BaseModel):
    """Basic QA result for one rendered segment."""

    model_config = ConfigDict(extra="forbid")

    shot_id: str
    status: str
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    expected_duration_s: int
    actual_duration_s: int | None = None
    expected_resolution: str
    actual_resolution: str | None = None
    consistency_score: float | None = None
    consistency_policy_action: str | None = None
    consistency_warnings: list[str] = Field(default_factory=list)
    cv_probe_signals: dict[str, object] = Field(default_factory=dict)
    visual_consistency: VisualConsistencyQAReport | None = None
    model_backed_qa: ModelBackedQAReport | None = None


class RenderQAService:
    """Run deterministic post-render checks before assembly."""

    def __init__(
        self,
        *,
        visual_consistency_qa: PostRenderConsistencyQA | None = None,
        visual_probe: OpenCVPostRenderProbe | None = None,
    ) -> None:
        self.visual_consistency_qa = visual_consistency_qa or PostRenderConsistencyQA()
        self.visual_probe = visual_probe or OpenCVPostRenderProbe()

    def evaluate_segment(
        self,
        *,
        shot: SeedanceShotPlan,
        result: SegmentRenderResult,
    ) -> SegmentQAReport:
        """Check URL presence, duration drift, and known resolution metadata."""
        warnings: list[str] = []
        errors: list[str] = []
        if result.status != "completed":
            errors.append(result.error_code or "segment_render_failed")
        if not result.video_url:
            errors.append("missing_video_url")
        elif not deliverable_http_url(result.video_url):
            errors.append("missing_deliverable_video_url")
        if result.duration_s is None:
            warnings.append("missing_duration_metadata")
        elif abs(int(result.duration_s) - int(shot.duration_s)) > 1:
            warnings.append("duration_mismatch_gt_1s")
        actual_resolution = str(result.payload.get("resolution") or "")
        if actual_resolution and actual_resolution != shot.resolution:
            warnings.append("resolution_payload_differs_from_shot")
        consistency_score = _coerce_float(shot.metadata.get("consistency_score"))
        consistency_warnings = [
            str(item)
            for item in (shot.metadata.get("consistency_risk_flags") or [])
            if str(item).strip()
        ]
        qa_signals = dict(result.qa_signals or {})
        cv_probe_report = self.visual_probe.probe(shot=shot, result=result) if _should_run_cv_probe(shot) else {}
        if cv_probe_report:
            qa_signals["cv_probe"] = cv_probe_report
            warnings.extend(str(item) for item in cv_probe_report.get("warnings") or [] if str(item).strip())
            probe_error = _optional_str(cv_probe_report.get("error"))
            if probe_error:
                warnings.append("cv_probe_error")

        visual_report = self.visual_consistency_qa.evaluate(
            shot_metadata=shot.metadata,
            qa_signals=qa_signals,
        )
        model_backed_qa = _model_backed_qa_report(
            shot_metadata=shot.metadata,
            qa_signals=qa_signals,
        )
        if visual_report.action != "allow":
            logger.warning(
                "post_render_visual_consistency_action",
                extra={
                    "shot_id": shot.shot_id,
                    "action": visual_report.action,
                    "risk_level": visual_report.risk_level,
                    "overall_score": visual_report.overall_score,
                    "missing_signals": visual_report.missing_signals,
                    "signal_confidence": visual_report.signal_confidence,
                    "signal_source": visual_report.signal_source,
                    "errors": visual_report.errors,
                },
            )
        warnings.extend(visual_report.warnings)
        errors.extend(visual_report.errors)
        if visual_report.action == "requires_review":
            warnings.append("post_render_consistency_requires_review")
        elif visual_report.action == "block" and not visual_report.errors:
            errors.append("post_render_consistency_blocked")
        consistency_policy_action = (
            _optional_str(shot.metadata.get("consistency_policy_action"))
            or visual_report.action
        )
        if visual_report.action not in {"allow", "warn"}:
            consistency_warnings.append(f"post_render_consistency_action:{visual_report.action}")
        if visual_report.overall_score is not None:
            consistency_score = visual_report.overall_score
        warnings.extend(model_backed_qa.warnings)
        errors.extend(model_backed_qa.errors)
        return SegmentQAReport(
            shot_id=shot.shot_id,
            status="fail" if errors else ("warn" if warnings else "pass"),
            warnings=warnings,
            errors=errors,
            expected_duration_s=shot.duration_s,
            actual_duration_s=result.duration_s,
            expected_resolution=shot.resolution,
            actual_resolution=actual_resolution or None,
            consistency_score=consistency_score,
            consistency_policy_action=consistency_policy_action,
            consistency_warnings=consistency_warnings,
            cv_probe_signals=cv_probe_report,
            visual_consistency=visual_report,
            model_backed_qa=model_backed_qa,
        )


def _model_backed_qa_report(
    *,
    shot_metadata: dict[str, Any],
    qa_signals: dict[str, Any],
) -> ModelBackedQAReport:
    required = _required_model_backed_checks(shot_metadata)
    raw = _extract_model_backed_raw(shot_metadata=shot_metadata, qa_signals=qa_signals)
    if not required:
        return ModelBackedQAReport(raw=raw)

    available = _available_model_backed_checks(raw)
    missing = [check for check in required if check not in available]
    errors = _string_list(raw.get("errors"))
    warnings = _string_list(raw.get("warnings"))
    raw_status = str(raw.get("status") or "").strip().lower()
    if raw_status in {"fail", "failed", "blocked"} or errors:
        status: ModelBackedQAStatus = "fail"
    elif missing:
        status = "needs_review"
        warnings.extend(f"model_backed_qa_missing:{check}" for check in missing)
    else:
        status = "pass"
    return ModelBackedQAReport(
        status=status,
        required_checks=required,
        available_checks=available,
        missing_checks=missing,
        warnings=list(dict.fromkeys(warnings)),
        errors=list(dict.fromkeys(errors)),
        source=str(raw.get("source") or ("model_backed_qa_signals" if raw else "missing")),
        raw=raw,
    )


def _required_model_backed_checks(metadata: dict[str, Any]) -> list[str]:
    if not (
        metadata.get("requires_model_backed_qa")
        or metadata.get("model_backed_qa_required")
        or metadata.get("model_backed_qa_required_checks")
    ):
        return []
    configured = _string_list(metadata.get("model_backed_qa_required_checks"))
    if configured:
        return configured
    checks: list[str] = []
    if metadata.get("needs_identity_consistency"):
        checks.append("identity_consistency")
    if metadata.get("needs_product_consistency"):
        checks.append("product_fidelity")
    if metadata.get("needs_style_consistency"):
        checks.append("style_fidelity")
    if metadata.get("needs_emotion_consistency"):
        checks.append("emotion_fidelity")
    if metadata.get("needs_audio_sync") or metadata.get("needs_lip_sync"):
        checks.append("audio_sync")
    if not checks:
        checks.append("prompt_adherence")
    return list(dict.fromkeys(checks))


def _extract_model_backed_raw(
    *,
    shot_metadata: dict[str, Any],
    qa_signals: dict[str, Any],
) -> dict[str, Any]:
    candidates = [
        qa_signals.get("model_backed_qa"),
        qa_signals.get("model_qa"),
        shot_metadata.get("model_backed_qa"),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            return dict(candidate)
    return {}


def _available_model_backed_checks(raw: dict[str, Any]) -> list[str]:
    available = _string_list(raw.get("available_checks"))
    if available:
        return available
    scores = raw.get("scores")
    if isinstance(scores, dict):
        return [str(key) for key, value in scores.items() if value is not None]
    checks = raw.get("checks")
    if isinstance(checks, dict):
        return [str(key) for key, value in checks.items() if value not in (None, "missing", "unavailable")]
    return []


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _should_run_cv_probe(shot: SeedanceShotPlan) -> bool:
    """Run expensive visual probing only when a shot has consistency surface."""
    metadata = shot.metadata or {}
    if any(
        metadata.get(key)
        for key in (
            "needs_identity_consistency",
            "needs_product_consistency",
            "needs_style_consistency",
            "needs_emotion_consistency",
            "consistency_policy_action",
            "consistency_score",
        )
    ):
        return True
    return False


__all__ = ["ModelBackedQAReport", "RenderQAService", "SegmentQAReport"]
