"""Core typed contracts for the CineForge production pipeline.

Phase 0 intentionally defines stable data boundaries before implementation
logic. Later phases can add smarter planners, compilers, and workers without
passing loose dictionaries between stages.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Mapping, Sequence
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for contract creation fields."""
    return datetime.now(timezone.utc)


def _json_safe(value: Any) -> Any:
    """Convert Pydantic models and common objects into stable JSON values."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value


def canonical_hash(value: Any) -> str:
    """Return a deterministic SHA-256 hash for any contract-like payload."""
    encoded = json.dumps(
        _json_safe(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class PipelineContract(BaseModel):
    """Base model for contracts with explicit extension space."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = Field(
        "cineforge.pipeline.v1",
        description="Contract schema namespace and version.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Forward-compatible extension data that is not part of the strict contract.",
    )


class ReferenceRole(str, Enum):
    """Stable roles for assets used by the pipeline and Seedance compiler."""

    UNKNOWN = "unknown"
    CHARACTER_ANCHOR = "character_anchor"
    SECONDARY_CHARACTER = "secondary_character"
    PRODUCT_HERO = "product_hero"
    PRODUCT_DETAIL = "product_detail"
    STYLE_REFERENCE = "style_reference"
    ENVIRONMENT = "environment"
    BRAND_ASSET = "brand_asset"
    CAMERA_MOTION = "camera_motion"
    MOTION_STYLE = "motion_style"
    ACTION_REFERENCE = "action_reference"
    VISUAL_EFFECT = "visual_effect"
    OUTFIT_REFERENCE = "outfit_reference"
    AUDIO_VOICE = "audio_voice"
    AUDIO_BGM = "audio_bgm"
    AUDIO_SFX = "audio_sfx"
    FIRST_FRAME = "first_frame"
    LAST_FRAME = "last_frame"
    CONTINUITY_ANCHOR = "continuity_anchor"


AssetKind = Literal["image", "video", "audio", "document", "pinned_asset", "other"]


class AssetRef(PipelineContract):
    """A normalized reference asset with a single primary pipeline role."""

    schema_version: str = "cineforge.asset_ref.v1"
    asset_id: str = Field(default_factory=lambda: f"asset_{uuid4().hex[:12]}")
    kind: AssetKind = "other"
    url: str = Field("", description="Public or internal URL for the asset.")
    tag: str | None = Field(
        None,
        description="Stable prompt tag such as @image_1, @video_1, or @audio_1.",
    )
    role: ReferenceRole = ReferenceRole.UNKNOWN
    role_confidence: float | None = Field(None, ge=0.0, le=1.0)
    role_locked: bool = Field(
        False,
        description="True when the user confirmed this role and planners must not override it silently.",
    )
    name: str = ""
    notes: str = ""
    source: str = Field(
        "user_upload",
        description="Where this asset came from: user_upload, pinned_asset, generated, imported, etc.",
    )


class InputContract(PipelineContract):
    """Canonical request entering the autonomous production pipeline."""

    schema_version: str = "cineforge.input_contract.v1"
    input_id: str = Field(default_factory=lambda: f"input_{uuid4().hex[:12]}")
    user_idea: str = Field(..., min_length=1)
    target_platform: str = "tiktok"
    target_market: str = "auto"
    duration_hint_s: int | None = Field(None, ge=1)
    aspect_ratio: str | None = None
    resolution: str | None = None
    assets: list[AssetRef] = Field(default_factory=list)
    conversation_context: list[dict[str, Any]] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class AnalyzedInput(PipelineContract):
    """Deterministic and model-assisted interpretation of the user's request."""

    schema_version: str = "cineforge.analyzed_input.v1"
    analysis_id: str = Field(default_factory=lambda: f"analysis_{uuid4().hex[:12]}")
    input_id: str
    idea_hash: str
    normalized_idea: str
    detected_niche: str = "unknown"
    intent: str = "unknown"
    target_platform: str = "tiktok"
    target_market: str = "auto"
    duration_s: int | None = Field(None, ge=1)
    aspect_ratio: str | None = None
    asset_summary: dict[str, Any] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CreativePlan(PipelineContract):
    """Creative strategy selected before storyboard and prompt compilation."""

    schema_version: str = "cineforge.creative_plan.v1"
    creative_plan_id: str = Field(default_factory=lambda: f"creative_{uuid4().hex[:12]}")
    analysis_id: str
    target_niche: str = "unknown"
    objective: str = ""
    hook_pattern: str = ""
    narrative_arc: list[str] = Field(default_factory=list)
    shot_count: int = Field(1, ge=1)
    duration_s: int = Field(8, ge=1)
    aspect_ratio: str = "9:16"
    reference_strategy: dict[str, Any] = Field(default_factory=dict)
    consistency_plan: dict[str, Any] = Field(default_factory=dict)
    style_direction: str = ""
    audio_direction: str = ""
    constraints: list[str] = Field(default_factory=list)


