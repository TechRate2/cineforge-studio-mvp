"""Contracts for Phase 9A long-form segmented rendering.

The MVP keeps long-form as a thin orchestration layer over existing Seedance
contracts. Every segment remains a normal SeedanceExecutionPlan, while the
LongFormExecutionPlan carries graph and continuity state for 30-60s videos.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from pipeline.contracts import SeedanceExecutionPlan, canonical_hash, utc_now


SegmentStatus = Literal[
    "planned",
    "compiled",
    "dry_run",
    "approved",
    "rendering",
    "completed",
    "failed",
    "repaired",
]
LongFormStatus = Literal["planned", "compiled", "dry_run", "approved", "rendering", "completed", "failed"]


class SegmentHandoff(BaseModel):
    """Continuity state transferred between adjacent long-form segments."""

    model_config = ConfigDict(extra="forbid")

    handoff_id: str = Field(default_factory=lambda: f"handoff_{uuid4().hex[:12]}")
    previous_segment_id: str | None = None
    next_segment_id: str
    last_frame_url: str | None = None
    character_state: dict[str, Any] = Field(default_factory=dict)
    prop_state: dict[str, Any] = Field(default_factory=dict)
    emotion_state: dict[str, Any] = Field(default_factory=dict)
    scene_state: dict[str, Any] = Field(default_factory=dict)
    continuity_notes: list[str] = Field(default_factory=list)
    rules_applied: list[str] = Field(default_factory=list)


class ContinuityBible(BaseModel):
    """Long-form continuity contract shared by every segment."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = "cineforge.longform.continuity_bible.v1"
    continuity_bible_id: str = Field(default_factory=lambda: f"continuity_{uuid4().hex[:12]}")
    source_identity_bible_snapshot: dict[str, Any] = Field(default_factory=dict)
    continuity_pressure: str = "medium"
    character_tracks: dict[str, Any] = Field(default_factory=dict)
    product_tracks: dict[str, Any] = Field(default_factory=dict)
    style_rules: list[str] = Field(default_factory=list)
    emotion_arc: list[str] = Field(default_factory=list)
    segment_snapshots: dict[str, dict[str, Any]] = Field(default_factory=dict)
    forbidden_drift: list[str] = Field(default_factory=list)
    rules_applied: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    @property
    def continuity_hash(self) -> str:
        """Return a stable hash for ApprovalLock metadata and trace."""
        return canonical_hash(self)


class SegmentPlan(BaseModel):
    """One 10-12s render unit inside a long-form execution graph."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = "cineforge.longform.segment_plan.v1"
    segment_id: str = Field(default_factory=lambda: f"segment_{uuid4().hex[:12]}")
    index: int = Field(..., ge=0)
    start_s: int = Field(..., ge=0)
    duration_s: int = Field(..., ge=1, le=15)
    objective: str = ""
    entry_state: dict[str, Any] = Field(default_factory=dict)
    exit_state: dict[str, Any] = Field(default_factory=dict)
    last_frame_anchor: dict[str, Any] = Field(default_factory=dict)
    identity_bible_snapshot: dict[str, Any] = Field(default_factory=dict)
    handoff_requirements: list[str] = Field(default_factory=list)
    seedance_execution_plan: SeedanceExecutionPlan | None = None
    repair_attempts: int = Field(0, ge=0)
    status: SegmentStatus = "planned"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SequencePlan(BaseModel):
    """Linear sequence of segments for Phase 9A MVP."""

    model_config = ConfigDict(extra="forbid")

    sequence_id: str = Field(default_factory=lambda: f"sequence_{uuid4().hex[:12]}")
    index: int = Field(..., ge=0)
    objective: str = ""
    segment_ids: list[str] = Field(default_factory=list)
    start_s: int = Field(0, ge=0)
    duration_s: int = Field(..., ge=1)


class ActPlan(BaseModel):
    """Top-level act container for Act -> Sequence -> Segment -> Shot."""

    model_config = ConfigDict(extra="forbid")

    act_id: str = Field(default_factory=lambda: f"act_{uuid4().hex[:12]}")
    index: int = Field(..., ge=0)
    objective: str = ""
    sequence_ids: list[str] = Field(default_factory=list)
    start_s: int = Field(0, ge=0)
    duration_s: int = Field(..., ge=1)


class LongFormExecutionPlan(BaseModel):
    """MVP long-form plan composed of linear Seedance segment plans."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = "cineforge.longform.execution_plan.v1"
    longform_plan_id: str = Field(default_factory=lambda: f"longform_{uuid4().hex[:12]}")
    source_creative_plan_id: str | None = None
    source_storyboard_id: str | None = None
    total_duration_s: int = Field(..., ge=16, le=60)
    status: LongFormStatus = "planned"
    acts: list[ActPlan] = Field(default_factory=list)
    sequences: list[SequencePlan] = Field(default_factory=list)
    segments: list[SegmentPlan] = Field(default_factory=list)
    segment_graph: list[SegmentHandoff] = Field(default_factory=list)
    continuity_bible: ContinuityBible
    master_execution_plan: SeedanceExecutionPlan | None = None
    rules_applied: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    @property
    def segment_graph_hash(self) -> str:
        """Return a stable hash for the linear segment graph."""
        return canonical_hash(self.segment_graph)


__all__ = [
    "ActPlan",
    "ContinuityBible",
    "LongFormExecutionPlan",
    "LongFormStatus",
    "SegmentHandoff",
    "SegmentPlan",
    "SegmentStatus",
    "SequencePlan",
]
