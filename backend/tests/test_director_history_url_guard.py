from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core import director_history


def test_director_history_does_not_store_local_output_url_as_deliverable() -> None:
    job_id = "test_history_local_output_guard"
    director_history.delete_job(job_id)
    try:
        director_history.record_job(
            job_id=job_id,
            plan_id="plan_history_guard",
            mode="autonomous",
            status="done",
            output_url="file:///tmp/local-final.mp4",
            title="Local only",
            duration_s=12,
            cost_estimate_usd=None,
        )

        item = director_history.get_job(job_id, include_plan=False)

        assert item is not None
        assert item["output_url"] is None
        assert item["local_output_path"] == ""
    finally:
        director_history.delete_job(job_id)


def test_director_history_does_not_store_loopback_output_url_as_deliverable() -> None:
    job_id = "test_history_loopback_output_guard"
    director_history.delete_job(job_id)
    try:
        director_history.record_job(
            job_id=job_id,
            plan_id="plan_history_loopback_guard",
            mode="autonomous",
            status="done",
            output_url="http://localhost:3000/local-final.mp4",
            title="Loopback only",
            duration_s=12,
            cost_estimate_usd=None,
        )

        item = director_history.get_job(job_id, include_plan=False)

        assert item is not None
        assert item["output_url"] is None
        assert item["local_output_path"] == ""
    finally:
        director_history.delete_job(job_id)


def test_director_history_sanitizes_legacy_file_url_rows_on_read() -> None:
    job_id = "test_history_legacy_file_url_guard"
    director_history.delete_job(job_id)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with director_history._LOCK:
            with director_history._conn() as conn:
                conn.execute(
                    """
                    INSERT INTO director_jobs (
                        job_id, plan_id, mode, status, output_url, title,
                        duration_s, cost_estimate_usd, plan_blob, chain_blob,
                        created_at, finished_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        "plan_legacy_guard",
                        "autonomous",
                        "done",
                        "file:///tmp/legacy-final.mp4",
                        "Legacy local",
                        12,
                        None,
                        None,
                        None,
                        now,
                        now,
                    ),
                )

        item = director_history.get_job(job_id, include_plan=False)

        assert item is not None
        assert item["output_url"] is None
        assert item["local_output_path"] == "file:///tmp/legacy-final.mp4"
    finally:
        director_history.delete_job(job_id)


def test_director_history_sanitizes_legacy_loopback_url_rows_on_read() -> None:
    job_id = "test_history_legacy_loopback_url_guard"
    director_history.delete_job(job_id)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with director_history._LOCK:
            with director_history._conn() as conn:
                conn.execute(
                    """
                    INSERT INTO director_jobs (
                        job_id, plan_id, mode, status, output_url, title,
                        duration_s, cost_estimate_usd, plan_blob, chain_blob,
                        created_at, finished_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        "plan_legacy_loopback_guard",
                        "autonomous",
                        "done",
                        "http://127.2.3.4:3000/legacy-final.mp4",
                        "Legacy loopback",
                        12,
                        None,
                        None,
                        None,
                        now,
                        now,
                    ),
                )

        item = director_history.get_job(job_id, include_plan=False)

        assert item is not None
        assert item["output_url"] is None
        assert item["local_output_path"] == "http://127.2.3.4:3000/legacy-final.mp4"
    finally:
        director_history.delete_job(job_id)


def test_director_history_preserves_http_output_url() -> None:
    job_id = "test_history_http_output_guard"
    director_history.delete_job(job_id)
    try:
        director_history.record_job(
            job_id=job_id,
            plan_id="plan_history_http_guard",
            mode="autonomous",
            status="done",
            output_url="https://cdn.example.com/final.mp4",
            title="HTTP output",
            duration_s=12,
            cost_estimate_usd=None,
        )

        item = director_history.get_job(job_id, include_plan=False)

        assert item is not None
        assert item["output_url"] == "https://cdn.example.com/final.mp4"
        assert item["local_output_path"] == ""
    finally:
        director_history.delete_job(job_id)
