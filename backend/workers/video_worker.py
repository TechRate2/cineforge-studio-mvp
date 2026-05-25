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
# V5.16 Fix#3 — Centralize render cost rates (was duplicated in 2 places).
# Source: verified against backend/agent/model_specs.py:cost_per_second_usd
# (2026-05-20). Update here when AtlasCloud changes pricing.
# ============================================================
RENDER_COST_PER_SECOND_USD: dict[str, float] = {
    "seedance_2_0": 0.096,
    "seedance_2_0_fast": 0.076,
    "wan_2_7": 0.10,
}
_DEFAULT_RATE_USD = 0.096


def get_render_cost_rate(user_model: str) -> float:
    """Return $/s render rate for a user_model. Falls back to Seedance 2.0 rate."""
    return RENDER_COST_PER_SECOND_USD.get(user_model, _DEFAULT_RATE_USD)


# ============================================================
# Model routing — user_model → AtlasCloud spec key per render mode
# SEEDANCE 2.0 CORE PATH: ref → reference-to-video, i2v → image-to-video
# FALLBACK PATH (Wan 2.7): only i2v endpoint available
# ============================================================
USER_MODEL_TO_ATLAS_REF: dict[str, str] = {
    "seedance_2_0": "seedance_2_0_ref",
    "seedance_2_0_fast": "seedance_2_0_fast_ref",
    "wan_2_7": "wan_2_7_i2v",                  # Wan: ref falls back to i2v
}
USER_MODEL_TO_ATLAS_I2V: dict[str, str] = {
    "seedance_2_0": "seedance_2_0_i2v",
    "seedance_2_0_fast": "seedance_2_0_fast_i2v",
    "wan_2_7": "wan_2_7_i2v",
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
        duration_hint_s=duration_hint_s,
        user_model=user_model,
    ))

    # Render the DirectorPlan via existing pipeline (backward-compat path)
    render_result = await render_plan(
        job_id=job_id,
        plan=result.director_plan,
        reference_images=reference_image_urls,
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
        "viral_hook_pattern": result.planner_out.hook_pattern,
        "hook_first_3s": result.planner_out.hook_first_3s,
    }
    return render_result


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

    # BUG #5 fix — "auto" giờ thật sự pick model dựa trên plan (heuristic).
    # Trước đó hardcode về seedance_2_0, không xứng với label "Auto".
    if user_model == "auto":
        from agent.model_picker import pick_model_for_plan
        picked, reasoning = pick_model_for_plan(plan, budget_tier="balanced")
        logger.info(f"[VideoWorker V3] auto-pick → {picked}: {reasoning}")
        # Sprint2 M12 — re-compute cost estimate against the ACTUAL picked model
        # (plan.cost_estimate was built using the original user_model 'auto'
        # placeholder $0.060/s heuristic — could be off-by-2x for premium models).
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

    # ============================================================
    # STRATEGY A — SINGLE CALL (Seedance 2.0 / 2.0 Fast multi-shot inline)
    # ============================================================
    if strategy == "single_call_multi_shot":
        _update_job(jobs_store, job_id, current_step="single_call_render")
        work_dir = Path(tempfile.gettempdir()) / f"cineforge_{job_id}"
        work_dir.mkdir(parents=True, exist_ok=True)

        spec = build_seedance_2_multi_shot(
            bible=bible,
            shots=list(shots),
            reference_images=reference_images,
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

        logger.info(
            f"[VideoWorker V4.5] single-call render: {ref_key_default} "
            f"dur={spec.total_duration_s}s refs={len(spec.reference_image_urls)} "
            f"prompt_chars={len(spec.prompt)}"
        )
        atlas_kwargs = {
            "model_key": ref_key_default,
            "prompt": spec.prompt,
            "negative_prompt": spec.negative_prompt,
            "images": spec.reference_image_urls,
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
        single_result = await asyncio.to_thread(atlas_client.generate_video, **atlas_kwargs)
        clip_url = single_result.get("video_url")
        if not clip_url:
            raise RuntimeError(f"Single-call render returned no video_url. {single_result}")

        clip_path = work_dir / "single_call.mp4"
        await _download_file(clip_url, clip_path)
        clip_paths = [clip_path]
        chain_meta = [{
            "shot_id": "ALL",
            "model_key": ref_key_default,
            "render_mode": "single_call_multi_shot",
            "video_url": clip_url,
            "last_frame_url": None,
            "prediction_id": single_result.get("prediction_id"),
            "duration_s": spec.total_duration_s,
            "shot_timing": spec.shot_timing,  # for downstream audio_timeline
        }]

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
            "prediction_id": result.get("prediction_id"),
            "duration_s": job.duration_s,
            "chained_from": psid if will_chain else None,
        })

    # Stage 3 — Assemble
    _update_job(jobs_store, job_id, status="assembling", progress=88, current_step="ffmpeg_assemble")

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
