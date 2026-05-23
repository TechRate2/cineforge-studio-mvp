"""Render Pipeline — Phase 3 orchestrator (V3 era).

3 paths:
    A. render_approved(job_id, request)  — Director Agent Phase 2 approved + V3 strategy
       approved_shots + approved_character_sheet → strategy.build_prompt() pure
       (KHÔNG tốn LLM call, format đúng spec mỗi model)
    B. render_scenes(job_id, request)    — TopView V2 Multi-Scene queue
       approved_scenes[] user-edit → parallel render N clips + FFmpeg concat
    C. render_auto(job_id, request)      — ⚠️ DEPRECATED (V3 yêu cầu /propose trước)

Sub-stages (cả 2 path đều có):
    1. (path A) Reuse proposal data | (path B) Run Analyzer
    2. Generator → video prompt
    3. AtlasCloud video gen → MP4 clips
    4. GenMax TTS → voice audio
    5. ElevenLabs SFX (nếu audio_mode=asmr_macro)
    6. FFmpeg assemble (assemble_worker)
    7. R2 upload → public URL
    8. Update JOBS dict status → done

ASYNC pattern: tất cả vendor call sync wrap qua asyncio.to_thread.

NOTE: Dramatiq cron + Redis worker integration sẽ làm Week 4 polish.
Hiện tại render runs inline trong same FastAPI event loop (acceptable cho 2-4 min job).
"""

import asyncio
import os
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx
from loguru import logger

from vendors.atlascloud import atlas_client as atlas_video
from vendors.genmax import genmax_client, VIETNAMESE_VOICE_PRESETS
from vendors.elevenlabs_sfx import elevenlabs_sfx_client
from workers.assemble_worker import AssembleWorker


# ============================================
# Model key mapping — user choice → AtlasCloud model_specs key
# ============================================
# AUDIT FIX: sync với VIDEO_MODEL_SPECS ground truth.
# - REMOVED wan_2_2_turbo (KHÔNG có endpoint Atlas)
# - FIXED seedance_1_5_pro key → seedance_v15_pro_i2v (real key có "v")
# - FIXED seedance_2_0_fast key → seedance_2_0_fast_ref (ref variant default)
USER_MODEL_TO_ATLAS_KEY: dict[str, str] = {
    "vidu_q3": "vidu_q3_ref",
    "vidu_q3_mix": "vidu_q3_mix_ref",
    "wan_2_7": "wan_2_7_i2v",
    "seedance_1_5_pro": "seedance_v15_pro_i2v",  # ✅ real Atlas key
    "seedance_2_0": "seedance_2_0_ref",
    "seedance_2_0_fast": "seedance_2_0_fast_ref",
}

# I2V mapping — dùng khi CÓ approved_keyframes (Phase 2.5 đã gen ảnh).
# Mỗi keyframe → 1 video clip i2v ngắn (3-5s). Concat sau bằng FFmpeg.
# Giữ identity 100% (character không đổi xuyên cảnh) + motion mượt hơn t2v.
USER_MODEL_TO_ATLAS_I2V_KEY: dict[str, str] = {
    "vidu_q3": "wan_2_7_i2v",                     # Vidu Q3 không có i2v native — fallback wan
    "vidu_q3_mix": "wan_2_7_i2v",
    "wan_2_7": "wan_2_7_i2v",
    "seedance_1_5_pro": "seedance_v15_pro_i2v",
    "seedance_2_0": "seedance_2_0_i2v",
    "seedance_2_0_fast": "seedance_2_0_fast_i2v",
}


# ============================================
# Public API — called from routes/jobs.py
# ============================================

async def render_approved(job_id: str, request: dict, jobs_store: dict) -> dict:
    """Path A — Director Agent Phase 2 approved path.

    Args:
        job_id: UUID string từ jobs.py.
        request: CreateJobRequest.model_dump().
        jobs_store: ref tới JOBS dict (in-memory store).

    Returns:
        dict {output_url, duration_s, cost_actual_usd, ...}.
    """
    approved_script = request.get("approved_script") or {}
    reference_mapping = request.get("reference_mapping") or {}
    settings = request.get("settings") or {}
    reference_images = request.get("reference_images") or []

    logger.info(
        f"[RenderPipeline] APPROVED path start: job={job_id}, "
        f"variant={approved_script.get('variant_id')}, "
        f"refs={len(reference_images)}"
    )

    _update_job(jobs_store, job_id, status="generating", progress=10,
                current_step="strategy_build")

    # Stage 2: V3 strategy.build_prompt() pure function — KHÔNG tốn LLM call.
    # YÊU CẦU: approved_shots + approved_character_sheet phải có từ Phase 2 /propose.
    approved_shots = request.get("approved_shots") or []
    approved_character_sheet = request.get("approved_character_sheet") or {}

    if not approved_shots:
        msg = (
            "approved_shots missing (V3 yêu cầu). Frontend phải /propose trước rồi pass "
            "shots + character_sheet vào /jobs/ugc."
        )
        logger.error(f"[RenderPipeline] {msg}")
        _update_job(jobs_store, job_id, status="failed", error_message=msg)
        raise ValueError(msg)

    try:
        gen_result = await asyncio.to_thread(
            _build_via_strategy,
            approved_script=approved_script,
            approved_shots=approved_shots,
            approved_character_sheet=approved_character_sheet,
            reference_images=reference_images,
            settings=settings,
        )
        logger.info(
            f"[RenderPipeline] V3 strategy build: model={gen_result.get('_strategy_user_model')}, "
            f"prompt_len={len(gen_result.get('prompt_full', ''))}, "
            f"submit_path={gen_result.get('_strategy_submit_path')}"
        )
    except Exception as e:
        logger.exception(f"[RenderPipeline] V3 strategy build fail: {e}")
        _update_job(jobs_store, job_id, status="failed", error_message=str(e))
        raise

    # Phase 2.5: approved keyframes (optional) → i2v render path
    approved_keyframes = request.get("approved_keyframes") or []

    return await _run_render_chain(
        job_id=job_id,
        gen_result=gen_result,
        settings=settings,
        reference_images=reference_images,
        jobs_store=jobs_store,
        approved_keyframes=approved_keyframes,
    )


def _merge_scenes_to_multishot_prompt(scenes: list[dict]) -> str:
    """Combine N scenes thành 1 multi-shot prompt cho Seedance 2.0 / model support multi-shot.

    Format: mỗi scene là 1 segment với marker `[Shot N — Xs]` + nội dung scene.
    Giữ nguyên tokens `[Image M]` (Seedance hiểu @image syntax) — KHÔNG strip.

    Pattern: TopView / Krea / Daymade — 1 prompt 15s liền mạch tốt hơn 2 clip ghép.
    """
    parts: list[str] = []
    for i, sc in enumerate(scenes):
        dur = sc.get("duration_s", 5)
        prompt = (sc.get("prompt") or "").strip()
        if not prompt:
            continue
        # Convert "[Image N]" → "@image_N" cho Seedance multi-shot syntax
        # Seedance recognise cả 2 format nhưng @image rõ hơn cho parser của họ
        prompt_normalized = re.sub(r"\[Image\s+(\d+)\]", r"@image_\1", prompt)
        marker = f"[Shot {i + 1} — {dur}s]"
        parts.append(f"{marker} {prompt_normalized}")
    return " ".join(parts)


def _chunk_scenes_by_max_duration(scenes: list[dict], max_dur: int) -> list[list[dict]]:
    """Chia N scenes thành chunks, mỗi chunk có tổng duration ≤ max_dur.

    Greedy bin-packing: gom scenes liên tiếp đến khi vượt max → chunk mới.
    Trả list of chunk (mỗi chunk là list[scene]).
    Edge case: 1 scene duration > max_dur → giữ riêng 1 chunk (sẽ clamp duration ở render).
    """
    chunks: list[list[dict]] = []
    current: list[dict] = []
    current_sum = 0
    for sc in scenes:
        dur = sc.get("duration_s", 5)
        if current and current_sum + dur > max_dur:
            chunks.append(current)
            current = [sc]
            current_sum = dur
        else:
            current.append(sc)
            current_sum += dur
    if current:
        chunks.append(current)
    return chunks


