"""Production artifact snapshots for autonomous jobs.

Director history stores the final completed job. Long-form autonomous work also
needs an early, inspectable snapshot immediately after planning: screenplay,
scene/chunk/shot graph, reference roles, market/niche playbooks, and producer
strategy. This file-based JSON store is deliberately simple and portable; it can
later be replaced by database-backed production graph tables.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger


_ROOT = Path(__file__).parent.parent / "data" / "production_artifacts"


def save_autonomous_snapshot(
    *,
    job_id: str,
    plan_id: str,
    plan: Any,
    planner_out: Any,
    storyboard_out: Any,
    director_out: Any,
    role_tagger_out: Any,
    editor_meta: Any,
    producer_strategy: dict[str, Any],
    asset_memory: Optional[dict[str, Any]] = None,
    request_meta: dict[str, Any],
) -> dict[str, Any]:
    """Persist one autonomous planning snapshot and return lightweight metadata."""
    _ROOT.mkdir(parents=True, exist_ok=True)
    path = _ROOT / f"{job_id}.json"
    bible = getattr(plan, "continuity_bible", None)
    storytelling_meta = getattr(bible, "storytelling_meta", {}) or {}
    production_graph = storytelling_meta.get("production_graph")
    runtime_structure = storytelling_meta.get("runtime_structure")
    production_decision = request_meta.get("production_decision") if isinstance(request_meta, dict) else None

    payload = {
        "schema_version": "cinejelly.production_artifact.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "job_id": job_id,
        "plan_id": plan_id,
        "request_meta": request_meta,
        "production_decision": production_decision,
        "producer_strategy": producer_strategy,
        "asset_memory": asset_memory or {},
        "director_plan": _dump(plan),
        "planner": _dump(planner_out),
        "storyboard": _dump(storyboard_out),
        "director": _dump(director_out),
        "role_tagger": _dump(role_tagger_out),
        "editor": _dump(editor_meta),
        "continuity_bible": _dump(bible),
        "shot_list": _dump(getattr(plan, "shot_list", [])),
        "runtime_structure": runtime_structure,
        "production_graph": production_graph,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    report = _agent_readable_report(payload)
    report_path = _report_path(job_id)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    summary = _summary(payload)
    logger.info(f"[production_artifacts] saved {job_id} -> {path}")
    return {
        "path": str(path),
        "report_path": str(report_path),
        "schema_version": payload["schema_version"],
        "summary": summary,
    }


def load_snapshot(job_id: str) -> Optional[dict[str, Any]]:
    """Load a snapshot by job id, if present."""
    path = _ROOT / f"{job_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_report(job_id: str, *, job_record: Optional[dict[str, Any]] = None) -> Optional[dict[str, Any]]:
    """Load or build a concise agent-readable production report."""
    report_path = _report_path(job_id)
    if report_path.exists() and not job_record:
        return json.loads(report_path.read_text(encoding="utf-8"))
    snapshot = load_snapshot(job_id)
    if not snapshot:
        return None
    return _agent_readable_report(snapshot, job_record=job_record or {})


def _dump(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, list):
        return [_dump(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _dump(v) for k, v in obj.items()}
    return obj


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    graph = payload.get("production_graph") or {}
    graph_summary = graph.get("summary") if isinstance(graph, dict) else None
    runtime = payload.get("runtime_structure") or {}
    decision = (payload.get("production_decision") or {}).get("decision") or {}
    shots = payload.get("shot_list") or []
    return {
        "runtime_class": decision.get("runtime_class") or runtime.get("runtime_class"),
        "target_duration_s": decision.get("target_duration_s") or runtime.get("target_duration_s"),
        "niche": decision.get("niche"),
        "readiness": decision.get("readiness"),
        "execution_mode": decision.get("execution_mode"),
        "graph_required": decision.get("graph_required"),
        "dialogue_candidate": (
            (decision.get("dialogue_route_policy") or {}).get("dialogue_candidate")
        ),
        "primary_visual_model": (
            (decision.get("primary_model_route") or {}).get("primary_visual_model")
        ),
        "benchmark_required_before_top_tier_claim": decision.get(
            "benchmark_required_before_top_tier_claim"
        ),
        "shot_count": len(shots),
        "scene_count": (graph_summary or {}).get("scene_count"),
        "chunk_count": (graph_summary or {}).get("chunk_count"),
        "node_count": (graph_summary or {}).get("node_count"),
        "risk_level": (payload.get("producer_strategy") or {}).get("risk_level"),
    }


def _report_path(job_id: str) -> Path:
    return _ROOT / f"{job_id}.report.json"


def _agent_readable_report(
    payload: dict[str, Any],
    *,
    job_record: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    job = job_record or {}
    decision_wrap = payload.get("production_decision") if isinstance(payload.get("production_decision"), dict) else {}
    decision = decision_wrap.get("decision") if isinstance(decision_wrap.get("decision"), dict) else {}
    runtime = payload.get("runtime_structure") if isinstance(payload.get("runtime_structure"), dict) else {}
    graph = payload.get("production_graph") if isinstance(payload.get("production_graph"), dict) else {}
    graph_summary = graph.get("summary") if isinstance(graph.get("summary"), dict) else {}
    request_meta = payload.get("request_meta") if isinstance(payload.get("request_meta"), dict) else {}
    preflight = request_meta.get("autonomous_preflight") if isinstance(request_meta.get("autonomous_preflight"), dict) else {}
    reference_allocation = decision_wrap.get("seedance_reference_allocation")
    if not isinstance(reference_allocation, dict):
        reference_allocation = {}
    segment_inspector = decision_wrap.get("seedance_segment_inspector")
    if not isinstance(segment_inspector, dict):
        segment_inspector = {}
    prompt_formula = decision_wrap.get("seedance_prompt_formula")
    if not isinstance(prompt_formula, dict):
        prompt_formula = {}

    return {
        "schema_version": "cinejelly.agent_readable_production_report.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "job_id": payload.get("job_id"),
        "plan_id": payload.get("plan_id"),
        "summary": _summary(payload),
        "storyboard_report": {
            "runtime_class": decision.get("runtime_class") or runtime.get("runtime_class"),
            "scene_count": runtime.get("scene_count") or graph_summary.get("scene_count"),
            "shot_count": len(payload.get("shot_list") or []),
            "sample_shots": _sample_shots(payload.get("shot_list") or []),
        },
        "design_report": {
            "niche": decision.get("niche"),
            "target_market": decision.get("target_market"),
            "primary_visual_model": (decision.get("primary_model_route") or {}).get("primary_visual_model"),
            "dialogue_candidate": (decision.get("dialogue_route_policy") or {}).get("dialogue_candidate"),
            "reference_counts": {
                "images": len(request_meta.get("reference_image_urls") or []),
                "videos": len(request_meta.get("reference_video_urls") or []),
                "audios": len(request_meta.get("reference_audio_urls") or []),
                "pinned_assets": len(request_meta.get("pinned_asset_ids") or []),
            },
            "reference_jobs": _reference_jobs(reference_allocation),
            "seedance_formula": {
                "schema_version": prompt_formula.get("schema_version"),
                "formula": prompt_formula.get("formula"),
                "source_pattern": prompt_formula.get("source_pattern"),
            },
            "segment_preview": {
                "mode": segment_inspector.get("mode"),
                "estimated_total_units": segment_inspector.get("estimated_total_units"),
                "unit_contract": segment_inspector.get("unit_contract"),
            },
        },
        "graph_report": {
            "graph_required": decision.get("graph_required"),
            "execution_mode": decision.get("execution_mode"),
            "graph_id": graph.get("graph_id") or graph.get("id"),
            "node_count": graph_summary.get("node_count") or len(graph.get("nodes") or []),
            "edge_count": graph_summary.get("edge_count") or len(graph.get("edges") or []),
            "scene_count": graph_summary.get("scene_count"),
            "chunk_count": graph_summary.get("chunk_count"),
            "resume_policy": "resume failed or pending graph nodes; do not regenerate accepted shots",
        },
        "qa_report": {
            "preflight_allowed": preflight.get("render_allowed"),
            "preflight_status": preflight.get("status"),
            "hard_failures": preflight.get("hard_failures") or [],
            "warnings": preflight.get("warnings") or [],
            "render_quality_count": len(job.get("render_quality") or []),
            "retry_count": _retry_count(job),
            "final_status": job.get("status"),
            "output_url": job.get("output_url"),
        },
        "benchmark_report": {
            "top_tier_claim_allowed": False,
            "requires_real_output_evidence": True,
            "evidence_endpoint": f"/api/v1/director/jobs/{payload.get('job_id')}/benchmark-evidence-pack",
            "required_next_evidence": [
                "real output_url",
                "QA frames",
                "visual/semantic/text/audio reports",
                "benchmark_review_score",
                "accepted_minute_cost",
                "human reviewer_notes",
            ],
        },
    }


def _sample_shots(shots: list[Any], *, limit: int = 8) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for shot in shots[:limit]:
        if not isinstance(shot, dict):
            continue
        visual = shot.get("visual") if isinstance(shot.get("visual"), dict) else {}
        audio = shot.get("audio") if isinstance(shot.get("audio"), dict) else {}
        continuity = shot.get("continuity") if isinstance(shot.get("continuity"), dict) else {}
        rows.append({
            "shot_id": shot.get("shot_id") or shot.get("id"),
            "purpose": shot.get("purpose"),
            "duration_s": shot.get("duration_s"),
            "subject": visual.get("subject"),
            "action": visual.get("action"),
            "camera": visual.get("camera_shot") or visual.get("camera_movement"),
            "caption": audio.get("caption_on_screen"),
            "reference_indices": continuity.get("reference_indices") or [],
            "previous_shot_id": continuity.get("previous_shot_id"),
        })
    return rows


def _reference_jobs(allocation: dict[str, Any]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for key in ("image_role_plan", "video_role_plan", "audio_role_plan"):
        for item in allocation.get(key) or []:
            if isinstance(item, dict):
                jobs.append({
                    "tag": item.get("tag"),
                    "role": item.get("role"),
                    "job": item.get("job"),
                })
    return jobs[:12]


def _retry_count(job_record: dict[str, Any]) -> int:
    retry_plan = job_record.get("retry_plan") if isinstance(job_record.get("retry_plan"), dict) else {}
    summary = retry_plan.get("summary") if isinstance(retry_plan.get("summary"), dict) else {}
    if summary.get("retry_count") is not None:
        return max(0, int(summary.get("retry_count") or 0))
    retry_execution = job_record.get("retry_execution") if isinstance(job_record.get("retry_execution"), dict) else {}
    results = retry_execution.get("results") if isinstance(retry_execution.get("results"), list) else []
    return len(results)


__all__ = ["save_autonomous_snapshot", "load_snapshot", "load_report"]
