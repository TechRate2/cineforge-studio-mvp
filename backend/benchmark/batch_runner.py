"""Batch benchmark orchestration for launch gate evidence."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from benchmark.cases import compile_benchmark_case, load_benchmark_case_definitions
from benchmark.evidence_store import BenchmarkEvidenceStore, BenchmarkLaunchGateReport, build_launch_gate_report
from benchmark.runner import BenchmarkRenderCase, BenchmarkRenderRunner, BenchmarkRunResult
from core.config import settings
from core.env_guard import missing_secret_names


class BenchmarkLaunchGateSlice(BaseModel):
    """Launch gate report scoped to one niche/runtime pair."""

    model_config = ConfigDict(extra="forbid")

    niche: str
    runtime_class: str
    report: BenchmarkLaunchGateReport


class BenchmarkBatchRunResult(BaseModel):
    """Result of a benchmark batch run."""

    model_config = ConfigDict(extra="forbid")

    dry_run_only: bool
    paid_mode: bool
    case_count: int
    evidence_path: str | None = None
    results: list[BenchmarkRunResult] = Field(default_factory=list)
    launch_gate_reports: list[BenchmarkLaunchGateSlice] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkBatchRunner:
    """Compile and run benchmark cases through BenchmarkRenderRunner."""

    def __init__(
        self,
        *,
        render_runner: BenchmarkRenderRunner | None = None,
        evidence_store: BenchmarkEvidenceStore | None = None,
    ) -> None:
        self.evidence_store = evidence_store
        self.render_runner = render_runner or BenchmarkRenderRunner(evidence_store=evidence_store)

    def run_cases(
        self,
        cases: list[BenchmarkRenderCase],
        *,
        dry_run_only: bool = True,
        paid_mode: bool = False,
        cost_gate_mode: str = "off",
        min_samples: int = 20,
        min_usable_rate: float = 0.85,
        max_hard_fail_rate: float = 0.10,
    ) -> BenchmarkBatchRunResult:
        """Run compiled benchmark cases and aggregate launch gates."""
        if paid_mode and dry_run_only:
            raise ValueError("paid_mode requires dry_run_only=False")
        if paid_mode:
            missing = missing_paid_benchmark_env()
            if missing:
                raise RuntimeError("missing_env: " + ", ".join(missing))
        results = [
            self.render_runner.run_case(
                case,
                dry_run_only=dry_run_only,
                cost_gate_mode=cost_gate_mode,
            )
            for case in cases
        ]
        evidence_records = self.evidence_store.load_all() if self.evidence_store is not None else [item.evidence for item in results]
        slices: list[BenchmarkLaunchGateSlice] = []
        for niche, runtime_class in _slice_keys(cases):
            records = [
                record
                for record in evidence_records
                if record.niche == niche and record.runtime_class == runtime_class
            ]
            slices.append(BenchmarkLaunchGateSlice(
                niche=niche,
                runtime_class=runtime_class,
                report=build_launch_gate_report(
                    records=records,
                    min_samples=min_samples,
                    min_usable_rate=min_usable_rate,
                    max_hard_fail_rate=max_hard_fail_rate,
                ),
            ))
        return BenchmarkBatchRunResult(
            dry_run_only=dry_run_only,
            paid_mode=paid_mode,
            case_count=len(cases),
            evidence_path=str(self.evidence_store.path) if self.evidence_store is not None else None,
            results=results,
            launch_gate_reports=slices,
        )


def run_benchmark_case_definitions(
    *,
    case_ids: set[str] | None = None,
    limit: int | None = None,
    evidence_path: str | Path | None = None,
    dry_run_only: bool = True,
    paid_mode: bool = False,
    cost_gate_mode: str = "off",
    min_samples: int = 20,
    min_usable_rate: float = 0.85,
    max_hard_fail_rate: float = 0.10,
) -> BenchmarkBatchRunResult:
    """Compile built-in definitions and run them as a benchmark batch."""
    definitions = load_benchmark_case_definitions()
    if case_ids:
        definitions = [definition for definition in definitions if definition.case_id in case_ids]
    if limit is not None:
        definitions = definitions[:max(0, int(limit))]
    cases = [compile_benchmark_case(definition) for definition in definitions]
    store = BenchmarkEvidenceStore(evidence_path) if evidence_path is not None else None
    return BenchmarkBatchRunner(evidence_store=store).run_cases(
        cases,
        dry_run_only=dry_run_only,
        paid_mode=paid_mode,
        cost_gate_mode=cost_gate_mode,
        min_samples=min_samples,
        min_usable_rate=min_usable_rate,
        max_hard_fail_rate=max_hard_fail_rate,
    )


def missing_paid_benchmark_env(settings_obj: Any = settings) -> list[str]:
    """Return required env vars missing for explicit paid benchmark mode."""
    return missing_secret_names([
        ("ATLASCLOUD_API_KEY", getattr(settings_obj, "atlascloud_api_key", "")),
        ("R2_ACCOUNT_ID", getattr(settings_obj, "r2_account_id", "")),
        ("R2_ACCESS_KEY_ID", getattr(settings_obj, "r2_access_key_id", "")),
        ("R2_SECRET_ACCESS_KEY", getattr(settings_obj, "r2_secret_access_key", "")),
        ("R2_BUCKET_NAME", getattr(settings_obj, "r2_bucket_name", "")),
    ])


def _slice_keys(cases: list[BenchmarkRenderCase]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for case in cases:
        key = (case.niche, case.runtime_class)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


__all__ = [
    "BenchmarkBatchRunResult",
    "BenchmarkBatchRunner",
    "BenchmarkLaunchGateSlice",
    "missing_paid_benchmark_env",
    "run_benchmark_case_definitions",
]