async def _render_extended_chain(
    job_id: str,
    approved_scenes: list[dict],
    reference_images: list[str],
    base_atlas_key: str,      # ref model cho chunk 1 (vd seedance_2_0_ref)
    i2v_atlas_key: str,       # i2v model cho chunks 2+ (vd seedance_2_0_i2v)
    aspect: str,
    resolution: str,
    max_chunk_duration: int,
    negative_prompt: Optional[str],
    work_dir: Path,
    jobs_store: Any,
) -> dict:
    """Extend chain render — gen N chunks với last_image chain → FFmpeg concat.

    Workflow:
        1. Chia scenes thành chunks ≤ max_chunk_duration mỗi cái
        2. Chunk 1: gen với base_model + return_last_frame=True
        3. Chunks 2+: i2v với image=previous_last_frame_url + return_last_frame=True
        4. FFmpeg concat all chunks → final.mp4
    """
    chunks = _chunk_scenes_by_max_duration(approved_scenes, max_chunk_duration)
    total_duration = sum(s.get("duration_s", 5) for s in approved_scenes)

    _update_job(
        jobs_store, job_id,
        status="rendering", progress=15,
        current_step=f"extend_chain_chunk_1/{len(chunks)}",
    )
    logger.info(
        f"[render_scenes] EXTEND_CHAIN: {len(approved_scenes)} scenes → "
        f"{len(chunks)} chunks ({[sum(s.get('duration_s', 5) for s in c) for c in chunks]}s) "
        f"base={base_atlas_key}, chain={i2v_atlas_key}"
    )

    chunk_clips: list[Path] = []
    last_frame_url: Optional[str] = None
    last_prediction_id: Optional[str] = None

    for idx, chunk in enumerate(chunks):
        chunk_dur = min(sum(s.get("duration_s", 5) for s in chunk), max_chunk_duration)
        chunk_prompt = _merge_scenes_to_multishot_prompt(chunk)
        is_first = idx == 0
        is_last_chunk = idx == len(chunks) - 1

        _update_job(
            jobs_store, job_id,
            current_step=f"extend_chain_chunk_{idx + 1}/{len(chunks)}",
        )

        # Gather all refs từ chunk's scenes
        all_refs_1based: list[int] = []
        for sc in chunk:
            for i in (sc.get("image_refs") or []):
                if isinstance(i, int) and i not in all_refs_1based:
                    all_refs_1based.append(i)
        chunk_refs = [
            reference_images[i - 1] for i in all_refs_1based
            if 0 < i <= len(reference_images)
        ]
        if not chunk_refs and is_first and reference_images:
            chunk_refs = reference_images[:]

        # Chunk 1 dùng base model (ref-to-video, multi-shot). Chunks 2+ dùng i2v với last_image.
        if is_first:
            call_kwargs = {
                "model_key": base_atlas_key,
                "prompt": chunk_prompt,
                "images": chunk_refs if chunk_refs else None,
                "duration_s": chunk_dur,
                "resolution": resolution,
                "aspect_ratio": aspect,
                "negative_prompt": negative_prompt,
                "return_last_frame": True if not is_last_chunk else None,
                "poll_interval_s": 5,
                "timeout_s": 600,
            }
        else:
            if not last_frame_url:
                raise RuntimeError(
                    f"[extend_chain] Chunk {idx} cần last_frame_url từ chunk trước, "
                    f"nhưng chunk {idx} previous KHÔNG trả last_frame_url. "
                    f"Atlas có thể disable return_last_frame ở model này."
                )
            call_kwargs = {
                "model_key": i2v_atlas_key,
                "prompt": chunk_prompt,
                "image": last_frame_url,  # i2v singular
                "duration_s": chunk_dur,
                "resolution": resolution,
                "aspect_ratio": aspect,
                "negative_prompt": negative_prompt,
                "return_last_frame": True if not is_last_chunk else None,
                "poll_interval_s": 5,
                "timeout_s": 600,
            }

        logger.info(
            f"[render_scenes] EXTEND chunk {idx + 1}/{len(chunks)} "
            f"dur={chunk_dur}s mode={'BASE' if is_first else 'i2v_chain'}"
        )

        try:
            result = await _call_atlas_with_retry(
                fn=atlas_video.generate_video,
                kwargs=call_kwargs,
                scope=f"extend_chain:{job_id[:8]}:chunk_{idx + 1}",
                max_attempts=3,
            )
        except Exception as e:
            logger.exception(f"[render_scenes] EXTEND chunk {idx + 1} fail: {e}")
            _update_job(
                jobs_store, job_id, status="failed",
                error_message=f"Extend chain chunk {idx + 1} fail: {str(e)[:300]}",
            )
            raise

        last_frame_url = result.get("last_frame_url")
        last_prediction_id = result.get("prediction_id") or last_prediction_id
        clip_url = result.get("video_url")
        if not clip_url:
            raise RuntimeError(
                f"[extend_chain] chunk {idx + 1} không có video_url. Result: {result}"
            )

        clip_path = work_dir / f"chunk_{idx + 1:02d}.mp4"
        await _download_file(clip_url, clip_path, expected_content_prefix="video/")
        chunk_clips.append(clip_path)
        logger.info(
            f"[render_scenes] EXTEND chunk {idx + 1} downloaded "
            f"{clip_path.stat().st_size / 1024:.0f}KB, last_frame={'YES' if last_frame_url else 'NO'}"
        )

    if last_prediction_id:
        _update_job(jobs_store, job_id, atlas_prediction_id=last_prediction_id)

    # FFmpeg concat chunks (codec đồng nhất vì cùng Seedance family)
    _update_job(jobs_store, job_id, status="assembling", progress=85, current_step="ffmpeg_concat_chain")
    final_mp4 = work_dir / "final.mp4"
    await asyncio.to_thread(_ffmpeg_concat_clips, chunk_clips, final_mp4)
    logger.info(
        f"[render_scenes] EXTEND concat done: {len(chunk_clips)} chunks → "
        f"{final_mp4.stat().st_size / 1024:.0f}KB"
    )

    _update_job(jobs_store, job_id, status="uploading", progress=95, current_step="r2_upload")
    output_url = await _stage_upload_r2(final_mp4, job_id)

    _update_job(
        jobs_store, job_id,
        status="done", progress=100, current_step="done",
        output_url=output_url, duration_s=total_duration,
    )

    logger.info(f"[RenderPipeline] EXTEND_CHAIN Job {job_id} DONE → {output_url}")
    return {
        "output_url": output_url,
        "job_id": job_id,
        "scene_count": len(approved_scenes),
        "chunk_count": len(chunks),
        "total_duration_s": total_duration,
        "render_mode": "extend_chain",
    }


async def _render_single_merged(
    job_id: str,
    approved_scenes: list[dict],
    reference_images: list[str],
    atlas_key: str,
    aspect: str,
    resolution: str,
    total_duration: int,
    negative_prompt: Optional[str],
    work_dir: Path,
    jobs_store: Any,
) -> dict:
    """Single-call render — gen 1 video duy nhất từ N scenes merged.

    Pattern: Multi-shot prompt + reference_images full set → Atlas gen video duy nhất
    với cuts/scenes inline. KHÔNG concat → identity + motion consistency 100%.
    """
    _update_job(jobs_store, job_id, status="rendering", progress=20, current_step="single_merged_render")

    merged_prompt = _merge_scenes_to_multishot_prompt(approved_scenes)
    # Refs: union tất cả image_refs từ scenes (1-based → 0-based), dedupe + preserve order
    all_refs_1based: list[int] = []
    for sc in approved_scenes:
        for i in (sc.get("image_refs") or []):
            if isinstance(i, int) and i not in all_refs_1based:
                all_refs_1based.append(i)
    scene_refs = [
        reference_images[i - 1] for i in all_refs_1based
        if 0 < i <= len(reference_images)
    ]
    # Fallback: nếu prompt không có [Image N] mention nhưng có refs upload → pass hết
    if not scene_refs and reference_images:
        scene_refs = reference_images[:]

    logger.info(
        f"[render_scenes] SINGLE_MERGED → {atlas_key} dur={total_duration}s "
        f"refs={len(scene_refs)} prompt_len={len(merged_prompt)} "
        f"prompt_head='{merged_prompt[:120]}'"
    )

    try:
        result = await _call_atlas_with_retry(
            fn=atlas_video.generate_video,
            kwargs={
                "model_key": atlas_key,
                "prompt": merged_prompt,
                "images": scene_refs if scene_refs else None,
                "duration_s": total_duration,
                "resolution": resolution,
                "aspect_ratio": aspect,
                "negative_prompt": negative_prompt,
                "poll_interval_s": 5,
                "timeout_s": 600,
            },
            scope=f"render_scenes_merged:{job_id[:8]}",
            max_attempts=3,
        )
    except Exception as e:
        logger.exception(f"[render_scenes] SINGLE_MERGED fail: {e}")
        _update_job(
            jobs_store, job_id, status="failed",
            error_message=f"Single-merged render fail: {str(e)[:300]}",
        )
        raise

    clip_url = result.get("video_url")
    if not clip_url:
        raise RuntimeError(f"AtlasCloud không trả video_url. Result: {result}")

    if result.get("prediction_id"):
        _update_job(jobs_store, job_id, atlas_prediction_id=result["prediction_id"])

    final_mp4 = work_dir / "final.mp4"
    await _download_file(clip_url, final_mp4, expected_content_prefix="video/")
    logger.info(
        f"[render_scenes] SINGLE_MERGED downloaded {final_mp4.stat().st_size / 1024:.0f}KB"
    )

    _update_job(jobs_store, job_id, status="uploading", progress=95, current_step="r2_upload")
    output_url = await _stage_upload_r2(final_mp4, job_id)

    _update_job(
        jobs_store, job_id,
        status="done", progress=100, current_step="done",
        output_url=output_url, duration_s=total_duration,
    )

    logger.info(f"[RenderPipeline] SINGLE_MERGED Job {job_id} DONE → {output_url}")
    return {
        "output_url": output_url,
        "job_id": job_id,
        "scene_count": len(approved_scenes),
        "total_duration_s": total_duration,
        "render_mode": "single_merged",
    }


async def _call_atlas_with_retry(
    fn,
    kwargs: dict,
    scope: str,
    max_attempts: int = 3,
) -> dict:
    """FIX #4: Retry wrapper cho AtlasCloud calls — exponential backoff 2s/4s/8s.

    Retry NẾU:
        - httpx.HTTPStatusError 429 (rate limit)
        - httpx.HTTPStatusError 5xx (server error)
        - asyncio.TimeoutError
        - httpx.RequestError / ConnectError (network transient)

    KHÔNG retry NẾU:
        - 4xx khác 429 (auth/validation/credit) — fix tay
        - ValueError / KeyError (bug code)
        - HTTPStatusError 402 (insufficient balance)

    Args:
        fn: callable (sync) — sẽ wrap qua asyncio.to_thread
        kwargs: dict kwargs pass vào fn
        scope: label log (vd "render_scenes:S1")
        max_attempts: số attempt tối đa, mặc định 3

    Returns:
        dict result từ fn cuối cùng thành công.

    Raises:
        Exception cuối cùng nếu tất cả attempt fail.
    """
    import httpx as _httpx
    last_exc: Optional[BaseException] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await asyncio.to_thread(fn, **kwargs)
        except _httpx.HTTPStatusError as e:
            status = e.response.status_code if e.response is not None else 0
            # 402 — insufficient balance, không retry (cần nạp tiền)
            if status == 402:
                logger.error(f"[atlas_retry] {scope} 402 insufficient balance — fail fast")
                raise
            # 4xx khác 429 — fail fast (auth/validation)
            if 400 <= status < 500 and status != 429:
                logger.error(f"[atlas_retry] {scope} {status} client error — fail fast: {e}")
                raise
            last_exc = e
            should_retry = status == 429 or 500 <= status < 600
            if not should_retry or attempt >= max_attempts:
                raise
        except (asyncio.TimeoutError, _httpx.RequestError) as e:
            last_exc = e
            if attempt >= max_attempts:
                raise
        except Exception as e:
            # Unknown error — không retry (có thể là bug code/data)
            logger.exception(f"[atlas_retry] {scope} unknown error — fail fast")
            raise

        # Backoff: 2s / 4s / 8s
        backoff = 2 ** attempt
        logger.warning(
            f"[atlas_retry] {scope} attempt {attempt}/{max_attempts} failed "
            f"({type(last_exc).__name__}). Retry in {backoff}s..."
        )
        await asyncio.sleep(backoff)

    # Defensive — không reachable
    if last_exc:
        raise last_exc
    raise RuntimeError(f"[atlas_retry] {scope} no result + no exception captured")


