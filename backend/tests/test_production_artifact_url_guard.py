from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.production_artifacts import _agent_readable_report


def test_production_report_sanitizes_loopback_output_url() -> None:
    report = _agent_readable_report(
        {
            "job_id": "job_report_loopback_guard",
            "plan_id": "plan_report_loopback_guard",
            "production_decision": {},
            "runtime_structure": {},
            "production_graph": {},
            "request_meta": {},
            "shot_list": [],
        },
        job_record={
            "status": "done",
            "output_url": "http://localhost:3000/final.mp4",
        },
    )

    assert report["qa_report"]["output_url"] is None
    assert report["qa_report"]["local_output_path"] == "http://localhost:3000/final.mp4"


def test_production_report_preserves_deliverable_output_url() -> None:
    report = _agent_readable_report(
        {
            "job_id": "job_report_public_guard",
            "plan_id": "plan_report_public_guard",
            "production_decision": {},
            "runtime_structure": {},
            "production_graph": {},
            "request_meta": {},
            "shot_list": [],
        },
        job_record={
            "status": "done",
            "output_url": "https://cdn.example.com/final.mp4",
        },
    )

    assert report["qa_report"]["output_url"] == "https://cdn.example.com/final.mp4"
    assert report["qa_report"]["local_output_path"] == ""
