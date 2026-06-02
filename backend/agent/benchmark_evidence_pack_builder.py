"""Build benchmark evidence packs from real production artifacts.

The benchmark store should not be filled by hand from memory after a paid
render. This module extracts the reproducible parts from the production
artifact/job record, while deliberately leaving human/model QA fields absent
when the artifact does not prove them.
"""
from __future__ import annotations

from typing import Any, Optional

from agent.benchmark_evidence_validator import REQUIRED_EVIDENCE_KEYS


def build_benchmark_evidence_pack_from_artifact(
    artifact: dict[str, Any],
    *,
    job_record: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Return a non-promotional evidence draft for a completed production job."""
    job = job_record or {}
    evidence: dict[str, Any] = {}

    per_shot_prompts = _extract_per_shot_prompts(artifact=artifact, job_record=job)
    if per_shot_prompts:
        evidence["per_shot_prompts"] = per_shot_prompts

    prompt_formula = _extract_seedance_prompt_formula(artifact)
    if _has_seedance_prompt_formula(prompt_formula):
        evidence["seedance_prompt_formula"] = prompt_formula

    reference_manifest = _extract_reference_manifest(artifact)
    if _has_reference_manifest(reference_manifest):
        evidence["reference_manifest"] = reference_manifest

    model_route = _extract_model_route_per_shot(artifact=artifact, job_record=job)
    if model_route:
        evidence["model_route_per_shot"] = model_route

    graph_snapshot = _extract_production_graph_snapshot(artifact=artifact, job_record=job)
    if graph_snapshot:
        evidence["production_graph_snapshot"] = graph_snapshot

    scene_memory = _extract_scene_memory_pack(artifact=artifact, job_record=job)
    if scene_memory:
        evidence["scene_memory_pack"] = scene_memory

    continuity_handoff = _extract_continuity_handoff_report(artifact)
    if continuity_handoff:
        evidence["continuity_handoff_report"] = continuity_handoff

    segment_inspector = _extract_seedance_segment_inspector(artifact)
    if segment_inspector:
        evidence["seedance_segment_inspector"] = segment_inspector

    dynamic_keyframe_memory = _extract_dynamic_keyframe_memory(artifact=artifact, job_record=job)
    if dynamic_keyframe_memory:
        evidence["dynamic_keyframe_memory"] = dynamic_keyframe_memory

    qa_frames = _extract_qa_frames(job)
    if qa_frames:
        evidence["qa_frames"] = qa_frames

    visual_reference_report = _extract_visual_reference_similarity_report(job)
    if visual_reference_report:
        evidence["visual_reference_similarity_report"] = visual_reference_report

    semantic_quality_report = _extract_semantic_quality_report(job)
    if semantic_quality_report:
        evidence["semantic_quality_report"] = semantic_quality_report

    text_artifact_report = _extract_text_artifact_report(job)
    if text_artifact_report:
        evidence["text_artifact_report"] = text_artifact_report

    audio_report = _extract_audio_report(job)
    if audio_report:
        evidence["audio_report"] = audio_report

    identity_notes = _extract_identity_product_notes(job)
    if identity_notes:
        evidence["identity_product_notes"] = identity_notes

    reviewer_notes = _extract_reviewer_notes(job)
    if reviewer_notes:
        evidence["reviewer_notes"] = reviewer_notes

    benchmark_review_score = _extract_benchmark_review_score(job)
    if benchmark_review_score:
        evidence["benchmark_review_score"] = benchmark_review_score

    accepted_minute_cost = _extract_accepted_minute_cost(job)
    if accepted_minute_cost:
        evidence["accepted_minute_cost"] = accepted_minute_cost

    production_report = _production_report_refs(artifact=artifact, job_record=job)
    if production_report:
        evidence["agent_readable_production_report"] = production_report

    evidence["retry_count"] = _extract_retry_count(job)

    present = [key for key in REQUIRED_EVIDENCE_KEYS if _present(evidence.get(key))]
    missing = [key for key in REQUIRED_EVIDENCE_KEYS if key not in present]
    return {
        "schema_version": "cinejelly.benchmark_evidence_pack_from_artifact.v1",
        "job_id": artifact.get("job_id") or job.get("job_id"),
        "plan_id": artifact.get("plan_id") or job.get("plan_id"),
        "output_url": job.get("output_url"),
        "status": job.get("status"),
        "production_report": production_report,
        "evidence": evidence,
        "autofilled_evidence_keys": present,
        "missing_evidence_keys": missing,
        "manual_review_required_keys": [
            key for key in missing
            if key in {"qa_frames", "audio_report", "identity_product_notes", "reviewer_notes"}
        ],
        "promotion_safety_note": (
            "This pack only includes fields proven by the artifact/job record. "
            "Do not promote a model route until the benchmark validator reports promotion_ready=true."
        ),
    }


def build_benchmark_result_draft_from_artifact(
    artifact: dict[str, Any],
    *,
    job_record: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Return a benchmark-store compatible draft row from a job artifact."""
    job = job_record or {}
    pack = build_benchmark_evidence_pack_from_artifact(artifact, job_record=job)
    decision = _decision(artifact)
    runtime = artifact.get("runtime_structure") if isinstance(artifact.get("runtime_structure"), dict) else {}
    niche = str(decision.get("niche") or _nested(artifact, "planner", "niche") or "general")
    target_market = str(
        decision.get("target_market")
        or _nested(artifact, "request_meta", "target_market")
        or "auto"
    )
    runtime_class = str(
        decision.get("runtime_class")
        or runtime.get("runtime_class")
        or "short"
    )
    return {
        "case_id": _case_id_for_niche(niche),
        "niche": niche,
        "target_market": target_market,
        "runtime_class": runtime_class,
        "model_key": _primary_model_key(artifact=artifact, job_record=job),
        "status": "needs_review" if job.get("output_url") else "planned",
        "output_url": job.get("output_url"),
        "cost_usd": None,
        "latency_s": None,
        "qa_score": None,
        "reviewer_decision": "unknown",
        "evidence": pack["evidence"],
        "evidence_pack": pack,
    }


def _extract_per_shot_prompts(
    *,
    artifact: dict[str, Any],
    job_record: dict[str, Any],
) -> list[dict[str, Any]]:
    chain_by_shot = {
        str(item.get("shot_id") or ""): item
        for item in _as_list(job_record.get("chain"))
        if isinstance(item, dict)
    }
    shots = _as_list(artifact.get("shot_list") or _nested(artifact, "director_plan", "shot_list"))
    out: list[dict[str, Any]] = []
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        shot_id = str(shot.get("shot_id") or shot.get("id") or f"S{len(out) + 1}")
        visual = shot.get("visual") if isinstance(shot.get("visual"), dict) else {}
        audio = shot.get("audio") if isinstance(shot.get("audio"), dict) else {}
        continuity = shot.get("continuity") if isinstance(shot.get("continuity"), dict) else {}
        chain = chain_by_shot.get(shot_id) or {}
        out.append({
            "shot_id": shot_id,
            "purpose": shot.get("purpose"),
            "duration_s": shot.get("duration_s"),
            "prompt": _first_text(
                chain.get("prompt"),
                shot.get("dynamic_description"),
                _compose_prompt_hint(visual=visual, audio=audio),
            ),
            "negative_prompt": chain.get("negative_prompt"),
            "reference_indices": continuity.get("reference_indices") or [],
            "previous_shot_id": continuity.get("previous_shot_id"),
            "caption_on_screen": audio.get("caption_on_screen"),
        })
    if out:
        return out

    for item in _as_list(job_record.get("chain")):
        if isinstance(item, dict) and item.get("shot_id"):
            out.append({
                "shot_id": item.get("shot_id"),
                "prompt": item.get("prompt") or item.get("render_prompt"),
                "duration_s": item.get("duration_s"),
                "video_url": item.get("video_url"),
            })
    return [item for item in out if _present(item.get("prompt"))]


def _extract_reference_manifest(artifact: dict[str, Any]) -> dict[str, Any]:
    for path in (
        ("continuity_bible", "storytelling_meta", "seedance_reference_allocation", "reference_manifest"),
        ("director_plan", "continuity_bible", "storytelling_meta", "seedance_reference_allocation", "reference_manifest"),
        ("production_decision", "seedance_reference_allocation", "reference_manifest"),
    ):
        manifest = _nested(artifact, *path)
        if isinstance(manifest, dict) and _has_reference_manifest(manifest):
            return manifest

    request_meta = artifact.get("request_meta") if isinstance(artifact.get("request_meta"), dict) else {}
    images = [
        {"tag": f"@image_{i}", "url": url, "role": "user_reference"}
        for i, url in enumerate(_as_list(request_meta.get("reference_image_urls")), start=1)
        if isinstance(url, str) and url.strip()
    ]
    videos = [
        {"tag": f"@video_{i}", "url": url, "role": "motion_reference"}
        for i, url in enumerate(_as_list(request_meta.get("reference_video_urls")), start=1)
        if isinstance(url, str) and url.strip()
    ]
    audios = [
        {"tag": f"@audio_{i}", "url": url, "role": "audio_reference"}
        for i, url in enumerate(_as_list(request_meta.get("reference_audio_urls")), start=1)
        if isinstance(url, str) and url.strip()
    ]
    pinned = _as_list(request_meta.get("pinned_assets"))
    if pinned:
        images.extend([
            {
                "tag": f"@pinned_{i}",
                "url": pin.get("image_url"),
                "role": pin.get("role") or "pinned_asset",
                "asset_id": pin.get("asset_id"),
                "name": pin.get("name"),
            }
            for i, pin in enumerate(pinned, start=1)
            if isinstance(pin, dict)
        ])
    return {
        "images": images,
        "videos": videos,
        "audios": audios,
        "source": "production_artifact.request_meta",
    }


def _extract_seedance_prompt_formula(artifact: dict[str, Any]) -> dict[str, Any]:
    for path in (
        ("continuity_bible", "storytelling_meta", "seedance_prompt_formula"),
        ("director_plan", "continuity_bible", "storytelling_meta", "seedance_prompt_formula"),
        ("production_decision", "seedance_prompt_formula"),
        ("request_meta", "production_decision", "seedance_prompt_formula"),
    ):
        formula = _nested(artifact, *path)
        if isinstance(formula, dict) and _has_seedance_prompt_formula(formula):
            return formula
    return {}


def _extract_model_route_per_shot(
    *,
    artifact: dict[str, Any],
    job_record: dict[str, Any],
) -> list[dict[str, Any]]:
    chain_items = [
        item for item in _as_list(job_record.get("chain"))
        if isinstance(item, dict) and item.get("shot_id")
    ]
    if chain_items:
        return [
            {
                "shot_id": item.get("shot_id"),
                "model_key": item.get("model_key") or _primary_model_key(artifact=artifact, job_record=job_record),
                "render_mode": item.get("render_mode"),
                "chained_from": item.get("chained_from"),
                "video_url": item.get("video_url"),
                "retry_replaced": bool(item.get("retry_replaced")),
            }
            for item in chain_items
        ]

    primary = _primary_model_key(artifact=artifact, job_record=job_record)
    shots = _as_list(artifact.get("shot_list") or _nested(artifact, "director_plan", "shot_list"))
    return [
        {
            "shot_id": shot.get("shot_id") or shot.get("id") or f"S{i}",
            "model_key": _nested(shot, "model_routing", "preferred_model") or primary,
            "render_mode": "planned_route",
            "chained_from": _nested(shot, "continuity", "previous_shot_id"),
        }
        for i, shot in enumerate(shots, start=1)
        if isinstance(shot, dict)
    ]


def _extract_dynamic_keyframe_memory(
    *,
    artifact: dict[str, Any],
    job_record: dict[str, Any],
) -> Optional[dict[str, Any]]:
    for candidate in (
        job_record.get("dynamic_keyframe_memory"),
        _nested(artifact, "continuity_bible", "storytelling_meta", "dynamic_keyframe_memory"),
        _nested(artifact, "director_plan", "continuity_bible", "storytelling_meta", "dynamic_keyframe_memory"),
    ):
        if isinstance(candidate, dict) and candidate.get("schema_version") == "cinejelly.dynamic_keyframe_memory.v1":
            return {
                "schema_version": candidate.get("schema_version"),
                "status": candidate.get("status"),
                "scene_count": candidate.get("scene_count"),
                "shot_count": candidate.get("shot_count"),
                "rendered_anchor_count": len(((candidate.get("memory_bank") or {}).get("rendered_anchors") or [])),
                "bridge_anchor_count": len(((candidate.get("memory_bank") or {}).get("bridge_anchors") or [])),
                "promotion_gate": candidate.get("promotion_gate"),
            }
    return None


def _extract_production_graph_snapshot(
    *,
    artifact: dict[str, Any],
    job_record: dict[str, Any],
) -> Optional[dict[str, Any]]:
    for candidate in (
        artifact.get("production_graph"),
        _nested(artifact, "request_meta", "production_graph"),
        _nested(job_record, "autonomous_meta", "production_graph"),
    ):
        if isinstance(candidate, dict) and candidate:
            nodes = _as_list(candidate.get("nodes"))
            edges = _as_list(candidate.get("edges"))
            return {
                "schema_version": candidate.get("schema_version") or "cinejelly.production_graph_snapshot.v1",
                "graph_id": candidate.get("graph_id") or candidate.get("id"),
                "node_count": candidate.get("node_count") or len(nodes),
                "edge_count": candidate.get("edge_count") or len(edges),
                "ready_count": candidate.get("ready_count"),
                "done_count": candidate.get("done_count"),
                "failed_count": candidate.get("failed_count"),
                "resume_checkpoint": candidate.get("resume_checkpoint") or candidate.get("checkpoint"),
                "runtime_class": candidate.get("runtime_class"),
            }

    graph_status = job_record.get("graph_status") if isinstance(job_record.get("graph_status"), dict) else {}
    if graph_status:
        return {
            "schema_version": "cinejelly.production_graph_snapshot.v1",
            "source": "job_record.graph_status",
            "graph_id": graph_status.get("graph_id"),
            "node_count": graph_status.get("node_count"),
            "done_count": graph_status.get("done_count"),
            "failed_count": graph_status.get("failed_count"),
            "resume_checkpoint": graph_status.get("resume_checkpoint"),
        }
    return None


def _extract_scene_memory_pack(
    *,
    artifact: dict[str, Any],
    job_record: dict[str, Any],
) -> Optional[dict[str, Any]]:
    for candidate in (
        artifact.get("scene_memory_pack"),
        _nested(artifact, "continuity_bible", "storytelling_meta", "scene_memory_pack"),
        _nested(artifact, "director_plan", "continuity_bible", "storytelling_meta", "scene_memory_pack"),
        job_record.get("scene_memory_pack"),
    ):
        if isinstance(candidate, dict) and candidate:
            return candidate

    dynamic = _extract_dynamic_keyframe_memory(artifact=artifact, job_record=job_record)
    if dynamic:
        return {
            "schema_version": "cinejelly.scene_memory_pack_from_dynamic_keyframes.v1",
            "source": "dynamic_keyframe_memory",
            "status": dynamic.get("status"),
            "scene_count": dynamic.get("scene_count"),
            "shot_count": dynamic.get("shot_count"),
            "rendered_anchor_count": dynamic.get("rendered_anchor_count"),
            "bridge_anchor_count": dynamic.get("bridge_anchor_count"),
        }
    return None


def _extract_continuity_handoff_report(artifact: dict[str, Any]) -> Optional[dict[str, Any]]:
    for candidate in (
        artifact.get("continuity_handoff_policy"),
        _nested(artifact, "director_plan", "continuity_handoff_policy"),
        _nested(artifact, "preflight_gate", "continuity_handoff_policy"),
        _nested(artifact, "request_meta", "continuity_handoff_policy"),
    ):
        if isinstance(candidate, dict) and candidate:
            return candidate
    return None


def _extract_seedance_segment_inspector(artifact: dict[str, Any]) -> Optional[dict[str, Any]]:
    for candidate in (
        artifact.get("seedance_segment_inspector"),
        _nested(artifact, "production_decision", "seedance_segment_inspector"),
        _nested(artifact, "request_meta", "production_decision", "seedance_segment_inspector"),
    ):
        if isinstance(candidate, dict) and candidate:
            return candidate
    return None


def _extract_qa_frames(job_record: dict[str, Any]) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    for report in _as_list(job_record.get("render_quality")):
        if not isinstance(report, dict):
            continue
        criteria = report.get("criteria") if isinstance(report.get("criteria"), dict) else {}
        frame_samples = criteria.get("frame_samples") if isinstance(criteria.get("frame_samples"), dict) else {}
        for frame in _as_list(frame_samples.get("frames")):
            if not isinstance(frame, dict):
                continue
            url = frame.get("url") or frame.get("path")
            if url:
                frames.append({
                    "shot_id": criteria.get("shot_id") or frame_samples.get("shot_id"),
                    "url": url,
                    "timestamp_s": frame.get("timestamp_s"),
                    "persist_status": frame.get("persist_status"),
                })
    return frames


def _extract_visual_reference_similarity_report(job_record: dict[str, Any]) -> Optional[dict[str, Any]]:
    return _extract_quality_criteria_report(
        job_record,
        keys=("visual_reference_probe", "visual_reference_similarity_report"),
        source="render_quality.visual_reference_probe",
    )


def _extract_semantic_quality_report(job_record: dict[str, Any]) -> Optional[dict[str, Any]]:
    return _extract_quality_criteria_report(
        job_record,
        keys=("semantic_quality", "semantic_quality_report"),
        source="render_quality.semantic_quality",
    )


def _extract_text_artifact_report(job_record: dict[str, Any]) -> Optional[dict[str, Any]]:
    report = _extract_quality_criteria_report(
        job_record,
        keys=("text_artifact_probe", "text_artifact_report"),
        source="render_quality.text_artifact_probe",
    )
    if report:
        return report
    if job_record.get("text_artifact_report"):
        value = job_record.get("text_artifact_report")
        return value if isinstance(value, dict) else {"source": "job_record.text_artifact_report", "value": value}
    return None


def _extract_quality_criteria_report(
    job_record: dict[str, Any],
    *,
    keys: tuple[str, ...],
    source: str,
) -> Optional[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for report in _as_list(job_record.get("render_quality")):
        if not isinstance(report, dict):
            continue
        criteria = report.get("criteria") if isinstance(report.get("criteria"), dict) else {}
        matched: dict[str, Any] = {}
        for key in keys:
            value = criteria.get(key)
            if isinstance(value, dict) and value:
                matched[key] = value
        if matched:
            items.append({
                "shot_id": criteria.get("shot_id"),
                "quality_status": report.get("status"),
                "quality_score": report.get("score"),
                **matched,
            })
    return {"source": source, "items": items} if items else None


def _extract_audio_report(job_record: dict[str, Any]) -> Optional[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for report in _as_list(job_record.get("render_quality")):
        if not isinstance(report, dict):
            continue
        criteria = report.get("criteria") if isinstance(report.get("criteria"), dict) else {}
        media_probe = criteria.get("media_probe") if isinstance(criteria.get("media_probe"), dict) else {}
        if not media_probe:
            continue
        audio_stream_count = media_probe.get("audio_stream_count")
        if audio_stream_count is not None:
            reports.append({
                "shot_id": criteria.get("shot_id"),
                "audio_stream_count": audio_stream_count,
                "media_probe_status": media_probe.get("status"),
                "duration_s": media_probe.get("duration_s"),
                "warnings": media_probe.get("warnings") or [],
            })
    return {"source": "render_quality.media_probe", "items": reports} if reports else None


def _extract_identity_product_notes(job_record: dict[str, Any]) -> Optional[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for report in _as_list(job_record.get("render_quality")):
        if not isinstance(report, dict):
            continue
        criteria = report.get("criteria") if isinstance(report.get("criteria"), dict) else {}
        visual_probe = criteria.get("visual_reference_probe") if isinstance(criteria.get("visual_reference_probe"), dict) else {}
        semantic = criteria.get("semantic_quality") if isinstance(criteria.get("semantic_quality"), dict) else {}
        if visual_probe or semantic:
            items.append({
                "shot_id": criteria.get("shot_id"),
                "visual_reference_probe": visual_probe,
                "semantic_quality": semantic,
                "quality_status": report.get("status"),
                "quality_score": report.get("score"),
            })
    return {"source": "render_quality", "items": items} if items else None


def _extract_reviewer_notes(job_record: dict[str, Any]) -> Optional[str]:
    notes = job_record.get("reviewer_notes") or job_record.get("human_review_notes")
    return str(notes).strip() if notes else None


def _extract_retry_count(job_record: dict[str, Any]) -> int:
    retry_plan = job_record.get("retry_plan") if isinstance(job_record.get("retry_plan"), dict) else {}
    summary = retry_plan.get("summary") if isinstance(retry_plan.get("summary"), dict) else {}
    if summary.get("retry_count") is not None:
        return max(0, int(summary.get("retry_count") or 0))
    retry_execution = job_record.get("retry_execution") if isinstance(job_record.get("retry_execution"), dict) else {}
    results = retry_execution.get("results") if isinstance(retry_execution.get("results"), list) else []
    return len(results)


def _extract_benchmark_review_score(job_record: dict[str, Any]) -> Optional[dict[str, Any]]:
    score = job_record.get("benchmark_review_score")
    if isinstance(score, dict) and score:
        return score
    evidence = job_record.get("evidence") if isinstance(job_record.get("evidence"), dict) else {}
    score = evidence.get("benchmark_review_score")
    if isinstance(score, dict) and score:
        return score
    return None


def _production_report_refs(
    *,
    artifact: dict[str, Any],
    job_record: dict[str, Any],
) -> Optional[dict[str, Any]]:
    job_id = str(artifact.get("job_id") or job_record.get("job_id") or "").strip()
    if not job_id:
        return None
    return {
        "schema_version": "cinejelly.production_report_reference.v1",
        "job_id": job_id,
        "production_report_url": f"/api/v1/director/jobs/{job_id}/production-report",
        "benchmark_evidence_pack_url": f"/api/v1/director/jobs/{job_id}/benchmark-evidence-pack",
        "artifact_url": f"/api/v1/director/jobs/{job_id}/artifact",
        "purpose": "Use this report to inspect storyboard, design, graph, QA, and resume context before route promotion.",
    }


def _extract_accepted_minute_cost(job_record: dict[str, Any]) -> Optional[dict[str, Any]]:
    existing = job_record.get("accepted_minute_cost")
    if isinstance(existing, dict) and existing:
        return existing
    cost = job_record.get("cost_usd")
    duration = _accepted_duration_s(job_record)
    if cost is None or duration is None or duration <= 0:
        return None
    cost_per_minute = float(cost) / (float(duration) / 60.0)
    return {
        "schema_version": "cinejelly.accepted_minute_cost.v1",
        "cost_usd": float(cost),
        "accepted_duration_s": float(duration),
        "cost_per_finished_minute_usd": round(cost_per_minute, 4),
        "includes_retries": True,
    }


def _accepted_duration_s(job_record: dict[str, Any]) -> Optional[float]:
    for key in ("accepted_duration_s", "duration_s", "final_duration_s"):
        value = job_record.get(key)
        if value is not None:
            return float(value)
    media_reports: list[float] = []
    for report in _as_list(job_record.get("render_quality")):
        if not isinstance(report, dict):
            continue
        criteria = report.get("criteria") if isinstance(report.get("criteria"), dict) else {}
        media_probe = criteria.get("media_probe") if isinstance(criteria.get("media_probe"), dict) else {}
        if media_probe.get("duration_s") is not None:
            media_reports.append(float(media_probe.get("duration_s") or 0))
    return sum(media_reports) if media_reports else None


def _primary_model_key(*, artifact: dict[str, Any], job_record: dict[str, Any]) -> str:
    return str(
        job_record.get("resolved_model")
        or _nested(job_record, "autonomous_meta", "resolved_model")
        or _nested(artifact, "request_meta", "resolved_model")
        or _nested(_decision(artifact), "primary_model_route", "primary_visual_model")
        or "seedance_2_0_fast_ref"
    )


def _decision(artifact: dict[str, Any]) -> dict[str, Any]:
    production_decision = artifact.get("production_decision")
    if isinstance(production_decision, dict):
        decision = production_decision.get("decision")
        if isinstance(decision, dict):
            return decision
    request_decision = _nested(artifact, "request_meta", "production_decision", "decision")
    return request_decision if isinstance(request_decision, dict) else {}


def _case_id_for_niche(niche: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(niche).lower()).strip("_")
    return f"bench_{safe or 'general'}"


def _nested(obj: Any, *keys: str) -> Any:
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _compose_prompt_hint(*, visual: dict[str, Any], audio: dict[str, Any]) -> str:
    parts = [
        visual.get("subject"),
        visual.get("action"),
        visual.get("camera_shot"),
        visual.get("camera_movement"),
        visual.get("background"),
        audio.get("music_cue"),
    ]
    return "; ".join(str(part).strip() for part in parts if str(part or "").strip())


def _first_text(*values: Any) -> Optional[str]:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _has_reference_manifest(manifest: dict[str, Any]) -> bool:
    return any(_as_list(manifest.get(key)) for key in ("images", "videos", "audios"))


def _has_seedance_prompt_formula(formula: dict[str, Any]) -> bool:
    return (
        isinstance(formula, dict)
        and str(formula.get("schema_version") or "") == "cinejelly.seedance_prompt_formula.v1"
        and _present(formula.get("formula"))
    )


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


__all__ = [
    "build_benchmark_evidence_pack_from_artifact",
    "build_benchmark_result_draft_from_artifact",
]