async def render_scenes(job_id: str, request: dict, jobs_store: dict) -> dict:
    """Path C — Multi-Scene Queue render (TopView V2 pattern).

    Mỗi `approved_scenes[i]` = 1 clip riêng:
        - prompt từ user edit (đã có [Image N] mention tokens)
        - duration_s riêng (2-20s)
        - image_refs subset của reference_images[]
        - extends_from chain continuity

    Pipeline:
        1. Parallel render N scenes (Semaphore concurrency 3 — AtlasCloud rate-limit safe)
        2. FFmpeg concat clips theo thứ tự → final.mp4
        3. R2 upload → public URL

    Note: KHÔNG có TTS/SFX cho path này — scenes embed dialogue inline trong prompt
    (audio-driven model như Wan 2.7 tự gen voice). User có thể thêm audio sau qua editor riêng.
    """
    approved_scenes = request.get("approved_scenes") or []
    if not approved_scenes:
        raise ValueError("approved_scenes empty — cannot run render_scenes path")

    settings = request.get("settings") or {}
    reference_images = request.get("reference_images") or []
    user_model = settings.get("model", "vidu_q3")
    aspect = settings.get("aspect_ratio", "9:16")
    resolution = settings.get("resolution", "720p")

    if atlas_video is None:
        raise RuntimeError("AtlasCloud client chưa init — ATLASCLOUD_API_KEY missing?")

    atlas_key = USER_MODEL_TO_ATLAS_KEY.get(user_model, "vidu_q3_ref")
    # V3.1 — derive negative_prompt per-model (anti-artifact bake-in)
    try:
        from agent.strategies import get_strategy_for_model
        scenes_negative_prompt = get_strategy_for_model(user_model).negative_prompt()
    except Exception:
        scenes_negative_prompt = None
    # V3.2 — per-spec duration range (clamp user-edited scene duration)
    # Fix bug: Vidu Q3 min=3 nhưng user edit 2s → atlas reject 400
    from agent.model_specs import get_spec
    _spec = get_spec(atlas_key)
    _dur_min = _spec.get("duration", {}).get("min", 2)
    _dur_max = _spec.get("duration", {}).get("max", 20)
    logger.info(
        f"[RenderPipeline] SCENES path start: job={job_id}, "
        f"scenes={len(approved_scenes)}, atlas_model={atlas_key}, "
        f"spec_duration_range={_dur_min}-{_dur_max}s, "
        f"total_duration={sum(s.get('duration_s', 5) for s in approved_scenes)}s"
    )

    work_dir = Path(tempfile.gettempdir()) / f"scenes_{job_id[:8]}"
    work_dir.mkdir(parents=True, exist_ok=True)

    # FIX #1 (CRITICAL): Sanitize MỌI scene prompt user edit (Multi-Scene Editor)
    # trước khi gửi AtlasCloud — chặn prompt injection + strip PII (SĐT/email/CCCD).
    # Khác user_brief đã sanitize ở /propose — scene.prompt user edit POST-proposal,
    # đi thẳng vào render_pipeline KHÔNG qua sanitize → security hole.
    from core.sanitize import sanitize_prompt_injection, strip_pii
    total_flagged: list[str] = []
    total_pii: dict[str, int] = {}
    for sc in approved_scenes:
        raw = sc.get("prompt") or ""
        clean1, flagged = sanitize_prompt_injection(raw)
        clean2, pii_counts = strip_pii(clean1)
        sc["prompt"] = clean2
        if flagged:
            total_flagged.extend(flagged)
        for k, v in (pii_counts or {}).items():
            total_pii[k] = total_pii.get(k, 0) + v
    if total_flagged:
        logger.warning(
            f"[render_scenes] {job_id} — prompt injection neutralized in {len(total_flagged)} "
            f"scene patterns: {total_flagged[:5]}"
        )
    if total_pii:
        logger.info(f"[render_scenes] {job_id} — PII redacted in scenes: {total_pii}")

    # ============================================================
    # FIX SMART MERGE (post-incident "500 + sai logic chia scene"):
    # Nếu N scenes total_duration ≤ model.max_duration_s VÀ model hỗ trợ multi-shot
    # → MERGE thành 1 single video call với multi-shot prompt (@image1, @image2 syntax)
    # → KHÔNG concat → liền mạch 100% (cùng seed, cùng pass model)
    # → Tiết kiệm 50%+ thời gian render (1 call thay vì N parallel)
    #
    # Anh user nói đúng: "Seedance 2 max 15s, user chọn 15s thì 1 video 15s luôn, KHÔNG
    # chia scene cut hard". Pipeline trước em CHIA mặc dù model fit → bug logic.
    # ============================================================
    total_duration = sum(s.get("duration_s", 5) for s in approved_scenes)
    model_supports_multishot = _spec.get("supports_multi_shot", False)
    can_single_call = (
        len(approved_scenes) >= 2
        and total_duration <= _dur_max
        and total_duration >= _dur_min
        and (model_supports_multishot or len(approved_scenes) == 1)
    )

    if can_single_call:
        logger.info(
            f"[render_scenes] {job_id} — SMART MERGE: {len(approved_scenes)} scenes → "
            f"1 single video call ({total_duration}s, model supports_multi_shot=True)"
        )
        return await _render_single_merged(
            job_id=job_id,
            approved_scenes=approved_scenes,
            reference_images=reference_images,
            atlas_key=atlas_key,
            aspect=aspect,
            resolution=resolution,
            total_duration=total_duration,
            negative_prompt=scenes_negative_prompt,
            work_dir=work_dir,
            jobs_store=jobs_store,
        )

    # ============================================================
    # PHASE 5: EXTEND CHAIN — khi total_duration > model.max_duration_s
    # Pattern: chunk 1 với return_last_frame=True → chunks 2+ i2v với last_image chain
    # → FFmpeg concat. Giữ liền mạch identity + motion smooth qua frame transition.
    # ============================================================
    if total_duration > _dur_max and _spec.get("audio_capability") in ("native", "driven"):
        # Pick i2v model key cho chunks tiếp theo (chain qua last_image)
        i2v_key = USER_MODEL_TO_ATLAS_I2V_KEY.get(user_model)
        if i2v_key and model_supports_multishot:
            logger.info(
                f"[render_scenes] {job_id} — EXTEND CHAIN: total={total_duration}s > "
                f"max={_dur_max}s → chunk + last_image chain. i2v_key={i2v_key}"
            )
            return await _render_extended_chain(
                job_id=job_id,
                approved_scenes=approved_scenes,
                reference_images=reference_images,
                base_atlas_key=atlas_key,
                i2v_atlas_key=i2v_key,
                aspect=aspect,
                resolution=resolution,
                max_chunk_duration=_dur_max,
                negative_prompt=scenes_negative_prompt,
                work_dir=work_dir,
                jobs_store=jobs_store,
            )

    _update_job(jobs_store, job_id, status="rendering", progress=15, current_step="scene_queue")

    sem = asyncio.Semaphore(3)  # parallel cap — tránh AtlasCloud 429
    last_prediction_id: Optional[str] = None
    PER_SCENE_TIMEOUT_S = 180  # FIX #2: per-scene deadline (giữa min vs max của model)

    async def _render_one_scene(scene: dict, idx: int) -> Path:
        nonlocal last_prediction_id
        async with sem:
            scene_id = scene.get("scene_id", f"S{idx + 1}")
            prompt = (scene.get("prompt") or "").strip()
            if not prompt:
                raise ValueError(f"Scene {scene_id} empty prompt — không thể render")

            # V3.2 — clamp duration vào RANGE CỦA SPEC model (KHÔNG generic [2,20])
            # Vidu Q3 min=3, Seedance 2.0 min=4, Wan 2.7 min=2 — phải tôn trọng spec
            user_dur = int(scene.get("duration_s", 5))
            duration = int(min(max(user_dur, _dur_min), _dur_max))
            if duration != user_dur:
                logger.warning(
                    f"[render_scenes] {scene_id} duration {user_dur}s clamped to {duration}s "
                    f"(spec range {_dur_min}-{_dur_max}s for {atlas_key})"
                )
            image_refs_1based = scene.get("image_refs") or []
            # Resolve [Image N] indices → actual reference image URLs
            scene_refs = [
                reference_images[i - 1]
                for i in image_refs_1based
                if isinstance(i, int) and 0 < i <= len(reference_images)
            ]

            # V3.3 — Auto-fallback: nếu user upload refs nhưng scene chưa tag [Image N]
            # → dùng TẤT CẢ reference_images (clamp vào max_references của spec).
            # Tránh atlas reject "min 1 images (nhận 0)" khi user upload mà không tag.
            if not scene_refs and reference_images:
                _max_refs_spec = _spec.get("max_references", 4)
                scene_refs = reference_images[:_max_refs_spec]
                logger.info(
                    f"[render_scenes] {scene_id} auto-fallback: scene chưa tag [Image N] → "
                    f"dùng {len(scene_refs)} refs từ uploads (max {_max_refs_spec} per spec)"
                )

            # Cuối cùng nếu vẫn 0 refs + spec yêu cầu min_refs → raise rõ ràng
            _min_refs_spec = _spec.get("min_references", 0)
            if _min_refs_spec > 0 and len(scene_refs) < _min_refs_spec:
                raise ValueError(
                    f"Scene {scene_id} cần {_min_refs_spec} refs nhưng KHÔNG có ảnh upload. "
                    f"Upload ảnh trước hoặc đổi model t2v."
                )

            logger.info(
                f"[render_scenes] {scene_id} → {atlas_key}, dur={duration}s, "
                f"refs={len(scene_refs)}, prompt_len={len(prompt)}"
            )

            # FIX #4: retry helper với 3× exponential backoff (2s/4s/8s)
            # AtlasCloud có thể trả 429 (rate limit) hoặc transient 5xx — không nên fail hard.
            result = await _call_atlas_with_retry(
                fn=atlas_video.generate_video,
                kwargs={
                    "model_key": atlas_key,
                    "prompt": prompt,
                    "negative_prompt": scenes_negative_prompt,  # V3.1 anti-artifact
                    "images": scene_refs if scene_refs else None,
                    "duration_s": duration,
                    "resolution": resolution,
                    "aspect_ratio": aspect,
                    "poll_interval_s": 5,
                    "timeout_s": 600,
                },
                scope=f"render_scenes:{scene_id}",
                max_attempts=3,
            )

            clip_url = result.get("video_url")
            last_prediction_id = result.get("prediction_id") or last_prediction_id
            if not clip_url:
                raise RuntimeError(f"AtlasCloud không trả video_url cho {scene_id}")

            clip_path = work_dir / f"scene_{idx + 1:02d}_{scene_id}.mp4"
            await _download_file(clip_url, clip_path, expected_content_prefix="video/")
            logger.info(
                f"[render_scenes] {scene_id} downloaded {clip_path.stat().st_size / 1024:.0f}KB"
            )
            return clip_path

    try:
        # FIX #2: Wrap mỗi scene với asyncio.wait_for timeout + return_exceptions
        # 1 scene timeout/fail KHÔNG kill toàn job — concat scenes thành công, mark scene fail rõ ràng.
        async def _render_with_timeout(scene: dict, idx: int) -> Any:
            try:
                return await asyncio.wait_for(
                    _render_one_scene(scene, idx),
                    timeout=PER_SCENE_TIMEOUT_S,
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"[render_scenes] {scene.get('scene_id', f'S{idx+1}')} "
                    f"PER_SCENE_TIMEOUT after {PER_SCENE_TIMEOUT_S}s — skip"
                )
                return TimeoutError(f"scene_timeout_{PER_SCENE_TIMEOUT_S}s")

        results = await asyncio.gather(
            *[_render_with_timeout(s, i) for i, s in enumerate(approved_scenes)],
            return_exceptions=True,
        )

        # Tách success / fail
        clip_paths: list[Path] = []
        failed_scenes: list[tuple[int, str, str]] = []  # (idx, scene_id, error)
        for i, r in enumerate(results):
            scene_id = approved_scenes[i].get("scene_id", f"S{i+1}")
            if isinstance(r, Path):
                clip_paths.append(r)
            elif isinstance(r, BaseException):
                err_msg = str(r)[:200]
                failed_scenes.append((i, scene_id, err_msg))
                logger.warning(f"[render_scenes] {scene_id} FAILED: {err_msg}")

        if not clip_paths:
            # KHÔNG có scene nào thành công → fail toàn job
            raise RuntimeError(
                f"All {len(approved_scenes)} scenes failed. "
                f"First error: {failed_scenes[0][2] if failed_scenes else 'unknown'}"
            )

        if failed_scenes:
            logger.warning(
                f"[render_scenes] PARTIAL SUCCESS: {len(clip_paths)}/{len(approved_scenes)} "
                f"scenes rendered. Failed: {[(s[1], s[2][:60]) for s in failed_scenes]}"
            )
            # Expose failed scenes vào job store cho frontend hiển thị
            _update_job(
                jobs_store, job_id,
                partial_failed_scenes=[
                    {"scene_id": s[1], "error": s[2]} for s in failed_scenes
                ],
            )

        if last_prediction_id:
            _update_job(jobs_store, job_id, atlas_prediction_id=last_prediction_id)

        _update_job(
            jobs_store, job_id,
            status="assembling", progress=80, current_step="ffmpeg_concat",
        )

        # V3.5 — FFmpeg crossfade (Higgsfield-style smooth transition) khi N ≥ 2 clips
        # Cũ: hard concat (cut-on-cut) — cảnh chuyển CỨNG, thiếu chuyên nghiệp
        # Mới: 0.4s crossfade giữa clips → seamless multi-shot story
        final_mp4 = work_dir / "final.mp4"
        if len(clip_paths) >= 2:
            try:
                await asyncio.to_thread(
                    _ffmpeg_concat_with_crossfade,
                    clip_paths, final_mp4,
                    crossfade_s=0.4,
                    audio_crossfade=True,
                )
                logger.info(
                    f"[render_scenes] FFmpeg CROSSFADE concat done: {len(clip_paths)} clips → "
                    f"{final_mp4.stat().st_size / 1024:.0f}KB"
                )
            except Exception as e:
                logger.warning(
                    f"[render_scenes] crossfade fail ({e}) — fallback hard concat"
                )
                await asyncio.to_thread(_ffmpeg_concat_clips, clip_paths, final_mp4)
        else:
            # 1 clip — không cần concat, copy thẳng
            import shutil as _sh
            _sh.copy2(str(clip_paths[0]), str(final_mp4))
            logger.info(f"[render_scenes] single clip → {final_mp4.stat().st_size / 1024:.0f}KB")

        _update_job(
            jobs_store, job_id,
            status="uploading", progress=95, current_step="r2_upload",
        )
        output_url = await _stage_upload_r2(final_mp4, job_id)

        total_duration = sum(s.get("duration_s", 5) for s in approved_scenes)
        _update_job(
            jobs_store, job_id,
            status="done", progress=100, current_step="done",
            output_url=output_url, duration_s=total_duration,
        )

        logger.info(f"[RenderPipeline] SCENES Job {job_id} DONE → {output_url}")
        return {
            "output_url": output_url,
            "job_id": job_id,
            "scene_count": len(approved_scenes),
            "total_duration_s": total_duration,
        }
    except Exception as e:
        current_job = jobs_store.get(job_id) if hasattr(jobs_store, "get") else None
        retry_count = (current_job or {}).get("retry_count", 0) if current_job else 0
        logger.exception(f"[RenderPipeline] SCENES Job {job_id} FAILED: {e}")
        _update_job(
            jobs_store, job_id,
            status="failed",
            error_message=str(e)[:500],
            retry_count=retry_count + 1,
            failed_at_stage=(current_job or {}).get("current_step") if current_job else None,
        )
        raise
    finally:
        if not os.getenv("KEEP_RENDER_WORKDIR"):
            try:
                import shutil
                shutil.rmtree(work_dir, ignore_errors=True)
            except OSError:
                pass


