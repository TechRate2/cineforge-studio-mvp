from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from benchmark.batch_runner import missing_paid_benchmark_env, run_benchmark_case_definitions
from benchmark.cases import compile_benchmark_case, load_benchmark_case_definitions
from benchmark.evidence_store import BenchmarkEvidenceRecord, build_launch_gate_report


def test_benchmark_case_catalog_covers_launch_niches() -> None:
    definitions = load_benchmark_case_definitions()
    niches = {case.niche for case in definitions}

    assert len(definitions) >= 7
    assert {
        "beauty",
        "food",
        "app_saas",
        "fashion",
        "travel_lifestyle",
        "real_estate",
        "drama",
    }.issubset(niches)


def test_benchmark_case_compiles_real_seedance_plan() -> None:
    definition = next(case for case in load_benchmark_case_definitions() if case.case_id == "bench_beauty_product_ugc_12s")

    case = compile_benchmark_case(definition)

    assert case.execution_plan.shots
    assert case.execution_plan.compiled_prompt
    assert case.execution_plan.reference_assets
    assert case.niche == "beauty"
    assert case.runtime_class == "short"


def test_benchmark_batch_runner_writes_dry_run_evidence_without_paid_vendor(tmp_path) -> None:
    evidence_path = tmp_path / "benchmark_evidence.jsonl"

    result = run_benchmark_case_definitions(
        case_ids={"bench_food_restaurant_12s"},
        evidence_path=evidence_path,
        dry_run_only=True,
        min_samples=2,
    )

    assert result.dry_run_only is True
    assert result.paid_mode is False
    assert result.case_count == 1
    assert result.results[0].render_status == "dry_run"
    assert result.results[0].evidence.verdict == "unreviewed"
    assert evidence_path.exists()
    assert "bench_food_restaurant_12s" in evidence_path.read_text(encoding="utf-8")
    assert result.launch_gate_reports[0].report.status == "fail"
    assert "benchmark_insufficient_sample_count" in result.launch_gate_reports[0].report.blockers


def test_benchmark_batch_runner_dry_run_with_references_keeps_approval_lock(tmp_path) -> None:
    evidence_path = tmp_path / "benchmark_reference_evidence.jsonl"

    result = run_benchmark_case_definitions(
        case_ids={"bench_beauty_product_ugc_12s"},
        evidence_path=evidence_path,
        dry_run_only=True,
        min_samples=2,
    )

    assert result.results[0].render_status == "dry_run"
    assert result.results[0].evidence.verdict == "unreviewed"
    assert result.results[0].evidence.failure_reason is None
    assert result.results[0].evidence.metadata["render_message"] == "Dry-run generated; no paid vendor call was made."
    assert evidence_path.exists()


def test_benchmark_cli_accepts_explicit_dry_run_flag(tmp_path) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_benchmark_cases.py"
    evidence_path = tmp_path / "benchmark_cli_evidence.jsonl"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--dry-run",
            "--case-id",
            "bench_food_restaurant_12s",
            "--evidence-path",
            str(evidence_path),
            "--min-samples",
            "2",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["dry_run_only"] is True
    assert payload["paid_mode"] is False
    assert payload["case_count"] == 1
    assert payload["results"][0]["render_status"] == "dry_run"
    assert evidence_path.exists()


def test_benchmark_cli_accepts_limit_for_fast_subset(tmp_path) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_benchmark_cases.py"
    evidence_path = tmp_path / "benchmark_cli_limit_evidence.jsonl"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--dry-run",
            "--limit",
            "2",
            "--evidence-path",
            str(evidence_path),
            "--min-samples",
            "1",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["case_count"] == 2
    assert len(payload["results"]) == 2
    assert evidence_path.exists()


def test_benchmark_launch_gate_passes_high_quality_evidence_slice() -> None:
    report = build_launch_gate_report(
        records=[
            BenchmarkEvidenceRecord(niche="food", runtime_class="short", output_url="https://cdn.example.com/food-1.mp4", cost_usd=0.36, latency_s=36, qa_score=91, human_score=9, verdict="usable"),
            BenchmarkEvidenceRecord(niche="food", runtime_class="short", output_url="https://cdn.example.com/food-2.mp4", cost_usd=0.37, latency_s=37, qa_score=89, human_score=8, verdict="usable"),
            BenchmarkEvidenceRecord(niche="food", runtime_class="short", output_url="https://cdn.example.com/food-3.mp4", cost_usd=0.38, latency_s=38, qa_score=93, human_score=9, verdict="usable"),
        ],
        min_samples=3,
        min_usable_rate=0.80,
        max_hard_fail_rate=0.20,
    )

    assert report.status == "pass"
    assert report.usable_rate == 1.0


def test_paid_benchmark_mode_reports_missing_env() -> None:
    missing = missing_paid_benchmark_env(SimpleNamespace(
        atlascloud_api_key="xxxxxxxxxxxxxxxxxxxxx",
        r2_account_id="",
        r2_access_key_id="your_api_key",
        r2_secret_access_key="<secret>",
        r2_bucket_name="ugc-vietnam-output",
    ))

    assert missing == [
        "ATLASCLOUD_API_KEY",
        "R2_ACCOUNT_ID",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
    ]
