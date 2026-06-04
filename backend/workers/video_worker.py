"""Video Worker V3 — Director Plan render orchestrator.

Sprint3 B3: exposes `cleanup_failed_job(job_id)` so the route layer can drop
the per-job work_dir on render failure — original C6 design only cleaned the
success path, leaving ~500MB/failed-job stranded in tempfile.

Replaces the linear render_pipeline path for Director Agent V3.

Pipeline:
    1. Receive DirectorPlan (Continuity Bible + Shot List + storyboard)
    2. Scene Generation Agent → N SceneRenderJobs (1 per shot)
    3. Reference Chaining loop:
        - shot[0]: ref_to_video using bound references
        - shot[i] (i>0, has previous_shot_id): i2v using shot[i-1].last_frame_url
        - shot[i] (i>0, no chain — intentional cut): ref_to_video with fresh refs
    4. Download all clips → temp dir
    5. AssembleWorker FFmpeg concat + color consistency pass + (optional) audio
    6. Upload R2 → public URL

Universal Reference: every bible.reference_assets[].url is part of a pool. Scene Gen
binds per-shot refs via continuity_manager.references_for_shot().

Reference Chaining: when a shot's continuity.previous_shot_id is set AND the previous
render returned a last_frame_url, this worker switches the model to i2v variant and
passes the prior last frame as image input — identity stays 100% across the chain.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Any, TYPE_CHECKING

import httpx
from loguru import logger

from agent.schemas import DirectorPlan, Shot
from agent import continuity_manager, scene_generation_agent
from agent.render_quality_gate import build_render_quality_report
from agent.media_quality_probe import probe_media_file, sample_video_frames
from agent.semantic_quality_evaluator import evaluate_render_frames
from agent.text_artifact_probe import probe_text_artifacts
from agent.visual_reference_probe import probe_visual_reference_similarity
from agent.render_retry_planner import build_retry_plan
from agent.render_retry_executor import prepare_retry_execution
from agent.model_specs import get_user_model_cost_rate, resolve_video_model_variant
from vendors.atlascloud import atlas_client
from vendors import r2_storage
from workers.assemble_worker import AssembleWorker
from workers import cost_gate
from core import director_history, production_graph_store

if TYPE_CHECKING:
    from pipeline.approval_lock import ApprovalLock
    from pipeline.contracts import SeedanceExecutionPlan
    from longform.contracts import LongFormExecutionPlan


# ============================================================
# V5.16 Fix#3 — Centralize render cost rates (was duplicated in 2 places).
# Source: verified against backend/agent/model_specs.py:cost_per_second_usd
# (2026-05-20). Update here when AtlasCloud changes pricing.
# ============================================================
def get_render_cost_rate(user_model: str) -> float:
    """Return $/s render rate from the authoritative model_specs registry."""
    return get_user_model_cost_rate(user_model)


# ============================================================
# Model routing — user_model → AtlasCloud spec key per render mode
# SEEDANCE 2.0 CORE PATH: ref → reference-to-video, i2v → image-to-video
# FALLBACK PATH (Wan 2.7): only i2v endpoint available
# ============================================================
def _resolve_models(user_model: str) -> tuple[str, str]:
    """Return (ref_key, i2v_key) for a user model choice."""
    return (
        resolve_video_model_variant(user_model, "ref"),
        resolve_video_model_variant(user_model, "i2v"),
    )


def _resolve_t2v_model(user_model: str) -> str:
    """Return text-to-video concrete key for a user model choice."""
    return resolve_video_model_variant(user_model, "t2v")


# ============================================================
# Public entry
# ============================================================
# ============================================================
# V6.1 — Autonomous mode convenience wrapper
# ============================================================
async def render_autonomous(
    job_id: str,
    user_idea: str,
    reference_image_urls: list[str],
    *,
    reference_video_urls: Optional[list[str]] = None,
    reference_audio_urls: Optional[list[str]] = None,
    target_platform: str = "tiktok",
    target_market: str = "auto",
    duration_hint_s: Optional[int] = None,
    user_model: str = "auto",
    resolution: str = "720p",
    jobs_store: Optional[dict] = None,
) -> dict:
    """End-to-end autonomous flow — 1 user idea + refs → rendered video.

    Chain: AutonomousDirector (5 skills) → render_plan() → MP4.
    Returns the same dict as render_plan() PLUS editor_meta (caption, hashtag,
    transitions) for FE post-render display.
    """
    from agent.autonomous_director import AutonomousDirector, AutonomousRunRequest

    director_chain = AutonomousDirector()
    result = await director_chain.run(AutonomousRunRequest(
        user_idea=user_idea,
        reference_image_urls=reference_image_urls,
        reference_video_urls=reference_video_urls or [],
        reference_audio_urls=reference_audio_urls or [],
        target_platform=target_platform,
        target_market=target_market,
        duration_hint_s=duration_hint_s,
        user_model=user_model,
    ))

    # Render the DirectorPlan via existing pipeline (backward-compat path)
    render_result = await render_plan(
        job_id=job_id,
        plan=result.director_plan,
        reference_images=reference_image_urls,
        reference_videos=reference_video_urls or [],
        reference_audios=reference_audio_urls or [],
        user_model=result.director_out.user_model,
        resolution=resolution,
        audio_plan=None,
        jobs_store=jobs_store,
        use_llm_scene_gen=True,
        cost_gate_mode="off",
    )

    # Merge editor meta into output
    render_result["editor_meta"] = result.editor_meta.model_dump()
    render_result["autonomous_meta"] = {
        "elapsed_chain_s": result.elapsed_s,
        "render_strategy": result.director_out.render_strategy,
        "n_chunks": result.director_out.n_chunks,
        "resolved_model": result.director_out.user_model,
        "target_market": target_market,
        "viral_hook_pattern": result.planner_out.hook_pattern,
        "hook_first_3s": result.planner_out.hook_first_3s,
    }
    return render_result


async def render_seedance_execution_plan(
    execution_plan: "SeedanceExecutionPlan",
    approval_lock: "ApprovalLock",
    *,
    jobs_store: Optional[dict] = None,
    dry_run_only: bool = False,
    cost_gate_mode: str = "off",
    max_total_cost_usd: Optional[float] = None,
) -> dict:
    """Phase 3 safe render entrypoint for SeedanceExecutionPlan + ApprovalLock.

    This path is intentionally separate from the legacy DirectorPlan renderer.
    It enforces ApprovalLock through RenderExecutor before any paid vendor call.
    """
    from pipeline.render_execution import RenderExecutor

    job_id = str(getattr(execution_plan, "execution_plan_id", "") or "seedance_execution")
    _update_job(
        jobs_store,
        job_id,
        status="dry_run" if dry_run_only else "rendering",
        current_step="approval_lock_verify",
        progress=5,
    )
    result = await asyncio.to_thread(
        RenderExecutor().execute,
        execution_plan=execution_plan,
        approval_lock=approval_lock,
        dry_run_only=dry_run_only,
        cost_gate_mode=cost_gate_mode,
        max_total_cost_usd=max_total_cost_usd,
    )
    final_status = "done" if result.status == "completed" else result.status
    success_statuses = {"dry_run", "completed"}
    _update_job(
        jobs_store,
        job_id,
        status=final_status,
        current_step="done" if result.status in success_statuses else result.status,
        progress=100 if result.status in success_statuses else 10,
        render_execution=result.model_dump(mode="json"),
        output_url=_first_seedance_output_url(result),
        output_path=_first_seedance_output_url(result),
        error_message=None if result.status in success_statuses else result.message,
    )
    return result.model_dump(mode="json")


async def render_longform_execution_plan(
    longform_plan: "LongFormExecutionPlan",
    approval_lock: "ApprovalLock",
    *,
    idea: str,
    editor_preview: dict[str, Any] | None = None,
    jobs_store: Optional[dict] = None,
    trace: Any | None = None,
    dry_run_only: bool = False,
    dry_run_approved: bool = False,
) -> dict:
    """Phase 10 safe render entrypoint for long-form segmented plans.

    The worker reuses the Phase 9A LongFormRenderExecutor, then assembles the
    completed segment videos into one final MP4. Paid rendering is still gated
    by the single master ApprovalLock inside LongFormRenderExecutor.
    """
    from workers.final_assembly import FinalVideoAssemblyService
    from workers.longform_render_executor import LongFormRenderExecutor
    from monitoring import longform_monitor

    job_id = str(getattr(longform_plan, "longform_plan_id", "") or "longform_execution")
    master_plan = getattr(longform_plan, "master_execution_plan", None)
    cost_estimate = getattr(master_plan, "cost_estimate", {}) or {}
    longform_monitor.record_job_started(
        job_id=job_id,
        segment_count=len(longform_plan.segments),
        model=str(getattr(master_plan, "model", "") or "seedance_2_0"),
        cost_estimate=cost_estimate,
        metadata={
            "longform_plan_id": job_id,
            "continuity_pressure": getattr(getattr(longform_plan, "continuity_bible", None), "continuity_pressure", None),
        },
    )
    _update_job(
        jobs_store,
        job_id,
        status="dry_run" if dry_run_only else "rendering",
        current_step="longform_approval_lock_verify",
        progress=5,
        longform_progress={
            "segment_count": len(longform_plan.segments),
            "completed_segments": 0,
            "current_segment_id": None,
            "events": [],
        },
    )

    def progress_callback(event: dict[str, object]) -> None:
        try:
            longform_monitor.record_segment_event(job_id=job_id, event=event)
        except Exception:
            logger.warning("[LongFormMonitor] segment event record failed", exc_info=True)
        current = dict((jobs_store or {}).get(job_id, {}).get("longform_progress") or {})
        events = list(current.get("events") or [])
        events.append(event)
        segment_count = int(event.get("segment_count") or len(longform_plan.segments) or 1)
        completed = len({
            str(item.get("segment_id"))
            for item in events
            if item.get("event") == "segment_completed" and item.get("segment_id")
        })
        base_progress = 10
        segment_progress = int((completed / max(1, segment_count)) * 75)
        _update_job(
            jobs_store,
            job_id,
            status="rendering",
            current_step=str(event.get("current_step") or event.get("event") or "longform_rendering"),
            progress=min(88, base_progress + segment_progress),
            longform_progress={
                "segment_count": segment_count,
                "completed_segments": completed,
                "current_segment_id": event.get("segment_id"),
                "last_event": event,
                "events": events[-30:],
            },
        )

    executor = LongFormRenderExecutor()
    if dry_run_only:
        result = await asyncio.to_thread(
            executor.dry_run,
            longform_plan=longform_plan,
            approval_lock=approval_lock,
            idea=idea,
            trace=trace,
        )
        _update_job(
            jobs_store,
            job_id,
            status="dry_run",
            current_step="longform_dry_run_ready",
            progress=100,
            longform_render_execution=result.model_dump(mode="json"),
            render_execution=result.model_dump(mode="json"),
            pipeline_trace=trace.model_dump(mode="json") if hasattr(trace, "model_dump") else None,
            error_message=None if result.status == "dry_run" else result.message,
        )
        return result.model_dump(mode="json")

    result = await asyncio.to_thread(
        executor.execute,
        longform_plan=longform_plan,
        approval_lock=approval_lock,
        idea=idea,
        dry_run_approved=dry_run_approved,
        trace=trace,
        progress_callback=progress_callback,
    )
    if result.status != "completed":
        _record_longform_monitoring_qa(job_id=job_id, result=result)
        alerts = longform_monitor.record_job_finished(job_id=job_id, status="failed", error=result.message)
        if hasattr(trace, "append_stage"):
            trace.append_stage(
                stage="longform_monitoring",
                stage_input={"job_id": job_id, "status": result.status},
                stage_output={"alerts": [alert.model_dump(mode="json") for alert in alerts]},
                decision="long-form monitoring recorded failed terminal state",
                reasoning_summary="Monitoring captured long-form failure metrics and alert state.",
                rules_applied=["phase13.monitoring.longform_terminal_state"],
                warnings=[alert.message for alert in alerts],
                cost_estimate=cost_estimate,
            )
        _update_job(
            jobs_store,
            job_id,
            status="failed",
            current_step=result.status,
            progress=100,
            longform_render_execution=result.model_dump(mode="json"),
            render_execution=result.model_dump(mode="json"),
            pipeline_trace=trace.model_dump(mode="json") if hasattr(trace, "model_dump") else None,
            error_message=result.message,
        )
        return result.model_dump(mode="json")

    _record_longform_monitoring_qa(job_id=job_id, result=result)
    _update_job(
        jobs_store,
        job_id,
        status="assembling",
        current_step="final_video_assembly",
        progress=92,
        longform_render_execution=result.model_dump(mode="json"),
        render_execution=result.model_dump(mode="json"),
        pipeline_trace=trace.model_dump(mode="json") if hasattr(trace, "model_dump") else None,
    )
    assembly = await asyncio.to_thread(
        FinalVideoAssemblyService().assemble,
        job_id=job_id,
        longform_plan_id=longform_plan.longform_plan_id,
        render_result=result,
        editor_preview=editor_preview or {},
    )
    if hasattr(trace, "append_stage"):
        trace.append_stage(
            stage="longform_final_assembly",
            stage_input=result,
            stage_output=assembly,
            decision="final assembly uploaded" if assembly.status == "completed" else "final assembly failed",
            reasoning_summary=(
                "Completed long-form segments were concatenated into one MP4 and uploaded to R2/S3."
                if assembly.status == "completed"
                else "Final assembly or R2/S3 upload failed before delivery."
            ),
            rules_applied=["phase10.final_assembly.concat_segments", "phase10.final_assembly.r2_storage_strategy"],
            warnings=[assembly.error] if assembly.error else [],
        )
    if assembly.status != "completed":
        upload_alert = longform_monitor.record_upload_result(
            job_id=job_id,
            success=False,
            storage_key=assembly.storage_key,
            error=assembly.error,
        )
        alerts = longform_monitor.record_job_finished(job_id=job_id, status="failed", error=assembly.error)
        if upload_alert is not None:
            alerts.insert(0, upload_alert)
        if hasattr(trace, "append_stage"):
            trace.append_stage(
                stage="longform_monitoring",
                stage_input={"job_id": job_id, "status": "final_video_assembly_failed"},
                stage_output={"alerts": [alert.model_dump(mode="json") for alert in alerts]},
                decision="long-form monitoring recorded assembly failure",
                reasoning_summary="Monitoring captured final assembly/R2 upload failure and terminal job state.",
                rules_applied=["phase13.monitoring.r2_upload_failure_alert"],
                warnings=[alert.message for alert in alerts],
                cost_estimate=cost_estimate,
            )
        _update_job(
            jobs_store,
            job_id,
            status="failed",
            current_step="final_video_assembly_failed",
            progress=100,
            assembly_result=assembly.model_dump(mode="json"),
            pipeline_trace=trace.model_dump(mode="json") if hasattr(trace, "model_dump") else None,
            error_message=assembly.error or "Final video assembly failed.",
        )
        return {
            **result.model_dump(mode="json"),
            "assembly_result": assembly.model_dump(mode="json"),
        }

    longform_monitor.record_upload_result(
        job_id=job_id,
        success=True,
        storage_key=assembly.storage_key,
    )
    alerts = longform_monitor.record_job_finished(job_id=job_id, status="completed")
    if hasattr(trace, "append_stage"):
        state = longform_monitor.load_job_state(job_id) or {}
        trace.append_stage(
            stage="longform_monitoring",
            stage_input={"job_id": job_id},
            stage_output={
                "status": state.get("status"),
                "duration_ms": state.get("duration_ms"),
                "completed_segments": state.get("completed_segments"),
                "alerts": [alert.model_dump(mode="json") for alert in alerts],
            },
            decision="long-form monitoring recorded completed terminal state",
            reasoning_summary="Monitoring captured segment timings, QA scores, upload status, and terminal job duration.",
            rules_applied=["phase13.monitoring.longform_job_metrics"],
            warnings=[alert.message for alert in alerts],
            cost_estimate=cost_estimate,
        )
    _update_job(
        jobs_store,
        job_id,
        status="done",
        current_step="done",
        progress=100,
        assembly_result=assembly.model_dump(mode="json"),
        pipeline_trace=trace.model_dump(mode="json") if hasattr(trace, "model_dump") else None,
        monitoring_state=longform_monitor.load_job_state(job_id),
        output_url=assembly.final_video_url,
        output_path=assembly.final_video_url,
        editor_meta=editor_preview or {},
        error_message=None,
    )
    return {
        **result.model_dump(mode="json"),
        "assembly_result": assembly.model_dump(mode="json"),
    }


def _record_longform_monitoring_qa(*, job_id: str, result: Any) -> None:
    """Record post-render QA scores for monitoring without failing render flow."""
    try:
        from monitoring import longform_monitor

        for report in getattr(result, "qa_reports", []) or []:
            visual = getattr(report, "visual_consistency", None)
            score = getattr(visual, "overall_score", None) if visual is not None else getattr(report, "consistency_score", None)
            action = getattr(visual, "action", None) if visual is not None else getattr(report, "consistency_policy_action", None)
            warnings = list(getattr(report, "warnings", []) or []) + list(getattr(report, "consistency_warnings", []) or [])
            longform_monitor.record_consistency_score(
                job_id=job_id,
                segment_id=str(getattr(report, "shot_id", "") or "segment"),
                score=score,
                action=action,
                warnings=[str(item) for item in warnings],
            )
    except Exception:
        logger.warning("[LongFormMonitor] QA metric record failed", exc_info=True)


def _first_seedance_output_url(result: Any) -> Optional[str]:
    """Return the first rendered segment URL from a RenderExecutionResult."""
    for segment in getattr(result, "rendered_segments", []) or []:
        url = getattr(segment, "video_url", None)
        if url:
            return str(url)
    return None


async def render_plan(
    job_id: str,
    plan: DirectorPlan,
    reference_images: list[str],
    user_model: str,
    resolution: str,
    reference_videos: Optional[list[str]] = None,
    reference_audios: Optional[list[str]] = None,
    audio_plan: Optional[dict] = None,
    jobs_store: Optional[dict] = None,
    use_llm_scene_gen: bool = True,
    cost_gate_mode: str = "off",
    cost_gate_threshold: float = 7.0,
    master_board_url: Optional[str] = None,
) -> dict:
    """Render a full DirectorPlan → final MP4.

    Args:
        job_id: UUID for tracking.
        plan: Validated DirectorPlan from Director Agent V3.
        reference_images: Full ordered list of uploaded refs (universal pool).
        user_model: seedance_2_0 / seedance_2_0_fast / wan_2_7 / auto
        resolution: 720p / 1080p / ...
        audio_plan: Optional {mode, voice_audio_url, sfx_audio_url, caption_text_vn}.
        jobs_store: Optional in-memory job state dict.
        use_llm_scene_gen: True = Scene Generation Agent LLM call per shot.
                           False = deterministic prompt build (no LLM, faster).
        cost_gate_mode: "off" (default) renders the full plan immediately.
                        "draft_first" renders shot[0] using the Fast tier first,
                        evaluates it against the Bible, then proceeds to render
                        the remaining N-1 shots ONLY if score >= threshold.
                        On fail, the job is marked `failed` with suggestions
                        and the user is invited to refine the plan.
        cost_gate_threshold: 0-10 score required to pass the gate (default 7.0).

    Returns:
        {output_path, output_url, scene_count, total_duration_s, chain, cost_gate?}
    """
    bible = plan.continuity_bible
    shots = plan.shot_list
    reference_videos = list((reference_videos or [])[:3])
    reference_audios = list((reference_audios or [])[:3])

    # BUG #5 fix — "auto" giờ thật sự pick model dựa trên plan (heuristic).
    # Trước đó hardcode về seedance_2_0, không xứng với label "Auto".
    if user_model == "auto":
        from agent.model_picker import pick_model_for_plan
        picked, reasoning = pick_model_for_plan(plan, budget_tier="balanced")
        logger.info(f"[VideoWorker V3] auto-pick → {picked}: {reasoning}")
        # Sprint2 M12 — re-compute cost estimate against the ACTUAL picked model
        # (plan.cost_estimate was built using the original user_model 'auto'
        # original $0.060/s heuristic, which can be off-by-2x for premium models).
        rate = get_render_cost_rate(picked)
        total_dur = sum(s.duration_s for s in shots)
        new_render_cost = round(rate * total_dur, 3)
        old_render_cost = plan.cost_estimate.render_cost_usd
        plan.cost_estimate.render_cost_usd = new_render_cost
        plan.cost_estimate.total_cost_usd = round(
            plan.cost_estimate.plan_cost_usd
            + plan.cost_estimate.storyboard_gen_cost_usd
            + new_render_cost
            + plan.cost_estimate.audio_cost_usd,
            3,
        )
        if abs(new_render_cost - old_render_cost) > 0.1:
            logger.warning(
                f"[VideoWorker V3] auto-pick cost re-estimate: render "
                f"${old_render_cost} → ${new_render_cost} (Δ ${new_render_cost - old_render_cost:+.2f}) "
                f"after picking {picked}"
            )
        _update_job(
            jobs_store, job_id,
            auto_pick={
                "model": picked,
                "reasoning": reasoning,
                "render_cost_usd_recomputed": new_render_cost,
            },
        )
        user_model = picked

    ref_key_default, i2v_key_default = _resolve_models(user_model)
    t2v_key_default = _resolve_t2v_model(user_model)

    # V5.15.4 B1 — Snap shot durations to the model's discrete options BEFORE
    # TTS pre-render so audio length matches the duration the vendor will
    # actually render. Without this, Wan 2.7 plans with non-discrete shots
    # (e.g. 7s) end up with 7s TTS + 5s video → mouth motion mis-syncs and
    # dialogue clips. Idempotent for models with continuous durations.
    snap_warnings = continuity_manager.snap_discrete_durations(plan, user_model)
    for w in snap_warnings:
        logger.warning(f"[VideoWorker B1] {job_id} {w}")
    if snap_warnings:
        shots = plan.shot_list  # refresh local reference after mutation
        # V5.15.5 L1 — Recompute cost_estimate so director_history and any
        # downstream poller sees the actual billed cost (snapped duration
        # × per-second rate). Without this, plan.cost_estimate keeps the
        # pre-snap render_cost which over-quotes by up to 2× on Wan 2.7.
        rate = get_render_cost_rate(user_model)
        snapped_total_dur = sum(s.duration_s for s in plan.shot_list)
        new_render_cost = round(rate * snapped_total_dur, 3)
        plan.cost_estimate.render_cost_usd = new_render_cost
        plan.cost_estimate.total_cost_usd = round(
            plan.cost_estimate.plan_cost_usd
            + plan.cost_estimate.storyboard_gen_cost_usd
            + new_render_cost
            + plan.cost_estimate.audio_cost_usd,
            3,
        )
        logger.info(
            f"[VideoWorker L1] {job_id} snap → cost recomputed: "
            f"render ${new_render_cost} (total ${plan.cost_estimate.total_cost_usd}) "
            f"for {snapped_total_dur}s @ ${rate}/s"
        )

    # V4 Sprint1 Task F — Auto pre-render dialogue TTS per-shot when:
    #   audio_plan.mode == "dialogue_vo" AND no driven_audio_urls/voice_audio_url yet
    # Wan 2.7 i2v will auto-receive the per-shot URL via shot.audio.dialogue_vn
    # → lip-sync khớp môi VN. The assemble layer also gets per-shot voice clips
    # for the new audio_timeline builder (per-shot start_s sync).
    if audio_plan and audio_plan.get("mode") == "dialogue_vo":
        already_has = bool(
            audio_plan.get("driven_audio_urls")
            or audio_plan.get("voice_audio_url")
        )
        if not already_has:
            try:
                tts_map = await _pre_render_dialogue_tts(
                    job_id=job_id, shots=list(shots),
                    voice_persona=(bible.characters[0].voice_persona if bible.characters else None),
                    user_model=user_model,
                )
                if tts_map:
                    audio_plan = {**audio_plan, "driven_audio_urls": tts_map}
                    logger.info(
                        f"[VideoWorker V4] {job_id} auto-prerendered {len(tts_map)} TTS clip(s)"
                    )
            except Exception as e:
                logger.warning(
                    f"[VideoWorker V4] {job_id} TTS pre-render fail (continuing silent): {e}"
                )

    # ---- Optional Cost Gate (Stage 0) ----------------------------------------
    # Render shot[0] with the Fast tier, then eval. If pass → continue with the
    # user's chosen model for the rest. If fail → fail-fast, save 80-90% spend.
    cost_gate_outcome: Optional[dict] = None
    if cost_gate_mode == "draft_first" and len(shots) > 0:
        _update_job(jobs_store, job_id, status="rendering", progress=5,
                    current_step="cost_gate_draft")
        draft_user_model = cost_gate.draft_model_for(user_model)
        draft_ref_key, _ = _resolve_models(draft_user_model)
        draft_shot = shots[0]

        draft_job = await asyncio.to_thread(
            scene_generation_agent.generate_scene,
            bible=bible,
            shot=draft_shot,
            model_key=draft_ref_key,
            reference_images=reference_images,
            reference_videos=reference_videos,
            reference_audios=reference_audios,
            last_frame_url=None,
            llm_mode=use_llm_scene_gen,
            resolution=resolution,
            is_last_shot=False,
        )
        try:
            draft_result = await asyncio.to_thread(
                atlas_client.generate_video, **draft_job.to_atlas_kwargs()
            )
        except Exception as e:
            logger.warning(f"[cost_gate] draft render fail — skipping gate: {e}")
            draft_result = None

        if draft_result and draft_result.get("video_url"):
            decision = await asyncio.to_thread(
                cost_gate.evaluate_draft_clip,
                plan_dict=plan.model_dump(),
                draft_shot_id=draft_shot.shot_id,
                threshold=cost_gate_threshold,
            )
            cost_gate_outcome = {
                "passed": decision.pass_,
                "score": decision.score,
                "threshold": decision.threshold,
                "reasoning": decision.reasoning,
                "suggestions": decision.suggestions,
                "draft_model": draft_user_model,
                "draft_video_url": draft_result["video_url"],
            }
            _update_job(jobs_store, job_id, cost_gate=cost_gate_outcome)
            logger.info(
                f"[cost_gate] {job_id} draft score={decision.score} "
                f"threshold={decision.threshold} → {'PASS' if decision.pass_ else 'FAIL'}"
            )
            if not decision.pass_:
                _update_job(
                    jobs_store, job_id,
                    status="failed", progress=10, current_step="cost_gate_failed",
                    error_message=(
                        f"Cost-gate failed (score {decision.score} < {decision.threshold}). "
                        f"Suggestions: {'; '.join(decision.suggestions[:3])}"
                    ),
                )
                return {
                    "output_path": None,
                    "output_url": None,
                    "scene_count": len(shots),
                    "total_duration_s": sum(s.duration_s for s in shots),
                    "cost_gate": cost_gate_outcome,
                    "aborted": True,
                }

    _update_job(jobs_store, job_id, status="rendering", progress=10,
                current_step="scene_gen", scene_count=len(shots))

    # V6 — PER-MODEL RENDER STRATEGY DISPATCH
    # SEEDANCE 2.0 CORE PATH: single-call multi-shot inline (1 API call → N cuts).
    # FALLBACK PATH (Wan 2.7 / long-form / cross-location): per-shot chain loop.
    from agent.multi_shot_prompt_builder import (
        pick_strategy, detect_cross_location_cut,
        build_seedance_2_multi_shot,
    )
    total_dur_plan = int(sum(s.duration_s for s in shots))
    has_cross_cut = detect_cross_location_cut(list(shots))
    strategy = pick_strategy(
        user_model=user_model,
        total_duration_s=total_dur_plan,
        num_shots=len(shots),
        has_cross_location_cut=has_cross_cut,
    )
    logger.info(
        f"[VideoWorker V4.5] {job_id} strategy={strategy} "
        f"model={user_model} dur={total_dur_plan}s shots={len(shots)} "
        f"cross_cut={has_cross_cut}"
    )
    if strategy != "single_call_multi_shot":
        duration_warnings = continuity_manager.normalize_per_shot_durations_for_model(
            plan, user_model
        )
        if duration_warnings:
            shots = plan.shot_list
            total_dur_plan = int(sum(s.duration_s for s in shots))
            rate = get_render_cost_rate(user_model)
            new_render_cost = round(rate * total_dur_plan, 3)
            plan.cost_estimate.render_cost_usd = new_render_cost
            plan.cost_estimate.total_cost_usd = round(
                plan.cost_estimate.plan_cost_usd
                + plan.cost_estimate.storyboard_gen_cost_usd
                + new_render_cost
                + plan.cost_estimate.audio_cost_usd,
                3,
            )
            logger.warning(
                f"[VideoWorker] {job_id} per-shot duration normalized: "
                f"{'; '.join(duration_warnings)}"
            )
            _update_job(
                jobs_store,
                job_id,
                duration_adjustments=duration_warnings,
                adjusted_total_duration_s=total_dur_plan,
                adjusted_render_cost_usd=new_render_cost,
            )

    # ============================================================
    # STRATEGY A — SINGLE CALL (Seedance 2.0 / 2.0 Fast multi-shot inline)
    # ============================================================
    render_quality: list[dict[str, Any]] = []
    retry_plan: dict[str, Any] = {
        "enabled": False,
        "executor_status": "not_planned",
        "items": [],
        "summary": {"retry_count": 0, "has_retries": False, "high_severity_count": 0},
    }
    retry_execution: dict[str, Any] = {
        "enabled": False,
        "executor_status": "not_planned",
        "summary": {"executable_count": 0, "deferred_count": 0, "total_items": 0},
    }
    if strategy == "single_call_multi_shot":
        _update_job(jobs_store, job_id, current_step="single_call_render")
        work_dir = Path(tempfile.gettempdir()) / f"cineforge_{job_id}"
        work_dir.mkdir(parents=True, exist_ok=True)

        spec = build_seedance_2_multi_shot(
            bible=bible,
            shots=list(shots),
            reference_images=reference_images,
            reference_videos=reference_videos,
            reference_audios=reference_audios,
            model_key=ref_key_default,
            resolution=resolution,
        )
        # Master Board → append as extra style ref (consistent with per-shot path).
        # V5.15.2 M1 — log warning when board is skipped due to ref cap so user
        # operators can see why their $0.04 board gen didn't anchor the render.
        if master_board_url and master_board_url not in spec.reference_image_urls:
            if len(spec.reference_image_urls) < 9:  # Seedance 2.0 max
                spec.reference_image_urls.append(master_board_url)
            else:
                logger.warning(
                    f"[VideoWorker] {job_id} master_board skipped — ref cap "
                    f"reached ({len(spec.reference_image_urls)}/9). Board $0.04 paid "
                    f"but not anchored — reduce user refs to free a slot."
                )

        single_call_model_key = (
            ref_key_default
            if (spec.reference_image_urls or spec.reference_video_urls)
            else t2v_key_default
        )

        logger.info(
            f"[VideoWorker V4.5] single-call render: {single_call_model_key} "
            f"dur={spec.total_duration_s}s refs={len(spec.reference_image_urls)} "
            f"prompt_chars={len(spec.prompt)}"
        )
        atlas_kwargs = {
            "model_key": single_call_model_key,
            "prompt": spec.prompt,
            "negative_prompt": spec.negative_prompt,
            "images": spec.reference_image_urls,
            "reference_videos": spec.reference_video_urls,
            "reference_audios": spec.reference_audio_urls,
            "duration_s": spec.total_duration_s,
            "resolution": spec.resolution,
            "aspect_ratio": spec.aspect_ratio,
            "generate_audio": spec.generate_audio,
            "return_last_frame": False,  # single call → no chain needed
            "poll_interval_s": 5,
            "timeout_s": 900,
        }
        atlas_kwargs["on_submit"] = lambda pid: _track_prediction(jobs_store, job_id, pid)
        # V5.3 — bail if user cancelled between render_plan entry and single-call
        # submit (closes the ~10-20s setup-phase race where Strategy A/B had no check).
        _check_cancelled(jobs_store, job_id)
        for planned_shot in shots:
            _graph_update_node(
                job_id,
                f"shot_{planned_shot.shot_id}",
                "rendering",
                {"render_scope": "single_call_multi_shot", "model_key": single_call_model_key},
            )
        single_result = await asyncio.to_thread(atlas_client.generate_video, **atlas_kwargs)
        clip_url = single_result.get("video_url")
        if not clip_url:
            raise RuntimeError(f"Single-call render returned no video_url. {single_result}")

        clip_path = work_dir / "single_call.mp4"
        await _download_file(clip_url, clip_path)
        media_probe = await asyncio.to_thread(
            probe_media_file, clip_path, expected_duration_s=spec.total_duration_s
        )
        frame_samples = await asyncio.to_thread(
            sample_video_frames,
            clip_path,
            work_dir / "qa_frames" / "single_call",
            duration_s=media_probe.get("duration_s") or spec.total_duration_s,
            prefix="all",
        )
        frame_samples = await _persist_frame_samples(job_id, "ALL", frame_samples)
        text_artifacts = await asyncio.to_thread(
            probe_text_artifacts,
            frame_samples,
            caption_expected=False,
        )
        visual_reference_probe = await asyncio.to_thread(
            probe_visual_reference_similarity,
            frame_samples=frame_samples,
            reference_image_urls=spec.reference_image_urls,
        )
        semantic_quality = await asyncio.to_thread(
            evaluate_render_frames,
            bible=bible,
            shot=None,
            frame_samples=frame_samples,
            output_scope="full_clip",
        )
        clip_paths = [clip_path]
        chain_meta = [{
            "shot_id": "ALL",
            "model_key": single_call_model_key,
            "render_mode": "single_call_multi_shot",
            "video_url": clip_url,
            "last_frame_url": None,
            "prediction_id": single_result.get("prediction_id"),
            "duration_s": spec.total_duration_s,
            "shot_timing": spec.shot_timing,  # for downstream audio_timeline
        }]
        qa_report = build_render_quality_report(
            bible=bible,
            shot=None,
            render_mode="single_call_multi_shot",
            model_key=single_call_model_key,
            video_url=clip_url,
            prediction_id=single_result.get("prediction_id"),
            duration_s=spec.total_duration_s,
            reference_image_count=len(spec.reference_image_urls),
            reference_video_count=len(spec.reference_video_urls),
            reference_audio_count=len(spec.reference_audio_urls),
            chained_from=None,
            output_scope="full_clip",
            media_probe=media_probe,
            frame_samples=frame_samples,
            semantic_quality=semantic_quality,
            text_artifacts=text_artifacts,
            visual_reference_probe=visual_reference_probe,
        )
        chain_meta[0]["quality"] = qa_report
        render_quality.append(qa_report)
        qa_status = _qa_node_status(qa_report)
        for planned_shot in shots:
            _graph_update_node(
                job_id,
                f"shot_{planned_shot.shot_id}",
                "rendered",
                {
                    "render_scope": "single_call_multi_shot",
                    "video_url": clip_url,
                    "prediction_id": single_result.get("prediction_id"),
                    "model_key": single_call_model_key,
                },
            )
            _graph_update_node(
                job_id,
                f"qa_{planned_shot.shot_id}",
                qa_status,
                {"quality_status": qa_report.get("status"), "quality": qa_report},
            )
        retry_plan = build_retry_plan(
            render_quality=render_quality,
            production_graph=(bible.storytelling_meta or {}).get("production_graph")
            if bible.storytelling_meta else None,
        )
        _update_job(jobs_store, job_id, render_quality=render_quality, retry_plan=retry_plan)

        # Skip per-shot loop entirely — go straight to assemble
        last_frame_urls_by_shot_id = {}
        _update_job(
            jobs_store, job_id, status="rendering", progress=80,
            current_step="single_call_done", scene_count=1,
        )
        # Continue to assemble stage below using clip_paths + chain_meta
        _SKIP_PER_SHOT_LOOP = True
    else:
        # FALLBACK PATH — per-shot chain loop (Wan 2.7 / long-form / cross-location)
        _SKIP_PER_SHOT_LOOP = False

    # Stage 1 — Reference-chained render loop.
    # We invoke Scene Generation Agent LAZILY per shot (right before its render
    # call) so the LLM sees the live `last_frame_url` and can format the prompt
    # accordingly (chain frame carries identity → drop char refs etc.).
    if not _SKIP_PER_SHOT_LOOP:
        work_dir = Path(tempfile.gettempdir()) / f"cineforge_{job_id}"
        work_dir.mkdir(parents=True, exist_ok=True)

        # BUG #3 fix — track last_frame by shot_id, not just "the previous one
        # we rendered". This is required when a shot chains back to a shot earlier
        # than the immediate predecessor (e.g. flashback / cutaway pattern where
        # S3.previous_shot_id == "S1"). The previous implementation always passed
        # the most-recently-rendered last_frame, which silently drifted identity.
        last_frame_urls_by_shot_id = {}
        clip_paths = []
        chain_meta = []

    # V4.5 — for-loop skips entirely when single-call mode (shots_to_iter=[])
    shots_to_iter = [] if _SKIP_PER_SHOT_LOOP else list(shots)
    total_shots = len(shots_to_iter)

    for i, shot in enumerate(shots_to_iter):
        _update_job(
            jobs_store, job_id,
            status="rendering",
            progress=15 + int(70 * (i / max(1, total_shots))),
            current_step=f"shot_{i + 1}/{total_shots}",
        )

        # Decide the model key for this shot. Honor per-shot override; otherwise
        # use the user's choice; switch to i2v variant when chaining.
        per_shot_user_model = shot.model_routing.preferred_model
        if per_shot_user_model and per_shot_user_model != "auto":
            ref_key, i2v_key = _resolve_models(per_shot_user_model)
        else:
            ref_key, i2v_key = ref_key_default, i2v_key_default

        # Look up the chain anchor by the explicit previous_shot_id — not "i-1".
        chain_anchor_url: Optional[str] = None
        psid = shot.continuity.previous_shot_id
        if psid:
            chain_anchor_url = last_frame_urls_by_shot_id.get(psid)
            # CRITICAL C7 — Warn when chain anchor is missing instead of silently
            # falling back to ref_to_video (which causes identity drift mid-video).
            if chain_anchor_url is None and psid in last_frame_urls_by_shot_id:
                logger.warning(
                    f"[VideoWorker V3] {job_id} shot {shot.shot_id}: chain anchor "
                    f"'{psid}' rendered but last_frame_url=None — identity may drift"
                )
            elif chain_anchor_url is None and psid not in last_frame_urls_by_shot_id:
                logger.warning(
                    f"[VideoWorker V3] {job_id} shot {shot.shot_id}: previous_shot_id "
                    f"'{psid}' not found in chain (typo? skip-chain to earlier shot?) "
                    f"— falling back to ref_to_video, identity may drift"
                )
        will_chain = chain_anchor_url is not None and i > 0
        active_model_key = i2v_key if will_chain else ref_key

        # BUG #1 fix + CRITICAL C9: For Wan 2.7 (driven audio), attach the
        # pre-rendered audio URL whenever the audio_plan provides one — NOT
        # gated by shot.audio.dialogue_vn. Wan can lip-sync to humming, SFX,
        # music tracks too; silent shots with Wan that need ANY mouth motion
        # need the audio field. Per-shot map wins over global voice_audio_url.
        driven_audio_url: Optional[str] = None
        if audio_plan and isinstance(audio_plan, dict):
            per_shot_map = audio_plan.get("driven_audio_urls")
            if isinstance(per_shot_map, dict):
                driven_audio_url = per_shot_map.get(shot.shot_id)
            if not driven_audio_url:
                driven_audio_url = audio_plan.get("voice_audio_url")

        # Build the prompt via Layer 2 (LLM or deterministic).
        job = await asyncio.to_thread(
            scene_generation_agent.generate_scene,
            bible=bible,
            shot=shot,
            model_key=active_model_key,
            reference_images=reference_images,
            reference_videos=reference_videos,
            reference_audios=reference_audios,
            last_frame_url=chain_anchor_url if will_chain else None,
            llm_mode=use_llm_scene_gen,
            resolution=resolution,
            is_last_shot=(i == total_shots - 1),
            driven_audio_url=driven_audio_url,
            master_board_url=master_board_url,  # V4 Sprint1 Task #7
        )

        kwargs = job.to_atlas_kwargs()
        kwargs["poll_interval_s"] = 5
        kwargs["timeout_s"] = 600
        kwargs["on_submit"] = lambda pid: _track_prediction(jobs_store, job_id, pid)

        # V5.1 — bail BEFORE firing a new vendor call if user cancelled mid-loop.
        _check_cancelled(jobs_store, job_id)

        logger.info(
            f"[VideoWorker V3] {job_id} shot {shot.shot_id} ({i + 1}/{total_shots}) "
            f"mode={job.render_mode} model={job.model_key} dur={job.duration_s}s "
            f"refs={len(job.reference_image_urls)}"
        )
        _graph_update_node(
            job_id,
            f"shot_{shot.shot_id}",
            "rendering",
            {
                "model_key": job.model_key,
                "render_mode": job.render_mode,
                "chained_from": psid if will_chain else None,
            },
        )

        result = await asyncio.to_thread(atlas_client.generate_video, **kwargs)
        clip_url = result.get("video_url")
        if not clip_url:
            raise RuntimeError(f"shot {shot.shot_id}: AtlasCloud returned no video_url. {result}")

        clip_path = work_dir / f"shot_{i:02d}_{shot.shot_id}.mp4"
        await _download_file(clip_url, clip_path)
        media_probe = await asyncio.to_thread(
            probe_media_file, clip_path, expected_duration_s=job.duration_s
        )
        frame_samples = await asyncio.to_thread(
            sample_video_frames,
            clip_path,
            work_dir / "qa_frames" / shot.shot_id,
            duration_s=media_probe.get("duration_s") or job.duration_s,
            prefix=shot.shot_id,
        )
        frame_samples = await _persist_frame_samples(job_id, shot.shot_id, frame_samples)
        text_artifacts = await asyncio.to_thread(
            probe_text_artifacts,
            frame_samples,
            caption_expected=bool(shot.audio.caption_on_screen),
        )
        visual_reference_probe = await asyncio.to_thread(
            probe_visual_reference_similarity,
            frame_samples=frame_samples,
            reference_image_urls=job.reference_image_urls,
        )
        semantic_quality = await asyncio.to_thread(
            evaluate_render_frames,
            bible=bible,
            shot=shot,
            frame_samples=frame_samples,
            output_scope="shot",
        )
        clip_paths.append(clip_path)

        produced_last_frame = result.get("last_frame_url")
        last_frame_urls_by_shot_id[shot.shot_id] = produced_last_frame
        chain_meta.append({
            "shot_id": shot.shot_id,
            "model_key": job.model_key,
            "render_mode": job.render_mode,
            "video_url": clip_url,
            "last_frame_url": produced_last_frame,
            "prediction_id": result.get("prediction_id"),
            "duration_s": job.duration_s,
            "chained_from": psid if will_chain else None,
        })
        qa_report = build_render_quality_report(
            bible=bible,
            shot=shot,
            render_mode=job.render_mode,
            model_key=job.model_key,
            video_url=clip_url,
            prediction_id=result.get("prediction_id"),
            duration_s=job.duration_s,
            reference_image_count=len(job.reference_image_urls),
            reference_video_count=len(job.reference_video_urls),
            reference_audio_count=len(job.reference_audio_urls),
            chained_from=psid if will_chain else None,
            output_scope="shot",
            media_probe=media_probe,
            frame_samples=frame_samples,
            semantic_quality=semantic_quality,
            text_artifacts=text_artifacts,
            visual_reference_probe=visual_reference_probe,
        )
        chain_meta[-1]["quality"] = qa_report
        render_quality.append(qa_report)
        _graph_update_node(
            job_id,
            f"shot_{shot.shot_id}",
            "rendered",
            {
                "video_url": clip_url,
                "prediction_id": result.get("prediction_id"),
                "last_frame_url": produced_last_frame,
                "model_key": job.model_key,
                "render_mode": job.render_mode,
            },
        )
        _graph_update_node(
            job_id,
            f"qa_{shot.shot_id}",
            _qa_node_status(qa_report),
            {"quality_status": qa_report.get("status"), "quality": qa_report},
        )
        retry_plan = build_retry_plan(
            render_quality=render_quality,
            production_graph=(bible.storytelling_meta or {}).get("production_graph")
            if bible.storytelling_meta else None,
        )
        _update_job(jobs_store, job_id, render_quality=render_quality, retry_plan=retry_plan)

    # Stage 3 — Assemble
    if not _SKIP_PER_SHOT_LOOP and retry_plan.get("items"):
        retry_execution = await _execute_retry_plan_once(
            job_id=job_id,
            retry_plan=retry_plan,
            plan=plan,
            reference_images=reference_images,
            reference_videos=reference_videos,
            reference_audios=reference_audios,
            resolution=resolution,
            audio_plan=audio_plan,
            use_llm_scene_gen=use_llm_scene_gen,
            work_dir=work_dir,
            clip_paths=clip_paths,
            chain_meta=chain_meta,
            render_quality=render_quality,
            last_frame_urls_by_shot_id=last_frame_urls_by_shot_id,
            ref_key_default=ref_key_default,
            i2v_key_default=i2v_key_default,
            jobs_store=jobs_store,
        )
        retry_plan = {
            **retry_plan,
            "enabled": retry_execution.get("enabled", False),
            "executor_status": retry_execution.get("executor_status"),
            "execution": retry_execution,
        }
        _update_job(
            jobs_store, job_id,
            render_quality=render_quality,
            retry_plan=retry_plan,
            retry_execution=retry_execution,
        )

    _update_job(jobs_store, job_id, status="assembling", progress=88, current_step="ffmpeg_assemble")
    _graph_update_node(job_id, "assembly_final", "assembling", {"clip_count": len(clip_paths)})

    final_mp4 = work_dir / "final.mp4"
    assembler = AssembleWorker(work_dir=str(work_dir))

    target_resolution = _resolution_for_aspect(bible.aspect_ratio, resolution)
    audio_plan = audio_plan or {"mode": "silent_native"}

    # V4 Sprint1 Task B — Build per-shot voice timeline if we have TTS URLs.
    # Download each TTS audio locally and prepare shots_for_timeline manifest
    # so AssembleWorker uses audio_timeline.build_timeline (per-shot sync).
    voice_clips_by_shot_id: dict[str, str] = {}
    driven_urls = audio_plan.get("driven_audio_urls") or {}
    if driven_urls:
        tts_dir = work_dir / "tts"
        tts_dir.mkdir(exist_ok=True)
        for shot_id, url in driven_urls.items():
            local_path = tts_dir / f"{shot_id}.mp3"
            try:
                await _download_file(url, local_path)
                voice_clips_by_shot_id[shot_id] = str(local_path)
            except Exception as e:
                logger.warning(f"[VideoWorker V4] download TTS for {shot_id} fail: {e}")

    await asyncio.to_thread(
        assembler.assemble,
        video_paths=[str(p) for p in clip_paths],
        audio_plan=audio_plan,
        output_path=str(final_mp4),
        bgm_path=audio_plan.get("bgm_path"),
        target_resolution=target_resolution,
        shots_for_timeline=[s.model_dump() for s in shots] if voice_clips_by_shot_id else None,
        voice_clips_by_shot_id=voice_clips_by_shot_id or None,
    )

    # Stage 4 — Color consistency pass (Bible-driven)
    color_pass_mp4 = work_dir / "final_graded.mp4"
    await asyncio.to_thread(
        _apply_color_consistency,
        str(final_mp4), str(color_pass_mp4),
        bible_color_grading=bible.visual_style.color_grading,
    )

    # Stage 5 — Upload to R2 (graceful fallback to file:// when not configured)
    _update_job(jobs_store, job_id, status="uploading", progress=95, current_step="r2_upload")
    r2_key = f"video/{job_id}/final.mp4"
    output_url = await r2_storage.upload_with_fallback(
        color_pass_mp4, key=r2_key, content_type="video/mp4",
    )
    dynamic_keyframe_memory = _populate_dynamic_keyframe_memory_from_render(
        plan=plan,
        chain_meta=chain_meta,
    )
    if dynamic_keyframe_memory:
        try:
            plan.continuity_bible.storytelling_meta = {
                **(plan.continuity_bible.storytelling_meta or {}),
                "dynamic_keyframe_memory": dynamic_keyframe_memory,
            }
        except Exception as e:
            logger.warning(f"[VideoWorker V3] dynamic keyframe memory attach failed: {e}")

    _update_job(
        jobs_store, job_id,
        status="done", progress=100, current_step="done",
        output_path=str(color_pass_mp4),
        output_url=output_url,
        duration_s=sum(s.duration_s for s in shots),
        render_quality=render_quality,
        retry_plan=retry_plan,
        retry_execution=retry_execution,
        dynamic_keyframe_memory=dynamic_keyframe_memory,
    )
    _graph_update_node(
        job_id,
        "assembly_final",
        "completed",
        {"output_url": output_url, "duration_s": sum(s.duration_s for s in shots)},
    )

    logger.info(
        f"[VideoWorker V3] {job_id} DONE — {len(shots)} shots, "
        f"{sum(s.duration_s for s in shots)}s total → {output_url}"
    )

    # Persist to Project History (restart-safe + listable in UI)
    try:
        director_history.record_job(
            job_id=job_id,
            plan_id=plan.plan_id,
            mode=(jobs_store or {}).get(job_id, {}).get("mode") or "approved",
            status="done",
            output_url=output_url,
            title=bible.title,
            duration_s=sum(s.duration_s for s in shots),
            cost_estimate_usd=plan.cost_estimate.total_cost_usd,
            plan=plan.model_dump(),
            chain=chain_meta,
            created_at=(jobs_store or {}).get(job_id, {}).get("created_at"),
        )
    except Exception as e:
        logger.warning(f"[VideoWorker V3] director_history.record_job fail (non-fatal): {e}")

    # CRITICAL C6 — Clean up the per-job work directory after success.
    # work_dir holds N intermediate clips + concat + graded MP4. Each render
    # is ~500MB, so without cleanup the disk fills within hundreds of jobs.
    # Failed jobs INTENTIONALLY skip cleanup (handled in `_run()` wrapper at
    # the route layer — caller can inspect work_dir for debugging).
    try:
        import shutil as _shutil
        _shutil.rmtree(work_dir, ignore_errors=True)
        logger.info(f"[VideoWorker V3] {job_id} cleaned work_dir {work_dir.name}")
    except Exception as e:
        logger.warning(f"[VideoWorker V3] work_dir cleanup fail (non-fatal): {e}")

    return {
        "output_path": str(color_pass_mp4),
        "output_url": output_url,
        "scene_count": len(shots),
        "total_duration_s": sum(s.duration_s for s in shots),
        "chain": chain_meta,
        "cost_gate": cost_gate_outcome,
        "render_quality": render_quality,
        "retry_plan": retry_plan,
        "retry_execution": retry_execution,
        "dynamic_keyframe_memory": dynamic_keyframe_memory,
    }


def _populate_dynamic_keyframe_memory_from_render(
    *,
    plan: DirectorPlan,
    chain_meta: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Populate the planned long-form memory bank with accepted render outputs."""
    meta = plan.continuity_bible.storytelling_meta or {}
    scene_memory_pack = meta.get("scene_memory_pack")
    production_graph = meta.get("production_graph")
    if not isinstance(scene_memory_pack, dict) or not isinstance(production_graph, dict):
        return None
    accepted_outputs: list[dict[str, Any]] = []
    for item in chain_meta:
        if not isinstance(item, dict):
            continue
        video_url = item.get("video_url") or item.get("output_url")
        if not video_url:
            continue
        quality = item.get("quality") if isinstance(item.get("quality"), dict) else {}
        if str(quality.get("status") or "pass").lower() == "fail":
            continue
        accepted_outputs.append({
            "shot_id": item.get("shot_id"),
            "scene_id": item.get("scene_id"),
            "video_url": video_url,
            "last_frame_url": item.get("last_frame_url"),
            "keyframe_url": item.get("last_frame_url"),
            "qa_score": quality.get("score") or quality.get("overall_score"),
            "accepted": True,
            "drift_notes": _dynamic_memory_drift_notes(quality),
        })
    try:
        from agent.dynamic_keyframe_memory import build_dynamic_keyframe_memory_contract

        return build_dynamic_keyframe_memory_contract(
            scene_memory_pack=scene_memory_pack,
            production_graph=production_graph,
            accepted_outputs=accepted_outputs,
        )
    except Exception as e:
        logger.warning(f"[VideoWorker V3] dynamic keyframe memory population failed: {e}")
        return None


