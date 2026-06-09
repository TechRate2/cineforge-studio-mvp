from __future__ import annotations

import pytest

from agent.autonomous_benchmark_runner import run_autonomous_benchmark_batch
from agent.benchmark_evidence_pack_builder import (
    build_benchmark_evidence_pack_from_artifact,
    build_benchmark_result_draft_from_artifact,
)
from agent.benchmark_evidence_validator import REQUIRED_EVIDENCE_KEYS, has_real_output_url
from api.routes.director import _assert_benchmark_payload_is_not_fabricated
from core import autonomous_benchmark_store


def test_dry_run_benchmark_runner_does_not_write_synthetic_output_or_metrics() -> None:
    batch = run_autonomous_benchmark_batch(niches=["beauty"], mode="dry_run", limit=1)
    row = batch["created"][0]
    try:
        assert row["status"] == "planned"
        assert row["output_url"] is None
        assert row["cost_usd"] is None
        assert row["latency_s"] is None
        assert row["evidence"]["mode"] == "dry_run"
        assert row["evidence"]["metadata_only"] is True
    finally:
        autonomous_benchmark_store.delete_result(row["id"])


def test_benchmark_real_output_url_requires_http_url() -> None:
    assert has_real_output_url({"output_url": "https://cdn.example.com/final.mp4"}) is True
    assert has_real_output_url({"output_url": "stub://benchmark/case"}) is False
    assert has_real_output_url({"output_url": "file:///tmp/final.mp4"}) is False
    assert has_real_output_url({"output_url": "final.mp4"}) is False
    assert has_real_output_url({"output_url": "http://localhost:3000/final.mp4"}) is False
    assert has_real_output_url({"output_url": "http://127.9.8.7:3000/final.mp4"}) is False
    assert has_real_output_url({"output_url": "http://studio.localhost/final.mp4"}) is False
    assert has_real_output_url({"output_url": "http://[::1]:3000/final.mp4"}) is False


def test_benchmark_passed_status_requires_promotion_ready_evidence() -> None:
    with pytest.raises(ValueError, match="promotion-ready evidence"):
        _assert_benchmark_payload_is_not_fabricated({
            "case_id": "bench_bad",
            "niche": "beauty",
            "target_market": "vn",
            "runtime_class": "short",
            "model_key": "seedance_2_0",
            "status": "passed",
            "output_url": "https://cdn.example.com/final.mp4",
            "cost_usd": 1.23,
            "latency_s": 45.0,
            "qa_score": 8.6,
            "reviewer_decision": "approved",
            "evidence": {},
        })


def test_benchmark_passed_status_accepts_complete_promotion_evidence() -> None:
    _assert_benchmark_payload_is_not_fabricated({
        "case_id": "bench_good",
        "niche": "beauty",
        "target_market": "vn",
        "runtime_class": "short",
        "model_key": "seedance_2_0",
        "status": "passed",
        "output_url": "https://cdn.example.com/final.mp4",
        "cost_usd": 1.23,
        "latency_s": 45.0,
        "qa_score": 8.6,
        "reviewer_decision": "approved",
        "evidence": {key: {"present": True} for key in REQUIRED_EVIDENCE_KEYS},
    })


def test_benchmark_result_rejects_stub_or_local_output_urls() -> None:
    for output_url in ["stub://benchmark/case", "file:///tmp/final.mp4", "http://127.0.0.1:3000/final.mp4"]:
        with pytest.raises(ValueError, match="real HTTP"):
            _assert_benchmark_payload_is_not_fabricated({
                "status": "needs_review",
                "output_url": output_url,
            })


def test_benchmark_evidence_pack_sanitizes_local_job_output_url() -> None:
    artifact = {
        "job_id": "job_local_pack",
        "planner": {"niche": "food"},
        "runtime_structure": {"runtime_class": "short"},
    }
    job_record = {
        "job_id": "job_local_pack",
        "status": "done",
        "output_url": "file:///tmp/local-final.mp4",
        "output_path": "C:/tmp/local-final.mp4",
    }

    pack = build_benchmark_evidence_pack_from_artifact(artifact, job_record=job_record)
    draft = build_benchmark_result_draft_from_artifact(artifact, job_record=job_record)

    assert pack["output_url"] is None
    assert pack["local_output_path"] == "C:/tmp/local-final.mp4"
    assert draft["output_url"] is None
    assert draft["status"] == "planned"


def test_benchmark_evidence_pack_sanitizes_loopback_job_output_url() -> None:
    artifact = {
        "job_id": "job_loopback_pack",
        "planner": {"niche": "food"},
        "runtime_structure": {"runtime_class": "short"},
    }
    job_record = {
        "job_id": "job_loopback_pack",
        "status": "done",
        "output_url": "http://localhost:3000/local-final.mp4",
    }

    pack = build_benchmark_evidence_pack_from_artifact(artifact, job_record=job_record)
    draft = build_benchmark_result_draft_from_artifact(artifact, job_record=job_record)

    assert pack["output_url"] is None
    assert pack["local_output_path"] == "http://localhost:3000/local-final.mp4"
    assert draft["output_url"] is None
    assert draft["status"] == "planned"


def test_benchmark_store_rejects_local_output_url_direct_writes() -> None:
    with pytest.raises(ValueError, match="real HTTP"):
        autonomous_benchmark_store.create_result(
            case_id="bench_store_local_url",
            niche="beauty",
            target_market="vn",
            runtime_class="short",
            model_key="seedance_2_0",
            status="needs_review",
            output_url="http://localhost:3000/local-final.mp4",
        )


def test_benchmark_store_rejects_passed_status_without_promotion_evidence() -> None:
    row = autonomous_benchmark_store.create_result(
        case_id="bench_store_pass_guard",
        niche="beauty",
        target_market="vn",
        runtime_class="short",
        model_key="seedance_2_0",
        status="planned",
    )
    try:
        with pytest.raises(ValueError, match="promotion-ready evidence"):
            autonomous_benchmark_store.update_result(
                row["id"],
                status="passed",
                output_url="https://cdn.example.com/final.mp4",
                cost_usd=1.23,
                latency_s=45.0,
                qa_score=8.6,
                reviewer_decision="approved",
                evidence={},
            )
    finally:
        autonomous_benchmark_store.delete_result(row["id"])


def test_benchmark_store_accepts_passed_status_with_complete_evidence() -> None:
    row = autonomous_benchmark_store.create_result(
        case_id="bench_store_pass_ok",
        niche="beauty",
        target_market="vn",
        runtime_class="short",
        model_key="seedance_2_0",
        status="planned",
    )
    try:
        updated = autonomous_benchmark_store.update_result(
            row["id"],
            status="passed",
            output_url="https://cdn.example.com/final.mp4",
            cost_usd=1.23,
            latency_s=45.0,
            qa_score=8.6,
            reviewer_decision="approved",
            evidence={key: {"present": True} for key in REQUIRED_EVIDENCE_KEYS},
        )
        assert updated is not None
        assert updated["status"] == "passed"
        assert updated["output_url"] == "https://cdn.example.com/final.mp4"
    finally:
        autonomous_benchmark_store.delete_result(row["id"])
