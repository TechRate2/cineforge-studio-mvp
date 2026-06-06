"""Deterministic reference intelligence for autonomous video planning.

This module is the first production-safe layer of the Reference Brain. It does
not call a paid vision/audio model and does not invent asset facts. Instead, it
uses only user-supplied asset metadata, tags, roles, names, and notes to produce
role confidence, quality warnings, and missing-reference guidance that can be
shown in dry-run/review flows before paid rendering.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from pipeline.contracts import AssetRef, ReferenceRole
from seedance.reference_policy import ReferencePolicy

ReferenceReadinessStatus = Literal["ready", "needs_review", "blocked"]


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


class ReferenceIntelligenceReport(BaseModel):
    """Project-level reference readiness report."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "cineforge.reference_intelligence.v1"
    status: ReferenceReadinessStatus
    asset_count: int
    image_count: int = 0
    video_count: int = 0
    audio_count: int = 0
    insights: list[ReferenceAssetInsight] = Field(default_factory=list)
    required_roles: list[str] = Field(default_factory=list)
    missing_required_roles: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
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
        if missing_required_roles:
            warnings.extend(f"missing_required_reference_role:{role}" for role in missing_required_roles)
        status: ReferenceReadinessStatus = "blocked" if blockers else ("needs_review" if warnings or any(i.readiness != "ready" for i in insights) else "ready")
        return ReferenceIntelligenceReport(
            status=status,
            asset_count=len(assigned_assets),
            image_count=sum(1 for asset in assigned_assets if asset.kind == "image"),
            video_count=sum(1 for asset in assigned_assets if asset.kind == "video"),
            audio_count=sum(1 for asset in assigned_assets if asset.kind == "audio"),
            insights=insights,
            required_roles=required_roles,
            missing_required_roles=missing_required_roles,
            warnings=list(dict.fromkeys(warnings)),
            blockers=list(dict.fromkeys(blockers)),
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
            ],
        )

    def _asset_insight(self, asset: AssetRef) -> ReferenceAssetInsight:
        warnings: list[str] = []
        missing: list[str] = []
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
        )


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
    "ReferenceIntelligenceReport",
    "ReferenceIntelligenceService",
    "ReferenceReadinessStatus",
]