def _dynamic_memory_drift_notes(quality: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if not isinstance(quality, dict):
        return notes
    for check in quality.get("checks") or []:
        if isinstance(check, dict) and str(check.get("status") or "").lower() in {"warn", "fail"}:
            label = str(check.get("id") or check.get("name") or "quality_check")
            message = str(check.get("message") or check.get("detail") or "").strip()
            notes.append(f"{label}: {message}" if message else label)
    criteria = quality.get("criteria") if isinstance(quality.get("criteria"), dict) else {}
    semantic = criteria.get("semantic_quality") if isinstance(criteria.get("semantic_quality"), dict) else {}
    for issue in semantic.get("issues") or []:
        if isinstance(issue, str) and issue.strip():
            notes.append(issue.strip())
    return notes[:8]


async def _execute_retry_plan_once(
    *,
    job_id: str,
    retry_plan: dict[str, Any],
    plan: DirectorPlan,
    reference_images: list[str],
    reference_videos: list[str],
    reference_audios: list[str],
    resolution: str,
    audio_plan: Optional[dict],
    use_llm_scene_gen: bool,
    work_dir: Path,
    clip_paths: list[Path],
    chain_meta: list[dict[str, Any]],
    render_quality: list[dict[str, Any]],
    last_frame_urls_by_shot_id: dict[str, Optional[str]],
    ref_key_default: str,
    i2v_key_default: str,
    jobs_store: Optional[dict],
) -> dict[str, Any]:
    """Run one safe retry pass before final assembly.

    Scope is intentionally conservative:
      - per-shot only, not single-call/full clip
      - no shots that are chain anchors for later shots
      - one attempt per queued item in the current worker run
    """
    shots = list(plan.shot_list)
    bible = plan.continuity_bible
    execution = prepare_retry_execution(retry_plan=retry_plan, shots=shots)
    if not execution.get("executable_items"):
        _update_job(jobs_store, job_id, retry_execution=execution)
        return execution

    _update_job(
        jobs_store, job_id,
        status="rendering",
        progress=82,
        current_step="auto_retry",
        retry_execution=execution,
    )

    shot_by_id = {s.shot_id: s for s in shots}
    shot_index = {s.shot_id: i for i, s in enumerate(shots)}
    results: list[dict[str, Any]] = []

    for n, item in enumerate(execution["executable_items"], start=1):
        shot_id = str(item.get("shot_id"))
        shot = shot_by_id.get(shot_id)
        if shot is None:
            results.append({**item, "status": "failed", "error": "shot_missing"})
            continue
        _graph_update_node(
            job_id,
            f"shot_{shot_id}",
            "retrying",
            {"retry_reason": item.get("reason"), "retry_item_index": item.get("item_index")},
        )

        _update_job(
            jobs_store, job_id,
            current_step=f"auto_retry_{n}/{len(execution['executable_items'])}",
        )
        repair_hint = str(item.get("prompt_repair_hint") or item.get("reason") or "")
        retry_shot = shot.model_copy(update={
            "dynamic_description": (
                f"{shot.dynamic_description or ''}\n"
                f"RETRY REPAIR: {repair_hint}\n"
                "Preserve the approved production bible and simplify only the failed visual/audio issue."
            ).strip()
        })

        try:
            ref_key, i2v_key = ref_key_default, i2v_key_default
            per_shot_user_model = retry_shot.model_routing.preferred_model
            if per_shot_user_model and per_shot_user_model != "auto":
                ref_key, i2v_key = _resolve_models(per_shot_user_model)

            psid = retry_shot.continuity.previous_shot_id
            chain_anchor_url = last_frame_urls_by_shot_id.get(psid) if psid else None
            will_chain = bool(chain_anchor_url)
            active_model_key = i2v_key if will_chain else ref_key

            driven_audio_url: Optional[str] = None
            if audio_plan and isinstance(audio_plan, dict):
                per_shot_map = audio_plan.get("driven_audio_urls")
                if isinstance(per_shot_map, dict):
                    driven_audio_url = per_shot_map.get(retry_shot.shot_id)
                if not driven_audio_url:
                    driven_audio_url = audio_plan.get("voice_audio_url")

            scene_job = await asyncio.to_thread(
                scene_generation_agent.generate_scene,
                bible=bible,
                shot=retry_shot,
                model_key=active_model_key,
                reference_images=reference_images,
                reference_videos=reference_videos,
                reference_audios=reference_audios,
                last_frame_url=chain_anchor_url if will_chain else None,
                llm_mode=use_llm_scene_gen,
                resolution=resolution,
                is_last_shot=(shot_index[shot_id] == len(shots) - 1),
                driven_audio_url=driven_audio_url,
            )

            kwargs = scene_job.to_atlas_kwargs()
            kwargs["poll_interval_s"] = 5
            kwargs["timeout_s"] = 600
            kwargs["on_submit"] = lambda pid: _track_prediction(jobs_store, job_id, pid)
            _check_cancelled(jobs_store, job_id)
            result = await asyncio.to_thread(atlas_client.generate_video, **kwargs)
            clip_url = result.get("video_url")
            if not clip_url:
                raise RuntimeError(f"retry shot {shot_id}: AtlasCloud returned no video_url. {result}")

            clip_path = work_dir / f"retry_{n:02d}_{shot_id}.mp4"
            await _download_file(clip_url, clip_path)
            media_probe = await asyncio.to_thread(
                probe_media_file, clip_path, expected_duration_s=scene_job.duration_s
            )
            frame_samples = await asyncio.to_thread(
                sample_video_frames,
                clip_path,
                work_dir / "qa_frames" / f"retry_{shot_id}",
                duration_s=media_probe.get("duration_s") or scene_job.duration_s,
                prefix=f"retry_{shot_id}",
            )
            frame_samples = await _persist_frame_samples(job_id, f"retry_{shot_id}", frame_samples)
            text_artifacts = await asyncio.to_thread(
                probe_text_artifacts,
                frame_samples,
                caption_expected=bool(retry_shot.audio.caption_on_screen),
            )
            visual_reference_probe = await asyncio.to_thread(
                probe_visual_reference_similarity,
                frame_samples=frame_samples,
                reference_image_urls=scene_job.reference_image_urls,
            )
            semantic_quality = await asyncio.to_thread(
                evaluate_render_frames,
                bible=bible,
                shot=retry_shot,
                frame_samples=frame_samples,
                output_scope="shot_retry",
            )
            qa_report = build_render_quality_report(
                bible=bible,
                shot=retry_shot,
                render_mode=scene_job.render_mode,
                model_key=scene_job.model_key,
                video_url=clip_url,
                prediction_id=result.get("prediction_id"),
                duration_s=scene_job.duration_s,
                reference_image_count=len(scene_job.reference_image_urls),
                reference_video_count=len(scene_job.reference_video_urls),
                reference_audio_count=len(scene_job.reference_audio_urls),
                chained_from=psid if will_chain else None,
                output_scope="shot_retry",
                media_probe=media_probe,
                frame_samples=frame_samples,
                semantic_quality=semantic_quality,
                text_artifacts=text_artifacts,
                visual_reference_probe=visual_reference_probe,
            )

            idx = shot_index[shot_id]
            if idx < len(clip_paths):
                clip_paths[idx] = clip_path
            if idx < len(chain_meta):
                chain_meta[idx] = {
                    **chain_meta[idx],
                    "video_url": clip_url,
                    "last_frame_url": result.get("last_frame_url"),
                    "prediction_id": result.get("prediction_id"),
                    "retry_replaced": True,
                    "retry_reason": item.get("reason"),
                    "quality": qa_report,
                }
            last_frame_urls_by_shot_id[shot_id] = result.get("last_frame_url")
            render_quality.append(qa_report)
            _graph_update_node(
                job_id,
                f"shot_{shot_id}",
                "rendered",
                {
                    "retry_replaced": True,
                    "retry_video_url": clip_url,
                    "prediction_id": result.get("prediction_id"),
                    "last_frame_url": result.get("last_frame_url"),
                },
            )
            _graph_update_node(
                job_id,
                f"qa_{shot_id}",
                _qa_node_status(qa_report),
                {"quality_status": qa_report.get("status"), "retry_quality": qa_report},
            )
            if item.get("item_index") is not None:
                retry_plan["items"][int(item["item_index"])] = {
                    **retry_plan["items"][int(item["item_index"])],
                    "status": "succeeded",
                    "attempts_done": int(retry_plan["items"][int(item["item_index"])].get("attempts_done") or 0) + 1,
                    "retry_video_url": clip_url,
                    "retry_quality": qa_report,
                }
            results.append({**item, "status": "succeeded", "video_url": clip_url})
        except Exception as e:
            logger.warning(f"[auto_retry] {job_id} shot {shot_id} retry failed: {e}")
            _graph_update_node(
                job_id,
                f"shot_{shot_id}",
                "retry_failed",
                {"retry_error": str(e)[:240]},
            )
            if item.get("item_index") is not None:
                retry_plan["items"][int(item["item_index"])] = {
                    **retry_plan["items"][int(item["item_index"])],
                    "status": "failed",
                    "attempts_done": int(retry_plan["items"][int(item["item_index"])].get("attempts_done") or 0) + 1,
                    "error": str(e)[:240],
                }
            results.append({**item, "status": "failed", "error": str(e)[:240]})

    succeeded = len([r for r in results if r.get("status") == "succeeded"])
    failed = len([r for r in results if r.get("status") == "failed"])
    status = "completed" if failed == 0 else ("partial" if succeeded else "failed")
    return {
        **execution,
        "executor_status": status,
        "enabled": True,
        "results": results,
        "summary": {
            **execution.get("summary", {}),
            "succeeded_count": succeeded,
            "failed_count": failed,
        },
    }


def cleanup_failed_job(job_id: str) -> bool:
    """Sprint3 B3 — drop the per-job work_dir after a render failure.

    Mirrors the success-path cleanup at the end of render_plan/render_single_shot
    so failed jobs don't strand ~500MB of intermediate clips per attempt. Safe
    to call even if the dir was never created (rmtree ignore_errors).
    Returns True on rmtree attempt, False on unexpected error.
    """
    import shutil as _shutil
    for prefix in ("cineforge_", "cineforge_refine_"):
        work_dir = Path(tempfile.gettempdir()) / f"{prefix}{job_id}"
        try:
            if work_dir.exists():
                _shutil.rmtree(work_dir, ignore_errors=True)
                logger.info(f"[VideoWorker V3] cleanup_failed_job removed {work_dir.name}")
        except Exception as e:
            logger.warning(f"[VideoWorker V3] cleanup_failed_job fail {work_dir.name}: {e}")
            return False
    return True


# ============================================================
# Refine — re-render a single shot (Evaluation-driven)
# ============================================================
async def render_single_shot(
    job_id: str,
    plan: DirectorPlan,
    shot_id: str,
    reference_images: list[str],
    user_model: str,
    resolution: str,
    *,
    reference_videos: Optional[list[str]] = None,
    reference_audios: Optional[list[str]] = None,
    previous_last_frame_url: Optional[str] = None,
    jobs_store: Optional[dict] = None,
    use_llm_scene_gen: bool = True,
    finalize_job: bool = True,
    cleanup_work_dir: bool = True,
) -> dict:
    """Render ONE shot (used by `/director/refine`).

    The caller already has the full plan; this just re-renders one shot,
    optionally chained from the previous shot's last frame so the new clip
    drops back into the timeline without identity drift.

    Returns `{shot_id, video_url, last_frame_url, render_mode, model_key}`.
    The caller is responsible for stitching the replacement clip back into
    the assembled video (typically by re-running FFmpeg concat with the new
    clip swapped in at the right slot).
    """
    reference_videos = list((reference_videos or [])[:3])
    reference_audios = list((reference_audios or [])[:3])
    shot = next((s for s in plan.shot_list if s.shot_id == shot_id), None)
    if shot is None:
        raise ValueError(f"shot_id '{shot_id}' not in plan {plan.plan_id}")

    bible = plan.continuity_bible
    ref_key_default, i2v_key_default = _resolve_models(user_model)
    per_shot = shot.model_routing.preferred_model
    if per_shot and per_shot != "auto":
        ref_key, i2v_key = _resolve_models(per_shot)
    else:
        ref_key, i2v_key = ref_key_default, i2v_key_default

    will_chain = (
        shot.continuity.previous_shot_id is not None
        and previous_last_frame_url is not None
    )
    active_model_key = i2v_key if will_chain else ref_key

    _update_job(jobs_store, job_id, status="rendering", progress=20,
                current_step=f"refine_{shot_id}")

    scene_job = await asyncio.to_thread(
        scene_generation_agent.generate_scene,
        bible=bible,
        shot=shot,
        model_key=active_model_key,
        reference_images=reference_images,
        reference_videos=reference_videos,
        reference_audios=reference_audios,
        last_frame_url=previous_last_frame_url if will_chain else None,
        llm_mode=use_llm_scene_gen,
        resolution=resolution,
        is_last_shot=False,  # refine always returns last_frame (to chain forward)
    )

    kwargs = scene_job.to_atlas_kwargs()
    kwargs["poll_interval_s"] = 5
    kwargs["timeout_s"] = 600

    logger.info(
        f"[VideoWorker V3] refine {job_id} {shot.shot_id} mode={scene_job.render_mode} "
        f"model={scene_job.model_key} dur={scene_job.duration_s}s"
    )
    kwargs["on_submit"] = lambda pid: _track_prediction(jobs_store, job_id, pid)
    _check_cancelled(jobs_store, job_id)
    result = await asyncio.to_thread(atlas_client.generate_video, **kwargs)
    clip_url = result.get("video_url")
    if not clip_url:
        raise RuntimeError(f"refine {shot_id}: AtlasCloud returned no video_url")

    work_dir = Path(tempfile.gettempdir()) / f"cineforge_refine_{job_id}"
    work_dir.mkdir(parents=True, exist_ok=True)
    clip_path = work_dir / f"refined_{shot_id}.mp4"
    await _download_file(clip_url, clip_path)

    # Upload to R2 (graceful fallback to file://)
    _update_job(jobs_store, job_id, status="uploading", progress=90, current_step="r2_upload")
    r2_key = f"refine/{job_id}/{shot_id}.mp4"
    output_url = await r2_storage.upload_with_fallback(
        clip_path, key=r2_key, content_type="video/mp4",
    )

    if finalize_job:
        _update_job(
            jobs_store, job_id,
            status="done", progress=100, current_step="done",
            output_path=str(clip_path),
            output_url=output_url,
        )
    else:
        _update_job(
            jobs_store, job_id,
            status="graph_executing",
            current_step=f"graph_rendered_{shot_id}",
            output_path=str(clip_path),
            output_url=output_url,
        )

    # CRITICAL C6 — cleanup refine work_dir after R2 upload (clip persisted).
    if cleanup_work_dir:
        try:
            import shutil as _shutil
            _shutil.rmtree(work_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"[VideoWorker V3] refine work_dir cleanup fail (non-fatal): {e}")

    return {
        "shot_id": shot_id,
        "video_url": clip_url,
        "output_url": output_url,
        "last_frame_url": result.get("last_frame_url"),
        "render_mode": scene_job.render_mode,
        "model_key": scene_job.model_key,
        "duration_s": scene_job.duration_s,
        "output_path": str(clip_path),
    }


def graph_executor_handlers_for_plan(
    *,
    job_id: str,
    plan: DirectorPlan,
    reference_images: list[str],
    user_model: str,
    resolution: str,
    reference_videos: Optional[list[str]] = None,
    reference_audios: Optional[list[str]] = None,
    audio_plan: Optional[dict] = None,
    jobs_store: Optional[dict] = None,
    use_llm_scene_gen: bool = True,
) -> dict[str, Any]:
    """Build real graph-executor handlers backed by the video worker.

    This is the bridge from the dependency-safe production graph executor to
    the existing AtlasCloud render path. It is intentionally not wired to the
    public HTTP `run-once` route, because calling these handlers starts paid
    vendor renders. A background worker can inject this handler registry after
    it has loaded the persisted DirectorPlan/artifact.
    """
    async def _render(task: dict[str, Any]) -> dict[str, Any]:
        shot_id = str(task.get("shot_id") or (task.get("payload") or {}).get("shot_id") or "")
        if not shot_id:
            return {
                "outcome": "failed",
                "payload_patch": {
                    "executor_status": "missing_shot_id",
                    "executor_error": "graph task has no shot_id",
                },
            }
        previous_last_frame_url = _previous_last_frame_from_graph(
            job_id=job_id,
            previous_shot_id=task.get("previous_shot_id") or (task.get("payload") or {}).get("previous_shot_id"),
        )
        result = await render_single_shot(
            job_id=job_id,
            plan=plan,
            shot_id=shot_id,
            reference_images=reference_images,
            reference_videos=reference_videos or [],
            reference_audios=reference_audios or [],
            user_model=user_model,
            resolution=resolution,
            previous_last_frame_url=previous_last_frame_url,
            jobs_store=jobs_store,
            use_llm_scene_gen=use_llm_scene_gen,
            finalize_job=False,
            cleanup_work_dir=False,
        )
        return {
            "outcome": "success",
            "payload_patch": {
                "executor_status": "rendered_by_video_worker",
                "video_url": result.get("video_url"),
                "output_url": result.get("output_url"),
                "last_frame_url": result.get("last_frame_url"),
                "render_mode": result.get("render_mode"),
                "model_key": result.get("model_key"),
                "duration_s": result.get("duration_s"),
                "output_path": result.get("output_path"),
            },
        }

    async def _qa(task: dict[str, Any]) -> dict[str, Any]:
        shot_id = str(task.get("shot_id") or (task.get("payload") or {}).get("shot_id") or "")
        shot = next((s for s in plan.shot_list if str(s.shot_id) == shot_id), None)
        shot_payload = _shot_payload_from_graph(job_id=job_id, shot_id=shot_id)
        checked_video_url = shot_payload.get("output_url") or shot_payload.get("video_url")
        if not shot or not checked_video_url:
            return {
                "outcome": "failed",
                "payload_patch": {
                    "executor_status": "strong_qa_missing_input",
                    "quality_status": "missing_render_output",
                    "checked_video_url": checked_video_url,
                },
            }

        local_video = _local_video_path_for_graph_qa(
            job_id=job_id,
            shot_id=shot_id,
            shot_payload=shot_payload,
        )
        if not local_video:
            try:
                work_dir = Path(tempfile.gettempdir()) / f"cineforge_graph_qa_{job_id}"
                work_dir.mkdir(parents=True, exist_ok=True)
                local_video = work_dir / f"qa_{shot_id}.mp4"
                await _download_file(str(checked_video_url), local_video)
            except Exception as exc:
                return {
                    "outcome": "failed",
                    "payload_patch": {
                        "executor_status": "strong_qa_download_failed",
                        "quality_status": "qa_video_download_failed",
                        "checked_video_url": checked_video_url,
                        "executor_error": str(exc)[:500],
                    },
                }

        media_probe = await asyncio.to_thread(
            probe_media_file,
            local_video,
            expected_duration_s=int(shot.duration_s or 0),
        )
        frame_samples = await asyncio.to_thread(
            sample_video_frames,
            local_video,
            max_frames=3,
        )
        frame_samples = await _persist_frame_samples(job_id, f"graph_{shot_id}", frame_samples)
        text_artifacts = await asyncio.to_thread(
            probe_text_artifacts,
            frame_samples=frame_samples,
            expected_caption=shot.audio.caption_on_screen,
            caption_expected=bool(shot.audio.caption_on_screen),
        )
        visual_reference_probe = await asyncio.to_thread(
            probe_visual_reference_similarity,
            frame_samples=frame_samples,
            reference_image_urls=reference_images,
        )
        semantic_quality = await asyncio.to_thread(
            evaluate_render_frames,
            bible=bible,
            shot=shot,
            frame_samples=frame_samples,
        )
        qa_report = build_render_quality_report(
            bible=bible,
            shot=shot,
            render_mode=str(shot_payload.get("render_mode") or "graph_executor"),
            model_key=str(shot_payload.get("model_key") or user_model),
            video_url=str(checked_video_url),
            prediction_id=shot_payload.get("prediction_id"),
            duration_s=int(shot_payload.get("duration_s") or shot.duration_s or 0),
            reference_image_count=len(reference_images),
            reference_video_count=len(reference_videos or []),
            reference_audio_count=len(reference_audios or []),
            chained_from=shot.continuity.previous_shot_id,
            output_scope="shot",
            media_probe=media_probe,
            frame_samples=frame_samples,
            semantic_quality=semantic_quality,
            text_artifacts=text_artifacts,
            visual_reference_probe=visual_reference_probe,
        )
        qa_status = str(qa_report.get("status") or "warn")
        outcome = "failed" if qa_status == "fail" else ("passed" if qa_status == "pass" else "warn")
        return {
            "outcome": outcome,
            "payload_patch": {
                "executor_status": "strong_graph_qa_gate",
                "quality_status": qa_status,
                "checked_video_url": checked_video_url,
                "render_quality": qa_report,
                "score": qa_report.get("score"),
                "retry_recommended": qa_report.get("retry_recommended"),
                "manual_review_recommended": qa_report.get("manual_review_recommended"),
                "retry_reason": qa_report.get("retry_reason"),
                "media_probe": media_probe,
                "frame_samples": frame_samples,
            },
        }

    async def _assembly(_task: dict[str, Any]) -> dict[str, Any]:
        ordered_outputs = _ordered_rendered_shot_outputs(job_id=job_id, plan=plan)
        if not ordered_outputs:
            return {
                "outcome": "failed",
                "payload_patch": {
                    "executor_status": "assembly_missing_clips",
                    "executor_error": "no rendered shot video_url/output_url found in production graph",
                },
            }

        work_dir = Path(tempfile.gettempdir()) / f"cineforge_graph_{job_id}"
        work_dir.mkdir(parents=True, exist_ok=True)
        clip_paths: list[Path] = []
        for idx, item in enumerate(ordered_outputs):
            clip_path = work_dir / f"graph_{idx:03d}_{item['shot_id']}.mp4"
            await _download_file(str(item["url"]), clip_path)
            clip_paths.append(clip_path)

        final_mp4 = work_dir / "graph_final.mp4"
        graded_mp4 = work_dir / "graph_final_graded.mp4"
        bible = plan.continuity_bible
        final_audio_plan = audio_plan or {"mode": "silent_native"}
        assembler = AssembleWorker(work_dir=str(work_dir))
        await asyncio.to_thread(
            assembler.assemble,
            video_paths=[str(p) for p in clip_paths],
            audio_plan=final_audio_plan,
            output_path=str(final_mp4),
            bgm_path=final_audio_plan.get("bgm_path"),
            target_resolution=_resolution_for_aspect(bible.aspect_ratio, resolution),
        )
        await asyncio.to_thread(
            _apply_color_consistency,
            str(final_mp4),
            str(graded_mp4),
            bible_color_grading=bible.visual_style.color_grading,
        )
        output_url = await r2_storage.upload_with_fallback(
            graded_mp4,
            key=f"video/{job_id}/final.mp4",
            content_type="video/mp4",
        )
        duration_s = sum(int(getattr(s, "duration_s", 0) or 0) for s in plan.shot_list)
        _update_job(
            jobs_store,
            job_id,
            status="done",
            progress=100,
            current_step="done",
            output_path=str(graded_mp4),
            output_url=output_url,
            duration_s=duration_s,
        )
        try:
            director_history.record_job(
                job_id=job_id,
                plan_id=plan.plan_id,
                mode=(jobs_store or {}).get(job_id, {}).get("mode") or "graph_executor",
                status="done",
                output_url=output_url,
                title=bible.title,
                duration_s=duration_s,
                cost_estimate_usd=plan.cost_estimate.total_cost_usd,
                plan=plan.model_dump(),
                chain=[
                    {
                        "shot_id": item["shot_id"],
                        "video_url": item["url"],
                        "render_mode": item.get("render_mode"),
                        "model_key": item.get("model_key"),
                    }
                    for item in ordered_outputs
                ],
                created_at=(jobs_store or {}).get(job_id, {}).get("created_at"),
            )
        except Exception as e:
            logger.warning(f"[graph_executor] director_history.record_job fail {job_id}: {e}")
        return {
            "outcome": "success",
            "payload_patch": {
                "executor_status": "assembled_by_video_worker",
                "output_url": output_url,
                "output_path": str(graded_mp4),
                "clip_count": len(clip_paths),
                "duration_s": duration_s,
            },
        }

    return {
        "render_shot": _render,
        "retry_shot": _render,
        "run_qa": _qa,
        "assemble_final": _assembly,
    }


def graph_executor_handlers_from_artifact(
    *,
    job_id: str,
    jobs_store: Optional[dict] = None,
    use_llm_scene_gen: bool = True,
) -> dict[str, Any]:
    """Load a persisted autonomous artifact and build paid graph handlers.

    This is intended for trusted background workers only. It reconstructs the
    DirectorPlan and reference URLs saved at planning time.
    """
    from core import production_artifacts

    snapshot = production_artifacts.load_snapshot(job_id)
    if not snapshot:
        raise ValueError(f"production artifact for job '{job_id}' not found")
    plan_payload = snapshot.get("director_plan")
    if not isinstance(plan_payload, dict):
        raise ValueError(
            f"production artifact for job '{job_id}' is missing director_plan; re-run autonomous planning"
        )
    plan = DirectorPlan.model_validate(plan_payload)
    request_meta = snapshot.get("request_meta") or {}
    reference_images = list(request_meta.get("reference_image_urls") or [])
    reference_videos = list(request_meta.get("reference_video_urls") or [])
    reference_audios = list(request_meta.get("reference_audio_urls") or [])
    resolved_model = str(request_meta.get("resolved_model") or request_meta.get("user_model") or "auto")
    resolution = str(request_meta.get("resolution") or "720p")
    return graph_executor_handlers_for_plan(
        job_id=job_id,
        plan=plan,
        reference_images=reference_images,
        reference_videos=reference_videos,
        reference_audios=reference_audios,
        user_model=resolved_model,
        resolution=resolution,
        jobs_store=jobs_store,
        use_llm_scene_gen=use_llm_scene_gen,
    )


# ============================================================
# Helpers
# ============================================================
def _previous_last_frame_from_graph(
    *,
    job_id: str,
    previous_shot_id: Optional[str],
) -> Optional[str]:
    if not previous_shot_id:
        return None
    payload = _shot_payload_from_graph(job_id=job_id, shot_id=str(previous_shot_id))
    return payload.get("last_frame_url") or payload.get("output_url") or payload.get("video_url")


def _shot_payload_from_graph(*, job_id: str, shot_id: str) -> dict[str, Any]:
    if not shot_id:
        return {}
    try:
        graph = production_graph_store.load_graph(job_id) or {}
        for node in graph.get("nodes") or []:
            if node.get("id") == f"shot_{shot_id}":
                payload = node.get("payload") or {}
                return payload if isinstance(payload, dict) else {}
    except Exception as e:
            logger.warning(f"[graph_executor] failed to load shot payload {job_id}/{shot_id}: {e}")
    return {}


def _local_video_path_for_graph_qa(
    *,
    job_id: str,
    shot_id: str,
    shot_payload: dict[str, Any],
) -> Optional[Path]:
    """Return an existing local video path for graph QA, if one is available."""
    for key in ("output_path", "local_path", "clip_path"):
        value = shot_payload.get(key)
        if value:
            path = Path(str(value))
            if path.exists():
                return path
    for key in ("output_url", "video_url", "retry_video_url"):
        value = str(shot_payload.get(key) or "")
        if value.startswith("file://"):
            path = Path(value[7:])
            if path.exists():
                return path
    work_dir = Path(tempfile.gettempdir()) / f"cineforge_graph_qa_{job_id}"
    cached = work_dir / f"qa_{shot_id}.mp4"
    if cached.exists():
        return cached
    return None


def _ordered_rendered_shot_outputs(
    *,
    job_id: str,
    plan: DirectorPlan,
) -> list[dict[str, Any]]:
    """Return rendered shot outputs in timeline order for graph assembly."""
    try:
        graph = production_graph_store.load_graph(job_id) or {}
    except Exception as e:
        logger.warning(f"[graph_executor] failed to load graph for assembly {job_id}: {e}")
        return []

    payload_by_shot: dict[str, dict[str, Any]] = {}
    for node in graph.get("nodes") or []:
        if node.get("kind") != "shot":
            continue
        payload = node.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        shot_id = str(payload.get("shot_id") or str(node.get("id") or "").replace("shot_", ""))
        url = payload.get("output_url") or payload.get("video_url") or payload.get("retry_video_url")
        if not shot_id or not url:
            continue
        payload_by_shot[shot_id] = {**payload, "shot_id": shot_id, "url": url}

    ordered: list[dict[str, Any]] = []
    for shot in plan.shot_list:
        item = payload_by_shot.get(str(shot.shot_id))
        if item:
            ordered.append(item)
    if ordered:
        return ordered

    return sorted(
        payload_by_shot.values(),
        key=lambda item: (float(item.get("start_s") or 0), str(item.get("shot_id") or "")),
    )


def _update_job(store: Optional[dict], job_id: str, **fields: Any) -> None:
    if store is None:
        return
    if job_id not in store:
        store[job_id] = {}
    store[job_id].update(fields)


def _graph_update_node(
    job_id: str,
    node_id: str,
    status: str,
    payload_patch: Optional[dict[str, Any]] = None,
) -> None:
    """Best-effort graph status update for autonomous long-form observability."""
    try:
        production_graph_store.update_node_status(
            job_id=job_id,
            node_id=node_id,
            status=status,
            payload_patch=payload_patch or {},
        )
    except Exception as e:
        logger.warning(f"[production_graph_store] node update failed {job_id}/{node_id}: {e}")


def _qa_node_status(report: dict[str, Any]) -> str:
    status = str((report or {}).get("status") or "")
    if status == "fail":
        return "failed"
    if status == "warn":
        return "warn"
    if status in ("pending_visual_qa", "pending"):
        return "pending_visual_qa"
    return "passed"


def _track_prediction(store: Optional[dict], job_id: str, prediction_id: str) -> None:
    """V5.1 — Register a vendor prediction_id while it's in-flight so /cancel
    can call atlas_client.cancel_prediction() on it. Also stores the most
    recent one as `current_prediction_id` for quick lookup."""
    if store is None or job_id not in store:
        return
    rec = store[job_id]
    pred_list = rec.setdefault("prediction_ids", [])
    if prediction_id and prediction_id not in pred_list:
        pred_list.append(prediction_id)
    rec["current_prediction_id"] = prediction_id


class JobCancelledError(RuntimeError):
    """V5.1 — raised when the worker detects status='cancelled' between shots
    so the outer `_run()` task exits cleanly without marking as failed."""


def _check_cancelled(store: Optional[dict], job_id: str) -> None:
    """V5.1 — peek at jobs_store status flag, raise JobCancelledError if user
    has cancelled. Called between shots in the chain loop so we don't fire
    additional vendor calls after a cancel."""
    if store is None or job_id not in store:
        return
    if store[job_id].get("status") == "cancelled":
        raise JobCancelledError(f"Job {job_id} cancelled by user")


async def _convert_to_48khz_wav(
    audio_url: str,
    job_id: str,
    shot_id: str,
) -> Optional[str]:
    """V5.2 — Download a TTS MP3, convert to 48kHz mono WAV via FFmpeg, upload
    to R2, return new URL. Returns None on any failure (caller falls back to
    the original MP3). Wan 2.7 lip-sync model prefers this format — feeding
    44.1kHz MP3 still works but produces mild formant smearing.

    The conversion is one-shot per TTS clip (small files, <1s ffmpeg) and the
    WAV gets cached in R2 keyed by job_id + shot_id so re-renders don't redo.
    """
    import subprocess as _sp
    work_dir = Path(tempfile.gettempdir()) / f"cineforge_wav_{job_id}"
    work_dir.mkdir(parents=True, exist_ok=True)
    mp3_path = work_dir / f"{shot_id}.mp3"
    wav_path = work_dir / f"{shot_id}.wav"
    try:
        await _download_file(audio_url, mp3_path, timeout_s=30.0)
        # FFmpeg: 48kHz, 16-bit PCM, mono — Wan-friendly
        cmd = [
            "ffmpeg", "-y", "-i", str(mp3_path),
            "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le",
            str(wav_path),
        ]
        await asyncio.to_thread(_sp.run, cmd, check=True, capture_output=True, timeout=30)
        # Upload to R2 if available
        try:
            key = f"tts_wav/{job_id}/{shot_id}.wav"
            uploaded = await r2_storage.upload_with_fallback(
                str(wav_path), key, content_type="audio/wav"
            )
            # Only accept R2 https URL (Wan won't accept file:// local path)
            if uploaded and uploaded.startswith("http"):
                return uploaded
            return None
        except Exception as e:
            logger.warning(f"[V5.2 WAV] R2 upload fail ({shot_id}): {e}")
            return None
    except Exception as e:
        logger.warning(f"[V5.2 WAV] ffmpeg convert fail ({shot_id}): {e}")
        return None
    finally:
        # Best-effort temp cleanup
        try:
            if mp3_path.exists(): mp3_path.unlink()
            if wav_path.exists(): wav_path.unlink()
        except OSError:
            pass


async def _download_file(url: str, dest: Path, timeout_s: float = 120.0) -> None:
    async with httpx.AsyncClient(timeout=timeout_s) as c:
        async with c.stream("GET", url) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                async for chunk in r.aiter_bytes(chunk_size=64 * 1024):
                    f.write(chunk)


async def _persist_frame_samples(job_id: str, shot_id: str, frame_samples: dict) -> dict:
    """Copy sampled frames out of temp work_dir and upload/fallback to stable URLs."""
    frames = list(frame_samples.get("frames") or [])
    if not frames:
        return frame_samples

    stable_dir = Path(__file__).parent.parent / "data" / "qa_frames" / job_id / shot_id
    stable_dir.mkdir(parents=True, exist_ok=True)
    persisted: list[dict] = []
    for frame in frames:
        src = Path(str(frame.get("path") or ""))
        if not src.exists():
            persisted.append({**frame, "persist_status": "missing_source"})
            continue
        dest = stable_dir / src.name
        try:
            await asyncio.to_thread(shutil.copy2, src, dest)
            key = f"qa_frames/{job_id}/{shot_id}/{dest.name}"
            url = await r2_storage.upload_with_fallback(
                dest, key=key, content_type="image/jpeg"
            )
            persisted.append({
                **frame,
                "path": str(dest),
                "url": url,
                "persist_status": "ok",
            })
        except Exception as e:
            logger.warning(f"[VideoWorker QA] persist frame fail {job_id}/{shot_id}/{src.name}: {e}")
            persisted.append({**frame, "persist_status": "failed", "error": str(e)[:160]})

    return {
        **frame_samples,
        "frames": persisted,
        "persisted": any(f.get("persist_status") == "ok" for f in persisted),
        "stable_dir": str(stable_dir),
    }


def _resolution_for_aspect(aspect: str, resolution: str) -> tuple[int, int]:
    """Map 'resolution' + aspect → (w, h) for FFmpeg scale.

    Loose mapping — production should read per-model spec.
    """
    short_side = {
        "480p": 480, "540p": 540, "720p": 720, "720P": 720,
        "1080p": 1080, "1080P": 1080,
    }.get(resolution, 720)

    if aspect == "9:16":
        return (short_side * 9 // 16, short_side)  # portrait
    if aspect == "16:9":
        return (short_side * 16 // 9, short_side)
    if aspect == "1:1":
        return (short_side, short_side)
    return (1080, 1920)


def _apply_color_consistency(input_path: str, output_path: str, bible_color_grading: str) -> None:
    """Single FFmpeg pass that enforces a consistent color grade across the whole video.

    Maps the bible's color_grading string to a deterministic FFmpeg `eq` / `curves` chain.
    Anything not matched → identity (saturation slightly up to keep "real UGC" feel).
    """
    import subprocess

    grade = (bible_color_grading or "").lower()
    # Heuristic mapping — extend over time
    if any(k in grade for k in ["teal", "orange"]):
        vf = "curves=preset=increase_contrast,eq=saturation=1.10:contrast=1.05"
    elif any(k in grade for k in ["warm", "filmic", "golden"]):
        vf = "eq=gamma_r=1.06:gamma_b=0.95:saturation=1.05,curves=preset=lighter"
    elif any(k in grade for k in ["pastel", "airy", "soft"]):
        vf = "eq=brightness=0.02:saturation=0.90:contrast=0.95"
    elif any(k in grade for k in ["noir", "desaturated", "moody"]):
        vf = "eq=saturation=0.55:contrast=1.10"
    elif any(k in grade for k in ["cinematic", "35mm"]):
        vf = "curves=preset=increase_contrast,eq=saturation=1.05"
    else:
        vf = "eq=saturation=1.03"

    cmd = [
        "ffmpeg", "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy",
        "-y", output_path,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    except Exception as e:
        logger.warning(f"[VideoWorker V3] color pass fail (using ungraded): {e}")
        import shutil
        shutil.copy(input_path, output_path)


# ============================================================
# V4 Sprint1 Task F — Auto pre-render dialogue TTS per shot
# ============================================================
async def _pre_render_dialogue_tts(
    job_id: str,
    shots: list[Shot],
    voice_persona: Optional[str] = None,
    user_model: Optional[str] = None,
) -> dict[str, str]:
    """Pre-render TTS Việt for every shot that has dialogue_vn.

    Returns: {shot_id: audio_url} for use as Wan-driven audio + assemble timeline.

    Voice preset selection priority:
        1. `voice_persona` arg (if provided and matches a preset key)
        2. ENV `GENMAX_DEFAULT_PRESET`
        3. Hard fallback "mai"

    V5.2 — Wan 2.7 lip-sync upgrade (per Grok V2 research, Wan tutorial 2026):
        When user_model == "wan_2_7", we now post-process each TTS MP3 →
        48kHz mono WAV via FFmpeg + upload to R2 → swap audio_url. Wan's
        lip-sync model expects 48kHz WAV; feeding 44.1kHz MP3 causes mild
        formant smearing. For Seedance native audio (no lip-sync), 44.1kHz
        MP3 is fine — we skip the conversion to save R2 bandwidth.
    """
    try:
        from vendors.genmax import genmax_client, VIETNAMESE_VOICE_PRESETS
    except ImportError:
        return {}
    if genmax_client is None:
        logger.info(f"[VideoWorker V4] {job_id} GenMax client unavailable — skip TTS pre-render")
        return {}

    # Pick preset
    import os
    preset = None
    if voice_persona and voice_persona in VIETNAMESE_VOICE_PRESETS:
        preset = voice_persona
    elif os.getenv("GENMAX_DEFAULT_PRESET"):
        env_preset = os.getenv("GENMAX_DEFAULT_PRESET")
        if env_preset in VIETNAMESE_VOICE_PRESETS:
            preset = env_preset
    preset = preset or "mai"

    out: dict[str, str] = {}
    SUCCESS_STATUSES = {"completed", "succeeded", "success"}
    for shot in shots:
        line = (shot.audio.dialogue_vn or "").strip()
        if not line:
            continue
        try:
            submit_resp = await asyncio.to_thread(
                genmax_client.text_to_speech_by_preset,
                text=line,
                preset=preset,
            )
            # AUDIT FIX L4 — mirror audio_direct.py key-order convention
            # (`id` first, `history_id` fallback) so we agree with the existing
            # production endpoint on key precedence when both are present.
            history_id = submit_resp.get("id") or submit_resp.get("history_id")
            if not history_id:
                logger.warning(
                    f"[VideoWorker V4] TTS submit for {shot.shot_id} no history_id, resp={submit_resp}"
                )
                continue
            final = await asyncio.to_thread(
                genmax_client.poll_until_done, history_id, timeout_s=60, interval_s=2.0
            )
            # AUDIT FIX M4 — verify status terminal-success AND grab audio_url
            # from nested result OR top-level (matches audio_direct.py:132).
            status = (final.get("status") or "").lower()
            if status not in SUCCESS_STATUSES:
                logger.warning(
                    f"[VideoWorker V4] TTS {shot.shot_id} status='{status}' "
                    f"err={final.get('error') or final.get('detail_error')}"
                )
                continue
            audio_url = (
                (final.get("result") or {}).get("audio_url")
                or final.get("audio_url")
            )
            if audio_url:
                # V5.2 — for Wan 2.7, convert MP3 → 48kHz mono WAV for cleaner lip-sync
                if user_model == "wan_2_7":
                    try:
                        wav_url = await _convert_to_48khz_wav(audio_url, job_id, shot.shot_id)
                        if wav_url:
                            audio_url = wav_url
                            logger.info(
                                f"[VideoWorker V5.2] {shot.shot_id} converted MP3 → 48kHz WAV for Wan lip-sync"
                            )
                    except Exception as e:
                        logger.warning(
                            f"[VideoWorker V5.2] {shot.shot_id} WAV convert fail (fallback to MP3): {e}"
                        )
                out[shot.shot_id] = audio_url
                logger.debug(
                    f"[VideoWorker V4] TTS {shot.shot_id} → {audio_url[:60]}..."
                )
        except Exception as e:
            logger.warning(
                f"[VideoWorker V4] TTS fail for {shot.shot_id} (continuing): {e}"
            )
    return out
