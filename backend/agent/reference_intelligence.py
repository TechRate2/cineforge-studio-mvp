"""Deterministic reference intelligence for autonomous video planning.

This module is the first production-safe layer of the Reference Brain. It does
not call a paid vision/audio model and does not invent asset facts. Instead, it
uses only user-supplied asset metadata, tags, roles, names, and notes to produce
role confidence, quality warnings, and missing-reference guidance that can be
shown in dry-run/review flows before paid rendering.
"""
from __future__ import annotations

import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from pipeline.contracts import AssetRef, ReferenceRole
from seedance.reference_policy import ReferencePolicy

ReferenceReadinessStatus = Literal["ready", "needs_review", "blocked"]
ReferenceEvidenceStatus = Literal["unavailable", "metadata_only", "partial", "computed"]


class ReferenceEvidence(BaseModel):
    """Traceable V2 evidence for one reference asset.

    Evidence is intentionally separated from user confirmation. A role can be
    user-confirmed while analyzer signals remain unavailable, and unavailable
    signals must be shown honestly instead of treated as inferred facts.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "cineforge.reference_evidence.v2"
    evidence_status: ReferenceEvidenceStatus = "unavailable"
    detected_signals: dict[str, Any] = Field(default_factory=dict)
    user_confirmed_signals: dict[str, Any] = Field(default_factory=dict)
    unavailable_signals: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    computed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ReferenceAssetInsight(BaseModel):
    """Deterministic insight for one supplied reference asset."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str
    kind: str
    tag: str | None = None
    role: str
    role_confidence: float | None = None
    role_locked: bool = False
    readiness: ReferenceReadinessStatus = "needs_review"
    best_use: str = ""
    warnings: list[str] = Field(default_factory=list)
    missing_confirmations: list[str] = Field(default_factory=list)
    evidence: ReferenceEvidence = Field(default_factory=ReferenceEvidence)


