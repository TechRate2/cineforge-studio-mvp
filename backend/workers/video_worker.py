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
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Any

import httpx
from loguru import logger

from agent.schemas import DirectorPlan, Shot
from agent import continuity_manager, scene_generation_agent
from vendors.atlascloud import atlas_client
from vendors import r2_storage
from workers.assemble_worker import AssembleWorker
from workers import cost_gate
from core import director_history


# ============================================================
# Model routing — user model choice → AtlasCloud keys for ref / i2v
# ============================================================
USER_MODEL_TO_ATLAS_REF: dict[str, str] = {
    "vidu_q3": "vidu_q3_ref",
    "vidu_q3_mix": "vidu_q3_mix_ref",
    "wan_2_7": "wan_2_7_i2v",                  # wan only i2v
    "seedance_1_5_pro": "seedance_v15_pro_i2v",
    "seedance_2_0": "seedance_2_0_ref",
    "seedance_2_0_fast": "seedance_2_0_fast_ref",
}
USER_MODEL_TO_ATLAS_I2V: dict[str, str] = {
    # NOTE on Vidu chaining: Vidu Q3 has NO native i2v endpoint. The earlier
    # fallback to wan_2_7_i2v caused cross-family identity drift (Wan re-styles
    # the frame). The correct pattern is to STAY in the Vidu family and feed
    # the previous shot's last frame as an additional entry in the `images`
    # array of vidu_q3_ref — Vidu treats it as a strong style anchor. This is
    # what V3.1 does.
    "vidu_q3": "vidu_q3_ref",
    "vidu_q3_mix": "vidu_q3_mix_ref",
    "wan_2_7": "wan_2_7_i2v",
    "seedance_1_5_pro": "seedance_v15_pro_i2v",
    "seedance_2_0": "seedance_2_0_i2v",
    "seedance_2_0_fast": "seedance_2_0_fast_i2v",
}


def _resolve_models(user_model: str) -> tuple[str, str]:
    """Return (ref_key, i2v_key) for a user model choice."""
    if user_model == "auto":
        user_model = "seedance_2_0"
    return (
        USER_MODEL_TO_ATLAS_REF.get(user_model, "seedance_2_0_ref"),
        USER_MODEL_TO_ATLAS_I2V.get(user_model, "seedance_2_0_i2v"),
    )


