"""Trace records for the multi-stage CineForge pipeline."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from pipeline.contracts import canonical_hash, utc_now


class PipelineTraceEntry(BaseModel):
    """One auditable decision record for a pipeline stage."""

    model_config = ConfigDict(extra="forbid")

    stage: str
    input_hash: str
    output_hash: str
    decision: str = ""
    reasoning_summary: str = ""
    rules_applied: list[str] = Field(default_factory=list)
    examples_used: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    model_route: dict[str, Any] = Field(default_factory=dict)
    cost_estimate: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class PipelineTrace(BaseModel):
    """Append-only trace for explaining how a request moved through stages."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = "cineforge.pipeline_trace.v1"
    trace_id: str = Field(default_factory=lambda: f"trace_{uuid4().hex[:12]}")
    input_id: str | None = None
    entries: list[PipelineTraceEntry] = Field(default_factory=list)

    def append_stage(
        self,
        *,
        stage: str,
        stage_input: Any,
        stage_output: Any,
        decision: str = "",
        reasoning_summary: str = "",
        rules_applied: list[str] | None = None,
        examples_used: list[str] | None = None,
        warnings: list[str] | None = None,
        model_route: dict[str, Any] | None = None,
        cost_estimate: dict[str, Any] | None = None,
    ) -> PipelineTraceEntry:
        """Hash the stage payloads and append one trace entry."""
        entry = PipelineTraceEntry(
            stage=stage,
            input_hash=canonical_hash(stage_input),
            output_hash=canonical_hash(stage_output),
            decision=decision,
            reasoning_summary=reasoning_summary,
            rules_applied=rules_applied or [],
            examples_used=examples_used or [],
            warnings=warnings or [],
            model_route=model_route or {},
            cost_estimate=cost_estimate or {},
        )
        self.entries.append(entry)
        return entry


__all__ = ["PipelineTrace", "PipelineTraceEntry"]
