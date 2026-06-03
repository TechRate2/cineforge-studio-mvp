"""Contracts for Phase 7A identity and consistency management."""
from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


RiskLevel = Literal["low", "medium", "high"]
AnchorKind = Literal["character", "product", "style", "environment", "audio", "unknown"]
ConsistencyAction = Literal["allow", "warn", "requires_review", "block"]


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp without importing pipeline contracts."""
    return datetime.now(timezone.utc)


class IdentityAnchor(BaseModel):
    """A reference asset selected as an identity, product, style, or audio anchor."""

    model_config = ConfigDict(extra="forbid")

    anchor_id: str = Field(default_factory=lambda: f"anchor_{uuid4().hex[:12]}")
    asset_id: str
    tag: str | None = None
    kind: AnchorKind = "unknown"
    role: str = "unknown"
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
    traits: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CharacterIdentityBible(BaseModel):
    """Stable character constraints that should survive storyboard and rendering."""

    model_config = ConfigDict(extra="forbid")

    character_id: str = Field(default_factory=lambda: f"character_{uuid4().hex[:12]}")
    required: bool = False
    anchor_asset_ids: list[str] = Field(default_factory=list)
    face_anchor_asset_id: str | None = None
    full_body_anchor_asset_id: str | None = None
    stable_traits: list[str] = Field(default_factory=list)
    wardrobe_traits: list[str] = Field(default_factory=list)
    forbidden_changes: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = "low"
    warnings: list[str] = Field(default_factory=list)


class ProductIdentityBible(BaseModel):
    """Stable product constraints for product-led videos."""

    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(default_factory=lambda: f"product_{uuid4().hex[:12]}")
    required: bool = False
    anchor_asset_ids: list[str] = Field(default_factory=list)
    hero_anchor_asset_id: str | None = None
    detail_anchor_asset_id: str | None = None
    package_shape: str = ""
    color_palette: list[str] = Field(default_factory=list)
    logo_label_rules: list[str] = Field(default_factory=list)
    forbidden_changes: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = "low"
    warnings: list[str] = Field(default_factory=list)


class StyleBible(BaseModel):
    """Visual style rules shared across shots."""

    model_config = ConfigDict(extra="forbid")

    style_id: str = Field(default_factory=lambda: f"style_{uuid4().hex[:12]}")
    visual_style: str = ""
    lighting: str = ""
    color_palette: list[str] = Field(default_factory=list)
    camera_language: str = ""
    quality_bar: str = "high clarity, stable details, production-ready image quality"
    forbidden_style_drift: list[str] = Field(default_factory=list)


class EmotionContinuityTrack(BaseModel):
    """MVP emotional state track used by drama and UGC strategies."""

    model_config = ConfigDict(extra="forbid")

    track_id: str = Field(default_factory=lambda: f"emotion_{uuid4().hex[:12]}")
    required: bool = False
    starting_emotion: str = ""
    target_emotion: str = ""
    allowed_transitions: list[str] = Field(default_factory=list)
    forbidden_emotion_jumps: list[str] = Field(default_factory=list)


class IdentityBibleBundle(BaseModel):
    """First-class identity contract passed from planning into prompting and QA."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = "cineforge.identity_bible_bundle.v1"
    bible_id: str = Field(default_factory=lambda: f"identity_bible_{uuid4().hex[:12]}")
    analysis_id: str
    anchors: list[IdentityAnchor] = Field(default_factory=list)
    character: CharacterIdentityBible = Field(default_factory=CharacterIdentityBible)
    product: ProductIdentityBible = Field(default_factory=ProductIdentityBible)
    style: StyleBible = Field(default_factory=StyleBible)
    emotion: EmotionContinuityTrack = Field(default_factory=EmotionContinuityTrack)
    rules_applied: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ConsistencyScore(BaseModel):
    """Rule-based consistency score that can be computed before paid render."""

    model_config = ConfigDict(extra="forbid")

    score_id: str = Field(default_factory=lambda: f"consistency_{uuid4().hex[:12]}")
    overall_score: float = Field(..., ge=0.0, le=100.0)
    character_score: float = Field(..., ge=0.0, le=100.0)
    product_score: float = Field(..., ge=0.0, le=100.0)
    style_score: float = Field(..., ge=0.0, le=100.0)
    emotion_score: float = Field(..., ge=0.0, le=100.0)
    reference_sufficiency_score: float = Field(..., ge=0.0, le=100.0)
    risk_flags: list[str] = Field(default_factory=list)
    rules_applied: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConsistencyPolicyResult(BaseModel):
    """Actionable policy derived from consistency scores and risk flags."""

    model_config = ConfigDict(extra="forbid")

    action: ConsistencyAction
    score_id: str
    overall_score: float = Field(..., ge=0.0, le=100.0)
    threshold: float = Field(..., ge=0.0, le=100.0)
    reason_ids: list[str] = Field(default_factory=list)
    blocking_reason_ids: list[str] = Field(default_factory=list)
    warning_reason_ids: list[str] = Field(default_factory=list)
    rules_applied: list[str] = Field(default_factory=list)


__all__ = [
    "AnchorKind",
    "CharacterIdentityBible",
    "ConsistencyAction",
    "ConsistencyPolicyResult",
    "ConsistencyScore",
    "EmotionContinuityTrack",
    "IdentityAnchor",
    "IdentityBibleBundle",
    "ProductIdentityBible",
    "RiskLevel",
    "StyleBible",
]