def _probe_clip(clip_path: Path) -> dict:
    """FIX #6: ffprobe MP4 clip → trả codec/fps/resolution/duration cho pre-check.

    Returns:
        dict {"video_codec", "width", "height", "fps", "duration_s", "audio_codec"}.
        None values khi field missing.

    Raises:
        RuntimeError nếu ffprobe fail hoặc file not video.
    """
    import json as _json
    import subprocess

    if not clip_path.exists() or clip_path.stat().st_size < 1024:
        raise RuntimeError(f"[_probe_clip] file missing or too small: {clip_path}")

    cmd = [
        "ffprobe", "-v", "error",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        str(clip_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        raise RuntimeError(f"[_probe_clip] ffprobe unavailable or hung: {e}") from e

    if proc.returncode != 0:
        raise RuntimeError(
            f"[_probe_clip] ffprobe rc={proc.returncode}: {proc.stderr[:200]}"
        )

    try:
        data = _json.loads(proc.stdout)
    except _json.JSONDecodeError as e:
        raise RuntimeError(f"[_probe_clip] ffprobe JSON parse fail: {e}") from e

    streams = data.get("streams") or []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not video_stream:
        raise RuntimeError(f"[_probe_clip] no video stream in {clip_path.name}")

    # FPS — avg_frame_rate là "N/D" fraction → eval
    fps_raw = video_stream.get("avg_frame_rate", "0/0")
    try:
        num, den = fps_raw.split("/")
        fps = round(int(num) / int(den), 2) if int(den) > 0 else 0
    except (ValueError, ZeroDivisionError):
        fps = 0

    duration_s: Optional[float] = None
    fmt_dur = (data.get("format") or {}).get("duration")
    if fmt_dur:
        try:
            duration_s = round(float(fmt_dur), 2)
        except ValueError:
            pass

    return {
        "video_codec": video_stream.get("codec_name"),
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "fps": fps,
        "pix_fmt": video_stream.get("pix_fmt"),
        "duration_s": duration_s,
        "audio_codec": (audio_stream or {}).get("codec_name") if audio_stream else None,
    }


def _validate_clips_homogeneity(clip_paths: list[Path]) -> tuple[bool, str, list[dict]]:
    """FIX #6: Pre-check N clips đồng nhất codec/resolution/fps trước concat.

    Returns:
        (is_homogeneous, reason, probes) — reason="" nếu homogeneous.
    """
    if not clip_paths:
        return False, "no clips", []
    probes = [_probe_clip(p) for p in clip_paths]
    first = probes[0]
    keys_to_match = ["video_codec", "width", "height", "pix_fmt"]

    mismatches: list[str] = []
    for i, pr in enumerate(probes[1:], start=1):
        for k in keys_to_match:
            if pr.get(k) != first.get(k):
                mismatches.append(
                    f"clip[{i}].{k}={pr.get(k)} ≠ clip[0].{k}={first.get(k)}"
                )
    # FPS với tolerance ±0.5 (29.97 vs 30 OK)
    base_fps = first.get("fps") or 0
    for i, pr in enumerate(probes[1:], start=1):
        cur_fps = pr.get("fps") or 0
        if base_fps > 0 and abs(cur_fps - base_fps) > 0.5:
            mismatches.append(f"clip[{i}].fps={cur_fps} ≠ clip[0].fps={base_fps} (>0.5 tol)")

    if mismatches:
        return False, "; ".join(mismatches[:5]), probes  # cap 5 reasons
    return True, "", probes


def _ffmpeg_concat_with_crossfade(
    clip_paths: list[Path],
    output: Path,
    crossfade_s: float = 0.5,
    audio_crossfade: bool = True,
) -> None:
    """V3.5 — Smooth crossfade transition giữa N clips (Higgsfield/Topview style).

    Khác `_ffmpeg_concat_clips` (cut-on-cut HARD) — function này dùng `xfade` filter
    chain → fade trắng/dim 0.3-0.5s giữa clips → cảnh chuyển MƯỢT MÀ chuyên nghiệp.

    Chỉ dùng khi:
        - N clips ≥ 2 (1 clip không cần xfade)
        - Mọi clip duration ≥ 1s (xfade cần đủ frame để fade)
        - User chấp nhận re-encode (xfade KHÔNG support stream copy)

    Args:
        clip_paths: list MP4 paths theo thứ tự
        output: final MP4 path
        crossfade_s: thời lượng fade transition (0.3-1.0s sweet spot)
        audio_crossfade: nếu True, audio cũng crossfade (acrossfade filter)
    """
    import subprocess

    if len(clip_paths) < 2:
        raise ValueError("[crossfade] cần ít nhất 2 clips để fade transition")

    # Probe duration mỗi clip để tính offset cho xfade chain
    durations: list[float] = []
    for cp in clip_paths:
        try:
            probe = _probe_clip(cp)
            durations.append(probe.get("duration_s") or 0.0)
        except Exception as e:
            logger.warning(f"[crossfade] probe fail {cp.name}: {e} — fallback 5s")
            durations.append(5.0)

    # Build -i inputs
    cmd: list[str] = ["ffmpeg", "-y"]
    for cp in clip_paths:
        cmd += ["-i", str(cp.resolve())]

    # Build xfade filter chain
    # Pattern N=3: [0][1]xfade=duration=0.5:offset=(d0-0.5)[v01]
    #              [v01][2]xfade=duration=0.5:offset=(d0+d1-2*0.5)[v012]
    filter_parts: list[str] = []
    cumulative_offset = 0.0
    current_label = "[0:v]"
    for i in range(1, len(clip_paths)):
        prev_dur = durations[i - 1]
        # offset = cumulative duration so far - crossfade duration (vì xfade overlaps)
        cumulative_offset += prev_dur - crossfade_s
        next_label = f"[v{i:02d}]"
        filter_parts.append(
            f"{current_label}[{i}:v]xfade=transition=fade:duration={crossfade_s}:"
            f"offset={cumulative_offset:.2f}{next_label}"
        )
        current_label = next_label

    # Audio crossfade (acrossfade chain) — optional
    if audio_crossfade:
        audio_current = "[0:a]"
        for i in range(1, len(clip_paths)):
            audio_next = f"[a{i:02d}]"
            filter_parts.append(
                f"{audio_current}[{i}:a]acrossfade=d={crossfade_s}{audio_next}"
            )
            audio_current = audio_next
        filter_complex = ";".join(filter_parts)
        map_args = ["-map", current_label, "-map", audio_current]
    else:
        filter_complex = ";".join(filter_parts)
        map_args = ["-map", current_label]

    cmd += [
        "-filter_complex", filter_complex,
        *map_args,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output),
    ]

    if not audio_crossfade:
        # Audio passthrough nếu KHÔNG crossfade audio (lấy audio clip đầu)
        cmd.insert(-1, "-c:a")
        cmd.insert(-1, "aac")

    logger.info(
        f"[crossfade] N={len(clip_paths)} clips, fade={crossfade_s}s, "
        f"audio_xfade={audio_crossfade}, total_dur≈{sum(durations) - crossfade_s*(len(clip_paths)-1):.1f}s"
    )

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=False)
    except subprocess.TimeoutExpired:
        raise RuntimeError("FFmpeg crossfade timeout 600s")

    if proc.returncode != 0:
        # Crossfade fail → fallback hard concat
        logger.warning(
            f"[crossfade] FAIL rc={proc.returncode}, stderr: {proc.stderr[:300]} — "
            f"fallback hard concat"
        )
        _ffmpeg_concat_clips(clip_paths, output)
        return

    if not output.exists() or output.stat().st_size < 1024:
        raise RuntimeError(f"[crossfade] output invalid: {output}")

    logger.info(f"[crossfade] done → {output.stat().st_size / 1024:.0f}KB")