class StoryboardScene(PipelineContract):
    """One storyboard scene card consumed by prompt compilation."""

    schema_version: str = "cineforge.storyboard_scene.v1"
    scene_id: str = Field(default_factory=lambda: f"scene_{uuid4().hex[:12]}")
    index: int = Field(..., ge=0)
    duration_s: int = Field(4, ge=1)
    beat: str = Field("", description="Narrative purpose or emotional beat.")
    visual_intent: str = ""
    action: str = ""
    camera_movement: str = ""
    spatial_change: str = ""
    audio_intent: str = ""
    reference_bindings: list[str] = Field(default_factory=list)
    continuity_notes: str = ""


class StoryboardContract(PipelineContract):
    """Ordered storyboard that freezes the intended video structure."""

    schema_version: str = "cineforge.storyboard_contract.v1"
    storyboard_id: str = Field(default_factory=lambda: f"storyboard_{uuid4().hex[:12]}")
    creative_plan_id: str
    scenes: list[StoryboardScene] = Field(default_factory=list)
    duration_s: int = Field(8, ge=1)
    aspect_ratio: str = "9:16"
    title: str = ""
    summary: str = ""


class SeedanceShotPlan(PipelineContract):
    """One Seedance render unit after prompt compilation."""

    schema_version: str = "cineforge.seedance_shot_plan.v1"
    shot_id: str
    index: int = Field(..., ge=0)
    duration_s: int = Field(..., ge=1)
    compiled_prompt: str = ""
    negative_prompt: str = ""
    model: str = "auto"
    aspect_ratio: str = "9:16"
    resolution: str = "1080p"
    references: list[AssetRef] = Field(default_factory=list)
    reference_bindings: dict[str, ReferenceRole] = Field(default_factory=dict)
    rules_applied: list[str] = Field(default_factory=list)
    examples_used: list[str] = Field(default_factory=list)
    linter_warnings: list[str] = Field(default_factory=list)


class SeedanceExecutionPlan(PipelineContract):
    """Compiled Seedance plan that later render workers should execute verbatim."""

    schema_version: str = "cineforge.seedance_execution_plan.v1"
    execution_plan_id: str = Field(default_factory=lambda: f"seedance_exec_{uuid4().hex[:12]}")
    storyboard_id: str | None = None
    model: str = "auto"
    aspect_ratio: str = "9:16"
    resolution: str = "1080p"
    duration_s: int = Field(8, ge=1)
    compiled_prompt: str = Field(
        "",
        description="Plan-level prompt summary for single-shot or preview flows.",
    )
    shots: list[SeedanceShotPlan] = Field(default_factory=list)
    reference_assets: list[AssetRef] = Field(default_factory=list)
    cost_estimate: dict[str, Any] = Field(default_factory=dict)
    rules_applied: list[str] = Field(default_factory=list)
    examples_used: list[str] = Field(default_factory=list)
    linter_warnings: list[str] = Field(default_factory=list)


class RenderAssemblyPlan(PipelineContract):
    """Post-render assembly contract for segment ordering and final output."""

    schema_version: str = "cineforge.render_assembly_plan.v1"
    assembly_plan_id: str = Field(default_factory=lambda: f"assembly_{uuid4().hex[:12]}")
    execution_plan_id: str
    segment_order: list[str] = Field(default_factory=list)
    transitions: list[dict[str, Any]] = Field(default_factory=list)
    audio_plan: dict[str, Any] = Field(default_factory=dict)
    output_settings: dict[str, Any] = Field(default_factory=dict)
    expected_outputs: list[str] = Field(default_factory=list)


__all__ = [
    "AnalyzedInput",
    "AssetKind",
    "AssetRef",
    "CreativePlan",
    "InputContract",
    "PipelineContract",
    "ReferenceRole",
    "RenderAssemblyPlan",
    "SeedanceExecutionPlan",
    "SeedanceShotPlan",
    "StoryboardContract",
    "StoryboardScene",
    "canonical_hash",
    "utc_now",
]
