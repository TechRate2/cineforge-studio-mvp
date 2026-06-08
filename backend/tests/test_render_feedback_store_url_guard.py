from __future__ import annotations

import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core import render_feedback_store
from api.routes.director import _merge_feedback_integrity_into_validation


def test_render_feedback_rejects_explicit_loopback_output_url() -> None:
    with pytest.raises(ValueError, match=r"HTTP\(S\)"):
        render_feedback_store.record_feedback(
            job_id="feedback_loopback_explicit_guard",
            rating="good",
            issue_tags=["good"],
            output_url="http://127.0.0.1:3000/final.mp4",
        )


def test_render_feedback_sanitizes_job_record_loopback_output_url() -> None:
    job_id = "feedback_loopback_job_record_guard"
    path = render_feedback_store._path(job_id)
    if path.exists():
        path.unlink()
    try:
        doc = render_feedback_store.record_feedback(
            job_id=job_id,
            rating="needs_work",
            issue_tags=["prompt_mismatch"],
            job_record={
                "status": "done",
                "mode": "autonomous",
                "output_url": "http://studio.localhost/final.mp4",
            },
        )

        entry = doc["entries"][0]
        assert entry["output_url"] == ""
        assert entry["local_output_path"] == "http://studio.localhost/final.mp4"
    finally:
        if path.exists():
            path.unlink()


def test_render_feedback_rejects_positive_feedback_without_delivery_qa() -> None:
    with pytest.raises(ValueError, match="final delivery QA pass"):
        render_feedback_store.record_feedback(
            job_id="feedback_positive_missing_delivery_qa_guard",
            rating="approved",
            issue_tags=["good"],
            output_url="https://cdn.example.com/final.mp4",
            job_record={
                "status": "done",
                "mode": "autonomous",
                "output_url": "https://cdn.example.com/final.mp4",
            },
        )


def test_render_feedback_rejects_positive_feedback_when_delivery_qa_warns() -> None:
    with pytest.raises(ValueError, match="final delivery QA pass"):
        render_feedback_store.record_feedback(
            job_id="feedback_positive_warn_delivery_qa_guard",
            rating="good",
            issue_tags=["good"],
            output_url="https://cdn.example.com/final.mp4",
            job_record={
                "status": "done",
                "mode": "autonomous",
                "output_url": "https://cdn.example.com/final.mp4",
                "assembly_result": {
                    "final_delivery_qa": {
                        "status": "warn",
                        "warnings": ["final_delivery_presigned_expiry_missing"],
                        "errors": [],
                    }
                },
            },
        )


def test_render_feedback_accepts_positive_feedback_after_clean_delivery_qa() -> None:
    job_id = "feedback_positive_clean_delivery_qa_guard"
    path = render_feedback_store._path(job_id)
    if path.exists():
        path.unlink()
    try:
        doc = render_feedback_store.record_feedback(
            job_id=job_id,
            rating="approved",
            issue_tags=["good"],
            output_url="https://cdn.example.com/final.mp4",
            job_record={
                "status": "done",
                "mode": "autonomous",
                "output_url": "https://cdn.example.com/final.mp4",
                "assembly_result": {
                    "final_delivery_qa": {
                        "status": "pass",
                        "warnings": [],
                        "errors": [],
                    }
                },
            },
        )

        entry = doc["entries"][0]
        assert entry["rating"] == "approved"
        assert entry["delivery_qa_status"] == "pass"
        assert entry["delivery_qa_errors"] == []
        assert entry["delivery_qa_warnings"] == []
        evidence = render_feedback_store.build_feedback_evidence(job_id)
        assert evidence["integrity"]["promotion_safe"] is True
        assert evidence["summary"]["recommended_next_action"] == "eligible_for_controlled_benchmark_review"
    finally:
        if path.exists():
            path.unlink()


def test_render_feedback_rejects_positive_rating_with_issue_tag() -> None:
    with pytest.raises(ValueError, match="positive feedback cannot include issue tags"):
        render_feedback_store.record_feedback(
            job_id="feedback_positive_issue_tag_guard",
            rating="approved",
            issue_tags=["prompt_mismatch"],
            output_url="https://cdn.example.com/final.mp4",
            job_record={
                "status": "done",
                "mode": "autonomous",
                "output_url": "https://cdn.example.com/final.mp4",
                "assembly_result": {
                    "final_delivery_qa": {
                        "status": "pass",
                        "warnings": [],
                        "errors": [],
                    }
                },
            },
        )


def test_render_feedback_rejects_negative_rating_with_good_tag() -> None:
    with pytest.raises(ValueError, match="negative feedback cannot include good tag"):
        render_feedback_store.record_feedback(
            job_id="feedback_negative_good_tag_guard",
            rating="needs_work",
            issue_tags=["good"],
            output_url="https://cdn.example.com/final.mp4",
            job_record={
                "status": "done",
                "mode": "autonomous",
                "output_url": "https://cdn.example.com/final.mp4",
            },
        )


def test_feedback_evidence_flags_legacy_positive_entry_without_clean_delivery_qa() -> None:
    job_id = "feedback_legacy_positive_integrity_guard"
    path = render_feedback_store._path(job_id)
    if path.exists():
        path.unlink()
    try:
        render_feedback_store._write_doc(
            job_id,
            {
                "schema_version": "cinejelly.render_feedback.v1",
                "job_id": job_id,
                "created_at": "2026-06-08T00:00:00+00:00",
                "updated_at": "2026-06-08T00:00:00+00:00",
                "entries": [
                    {
                        "id": "fb_legacy",
                        "created_at": "2026-06-08T00:00:00+00:00",
                        "rating": "approved",
                        "issue_tags": ["prompt_mismatch"],
                        "notes": "",
                        "reviewer": "legacy",
                        "output_url": "https://cdn.example.com/final.mp4",
                        "local_output_path": "",
                    }
                ],
            },
        )

        evidence = render_feedback_store.build_feedback_evidence(job_id)
        assert evidence["integrity"]["promotion_safe"] is False
        assert "entry_0_positive_feedback_has_issue_tags" in evidence["integrity"]["issues"]
        assert "entry_0_positive_feedback_missing_clean_delivery_qa" in evidence["integrity"]["issues"]
        assert evidence["summary"]["has_invalid_positive_evidence"] is True
        assert evidence["summary"]["has_blocking_issue"] is True
        assert evidence["summary"]["recommended_next_action"] == "review_feedback_integrity_before_promotion"
    finally:
        if path.exists():
            path.unlink()


def test_benchmark_validation_preview_preserves_clean_feedback_integrity() -> None:
    validation = {
        "promotion_ready": False,
        "missing_reasons": ["missing_cost_usd"],
    }
    user_feedback = {
        "integrity": {
            "promotion_safe": True,
            "issues": [],
        }
    }

    merged = _merge_feedback_integrity_into_validation(validation, user_feedback)

    assert merged == validation


def test_benchmark_validation_preview_blocks_unsafe_feedback_integrity() -> None:
    validation = {
        "promotion_ready": True,
        "missing_reasons": ["missing_latency_ms"],
    }
    user_feedback = {
        "integrity": {
            "promotion_safe": False,
            "issues": [
                "entry_0_positive_feedback_has_issue_tags",
                "entry_0_positive_feedback_missing_clean_delivery_qa",
            ],
        }
    }

    merged = _merge_feedback_integrity_into_validation(validation, user_feedback)

    assert merged["promotion_ready"] is False
    assert merged["missing_reasons"] == [
        "missing_latency_ms",
        "feedback_integrity_not_safe",
    ]
    assert merged["feedback_integrity"] == user_feedback["integrity"]