# ============================================================
# Public entry
# ============================================================
async def render_plan(
    job_id: str,
    plan: DirectorPlan,
    reference_images: list[str],
    user_model: str,
    resolution: str,
    audio_plan: Optional[dict] = None,
    jobs_store: Optional[dict] = None,
    use_llm_scene_gen: bool = True,
    cost_gate_mode: str = "off",
    cost_gate_threshold: float = 7.0,
) -> dict:
    """Render a full DirectorPlan → final MP4.

    Args:
        job_id: UUID for tracking.
        plan: Validated DirectorPlan from Director Agent V3.
        reference_images: Full ordered list of uploaded refs (universal pool).
        user_model: vidu_q3 / wan_2_7 / seedance_2_0 / auto / ...
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

    # BUG #5 fix — "auto" giờ thật sự pick model dựa trên plan (heuristic).
    # Trước đó hardcode về seedance_2_0, không xứng với label "Auto".
    if user_model == "auto":
        from agent.model_picker import pick_model_for_plan
        picked, reasoning = pick_model_for_plan(plan, budget_tier="balanced")
        logger.info(f"[VideoWorker V3] auto-pick → {picked}: {reasoning}")
        # Sprint2 M12 — re-compute cost estimate against the ACTUAL picked model
        # (plan.cost_estimate was built using the original user_model 'auto'
        # placeholder $0.060/s heuristic — could be off-by-2x for premium models).
        _PER_S = {
            "vidu_q3": 0.042, "vidu_q3_mix": 0.106,
            "wan_2_7": 0.10,
            "seedance_1_5_pro": 0.047,
            "seedance_2_0": 0.096, "seedance_2_0_fast": 0.076,
        }.get(picked, 0.096)
        total_dur = sum(s.duration_s for s in shots)
        new_render_cost = round(_PER_S * total_dur, 3)
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

    # Stage 1 — Reference-chained render loop.
    # We invoke Scene Generation Agent LAZILY per shot (right before its render
    # call) so the LLM sees the live `last_frame_url` and can format the prompt
    # accordingly (chain frame carries identity → drop char refs etc.).
    work_dir = Path(tempfile.gettempdir()) / f"cineforge_{job_id}"
    work_dir.mkdir(parents=True, exist_ok=True)

    # BUG #3 fix — track last_frame by shot_id, not just "the previous one
    # we rendered". This is required when a shot chains back to a shot earlier
    # than the immediate predecessor (e.g. flashback / cutaway pattern where
    # S3.previous_shot_id == "S1"). The previous implementation always passed
    # the most-recently-rendered last_frame, which silently drifted identity.
    last_frame_urls_by_shot_id: dict[str, Optional[str]] = {}
    clip_paths: list[Path] = []
    chain_meta: list[dict] = []
    total_shots = len(shots)

    for i, shot in enumerate(shots):
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
            last_frame_url=chain_anchor_url if will_chain else None,
            llm_mode=use_llm_scene_gen,
            resolution=resolution,
            is_last_shot=(i == total_shots - 1),
            driven_audio_url=driven_audio_url,
        )

        kwargs = job.to_atlas_kwargs()
        kwargs["poll_interval_s"] = 5
        kwargs["timeout_s"] = 600

        logger.info(
            f"[VideoWorker V3] {job_id} shot {shot.shot_id} ({i + 1}/{total_shots}) "
            f"mode={job.render_mode} model={job.model_key} dur={job.duration_s}s "
            f"refs={len(job.reference_image_urls)}"
        )

        result = await asyncio.to_thread(atlas_client.generate_video, **kwargs)
        clip_url = result.get("video_url")
        if not clip_url:
            raise RuntimeError(f"shot {shot.shot_id}: AtlasCloud returned no video_url. {result}")

        clip_path = work_dir / f"shot_{i:02d}_{shot.shot_id}.mp4"
        await _download_file(clip_url, clip_path)
        clip_paths.append(clip_path)

        produced_last_frame = result.get("last_frame_url")
        last_frame_urls_by_shot_id[shot.shot_id] = produced_last_frame
        chain_meta.append({
            "shot_id": shot.shot_id,
            "model_key": job.model_key,
            "render_mode": job.render_mode,
            "video_url": clip_url,
            "last_frame_url": produced_last_frame,
            "duration_s": job.duration_s,
            "chained_from": psid if will_chain else None,
        })

    # Stage 3 — Assemble
    _update_job(jobs_store, job_id, status="assembling", progress=88, current_step="ffmpeg_assemble")

    final_mp4 = work_dir / "final.mp4"
    assembler = AssembleWorker(work_dir=str(work_dir))

    target_resolution = _resolution_for_aspect(bible.aspect_ratio, resolution)
    audio_plan = audio_plan or {"mode": "silent_native"}

    await asyncio.to_thread(
        assembler.assemble,
        video_paths=[str(p) for p in clip_paths],
        audio_plan=audio_plan,
        output_path=str(final_mp4),
        bgm_path=audio_plan.get("bgm_path"),
        target_resolution=target_resolution,
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

    _update_job(
        jobs_store, job_id,
        status="done", progress=100, current_step="done",
        output_path=str(color_pass_mp4),
        output_url=output_url,
        duration_s=sum(s.duration_s for s in shots),
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
    previous_last_frame_url: Optional[str] = None,
    jobs_store: Optional[dict] = None,
    use_llm_scene_gen: bool = True,
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

    _update_job(
        jobs_store, job_id,
        status="done", progress=100, current_step="done",
        output_path=str(clip_path),
        output_url=output_url,
    )

    # CRITICAL C6 — cleanup refine work_dir after R2 upload (clip persisted).
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


# ============================================================
# Helpers
# ============================================================
def _update_job(store: Optional[dict], job_id: str, **fields: Any) -> None:
    if store is None:
        return
    if job_id not in store:
        store[job_id] = {}
    store[job_id].update(fields)


async def _download_file(url: str, dest: Path, timeout_s: float = 120.0) -> None:
    async with httpx.AsyncClient(timeout=timeout_s) as c:
        async with c.stream("GET", url) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                async for chunk in r.aiter_bytes(chunk_size=64 * 1024):
                    f.write(chunk)


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
