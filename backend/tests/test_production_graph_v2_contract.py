"""Production graph V2 contract tests."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_production_graph_v2_role_stages_and_task_payload_are_persisted() -> None:
    from agent.production_graph import build_production_graph
    from core import production_graph_store

    shot = SimpleNamespace(
        shot_id="S1",
        start_s=0,
        end_s=5,
        duration_s=5,
        purpose="hero product reveal",
        continuity=SimpleNamespace(previous_shot_id=None, reference_indices=[0]),
    )
    graph = build_production_graph(
        plan_id="plan_graph_v2",
        duration_s=5,
        runtime_structure={"runtime_class": "short", "chunk_count": 1},
        shots=[shot],
        prompt_formula={"schema_version": "test", "formula": ["subject", "motion"]},
        reference_contract={"reference_job_policy": {"required_reference_jobs": ["product_hero"]}},
    ).model_dump()

    assert graph["approval_policy"]["paid_render_requires"]
    assert graph["evidence_policy"]["schema_version"] == "cinejelly.production_graph_evidence.v2"
    assert any(node["kind"] == "role_stage" for node in graph["nodes"])

    job_id = f"job_{uuid4().hex}"
    production_graph_store.save_graph(job_id=job_id, plan_id="plan_graph_v2", graph=graph)
    try:
        record = production_graph_store.load_graph(job_id)
        assert record is not None
        batch = production_graph_store.build_execution_batch(record)
        task_payload = batch["tasks"][0]["payload"]
        assert task_payload["prompt_formula"]["schema_version"] == "test"
        assert task_payload["reference_contract"]["required_reference_jobs"] == ["product_hero"]
        assert task_payload["approval_evidence"]["requires_approval_lock"] is True
        resume = production_graph_store.build_resume_plan(record)
        assert resume["approval_policy"]["schema_version"] == "cinejelly.production_graph_approval.v2"
    finally:
        production_graph_store.delete_graph(job_id)
