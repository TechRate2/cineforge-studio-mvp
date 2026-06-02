"""Seedance knowledge and example provenance contracts.

These models are intentionally source-aware. Rules and examples imported from
community repositories must remain traceable back to their repository, URL, and
license before they affect prompts or paid render decisions.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from pipeline.contracts import canonical_hash, utc_now


class SeedanceContract(BaseModel):
    """Base Seedance contract with explicit metadata extension space."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = "cineforge.seedance.v1"
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSource(SeedanceContract):
    """A source repository or document used to derive rules or examples."""

    schema_version: str = "cineforge.seedance.knowledge_source.v1"
    source_id: str = Field(default_factory=lambda: f"source_{uuid4().hex[:12]}")
    source_repo: str = Field(..., description="Repository in owner/name form.")
    source_url: str = Field(..., description="Canonical URL for the source material.")
    license: str = Field(..., description="Source license or usage note.")
    commit_sha: str | None = None
    retrieved_at: datetime = Field(default_factory=utc_now)
    description: str = ""


RuleType = Literal[
    "prompt_formula",
    "prompt_linter",
    "reference_policy",
    "model_router",
    "storyboard",
    "curated_example",
    "quality_gate",
]


class SeedanceKnowledgeRule(SeedanceContract):
    """One implementation-ready rule derived from a knowledge source."""

    schema_version: str = "cineforge.seedance.knowledge_rule.v1"
    rule_id: str = Field(default_factory=lambda: f"rule_{uuid4().hex[:12]}")
    source_repo: str
    source_url: str
    license: str
    rule_type: RuleType
    applies_to_files: list[str] = Field(default_factory=list)
    target_functions: list[str] = Field(default_factory=list)
    summary: str
    implementation_notes: str = ""
    phase: str = Field("1b", description="Planned integration phase.")
    severity: Literal["info", "warn", "block"] = "info"
    tags: list[str] = Field(default_factory=list)


AssetMode = Literal[
    "t2v",
    "i2v",
    "v2v",
    "audio_driven",
    "multi_reference",
    "mixed",
    "unknown",
]


class ExampleMetadata(SeedanceContract):
    """Search and filtering metadata for a curated few-shot example."""

    schema_version: str = "cineforge.seedance.example_metadata.v1"
    niche: str = "unknown"
    duration_s: int | None = Field(None, ge=1)
    duration_bucket: str = ""
    asset_mode: AssetMode = "unknown"
    shot_count: int | None = Field(None, ge=1)
    language: str = "unknown"
    style_tags: list[str] = Field(default_factory=list)
    continuity_tags: list[str] = Field(default_factory=list)
    camera_tags: list[str] = Field(default_factory=list)
    audio_tags: list[str] = Field(default_factory=list)
    quality_tags: list[str] = Field(default_factory=list)
    featured: bool = False
    source_quality_score: float | None = Field(None, ge=0.0, le=1.0)


class CuratedExample(SeedanceContract):
    """A curated Seedance few-shot example with provenance and search metadata."""

    schema_version: str = "cineforge.seedance.curated_example.v1"
    example_id: str = Field(default_factory=lambda: f"example_{uuid4().hex[:12]}")
    title: str
    source_repo: str
    source_url: str
    license: str
    author: str | None = None
    published_at: str | None = None
    prompt_excerpt: str = Field(
        "",
        description="A controlled excerpt or normalized few-shot text, not a bulk raw prompt dump.",
    )
    prompt_hash: str = ""
    video_url: str | None = None
    thumbnail_url: str | None = None
    metadata: ExampleMetadata = Field(default_factory=ExampleMetadata)

    def ensure_prompt_hash(self) -> "CuratedExample":
        """Populate prompt_hash from prompt_excerpt when an importer omitted it."""
        if not self.prompt_hash and self.prompt_excerpt:
            self.prompt_hash = canonical_hash(self.prompt_excerpt)
        return self


__all__ = [
    "AssetMode",
    "CuratedExample",
    "ExampleMetadata",
    "KnowledgeSource",
    "RuleType",
    "SeedanceKnowledgeRule",
]