def _ffmpeg_concat_clips(clip_paths: list[Path], output: Path) -> None:
    """Concat N MP4 clips theo thứ tự → 1 MP4 dùng FFmpeg concat demuxer.

    Demuxer pattern: tạo concat.txt list file paths → ffmpeg -f concat -safe 0
    -i concat.txt -c copy output.mp4 (stream copy, không re-encode → nhanh).

    FIX #6 (HIGH): ffprobe TẤT CẢ clips trước → kiểm tra codec/resolution/fps đồng nhất.
        - Đồng nhất → stream copy nhanh (-c copy), ~1s cho 8 clips
        - Mismatch → fail-fast re-encode với reason rõ ràng (lưu probes vào log/exception)
        - Không còn silent fallback ẩn lý do
    """
    import subprocess

    if not clip_paths:
        raise ValueError("[ffmpeg_concat] no clips to concat")

    # FIX #6: Pre-check codec/fps/resolution homogeneity
    try:
        homogeneous, reason, probes = _validate_clips_homogeneity(clip_paths)
    except RuntimeError as e:
        # ffprobe fail → fallback bypass pre-check (best effort concat)
        logger.warning(f"[ffmpeg_concat] ffprobe pre-check unavailable: {e}. Skip pre-check.")
        homogeneous, reason, probes = True, "", []

    if probes:
        # Log summary first probe + count of unique signatures
        unique_sigs = {
            (p.get("video_codec"), p.get("width"), p.get("height"), p.get("fps"))
            for p in probes
        }
        logger.info(
            f"[ffmpeg_concat] probed {len(probes)} clips → "
            f"{len(unique_sigs)} unique codec/dim/fps signature(s). "
            f"First: {probes[0].get('video_codec')} "
            f"{probes[0].get('width')}x{probes[0].get('height')} @ {probes[0].get('fps')}fps"
        )

    concat_list = output.parent / f"concat_{output.stem}.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for p in clip_paths:
            abs_path = str(p.resolve()).replace("'", "'\\''")
            f.write(f"file '{abs_path}'\n")

    if homogeneous:
        # Path A: Stream copy (fast, lossless)
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            "-movflags", "+faststart",
            str(output),
        ]
        logger.debug(f"[ffmpeg_concat] stream copy cmd: {' '.join(cmd)}")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
        except subprocess.TimeoutExpired:
            raise RuntimeError("FFmpeg stream-copy concat timeout 300s")

        if proc.returncode == 0:
            if output.exists() and output.stat().st_size >= 1024:
                return
            # Output file ko hợp lệ → fallthrough re-encode
            logger.warning(
                f"[ffmpeg_concat] stream copy rc=0 nhưng output invalid "
                f"({output.stat().st_size if output.exists() else 'missing'}B) — re-encode"
            )
        else:
            logger.warning(
                f"[ffmpeg_concat] stream copy rc={proc.returncode} dù homogeneity check OK. "
                f"stderr: {proc.stderr[:200]}. Re-encode..."
            )
    else:
        logger.warning(
            f"[ffmpeg_concat] CODEC/DIM MISMATCH: {reason}. "
            f"Skip stream copy → re-encode trực tiếp."
        )

    # Path B: Re-encode (slower but tolerant codec mismatch)
    cmd_reencode = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",  # explicit cho compatibility
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(output),
    ]
    try:
        proc = subprocess.run(
            cmd_reencode, capture_output=True, text=True, timeout=600, check=False,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("FFmpeg re-encode concat timeout 600s")

    if proc.returncode != 0:
        raise RuntimeError(
            f"FFmpeg concat re-encode FAIL (rc={proc.returncode}). "
            f"Homogeneity check: {'PASS' if homogeneous else f'FAIL ({reason})'}. "
            f"stderr: {proc.stderr[:500]}"
        )

    if not output.exists() or output.stat().st_size < 1024:
        raise RuntimeError(f"FFmpeg concat output too small or missing: {output}")


async def render_auto(job_id: str, request: dict, jobs_store: dict) -> dict:
    """⚠️ DEPRECATED — V3 era yêu cầu mọi job đi qua /propose trước.

    Path này (no approved_script) đã được loại bỏ. Frontend luôn /propose → /jobs/ugc.
    Nếu vẫn rơi vào đây → frontend cũ hoặc gọi API trực tiếp sai pattern.
    """
    _update_job(
        jobs_store, job_id,
        status="failed",
        error_message=(
            "render_auto path đã deprecated (V3). Phải /propose trước rồi mới /jobs/ugc "
            "với approved_script + approved_shots + approved_character_sheet."
        ),
    )
    raise RuntimeError(
        "render_auto deprecated — gọi /api/v1/jobs/propose trước khi /jobs/ugc"
    )


# ============================================
# Shared render chain (Stage 3 onwards)
# ============================================

async def _run_render_chain(
    job_id: str,
    gen_result: dict,
    settings: dict,
    reference_images: list[str],
    jobs_store: Any,
    approved_keyframes: Optional[list[dict]] = None,
) -> dict:
    """Stages 3-8: (TTS first nếu audio-driven) → video gen → SFX → compose → upload.

    BUG-B1 fix: Wan 2.7 là audio-driven model — TTS PHẢI chạy TRƯỚC video gen
    để pass voice MP3 URL làm `audio_url` cho lipsync. Các model khác giữ flow cũ.
    """

    work_dir = Path(tempfile.gettempdir()) / f"render_{job_id[:8]}"
    work_dir.mkdir(parents=True, exist_ok=True)

    audio_driven_models = {"wan_2_7"}  # add models khác nếu sau này có
    is_audio_driven = settings.get("model") in audio_driven_models

    try:
        voice_path: Optional[Path] = None
        if is_audio_driven:
            # Audio-driven path: TTS first → pass audio URL cho video gen
            _update_job(jobs_store, job_id, status="voicing", progress=25,
                        current_step="tts_pre_video")
            voice_path = await _stage_tts(gen_result, settings, work_dir)

        # Stage 3: Video gen qua AtlasCloud (track prediction_id cho cancel)
        _update_job(jobs_store, job_id, status="rendering", progress=40,
                    current_step="video_gen")
        video_paths, atlas_pred_id = await _stage_video_gen(
            gen_result=gen_result,
            reference_images=reference_images,
            settings=settings,
            work_dir=work_dir,
            voice_path=voice_path,  # ← pass voice cho audio-driven
            approved_keyframes=approved_keyframes or [],  # Phase 2.5 i2v path
        )
        if atlas_pred_id:
            _update_job(jobs_store, job_id, atlas_prediction_id=atlas_pred_id)

        # Stage 4 + 5: TTS + (optional) SFX — parallel
        # Nếu audio-driven (Wan 2.7), TTS đã chạy trước video gen → skip TTS, chạy SFX.
        _update_job(jobs_store, job_id, status="voicing", progress=65,
                    current_step="tts_sfx")
        if is_audio_driven:
            sfx_path = await _stage_sfx(gen_result, settings, work_dir)
            # voice_path đã có từ pre-video TTS
        else:
            voice_path, sfx_path = await asyncio.gather(
                _stage_tts(gen_result, settings, work_dir),
                _stage_sfx(gen_result, settings, work_dir),
            )

        # Stage 6: FFmpeg compose
        _update_job(jobs_store, job_id, status="assembling", progress=80,
                    current_step="ffmpeg")
        final_mp4 = await _stage_compose(
            video_paths=video_paths,
            voice_path=voice_path,
            sfx_path=sfx_path,
            gen_result=gen_result,
            settings=settings,
            work_dir=work_dir,
        )

        # Stage 7: R2 upload
        _update_job(jobs_store, job_id, status="uploading", progress=95,
                    current_step="r2_upload")
        output_url = await _stage_upload_r2(final_mp4, job_id)

        # Stage 8: Done
        _update_job(
            jobs_store, job_id,
            status="done", progress=100,
            current_step="done",
            output_url=output_url,
            duration_s=settings.get("duration_s"),
        )

        logger.info(f"[RenderPipeline] Job {job_id} DONE → {output_url}")
        return {"output_url": output_url, "job_id": job_id}

    except Exception as e:
        # BUG-H2 fix: lightweight retry tracking trong JOBS store
        # Production-grade retry (Dramatiq) sẽ ship sau khi Redis setup.
        # Hiện tại log retry_count để admin biết job đã retry mấy lần.
        current_job = jobs_store.get(job_id) if hasattr(jobs_store, "get") else None
        retry_count = (current_job or {}).get("retry_count", 0) if current_job else 0
        logger.exception(
            f"[RenderPipeline] Job {job_id} FAILED (retry_count={retry_count}): {e}"
        )
        _update_job(
            jobs_store, job_id,
            status="failed",
            error_message=str(e)[:500],
            retry_count=retry_count + 1,
            failed_at_stage=(current_job or {}).get("current_step") if current_job else None,
        )
        raise
    finally:
        # Cleanup work dir (keep nếu DEBUG=true)
        if not os.getenv("KEEP_RENDER_WORKDIR"):
            try:
                import shutil
                shutil.rmtree(work_dir, ignore_errors=True)
            except OSError:
                pass


# ============================================
# Stage implementations
# ============================================

async def _stage_video_gen(
    gen_result: dict,
    reference_images: list[str],
    settings: dict,
    work_dir: Path,
    voice_path: Optional[Path] = None,  # ← BUG-B1: audio-driven model dùng voice URL
    approved_keyframes: Optional[list[dict]] = None,  # Phase 2.5: i2v multi-keyframe path
) -> tuple[list[Path], Optional[str]]:
    """Call AtlasCloud video gen với prompt từ Generator → download MP4 local.

    2 paths:
        A. LEGACY (no keyframes): 1 video clip dài duration_s, dùng ref-to-video / i2v
           với reference_images user upload.
        B. NEW (approved_keyframes): N clips ngắn (3-5s) — mỗi keyframe → 1 clip i2v
           anim từ ảnh đã duyệt Phase 2.5. Concat sau bằng FFmpeg. Identity 100%.

    Returns:
        (video_paths, prediction_id) — list path MP4 + id cuối cùng cho cancel propagation.
    """
    user_model = settings.get("model", "vidu_q3")
    duration = settings.get("duration_s", 15)
    aspect = settings.get("aspect_ratio", "9:16")
    resolution = settings.get("resolution", "720p")

    if atlas_video is None:
        raise RuntimeError("AtlasCloud client chưa init — ATLASCLOUD_API_KEY missing?")

    # V3.2 — clamp settings.duration_s vào per-spec range (PATH A)
    # Tránh: user pick Wan 2.7 (max 8s) + duration 15s → atlas reject
    from agent.model_specs import get_spec, VIDEO_MODEL_SPECS
    _atlas_key_for_duration = USER_MODEL_TO_ATLAS_KEY.get(user_model, "vidu_q3_ref")
    _spec_a = VIDEO_MODEL_SPECS.get(_atlas_key_for_duration, {})
    _dur_min_a = _spec_a.get("duration", {}).get("min", 2)
    _dur_max_a = _spec_a.get("duration", {}).get("max", 60)
    _clamped_dur = min(max(int(duration), _dur_min_a), _dur_max_a)
    if _clamped_dur != int(duration):
        logger.warning(
            f"[render._stage_video_gen] PATH A duration {duration}s clamped to {_clamped_dur}s "
            f"(spec range {_dur_min_a}-{_dur_max_a}s for {_atlas_key_for_duration})"
        )
        duration = _clamped_dur

    # ========================================
    # PATH B — Phase 2.5 i2v multi-keyframe (preferred khi có approved_keyframes)
    # ========================================
    valid_keyframes = [
        kf for kf in (approved_keyframes or [])
        if isinstance(kf, dict) and kf.get("image_url") and kf.get("status") == "completed"
    ]

    if valid_keyframes:
        logger.info(
            f"[render._stage_video_gen] PATH B (i2v multi-keyframe): "
            f"{len(valid_keyframes)} keyframes, user_model={user_model}"
        )
        # V3 — pass character_sheet để inject identity descr vào per-keyframe prompt
        # (gen_result._strategy_payload chứa character đã inject sẵn, nhưng PATH B
        # per-keyframe nên cần character_sheet riêng để rewrite per-shot prompt)
        char_sheet_descr: Optional[str] = None
        if gen_result.get("_strategy_user_model"):
            # V3 path active — extract character descr từ gen_result metadata
            try:
                strat_payload = gen_result.get("_strategy_payload", {}) or {}
                prompt_full_str = strat_payload.get("prompt", "")
                # prompt_full đã có character descr (do strategy inject). Tách lấy snippet đầu.
                if prompt_full_str:
                    # Take first 200 chars as character ref hint
                    char_sheet_descr = prompt_full_str[:200]
            except Exception:
                pass
        return await _render_i2v_per_keyframe(
            keyframes=valid_keyframes,
            user_model=user_model,
            aspect=aspect,
            resolution=resolution,
            work_dir=work_dir,
            character_descr_hint=char_sheet_descr,
        )

    # ========================================
    # PATH A — LEGACY (no keyframes): ref-to-video / i2v with user-uploaded refs
    # ========================================
    atlas_model_key = USER_MODEL_TO_ATLAS_KEY.get(user_model, "vidu_q3_ref")
    prompt_full = gen_result.get("prompt_full") or gen_result.get("prompt") or ""
    if not prompt_full:
        raise ValueError("Generator không trả prompt_full")

    logger.info(
        f"[render._stage_video_gen] PATH A (legacy ref-to-video): "
        f"atlas_model={atlas_model_key} (user chose {user_model}), "
        f"duration={duration}s, prompt_len={len(prompt_full)}, refs={len(reference_images)}"
    )

    # BUG-B1: Upload voice mp3 lên AtlasCloud trước → có URL pass `audio_url` cho audio-driven
    audio_url: Optional[str] = None
    if voice_path and voice_path.exists() and atlas_video:
        try:
            audio_url = await asyncio.to_thread(atlas_video.upload_media, str(voice_path))
            logger.info(f"[render._stage_video_gen] uploaded voice → AtlasCloud {audio_url[:80]}")
        except Exception as e:
            logger.warning(
                f"[render._stage_video_gen] voice upload fail: {e} — video sẽ silent"
            )

    # Submit + poll AtlasCloud video gen (sync API wrapped in thread)
    # BUG-M4: soft timeout 5min warning, hard timeout 10min
    import time as _time
    start_ts = _time.monotonic()
    # BUG-V3.1: pass negative_prompt từ V3 strategy (anti-artifact bake-in industry-tested)
    negative_prompt = (gen_result.get("_strategy_payload") or {}).get("negative_prompt")
    try:
        result = await asyncio.to_thread(
            atlas_video.generate_video,
            model_key=atlas_model_key,
            prompt=prompt_full,
            negative_prompt=negative_prompt,  # ← V3.1 anti-artifact
            images=reference_images if reference_images else None,
            duration_s=duration,
            resolution=resolution,
            aspect_ratio=aspect,
            audio_url=audio_url,  # ← BUG-B1: audio-driven Wan 2.7 lipsync
            poll_interval_s=5,
            timeout_s=600,
        )
    except TimeoutError as e:
        elapsed = _time.monotonic() - start_ts
        logger.error(
            f"[render._stage_video_gen] AtlasCloud HARD timeout after {elapsed:.0f}s: {e}"
        )
        raise RuntimeError(
            f"AtlasCloud video gen quá thời gian ({elapsed:.0f}s) — thường do model overload. "
            f"Anh thử model khác (seedance_2_0_fast nhanh hơn) hoặc duration ngắn hơn."
        ) from e
    except Exception as e:
        logger.exception(f"[render._stage_video_gen] AtlasCloud fail: {e}")
        raise

    elapsed = _time.monotonic() - start_ts
    if elapsed > 300:
        logger.warning(
            f"[render._stage_video_gen] SLOW render — {elapsed:.0f}s (> 5min soft limit). "
            f"Consider switching to faster model."
        )

    video_url = result.get("video_url")
    prediction_id = result.get("prediction_id")
    if not video_url:
        raise RuntimeError(f"AtlasCloud không trả video_url. Result: {result}")

    # Download MP4 về local (validate Content-Type — BUG-M2 fix)
    local_path = work_dir / "video_clip_01.mp4"
    await _download_file(video_url, local_path, expected_content_prefix="video/")
    logger.info(
        f"[render._stage_video_gen] downloaded {local_path.stat().st_size / 1024:.0f}KB "
        f"từ {video_url[:80]}..."
    )
    return [local_path], prediction_id


# ============================================
# PATH B — i2v multi-keyframe (Phase 2.5)
# ============================================

async def _render_i2v_per_keyframe(
    keyframes: list[dict],
    user_model: str,
    aspect: str,
    resolution: str,
    work_dir: Path,
    character_descr_hint: Optional[str] = None,
) -> tuple[list[Path], Optional[str]]:
    """Render N video clips ngắn, mỗi clip animate 1 keyframe (i2v).

    Trả list MP4 paths (assemble_worker sẽ concat sau).

    Lưu ý: dùng MỘT model i2v duy nhất cho tất cả keyframes (user yêu cầu KHÔNG mix model).

    Args:
        character_descr_hint: V3 — character descr inject vào mỗi prompt để
            giữ identity consistency xuyên keyframes (Higgsfield Soul.0 pattern).
    """
    i2v_model_key = USER_MODEL_TO_ATLAS_I2V_KEY.get(user_model, "wan_2_7_i2v")
    logger.info(
        f"[render._render_i2v] {len(keyframes)} keyframes via {i2v_model_key} "
        f"(user chose {user_model})"
    )

    from agent.model_specs import get_spec
    spec = get_spec(i2v_model_key)
    # Pick duration trong range cho mỗi clip — ưu tiên duration_s từ keyframe, clamp vào range model
    dur_min = spec.get("duration", {}).get("min", 4)
    dur_max = spec.get("duration", {}).get("max", 8)

    # V3.1 — derive negative_prompt từ strategy của user_model (anti-artifact bake-in)
    try:
        from agent.strategies import get_strategy_for_model
        i2v_negative_prompt = get_strategy_for_model(user_model).negative_prompt()
    except Exception:
        i2v_negative_prompt = None

    last_prediction_id: Optional[str] = None
    video_paths: list[Path] = []

    # Sequential render — KHÔNG parallel để tránh rate limit + cost spike khi 1 clip fail
    for idx, kf in enumerate(keyframes):
        shot_id = kf.get("shot_id", f"S{idx+1}")
        image_url = kf["image_url"]
        # Per-shot prompt: dùng dialogue + action nếu có, fallback subject
        prompt_parts = []
        # V3 — inject character descr ở đầu prompt để giữ identity (Higgsfield Soul.0)
        if character_descr_hint:
            prompt_parts.append(character_descr_hint)
        if kf.get("dialogue_vn"):
            prompt_parts.append(kf["dialogue_vn"])
        if kf.get("caption_on_screen"):
            prompt_parts.append(kf["caption_on_screen"])
        if not prompt_parts:
            prompt_parts.append(kf.get("purpose", "natural motion"))
        shot_prompt = ". ".join(prompt_parts)

        # Clamp clip duration vào model range
        clip_dur = int(min(max(kf.get("duration_s", 4), dur_min), dur_max))

        logger.info(
            f"[render._render_i2v] {shot_id} → {i2v_model_key} dur={clip_dur}s "
            f"prompt='{shot_prompt[:60]}'"
        )

        try:
            result = await asyncio.to_thread(
                atlas_video.generate_video,
                model_key=i2v_model_key,
                prompt=shot_prompt,
                negative_prompt=i2v_negative_prompt,  # V3.1 anti-artifact
                image=image_url,  # ← i2v dùng `image` singular
                duration_s=clip_dur,
                resolution=resolution,
                aspect_ratio=aspect,
                poll_interval_s=5,
                timeout_s=600,
            )
        except Exception as e:
            logger.exception(f"[render._render_i2v] {shot_id} fail: {e}")
            raise RuntimeError(
                f"i2v render fail shot {shot_id}: {str(e)[:200]}"
            ) from e

        clip_url = result.get("video_url")
        last_prediction_id = result.get("prediction_id") or last_prediction_id
        if not clip_url:
            raise RuntimeError(f"AtlasCloud không trả video_url cho {shot_id}. Result: {result}")

        clip_path = work_dir / f"clip_{idx+1:02d}_{shot_id}.mp4"
        await _download_file(clip_url, clip_path, expected_content_prefix="video/")
        logger.info(
            f"[render._render_i2v] {shot_id} → {clip_path.stat().st_size / 1024:.0f}KB"
        )
        video_paths.append(clip_path)

    logger.info(
        f"[render._render_i2v] DONE: {len(video_paths)}/{len(keyframes)} clips rendered"
    )
    return video_paths, last_prediction_id


async def _download_file(
    url: str,
    dest: Path,
    expected_content_prefix: Optional[str] = None,
):
    """Stream download URL → local file.

    BUG-M2 fix: validate Content-Type để KHÔNG download HTML error page như "MP4".
    """
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            ctype = response.headers.get("content-type", "").lower()
            if expected_content_prefix and not ctype.startswith(expected_content_prefix):
                raise RuntimeError(
                    f"Content-Type '{ctype}' không match expected '{expected_content_prefix}*' "
                    f"từ {url[:80]} — likely HTML error page"
                )
            with open(dest, "wb") as f:
                async for chunk in response.aiter_bytes(64 * 1024):
                    f.write(chunk)


async def _stage_tts(gen_result: dict, settings: dict, work_dir: Path) -> Optional[Path]:
    """Generate voice TTS từ approved script (hoặc gen_result voice_script).

    Wire GenMax client → poll history → download MP3.
    """
    audio_mode = settings.get("audio_mode")
    if audio_mode not in ("dialogue_vo",):
        return None

    # Approved path — TTS source preserved trong gen_result
    hook = gen_result.get("_tts_hook_vn", "")
    body = gen_result.get("_tts_body_vn", "")
    cta = gen_result.get("_tts_cta_vn", "")
    full_script = " ".join(filter(None, [hook, body, cta])).strip()

    # Legacy path fallback
    if not full_script:
        full_script = gen_result.get("voice_script", "")

    if not full_script:
        logger.warning("[render._stage_tts] No script text for TTS")
        return None

    if genmax_client is None:
        raise RuntimeError("GenMax client chưa init — GENMAX_API_KEY missing?")

    # BUG-B11 fix: voice fallback theo skill_pack thay vì hardcode "mai".
    # Đọc skill_pack từ gen_result nếu Director Brain pass qua, fallback gender từ niche.
    voice_persona = settings.get("voice_persona")
    if not voice_persona:
        voice_persona = _resolve_default_voice(gen_result, settings)

    # Try preset first
    preset_cfg = VIETNAMESE_VOICE_PRESETS.get(voice_persona)
    if preset_cfg:
        voice_id = preset_cfg["voice_id"]
        provider = preset_cfg["provider"]
    else:
        # voice_persona là raw voice_id — default ElevenLabs
        voice_id = voice_persona
        provider = "elevenlabs"

    logger.info(
        f"[render._stage_tts] GenMax TTS — voice={voice_persona} ({provider}), "
        f"script_len={len(full_script)} chars"
    )

    # Submit TTS job
    try:
        submit_resp = await asyncio.to_thread(
            genmax_client.text_to_speech,
            text=full_script,
            voice_id=voice_id,
            provider=provider,
            language_code="Vietnamese",
        )
    except Exception as e:
        logger.exception(f"[render._stage_tts] GenMax submit fail: {e}")
        raise

    # Extract history_id / audio_url
    audio_url = submit_resp.get("audio_url") or (
        submit_resp.get("result", {}).get("audio_url") if isinstance(submit_resp.get("result"), dict) else None
    )

    if not audio_url:
        # Need to poll history
        history_id = submit_resp.get("history_id") or submit_resp.get("id")
        if not history_id:
            raise RuntimeError(f"GenMax không trả audio_url hoặc history_id: {submit_resp}")

        logger.info(f"[render._stage_tts] polling history {history_id}")
        task = await asyncio.to_thread(
            genmax_client.poll_until_done, history_id, 90, 2.0
        )
        if task.get("status") not in ("completed", "succeeded", "success"):
            raise RuntimeError(f"GenMax TTS failed: {task.get('error', task)}")
        audio_url = (task.get("result") or {}).get("audio_url")

    if not audio_url:
        raise RuntimeError(f"GenMax không có audio_url sau poll: {submit_resp}")

    local_path = work_dir / "voice.mp3"
    await _download_file(audio_url, local_path)
    logger.info(
        f"[render._stage_tts] downloaded voice.mp3 {local_path.stat().st_size / 1024:.0f}KB"
    )
    return local_path


async def _stage_sfx(gen_result: dict, settings: dict, work_dir: Path) -> Optional[Path]:
    """Generate SFX nếu audio_mode=asmr_macro.

    Wire ElevenLabs SFX → save MP3 từng SFX → concat thành 1 track.
    """
    if settings.get("audio_mode") != "asmr_macro":
        return None

    sfx_sequence = gen_result.get("sfx_sequence") or []
    if not sfx_sequence:
        logger.info("[render._stage_sfx] No sfx_sequence in gen_result, skip")
        return None

    if elevenlabs_sfx_client is None:
        logger.warning("[render._stage_sfx] ElevenLabs SFX client unavailable")
        return None

    logger.info(f"[render._stage_sfx] generating {len(sfx_sequence)} SFX clips")

    sfx_dir = work_dir / "sfx"
    sfx_dir.mkdir(exist_ok=True)
    sfx_paths: list[Path] = []

    # Gen từng SFX (sequential — ElevenLabs có rate limit)
    for idx, sfx_item in enumerate(sfx_sequence):
        text_prompt = sfx_item.get("description") or sfx_item.get("prompt") or sfx_item.get("text", "")
        duration = float(sfx_item.get("duration_s", 2.0))
        if not text_prompt:
            continue

        try:
            audio_bytes = await asyncio.to_thread(
                elevenlabs_sfx_client.generate_sfx,
                text_prompt=text_prompt,
                duration_s=duration,
                prompt_influence=0.5,
            )
        except Exception as e:
            logger.warning(f"[render._stage_sfx] SFX {idx} fail: {e}, skipping")
            continue

        sfx_path = sfx_dir / f"sfx_{idx:02d}.mp3"
        sfx_path.write_bytes(audio_bytes)
        sfx_paths.append(sfx_path)

    if not sfx_paths:
        return None

    # Concat all SFX → single track bằng ffmpeg concat demuxer
    if len(sfx_paths) == 1:
        return sfx_paths[0]

    # BUG-M6 fix: FFmpeg concat demuxer cần forward-slash path trên Windows
    concat_list = sfx_dir / "concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{p.absolute().as_posix()}'" for p in sfx_paths),
        encoding="utf-8",
    )
    combined_path = work_dir / "sfx.mp3"
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list), "-c", "copy", str(combined_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.warning(
            f"[render._stage_sfx] ffmpeg concat fail: {stderr.decode()[:200]}, "
            f"return first SFX only"
        )
        return sfx_paths[0]

    logger.info(f"[render._stage_sfx] concat {len(sfx_paths)} SFX → {combined_path.name}")
    return combined_path


async def _stage_compose(
    video_paths: list[Path],
    voice_path: Optional[Path],
    sfx_path: Optional[Path],
    gen_result: dict,
    settings: dict,
    work_dir: Path,
) -> Path:
    """FFmpeg compose video + audio + caption + watermark.

    Fix BUG-C1: audio_plan có đầy đủ field bắt buộc cho assemble_worker
        (mode, voice_audio_url, sfx_audio_url, sfx_sequence, caption_text_vn).
    Fix BUG-C3: aspect-aware (truyền target_resolution xuống ffmpeg).
    Fix BUG-C4: pull captions_timeline từ gen_result để burn-in.
    """
    output_path = work_dir / "final.mp4"
    assembler = AssembleWorker(work_dir=str(work_dir))

    # BUG-M1 fix: fallback mode khi missing voice/sfx — tránh assemble crash
    requested_mode = settings.get("audio_mode", "silent_native")
    effective_mode = requested_mode
    if requested_mode == "dialogue_vo" and not voice_path:
        logger.warning(
            "[render._stage_compose] dialogue_vo nhưng voice_path missing → fallback silent_native"
        )
        effective_mode = "silent_native"
    elif requested_mode == "asmr_macro" and not sfx_path:
        logger.warning(
            "[render._stage_compose] asmr_macro nhưng sfx_path missing → fallback silent_native"
        )
        effective_mode = "silent_native"

    audio_plan = {
        "mode": effective_mode,
        "voice_audio_url": str(voice_path) if voice_path else None,
        "sfx_audio_url": str(sfx_path) if sfx_path else None,
        "sfx_sequence": gen_result.get("sfx_sequence") or [],
        "caption_text_vn": (
            gen_result.get("captions_timeline")
            or gen_result.get("caption_text_vn")
            or _captions_from_approved_script(gen_result, settings)
        ),
    }

    # BUG-C3 fix: aspect-aware target resolution
    target_resolution = _resolve_target_resolution(
        settings.get("aspect_ratio", "9:16"),
        settings.get("resolution", "720p"),
    )

    await asyncio.to_thread(
        assembler.assemble,
        video_paths=[str(p) for p in video_paths],
        audio_plan=audio_plan,
        output_path=str(output_path),
        target_resolution=target_resolution,
    )

    return output_path


def _resolve_target_resolution(aspect_ratio: str, resolution: str) -> tuple[int, int]:
    """Map aspect + resolution → exact (width, height)."""
    base_height = {"480p": 854, "720p": 1280, "1080p": 1920}.get(resolution, 1280)
    if aspect_ratio == "9:16":
        return (base_height * 9 // 16, base_height)  # vertical
    if aspect_ratio == "16:9":
        return (base_height, base_height * 9 // 16)  # horizontal
    if aspect_ratio == "1:1":
        return (base_height, base_height)
    return (base_height * 9 // 16, base_height)  # default vertical


def _resolve_default_voice(gen_result: dict, settings: dict) -> str:
    """BUG-B11 fix: voice default theo niche thay vì hardcode 'mai'.

    Heuristic chain:
        1. Niche detected từ product → suggest male/female
        2. Audio mode authority-style → male tone
        3. Fallback "mai" (nữ Bắc) cho mọi case còn lại.
    """
    # Niche hint from gen_result product_positioning (passed by Director Brain)
    category = (
        (gen_result.get("product_positioning") or {})
        .get("product", {})
        .get("category", "")
    ).lower()

    # Tech / supplement_health authority → male voice
    if category.startswith(("tech", "supplement", "health")):
        return "duc_huy"  # nam trẻ Bắc, ấm áp
    # Mom_baby / cooking → millennial warm female
    if category.startswith(("mom_baby", "food")):
        return "huong"  # nữ Bắc credibility
    # Beauty / fashion → Gen Z young female
    if category.startswith(("beauty", "fashion")):
        return "ngan"  # nữ trẻ Bắc, dễ thương

    # Fallback default
    return "mai"


def _captions_from_approved_script(gen_result: dict, settings: dict) -> list[dict]:
    """BUG-C4 fix: nếu Generator không trả captions_timeline, gen từ approved script.

    Chia hook(0-3s) + body(3-N) + cta(last-5s..end) đều thời lượng.
    """
    hook = gen_result.get("_tts_hook_vn") or ""
    body = gen_result.get("_tts_body_vn") or ""
    cta = gen_result.get("_tts_cta_vn") or ""

    if not any([hook, body, cta]):
        return []

    duration = float(settings.get("duration_s", 15))
    hook_end = min(3.0, duration * 0.2)
    cta_start = max(duration - 5.0, duration * 0.75)

    captions: list[dict] = []
    if hook:
        captions.append({"time_s": f"0-{hook_end:.1f}", "text": hook})
    if body:
        captions.append({"time_s": f"{hook_end:.1f}-{cta_start:.1f}", "text": body})
    if cta:
        captions.append({"time_s": f"{cta_start:.1f}-{duration:.1f}", "text": cta})
    return captions


async def _stage_upload_r2(final_mp4: Path, job_id: str) -> str:
    """Upload final MP4 to Cloudflare R2 (S3-compatible) → return public URL.

    Wire boto3 S3 client với R2 endpoint.
    """
    bucket = os.getenv("R2_BUCKET_NAME", "ugc-vietnam-output")
    public_base = os.getenv("R2_PUBLIC_URL", "").rstrip("/")
    account_id = os.getenv("R2_ACCOUNT_ID")
    access_key = os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")

    if not all([account_id, access_key, secret_key, public_base]):
        # V3.4 — Persistent fallback dir (KHÔNG dùng work_dir vì work_dir bị cleanup)
        # Copy final.mp4 ra dir persistent → /api/v1/jobs/{id}/download serve được
        import shutil
        from pathlib import Path as _P
        persist_dir = _P(os.path.expanduser("~")) / ".ugc_vietnam" / "outputs" / job_id
        persist_dir.mkdir(parents=True, exist_ok=True)
        persist_path = persist_dir / "final.mp4"
        try:
            shutil.copy2(str(final_mp4), str(persist_path))
            logger.warning(
                f"[render._stage_upload_r2] R2 creds chưa setup → copied to persistent: {persist_path}"
            )
            return f"file://{persist_path.absolute()}"
        except Exception as e:
            logger.error(f"[render._stage_upload_r2] persist copy fail: {e}")
            return f"file://{final_mp4.absolute()}"

    key = f"jobs/{job_id}/final.mp4"
    endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"

    logger.info(f"[render._stage_upload_r2] uploading → s3://{bucket}/{key}")

    try:
        import boto3
        from botocore.config import Config as BotoConfig

        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=BotoConfig(
                signature_version="s3v4",
                region_name="auto",
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )

        await asyncio.to_thread(
            s3.upload_file,
            str(final_mp4),
            bucket,
            key,
            ExtraArgs={
                "ContentType": "video/mp4",
                "CacheControl": "public, max-age=31536000",
            },
        )

        public_url = f"{public_base}/{key}"

        # BUG-M3 fix: verify public access (HEAD request)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                head = await client.head(public_url)
                if head.status_code != 200:
                    logger.warning(
                        f"[render._stage_upload_r2] public_url returned {head.status_code} — "
                        f"R2 bucket có thể chưa set public read policy. URL: {public_url}"
                    )
        except Exception as e:
            logger.warning(f"[render._stage_upload_r2] public verify fail (non-fatal): {e}")

        logger.info(f"[render._stage_upload_r2] uploaded → {public_url}")
        return public_url

    except Exception as e:
        logger.exception(f"[render._stage_upload_r2] upload fail: {e}")
        # Fallback to local URL — user vẫn có thể access nếu cùng máy
        return f"file://{final_mp4.absolute()}"


# ============================================
# V3 Strategy → gen_result adapter
# ============================================

def _build_via_strategy(
    approved_script: dict,
    approved_shots: list[dict],
    approved_character_sheet: dict,
    reference_images: list[str],
    settings: dict,
) -> dict:
    """V3 — gọi strategy.build_prompt() pure function thay vì LLM generator.

    Build `gen_result` dict cùng shape generator.generate_from_approved() trả về
    để downstream stages (TTS, caption, SFX, atlas video gen) đọc bình thường.

    Strategy chọn:
        - settings.model → get_strategy_for_model(user_model)
        - Script object compose từ approved_shots + approved_character_sheet

    Output thêm metadata `_strategy_*` để render_pipeline biết:
        - submit_path override (Wan 2.7 dùng /generateImage)
        - payload đã built sẵn (downstream có thể pass thẳng hoặc rebuild)
    """
    from agent.strategies import get_strategy_for_model
    from agent.strategies.base import Script, Scene, Character

    user_model = settings.get("model", "vidu_q3")
    duration_s = int(settings.get("duration_s") or 15)
    aspect_ratio = settings.get("aspect_ratio") or "9:16"
    resolution = settings.get("resolution") or "720p"
    audio_mode = settings.get("audio_mode", "silent_native")

    # Build Character từ approved_character_sheet
    characters: list[Character] = []
    if approved_character_sheet:
        try:
            characters.append(Character(
                id=approved_character_sheet.get("id") or "main_character",
                name_vn=approved_character_sheet.get("name_vn") or "Main",
                age_apparent=approved_character_sheet.get("age_apparent"),
                gender=approved_character_sheet.get("gender"),
                face=approved_character_sheet.get("face") or "",
                outfit_top=approved_character_sheet.get("outfit_top"),
                outfit_bottom=approved_character_sheet.get("outfit_bottom"),
                personality_traits=approved_character_sheet.get("personality_traits") or [],
            ))
        except Exception as e:
            logger.warning(f"[render._build_via_strategy] char sheet parse fail: {e}")

    # Build Scenes từ approved_shots (MCSLA fields)
    scenes: list[Scene] = []
    for s in approved_shots:
        try:
            scenes.append(Scene(
                shot_id=s.get("shot_id") or f"S{len(scenes)+1}",
                duration_s=float(s.get("duration_s") or 3),
                purpose=s.get("purpose") or "shot",
                camera=s.get("C_camera") or s.get("camera") or "",
                subject=s.get("S_subject") or s.get("subject") or "",
                lighting=s.get("L_lighting") or s.get("lighting") or "",
                action=s.get("A_action") or s.get("action") or "",
                dialogue_vn=s.get("dialogue_vn"),
                caption_on_screen=s.get("caption_on_screen"),
            ))
        except Exception as e:
            logger.warning(f"[render._build_via_strategy] scene parse fail: {e}")

    needs_lipsync = audio_mode == "dialogue_vo" and any(s.dialogue_vn for s in scenes)
    needs_native_audio = audio_mode in ("dialogue_vo", "asmr_macro")

    script_obj = Script(
        title=approved_script.get("variant_id", ""),
        scenes=scenes,
        characters=characters,
        target_duration_s=duration_s,
        aspect_ratio=aspect_ratio,
        resolution_hint=resolution,
        needs_lipsync=needs_lipsync,
        needs_native_audio=needs_native_audio,
        style=settings.get("style", "ugc"),
    )

    strategy = get_strategy_for_model(user_model)
    # reference_images đóng vai keyframes cho strategy nếu user chưa qua Phase 2.5
    # (Phase 2.5 generated keyframes được handle riêng ở PATH B của _stage_video_gen)
    refs_for_strategy = reference_images[: strategy.max_refs()]

    # Wan 2.7 + lipsync models cần TTS audio_url TRƯỚC khi build_prompt.
    # Adapter này chạy TRƯỚC TTS stage → defer prompt build với placeholder.
    # Downstream _stage_video_gen (audio-driven branch) sẽ rebuild prompt khi có audio.
    if strategy.needs_tts_first():
        logger.info(
            f"[render._build_via_strategy] {user_model} cần TTS first — "
            f"defer strategy.build_prompt(), downstream sẽ rebuild khi có audio_url"
        )
        # Build placeholder gen_result với metadata; _stage_video_gen sẽ override payload sau
        placeholder_prompt = "[TTS deferred — built after audio gen]"
        return {
            "prompt_full": placeholder_prompt,
            "prompt": placeholder_prompt,
            "model": user_model,
            "_tts_hook_vn": approved_script.get("hook_text_vn"),
            "_tts_body_vn": approved_script.get("body_text_vn"),
            "_tts_cta_vn": approved_script.get("cta_text_vn"),
            "_source_variant_id": approved_script.get("variant_id"),
            "captions_timeline": _build_captions_timeline_local(
                hook=approved_script.get("hook_text_vn", ""),
                body=approved_script.get("body_text_vn", ""),
                cta=approved_script.get("cta_text_vn", ""),
                duration_s=approved_script.get("total_duration_s") or duration_s,
            ),
            "sfx_sequence": [],
            "_strategy_user_model": user_model,
            "_strategy_atlas_key": strategy.atlas_model_key,
            "_strategy_needs_tts_first": True,
            "_strategy_script_obj": script_obj.model_dump(),  # downstream rebuild
            "_strategy_refs_for_build": refs_for_strategy,
        }

    video_job = strategy.build_prompt(
        script=script_obj,
        keyframes=refs_for_strategy if refs_for_strategy else None,
        audio_urls=None,  # TTS chạy sau ở _stage_tts
    )

    # Compose gen_result dict matching shape downstream stages expect
    prompt_full = video_job.payload.get("prompt", "")
    gen_result: dict = {
        "prompt_full": prompt_full,
        "prompt": prompt_full,
        "model": user_model,
        "_tts_hook_vn": approved_script.get("hook_text_vn"),
        "_tts_body_vn": approved_script.get("body_text_vn"),
        "_tts_cta_vn": approved_script.get("cta_text_vn"),
        "_source_variant_id": approved_script.get("variant_id"),
        "captions_timeline": _build_captions_timeline_local(
            hook=approved_script.get("hook_text_vn", ""),
            body=approved_script.get("body_text_vn", ""),
            cta=approved_script.get("cta_text_vn", ""),
            duration_s=approved_script.get("total_duration_s") or duration_s,
        ),
        "sfx_sequence": [],  # V3 chưa drive SFX từ strategy — silent default
        # V3 metadata cho dispatcher
        "_strategy_user_model": user_model,
        "_strategy_atlas_key": video_job.model_key,
        "_strategy_submit_path": video_job.submit_path,
        "_strategy_payload": video_job.payload,
        "_strategy_refs": video_job.refs,
        "_strategy_name": video_job.strategy_name,
        "_strategy_reasoning": video_job.reasoning,
    }
    return gen_result


def _build_captions_timeline_local(hook: str, body: str, cta: str, duration_s: int) -> list[dict]:
    """Duplicate of generator._build_captions_timeline — tránh dependency vòng.

    Format match assemble_worker._burn_caption_vn expects:
        [{"time_s": "0-3.0", "text": "..."}]
    """
    if not any([hook, body, cta]):
        return []
    duration = float(duration_s or 15)
    hook_end = min(3.0, duration * 0.2)
    cta_start = max(duration - 5.0, duration * 0.75)
    captions: list[dict] = []
    if hook:
        captions.append({"time_s": f"0-{hook_end:.1f}", "text": hook})
    if body:
        captions.append({"time_s": f"{hook_end:.1f}-{cta_start:.1f}", "text": body})
    if cta:
        captions.append({"time_s": f"{cta_start:.1f}-{duration:.1f}", "text": cta})
    return captions


# ============================================
# JOBS store helper
# ============================================

def _update_job(jobs_store: Any, job_id: str, **fields: Any):
    """Patch job fields via jobs_store (file-based SQLite).

    BUG-H1 fix: use core.jobs_store.update() — persist qua restart.
    """
    try:
        from core.jobs_store import update as _store_update
        _store_update(job_id, **fields)
    except Exception as e:
        logger.warning(f"[render] Job {job_id} update fail: {e}")
