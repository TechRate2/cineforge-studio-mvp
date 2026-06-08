"""Benchmark evidence contracts for launch readiness.

The store is intentionally simple and local-first: it records real render output
URLs, costs, latency, QA status, and human review scores to JSONL. It does not
mock renders or fabricate quality; it only stores evidence produced elsewhere in
the production pipeline so launch claims can be backed by data.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.deliverable_url import deliverable_http_url

BenchmarkVerdict = Literal["usable", "needs_repair", "failed", "unreviewed"]


class BenchmarkEvidenceRecord(BaseModel):
    """One render benchmark evidence row."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "cineforge.benchmark_evidence.v1"
    evidence_id: str = Field(default_factory=lambda: f"evidence_{uuid4().hex[:12]}")
    project_id: str | None = None
    job_id: str | None = None
    niche: str
    runtime_class: str = "short"
    target_platform: str = "tiktok"
    target_market: str = "auto"
    creative_treatment_id: str | None = None
    model: str | None = None
    output_url: str | None = None
    cost_usd: float | None = Field(None, ge=0.0)
    latency_s: float | None = Field(None, ge=0.0)
    qa_status: str | None = None
    qa_score: float | None = Field(None, ge=0.0, le=100.0)
    repair_count: int = Field(0, ge=0)
    human_score: float | None = Field(None, ge=0.0, le=10.0)
    verdict: BenchmarkVerdict = "unreviewed"
    failure_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("output_url")
    @classmethod
    def _output_url_must_be_http(cls, value: str | None) -> str | None:
        if not str(value or "").strip():
            return None
        url = deliverable_http_url(value)
        if url:
            return url
        raise ValueError("benchmark output_url must be a real HTTP(S) render URL")


class BenchmarkLaunchGateReport(BaseModel):
    """Aggregated launch-readiness signal for a niche/runtime slice."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "cineforge.benchmark_launch_gate.v1"
    status: Literal["pass", "warn", "fail"]
    sample_count: int
    usable_count: int
    failed_count: int
    usable_rate: float
    hard_fail_rate: float
    average_qa_score: float | None = None
    average_human_score: float | None = None
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    rules_applied: list[str] = Field(default_factory=list)


class BenchmarkEvidenceStore:
    """Append/read benchmark evidence JSONL records."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: BenchmarkEvidenceRecord) -> None:
        """Append one evidence record to JSONL using strict Pydantic serialization."""
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n")

    def load_all(self) -> list[BenchmarkEvidenceRecord]:
        """Load all valid records from the store."""
        if not self.path.exists():
            return []
        records: list[BenchmarkEvidenceRecord] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                text = line.strip()
                if not text:
                    continue
                records.append(BenchmarkEvidenceRecord.model_validate_json(text))
        return records

    def launch_gate_report(
        self,
        *,
        niche: str | None = None,
        runtime_class: str | None = None,
        min_samples: int = 20,
        min_usable_rate: float = 0.85,
        max_hard_fail_rate: float = 0.10,
    ) -> BenchmarkLaunchGateReport:
        """Return launch-readiness aggregate without hiding weak sample size."""
        records = self.load_all()
        if niche is not None:
            records = [record for record in records if record.niche == niche]
        if runtime_class is not None:
            records = [record for record in records if record.runtime_class == runtime_class]
        return build_launch_gate_report(
            records=records,
            min_samples=min_samples,
            min_usable_rate=min_usable_rate,
            max_hard_fail_rate=max_hard_fail_rate,
        )


def build_launch_gate_report(
    *,
    records: list[BenchmarkEvidenceRecord],
    min_samples: int = 20,
    min_usable_rate: float = 0.85,
    max_hard_fail_rate: float = 0.10,
) -> BenchmarkLaunchGateReport:
    """Aggregate evidence records into a conservative launch decision."""
    sample_count = len(records)
    usable_count = sum(1 for record in records if record.verdict == "usable")
    failed_count = sum(1 for record in records if record.verdict == "failed")
    complete_usable_count = sum(1 for record in records if record.verdict == "usable" and _has_complete_launch_evidence(record))
    usable_rate = usable_count / sample_count if sample_count else 0.0
    hard_fail_rate = failed_count / sample_count if sample_count else 0.0
    warnings: list[str] = []
    blockers: list[str] = []
    if sample_count < min_samples:
        blockers.append("benchmark_insufficient_sample_count")
    if complete_usable_count < min_samples:
        blockers.append("benchmark_insufficient_complete_launch_evidence")
    if usable_rate < min_usable_rate:
        blockers.append("benchmark_usable_rate_below_launch_threshold")
    if hard_fail_rate > max_hard_fail_rate:
        blockers.append("benchmark_hard_fail_rate_above_launch_threshold")
    if any(record.verdict == "usable" and not _has_complete_launch_evidence(record) for record in records):
        warnings.append("benchmark_usable_records_missing_launch_evidence_fields")
    if any(record.verdict == "failed" and not str(record.failure_reason or "").strip() for record in records):
        warnings.append("benchmark_failed_records_missing_failure_reason")
    qa_values = [record.qa_score for record in records if record.qa_score is not None]
    human_values = [record.human_score for record in records if record.human_score is not None]
    if not qa_values:
        warnings.append("benchmark_missing_qa_scores")
    if not human_values:
        warnings.append("benchmark_missing_human_scores")
    status: Literal["pass", "warn", "fail"] = "fail" if blockers else ("warn" if warnings else "pass")
    return BenchmarkLaunchGateReport(
        status=status,
        sample_count=sample_count,
        usable_count=usable_count,
        failed_count=failed_count,
        usable_rate=round(usable_rate, 4),
        hard_fail_rate=round(hard_fail_rate, 4),
        average_qa_score=round(sum(qa_values) / len(qa_values), 2) if qa_values else None,
        average_human_score=round(sum(human_values) / len(human_values), 2) if human_values else None,
        warnings=warnings,
        blockers=blockers,
        rules_applied=[
            "benchmark.launch_gate.min_sample_count",
            "benchmark.launch_gate.usable_rate",
            "benchmark.launch_gate.hard_fail_rate",
            "benchmark.launch_gate.qa_and_human_review_coverage",
            "benchmark.launch_gate.complete_launch_evidence",
        ],
    )


def _has_complete_launch_evidence(record: BenchmarkEvidenceRecord) -> bool:
    """Return whether a usable record contains the evidence required for launch claims."""
    return bool(
        _has_real_output_url(record.output_url)
        and record.cost_usd is not None
        and record.latency_s is not None
        and record.qa_score is not None
        and record.human_score is not None
    )


def _has_real_output_url(value: str | None) -> bool:
    return deliverable_http_url(value) is not None


__all__ = [
    "BenchmarkEvidenceRecord",
    "BenchmarkEvidenceStore",
    "BenchmarkLaunchGateReport",
    "BenchmarkVerdict",
    "build_launch_gate_report",
]