class ReferenceIntelligenceReport(BaseModel):
    """Project-level reference readiness report."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "cineforge.reference_intelligence.v2"
    status: ReferenceReadinessStatus
    evidence_status: ReferenceEvidenceStatus = "unavailable"
    asset_count: int
    image_count: int = 0
    video_count: int = 0
    audio_count: int = 0
    insights: list[ReferenceAssetInsight] = Field(default_factory=list)
    required_roles: list[str] = Field(default_factory=list)
    missing_required_roles: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
    reference_sufficiency: dict[str, Any] = Field(default_factory=dict)
    rules_applied: list[str] = Field(default_factory=list)


class ReferenceIntelligenceService:
    """Build deterministic reference reports for preflight and UI review."""

    def __init__(self, *, reference_policy: ReferencePolicy | None = None) -> None:
        self.reference_policy = reference_policy or ReferencePolicy()

    def analyze(
        self,
        *,
        assets: list[AssetRef],
        needs_character_lock: bool = False,
        needs_product_lock: bool = False,
    ) -> ReferenceIntelligenceReport:
        """Return reference readiness using only real supplied asset metadata."""
        assigned_assets = self.reference_policy.assign_reference_roles(assets)
        assigned_assets = self.reference_policy.prioritize_reference_assets(assigned_assets)
        policy_issues = [
            *self.reference_policy.validate_reference_caps(assigned_assets),
            *self.reference_policy.validate_reference_role_conflicts(assigned_assets),
            *self.reference_policy.validate_identity_bible_assets(
                assets=assigned_assets,
                needs_character_lock=needs_character_lock,
                needs_product_lock=needs_product_lock,
            ),
        ]
        warnings = [f"{issue.rule_id}: {issue.message}" for issue in policy_issues if issue.severity != "error"]
        blockers = [f"{issue.rule_id}: {issue.message}" for issue in policy_issues if issue.severity == "error"]
        requirements = self.reference_policy.build_identity_anchor_requirements(
            needs_character_lock=needs_character_lock,
            needs_product_lock=needs_product_lock,
        )
        required_roles = [str(role) for role in requirements.get("required_roles") or []]
        present_roles = {asset.role.value for asset in assigned_assets if asset.role != ReferenceRole.UNKNOWN}
        missing_required_roles = [role for role in required_roles if role not in present_roles]
        insights = [self._asset_insight(asset) for asset in assigned_assets]
        evidence_summary = _evidence_summary(insights)
        if missing_required_roles:
            warnings.extend(f"missing_required_reference_role:{role}" for role in missing_required_roles)
        blocked_asset_messages = _blocked_asset_messages(insights)
        blockers.extend(blocked_asset_messages)
        status: ReferenceReadinessStatus = (
            "blocked"
            if blockers
            else "needs_review"
            if warnings or any(i.readiness != "ready" for i in insights)
            else "ready"
        )
        return ReferenceIntelligenceReport(
            status=status,
            evidence_status=evidence_summary["evidence_status"],
            asset_count=len(assigned_assets),
            image_count=sum(1 for asset in assigned_assets if asset.kind == "image"),
            video_count=sum(1 for asset in assigned_assets if asset.kind == "video"),
            audio_count=sum(1 for asset in assigned_assets if asset.kind == "audio"),
            insights=insights,
            required_roles=required_roles,
            missing_required_roles=missing_required_roles,
            warnings=list(dict.fromkeys(warnings)),
            blockers=list(dict.fromkeys(blockers)),
            evidence_summary=evidence_summary,
            reference_sufficiency=self.reference_policy.score_reference_sufficiency(
                assets=assigned_assets,
                needs_character_lock=needs_character_lock,
                needs_product_lock=needs_product_lock,
            ),
            rules_applied=[
                "reference_intelligence.assign_roles",
                "reference_intelligence.reference_caps",
                "reference_intelligence.role_conflicts",
                "reference_intelligence.identity_bible_requirements",
                "reference_intelligence.asset_readiness",
                "reference_intelligence.v2_reference_evidence",
            ],
        )

    def _asset_insight(self, asset: AssetRef) -> ReferenceAssetInsight:
        warnings: list[str] = []
        missing: list[str] = []
        evidence = _build_reference_evidence(asset)
        role = asset.role.value if isinstance(asset.role, ReferenceRole) else str(asset.role)
        confidence = asset.role_confidence
        if asset.role == ReferenceRole.UNKNOWN:
            warnings.append("reference_role_unknown")
            missing.append("confirm_reference_role")
        if not asset.role_locked:
            missing.append("user_role_confirmation")
        if confidence is not None and confidence < 0.6:
            warnings.append("low_role_confidence")
        if not str(asset.url or "").strip() and asset.kind in {"image", "video", "audio"}:
            warnings.append("missing_asset_url")
        best_use = _best_use_for_role(asset.role)
        readiness: ReferenceReadinessStatus = "ready"
        if "missing_asset_url" in warnings:
            readiness = "blocked"
        elif warnings or missing:
            readiness = "needs_review"
        return ReferenceAssetInsight(
            asset_id=asset.asset_id,
            kind=str(asset.kind),
            tag=asset.tag,
            role=role,
            role_confidence=confidence,
            role_locked=asset.role_locked,
            readiness=readiness,
            best_use=best_use,
            warnings=warnings,
            missing_confirmations=list(dict.fromkeys(missing)),
            evidence=evidence,
        )


def _build_reference_evidence(asset: AssetRef) -> ReferenceEvidence:
    """Build V2 evidence without paid model calls or invented media facts."""
    metadata = _safe_dict(getattr(asset, "metadata", None))
    explicit = _safe_dict(getattr(asset, "evidence", None))
    detected: dict[str, Any] = {}
    user_confirmed: dict[str, Any] = {}
    unavailable: list[str] = []
    warnings: list[str] = []
    sources: list[str] = []

    url = str(asset.url or "").strip()
    if url:
        detected["url_present"] = True
        sources.append("asset.url")
        mime_hint = _mime_hint(url)
        if mime_hint:
            detected["mime_hint"] = mime_hint
            sources.append("url_extension")
    else:
        warnings.append("evidence_missing_asset_url")

    if asset.role_locked and asset.role != ReferenceRole.UNKNOWN:
        user_confirmed["role"] = asset.role.value
        sources.append("user_role_confirmation")
    if asset.tag:
        user_confirmed["tag"] = asset.tag
    if asset.name:
        user_confirmed["name"] = asset.name
    if asset.notes:
        user_confirmed["notes_present"] = True

    _merge_explicit_evidence(detected, explicit, metadata, sources)
    _role_based_expected_signals(asset, detected, user_confirmed)
    unavailable.extend(_missing_signals_for_asset(asset, detected))

    status = _evidence_status(detected, user_confirmed, unavailable, sources)
    return ReferenceEvidence(
        evidence_status=status,
        detected_signals=detected,
        user_confirmed_signals=user_confirmed,
        unavailable_signals=list(dict.fromkeys(unavailable)),
        warnings=list(dict.fromkeys(warnings)),
        sources=list(dict.fromkeys(sources)),
    )


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _mime_hint(url: str) -> str:
    path = url.split("?", 1)[0].split("#", 1)[0]
    mime, _ = mimetypes.guess_type(Path(path).name)
    return mime or ""


def _merge_explicit_evidence(
    detected: dict[str, Any],
    explicit: dict[str, Any],
    metadata: dict[str, Any],
    sources: list[str],
) -> None:
    """Merge caller-provided evidence fields into normalized signal names."""
    evidence = {**metadata, **explicit}
    dimensions_raw = evidence.get("dimensions")
    dimensions: dict[str, Any] = dict(dimensions_raw) if isinstance(dimensions_raw, dict) else {}
    width = _first_number(evidence, dimensions, keys=("width", "w", "image_width"))
    height = _first_number(evidence, dimensions, keys=("height", "h", "image_height"))
    if width and height:
        detected["width"] = int(width)
        detected["height"] = int(height)
        detected["aspect_ratio"] = round(float(width) / max(1.0, float(height)), 4)
        sources.append("asset.evidence.dimensions")

    duration_s = _first_number(evidence, keys=("duration_s", "duration_seconds", "media_duration_s"))
    if duration_s is not None:
        detected["duration_s"] = float(duration_s)
        sources.append("asset.evidence.duration")

    loudness = _first_number(evidence, keys=("loudness_lufs", "integrated_loudness_lufs"))
    if loudness is not None:
        detected["loudness_lufs"] = float(loudness)
        sources.append("asset.evidence.audio")

    for key in (
        "ocr_text_present",
        "logo_present",
        "face_present",
        "person_present",
        "product_present",
        "speech_present",
        "music_present",
        "motion_profile",
        "handoff_frame_present",
    ):
        if key in evidence:
            detected[key] = evidence[key]
            sources.append(f"asset.evidence.{key}")


def _first_number(*records: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for record in records:
        for key in keys:
            value = record.get(key)
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                try:
                    return float(value.strip())
                except ValueError:
                    continue
    return None


def _role_based_expected_signals(
    asset: AssetRef,
    detected: dict[str, Any],
    user_confirmed: dict[str, Any],
) -> None:
    role = asset.role
    role_text = role.value if isinstance(role, ReferenceRole) else str(role)
    if role in {ReferenceRole.CHARACTER_ANCHOR, ReferenceRole.SECONDARY_CHARACTER, ReferenceRole.OUTFIT_REFERENCE}:
        user_confirmed["person_or_character_anchor_expected"] = True
    if role in {ReferenceRole.PRODUCT_HERO, ReferenceRole.PRODUCT_DETAIL, ReferenceRole.BRAND_ASSET}:
        user_confirmed["product_or_brand_anchor_expected"] = True
    if role in {ReferenceRole.STYLE_REFERENCE, ReferenceRole.ENVIRONMENT}:
        user_confirmed["style_or_environment_expected"] = True
    if role in {ReferenceRole.AUDIO_VOICE, ReferenceRole.AUDIO_BGM, ReferenceRole.AUDIO_SFX}:
        user_confirmed["audio_reference_expected"] = True

    search_text = " ".join(
        str(value or "").lower()
        for value in (asset.tag, asset.name, asset.notes, role_text)
    )
    if any(token in search_text for token in ("logo", "brand", "label", "packaging")):
        detected.setdefault("ocr_or_logo_risk_hint", "possible")
    if any(token in search_text for token in ("face", "person", "character", "human", "model")):
        detected.setdefault("person_anchor_hint", "possible")
    if any(token in search_text for token in ("voice", "speech", "dialogue", "narration")):
        detected.setdefault("speech_hint", "possible")


def _missing_signals_for_asset(asset: AssetRef, detected: dict[str, Any]) -> list[str]:
    kind = str(asset.kind or "other")
    missing: list[str] = []
    if kind == "image":
        _missing_if_absent(missing, detected, "width", "image_dimensions")
        _missing_if_absent(missing, detected, "ocr_text_present", "ocr_text_presence")
        _missing_if_absent(missing, detected, "face_present", "face_or_person_detection")
        _missing_if_absent(missing, detected, "product_present", "product_detection")
        _missing_if_absent(missing, detected, "logo_present", "logo_detection")
    elif kind == "video":
        _missing_if_absent(missing, detected, "duration_s", "video_duration")
        _missing_if_absent(missing, detected, "motion_profile", "video_motion_profile")
        _missing_if_absent(missing, detected, "handoff_frame_present", "handoff_frame")
        _missing_if_absent(missing, detected, "ocr_text_present", "video_ocr_text_presence")
    elif kind == "audio":
        _missing_if_absent(missing, detected, "duration_s", "audio_duration")
        _missing_if_absent(missing, detected, "loudness_lufs", "audio_loudness_lufs")
        _missing_if_absent(missing, detected, "speech_present", "speech_presence")
        _missing_if_absent(missing, detected, "music_present", "music_presence")
    return missing


def _missing_if_absent(
    missing: list[str],
    detected: dict[str, Any],
    key: str,
    label: str,
) -> None:
    if key not in detected:
        missing.append(label)


def _evidence_status(
    detected: dict[str, Any],
    user_confirmed: dict[str, Any],
    unavailable: list[str],
    sources: list[str],
) -> ReferenceEvidenceStatus:
    computed_sources = [source for source in sources if source.startswith("asset.evidence.")]
    if computed_sources and not unavailable:
        return "computed"
    if computed_sources:
        return "partial"
    if detected or user_confirmed:
        return "metadata_only"
    return "unavailable"


def _evidence_summary(insights: list[ReferenceAssetInsight]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    unavailable: dict[str, int] = {}
    detected_count = 0
    user_confirmed_count = 0
    for insight in insights:
        status = insight.evidence.evidence_status
        counts[status] = counts.get(status, 0) + 1
        detected_count += len(insight.evidence.detected_signals)
        user_confirmed_count += len(insight.evidence.user_confirmed_signals)
        for signal in insight.evidence.unavailable_signals:
            unavailable[signal] = unavailable.get(signal, 0) + 1
    if counts.get("computed"):
        overall: ReferenceEvidenceStatus = "computed" if counts.get("computed") == len(insights) else "partial"
    elif counts.get("partial"):
        overall = "partial"
    elif counts.get("metadata_only"):
        overall = "metadata_only"
    else:
        overall = "unavailable"
    return {
        "schema_version": "cineforge.reference_evidence_summary.v2",
        "evidence_status": overall,
        "status_counts": counts,
        "detected_signal_count": detected_count,
        "user_confirmed_signal_count": user_confirmed_count,
        "unavailable_signal_counts": unavailable,
    }


def _blocked_asset_messages(insights: list[ReferenceAssetInsight]) -> list[str]:
    """Return project-level blockers for asset insights that cannot render safely."""
    messages: list[str] = []
    for insight in insights:
        if insight.readiness != "blocked":
            continue
        reason = ",".join(insight.warnings) or "blocked_reference_asset"
        messages.append(f"reference_asset_blocked:{insight.asset_id}:{reason}")
    return messages


def _best_use_for_role(role: ReferenceRole) -> str:
    return {
        ReferenceRole.CHARACTER_ANCHOR: "Lock the main character face and identity.",
        ReferenceRole.SECONDARY_CHARACTER: "Support secondary character continuity.",
        ReferenceRole.OUTFIT_REFERENCE: "Preserve wardrobe, silhouette, and body styling.",
        ReferenceRole.PRODUCT_HERO: "Keep product packaging, geometry, color, and hero visibility stable.",
        ReferenceRole.PRODUCT_DETAIL: "Preserve product material, label, macro detail, and close-up evidence.",
        ReferenceRole.BRAND_ASSET: "Preserve brand/logo/color system when visible.",
        ReferenceRole.STYLE_REFERENCE: "Guide color grade, lens feel, mood, and art direction.",
        ReferenceRole.ENVIRONMENT: "Anchor location layout, background, and scene geography.",
        ReferenceRole.CAMERA_MOTION: "Guide camera path and movement style.",
        ReferenceRole.MOTION_STYLE: "Guide pacing, rhythm, and movement energy.",
        ReferenceRole.ACTION_REFERENCE: "Guide the physical action or gesture.",
        ReferenceRole.AUDIO_VOICE: "Guide voice, tone, narration, or dialogue route.",
        ReferenceRole.AUDIO_BGM: "Guide music bed, tempo, and mood.",
        ReferenceRole.AUDIO_SFX: "Guide sound effects, ambience, and foley.",
        ReferenceRole.FIRST_FRAME: "Anchor the opening frame.",
        ReferenceRole.LAST_FRAME: "Anchor the final or handoff frame.",
        ReferenceRole.CONTINUITY_ANCHOR: "Preserve cross-segment continuity state.",
    }.get(role, "Reference role needs user confirmation before paid render.")


__all__ = [
    "ReferenceAssetInsight",
    "ReferenceEvidence",
    "ReferenceEvidenceStatus",
    "ReferenceIntelligenceReport",
    "ReferenceIntelligenceService",
    "ReferenceReadinessStatus",
]
