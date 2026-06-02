"""Curated Seedance example retrieval for Phase 2.

The retriever loads a small provenance-preserving JSONL knowledge base and
ranks examples for few-shot use. It does not execute renders or fetch remote
data at runtime.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from seedance.contracts import AssetMode, CuratedExample, ExampleMetadata


DEFAULT_EXAMPLES_PATH = Path(__file__).resolve().parent / "knowledge" / "examples.jsonl"
LEGACY_EXAMPLES_PATH = Path(__file__).resolve().parent / "knowledge" / "curated_examples.jsonl"


class ExampleQuery(BaseModel):
    """Search intent for curated Seedance few-shot examples."""

    model_config = ConfigDict(extra="forbid")

    niche: str = "unknown"
    asset_mode: AssetMode = "unknown"
    shot_count: int | None = Field(None, ge=1)
    duration_s: int | None = Field(None, ge=1)
    continuity_tags: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list)
    camera_tags: list[str] = Field(default_factory=list)
    audio_tags: list[str] = Field(default_factory=list)
    limit: int = Field(4, ge=2, le=4)


class ExampleRetriever:
    """Load, filter, and rank curated examples with source attribution."""

    def __init__(self, examples: list[CuratedExample] | None = None) -> None:
        self._examples = list(examples or [])

    @classmethod
    def from_jsonl(cls, path: str | Path = DEFAULT_EXAMPLES_PATH) -> "ExampleRetriever":
        """Load examples from a JSONL file."""
        examples: list[CuratedExample] = []
        file_path = Path(path)
        if not file_path.exists() and file_path == DEFAULT_EXAMPLES_PATH:
            file_path = LEGACY_EXAMPLES_PATH
        if not file_path.exists():
            return cls([])
        for line in file_path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            examples.append(_example_from_raw(json.loads(text)).ensure_prompt_hash())
        return cls(examples)

    def retrieve(
        self,
        *,
        niche: str = "unknown",
        asset_mode: AssetMode = "unknown",
        shot_count: int | None = None,
        duration_s: int | None = None,
        continuity_tags: list[str] | None = None,
        style_tags: list[str] | None = None,
        camera_tags: list[str] | None = None,
        audio_tags: list[str] | None = None,
        limit: int = 4,
    ) -> list[CuratedExample]:
        """Return 2-4 ranked examples with attribution fields populated."""
        query = ExampleQuery(
            niche=_norm(niche),
            asset_mode=asset_mode,
            shot_count=shot_count,
            duration_s=duration_s,
            continuity_tags=[_norm(tag) for tag in (continuity_tags or [])],
            style_tags=[_norm(tag) for tag in (style_tags or [])],
            camera_tags=[_norm(tag) for tag in (camera_tags or [])],
            audio_tags=[_norm(tag) for tag in (audio_tags or [])],
            limit=max(2, min(4, int(limit))),
        )
        ranked = sorted(
            (example for example in self._examples if _has_attribution(example)),
            key=lambda example: _ranking_tuple(example, query),
            reverse=True,
        )
        return ranked[:query.limit]

    def list_examples(self) -> list[CuratedExample]:
        """Return all loaded examples without ranking."""
        return list(self._examples)


def _example_from_raw(raw: dict[str, Any]) -> CuratedExample:
    metadata = ExampleMetadata(
        niche=_norm(str(raw.get("niche") or "unknown")),
        duration_s=raw.get("duration_s"),
        duration_bucket=str(raw.get("duration_bucket") or _duration_bucket(raw.get("duration_s"))),
        asset_mode=str(raw.get("asset_mode") or "unknown"),
        shot_count=raw.get("shot_count"),
        language=str(raw.get("language") or "unknown"),
        style_tags=_norm_list(raw.get("style_tags")),
        continuity_tags=_norm_list(raw.get("continuity_tags")),
        camera_tags=_norm_list(raw.get("camera_patterns") or raw.get("camera_tags")),
        audio_tags=_norm_list(raw.get("audio_tags")),
        quality_tags=_norm_list(raw.get("quality_tags")),
        featured=bool(raw.get("featured")),
        source_quality_score=raw.get("source_quality_score"),
        metadata={
            "timing_style": raw.get("timing_style") or "",
            "source_commit": raw.get("source_commit") or "",
            "curation_notes": raw.get("curation_notes") or "",
        },
    )
    return CuratedExample(
        example_id=str(raw.get("example_id") or ""),
        title=str(raw.get("title") or "Untitled Seedance example"),
        source_repo=str(raw.get("source_repo") or ""),
        source_url=str(raw.get("source_url") or ""),
        license=str(raw.get("license") or ""),
        author=raw.get("author"),
        published_at=raw.get("published_at"),
        prompt_excerpt=str(raw.get("prompt_excerpt") or ""),
        prompt_hash=str(raw.get("prompt_hash") or ""),
        video_url=raw.get("video_url"),
        thumbnail_url=raw.get("thumbnail_url"),
        metadata=metadata,
    )


def _ranking_tuple(example: CuratedExample, query: ExampleQuery) -> tuple[int, int, int, int, int, int, int]:
    metadata = example.metadata
    exact_niche = int(query.niche != "unknown" and metadata.niche == query.niche)
    asset_match = int(query.asset_mode != "unknown" and metadata.asset_mode == query.asset_mode)
    shot_match = int(query.shot_count is not None and metadata.shot_count == query.shot_count)
    duration_match = int(
        query.duration_s is not None
        and metadata.duration_bucket == _duration_bucket(query.duration_s)
    )
    tag_score = _tag_overlap(metadata, query)
    quality_score = int((metadata.source_quality_score or 0.0) * 10) + (3 if metadata.featured else 0)
    recency_score = _recency_score(example.published_at)
    return (
        exact_niche,
        asset_match,
        shot_match,
        duration_match,
        tag_score,
        quality_score,
        recency_score,
    )


def _tag_overlap(metadata: ExampleMetadata, query: ExampleQuery) -> int:
    query_tags = set(query.continuity_tags + query.style_tags + query.camera_tags + query.audio_tags)
    example_tags = set(
        metadata.continuity_tags
        + metadata.style_tags
        + metadata.camera_tags
        + metadata.audio_tags
        + metadata.quality_tags
    )
    return len(query_tags & example_tags)


def _duration_bucket(duration_s: Any) -> str:
    if duration_s is None:
        return "unknown"
    value = int(duration_s)
    if value <= 6:
        return "short"
    if value <= 9:
        return "medium"
    if value <= 15:
        return "long"
    return "extended"


def _recency_score(value: str | None) -> int:
    if not value:
        return 0
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.toordinal()
        except ValueError:
            continue
    return 0


def _has_attribution(example: CuratedExample) -> bool:
    return bool(example.source_repo and example.source_url and example.license)


def _norm_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [_norm(value)] if value.strip() else []
    return [_norm(str(item)) for item in value if str(item).strip()]


def _norm(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


__all__ = ["DEFAULT_EXAMPLES_PATH", "ExampleQuery", "ExampleRetriever"]
