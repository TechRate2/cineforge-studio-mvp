"""Director V3 routes — Layer 1 planning + Human-in-the-Loop + Layer 3 generate.

Endpoints:
    POST   /api/v1/director/plan              — sync JSON, returns DirectorPlan
    POST   /api/v1/director/plan/stream       — SSE stream with stage progress
    POST   /api/v1/director/storyboard        — gen storyboard images for approved plan
    POST   /api/v1/director/generate          — fire render queue from approved plan
    GET    /api/v1/director/jobs/{job_id}     — poll job status
    POST   /api/v1/director/jobs/{job_id}/cancel

DirectorPlan flow (replaces old /jobs/propose):
    1. User submits brief + refs → /plan or /plan/stream
    2. Frontend shows Continuity Bible + Shot List + Evaluation in "Director Plan" tab
    3. User reviews / edits / approves (Human-in-the-Loop)
    4. (optional) /storyboard fires Seedream image gen for each storyboard_grid entry
    5. /generate kicks off video_worker.render_plan() → MP4

We keep the existing /jobs/* render path untouched (for backwards compat with the
legacy linear pipeline), but the canonical V3 flow is /director/*.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from typing import Optional, Any
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from vendors import r2_storage


# Sprint2 M2 — Per-image size cap to prevent OOM via base64 upload spam.
# 10MB raw decodes to ~13MB base64 chars; users uploading > this should
# go through /api/v1/upload first (R2 hosted URL).
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
_AUTONOMOUS_ASPECT_RATIOS = {"9:16", "16:9", "1:1"}


def _validate_optional_aspect_ratio(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"", "auto", "adaptive"}:
        return None
    if normalized not in _AUTONOMOUS_ASPECT_RATIOS:
        raise ValueError("aspect_ratio must be one of 9:16, 16:9, 1:1, auto")
    return normalized


def _validate_reference_images(images: list[str]) -> list[str]:
    """Reject reference_images that exceed the per-image size cap.

    Accepts both external URLs (http/https → cheap, just length check) and
    `data:image/...;base64,...` data-URLs (computes decoded byte size).
    """
    if not images:
        return images
    for i, img in enumerate(images):
        if not isinstance(img, str):
            raise ValueError(f"reference_images[{i}] not a string")
        if len(img) > 50_000_000:
            # 50MB string is suspicious regardless of format
            raise ValueError(f"reference_images[{i}] too large ({len(img)} chars)")
        if img.startswith("data:"):
            # Strip "data:image/jpeg;base64," prefix to get base64 payload
            comma = img.find(",")
            if comma > 0:
                b64 = img[comma + 1:]
                # base64 expansion ratio = 4/3 → bytes ≈ chars * 3/4
                approx_bytes = len(b64) * 3 // 4
                if approx_bytes > _MAX_IMAGE_BYTES:
                    raise ValueError(
                        f"reference_images[{i}] decoded ~{approx_bytes // 1024}KB "
                        f"> {_MAX_IMAGE_BYTES // 1024}KB cap. "
                        f"Upload qua POST /api/v1/upload trước để dùng external URL."
                    )
    return images

from agent.director_agent import director
from agent.schemas import DirectorPlan, ContinuityBible, Shot, StoryboardFrame
from agent import continuity_manager
from api.schemas import ProductInput, VideoSettings, AudioPlan
from workers import video_worker, reassemble_worker
from core import (
    director_history,
    production_artifacts,
    production_graph_store,
    autonomous_benchmark_store,
    render_feedback_store,
)
from core.config import settings as app_settings


router = APIRouter()


def _require_mutation_admin(x_admin_key: Optional[str]) -> None:
    """Guard routes that mutate production evidence or graph state."""
    expected = app_settings.admin_api_key
    if not expected:
        raise HTTPException(403, "Mutating endpoint is locked: set ADMIN_API_KEY first")
    if x_admin_key != expected:
        raise HTTPException(403, "Unauthorized: set X-Admin-Key with ADMIN_API_KEY value")


def _require_dev_metadata_stub(x_admin_key: Optional[str]) -> None:
    """Metadata stubs are allowed only for local development smoke tests."""
    if app_settings.app_env != "development":
        raise HTTPException(403, "Metadata stubs are disabled outside development")
    _require_mutation_admin(x_admin_key)


def _require_paid_executor_admin(x_admin_key: Optional[str]) -> None:
    """Paid graph execution must never be enabled by an unauthenticated request."""
    expected = app_settings.admin_api_key
    if not expected:
        raise HTTPException(403, "Set ADMIN_API_KEY before enabling paid graph execution")
    if x_admin_key != expected:
        raise HTTPException(403, "Unauthorized: paid graph execution requires X-Admin-Key")


# ============================================================
# Sprint2 M8 — Safe error message redaction
# ============================================================
import re as _re
_PATH_RE = _re.compile(
    r"(?:[A-Za-z]:\\|/)"           # Drive letter "C:\" or POSIX root "/"
    r"[\w\-./\\ ]+"                # path body
    r"(?::\d+)?",                  # optional ":line_number"
)


def _redact_error(e: BaseException, cap: int = 240) -> str:
    """Redact filesystem paths + line numbers from exception messages before
    exposing to API clients.

    Logs still get full str(e) via logger.exception — only the HTTP response
    body / error_message field gets the redacted version.
    """
    msg = str(e)
    # Strip type prefix "RuntimeError: " etc. → cleaner UX
    if ":" in msg[:60]:
        type_name = type(e).__name__
        if msg.startswith(f"{type_name}: "):
            msg = msg[len(type_name) + 2:]
    redacted = _PATH_RE.sub("<path>", msg)
    return redacted[:cap]


# ============================================================
# Request schemas
# ============================================================
class ContextInjection(BaseModel):
    pain_points: Optional[str] = Field(None, max_length=2000)
    real_reviews: Optional[str] = Field(None, max_length=3000)
    usps: Optional[str] = Field(None, max_length=1500)
    forbidden_to_say: Optional[str] = Field(None, max_length=1000)
    mood_hint: Optional[str] = Field(None, max_length=500)


class RenderFeedbackRequest(BaseModel):
    rating: str = Field("needs_work", max_length=20)
    issue_tags: list[str] = Field(default_factory=list, max_length=12)
    notes: Optional[str] = Field(None, max_length=1200)
    reviewer: Optional[str] = Field(None, max_length=80)
    output_url: Optional[str] = Field(None, max_length=2000)

    @field_validator("rating")
    @classmethod
    def _check_rating(cls, v: str) -> str:
        value = str(v or "").strip()
        if value not in render_feedback_store.ALLOWED_RATINGS:
            raise ValueError(
                f"rating must be one of {sorted(render_feedback_store.ALLOWED_RATINGS)}"
            )
        return value

    @field_validator("issue_tags")
    @classmethod
    def _check_issue_tags(cls, v: list[str]) -> list[str]:
        clean: list[str] = []
        for raw in v:
            tag = str(raw or "").strip()
            if not tag:
                continue
            if tag not in render_feedback_store.ALLOWED_ISSUE_TAGS:
                raise ValueError(f"unsupported issue tag: {tag}")
            if tag not in clean:
                clean.append(tag)
        return clean


class PlanRequest(BaseModel):
    product_input: ProductInput
    reference_images: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("reference_images")
    @classmethod
    def _check_image_sizes(cls, v: list[str]) -> list[str]:
        return _validate_reference_images(v)
    reference_role_hints: list[Optional[str]] = Field(
        default_factory=list,
        max_length=12,
        description=(
            "Per-image role hints (same length as reference_images, null = AI "
            "auto-detect). Allowed roles match agent/schemas.ReferenceAsset.role: "
            "primary_subject | secondary_subject | product_hero | product_detail | "
            "style_reference | environment | brand_asset. When supplied, Director "
            "skips the vision-pass for these refs."
        ),
    )
    reference_videos: list[str] = Field(default_factory=list, max_length=3)
    reference_audios: list[str] = Field(default_factory=list, max_length=3)
    user_brief: str = Field("", max_length=3000)
    context_injection: ContextInjection = Field(default_factory=ContextInjection)
    settings: VideoSettings
    niche_hint: Optional[str] = Field(
        None,
        description="Free string — Director Agent xử lý dynamic, không enum cứng",
    )


class StoryboardRequest(BaseModel):
    plan: DirectorPlan
    image_model: str = Field(
        "bytedance/seedream-v4.5",
        description="AtlasCloud image model — Seedream v4.5 default",
    )


class MasterBoardRequest(BaseModel):
    """V4 Sprint1 — request body for single-image director's storyboard board.

    V5.17.3 BUG FIX — added `reference_images` field. Previously Master Board
    used Seedream v4.5 TEXT-TO-IMAGE which has max_references=0 → ignored
    user-uploaded refs and auto-generated random character/product. Now when
    refs are supplied, endpoint auto-switches to Seedream v4.5 EDIT variant
    (max 10 refs, min 1) so character DNA + product details lock to user's
    actual uploads.
    """
    plan: DirectorPlan
    image_model: str = Field(
        "bytedance/seedream-v4.5",
        description="Image model — Seedream v4.5 default (ultra-wide 6240*2656). "
                    "Auto-switches to v4.5/edit when reference_images supplied. "
                    "Alternatives: google/nano-banana-pro/text-to-image",
    )
    reference_images: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="V5.17.3 — User-uploaded refs (character/product/style). "
                    "When non-empty, endpoint uses image-to-image edit variant "
                    "so generated board matches user's actual visual content "
                    "instead of model auto-bịa.",
    )

    @field_validator("reference_images")
    @classmethod
    def _check_master_board_refs(cls, v: list[str]) -> list[str]:
        return _validate_reference_images(v)


class MasterBoardResponse(BaseModel):
    plan_id: str
    board_url: str
    prompt: str
    size: str
    cost_usd: float
    elapsed_s: float


class GenerateRequest(BaseModel):
    """Render an approved DirectorPlan (canonical Human-in-the-Loop path).

    Use this when the user has reviewed (and optionally edited) the plan in the
    DirectorPlanModal. Pass the plan back verbatim — the server will
    re-validate continuity, sanitize, then dispatch render.

    For the rare case of "just plan and render in one shot" (skip review), use
    POST /api/v1/director/plan-and-render instead.
    """
    plan: DirectorPlan
    reference_images: list[str] = Field(default_factory=list, max_length=12)
    reference_videos: list[str] = Field(default_factory=list, max_length=3)
    reference_audios: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("reference_images")
    @classmethod
    def _check_image_sizes_generate(cls, v: list[str]) -> list[str]:
        return _validate_reference_images(v)

    settings: VideoSettings
    # V5.15.7 H2 — strict Pydantic schema. Was Optional[dict] (untyped) which
    # accepted typos like "dialogue_v0" silently → worker treated as no-mode →
    # silent render. AudioPlan enforces enum mode + URL field types with
    # extra="forbid" so typo keys 422.
    audio_plan: Optional[AudioPlan] = Field(
        None,
        description="Audio overlay plan. See AudioPlan schema for field semantics.",
    )
    use_llm_scene_gen: bool = Field(
        True,
        description="True = 1 LLM call per shot for adaptive prompt (slow, best). "
                    "False = deterministic build (fast, cheap).",
    )
    cost_gate_mode: str = Field(
        "off",
        description="`off` (default) → render full plan immediately. "
                    "`draft_first` → render shot[0] using Fast tier, evaluate, "
                    "then continue only if score ≥ cost_gate_threshold. "
                    "Saves 80-90% credits when a plan would fail.",
    )
    master_board_url: Optional[str] = Field(
        None,
        description="V4 Sprint1 Task #7 — URL of master storyboard board "
                    "(from POST /storyboard/master). When supplied, the worker "
                    "appends it as a GLOBAL style reference to every shot's "
                    "ref list — strongest identity-lock pattern (AtlasCloud "
                    "9-Panel Anchor). Skipped on i2v_chain and single-ref models.",
    )
    cost_gate_threshold: float = Field(
        7.0, ge=0, le=10,
        description="Pass threshold for cost_gate_mode='draft_first' (default 7.0/10).",
    )


class PlanAndRenderRequest(BaseModel):
    """One-shot: build plan + render immediately, no Human-in-the-Loop pause.

    Same input shape as POST /api/v1/director/plan, plus render settings +
    optional audio_plan. Returns the same response shape as POST /generate so
    clients can use a single polling path.
    """
    plan_request: PlanRequest
    audio_plan: Optional[AudioPlan] = None
    use_llm_scene_gen: bool = True


class ReviseRequest(BaseModel):
    """Mutate an existing DirectorPlan with a free-form user instruction.

    Use case: user is reviewing a plan in `DirectorPlanModal`, types
    "đổi shot 3 sang ban đêm" — server runs Layer 1.5 LLM call against
    `system_prompts/revise.md` which produces a minimally-edited plan that
    the FE swaps in (and the editor preserves dirty tracking).
    """
    plan: DirectorPlan
    instruction: str = Field(..., min_length=1, max_length=2000)
    settings: VideoSettings


class RefineRequest(BaseModel):
    """Re-render ONE shot from an existing plan.

    Trigger: Evaluation Layer flagged a shot (low score / red_flag), OR user
    eyeballed the final video and wants to redo a specific shot only — without
    burning credits on the whole video.

    Optionally pass `previous_last_frame_url` from the original render's chain
    metadata to keep identity continuity with the prior shot. If omitted and
    the shot has `previous_shot_id`, refine falls back to ref-mode (slight
    drift possible).

    Optional `shot_overrides` lets the user nudge the shot before re-render
    (e.g. tweak `visual.action`, change `duration_s`). The override is shallow-
    merged into the plan's shot before generation; the rest of the plan stays
    intact.
    """
    plan: DirectorPlan
    shot_id: str
    reference_images: list[str] = Field(default_factory=list, max_length=12)
    reference_videos: list[str] = Field(default_factory=list, max_length=3)
    reference_audios: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("reference_images")
    @classmethod
    def _check_image_sizes_refine(cls, v: list[str]) -> list[str]:
        return _validate_reference_images(v)

    settings: VideoSettings
    previous_last_frame_url: Optional[str] = None
    shot_overrides: Optional[dict] = Field(
        None,
        description="Shallow-merge overrides for the target shot (e.g. {'visual': {'action': 'now smiles'}}).",
    )
    use_llm_scene_gen: bool = True


# ============================================================
# In-memory job store for Director V3 (replace with Dramatiq queue later)
# ============================================================
# CRITICAL C4 — Concurrency safety notes:
#   This dict is mutated by FastAPI request handlers AND background coroutines
#   spawned via `_spawn()`. Because asyncio is single-threaded, single dict ops
#   (`d[k] = v`, `d[k].update(fields)`) are atomic at the bytecode level — no
#   race possible between coroutines. The only risk pattern would be
#   compound read-modify-write across `await` boundaries; there is currently
#   no such pattern in this module (verified by audit).
#
#   When we migrate to Dramatiq + Redis (multi-worker), this dict MUST be
#   replaced with a shared backing store (Redis hash or Postgres jobs table).
#   At that point add an explicit `asyncio.Lock` or use the SQLite-backed
#   `core/jobs_store.py` pattern.
_JOBS_STORE: dict[str, dict[str, Any]] = {}

# CRITICAL C5 — Background task lifecycle management.
# `asyncio.create_task(_run())` fire-and-forget loses references → tasks can be
# GC-cancelled mid-render, and on server shutdown there's no way to cancel them
# gracefully. We register every task in `_PENDING_TASKS` and provide a helper
# that wires `add_done_callback(discard)` so the set self-cleans, plus a public
# `shutdown_pending_tasks()` the lifespan handler in `main.py` can await.
_PENDING_TASKS: "set[asyncio.Task]" = set()


def _spawn(coro) -> asyncio.Task:
    """Spawn a background task with proper lifecycle tracking.

    Use this instead of `asyncio.create_task()` for any task that should
    survive past the originating request (long renders, refines, reassembles).
    """
    task = asyncio.create_task(coro)
    _PENDING_TASKS.add(task)
    task.add_done_callback(_PENDING_TASKS.discard)
    return task


async def shutdown_pending_tasks(timeout_s: float = 30.0) -> None:
    """Called by FastAPI lifespan shutdown — wait for in-flight tasks then cancel.

    Order:
      1. Snapshot current pending tasks
      2. Wait up to `timeout_s` for graceful completion
      3. Cancel any still pending + await cancellation
    """
    if not _PENDING_TASKS:
        return
    pending = list(_PENDING_TASKS)
    logger.info(f"[director] shutdown — awaiting {len(pending)} pending task(s) up to {timeout_s}s")
    done, still_pending = await asyncio.wait(pending, timeout=timeout_s)
    if still_pending:
        logger.warning(f"[director] shutdown — cancelling {len(still_pending)} task(s) past timeout")
        for t in still_pending:
            t.cancel()
        await asyncio.gather(*still_pending, return_exceptions=True)
    logger.info(f"[director] shutdown — {len(done)} task(s) finished gracefully")


# ============================================================
# POST /plan — sync
# ============================================================
@router.post("/plan", response_model=DirectorPlan)
async def create_plan(request: PlanRequest):
    """Layer 1 — Director Agent V3 builds DirectorPlan from brief + refs."""
    if not (request.product_input.url or request.product_input.text_description or request.user_brief):
        raise HTTPException(400, "Provide at least one of: product_input.url, product_input.text_description, or user_brief")

    tech_config = {
        "duration_s": request.settings.duration_s,
        "aspect_ratio": request.settings.aspect_ratio,
        "audio_mode": request.settings.audio_mode,
        "model": request.settings.model,
        "resolution": request.settings.resolution,
        "num_shots": request.settings.num_shots,
    }

    try:
        plan = await director.plan(
            product_input=request.product_input.model_dump(exclude_none=True),
            reference_images=request.reference_images,
            reference_videos=request.reference_videos,
            reference_audios=request.reference_audios,
            user_brief=request.user_brief,
            context_injection=request.context_injection.model_dump(exclude_none=True),
            tech_config=tech_config,
            niche_hint=request.niche_hint,
            reference_role_hints=request.reference_role_hints or None,
        )
    except Exception as e:
        logger.exception("[/director/plan] failed")
        raise HTTPException(500, f"Director Agent failed: {_redact_error(e)}") from e

    return plan


# ============================================================
# POST /plan/stream — SSE
# ============================================================
@router.post("/plan/stream")
async def create_plan_stream(request: PlanRequest, raw_request: Request):
    """SSE-streamed Director planning. Stages: init → vision → director → evaluation → done."""
    if not (request.product_input.url or request.product_input.text_description or request.user_brief):
        raise HTTPException(400, "Provide brief or product_input")

    tech_config = {
        "duration_s": request.settings.duration_s,
        "aspect_ratio": request.settings.aspect_ratio,
        "audio_mode": request.settings.audio_mode,
        "model": request.settings.model,
        "resolution": request.settings.resolution,
        "num_shots": request.settings.num_shots,
    }

    event_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    async def _cb(event: dict):
        try:
            event_queue.put_nowait(("stage", event))
        except asyncio.QueueFull:
            try:
                event_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            await event_queue.put(("stage", event))

    async def _run():
        try:
            plan = await director.plan(
                product_input=request.product_input.model_dump(exclude_none=True),
                reference_images=request.reference_images,
                reference_videos=request.reference_videos,
                reference_audios=request.reference_audios,
                user_brief=request.user_brief,
                context_injection=request.context_injection.model_dump(exclude_none=True),
                tech_config=tech_config,
                niche_hint=request.niche_hint,
                reference_role_hints=request.reference_role_hints or None,
                progress_callback=_cb,
            )
            await event_queue.put(("complete", plan.model_dump()))
        except Exception as e:
            logger.exception("[/director/plan/stream] failed")
            # M14 fix — force-put error event even if queue full (drain oldest)
            try:
                await asyncio.wait_for(
                    event_queue.put(("error", {"error": _redact_error(e)})),
                    timeout=2.0,
                )
            except asyncio.TimeoutError:
                logger.error("[/director/plan/stream] queue stuck — could not send error event")
        finally:
            # Sprint2 M14 — guarantee __end__ delivery even when queue is full.
            # Drain enough capacity for the terminal sentinel; client must
            # receive __end__ to close the SSE loop cleanly.
            try:
                await asyncio.wait_for(
                    event_queue.put(("__end__", None)),
                    timeout=2.0,
                )
            except asyncio.TimeoutError:
                # Last-resort drain: pop oldest event, then retry
                try:
                    event_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    event_queue.put_nowait(("__end__", None))
                except asyncio.QueueFull:
                    logger.error("[/director/plan/stream] failed to send __end__ — client may hang")

    async def _gen():
        yield 'event: open\ndata: {"message":"Director V3 starting"}\n\n'
        task = asyncio.create_task(_run())
        try:
            while True:
                if await raw_request.is_disconnected():
                    task.cancel()
                    break
                try:
                    et, payload = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                if et == "__end__":
                    break
                yield f"event: {et}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                if et in ("complete", "error"):
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ============================================================
# POST /storyboard — gen storyboard images for an approved plan
# ============================================================
@router.post("/storyboard")
async def gen_storyboard(request: StoryboardRequest):
    """Fire Seedream/Flux image gen for each frame in storyboard_grid.

    Returns updated DirectorPlan with `generated_url` filled per frame.
    Cost: ~$0.04 / frame × N shots. User can skip and upload manually instead.
    """
    from vendors.atlascloud import atlas_client
    if atlas_client is None:
        raise HTTPException(503, "AtlasCloud not configured")

    plan = request.plan
    if not plan.storyboard_grid:
        plan = continuity_manager.ensure_storyboard_complete(plan)

    async def _gen_one(frame: StoryboardFrame) -> StoryboardFrame:
        if frame.user_uploaded_url:
            frame.generated_url = frame.user_uploaded_url
            return frame
        try:
            res = await asyncio.to_thread(
                atlas_client.generate_image,
                prompt=frame.prompt,
                model=request.image_model,
                size=frame.image_size,
                n=1,
            )
            frame.generated_url = res.get("url")
        except Exception as e:
            logger.warning(f"[storyboard] frame {frame.shot_id} fail: {e}")
        return frame

    # Parallel batch — 4 concurrent
    sem = asyncio.Semaphore(4)

    async def _bounded(f: StoryboardFrame) -> StoryboardFrame:
        async with sem:
            return await _gen_one(f)

    plan.storyboard_grid = await asyncio.gather(*(_bounded(f) for f in plan.storyboard_grid))
    plan.cost_estimate.storyboard_gen_cost_usd = round(0.04 * len(plan.storyboard_grid), 3)
    plan.cost_estimate.total_cost_usd = round(
        plan.cost_estimate.plan_cost_usd
        + plan.cost_estimate.storyboard_gen_cost_usd
        + plan.cost_estimate.render_cost_usd
        + plan.cost_estimate.audio_cost_usd,
        3,
    )
    return plan


# ============================================================
# POST /storyboard/master/preview — V5.17.4 prompt preview (no LLM call)
# ============================================================
class MasterBoardPromptPreview(BaseModel):
    """V5.17.4 — Return the EXACT prompt that /storyboard/master would send to
    the image model, WITHOUT actually generating. Enables users to:
      - Review/copy the prompt before paying $0.04
      - Paste into external tools (ChatGPT, Midjourney, etc.) if they have
        better image gen subscriptions
      - Make an informed Upload-vs-Generate decision
    Fast (~10ms, no vendor call, no charge).
    """
    plan_id: str
    prompt: str
    size: str
    suggested_models: list[dict]  # [{key, name, cost_usd, supports_refs}]


@router.post("/storyboard/master/preview", response_model=MasterBoardPromptPreview)
async def preview_master_storyboard_prompt(request: MasterBoardRequest) -> MasterBoardPromptPreview:
    """V5.17.4 — Return prompt + suggested models WITHOUT generating image.

    User can copy prompt to external tool (GPT-Image, MJ, etc.) and upload
    result back via /upload-media. Or click Generate to use AtlasCloud
    vendor (current flow).
    """
    from agent.image_specs import IMAGE_MODEL_SPECS
    from agent.storyboard_board import (
        build_master_board_prompt, board_size_for_aspect,
    )
    plan = request.plan
    prompt = build_master_board_prompt(plan)
    size = board_size_for_aspect(plan.continuity_bible.aspect_ratio)

    user_refs_present = bool(request.reference_images)
    # Surface available models with cost + whether they support refs
    suggested = []
    for key, spec in IMAGE_MODEL_SPECS.items():
        if not spec.get("available", True):
            continue
        supports_refs = bool(spec.get("images_field"))
        # If user has refs uploaded, only suggest edit variants
        if user_refs_present and not supports_refs:
            continue
        # If user has NO refs, only suggest t2i variants (edit needs refs)
        if not user_refs_present and supports_refs:
            continue
        suggested.append({
            "key": key,
            "name": spec.get("name_vn", key),
            "endpoint": spec.get("endpoint"),
            "cost_usd": spec.get("cost_per_image_usd", 0.0),
            "supports_refs": supports_refs,
            "variant": spec.get("variant", "text-to-image"),
        })

    return MasterBoardPromptPreview(
        plan_id=plan.plan_id,
        prompt=prompt,
        size=size,
        suggested_models=suggested,
    )


# ============================================================
# POST /storyboard/master — V4 Sprint1 single-image director board
# ============================================================
@router.post("/storyboard/master", response_model=MasterBoardResponse)
async def gen_master_storyboard(request: MasterBoardRequest) -> MasterBoardResponse:
    """Gen ONE ultra-wide director's storyboard board (12-panel grid on 1 canvas).

    Replaces the 12-separate-image flow with a SINGLE Seedream v4.5 call.
    Industry pattern (AtlasCloud 9-Panel Anchor): all panels share pixels →
    same outfit/hair/face locked across panels. Becomes a style_reference for
    every Seedance shot render downstream → global identity anchoring.

    Cost: ~$0.036 (Seedream) or ~$0.084 (Nano Banana Pro) per board.

    AUDIT FIX H1: previously called `atlas_client.generate_image()` which hits
    `/model/generateImage` — but per `image_specs.py`, Seedream actually uses
    `/model/generateVideo` + polls `/model/result`. We now mirror the
    image_direct.py pattern: build_image_payload + custom POST + correct
    poll_path per spec.
    """
    import time
    from vendors.atlascloud import atlas_client, _unwrap
    from agent.image_specs import (
        IMAGE_MODEL_SPECS, build_image_payload, estimate_image_cost,
    )
    from agent.storyboard_board import (
        build_master_board_prompt, board_size_for_aspect,
    )
    if atlas_client is None:
        raise HTTPException(503, "AtlasCloud not configured")

    plan = request.plan
    t_start = time.time()
    prompt = build_master_board_prompt(plan)
    size = board_size_for_aspect(plan.continuity_bible.aspect_ratio)

    # Resolve model_key — accept short keys ("seedream_v45") OR full endpoint
    # ("bytedance/seedream-v4.5"). Default Seedream v4.5.
    # V5.17.6 — Include EDIT variant endpoints so FE Board UI dropdown can
    # send any endpoint listed in /storyboard/master/preview suggested_models.
    short_to_key = {
        "bytedance/seedream-v4.5": "seedream_v45",
        "bytedance/seedream-v4.5/edit": "seedream_v45_edit",
        "google/nano-banana-pro/text-to-image": "nano_banana_pro_t2i",
        "google/nano-banana-pro/edit": "nano_banana_pro_edit",
        "google/nano-banana-2/text-to-image": "nano_banana_2_t2i",
        "google/nano-banana-2/edit": "nano_banana_2_edit",
    }
    model_key = short_to_key.get(request.image_model, request.image_model)

    # V5.17.3 BUG FIX — Auto-switch to EDIT variant when user provided refs.
    # Otherwise Seedream text-to-image (max_refs=0) ignores refs and bịa
    # random character/product → Master Board doesn't match user uploads.
    user_refs = [u for u in (request.reference_images or []) if u][:10]
    if user_refs:
        edit_map = {
            "seedream_v45": "seedream_v45_edit",
            "nano_banana_pro_t2i": "nano_banana_pro_edit",
            "nano_banana_2_t2i": "nano_banana_2_edit",
        }
        edit_key = edit_map.get(model_key)
        if edit_key and edit_key in IMAGE_MODEL_SPECS:
            logger.info(
                f"[master_board] {plan.plan_id} {len(user_refs)} refs supplied → "
                f"auto-switching {model_key} → {edit_key} (image-to-image edit "
                f"variant locks character/product to user uploads)"
            )
            model_key = edit_key

    if model_key not in IMAGE_MODEL_SPECS:
        raise HTTPException(
            400,
            f"image_model '{request.image_model}' không support. "
            f"Available: {list(short_to_key.keys())}",
        )
    spec = IMAGE_MODEL_SPECS[model_key]

    # V5.15.7 H3 — Pre-validate per-model payload contract BEFORE calling
    # build_image_payload so 400s surface with actionable messages instead
    # of leaking ValueError text. Two payload contracts:
    #   - "size" models (Seedream v4.5): expect a "WxH" string like "6240*2656"
    #   - "aspect_ratio" models (Nano Banana): expect ratio + resolution enum
    uses_size_contract = bool(spec.get("size"))
    if uses_size_contract:
        if not (isinstance(size, str) and ("*" in size or "x" in size.lower())):
            raise HTTPException(
                400,
                f"image_model '{model_key}' requires WxH size string; "
                f"board_size_for_aspect returned '{size}' for aspect "
                f"'{plan.continuity_bible.aspect_ratio}'. This is a server bug — "
                f"file a ticket.",
            )
    else:
        ar_options = (spec.get("aspect_ratio") or {}).get("options") or []
        if not ar_options:
            raise HTTPException(
                500,
                f"image_model '{model_key}' has no aspect_ratio.options in spec — "
                f"misconfigured. File a ticket.",
            )

    # Build per-model payload — Seedream uses `size`, Nano Banana uses
    # aspect_ratio+resolution. board_size_for_aspect returns Seedream-style
    # "WxH" — for Nano Banana we fall back to 4K + matching aspect.
    # V5.17.3 — Edit variants need `images` param (user-uploaded refs).
    is_edit_variant = spec.get("variant") == "edit"
    edit_images = user_refs if is_edit_variant else None
    try:
        if uses_size_contract:
            logger.info(
                f"[master_board] {plan.plan_id} model={model_key} size={size} "
                f"variant={spec.get('variant')} refs={len(edit_images or [])} (size contract)"
            )
            payload = build_image_payload(
                model_key=model_key, prompt=prompt, size=size, n=1,
                images=edit_images,
            )
        else:
            ar_options = (spec.get("aspect_ratio") or {}).get("options") or []
            requested_ar = plan.continuity_bible.aspect_ratio
            ar = requested_ar if requested_ar in ar_options else "16:9"
            if ar != requested_ar:
                logger.info(
                    f"[master_board] {plan.plan_id} aspect '{requested_ar}' not in "
                    f"{ar_options} for {model_key} — fallback to '16:9'"
                )
            logger.info(
                f"[master_board] {plan.plan_id} model={model_key} ar={ar} res=4k "
                f"variant={spec.get('variant')} refs={len(edit_images or [])} (aspect contract)"
            )
            payload = build_image_payload(
                model_key=model_key, prompt=prompt,
                aspect_ratio=ar, resolution="4k",
                images=edit_images,
            )
    except ValueError as e:
        raise HTTPException(400, f"Master board payload invalid: {e}") from e

    submit_path = spec.get("submit_path", "/model/generateImage")
    poll_path = spec.get("poll_path", "/model/prediction")

    # Submit + poll using the per-model paths
    try:
        resp = await asyncio.to_thread(
            atlas_client.client.post,
            f"{atlas_client.base_url}{submit_path}",
            json=payload,
        )
        resp.raise_for_status()
        body = _unwrap(resp.json())
        prediction_id = body.get("id") or body.get("prediction_id") or body.get("request_id")
        if not prediction_id:
            raise HTTPException(502, f"AtlasCloud submit no prediction_id. Body: {body}")
        result = await asyncio.to_thread(
            atlas_client._poll_prediction,
            prediction_id, 3, 180, poll_path,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[master_board] gen fail: {e}")
        raise HTTPException(502, f"Master board gen failed: {e}") from e

    outputs = result.get("outputs") or []
    board_url = (outputs[0] if outputs else result.get("output_url") or result.get("url") or "")
    if not board_url:
        raise HTTPException(502, f"Image model returned no URL. result={result}")

    cost = estimate_image_cost(model_key, 1)

    return MasterBoardResponse(
        plan_id=plan.plan_id,
        board_url=board_url,
        prompt=prompt,
        size=size,
        cost_usd=cost,
        elapsed_s=round(time.time() - t_start, 2),
    )


# ============================================================
# POST /generate — render an approved DirectorPlan (canonical path)
# ============================================================
@router.post("/generate")
async def generate_video(
    request: GenerateRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """Layer 3 — render an approved DirectorPlan.

    Canonical Human-in-the-Loop entry: the frontend POSTs back the plan the user
    just reviewed (or edited) in `DirectorPlanModal`. The server re-validates
    continuity, sanitizes soft issues, then dispatches the render in the
    background. Returns a `job_id` for polling at `/director/jobs/{id}`.

    Sprint2 M11 — Idempotency-Key support (Stripe pattern). When the client
    sends `Idempotency-Key: <uuid>` header, the same key+body combo replays
    the original response for 24h. Prevents double-render on browser retry.

    V5.15.5 L3 — Idempotency scope note: the body hash includes every field
    of GenerateRequest, including `master_board_url` and the full `plan`
    (with shot.duration_s). Two consequences worth knowing:
      1. **Master Board regen**: if the user generates a new board between
         retries (different board_url), the body hash differs and the second
         /generate call returns 409 Conflict. Workaround: rotate the
         Idempotency-Key after each board regen.
      2. **Wan 2.7 duration snap**: the worker mutates shot.duration_s via
         continuity_manager.snap_discrete_durations() AFTER /generate accepts
         the body. A retry with the same key returns the cached response,
         which may reflect the snapped durations (different from what the
         client originally sent). This is intentional — replay surfaces the
         actual state of record, not the original request payload.
    """
    # Sprint2 M11 — Idempotency check (replay cached response if key+body match)
    if idempotency_key:
        from core.idempotency import hash_body as _hash_body, lookup as _idem_lookup
        body_hash = _hash_body(request.model_dump())
        cached = _idem_lookup(idempotency_key, body_hash)
        if cached:
            if not cached["body_match"]:
                raise HTTPException(
                    409,
                    "Idempotency-Key đã dùng với body khác. Đổi key hoặc đợi 24h.",
                )
            logger.info(
                f"[/director/generate] Idempotency replay key={idempotency_key[:16]}…"
            )
            return cached["response_json"]

    # Validate continuity upfront → fail-fast 400 for tampered plans
    try:
        warnings = continuity_manager.validate_plan(
            request.plan,
            target_duration_s=request.settings.duration_s,
            tolerance_s=2,
        )
    except continuity_manager.ContinuityError as e:
        raise HTTPException(400, f"Plan rejected by Continuity Manager: {e}") from e

    # V3.1 + Sprint2 M1 — validate plan against chosen model's HARD limits
    # (max refs, discrete durations, etc.). These are SPEC violations that
    # will cause AtlasCloud to 400-reject the render mid-pipeline → user
    # wastes the LLM cost. Strict mode rejects 400 with a clear message,
    # forcing user to Refine before burning credits.
    model_violations = continuity_manager.validate_plan_against_model(
        request.plan, user_model=request.settings.model,
    )
    if model_violations:
        # Whitelist: minor violations (info-only) we still warn but don't reject.
        # Hard violations (duration discrete / refs overflow) MUST reject.
        hard_violations = [
            v for v in model_violations
            if "discrete" in v or "max " in v or "out of range" in v
        ]
        if hard_violations:
            logger.error(
                f"[/director/generate] {request.plan.plan_id} HARD model-fit "
                f"violations — render rejected: {hard_violations[:3]}"
            )
            raise HTTPException(
                400,
                "Plan not executable with model "
                f"`{request.settings.model}`: " + " · ".join(hard_violations[:3]) +
                " — open DirectorPlanModal → adjust durations/refs or switch model.",
            )
        # Soft violations only — log + record on job for UI display
        warnings.extend(model_violations)
        logger.warning(
            f"[/director/generate] {request.plan.plan_id} soft model-fit "
            f"warnings: {model_violations[:5]}"
        )

    job_id = f"job_{uuid.uuid4().hex[:12]}"
    # Sprint2 M16 — bucket warnings by severity for UI display
    classified = continuity_manager.classify_warnings(warnings)
    _JOBS_STORE[job_id] = {
        "status": "pending",
        "progress": 0,
        "current_step": "queued",
        "plan_id": request.plan.plan_id,
        "mode": "approved",
        "validation_warnings": warnings or [],
        "validation_severity": classified,  # {errors, warnings, info}
        "created_at": datetime.now(timezone.utc).isoformat() + "Z",
    }
    if warnings:
        logger.warning(
            f"[/director/generate] {job_id} plan warnings "
            f"({len(classified['errors'])}E/{len(classified['warnings'])}W/{len(classified['info'])}I, "
            f"will sanitize): {warnings[:5]}"
        )

    sanitized_plan = continuity_manager.sanitize_plan(request.plan)
    # V5.15.7 H2 — worker uses dict.get() on audio_plan; convert AudioPlan
    # model to dict here so worker stays unchanged.
    audio_plan_dict = (
        request.audio_plan.model_dump(exclude_none=True)
        if request.audio_plan is not None else None
    )

    async def _run():
        try:
            await video_worker.render_plan(
                job_id=job_id,
                plan=sanitized_plan,
                reference_images=request.reference_images,
                reference_videos=request.reference_videos,
                reference_audios=request.reference_audios,
                user_model=request.settings.model,
                resolution=request.settings.resolution,
                audio_plan=audio_plan_dict,
                jobs_store=_JOBS_STORE,
                use_llm_scene_gen=request.use_llm_scene_gen,
                cost_gate_mode=request.cost_gate_mode,
                cost_gate_threshold=request.cost_gate_threshold,
                master_board_url=request.master_board_url,
            )
        except video_worker.JobCancelledError:
            # V5.1 — user cancelled mid-render; status already set by /cancel route
            logger.info(f"[/director/generate] job {job_id} cancelled gracefully")
            await asyncio.to_thread(video_worker.cleanup_failed_job, job_id)
        except Exception as e:
            logger.exception(f"[/director/generate] job {job_id} failed")
            _JOBS_STORE[job_id].update(status="failed", error_message=_redact_error(e))
            await asyncio.to_thread(video_worker.cleanup_failed_job, job_id)  # Sprint3 B3

    _spawn(_run())

    response = {
        "job_id": job_id,
        "polling_url": f"/api/v1/director/jobs/{job_id}",
        "estimated_duration_s": sum(s.duration_s for s in sanitized_plan.shot_list),
        "estimated_cost_usd": sanitized_plan.cost_estimate.total_cost_usd,
        "plan_id": sanitized_plan.plan_id,
        "mode": "approved",
        "cost_gate_mode": request.cost_gate_mode,
    }

    # Sprint2 M11 — store for idempotency replay (24h TTL)
    if idempotency_key:
        from core.idempotency import hash_body as _hash_body, store as _idem_store
        try:
            _idem_store(idempotency_key, _hash_body(request.model_dump()), response, status_code=201)
        except Exception as e:
            logger.warning(f"[/director/generate] idem store fail (non-fatal): {e}")

    return response


# ============================================================
# POST /plan-and-render — one-shot escape hatch (no Human-in-the-Loop)
# ============================================================
# ============================================================
# V6.1 — Autonomous Director endpoint (1-call full pipeline)
# ============================================================

class AutonomousGenerateRequest(BaseModel):
    """User-facing request — 1 idea + refs, agent tự tạo plan + render.

    Khác với /plan-and-render (cần ProductInput + VideoSettings chi tiết),
    endpoint này chỉ cần 1 ý tưởng ngắn — toàn bộ niche/hook/storyboard/
    director do 5-skill autonomous chain tự quyết.
    """
    user_idea: str = Field(..., min_length=5, max_length=2000)
    reference_image_urls: list[str] = Field(default_factory=list, max_length=9)
    reference_video_urls: list[str] = Field(default_factory=list, max_length=3)
    reference_audio_urls: list[str] = Field(default_factory=list, max_length=3)
    reference_manifest: dict[str, Any] = Field(default_factory=dict)
    pinned_asset_ids: list[str] = Field(
        default_factory=list,
        max_length=12,
        description="Approved autonomous asset pin IDs to inject as image references.",
    )
    auto_select_asset_pins: bool = Field(
        True,
        description="When true, backend may add high-priority approved pins for the inferred niche/market/series.",
    )
    series_key: str = Field("", max_length=120, description="Optional brand/series/campaign memory scope.")
    user_id: str = Field("default_user", max_length=120, description="Commercial user/account id for usage and quota tracking.")
    brand_kit_id: Optional[str] = Field(None, max_length=120, description="Optional Brand Kit id to apply to strategy and prompts.")
    template_id: Optional[str] = Field(None, max_length=120, description="Optional commercial template id to apply to strategy and prompts.")
    target_platform: str = Field("tiktok", description="tiktok|reels|youtube_short|youtube_long|universal")
    target_market: str = Field("auto", description="auto|vn|us|sea|jp|kr|global")
    duration_hint_s: Optional[int] = Field(None, ge=4, le=1800)
    aspect_ratio: Optional[str] = Field(None, description="auto|9:16|16:9|1:1")
    user_model: str = Field("auto", description="auto|seedance_2_0|seedance_2_0_fast|wan_2_7")
    resolution: str = "720p"
    use_vision_llm_for_tagging: bool = True
    approved_plan_id: Optional[str] = Field(None, max_length=80)
    approved_plan_source_hash: Optional[str] = Field(None, max_length=80)
    approved_plan_source_length: Optional[int] = Field(None, ge=0, le=2000)
    consistency_review_approved: bool = Field(
        False,
        description="Explicit user approval for requires_review consistency policies before paid render.",
    )
    consistency_review_decision: str = Field(
        "",
        max_length=24,
        description="Human consistency review decision: approved or rejected.",
    )
    consistency_review_reason: str = Field(
        "",
        max_length=1000,
        description="Human-entered reason for approving or rejecting a requires_review consistency policy.",
    )
    consistency_reviewed_segment_ids: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Segment ids included in the consistency review decision.",
    )
    approved_dry_run_job_id: Optional[str] = Field(
        None,
        max_length=120,
        description="Dry-run job id whose exact long-form plan was approved before paid render.",
    )
    approved_segment_ids: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Optional approved long-form segment ids from the review UI.",
    )
    dry_run_only: bool = Field(
        False,
        description="When true, build the safe Seedance execution plan and dry-run report without paid vendor calls.",
    )
    max_total_cost_usd: Optional[float] = Field(
        None,
        ge=0,
        description="Optional hard spend cap enforced before paid Seedance render.",
    )

    @field_validator("reference_image_urls")
    @classmethod
    def _check_image_urls(cls, v: list[str]) -> list[str]:
        return _validate_reference_images(v)

    @field_validator("aspect_ratio")
    @classmethod
    def _check_aspect_ratio(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_aspect_ratio(v)


class BrandKitUpsertRequest(BaseModel):
    """User-facing Brand Kit mutation payload."""

    owner_user_id: str = Field("default_user", max_length=120)
    brand_id: Optional[str] = Field(None, max_length=120)
    name: str = Field(..., min_length=1, max_length=120)
    logo_urls: list[str] = Field(default_factory=list, max_length=12)
    primary_colors: list[str] = Field(default_factory=list, max_length=12)
    fonts: list[str] = Field(default_factory=list, max_length=8)
    voice: str = Field("", max_length=600)
    style_guide: str = Field("", max_length=2000)
    negative_constraints: list[str] = Field(default_factory=list, max_length=20)


@router.post("/commercial/brand-kits")
async def upsert_commercial_brand_kit(request: BrandKitUpsertRequest):
    """Create or update a persistent Brand Kit used by autonomous renders."""
    from commercial import commercial_store

    try:
        kit = commercial_store.upsert_brand_kit(**request.model_dump())
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc
    return kit.model_dump(mode="json")


@router.get("/commercial/brand-kits")
async def list_commercial_brand_kits(owner_user_id: str = "default_user"):
    """List Brand Kits for a user/account."""
    from commercial import commercial_store

    return {
        "brand_kits": [kit.model_dump(mode="json") for kit in commercial_store.list_brand_kits(owner_user_id)],
    }


@router.get("/commercial/templates")
async def list_commercial_templates():
    """List active commercial templates."""
    from commercial import commercial_store

    return {
        "templates": [template.model_dump(mode="json") for template in commercial_store.list_templates()],
    }


@router.get("/commercial/usage/{user_id}")
async def get_commercial_usage(user_id: str):
    """Return credit balance and recent usage history for a user/account."""
    from commercial import commercial_store

    try:
        return commercial_store.credit_balance(user_id)
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/commercial/analytics/summary")
async def get_commercial_analytics_summary(user_id: Optional[str] = None, brand_id: Optional[str] = None):
    """Return basic render/usage analytics from the commercial ledger."""
    from commercial import commercial_store

    try:
        return commercial_store.analytics_summary(user_id=user_id, brand_id=brand_id)
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/monitoring/longform/summary")
async def get_longform_monitoring_summary(limit: int = 100):
    """Return recent long-form operational metrics and alerts."""
    from monitoring import longform_monitor

    longform_monitor.evaluate_stuck_jobs()
    return longform_monitor.monitoring_summary(limit=limit)


@router.get("/monitoring/longform/alerts")
async def get_longform_monitoring_alerts(limit: int = 50):
    """Return recent long-form monitoring alerts."""
    from monitoring import longform_monitor

    return {"alerts": longform_monitor.list_alerts(limit=limit)}


def _approved_plan_meta_from_request(request: AutonomousGenerateRequest) -> dict[str, Any]:
    """Validate optional preflight approval metadata before paid rendering."""
    if request.approved_plan_source_hash and request.aspect_ratio:
        approved_aspect_marker = f"Output frame:\n{request.aspect_ratio}"
        if approved_aspect_marker not in request.user_idea:
            raise HTTPException(
                422,
                {
                    "code": "approved_plan_aspect_ratio_mismatch",
                    "message": "Approved plan does not include the requested output frame. Re-approve the current plan before rendering.",
                    "approved_plan_id": request.approved_plan_id,
                    "requested_aspect_ratio": request.aspect_ratio,
                },
            )
    actual_hash = hashlib.sha256(request.user_idea.encode("utf-8")).hexdigest()
    actual_length = len(request.user_idea)
    if request.approved_plan_source_hash and request.approved_plan_source_hash != actual_hash:
        raise HTTPException(
            422,
            {
                "code": "approved_plan_source_hash_mismatch",
                "message": "Approved plan hash does not match the render source. Re-approve the current plan before rendering.",
                "approved_plan_id": request.approved_plan_id,
            },
        )
    if (
        request.approved_plan_source_length is not None
        and request.approved_plan_source_length != actual_length
    ):
        raise HTTPException(
            422,
            {
                "code": "approved_plan_source_length_mismatch",
                "message": "Approved plan length does not match the render source. Re-approve the current plan before rendering.",
                "approved_plan_id": request.approved_plan_id,
            },
        )
    return {
        "id": request.approved_plan_id,
        "source_hash": request.approved_plan_source_hash,
        "source_length": request.approved_plan_source_length,
        "actual_source_hash": actual_hash if request.approved_plan_source_hash else None,
        "actual_source_length": actual_length if request.approved_plan_source_length is not None else None,
        "consistency_review_approved": bool(request.consistency_review_approved),
        "included_in_render_source": bool(
            request.approved_plan_id
            and request.approved_plan_source_hash
            and request.approved_plan_source_hash == actual_hash
        ),
    }


_CONFIRMED_REFERENCE_ROLES = {
    "image": {
        "character_anchor", "secondary_character", "product_hero", "product_detail",
        "style_reference", "environment", "brand_asset", "continuity_anchor",
        "outfit_reference", "first_frame", "last_frame",
    },
    "video": {"camera_motion", "motion_style", "action_reference", "visual_effect", "shot_pacing"},
    "audio": {"audio_bgm", "audio_voice", "audio_sfx", "beat_reference", "lip_sync_source", "sfx_layer"},
}


def _require_confirmed_reference_manifest_for_paid_render(request: AutonomousGenerateRequest) -> None:
    """Block paid autonomous renders when uploaded refs have unconfirmed jobs."""
    expected_refs: list[tuple[str, str]] = [
        *[("image", url) for url in request.reference_image_urls],
        *[("video", url) for url in request.reference_video_urls],
        *[("audio", url) for url in request.reference_audio_urls],
    ]
    expected_refs = [(kind, str(url or "").strip()) for kind, url in expected_refs if str(url or "").strip()]
    if not expected_refs:
        return

    manifest = request.reference_manifest if isinstance(request.reference_manifest, dict) else {}
    items = manifest.get("items") or []
    if not isinstance(items, list) or not bool(manifest.get("confirmed")):
        raise HTTPException(
            422,
            {
                "code": "reference_manifest_confirmation_required",
                "message": "Confirm every uploaded reference role before paid autonomous render.",
                "expected_references": len(expected_refs),
            },
        )

    confirmed_by_url: dict[tuple[str, str], dict[str, Any]] = {}
    for item in items[:12]:
        if not isinstance(item, dict) or not item.get("role_confirmed"):
            continue
        kind = str(item.get("kind") or "").strip().lower()
        role = str(item.get("role") or "").strip().lower()
        url = str(item.get("url") or "").strip()
        if kind in _CONFIRMED_REFERENCE_ROLES and role in _CONFIRMED_REFERENCE_ROLES[kind] and url:
            confirmed_by_url[(kind, url)] = item

    missing = [
        {"kind": kind, "url": url[:160]}
        for kind, url in expected_refs
        if (kind, url) not in confirmed_by_url
    ]
    if missing:
        raise HTTPException(
            422,
            {
                "code": "reference_manifest_mismatch",
                "message": "Uploaded references do not match confirmed reference manifest. Re-confirm roles before render.",
                "missing": missing[:12],
            },
        )


def _resolve_pinned_asset_refs(
    *,
    reference_image_urls: list[str],
    pinned_asset_ids: list[str],
    auto_selected_pin_ids: Optional[list[str]] = None,
    max_images: int = 9,
) -> dict[str, Any]:
    """Append approved pinned asset images to the reference pool.

    Seedance 2.0 Reference-to-Video accepts up to 9 image refs. Pins are
    explicit approvals, but they still must respect that vendor cap.
    """
    auto_selected_set = set(auto_selected_pin_ids or [])
    if not pinned_asset_ids:
        return {
            "reference_image_urls": reference_image_urls,
            "pinned_assets": [],
            "skipped_pins": [],
        }
    from core import autonomous_asset_pins

    out_urls = list(reference_image_urls)
    pinned_assets: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen_urls = set(out_urls)
    seen_pin_ids: set[str] = set()

    for pin_id in pinned_asset_ids:
        if pin_id in seen_pin_ids:
            continue
        seen_pin_ids.add(pin_id)
        pin = autonomous_asset_pins.get_pin(pin_id)
        if not pin:
            skipped.append({"pin_id": pin_id, "reason": "pin_not_found"})
            continue
        if pin.get("status") != "active":
            skipped.append({"pin_id": pin_id, "reason": f"pin_status_{pin.get('status')}"})
            continue
        asset = pin.get("asset") or {}
        image_url = str(asset.get("image_url") or "")
        if not image_url:
            skipped.append({"pin_id": pin_id, "reason": "asset_missing_image_url"})
            continue
        if image_url in seen_urls:
            reference_index = out_urls.index(image_url)
        elif len(out_urls) < max_images:
            reference_index = len(out_urls)
            out_urls.append(image_url)
            seen_urls.add(image_url)
        else:
            skipped.append({"pin_id": pin_id, "reason": "seedance_image_reference_cap"})
            continue
        pinned_assets.append({
            "pin_id": pin_id,
            "asset_id": asset.get("id"),
            "asset_type": asset.get("type"),
            "name": asset.get("name"),
            "image_url": image_url,
            "role": pin.get("role"),
            "target_market": pin.get("target_market"),
            "niche": pin.get("niche"),
            "series_key": pin.get("series_key"),
            "priority": pin.get("priority"),
            "reference_index": reference_index,
            "injection_source": "auto" if pin_id in auto_selected_set else "explicit",
        })
    return {
        "reference_image_urls": out_urls,
        "pinned_assets": pinned_assets,
        "skipped_pins": skipped,
    }


class BenchmarkResultCreateRequest(BaseModel):
    case_id: str = Field(..., min_length=3, max_length=120)
    niche: str = Field(..., min_length=2, max_length=80)
    target_market: str = Field("auto", max_length=40)
    runtime_class: str = Field(..., min_length=3, max_length=40)
    model_key: str = Field(..., min_length=3, max_length=120)
    status: str = Field("planned", description="planned|running|passed|failed|needs_review")
    output_url: Optional[str] = Field(None, max_length=2000)
    cost_usd: Optional[float] = Field(None, ge=0)
    latency_s: Optional[float] = Field(None, ge=0)
    qa_score: Optional[float] = Field(None, ge=0, le=10)
    reviewer_decision: Optional[str] = Field(
        None,
        description="approved|rejected|needs_review|unknown",
    )
    evidence: dict[str, Any] = Field(default_factory=dict)
    review_scores: Optional[dict[str, float]] = Field(
        None,
        description="Optional rubric dimension scores. When provided, backend computes qa_score.",
    )
    review_hard_failures: list[str] = Field(default_factory=list)


class BenchmarkResultUpdateRequest(BaseModel):
    status: Optional[str] = Field(None, description="planned|running|passed|failed|needs_review")
    output_url: Optional[str] = Field(None, max_length=2000)
    cost_usd: Optional[float] = Field(None, ge=0)
    latency_s: Optional[float] = Field(None, ge=0)
    qa_score: Optional[float] = Field(None, ge=0, le=10)
    reviewer_decision: Optional[str] = Field(None)
    evidence: Optional[dict[str, Any]] = None
    review_scores: Optional[dict[str, float]] = None
    review_hard_failures: list[str] = Field(default_factory=list)


class BenchmarkRunRequest(BaseModel):
    case_ids: list[str] = Field(default_factory=list, max_length=50)
    niches: list[str] = Field(default_factory=list, max_length=50)
    model_key: Optional[str] = Field(None, max_length=120)
    mode: str = Field("dry_run", description="dry_run|stub_evidence")
    limit: int = Field(5, ge=1, le=100)


class AutonomousProductionDecisionRequest(BaseModel):
    user_idea: str = Field(..., min_length=5, max_length=3000)
    target_market: str = Field("auto", max_length=40)
    target_platform: str = Field("tiktok", max_length=40)
    duration_hint_s: Optional[int] = Field(None, ge=4, le=1800)
    aspect_ratio: Optional[str] = Field(None, description="auto|9:16|16:9|1:1")
    niche_hint: Optional[str] = Field(None, max_length=80)
    speaker_count: int = Field(1, ge=1, le=4)
    reference_counts: dict[str, int] = Field(default_factory=dict)
    reference_image_urls: list[str] = Field(default_factory=list, max_length=9)
    reference_video_urls: list[str] = Field(default_factory=list, max_length=3)
    reference_audio_urls: list[str] = Field(default_factory=list, max_length=3)
    reference_manifest: dict[str, Any] = Field(default_factory=dict)
    allow_expensive_reasoning: bool = Field(
        False,
        description="Cost guard: when false, Pro is only surfaced as an upgrade candidate.",
    )
    allow_premium_brain: bool = Field(
        False,
        description="Cost guard: when false, premium Claude brain is locked.",
    )

    @field_validator("reference_image_urls")
    @classmethod
    def _validate_preflight_reference_images(cls, v: list[str]) -> list[str]:
        return _validate_reference_images(v)

    @field_validator("aspect_ratio")
    @classmethod
    def _validate_preflight_aspect_ratio(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_aspect_ratio(v)


class ConversationalPreflightRequest(BaseModel):
    user_idea: str = Field(..., min_length=5, max_length=3000)
    target_market: str = Field("auto", max_length=40)
    target_platform: str = Field("tiktok", max_length=40)
    duration_hint_s: Optional[int] = Field(None, ge=4, le=1800)
    aspect_ratio: Optional[str] = Field(None, description="auto|9:16|16:9|1:1")
    speaker_count: int = Field(1, ge=1, le=4)
    reference_counts: dict[str, int] = Field(default_factory=dict)
    reference_image_urls: list[str] = Field(default_factory=list, max_length=9)
    reference_video_urls: list[str] = Field(default_factory=list, max_length=3)
    reference_audio_urls: list[str] = Field(default_factory=list, max_length=3)
    reference_manifest: dict[str, Any] = Field(default_factory=dict)
    approved: bool = False
    edited_brief: Optional[str] = Field(None, max_length=3000)
    revision_notes: Optional[str] = Field(None, max_length=1200)
    conversation_messages: list[dict[str, Any]] = Field(default_factory=list, max_length=20)

    @field_validator("reference_image_urls")
    @classmethod
    def _validate_conversation_reference_images(cls, v: list[str]) -> list[str]:
        return _validate_reference_images(v)

    @field_validator("aspect_ratio")
    @classmethod
    def _validate_conversation_aspect_ratio(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_aspect_ratio(v)


class ProductIntelligenceRequest(BaseModel):
    url: str = Field(..., min_length=4, max_length=2000)
    user_idea: str = Field("", max_length=3000)


class DeepPreflightRequest(AutonomousProductionDecisionRequest):
    allow_live_llm: bool = Field(
        False,
        description="Opt-in only: true lets the endpoint call the low-cost text LLM.",
    )
    allow_vision_llm: bool = Field(
        False,
        description="Opt-in only: true lets the endpoint call vision LLM for image role suggestions.",
    )
    product_context: dict[str, Any] = Field(default_factory=dict)


class GraphExecutionClaimRequest(BaseModel):
    worker_id: str = Field("autonomous_executor", max_length=120)
    limit: int = Field(4, ge=1, le=25)
    lease_ttl_s: int = Field(900, ge=30, le=7200)


class GraphTaskResultRequest(BaseModel):
    outcome: str = Field(..., description="success|passed|warn|accepted|failed|retry_failed|completed")
    lease_id: Optional[str] = Field(None, max_length=120)
    worker_id: Optional[str] = Field(None, max_length=120)
    payload_patch: dict[str, Any] = Field(default_factory=dict)


class GraphExecutorRunOnceRequest(BaseModel):
    worker_id: str = Field("autonomous_graph_executor", max_length=120)
    limit: int = Field(1, ge=1, le=25)
    lease_ttl_s: int = Field(900, ge=30, le=7200)
    preview: bool = Field(True, description="Preview next executable batch without leasing or mutating graph state.")
    allow_metadata_stub: bool = Field(
        False,
        description="Use non-vendor stub handlers for local smoke tests. Never produces real video.",
    )


class GraphExecutorLoopRequest(BaseModel):
    worker_id: str = Field("autonomous_graph_executor", max_length=120)
    limit: int = Field(1, ge=1, le=25)
    lease_ttl_s: int = Field(900, ge=30, le=7200)
    max_cycles: int = Field(100, ge=1, le=1000)
    run_background: bool = Field(True, description="Spawn the loop in the Director background task supervisor.")
    allow_metadata_stub: bool = Field(False, description="Run non-vendor stub handlers for local smoke tests.")
    allow_paid_handlers: bool = Field(False, description="Trusted-only: use video_worker handlers that may call AtlasCloud.")


def _apply_benchmark_review_scores(
    payload: dict[str, Any],
    *,
    existing: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Compute qa_score from benchmark review rubric when dimension scores exist."""
    payload = dict(payload)
    review_scores = payload.pop("review_scores", None)
    hard_failures = payload.pop("review_hard_failures", None) or []
    if not review_scores:
        return payload

    from agent.benchmark_review_rubric import (
        build_benchmark_review_rubric,
        score_benchmark_review,
    )

    context = {**(existing or {}), **payload}
    evidence = dict(context.get("evidence") or {})
    has_dialogue = bool(
        context.get("has_dialogue")
        or evidence.get("has_dialogue")
        or "dialogue" in str(evidence.get("audio_report") or "").lower()
        or "voice" in str(evidence.get("audio_report") or "").lower()
    )
    rubric = build_benchmark_review_rubric(
        niche=str(context.get("niche") or "ugc_review"),
        runtime_class=str(context.get("runtime_class") or "short"),
        target_market=str(context.get("target_market") or "auto"),
        has_dialogue=has_dialogue,
    )
    review_score = score_benchmark_review(
        rubric=rubric,
        dimension_scores={str(k): float(v) for k, v in review_scores.items()},
        hard_failures=[str(item) for item in hard_failures],
    )
    next_evidence = dict(payload.get("evidence") or {})
    next_evidence.update({
        "benchmark_review_rubric": rubric,
        "benchmark_review_score": review_score,
    })
    payload["evidence"] = next_evidence
    payload["qa_score"] = review_score["weighted_score"]
    if not payload.get("reviewer_decision"):
        payload["reviewer_decision"] = review_score["recommended_reviewer_decision"]
    return payload


@router.get("/autonomous/capabilities")
async def autonomous_capabilities():
    """Return current autonomous niche/runtime/model readiness matrix."""
    from skills.niche_readiness import build_niche_readiness_matrix

    return build_niche_readiness_matrix()


@router.get("/autonomous/capability-matrix")
async def autonomous_capability_matrix():
    """Return detailed runtime x niche capability guidance for autonomous routing."""
    from agent.autonomous_capability_matrix import build_autonomous_capability_matrix

    return build_autonomous_capability_matrix()


@router.get("/autonomous/benchmarks")
async def autonomous_benchmarks():
    """Return the deterministic benchmark contract for autonomous quality."""
    from agent.autonomous_benchmark_suite import build_autonomous_benchmark_contract

    return build_autonomous_benchmark_contract()


@router.get("/autonomous/benchmarks/plan")
async def autonomous_benchmark_plan(
    focus: str = "launch",
    limit: int = 12,
):
    """Return prioritized benchmark work for route promotion."""
    from agent.autonomous_benchmark_planner import build_autonomous_benchmark_plan

    return build_autonomous_benchmark_plan(focus=focus, limit=limit)


@router.post("/autonomous/benchmarks/run")
async def run_autonomous_benchmarks(
    request: BenchmarkRunRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """Create benchmark evidence rows without calling vendors by default."""
    from agent.autonomous_benchmark_runner import run_autonomous_benchmark_batch

    _require_mutation_admin(x_admin_key)
    if (request.mode or "").strip().lower() == "stub_evidence":
        _require_dev_metadata_stub(x_admin_key)
    try:
        return run_autonomous_benchmark_batch(
            case_ids=request.case_ids,
            niches=request.niches,
            model_key=request.model_key,
            mode=request.mode,
            limit=request.limit,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/autonomous/benchmarks/results")
async def list_autonomous_benchmark_results(
    case_id: Optional[str] = None,
    niche: Optional[str] = None,
    model_key: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
):
    """List stored benchmark evidence rows."""
    from agent.benchmark_evidence_validator import validate_benchmark_result_evidence

    results = autonomous_benchmark_store.list_results(
        case_id=case_id,
        niche=niche,
        model_key=model_key,
        status=status,
        limit=limit,
    )
    return {
        "schema_version": "cinejelly.benchmark_results.v1",
        "stats": autonomous_benchmark_store.stats(),
        "results": [
            {**row, "evidence_validation": validate_benchmark_result_evidence(row)}
            for row in results
        ],
    }


@router.post("/autonomous/benchmarks/results")
async def create_autonomous_benchmark_result(
    request: BenchmarkResultCreateRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """Create one benchmark evidence row after a benchmark render or review."""
    from agent.benchmark_evidence_validator import validate_benchmark_result_evidence

    _require_mutation_admin(x_admin_key)
    try:
        payload = _apply_benchmark_review_scores(request.model_dump())
        row = autonomous_benchmark_store.create_result(**payload)
        return {**row, "evidence_validation": validate_benchmark_result_evidence(row)}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/autonomous/benchmarks/results/{result_id}")
async def get_autonomous_benchmark_result(result_id: str):
    """Get one benchmark evidence row by id."""
    from agent.benchmark_evidence_validator import validate_benchmark_result_evidence

    result = autonomous_benchmark_store.get_result(result_id)
    if not result:
        raise HTTPException(404, f"benchmark result '{result_id}' not found")
    return {**result, "evidence_validation": validate_benchmark_result_evidence(result)}


@router.patch("/autonomous/benchmarks/results/{result_id}")
async def update_autonomous_benchmark_result(
    result_id: str,
    request: BenchmarkResultUpdateRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """Patch one benchmark evidence row."""
    from agent.benchmark_evidence_validator import validate_benchmark_result_evidence

    _require_mutation_admin(x_admin_key)
    existing = autonomous_benchmark_store.get_result(result_id)
    if not existing:
        raise HTTPException(404, f"benchmark result '{result_id}' not found")
    try:
        patch = _apply_benchmark_review_scores(
            request.model_dump(exclude_unset=True),
            existing=existing,
        )
        result = autonomous_benchmark_store.update_result(
            result_id,
            **patch,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if not result:
        raise HTTPException(404, f"benchmark result '{result_id}' not found")
    return {**result, "evidence_validation": validate_benchmark_result_evidence(result)}


@router.delete("/autonomous/benchmarks/results/{result_id}")
async def delete_autonomous_benchmark_result(
    result_id: str,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """Delete one benchmark evidence row."""
    _require_mutation_admin(x_admin_key)
    deleted = autonomous_benchmark_store.delete_result(result_id)
    if not deleted:
        raise HTTPException(404, f"benchmark result '{result_id}' not found")
    return {"deleted": True, "id": result_id}


@router.post("/autonomous/benchmarks/results/from-job/{job_id}")
async def create_autonomous_benchmark_result_from_job(
    job_id: str,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """Create a needs-review benchmark row from a rendered autonomous job.

    The generated evidence draft only contains fields proven by the saved
    artifact/job record. Missing QA/reviewer evidence keeps promotion locked.
    """
    from agent.benchmark_evidence_pack_builder import build_benchmark_result_draft_from_artifact
    from agent.benchmark_evidence_validator import validate_benchmark_result_evidence

    _require_mutation_admin(x_admin_key)
    snapshot = production_artifacts.load_snapshot(job_id)
    if not snapshot:
        raise HTTPException(404, f"artifact for job '{job_id}' not found")
    job_record = _JOBS_STORE.get(job_id, {})
    draft = build_benchmark_result_draft_from_artifact(snapshot, job_record={**job_record, "job_id": job_id})
    try:
        row = autonomous_benchmark_store.create_result(
            case_id=draft["case_id"],
            niche=draft["niche"],
            target_market=draft["target_market"],
            runtime_class=draft["runtime_class"],
            model_key=draft["model_key"],
            status=draft["status"],
            output_url=draft.get("output_url"),
            cost_usd=draft.get("cost_usd"),
            latency_s=draft.get("latency_s"),
            qa_score=draft.get("qa_score"),
            reviewer_decision=draft.get("reviewer_decision"),
            evidence={
                **(draft.get("evidence") or {}),
                "artifact_evidence_pack": draft.get("evidence_pack"),
            },
        )
        return {**row, "evidence_validation": validate_benchmark_result_evidence(row)}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/autonomous/workflow")
async def autonomous_workflow():
    """Return the structured workflow contract for autonomous inspection."""
    from agent.autonomous_workflow_contract import build_autonomous_workflow_contract

    return build_autonomous_workflow_contract()


@router.get("/autonomous/readiness")
async def autonomous_readiness():
    """Return source-backed readiness verdict for autonomous production quality."""
    from agent.autonomous_readiness_report import build_autonomous_readiness_report

    return build_autonomous_readiness_report()


@router.get("/autonomous/recommendations")
async def autonomous_recommendations():
    """Return source-backed upgrade recommendations for top-tier autonomous video."""
    from agent.autonomous_upgrade_recommendations import build_autonomous_upgrade_recommendations

    return build_autonomous_upgrade_recommendations()


@router.get("/autonomous/research")
async def autonomous_research():
    """Return curated external research mapped to current source gaps."""
    from agent.autonomous_competitive_research import build_autonomous_competitive_research

    return build_autonomous_competitive_research()


@router.get("/autonomous/niche-launch-matrix")
async def autonomous_niche_launch_matrix():
    """Return launch tiers, duration envelope, and proof gates by niche."""
    from agent.autonomous_niche_launch_matrix import build_autonomous_niche_launch_matrix

    return build_autonomous_niche_launch_matrix()


@router.get("/autonomous/atlas-model-matrix")
async def autonomous_atlas_model_matrix():
    """Return internal AtlasCloud model lanes and benchmark promotion gates."""
    from agent.atlas_model_integration_matrix import build_atlas_model_integration_matrix

    return build_atlas_model_integration_matrix()


@router.get("/autonomous/niche-playbook-catalog")
async def autonomous_niche_playbook_catalog():
    """Return production playbooks for all autonomous niches and durations."""
    from agent.autonomous_niche_playbook_catalog import build_autonomous_niche_playbook_catalog

    return build_autonomous_niche_playbook_catalog()


@router.get("/autonomous/niche-audit")
async def autonomous_niche_audit(
    include_long_form: bool = True,
    limit: int = 40,
):
    """Return all-niche source-backed routing audit without vendor calls."""
    from agent.autonomous_niche_audit import build_autonomous_niche_audit

    return build_autonomous_niche_audit(
        include_long_form=include_long_form,
        limit=limit,
    )


@router.get("/autonomous/market-audit")
async def autonomous_market_audit():
    """Return market/localization routing audit without vendor calls."""
    from agent.autonomous_market_audit import build_autonomous_market_audit

    return build_autonomous_market_audit()


@router.get("/autonomous/top-tier-completion-gate")
async def autonomous_top_tier_completion_gate():
    """Return strict top-app parity gate with evidence requirements."""
    from agent.autonomous_top_tier_completion_gate import build_autonomous_top_tier_completion_gate

    return build_autonomous_top_tier_completion_gate()


@router.get("/autonomous/paid-benchmark-manifest")
async def autonomous_paid_benchmark_manifest(
    focus: str = "sell_first",
    outputs_per_route: int = 2,
    limit: int = 18,
):
    """Return a concrete manifest for the next paid AtlasCloud benchmark batch."""
    from agent.autonomous_paid_benchmark_manifest import build_autonomous_paid_benchmark_manifest

    return build_autonomous_paid_benchmark_manifest(
        focus=focus,
        outputs_per_route=outputs_per_route,
        limit=limit,
    )


@router.get("/autonomous/phase3-prompt-route-audit")
async def autonomous_phase3_prompt_route_audit():
    """Return Phase 3 model/niche/prompt audit without vendor calls."""
    from agent.phase3_prompt_route_audit import build_phase3_prompt_route_audit

    return build_phase3_prompt_route_audit()


@router.get("/autonomous/phase4-completion-audit")
async def autonomous_phase4_completion_audit():
    """Return Phase 4 non-paid completion gate without vendor calls."""
    from agent.phase4_non_paid_completion_audit import build_phase4_non_paid_completion_audit

    return build_phase4_non_paid_completion_audit()


@router.get("/autonomous/benchmark-review-rubric")
async def autonomous_benchmark_review_rubric(
    niche: str = "ugc_review",
    runtime_class: str = "short",
    target_market: str = "auto",
    has_dialogue: bool = False,
):
    """Return human/model-backed scoring rubric for benchmark review."""
    from agent.benchmark_review_rubric import build_benchmark_review_rubric

    return build_benchmark_review_rubric(
        niche=niche,
        runtime_class=runtime_class,
        target_market=target_market,
        has_dialogue=has_dialogue,
    )


@router.get("/autonomous/production-audit")
async def autonomous_production_audit():
    """Return source-backed audit of workflow, niche fit, evidence gaps, and roadmap."""
    from agent.autonomous_production_audit import build_autonomous_production_audit

    return build_autonomous_production_audit()


@router.get("/autonomous/operator-brief")
async def autonomous_operator_brief():
    """Return concise source-backed answer for product/operator review."""
    from agent.autonomous_operator_brief import build_autonomous_operator_brief

    return build_autonomous_operator_brief()


@router.get("/autonomous/workflow-niche-guide")
async def autonomous_workflow_niche_guide():
    """Return source-backed workflow, niche, duration, and model route guide."""
    from agent.autonomous_workflow_niche_guide import build_autonomous_workflow_niche_guide

    return build_autonomous_workflow_niche_guide()


@router.post("/autonomous/product-intelligence")
async def autonomous_product_intelligence(request: ProductIntelligenceRequest):
    """Extract public product/page metadata without LLM or paid video calls."""
    from agent.product_intelligence import build_product_intelligence

    return await build_product_intelligence(url=request.url, user_idea=request.user_idea)


@router.post("/autonomous/deep-preflight")
async def autonomous_deep_preflight(request: DeepPreflightRequest):
    """Opt-in deep preflight brain.

    Default mode is deterministic and vendor-free. Live LLM/Vision calls happen
    only when the client explicitly sets allow_live_llm/allow_vision_llm.
    This endpoint never starts paid video rendering.
    """
    from agent.deep_preflight_brain import build_deep_preflight_brain

    return build_deep_preflight_brain(
        user_idea=request.user_idea,
        target_market=request.target_market,
        target_platform=request.target_platform,
        duration_hint_s=request.duration_hint_s,
        aspect_ratio=request.aspect_ratio,
        reference_counts=request.reference_counts,
        reference_image_urls=request.reference_image_urls,
        reference_video_urls=request.reference_video_urls,
        reference_audio_urls=request.reference_audio_urls,
        reference_manifest=request.reference_manifest,
        speaker_count=request.speaker_count,
        allow_live_llm=request.allow_live_llm,
        allow_vision_llm=request.allow_vision_llm,
        product_context=request.product_context,
    )


@router.post("/autonomous/production-decision")
async def autonomous_production_decision(request: AutonomousProductionDecisionRequest):
    """Return a vendor-free production strategy preview for an idea.

    This does not call LLMs and does not start rendering. It is meant for
    admin/UI inspection of niche, runtime, market, model route, dialogue lane,
    Seedance constraints, QA gates, and benchmark requirements before the
    paid `/autonomous` render path is invoked.
    """
    from agent.autonomous_production_decision import build_autonomous_production_decision

    return build_autonomous_production_decision(
        user_idea=request.user_idea,
        target_market=request.target_market,
        target_platform=request.target_platform,
        duration_hint_s=request.duration_hint_s,
        reference_counts=request.reference_counts,
        reference_image_urls=request.reference_image_urls,
        reference_video_urls=request.reference_video_urls,
        reference_audio_urls=request.reference_audio_urls,
        reference_manifest=request.reference_manifest,
        niche_hint=request.niche_hint,
        speaker_count=request.speaker_count,
        allow_expensive_reasoning=request.allow_expensive_reasoning,
        allow_premium_brain=request.allow_premium_brain,
    )


@router.post("/autonomous/llm-brain-policy")
async def autonomous_llm_brain_policy(request: AutonomousProductionDecisionRequest):
    """Return the Phase 1 low-cost LLM brain route without live LLM/video calls."""
    from agent.autonomous_production_decision import build_autonomous_production_decision

    decision = build_autonomous_production_decision(
        user_idea=request.user_idea,
        target_market=request.target_market,
        target_platform=request.target_platform,
        duration_hint_s=request.duration_hint_s,
        reference_counts=request.reference_counts,
        reference_image_urls=request.reference_image_urls,
        reference_video_urls=request.reference_video_urls,
        reference_audio_urls=request.reference_audio_urls,
        niche_hint=request.niche_hint,
        speaker_count=request.speaker_count,
        allow_expensive_reasoning=request.allow_expensive_reasoning,
        allow_premium_brain=request.allow_premium_brain,
    )
    return decision["llm_brain_policy"]


@router.post("/autonomous/creative-brief-contract")
async def autonomous_creative_brief_contract(request: AutonomousProductionDecisionRequest):
    """Return Phase 1 chat-input understanding without live LLM/video calls."""
    from agent.creative_brief_contract import build_creative_brief_contract

    return build_creative_brief_contract(
        user_idea=request.user_idea,
        target_market=request.target_market,
        target_platform=request.target_platform,
        duration_hint_s=request.duration_hint_s,
        reference_counts=request.reference_counts,
    )


@router.post("/autonomous/creative-producer-v2")
async def autonomous_creative_producer_v2(request: AutonomousProductionDecisionRequest):
    """Return Phase 2 producer angles, script beats, and shot graph without vendor calls."""
    from agent.autonomous_production_decision import build_autonomous_production_decision

    decision = build_autonomous_production_decision(
        user_idea=request.user_idea,
        target_market=request.target_market,
        target_platform=request.target_platform,
        duration_hint_s=request.duration_hint_s,
        reference_counts=request.reference_counts,
        reference_image_urls=request.reference_image_urls,
        reference_video_urls=request.reference_video_urls,
        reference_audio_urls=request.reference_audio_urls,
        niche_hint=request.niche_hint,
        speaker_count=request.speaker_count,
        allow_expensive_reasoning=request.allow_expensive_reasoning,
        allow_premium_brain=request.allow_premium_brain,
    )
    return decision["creative_producer_v2"]


@router.post("/autonomous/prompt-execution-contract")
async def autonomous_prompt_execution_contract(request: AutonomousProductionDecisionRequest):
    """Return Phase 3 per-shot prompt/model execution contract without vendor calls."""
    from agent.autonomous_production_decision import build_autonomous_production_decision

    decision = build_autonomous_production_decision(
        user_idea=request.user_idea,
        target_market=request.target_market,
        target_platform=request.target_platform,
        duration_hint_s=request.duration_hint_s,
        reference_counts=request.reference_counts,
        reference_image_urls=request.reference_image_urls,
        reference_video_urls=request.reference_video_urls,
        reference_audio_urls=request.reference_audio_urls,
        niche_hint=request.niche_hint,
        speaker_count=request.speaker_count,
        allow_expensive_reasoning=request.allow_expensive_reasoning,
        allow_premium_brain=request.allow_premium_brain,
    )
    return decision["prompt_execution_contract_v3"]


@router.post("/autonomous/viral-creative-brain")
async def autonomous_viral_creative_brain(request: AutonomousProductionDecisionRequest):
    """Return Phase 4A viral hooks, retention plan, and packaging without vendor calls."""
    from agent.autonomous_production_decision import build_autonomous_production_decision

    decision = build_autonomous_production_decision(
        user_idea=request.user_idea,
        target_market=request.target_market,
        target_platform=request.target_platform,
        duration_hint_s=request.duration_hint_s,
        reference_counts=request.reference_counts,
        reference_image_urls=request.reference_image_urls,
        reference_video_urls=request.reference_video_urls,
        reference_audio_urls=request.reference_audio_urls,
        niche_hint=request.niche_hint,
        speaker_count=request.speaker_count,
        allow_expensive_reasoning=request.allow_expensive_reasoning,
        allow_premium_brain=request.allow_premium_brain,
    )
    return decision["viral_creative_brain"]


@router.post("/autonomous/output-qa-retry-brain")
async def autonomous_output_qa_retry_brain(request: AutonomousProductionDecisionRequest):
    """Return Phase 4B output QA and retry contract without vendor calls."""
    from agent.autonomous_production_decision import build_autonomous_production_decision

    decision = build_autonomous_production_decision(
        user_idea=request.user_idea,
        target_market=request.target_market,
        target_platform=request.target_platform,
        duration_hint_s=request.duration_hint_s,
        reference_counts=request.reference_counts,
        reference_image_urls=request.reference_image_urls,
        reference_video_urls=request.reference_video_urls,
        reference_audio_urls=request.reference_audio_urls,
        niche_hint=request.niche_hint,
        speaker_count=request.speaker_count,
        allow_expensive_reasoning=request.allow_expensive_reasoning,
        allow_premium_brain=request.allow_premium_brain,
    )
    return decision["output_qa_retry_brain"]


@router.post("/autonomous/conversation/preflight")
async def autonomous_conversational_preflight(request: ConversationalPreflightRequest):
    """Return chat-style preflight: ask, draft, approve, then render."""
    from agent.conversational_preflight import build_conversational_preflight

    return build_conversational_preflight(
        user_idea=request.user_idea,
        target_market=request.target_market,
        target_platform=request.target_platform,
        duration_hint_s=request.duration_hint_s,
        aspect_ratio=request.aspect_ratio,
        reference_counts=request.reference_counts,
        reference_image_urls=request.reference_image_urls,
        reference_video_urls=request.reference_video_urls,
        reference_audio_urls=request.reference_audio_urls,
        reference_manifest=request.reference_manifest,
        speaker_count=request.speaker_count,
        approved=request.approved,
        edited_brief=request.edited_brief,
        revision_notes=request.revision_notes,
        conversation_messages=request.conversation_messages,
    )


def _build_autonomous_seedance_execution_bundle(
    *,
    request: AutonomousGenerateRequest,
    reference_image_urls: list[str],
    pinned_refs: dict[str, Any],
    pre_decision: dict[str, Any],
    production_decision: dict[str, Any],
    approved_plan_meta: dict[str, Any],
) -> dict[str, Any]:
    """Build the canonical autonomous paid-render bundle for Seedance.

    This is the production migration boundary: `/director/autonomous` no longer
    builds a legacy DirectorPlan for paid render. It compiles typed pipeline
    contracts, creates an ApprovalLock, verifies it immediately, and returns the
    exact SeedanceExecutionPlan that RenderExecutor will verify again.
    """
    from pipeline.adapters import build_input_contract_from_legacy_request
    from pipeline.approval_lock import ApprovalLock
    from pipeline.creative_planning import CreativePlanner
    from pipeline.input_analysis import InputAnalyzer
    from pipeline.storyboard_generation import StoryboardGenerator
    from pipeline.trace import PipelineTrace
    from seedance.example_retriever import ExampleRetriever
    from seedance.prompt_compiler import SeedancePromptCompiler
    from workers.cost_control import CostControlService
    from commercial import commercial_store
    from commercial.commercial_overrides import (
        apply_commercial_context_to_creative_plan,
        apply_commercial_context_to_execution_plan,
    )

    input_contract = build_input_contract_from_legacy_request(
        user_idea=request.user_idea,
        target_platform=request.target_platform,
        target_market=request.target_market,
        duration_hint_s=request.duration_hint_s,
        aspect_ratio=request.aspect_ratio,
        resolution=request.resolution,
        reference_image_urls=reference_image_urls,
        reference_video_urls=request.reference_video_urls,
        reference_audio_urls=request.reference_audio_urls,
        reference_manifest=request.reference_manifest,
        settings={
            "model": request.user_model,
            "resolution": request.resolution,
            "dry_run_only": request.dry_run_only,
            "max_total_cost_usd": request.max_total_cost_usd,
        },
        metadata={
            "approved_plan": approved_plan_meta,
            "pinned_assets": pinned_refs.get("pinned_assets") or [],
            "auto_pin_selection_enabled": bool(request.auto_select_asset_pins),
        },
    )
    trace = PipelineTrace(input_id=input_contract.input_id)
    trace.append_stage(
        stage="input_contract",
        stage_input=request.model_dump(mode="json"),
        stage_output=input_contract,
        decision="normalized autonomous request into InputContract",
        reasoning_summary="Legacy request arrays and confirmed reference manifest were converted into typed AssetRef records.",
        rules_applied=["phase0.contracts.input_contract", "phase0.adapters.legacy_reference_manifest"],
    )

    analyzed_input = InputAnalyzer().analyze(input_contract)
    trace.append_stage(
        stage="input_analysis",
        stage_input=input_contract,
        stage_output=analyzed_input,
        decision=f"detected niche={analyzed_input.detected_niche}",
        reasoning_summary="Deterministic analyzer scored niche keywords, duration, reference sufficiency, and primary risks.",
        rules_applied=list(analyzed_input.metadata.get("analysis_rules") or []),
        warnings=list(analyzed_input.warnings),
    )

    requested_duration_s = int(analyzed_input.duration_s or request.duration_hint_s or 8)
    if requested_duration_s > 60:
        raise HTTPException(
            422,
            {
                "code": "autonomous_duration_too_long",
                "message": "Long-form autonomous production currently supports 30-60 seconds. Use 60s or shorter for the production path.",
                "strategy": "phase10_fail_safe_duration_cap",
                "requested_duration_s": requested_duration_s,
                "max_long_form_duration_s": 60,
                "pipeline_trace": trace.model_dump(mode="json"),
            },
        )
    if 15 < requested_duration_s < 30:
        raise HTTPException(
            422,
            {
                "code": "autonomous_duration_gap_not_supported",
                "message": "Choose 15s or shorter for a single Seedance clip, or 30-60s for long-form segmented production.",
                "strategy": "phase10_short_or_long_form_only",
                "requested_duration_s": requested_duration_s,
                "short_form_max_duration_s": 15,
                "long_form_min_duration_s": 30,
            },
        )
    is_longform = requested_duration_s > 15

    creative_plan = CreativePlanner().plan(analyzed_input)
    brand_kit = commercial_store.load_brand_kit(request.brand_kit_id)
    template = commercial_store.load_template(request.template_id)
    if request.brand_kit_id and brand_kit is None:
        raise HTTPException(422, {"code": "brand_kit_not_found", "message": "The requested Brand Kit was not found."})
    if request.template_id and template is None:
        raise HTTPException(422, {"code": "template_not_found", "message": "The requested commercial template was not found."})
    creative_metadata = {
        **creative_plan.metadata,
        "model": None if request.user_model == "auto" else request.user_model,
        "requested_model": request.user_model,
        "resolution": request.resolution,
        "pre_decision": {
            "niche": (pre_decision.get("decision") or {}).get("niche"),
            "target_market": (pre_decision.get("decision") or {}).get("target_market"),
        },
        "production_decision": {
            "niche": (production_decision.get("decision") or {}).get("niche"),
            "primary_model_route": (production_decision.get("decision") or {}).get("primary_model_route"),
        },
    }
    creative_plan = creative_plan.model_copy(update={"metadata": creative_metadata})
    creative_plan = apply_commercial_context_to_creative_plan(
        creative_plan,
        brand_kit=brand_kit,
        template=template,
    )
    if brand_kit is not None or template is not None:
        trace.append_stage(
            stage="commercial_context",
            stage_input={
                "brand_kit_id": request.brand_kit_id,
                "template_id": request.template_id,
                "user_id": request.user_id,
            },
            stage_output={
                "brand_kit": brand_kit.model_dump(mode="json") if brand_kit is not None else None,
                "template": template.model_dump(mode="json") if template is not None else None,
            },
            decision="applied commercial Brand Kit and/or template",
            reasoning_summary="Commercial context overrides creative style, hook/template structure, prompt constraints, and downstream render metadata.",
            rules_applied=["phase13.commercial.brand_template_override"],
        )
    identity_bible_payload = creative_plan.metadata.get("identity_bible") or {}
    consistency_score_payload = creative_plan.metadata.get("consistency_score") or {}
    baseline_consistency_score_payload = creative_plan.metadata.get("baseline_consistency_score") or {}
    consistency_policy_payload = creative_plan.metadata.get("consistency_policy") or {}
    if isinstance(identity_bible_payload, dict) and isinstance(consistency_score_payload, dict):
        trace.append_stage(
            stage="identity_consistency",
            stage_input=analyzed_input,
            stage_output={
                "identity_bible": identity_bible_payload,
                "baseline_consistency_score": baseline_consistency_score_payload,
                "consistency_score": consistency_score_payload,
                "consistency_delta": creative_plan.metadata.get("consistency_delta"),
                "consistency_policy": consistency_policy_payload,
            },
            decision=(
                f"consistency score={consistency_score_payload.get('overall_score')} "
                f"policy={consistency_policy_payload.get('action')}"
            ),
            reasoning_summary="IdentityBibleBuilder and ConsistencyScorer converted references and intent into character, product, style, and emotion constraints before paid render.",
            rules_applied=list(identity_bible_payload.get("rules_applied") or [])
            + list(consistency_score_payload.get("rules_applied") or [])
            + list(consistency_policy_payload.get("rules_applied") or []),
            warnings=list(identity_bible_payload.get("warnings") or [])
            + list(consistency_score_payload.get("risk_flags") or [])
            + list(consistency_policy_payload.get("reason_ids") or []),
        )
    creative_strategy_payload = creative_plan.metadata.get("creative_strategy") or {}
    if isinstance(creative_strategy_payload, dict):
        selected_strategy = creative_strategy_payload.get("selected_strategy") or {}
        selected_strategy_id = (
            selected_strategy.get("strategy_id")
            if isinstance(selected_strategy, dict)
            else None
        )
        trace.append_stage(
            stage="creative_reasoning",
            stage_input={
                "analysis_id": analyzed_input.analysis_id,
                "consistency_score": consistency_score_payload,
            },
            stage_output=creative_strategy_payload,
            decision=f"selected strategy={selected_strategy_id}",
            reasoning_summary=str(creative_strategy_payload.get("reasoning_summary") or ""),
            rules_applied=list(creative_strategy_payload.get("rules_applied") or []),
            warnings=list(creative_strategy_payload.get("warnings") or []),
            model_route={
                "reasoning_mode": creative_strategy_payload.get("reasoning_mode"),
                "llm_selector_configured": False,
                "llm_policy_result": creative_strategy_payload.get("llm_policy_result"),
                "candidate_rankings": (
                    (creative_strategy_payload.get("decision_factors") or {}).get("candidate_rankings")
                    if isinstance(creative_strategy_payload.get("decision_factors"), dict)
                    else None
                ),
            },
        )
    trace.append_stage(
        stage="creative_planning",
        stage_input=analyzed_input,
        stage_output=creative_plan,
        decision=f"{creative_plan.metadata.get('shot_mode')} with {creative_plan.shot_count} shot(s)",
        reasoning_summary="CreativePlanner selected shot mode, reference strategy, consistency locks, and niche playbook.",
        rules_applied=list(creative_plan.metadata.get("planning_rules") or []),
    )

    storyboard = StoryboardGenerator().generate(creative_plan, analyzed_input)
    trace.append_stage(
        stage="storyboard_generation",
        stage_input=creative_plan,
        stage_output=storyboard,
        decision=f"generated {len(storyboard.scenes)} storyboard scene(s)",
        reasoning_summary="StoryboardGenerator produced typed scenes with beat, action, camera, spatial change, audio intent, references, and continuity notes.",
        rules_applied=list(storyboard.metadata.get("rules_applied") or []),
    )

    example_tags = []
    if creative_plan.consistency_plan.get("product_lock"):
        example_tags.append("product_lock")
    if creative_plan.consistency_plan.get("character_lock"):
        example_tags.append("character_lock")
    examples = ExampleRetriever.from_jsonl().retrieve(
        niche=creative_plan.target_niche,
        asset_mode=str(creative_plan.metadata.get("asset_mode") or "unknown"),
        shot_count=creative_plan.shot_count,
        duration_s=creative_plan.duration_s,
        continuity_tags=example_tags,
        limit=4,
    )
    example_ids = [example.example_id for example in examples]

    rules_applied = _dedupe_strings(
        list(analyzed_input.metadata.get("analysis_rules") or [])
        + list(creative_plan.metadata.get("planning_rules") or [])
        + list(storyboard.metadata.get("rules_applied") or [])
        + ["phase3.render.approval_lock_enforced", "phase3.render.render_executor_required"]
    )
    longform_plan = None
    if is_longform:
        from longform.longform_planner import LongFormPlanner
        from longform.segment_prompt_compiler import SegmentPromptCompiler

        rules_applied = _dedupe_strings(rules_applied + [
            "phase9a.longform.segmented_orchestration",
            "phase10.longform.production_endpoint_enabled",
            "phase10.longform.final_assembly_required",
        ])
        longform_plan = LongFormPlanner().plan(
            creative_plan=creative_plan,
            analyzed_input=analyzed_input,
        ).model_copy(update={"source_storyboard_id": storyboard.storyboard_id})
        trace.append_stage(
            stage="longform_planning",
            stage_input=creative_plan,
            stage_output=longform_plan,
            decision=f"planned {len(longform_plan.segments)} long-form segment(s)",
            reasoning_summary="Phase 10 routes 30-60s requests through segmented Seedance orchestration instead of a single long render.",
            rules_applied=list(longform_plan.rules_applied),
            warnings=list(longform_plan.warnings),
        )
        longform_plan = SegmentPromptCompiler().compile(
            longform_plan=longform_plan,
            creative_plan=creative_plan,
            analyzed_input=analyzed_input,
        )
        if brand_kit is not None or template is not None:
            longform_plan = longform_plan.model_copy(update={
                "segments": [
                    segment.model_copy(update={
                        "seedance_execution_plan": apply_commercial_context_to_execution_plan(
                            segment.seedance_execution_plan,
                            brand_kit=brand_kit,
                            template=template,
                        ) if segment.seedance_execution_plan is not None else None,
                    })
                    for segment in longform_plan.segments
                ],
            })
        if longform_plan.master_execution_plan is None:
            raise HTTPException(500, "Long-form compiler did not produce a master SeedanceExecutionPlan.")
        execution_plan = longform_plan.master_execution_plan
        execution_plan = apply_commercial_context_to_execution_plan(
            execution_plan,
            brand_kit=brand_kit,
            template=template,
        )
        shots = [
            shot.model_copy(update={
                "rules_applied": _dedupe_strings(shot.rules_applied + rules_applied),
                "examples_used": _dedupe_strings(shot.examples_used + example_ids),
            })
            for shot in execution_plan.shots
        ]
        execution_plan = execution_plan.model_copy(update={
            "shots": shots,
            "reference_assets": input_contract.assets,
            "rules_applied": rules_applied,
            "examples_used": example_ids,
            "metadata": {
                **execution_plan.metadata,
                "approved_idea": request.user_idea,
                "input_contract_id": input_contract.input_id,
                "analysis_id": analyzed_input.analysis_id,
                "creative_plan_id": creative_plan.creative_plan_id,
                "storyboard_id": storyboard.storyboard_id,
                "approved_plan": approved_plan_meta,
                "commercial_user_id": request.user_id,
                "brand_kit_id": request.brand_kit_id,
                "template_id": request.template_id,
                "knowledge_rule_ids": rules_applied,
                "curated_example_ids": example_ids,
                "pipeline_migration": "director_autonomous_longform_segmented_execution_plan",
                "render_path": "long_form_segmented",
                "longform_plan_id": longform_plan.longform_plan_id,
                "segment_count": len(longform_plan.segments),
                "segment_ids": [segment.segment_id for segment in longform_plan.segments],
                "segment_graph_hash": longform_plan.segment_graph_hash,
                "continuity_bible_hash": longform_plan.continuity_bible.continuity_hash,
                "final_assembly_required": True,
            },
        })
        execution_plan = execution_plan.model_copy(update={
            "cost_estimate": CostControlService().estimate_plan_cost(execution_plan),
        })
        longform_plan = longform_plan.model_copy(update={
            "master_execution_plan": execution_plan,
            "rules_applied": rules_applied,
            "metadata": {
                **longform_plan.metadata,
                "phase10_production_enabled": True,
                "final_assembly_required": True,
                "approved_segment_ids": request.approved_segment_ids,
                "commercial_user_id": request.user_id,
                "brand_kit_id": request.brand_kit_id,
                "template_id": request.template_id,
            },
        })
        trace.append_stage(
            stage="longform_segment_compile",
            stage_input=longform_plan,
            stage_output=execution_plan,
            decision=f"compiled master long-form execution plan {execution_plan.execution_plan_id}",
            reasoning_summary="Every long-form segment remains a normal Seedance clip, while one master plan protects graph and continuity hashes.",
            rules_applied=rules_applied,
            examples_used=example_ids,
            model_route={"model": execution_plan.model, "segments": [shot.model for shot in execution_plan.shots]},
            cost_estimate=execution_plan.cost_estimate,
            warnings=list(execution_plan.linter_warnings) + list(longform_plan.warnings),
        )
    else:
        execution_plan = SeedancePromptCompiler().compile(creative_plan, storyboard, analyzed_input)
        execution_plan = apply_commercial_context_to_execution_plan(
            execution_plan,
            brand_kit=brand_kit,
            template=template,
        )
        shots = [
            shot.model_copy(update={
                "rules_applied": _dedupe_strings(shot.rules_applied + rules_applied),
                "examples_used": _dedupe_strings(shot.examples_used + example_ids),
            })
            for shot in execution_plan.shots
        ]
        execution_plan = execution_plan.model_copy(update={
            "shots": shots,
            "reference_assets": input_contract.assets,
            "rules_applied": rules_applied,
            "examples_used": example_ids,
            "metadata": {
                **execution_plan.metadata,
                "approved_idea": request.user_idea,
                "input_contract_id": input_contract.input_id,
                "analysis_id": analyzed_input.analysis_id,
                "creative_plan_id": creative_plan.creative_plan_id,
                "storyboard_id": storyboard.storyboard_id,
                "approved_plan": approved_plan_meta,
                "commercial_user_id": request.user_id,
                "brand_kit_id": request.brand_kit_id,
                "template_id": request.template_id,
                "knowledge_rule_ids": rules_applied,
                "curated_example_ids": example_ids,
                "pipeline_migration": "director_autonomous_seedance_execution_plan",
            },
        })
        cost_estimate = CostControlService().estimate_plan_cost(execution_plan)
        execution_plan = execution_plan.model_copy(update={"cost_estimate": cost_estimate})
        trace.append_stage(
            stage="seedance_prompt_compile",
            stage_input=storyboard,
            stage_output=execution_plan,
            decision=f"compiled SeedanceExecutionPlan {execution_plan.execution_plan_id}",
            reasoning_summary="SeedancePromptCompiler produced the only render plan allowed on the autonomous production path.",
            rules_applied=rules_applied,
            examples_used=example_ids,
            model_route={"model": execution_plan.model, "shots": [shot.model for shot in execution_plan.shots]},
            cost_estimate=cost_estimate,
            warnings=list(execution_plan.linter_warnings),
        )

    approval_lock = ApprovalLock.from_execution_plan(
        idea=request.user_idea,
        execution_plan=execution_plan,
        reference_assets=execution_plan.reference_assets,
        cost_estimate=execution_plan.cost_estimate,
        approved_by="studio_user",
        approval_source="longform_dry_run_preview" if is_longform else "prompt_preview",
        metadata={
            "approved_idea": request.user_idea,
            "approved_plan": approved_plan_meta,
            "render_path": "long_form_segmented" if is_longform else "short_form_seedance",
            "longform_plan_id": getattr(longform_plan, "longform_plan_id", None),
            "longform_dry_run_approved": bool(is_longform and (request.dry_run_only or request.approved_dry_run_job_id)),
            "approved_segment_ids": request.approved_segment_ids,
            "segment_graph_hash": execution_plan.metadata.get("segment_graph_hash"),
            "continuity_bible_hash": execution_plan.metadata.get("continuity_bible_hash"),
            "consistency_policy": execution_plan.metadata.get("consistency_policy"),
            "consistency_policy_action": execution_plan.metadata.get("consistency_policy_action"),
            "consistency_policy_reasons": execution_plan.metadata.get("consistency_policy_reasons") or [],
            "consistency_review_approved": bool(approved_plan_meta.get("consistency_review_approved")),
            "consistency_review_approved_policy_action": (
                execution_plan.metadata.get("consistency_policy_action")
                if approved_plan_meta.get("consistency_review_approved")
                else None
            ),
            "input_id": input_contract.input_id,
            "trace_id": trace.trace_id,
        },
    )
    approval_verification = approval_lock.verify_against(
        idea=request.user_idea,
        execution_plan=execution_plan,
        reference_assets=execution_plan.reference_assets,
        cost_estimate=execution_plan.cost_estimate,
    )
    trace.append_stage(
        stage="approval_lock",
        stage_input=execution_plan,
        stage_output=approval_verification,
        decision="approval lock verified" if approval_verification.valid else "approval lock rejected",
        reasoning_summary="ApprovalLock was created from the approved SeedanceExecutionPlan and verified before queueing any paid render.",
        rules_applied=["phase0.approval_lock.verify_against", "phase3.render.pre_vendor_lock"],
        warnings=approval_verification.mismatched_fields,
        cost_estimate=execution_plan.cost_estimate,
    )
    if not approval_verification.valid:
        raise HTTPException(
            422,
            {
                "code": "approval_lock_mismatch",
                "message": "ApprovalLock verification failed before render queueing.",
                "mismatched_fields": approval_verification.mismatched_fields,
            },
        )

    return {
        "input_contract": input_contract,
        "analyzed_input": analyzed_input,
        "creative_plan": creative_plan,
        "storyboard": storyboard,
        "execution_plan": execution_plan,
        "approval_lock": approval_lock,
        "approval_verification": approval_verification,
        "pipeline_trace": trace,
        "curated_examples": examples,
        "longform_plan": longform_plan,
        "render_path": "long_form_segmented" if is_longform else "short_form_seedance",
        "editor_preview": _build_seedance_editor_preview(
            request=request,
            creative_plan=creative_plan,
            storyboard=storyboard,
            execution_plan=execution_plan,
            production_decision=production_decision,
        ),
    }


def _dedupe_strings(values: list[Any]) -> list[str]:
    """Return non-empty strings in first-seen order."""
    return list(dict.fromkeys(str(value) for value in values if str(value).strip()))


def _charge_commercial_usage_for_render(
    *,
    request: AutonomousGenerateRequest,
    job_id: str,
    execution_plan: Any,
    render_path: str,
):
    """Deduct commercial credits for a paid autonomous render."""
    from commercial import commercial_store

    estimated_cost = float(
        (execution_plan.cost_estimate or {}).get("total_cost_usd")
        or (execution_plan.cost_estimate or {}).get("render_cost_usd")
        or 0.0
    )
    credits = commercial_store.credits_for_render(
        estimated_cost_usd=estimated_cost,
        duration_s=int(getattr(execution_plan, "duration_s", 0) or 0),
        segment_count=len(getattr(execution_plan, "shots", []) or []),
        is_longform=render_path == "long_form_segmented",
    )
    try:
        return commercial_store.charge_credits(
            user_id=request.user_id,
            job_id=job_id,
            credits=credits,
            estimated_cost_usd=estimated_cost,
            model=str(getattr(execution_plan, "model", "") or ""),
            segment_count=len(getattr(execution_plan, "shots", []) or []),
            render_path=render_path,
            metadata={
                "brand_id": request.brand_kit_id,
                "template_id": request.template_id,
                "duration_s": getattr(execution_plan, "duration_s", None),
            },
        )
    except ValueError as exc:
        raise HTTPException(
            402,
            {
                "code": "insufficient_credits",
                "message": str(exc),
                "required_credits": credits,
                "user_id": request.user_id,
            },
        ) from exc


def _longform_response_summary(longform_plan: Any | None) -> dict[str, Any] | None:
    """Return UI-safe long-form plan fields without duplicating full prompts."""
    if longform_plan is None:
        return None
    return {
        "longform_plan_id": getattr(longform_plan, "longform_plan_id", None),
        "total_duration_s": getattr(longform_plan, "total_duration_s", None),
        "status": getattr(longform_plan, "status", None),
        "segment_graph_hash": getattr(longform_plan, "segment_graph_hash", None),
        "continuity_bible_hash": getattr(getattr(longform_plan, "continuity_bible", None), "continuity_hash", None),
        "continuity_pressure": getattr(getattr(longform_plan, "continuity_bible", None), "continuity_pressure", None),
        "segments": [
            {
                "segment_id": segment.segment_id,
                "index": segment.index,
                "start_s": segment.start_s,
                "duration_s": segment.duration_s,
                "objective": segment.objective,
                "entry_state": segment.entry_state,
                "exit_state": segment.exit_state,
                "last_frame_anchor": segment.last_frame_anchor,
                "handoff_requirements": segment.handoff_requirements,
                "status": segment.status,
            }
            for segment in (getattr(longform_plan, "segments", None) or [])
        ],
        "handoffs": [
            handoff.model_dump(mode="json") if hasattr(handoff, "model_dump") else handoff
            for handoff in (getattr(longform_plan, "segment_graph", None) or [])
        ],
        "warnings": list(getattr(longform_plan, "warnings", None) or []),
    }


def _consistency_review_record_from_request(
    *,
    request: AutonomousGenerateRequest,
    action: str,
    segment_ids: list[str],
) -> dict[str, Any]:
    """Normalize human consistency review metadata for trace and ApprovalLock."""
    raw_decision = str(request.consistency_review_decision or "").strip().lower()
    if not raw_decision and request.consistency_review_approved:
        raw_decision = "approved"
    if raw_decision not in {"", "approved", "rejected"}:
        raw_decision = "rejected"
    reviewed_ids = [
        str(item).strip()
        for item in (request.consistency_reviewed_segment_ids or request.approved_segment_ids or segment_ids)
        if str(item).strip()
    ]
    return {
        "schema_version": "cineforge.consistency_review.v1",
        "decision": raw_decision or "not_submitted",
        "reason": str(request.consistency_review_reason or "").strip()[:1000],
        "policy_action": action or "allow",
        "reviewed_segment_ids": reviewed_ids,
        "segment_count": len(segment_ids),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _load_approved_longform_bundle(
    *,
    request: AutonomousGenerateRequest,
    approved_plan_meta: dict[str, Any],
    production_decision: dict[str, Any],
) -> dict[str, Any]:
    """Load the exact dry-run-approved long-form bundle for paid render."""
    from longform.contracts import LongFormExecutionPlan
    from pipeline.approval_lock import ApprovalLock
    from pipeline.contracts import AnalyzedInput, CreativePlan, InputContract, SeedanceExecutionPlan, StoryboardContract
    from pipeline.trace import PipelineTrace
    from seedance.contracts import CuratedExample

    dry_run_job_id = str(request.approved_dry_run_job_id or "").strip()
    if not dry_run_job_id:
        raise HTTPException(
            422,
            {
                "code": "long_form_dry_run_required",
                "message": "Long-form paid render requires an approved dry-run preview first.",
                "strategy": "dry_run_approve_then_paid_render",
            },
        )
    stored = _JOBS_STORE.get(dry_run_job_id)
    if not stored:
        raise HTTPException(
            422,
            {
                "code": "approved_dry_run_job_not_found",
                "message": "The approved long-form dry-run job was not found. Re-run the dry-run preview.",
                "approved_dry_run_job_id": dry_run_job_id,
            },
        )
    if stored.get("execution_mode") != "long_form_segmented":
        raise HTTPException(
            422,
            {
                "code": "approved_dry_run_job_wrong_mode",
                "message": "The approved dry-run job is not a long-form segmented plan.",
                "approved_dry_run_job_id": dry_run_job_id,
            },
        )
    meta = stored.get("autonomous_meta") or {}
    stored_approved = meta.get("approved_plan") or {}
    if stored_approved.get("source_hash") != approved_plan_meta.get("source_hash"):
        raise HTTPException(
            422,
            {
                "code": "approved_dry_run_source_hash_mismatch",
                "message": "The dry-run plan was approved for a different render source. Re-run dry-run after edits.",
                "approved_dry_run_job_id": dry_run_job_id,
            },
        )

    execution_plan = SeedanceExecutionPlan.model_validate(stored["seedance_execution_plan"])
    longform_plan = LongFormExecutionPlan.model_validate(stored["longform_plan"])
    approval_lock = ApprovalLock.model_validate(stored["approval_lock"])
    input_contract = InputContract.model_validate(stored["input_contract"])
    analyzed_input = AnalyzedInput.model_validate(stored["analyzed_input"])
    creative_plan = CreativePlan.model_validate(stored["creative_plan"])
    storyboard = StoryboardContract.model_validate(stored["storyboard"])
    pipeline_trace = PipelineTrace.model_validate(stored["pipeline_trace"])
    curated_examples = [
        CuratedExample.model_validate(item)
        for item in stored.get("curated_examples") or []
        if isinstance(item, dict)
    ]

    action = str(execution_plan.metadata.get("consistency_policy_action") or "").strip()
    consistency_review_record = _consistency_review_record_from_request(
        request=request,
        action=action,
        segment_ids=[segment.segment_id for segment in longform_plan.segments],
    )
    if action == "requires_review" and consistency_review_record["decision"] == "rejected":
        raise HTTPException(
            422,
            {
                "code": "consistency_review_rejected",
                "message": "The consistency review was rejected. Adjust references, segment plan, or prompts before paid render.",
                "consistency_policy_action": action,
                "consistency_policy_reasons": execution_plan.metadata.get("consistency_policy_reasons") or [],
                "review_reason": consistency_review_record.get("reason"),
                "approved_dry_run_job_id": dry_run_job_id,
            },
        )
    if action == "requires_review" and not request.consistency_review_approved:
        raise HTTPException(
            422,
            {
                "code": "consistency_review_required",
                "message": "This long-form plan requires explicit consistency review approval before paid render.",
                "consistency_policy_action": action,
                "consistency_policy_reasons": execution_plan.metadata.get("consistency_policy_reasons") or [],
                "approved_dry_run_job_id": dry_run_job_id,
            },
        )
    if action == "requires_review" and consistency_review_record["decision"] != "approved":
        raise HTTPException(
            422,
            {
                "code": "consistency_review_decision_required",
                "message": "Submit an approved consistency review decision before paid render.",
                "consistency_policy_action": action,
                "approved_dry_run_job_id": dry_run_job_id,
            },
        )
    if action == "requires_review" and not consistency_review_record.get("reason"):
        raise HTTPException(
            422,
            {
                "code": "consistency_review_reason_required",
                "message": "Enter a short reason for approving the consistency review before paid render.",
                "consistency_policy_action": action,
                "approved_dry_run_job_id": dry_run_job_id,
            },
        )
    approved_segment_ids = list(request.approved_segment_ids)
    if not approved_segment_ids:
        raise HTTPException(
            422,
            {
                "code": "long_form_segment_review_required",
                "message": "Approve the reviewed long-form segments before paid render.",
                "segment_ids": [segment.segment_id for segment in longform_plan.segments],
            },
        )
    missing_segments = [
        segment.segment_id
        for segment in longform_plan.segments
        if segment.segment_id not in approved_segment_ids
    ]
    if missing_segments:
        raise HTTPException(
            422,
            {
                "code": "long_form_segment_review_incomplete",
                "message": "Approve every long-form segment before paid render.",
                "missing_segment_ids": missing_segments,
            },
        )

    approval_lock = approval_lock.model_copy(update={
        "metadata": {
            **approval_lock.metadata,
            "longform_dry_run_approved": True,
            "approved_dry_run_job_id": dry_run_job_id,
            "approved_segment_ids": approved_segment_ids,
            "consistency_review_approved": bool(request.consistency_review_approved),
            "consistency_review_approved_policy_action": action if request.consistency_review_approved else None,
            "consistency_review": consistency_review_record if action == "requires_review" else None,
            "consistency_review_history": (
                list(approval_lock.metadata.get("consistency_review_history") or [])
                + ([consistency_review_record] if action == "requires_review" else [])
            )[-20:],
        }
    })
    verification = approval_lock.verify_against(
        idea=request.user_idea,
        execution_plan=execution_plan,
        reference_assets=execution_plan.reference_assets,
        cost_estimate=execution_plan.cost_estimate,
    )
    if not verification.valid:
        raise HTTPException(
            422,
            {
                "code": "approved_dry_run_lock_mismatch",
                "message": "The approved dry-run lock no longer matches this render request.",
                "mismatched_fields": verification.mismatched_fields,
            },
        )
    pipeline_trace.append_stage(
        stage="longform_approved_dry_run_loaded",
        stage_input={"approved_dry_run_job_id": dry_run_job_id},
        stage_output=verification,
        decision="loaded approved long-form dry-run bundle",
        reasoning_summary="Paid long-form render reuses the exact dry-run-approved master execution plan and ApprovalLock snapshot.",
        rules_applied=["phase10.longform.approved_dry_run_snapshot_required"],
        warnings=verification.mismatched_fields,
        cost_estimate=execution_plan.cost_estimate,
    )
    if action == "requires_review":
        pipeline_trace.append_stage(
            stage="consistency_review_approval",
            stage_input={
                "approved_dry_run_job_id": dry_run_job_id,
                "consistency_policy_action": action,
                "segment_ids": [segment.segment_id for segment in longform_plan.segments],
            },
            stage_output=consistency_review_record,
            decision=f"consistency review {consistency_review_record['decision']}",
            reasoning_summary="Human review approval is captured before paid long-form render for requires_review consistency policies.",
            rules_applied=["phase10.consistency_review.human_approval_required"],
            warnings=list(execution_plan.metadata.get("consistency_policy_reasons") or []),
            cost_estimate=execution_plan.cost_estimate,
        )
    return {
        "input_contract": input_contract,
        "analyzed_input": analyzed_input,
        "creative_plan": creative_plan,
        "storyboard": storyboard,
        "execution_plan": execution_plan,
        "approval_lock": approval_lock,
        "approval_verification": verification,
        "pipeline_trace": pipeline_trace,
        "curated_examples": curated_examples,
        "longform_plan": longform_plan,
        "render_path": "long_form_segmented",
        "editor_preview": meta.get("editor_preview") or _build_seedance_editor_preview(
            request=request,
            creative_plan=creative_plan,
            storyboard=storyboard,
            execution_plan=execution_plan,
            production_decision=production_decision,
        ),
    }


def _build_seedance_editor_preview(
    *,
    request: AutonomousGenerateRequest,
    creative_plan: Any,
    storyboard: Any,
    execution_plan: Any,
    production_decision: dict[str, Any],
) -> dict[str, Any]:
    """Create editor metadata from the new Seedance pipeline, without legacy director calls."""
    niche = str(getattr(creative_plan, "target_niche", "") or "video").replace("_", " ")
    hook = str(getattr(creative_plan, "hook_pattern", "") or "").strip()
    style = str(getattr(creative_plan, "style_direction", "") or "").strip()
    scenes = list(getattr(storyboard, "scenes", []) or [])
    first_beat = str(getattr(scenes[0], "beat", "") if scenes else "").strip()
    title_en = _preview_title_from_idea(request.user_idea, fallback=f"{niche.title()} concept")
    caption_core = first_beat or hook or title_en
    caption_en = _bounded_preview_text(
        f"{caption_core}. {style}" if style and style.lower() not in caption_core.lower() else caption_core,
        240,
    )
    target_market = str(
        (production_decision.get("decision") or {}).get("target_market")
        or request.target_market
        or "auto"
    ).lower()
    caption_vn = (
        _bounded_preview_text(f"{caption_core}. Ban dung da duoc khoa truoc khi render.", 240)
        if target_market in {"vn", "vi", "vietnam"}
        else caption_en
    )
    base_tags = _dedupe_strings([
        "CineForge",
        "AIvideo",
        niche.replace(" ", ""),
        str(request.target_platform or "").replace("_", ""),
        str(request.target_market or "").upper(),
        *list(getattr(execution_plan, "examples_used", []) or [])[:2],
    ])
    hashtags_en = [f"#{token}" for token in (_hashtag_token(tag) for tag in base_tags) if token][:8]
    hashtags_vn = list(hashtags_en) if target_market in {"vn", "vi", "vietnam"} else []
    distribution_package = {
        "source": "seedance_execution_plan_pipeline",
        "status": "generated",
        "title_en": title_en,
        "title_vn": title_en,
        "caption_en": caption_en,
        "caption_vn": caption_vn,
        "hashtags_en": hashtags_en,
        "hashtags_vn": hashtags_vn,
        "cover_frame_cue": first_beat or hook or "Use the strongest hero frame from shot 1.",
        "shot_count": len(getattr(execution_plan, "shots", []) or []),
        "duration_s": getattr(execution_plan, "duration_s", None),
        "knowledge_rule_ids": list(getattr(execution_plan, "rules_applied", []) or []),
        "curated_example_ids": list(getattr(execution_plan, "examples_used", []) or []),
    }
    return {
        "caption_vn": caption_vn,
        "caption_en": caption_en,
        "hashtags_vn": hashtags_vn,
        "hashtags_en": hashtags_en,
        "distribution_package": distribution_package,
        "disabled": False,
        "source": "seedance_execution_plan_pipeline",
    }


def _preview_title_from_idea(idea: str, *, fallback: str) -> str:
    """Return a compact editor title from the approved user idea."""
    cleaned = " ".join(str(idea or "").split())
    if not cleaned:
        return fallback
    return _bounded_preview_text(cleaned, 72)


def _bounded_preview_text(value: str, limit: int) -> str:
    """Clamp preview copy without splitting into an empty string."""
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _hashtag_token(value: str) -> str:
    """Normalize arbitrary metadata into a conservative hashtag token."""
    return "".join(ch for ch in str(value or "") if ch.isalnum())[:32]


@router.post("/autonomous")
async def autonomous_generate(
    request: AutonomousGenerateRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """Production autonomous endpoint using SeedanceExecutionPlan + ApprovalLock.

    Paid render on this route is allowed only through the Phase 3 safe path:
    SeedanceExecutionPlan -> ApprovalLock.verify_against() -> RenderExecutor.
    The legacy DirectorPlan renderer is intentionally not called here.
    """
    if idempotency_key:
        from core.idempotency import hash_body as _hash_body, lookup as _idem_lookup
        body_hash = _hash_body(request.model_dump())
        cached = _idem_lookup(idempotency_key, body_hash)
        if cached:
            if not cached["body_match"]:
                raise HTTPException(
                    409,
                    "Idempotency-Key da dung voi body khac. Doi key hoac doi 24h.",
                )
            logger.info(f"[/director/autonomous] Idempotency replay key={idempotency_key[:16]}...")
            return cached["response_json"]

    _require_confirmed_reference_manifest_for_paid_render(request)

    from agent.autonomous_production_decision import build_autonomous_production_decision

    pre_decision = build_autonomous_production_decision(
        user_idea=request.user_idea,
        target_market=request.target_market,
        target_platform=request.target_platform,
        duration_hint_s=request.duration_hint_s,
        reference_counts={
            "images": len(request.reference_image_urls),
            "videos": len(request.reference_video_urls),
            "audios": len(request.reference_audio_urls),
            "pinned_assets": len(request.pinned_asset_ids),
        },
        reference_image_urls=request.reference_image_urls,
        reference_video_urls=request.reference_video_urls,
        reference_audio_urls=request.reference_audio_urls,
        reference_manifest=request.reference_manifest,
    )
    if (pre_decision.get("decision") or {}).get("niche_resolution_review_required"):
        raise HTTPException(
            422,
            {
                "code": "niche_resolution_requires_clarification",
                "message": "Clarify the primary niche and proof target before paid autonomous render.",
                "niche_resolution": (pre_decision.get("input_summary") or {}).get("niche_resolution"),
            },
        )
    responsible_gate = pre_decision.get("responsible_content_gate") or {}
    if not bool(responsible_gate.get("render_allowed", True)):
        raise HTTPException(
            422,
            {
                "code": "responsible_content_requires_review",
                "message": "This prompt needs likeness, voice, or IP review before paid autonomous render.",
                "responsible_content_gate": responsible_gate,
            },
        )

    approved_plan_meta = _approved_plan_meta_from_request(request)
    if not request.dry_run_only and not bool(approved_plan_meta.get("included_in_render_source")):
        raise HTTPException(
            422,
            {
                "code": "approval_lock_source_required",
                "message": "Paid autonomous render requires an approved render source hash. Re-approve Storyboard or Prompt Preview before rendering.",
            },
        )

    auto_pin_selection = {
        "enabled": bool(request.auto_select_asset_pins),
        "mode": "disabled",
        "explicit_pin_ids": request.pinned_asset_ids,
        "auto_selected_pin_ids": [],
        "count": 0,
    }
    combined_pin_ids = list(request.pinned_asset_ids)
    if request.auto_select_asset_pins and len(combined_pin_ids) < 12:
        try:
            from agent.asset_memory import select_approved_asset_pins_for_render
            effective_target_market = str(
                (pre_decision.get("decision") or {}).get("target_market")
                or request.target_market
                or "auto"
            )
            auto_pin_selection = select_approved_asset_pins_for_render(
                user_idea=request.user_idea,
                niche=str((pre_decision.get("decision") or {}).get("niche") or "any"),
                target_market=effective_target_market,
                series_key=request.series_key,
                explicit_pin_ids=request.pinned_asset_ids,
                limit=min(6, 12 - len(combined_pin_ids)),
            )
            for pin_id in auto_pin_selection.get("auto_selected_pin_ids") or []:
                if pin_id not in combined_pin_ids:
                    combined_pin_ids.append(pin_id)
        except Exception as e:
            logger.warning(f"[/director/autonomous] auto pin selection skipped: {_redact_error(e)}")

    pinned_refs = _resolve_pinned_asset_refs(
        reference_image_urls=request.reference_image_urls,
        pinned_asset_ids=combined_pin_ids,
        auto_selected_pin_ids=auto_pin_selection.get("auto_selected_pin_ids") or [],
    )
    reference_image_urls = pinned_refs["reference_image_urls"]
    reference_counts = {
        "images": len(reference_image_urls),
        "videos": len(request.reference_video_urls),
        "audios": len(request.reference_audio_urls),
        "pinned_assets": len(pinned_refs["pinned_assets"]),
    }
    production_decision = build_autonomous_production_decision(
        user_idea=request.user_idea,
        target_market=request.target_market,
        target_platform=request.target_platform,
        duration_hint_s=request.duration_hint_s,
        reference_counts=reference_counts,
        reference_image_urls=reference_image_urls,
        reference_video_urls=request.reference_video_urls,
        reference_audio_urls=request.reference_audio_urls,
        reference_manifest=request.reference_manifest,
        niche_hint=str((pre_decision.get("decision") or {}).get("niche") or ""),
        speaker_count=max(1, min(4, len(request.reference_audio_urls) or 1)),
    )

    paid_duration_s = int(
        request.duration_hint_s
        or ((production_decision.get("decision") or {}).get("target_duration_s") or 0)
        or 8
    )
    if paid_duration_s > 60:
        raise HTTPException(
            422,
            {
                "code": "autonomous_duration_too_long",
                "message": "Long-form autonomous production currently supports 30-60 seconds. Use 60s or shorter.",
                "requested_duration_s": paid_duration_s,
                "max_long_form_duration_s": 60,
            },
        )
    if 15 < paid_duration_s < 30:
        raise HTTPException(
            422,
            {
                "code": "autonomous_duration_gap_not_supported",
                "message": "Choose 15s or shorter for a single Seedance clip, or 30-60s for long-form segmented production.",
                "requested_duration_s": paid_duration_s,
                "short_form_max_duration_s": 15,
                "long_form_min_duration_s": 30,
            },
        )
    if paid_duration_s > 15 and not request.dry_run_only and not request.approved_dry_run_job_id:
        raise HTTPException(
            422,
            {
                "code": "long_form_dry_run_required",
                "message": "Run and approve the full long-form dry-run before starting paid segmented render.",
                "strategy": "dry_run_approve_then_paid_render",
                "requested_duration_s": paid_duration_s,
            },
        )

    if request.approved_dry_run_job_id and not request.dry_run_only:
        bundle = _load_approved_longform_bundle(
            request=request,
            approved_plan_meta=approved_plan_meta,
            production_decision=production_decision,
        )
    else:
        bundle = _build_autonomous_seedance_execution_bundle(
            request=request,
            reference_image_urls=reference_image_urls,
            pinned_refs=pinned_refs,
            pre_decision=pre_decision,
            production_decision=production_decision,
            approved_plan_meta=approved_plan_meta,
        )
    execution_plan = bundle["execution_plan"]
    approval_lock = bundle["approval_lock"]
    pipeline_trace = bundle["pipeline_trace"]
    approval_verification = bundle["approval_verification"]
    editor_preview = bundle["editor_preview"]
    longform_plan = bundle.get("longform_plan")
    is_longform = bundle.get("render_path") == "long_form_segmented"
    job_id = longform_plan.longform_plan_id if is_longform and longform_plan is not None else execution_plan.execution_plan_id
    plan_id = str(execution_plan.storyboard_id or execution_plan.execution_plan_id)
    from workers.render_dry_run import RenderDryRunService
    render_dry_run_report = RenderDryRunService().generate_dry_run_report(
        execution_plan,
        approval_lock,
        approval_verification=approval_verification,
    )
    if is_longform and request.dry_run_only:
        pipeline_trace.append_stage(
            stage="longform_dry_run",
            stage_input=execution_plan,
            stage_output=render_dry_run_report,
            decision="long-form dry-run generated",
            reasoning_summary="Full segmented payload preview was generated synchronously; no paid vendor call was made.",
            rules_applied=["phase10.longform.dry_run_required", "phase10.longform.no_paid_vendor_call_on_preview"],
            warnings=list(render_dry_run_report.warnings),
            cost_estimate=execution_plan.cost_estimate,
        )
    commercial_usage_entry = None
    if not request.dry_run_only:
        commercial_usage_entry = _charge_commercial_usage_for_render(
            request=request,
            job_id=job_id,
            execution_plan=execution_plan,
            render_path="long_form_segmented" if is_longform else "seedance_execution_plan",
        )
        pipeline_trace.append_stage(
            stage="commercial_usage",
            stage_input={
                "user_id": request.user_id,
                "job_id": job_id,
                "render_path": "long_form_segmented" if is_longform else "seedance_execution_plan",
            },
            stage_output=commercial_usage_entry,
            decision="charged render credits before paid queue",
            reasoning_summary="Credit usage was deducted before spawning any paid render worker.",
            rules_applied=["phase13.credits.prepaid_render_gate"],
            cost_estimate=execution_plan.cost_estimate,
        )

    _JOBS_STORE[job_id] = {
        "status": "dry_run" if is_longform and request.dry_run_only else "pending",
        "progress": 100 if is_longform and request.dry_run_only else 0,
        "current_step": (
            "longform_dry_run_ready"
            if is_longform and request.dry_run_only
            else "queued_longform_execution_plan"
            if is_longform
            else "queued_seedance_execution_plan"
        ),
        "plan_id": plan_id,
        "mode": "autonomous",
        "execution_mode": "long_form_segmented" if is_longform else "seedance_execution_plan",
        "approval_lock": approval_lock.model_dump(mode="json"),
        "approval_verification": approval_verification.model_dump(mode="json"),
        "seedance_execution_plan": execution_plan.model_dump(mode="json"),
        "longform_plan": longform_plan.model_dump(mode="json") if longform_plan is not None else None,
        "render_dry_run_report": render_dry_run_report.model_dump(mode="json"),
        "longform_render_execution": (
            {
                "status": "dry_run",
                "longform_plan_id": job_id,
                "approval_lock_id": approval_lock.lock_id,
                "approval_verification": approval_verification.model_dump(mode="json"),
                "dry_run_report": render_dry_run_report.model_dump(mode="json"),
                "message": "Long-form dry-run generated; no paid vendor call was made.",
            }
            if is_longform and request.dry_run_only
            else None
        ),
        "input_contract": bundle["input_contract"].model_dump(mode="json"),
        "analyzed_input": bundle["analyzed_input"].model_dump(mode="json"),
        "creative_plan": bundle["creative_plan"].model_dump(mode="json"),
        "storyboard": bundle["storyboard"].model_dump(mode="json"),
        "curated_examples": [
            example.model_dump(mode="json") if hasattr(example, "model_dump") else example
            for example in (bundle.get("curated_examples") or [])
        ],
        "pipeline_trace": pipeline_trace.model_dump(mode="json"),
        "autonomous_meta": {
            "migration": "long_form_segmented_render_executor" if is_longform else "seedance_execution_plan_render_executor",
            "legacy_render_plan_used": False,
            "render_executor_required": True,
            "final_assembly_required": bool(is_longform),
            "approved_plan": approved_plan_meta,
            "approved_dry_run_job_id": request.approved_dry_run_job_id,
            "commercial_usage": commercial_usage_entry.model_dump(mode="json") if commercial_usage_entry is not None else None,
            "production_decision": production_decision,
            "pinned_assets": pinned_refs["pinned_assets"],
            "skipped_pins": pinned_refs["skipped_pins"],
            "auto_pin_selection": auto_pin_selection,
            "pipeline_trace": pipeline_trace.model_dump(mode="json"),
            "editor_preview": editor_preview,
            "dry_run_only": request.dry_run_only,
            "consistency_review": _consistency_review_record_from_request(
                request=request,
                action=str(execution_plan.metadata.get("consistency_policy_action") or "allow"),
                segment_ids=[
                    segment.segment_id
                    for segment in (getattr(longform_plan, "segments", None) or [])
                ],
            ) if is_longform else None,
        },
        "created_at": datetime.now(timezone.utc).isoformat() + "Z",
    }

    async def _run_seedance_execution_plan():
        try:
            if is_longform:
                await video_worker.render_longform_execution_plan(
                    longform_plan=longform_plan,
                    approval_lock=approval_lock,
                    idea=request.user_idea,
                    editor_preview=editor_preview,
                    jobs_store=_JOBS_STORE,
                    trace=pipeline_trace,
                    dry_run_only=request.dry_run_only,
                    dry_run_approved=bool(request.approved_dry_run_job_id),
                )
            else:
                await video_worker.render_seedance_execution_plan(
                    execution_plan=execution_plan,
                    approval_lock=approval_lock,
                    jobs_store=_JOBS_STORE,
                    dry_run_only=request.dry_run_only,
                    cost_gate_mode="draft_first" if not request.dry_run_only else "off",
                    max_total_cost_usd=request.max_total_cost_usd,
                )
        except video_worker.JobCancelledError:
            logger.info(f"[/director/autonomous] job {job_id} cancelled gracefully")
            await asyncio.to_thread(video_worker.cleanup_failed_job, job_id)
        except Exception as e:
            logger.exception(f"[/director/autonomous] job {job_id} failed")
            _JOBS_STORE[job_id].update(status="failed", error_message=_redact_error(e))
            await asyncio.to_thread(video_worker.cleanup_failed_job, job_id)

    if not (is_longform and request.dry_run_only):
        _spawn(_run_seedance_execution_plan())

    response = {
        "job_id": job_id,
        "polling_url": f"/api/v1/director/jobs/{job_id}",
        "plan_id": plan_id,
        "mode": "autonomous",
        "execution_mode": "long_form_segmented" if is_longform else "seedance_execution_plan",
        "legacy_render_plan_used": False,
        "approval_lock_id": approval_lock.lock_id,
        "approval_verification": approval_verification.model_dump(mode="json"),
        "pipeline_trace": pipeline_trace.model_dump(mode="json"),
        "seedance_execution_plan": {
            "execution_plan_id": execution_plan.execution_plan_id,
            "model": execution_plan.model,
            "duration_s": execution_plan.duration_s,
            "aspect_ratio": execution_plan.aspect_ratio,
            "resolution": execution_plan.resolution,
            "shot_count": len(execution_plan.shots),
            "knowledge_rule_ids": execution_plan.rules_applied,
            "curated_example_ids": execution_plan.examples_used,
        },
        "longform_plan": _longform_response_summary(longform_plan) if longform_plan is not None else None,
        "render_dry_run_report": render_dry_run_report.model_dump(mode="json"),
        "requires_consistency_review": execution_plan.metadata.get("consistency_policy_action") == "requires_review",
        "consistency_policy": {
            "action": execution_plan.metadata.get("consistency_policy_action") or "allow",
            "reasons": execution_plan.metadata.get("consistency_policy_reasons") or [],
            "review_approved": bool(request.consistency_review_approved),
            "review_decision": request.consistency_review_decision or ("approved" if request.consistency_review_approved else ""),
            "review_reason": request.consistency_review_reason,
            "reviewed_segment_ids": request.consistency_reviewed_segment_ids or request.approved_segment_ids,
        },
        "resolved_model": execution_plan.model,
        "target_market": (production_decision.get("decision") or {}).get("target_market") or request.target_market,
        "requested_target_market": request.target_market,
        "estimated_duration_s": execution_plan.duration_s,
        "estimated_cost_usd": float(
            execution_plan.cost_estimate.get("total_cost_usd")
            or execution_plan.cost_estimate.get("render_cost_usd")
            or 0.0
        ),
        "n_shots": len(execution_plan.shots),
        "render_strategy": "long_form_segmented" if is_longform else "seedance_execution_plan",
        "n_chunks": len(execution_plan.shots),
        "production_decision": production_decision,
        "pinned_assets": pinned_refs["pinned_assets"],
        "skipped_pins": pinned_refs["skipped_pins"],
        "auto_pin_selection": auto_pin_selection,
        "approved_plan": approved_plan_meta,
        "commercial_usage": commercial_usage_entry.model_dump(mode="json") if commercial_usage_entry is not None else None,
        "chain_elapsed_s": 0.0,
        "editor_preview": editor_preview,
        "hook_preview": {
            "pattern": bundle["creative_plan"].hook_pattern,
            "first_3s": bundle["storyboard"].scenes[0].beat if bundle["storyboard"].scenes else "",
            "niche": bundle["creative_plan"].target_niche,
            "mood": bundle["creative_plan"].style_direction,
        },
    }

    if idempotency_key:
        from core.idempotency import hash_body as _hash_body, store as _idem_store
        try:
            _idem_store(idempotency_key, _hash_body(request.model_dump()), response, status_code=201)
        except Exception as e:
            logger.warning(f"[/director/autonomous] idem store fail (non-fatal): {e}")

    return response


@router.post("/autonomous/legacy-director-plan")
async def autonomous_generate_legacy_director_plan(
    request: AutonomousGenerateRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """V6.1 Autonomous Director — 1-call: idea + refs → rendered MP4.

    Flow:
      1. AutonomousDirector chain (5 skills) → builds DirectorPlan
      2. Spawn render_plan() background task
      3. Return job_id + plan_id + editor_meta (caption + hashtag preview)

    Client polls /director/jobs/{job_id} for status + video_url.

    Backward compat: KHÔNG touch /director/plan (manual mode). User cũ chạy
    manual flow 100% giữ nguyên.
    """
    _require_paid_executor_admin(x_admin_key)
    from agent.autonomous_director import AutonomousDirector, AutonomousRunRequest

    # ---- Idempotency replay ----
    if idempotency_key:
        from core.idempotency import hash_body as _hash_body, lookup as _idem_lookup
        body_hash = _hash_body(request.model_dump())
        cached = _idem_lookup(idempotency_key, body_hash)
        if cached:
            if not cached["body_match"]:
                raise HTTPException(
                    409,
                    "Idempotency-Key đã dùng với body khác. Đổi key hoặc đợi 24h.",
                )
            logger.info(
                f"[/director/autonomous] Idempotency replay key={idempotency_key[:16]}…"
            )
            return cached["response_json"]

    _require_confirmed_reference_manifest_for_paid_render(request)

    auto_pin_selection = {
        "enabled": bool(request.auto_select_asset_pins),
        "mode": "disabled",
        "explicit_pin_ids": request.pinned_asset_ids,
        "auto_selected_pin_ids": [],
        "count": 0,
    }
    from agent.autonomous_production_decision import build_autonomous_production_decision

    pre_decision = build_autonomous_production_decision(
        user_idea=request.user_idea,
        target_market=request.target_market,
        target_platform=request.target_platform,
        duration_hint_s=request.duration_hint_s,
        reference_counts={
            "images": len(request.reference_image_urls),
            "videos": len(request.reference_video_urls),
            "audios": len(request.reference_audio_urls),
            "pinned_assets": len(request.pinned_asset_ids),
        },
        reference_image_urls=request.reference_image_urls,
        reference_video_urls=request.reference_video_urls,
        reference_audio_urls=request.reference_audio_urls,
        reference_manifest=request.reference_manifest,
    )
    if (pre_decision.get("decision") or {}).get("niche_resolution_review_required"):
        raise HTTPException(
            422,
            {
                "code": "niche_resolution_requires_clarification",
                "message": "Clarify the primary niche and proof target before paid autonomous render.",
                "niche_resolution": (pre_decision.get("input_summary") or {}).get("niche_resolution"),
            },
        )
    responsible_gate = pre_decision.get("responsible_content_gate") or {}
    if not bool(responsible_gate.get("render_allowed", True)):
        raise HTTPException(
            422,
            {
                "code": "responsible_content_requires_review",
                "message": "This prompt needs likeness, voice, or IP review before paid autonomous render.",
                "responsible_content_gate": responsible_gate,
            },
        )
    approved_plan_meta = _approved_plan_meta_from_request(request)
    combined_pin_ids = list(request.pinned_asset_ids)
    if request.auto_select_asset_pins and len(combined_pin_ids) < 12:
        try:
            from agent.asset_memory import select_approved_asset_pins_for_render
            effective_target_market = str(
                (pre_decision.get("decision") or {}).get("target_market")
                or request.target_market
                or "auto"
            )
            auto_pin_selection = select_approved_asset_pins_for_render(
                user_idea=request.user_idea,
                niche=str((pre_decision.get("decision") or {}).get("niche") or "any"),
                target_market=effective_target_market,
                series_key=request.series_key,
                explicit_pin_ids=request.pinned_asset_ids,
                limit=min(6, 12 - len(combined_pin_ids)),
            )
            for pin_id in auto_pin_selection.get("auto_selected_pin_ids") or []:
                if pin_id not in combined_pin_ids:
                    combined_pin_ids.append(pin_id)
        except Exception as e:
            logger.warning(f"[/director/autonomous] auto pin selection skipped: {_redact_error(e)}")

    pinned_refs = _resolve_pinned_asset_refs(
        reference_image_urls=request.reference_image_urls,
        pinned_asset_ids=combined_pin_ids,
        auto_selected_pin_ids=auto_pin_selection.get("auto_selected_pin_ids") or [],
    )
    reference_image_urls = pinned_refs["reference_image_urls"]

    # ---- Step 1: Run autonomous chain (4-5 LLM calls, ~5-15s) ----
    director_chain = AutonomousDirector()
    try:
        chain_result = await director_chain.run(AutonomousRunRequest(
            user_idea=request.user_idea,
            reference_image_urls=reference_image_urls,
            reference_video_urls=request.reference_video_urls,
            reference_audio_urls=request.reference_audio_urls,
            reference_manifest=request.reference_manifest,
            pinned_asset_ids=combined_pin_ids,
            pinned_assets=pinned_refs["pinned_assets"],
            target_platform=request.target_platform,
            target_market=request.target_market,
            duration_hint_s=request.duration_hint_s,
            aspect_ratio=request.aspect_ratio,
            user_model=request.user_model,
            use_vision_llm_for_tagging=request.use_vision_llm_for_tagging,
        ))
    except Exception as e:
        logger.exception("[/director/autonomous] chain failed")
        raise HTTPException(500, f"Autonomous chain failed: {_redact_error(e)}") from e

    plan = chain_result.director_plan
    resolved_model = chain_result.director_out.user_model
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    from agent.producer_strategy import build_producer_strategy
    producer_strategy = build_producer_strategy(
        estimated_cost_usd=plan.cost_estimate.total_cost_usd,
        estimated_duration_s=plan.continuity_bible.duration_s,
        n_shots=len(plan.shot_list),
        n_chunks=chain_result.director_out.n_chunks,
        render_strategy=chain_result.director_out.render_strategy,
        resolved_model=resolved_model,
    )
    storytelling_meta = plan.continuity_bible.storytelling_meta or {}
    production_graph = storytelling_meta.get("production_graph")
    scene_memory_pack = storytelling_meta.get("scene_memory_pack")
    model_violations = continuity_manager.validate_plan_against_model(
        plan, user_model=resolved_model,
    )
    from agent.autonomous_preflight_gate import build_autonomous_preflight_report
    autonomous_preflight = build_autonomous_preflight_report(
        plan=plan,
        resolved_model=resolved_model,
        target_market=str(
            (plan.continuity_bible.storytelling_meta or {}).get("target_market")
            if plan.continuity_bible.storytelling_meta else request.target_market
        ),
        target_platform=request.target_platform,
        reference_counts={
            "images": len(reference_image_urls),
            "videos": len(request.reference_video_urls),
            "audios": len(request.reference_audio_urls),
            "pinned_assets": len(pinned_refs["pinned_assets"]),
        },
        model_violations=model_violations,
        pinned_assets=pinned_refs["pinned_assets"],
    )
    reference_counts = {
        "images": len(reference_image_urls),
        "videos": len(request.reference_video_urls),
        "audios": len(request.reference_audio_urls),
        "pinned_assets": len(pinned_refs["pinned_assets"]),
    }
    from agent.autonomous_production_decision import build_autonomous_production_decision
    production_decision = build_autonomous_production_decision(
        user_idea=request.user_idea,
        target_market=request.target_market,
        target_platform=request.target_platform,
        duration_hint_s=plan.continuity_bible.duration_s,
        reference_counts=reference_counts,
        reference_image_urls=reference_image_urls,
        reference_video_urls=request.reference_video_urls,
        reference_audio_urls=request.reference_audio_urls,
        reference_manifest=request.reference_manifest,
        niche_hint=chain_result.planner_out.niche,
        speaker_count=max(1, min(4, len(request.reference_audio_urls) or 1)),
    )
    effective_response_market = str(
        (production_decision.get("decision") or {}).get("target_market")
        or request.target_market
        or "auto"
    )
    artifact_meta = production_artifacts.save_autonomous_snapshot(
        job_id=job_id,
        plan_id=plan.plan_id,
        plan=plan,
        planner_out=chain_result.planner_out,
        storyboard_out=chain_result.storyboard_out,
        director_out=chain_result.director_out,
        role_tagger_out=chain_result.role_tagger_out,
        editor_meta=chain_result.editor_meta,
        producer_strategy=producer_strategy.model_dump(),
        asset_memory=chain_result.asset_memory_meta,
        request_meta={
            "target_platform": request.target_platform,
            "target_market": effective_response_market,
            "requested_target_market": request.target_market,
            "series_key": request.series_key,
            "auto_select_asset_pins": request.auto_select_asset_pins,
            "duration_hint_s": request.duration_hint_s,
            "aspect_ratio": request.aspect_ratio,
            "user_model": request.user_model,
            "resolved_model": resolved_model,
            "resolution": request.resolution,
            "reference_image_urls": reference_image_urls,
            "reference_video_urls": request.reference_video_urls,
            "reference_audio_urls": request.reference_audio_urls,
            "reference_counts": reference_counts,
            "pinned_assets": pinned_refs["pinned_assets"],
            "skipped_pins": pinned_refs["skipped_pins"],
            "auto_pin_selection": auto_pin_selection,
            "approved_plan": approved_plan_meta,
            "autonomous_preflight": autonomous_preflight,
            "production_decision": production_decision,
        },
    )
    graph_meta = production_graph_store.save_graph(
        job_id=job_id,
        plan_id=plan.plan_id,
        graph=production_graph if isinstance(production_graph, dict) else {},
    )
    graph_long_form_enabled = (
        os.getenv("CINEJELLY_ENABLE_GRAPH_LONG_FORM", "").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    graph_executor_available = bool(
        producer_strategy.long_form_mode and graph_meta.get("persisted")
    )
    use_graph_executor = bool(
        graph_executor_available
        and graph_long_form_enabled
        and autonomous_preflight.get("render_allowed", True)
    )
    execution_mode = (
        "graph_executor_long_form" if use_graph_executor else "linear_worker"
    )

    # ---- Step 2: Validate against resolved model (hard cap check) ----
    hard_violations = [
        v for v in model_violations
        if "discrete" in v or "max " in v or "out of range" in v
    ]
    if hard_violations:
        # Auto-snap discrete for Wan 2.7 (was deferred in chain)
        from agent.continuity_manager import snap_discrete_durations
        snap_warnings = snap_discrete_durations(plan, resolved_model)
        if snap_warnings:
            logger.info(
                f"[/director/autonomous] {job_id} snapped {len(snap_warnings)} shot durations: "
                f"{snap_warnings[:3]}"
            )

    # ---- Step 3: Spawn render in background ----
    _JOBS_STORE[job_id] = {
        "status": "pending",
        "progress": 0,
        "current_step": "queued",
        "plan_id": plan.plan_id,
        "mode": "autonomous",
        "execution_mode": execution_mode,
        "autonomous_meta": {
            "chain_elapsed_s": chain_result.elapsed_s,
            "render_strategy": chain_result.director_out.render_strategy,
            "n_chunks": chain_result.director_out.n_chunks,
            "resolved_model": resolved_model,
            "target_market": effective_response_market,
            "requested_target_market": request.target_market,
            "execution_mode": execution_mode,
            "graph_executor_available": graph_executor_available,
            "graph_long_form_enabled": graph_long_form_enabled,
            "producer_strategy": producer_strategy.model_dump(),
            "autonomous_preflight": autonomous_preflight,
            "production_decision": production_decision,
            "scene_memory_pack": scene_memory_pack,
            "artifact": artifact_meta,
            "production_graph": graph_meta,
            "asset_memory": chain_result.asset_memory_meta,
            "pinned_assets": pinned_refs["pinned_assets"],
            "skipped_pins": pinned_refs["skipped_pins"],
            "auto_pin_selection": auto_pin_selection,
            "approved_plan": approved_plan_meta,
            "viral_hook_pattern": chain_result.planner_out.hook_pattern,
            "hook_first_3s": chain_result.planner_out.hook_first_3s,
            "production_graph_summary": (
                production_graph.get("summary") if isinstance(production_graph, dict) else None
            ),
        },
        "editor_meta": chain_result.editor_meta.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat() + "Z",
    }

    sanitized_plan = continuity_manager.sanitize_plan(plan)

    async def _run():
        try:
            if use_graph_executor:
                from agent.production_graph_executor import run_graph_executor_until_idle

                _JOBS_STORE[job_id].update(
                    status="graph_executing",
                    progress=max(1, int(_JOBS_STORE[job_id].get("progress") or 1)),
                    current_step="graph_executor_loop",
                )
                handlers = video_worker.graph_executor_handlers_from_artifact(
                    job_id=job_id,
                    jobs_store=_JOBS_STORE,
                )
                result = await run_graph_executor_until_idle(
                    job_id=job_id,
                    worker_id="autonomous_graph_executor",
                    limit=1,
                    lease_ttl_s=900,
                    handlers=handlers,
                    max_cycles=max(20, len(sanitized_plan.shot_list) * 4 + 10),
                )
                _JOBS_STORE[job_id].update(
                    graph_executor=result,
                    current_step="done" if result.get("completed") else "graph_executor_idle",
                    status="done" if result.get("completed") else "graph_idle",
                    progress=100 if result.get("completed") else _JOBS_STORE[job_id].get("progress", 1),
                )
            else:
                await video_worker.render_plan(
                    job_id=job_id,
                    plan=sanitized_plan,
                    reference_images=reference_image_urls,
                    reference_videos=request.reference_video_urls,
                    reference_audios=request.reference_audio_urls,
                    user_model=resolved_model,
                    resolution=request.resolution,
                    audio_plan=None,
                    jobs_store=_JOBS_STORE,
                    use_llm_scene_gen=True,
                    cost_gate_mode=producer_strategy.cost_gate_mode,
                    cost_gate_threshold=producer_strategy.cost_gate_threshold,
                )
        except video_worker.JobCancelledError:
            logger.info(f"[/director/autonomous] job {job_id} cancelled gracefully")
            await asyncio.to_thread(video_worker.cleanup_failed_job, job_id)
        except Exception as e:
            logger.exception(f"[/director/autonomous] job {job_id} failed")
            _JOBS_STORE[job_id].update(status="failed", error_message=_redact_error(e))
            await asyncio.to_thread(video_worker.cleanup_failed_job, job_id)

    _spawn(_run())

    response = {
        "job_id": job_id,
        "polling_url": f"/api/v1/director/jobs/{job_id}",
        "plan_id": plan.plan_id,
        "mode": "autonomous",
        "execution_mode": execution_mode,
        "graph_executor_available": graph_executor_available,
        "graph_long_form_enabled": graph_long_form_enabled,
        "resolved_model": resolved_model,
        "target_market": effective_response_market,
        "requested_target_market": request.target_market,
        "estimated_duration_s": plan.continuity_bible.duration_s,
        "estimated_cost_usd": plan.cost_estimate.total_cost_usd,
        "n_shots": len(plan.shot_list),
        "render_strategy": chain_result.director_out.render_strategy,
        "n_chunks": chain_result.director_out.n_chunks,
        "producer_strategy": producer_strategy.model_dump(),
        "autonomous_preflight": autonomous_preflight,
        "production_decision": production_decision,
        "scene_memory_pack": scene_memory_pack,
        "asset_memory": chain_result.asset_memory_meta,
        "pinned_assets": pinned_refs["pinned_assets"],
        "skipped_pins": pinned_refs["skipped_pins"],
        "auto_pin_selection": auto_pin_selection,
        "approved_plan": approved_plan_meta,
        "artifact_summary": artifact_meta.get("summary"),
        "production_graph_persistence": graph_meta,
        "production_graph_summary": (
            production_graph.get("summary") if isinstance(production_graph, dict) else None
        ),
        "chain_elapsed_s": chain_result.elapsed_s,
        # Editor preview — FE can display caption + hashtags ngay sau khi /autonomous trả về
        "editor_preview": {
            "caption_vn": chain_result.editor_meta.caption_vn,
            "caption_en": chain_result.editor_meta.caption_en,
            "hashtags_vn": chain_result.editor_meta.hashtags_vn,
            "hashtags_en": chain_result.editor_meta.hashtags_en,
            "distribution_package": chain_result.editor_meta.distribution_package,
        },
        # Viral hook preview
        "hook_preview": {
            "pattern": chain_result.planner_out.hook_pattern,
            "first_3s": chain_result.planner_out.hook_first_3s,
            "niche": chain_result.planner_out.niche,
            "mood": chain_result.planner_out.mood,
        },
    }

    # Idempotency store
    if idempotency_key:
        from core.idempotency import hash_body as _hash_body, store as _idem_store
        try:
            _idem_store(idempotency_key, _hash_body(request.model_dump()), response, status_code=201)
        except Exception as e:
            logger.warning(f"[/director/autonomous] idem store fail (non-fatal): {e}")

    return response


@router.get("/jobs/{job_id}/artifact")
async def get_job_artifact(job_id: str):
    """Return persisted autonomous production artifact snapshot, if available."""
    snapshot = production_artifacts.load_snapshot(job_id)
    if not snapshot:
        raise HTTPException(404, f"artifact for job '{job_id}' not found")
    return snapshot


@router.get("/jobs/{job_id}/production-report")
async def get_job_production_report(job_id: str):
    """Return a concise agent-readable storyboard/design/graph/QA report."""
    report = production_artifacts.load_report(
        job_id,
        job_record={**_JOBS_STORE.get(job_id, {}), "job_id": job_id},
    )
    if not report:
        raise HTTPException(404, f"production report for job '{job_id}' not found")
    report["user_feedback"] = render_feedback_store.summarize_job_feedback(job_id)
    return report


@router.get("/jobs/{job_id}/benchmark-evidence-pack")
async def get_job_benchmark_evidence_pack(job_id: str):
    """Return a benchmark evidence draft extracted from a production artifact."""
    from agent.benchmark_evidence_pack_builder import build_benchmark_result_draft_from_artifact
    from agent.benchmark_evidence_validator import validate_benchmark_result_evidence

    snapshot = production_artifacts.load_snapshot(job_id)
    if not snapshot:
        raise HTTPException(404, f"artifact for job '{job_id}' not found")
    job_record = _JOBS_STORE.get(job_id, {})
    draft = build_benchmark_result_draft_from_artifact(snapshot, job_record={**job_record, "job_id": job_id})
    return {
        "schema_version": "cinejelly.job_benchmark_evidence_pack.v1",
        "job_id": job_id,
        "benchmark_result_draft": draft,
        "user_feedback": render_feedback_store.build_feedback_evidence(job_id),
        "evidence_validation_preview": validate_benchmark_result_evidence(draft),
    }


def _find_feedback_job_record(job_id: str) -> Optional[dict[str, Any]]:
    if job_id in _JOBS_STORE:
        return {**_JOBS_STORE[job_id], "job_id": job_id}
    history = director_history.get_job(job_id, include_plan=False)
    if history:
        return history
    snapshot = production_artifacts.load_snapshot(job_id)
    if snapshot:
        return {
            "job_id": job_id,
            "status": "artifact",
            "mode": "autonomous",
            "output_url": None,
        }
    return None


@router.get("/jobs/{job_id}/feedback")
async def get_job_feedback(job_id: str):
    """Return human/operator feedback captured for a rendered job."""
    try:
        evidence = render_feedback_store.build_feedback_evidence(job_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if evidence["summary"]["feedback_count"] == 0 and _find_feedback_job_record(job_id) is None:
        raise HTTPException(404, "job not found")
    return evidence


@router.post("/jobs/{job_id}/feedback")
async def record_job_feedback(job_id: str, request: RenderFeedbackRequest):
    """Persist post-render feedback without triggering any paid render work."""
    job_record = _find_feedback_job_record(job_id)
    if job_record is None:
        raise HTTPException(404, "job not found")
    try:
        doc = render_feedback_store.record_feedback(
            job_id=job_id,
            rating=request.rating,
            issue_tags=request.issue_tags,
            notes=request.notes,
            reviewer=request.reviewer,
            output_url=request.output_url,
            job_record=job_record,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {
        "schema_version": "cinejelly.render_feedback_response.v1",
        "job_id": job_id,
        "summary": doc["summary"],
        "latest": doc["entries"][-1],
    }


@router.get("/jobs/{job_id}/production-graph")
async def get_job_production_graph(job_id: str):
    """Return queryable persisted production graph nodes/edges, if available."""
    graph = production_graph_store.load_graph(job_id)
    if not graph:
        raise HTTPException(404, f"production graph for job '{job_id}' not found")
    return {
        **graph,
        "resume_plan": production_graph_store.build_resume_plan(graph),
        "execution_batch": production_graph_store.build_execution_batch(graph),
    }


@router.post("/jobs/{job_id}/production-graph/claim")
async def claim_job_production_graph_batch(
    job_id: str,
    request: GraphExecutionClaimRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """Lease the next dependency-safe production graph tasks for a worker."""
    _require_mutation_admin(x_admin_key)
    claim = production_graph_store.claim_execution_batch(
        job_id=job_id,
        worker_id=request.worker_id,
        limit=request.limit,
        lease_ttl_s=request.lease_ttl_s,
    )
    if not claim:
        raise HTTPException(404, f"production graph for job '{job_id}' not found")
    return claim


@router.post("/jobs/{job_id}/production-graph/leases/expire")
async def expire_job_production_graph_leases(
    job_id: str,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """Release expired leased graph nodes back to executable states."""
    _require_mutation_admin(x_admin_key)
    graph = production_graph_store.load_graph(job_id)
    if not graph:
        raise HTTPException(404, f"production graph for job '{job_id}' not found")
    return production_graph_store.release_expired_leases(job_id)


@router.post("/jobs/{job_id}/production-graph/tasks/{node_id}/result")
async def record_job_production_graph_task_result(
    job_id: str,
    node_id: str,
    request: GraphTaskResultRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """Record completion/failure for one leased graph task.

    This is the executor acknowledgement path: a graph worker claims a shot,
    QA, or assembly node, performs the work, then posts the result here so the
    next dependency-safe batch can be computed without re-planning the job.
    """
    _require_mutation_admin(x_admin_key)
    graph = production_graph_store.load_graph(job_id)
    if not graph:
        raise HTTPException(404, f"production graph for job '{job_id}' not found")
    try:
        result = production_graph_store.record_task_result(
            job_id=job_id,
            node_id=node_id,
            outcome=request.outcome,
            payload_patch=request.payload_patch,
            lease_id=request.lease_id,
            worker_id=request.worker_id,
        )
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    if not result.get("recorded"):
        raise HTTPException(404, f"node '{node_id}' not found in production graph for job '{job_id}'")
    return result


@router.post("/jobs/{job_id}/production-graph/executor/run-once")
async def run_job_production_graph_executor_once(
    job_id: str,
    request: GraphExecutorRunOnceRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """Run one graph executor cycle.

    Default `preview=true` is read-only. Real paid render execution must be
    wired through internal worker handlers; the HTTP route exposes only preview
    plus explicit metadata stubs for local non-vendor smoke tests.
    """
    from agent.production_graph_executor import (
        metadata_stub_handlers,
        run_graph_executor_once,
    )

    if not request.preview:
        if request.allow_metadata_stub:
            _require_dev_metadata_stub(x_admin_key)
        else:
            _require_mutation_admin(x_admin_key)
    if not request.preview and not request.allow_metadata_stub:
        raise HTTPException(
            400,
            "HTTP graph executor cannot run paid render handlers. Use preview=true or allow_metadata_stub=true for local smoke tests.",
        )
    result = await run_graph_executor_once(
        job_id=job_id,
        worker_id=request.worker_id,
        limit=request.limit,
        lease_ttl_s=request.lease_ttl_s,
        handlers=metadata_stub_handlers() if request.allow_metadata_stub else None,
        preview=request.preview,
    )
    if not result.get("ok") and result.get("reason") == "graph_not_found":
        raise HTTPException(404, f"production graph for job '{job_id}' not found")
    return result


@router.post("/jobs/{job_id}/production-graph/executor/run-loop")
async def run_job_production_graph_executor_loop(
    job_id: str,
    request: GraphExecutorLoopRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """Run a graph executor loop until idle/noop/blocked.

    By default this route refuses to run mutating work unless either
    `allow_metadata_stub` or `allow_paid_handlers` is explicit. Paid handlers
    reconstruct the persisted DirectorPlan artifact and may call AtlasCloud.
    """
    from agent.production_graph_executor import (
        metadata_stub_handlers,
        run_graph_executor_until_idle,
    )

    if request.allow_metadata_stub and request.allow_paid_handlers:
        raise HTTPException(400, "choose either metadata stubs or paid handlers, not both")
    if request.allow_metadata_stub:
        _require_dev_metadata_stub(x_admin_key)
    if request.allow_paid_handlers:
        _require_paid_executor_admin(x_admin_key)
    if not request.allow_metadata_stub and not request.allow_paid_handlers:
        raise HTTPException(
            400,
            "run-loop mutates graph state. Set allow_metadata_stub=true for local tests or allow_paid_handlers=true for trusted paid execution.",
        )
    graph = production_graph_store.load_graph(job_id)
    if not graph:
        raise HTTPException(404, f"production graph for job '{job_id}' not found")

    def _handlers():
        if request.allow_metadata_stub:
            return metadata_stub_handlers()
        return video_worker.graph_executor_handlers_from_artifact(
            job_id=job_id,
            jobs_store=_JOBS_STORE,
        )

    async def _run_loop():
        return await run_graph_executor_until_idle(
            job_id=job_id,
            worker_id=request.worker_id,
            limit=request.limit,
            lease_ttl_s=request.lease_ttl_s,
            handlers=_handlers(),
            max_cycles=request.max_cycles,
        )

    if request.run_background:
        _JOBS_STORE.setdefault(job_id, {}).update(
            status="graph_executing",
            current_step="graph_executor_loop",
            progress=max(1, int(_JOBS_STORE.get(job_id, {}).get("progress") or 1)),
        )

        async def _run():
            try:
                result = await _run_loop()
                _JOBS_STORE.setdefault(job_id, {}).update(
                    graph_executor=result,
                    current_step="graph_executor_idle" if not result.get("completed") else "done",
                    status="done" if result.get("completed") else "graph_idle",
                    progress=100 if result.get("completed") else _JOBS_STORE.get(job_id, {}).get("progress", 1),
                )
            except Exception as e:
                logger.exception(f"[graph_executor] loop failed for {job_id}")
                _JOBS_STORE.setdefault(job_id, {}).update(
                    status="failed",
                    current_step="graph_executor_failed",
                    error_message=_redact_error(e),
                )

        _spawn(_run())
        return {
            "schema_version": "cinejelly.graph_executor_loop_start.v1",
            "job_id": job_id,
            "started": True,
            "mode": "metadata_stub" if request.allow_metadata_stub else "paid_handlers",
            "polling_url": f"/api/v1/director/jobs/{job_id}",
        }

    return await _run_loop()


@router.post("/plan-and-render")
async def plan_and_render(request: PlanAndRenderRequest):
    """Build a plan then render it immediately. Skips Human-in-the-Loop review.

    Use cases:
        - Automated batch jobs (CI / cron).
        - CLI / scripted tools where there is no human reviewer.

    The job state goes `pending → planning → rendering → assembling → done`.
    Plan/eval cost is still incurred; clients that want savings should batch via
    `/plan` + caching the DirectorPlan client-side instead.
    """
    pr = request.plan_request

    if not (pr.product_input.url or pr.product_input.text_description or pr.user_brief):
        raise HTTPException(400, "Provide brief or product_input on plan_request")

    job_id = f"job_{uuid.uuid4().hex[:12]}"
    _JOBS_STORE[job_id] = {
        "status": "pending",
        "progress": 0,
        "current_step": "queued",
        "plan_id": None,
        "mode": "plan_and_render",
        "created_at": datetime.now(timezone.utc).isoformat() + "Z",
    }

    async def _run():
        try:
            _JOBS_STORE[job_id].update(status="planning", current_step="director_agent")
            tech_config = {
                "duration_s": pr.settings.duration_s,
                "aspect_ratio": pr.settings.aspect_ratio,
                "audio_mode": pr.settings.audio_mode,
                "model": pr.settings.model,
                "resolution": pr.settings.resolution,
                "num_shots": pr.settings.num_shots,
            }
            plan_built = await director.plan(
                product_input=pr.product_input.model_dump(exclude_none=True),
                reference_images=pr.reference_images,
                reference_videos=pr.reference_videos,
                reference_audios=pr.reference_audios,
                user_brief=pr.user_brief,
                context_injection=pr.context_injection.model_dump(exclude_none=True),
                tech_config=tech_config,
                niche_hint=pr.niche_hint,
                reference_role_hints=pr.reference_role_hints or None,
            )
            _JOBS_STORE[job_id]["plan_id"] = plan_built.plan_id

            warnings = continuity_manager.validate_plan(
                plan_built,
                target_duration_s=pr.settings.duration_s,
                tolerance_s=2,
            )
            if warnings:
                _JOBS_STORE[job_id]["validation_warnings"] = warnings
                logger.warning(
                    f"[/director/plan-and-render] {job_id} warnings: {warnings[:5]}"
                )
            plan_built = continuity_manager.sanitize_plan(plan_built)

            await video_worker.render_plan(
                job_id=job_id,
                plan=plan_built,
                reference_images=pr.reference_images,
                reference_videos=pr.reference_videos,
                reference_audios=pr.reference_audios,
                user_model=pr.settings.model,
                resolution=pr.settings.resolution,
                audio_plan=(
                    request.audio_plan.model_dump(exclude_none=True)
                    if request.audio_plan is not None else None
                ),
                jobs_store=_JOBS_STORE,
                use_llm_scene_gen=request.use_llm_scene_gen,
            )
        except video_worker.JobCancelledError:
            logger.info(f"[/director/plan-and-render] job {job_id} cancelled gracefully")
            await asyncio.to_thread(video_worker.cleanup_failed_job, job_id)
        except Exception as e:
            logger.exception(f"[/director/plan-and-render] job {job_id} failed")
            _JOBS_STORE[job_id].update(status="failed", error_message=_redact_error(e))
            await asyncio.to_thread(video_worker.cleanup_failed_job, job_id)  # Sprint3 B3

    _spawn(_run())

    return {
        "job_id": job_id,
        "polling_url": f"/api/v1/director/jobs/{job_id}",
        "estimated_duration_s": pr.settings.duration_s,
        "estimated_cost_usd": 0.0,  # unknown until plan() returns
        "plan_id": None,
        "mode": "plan_and_render",
    }


# ============================================================
# POST /revise — Layer 1.5 LLM revise current plan via instruction
# ============================================================
@router.post("/revise", response_model=DirectorPlan)
async def revise_plan(request: ReviseRequest):
    """Mutate the provided plan based on `instruction` and return revised plan.

    Implementation: single LLM call against `system_prompts/revise.md`.
    Server then re-validates continuity + sanitizes — frontend can swap the
    revised plan into the editor directly.
    """
    from system_prompts import load as load_system_prompt
    from vendors.llm_router import llm
    from agent.model_capabilities import summary_for_director_prompt
    from agent.director_agent import _safe_parse_json  # reuse fence-stripping parser
    from pydantic import ValidationError as _PVE
    import json as _json

    tech_config = {
        "duration_s": request.settings.duration_s,
        "aspect_ratio": request.settings.aspect_ratio,
        "audio_mode": request.settings.audio_mode,
        "model": request.settings.model,
        "resolution": request.settings.resolution,
        "num_shots": request.settings.num_shots,
        "model_capability_notes": summary_for_director_prompt(request.settings.model),
    }
    payload = {
        "current_plan": request.plan.model_dump(),
        "user_instruction": request.instruction,
        "tech_config": tech_config,
    }
    try:
        raw = await asyncio.to_thread(
            llm.complete,
            system_prompt=load_system_prompt("revise"),
            user_message=_json.dumps(payload, ensure_ascii=False, default=str),
            task="generator",
            max_tokens=8000,
            temperature=0.4,
        )
    except Exception as e:
        logger.exception("[/director/revise] LLM call failed")
        raise HTTPException(500, f"Revise LLM call failed: {_redact_error(e)}") from e

    try:
        raw_dict = _safe_parse_json(raw)
    except Exception as e:
        logger.error(f"[/director/revise] JSON parse fail. Head: {raw[:300]}")
        raise HTTPException(500, f"Revise output is not valid JSON: {e}") from e

    # Pydantic validate — re-use DirectorPlan schema (raises 422 on shape drift)
    try:
        revised = DirectorPlan(**raw_dict)
    except _PVE as e:
        logger.error(f"[/director/revise] schema invalid: {e}")
        raise HTTPException(500, f"Revised plan schema invalid: {e}") from e

    # Re-validate continuity + sanitize before returning
    warnings = continuity_manager.validate_plan(
        revised, target_duration_s=request.settings.duration_s, tolerance_s=2,
    )
    if warnings:
        logger.warning(f"[/director/revise] revised plan warnings: {warnings[:5]}")
    revised = continuity_manager.sanitize_plan(revised)
    return revised


# ============================================================
# POST /refine — re-render ONE shot
# ============================================================
@router.post("/refine")
async def refine_shot(request: RefineRequest):
    """Re-render a single shot from an approved plan (Evaluation-driven flow).

    Cost: 1 shot × per-second model price (vs. full plan re-render). Typical
    use: Evaluation flagged `S3` as `consistency_score=5.2` → user clicks
    "Refine S3" → this endpoint regenerates just that clip.
    """
    # Validate shot exists
    target = next((s for s in request.plan.shot_list if s.shot_id == request.shot_id), None)
    if target is None:
        raise HTTPException(404, f"shot_id '{request.shot_id}' not in plan")

    # Apply shot overrides (shallow merge into the target shot)
    plan_for_refine = request.plan
    if request.shot_overrides:
        plan_copy = request.plan.model_copy(deep=True)
        target_copy = next(s for s in plan_copy.shot_list if s.shot_id == request.shot_id)
        # Shallow merge — for nested visual/audio/continuity dicts, take user override entirely
        for k, v in request.shot_overrides.items():
            if hasattr(target_copy, k):
                if isinstance(v, dict) and hasattr(getattr(target_copy, k), "model_fields"):
                    sub = getattr(target_copy, k)
                    for sk, sv in v.items():
                        if hasattr(sub, sk):
                            setattr(sub, sk, sv)
                else:
                    setattr(target_copy, k, v)
        plan_for_refine = plan_copy

    job_id = f"refine_{uuid.uuid4().hex[:12]}"
    _JOBS_STORE[job_id] = {
        "status": "pending",
        "progress": 0,
        "current_step": "queued",
        "plan_id": request.plan.plan_id,
        "shot_id": request.shot_id,
        "mode": "refine",
        "created_at": datetime.now(timezone.utc).isoformat() + "Z",
    }

    async def _run():
        try:
            result = await video_worker.render_single_shot(
                job_id=job_id,
                plan=plan_for_refine,
                shot_id=request.shot_id,
                reference_images=request.reference_images,
                reference_videos=request.reference_videos,
                reference_audios=request.reference_audios,
                user_model=request.settings.model,
                resolution=request.settings.resolution,
                previous_last_frame_url=request.previous_last_frame_url,
                jobs_store=_JOBS_STORE,
                use_llm_scene_gen=request.use_llm_scene_gen,
            )
            _JOBS_STORE[job_id].update(refine_result=result)
        except video_worker.JobCancelledError:
            logger.info(f"[/director/refine] {job_id} cancelled gracefully")
            await asyncio.to_thread(video_worker.cleanup_failed_job, job_id)
        except Exception as e:
            logger.exception(f"[/director/refine] {job_id} failed")
            _JOBS_STORE[job_id].update(status="failed", error_message=_redact_error(e))
            await asyncio.to_thread(video_worker.cleanup_failed_job, job_id)  # Sprint3 B3

    _spawn(_run())
    return {
        "job_id": job_id,
        "polling_url": f"/api/v1/director/jobs/{job_id}",
        "shot_id": request.shot_id,
        "estimated_duration_s": target.duration_s,
        "mode": "refine",
    }


# ============================================================
# GET /jobs/{job_id}
# ============================================================
@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    if job_id not in _JOBS_STORE:
        raise HTTPException(404, "job not found")
    return {
        "job_id": job_id,
        **_JOBS_STORE[job_id],
        "feedback_summary": render_feedback_store.summarize_job_feedback(job_id),
    }


@router.get("/jobs/{job_id}/final-video")
async def get_job_final_video(job_id: str, refresh: bool = False):
    """Return object-storage metadata for the assembled long-form MP4.

    Public/CDN-backed objects return a stable URL. Private objects return a
    presigned URL and can refresh it from the persisted object key.
    """
    if job_id not in _JOBS_STORE:
        raise HTTPException(404, "job not found")
    assembly = _JOBS_STORE[job_id].get("assembly_result") or {}
    if not isinstance(assembly, dict):
        raise HTTPException(404, "final video metadata is not available for this job")
    storage_key = str(assembly.get("storage_key") or "").strip()
    is_public = bool(assembly.get("storage_is_public") or assembly.get("is_public"))
    refresh_supported = bool(assembly.get("storage_refresh_supported") or assembly.get("refresh_supported"))
    was_refreshed = False
    if storage_key and not is_public and (refresh or _private_url_refresh_needed(assembly)):
        if not refresh_supported:
            raise HTTPException(409, "final video URL refresh is not enabled for this object")
        try:
            refreshed = r2_storage.refresh_presigned_url_sync(storage_key)
        except Exception as exc:
            logger.exception("final_video_presigned_refresh_failed", extra={"job_id": job_id, "storage_key": storage_key})
            raise HTTPException(502, f"failed to refresh final video URL: {str(exc)[:200]}") from exc
        assembly.update(refreshed)
        assembly["storage_delivery_url"] = refreshed["storage_presigned_url"]
        assembly["final_video_url"] = refreshed["storage_presigned_url"]
        assembly["storage_access_strategy"] = assembly.get("storage_access_strategy") or "private_presigned"
        assembly["storage_refresh_supported"] = bool(refreshed.get("refresh_supported", True))
        _JOBS_STORE[job_id]["assembly_result"] = assembly
        _JOBS_STORE[job_id]["output_url"] = refreshed["storage_presigned_url"]
        _JOBS_STORE[job_id]["output_path"] = refreshed["storage_presigned_url"]
        refresh_supported = bool(assembly.get("storage_refresh_supported") or assembly.get("refresh_supported"))
        was_refreshed = True
        _append_final_video_refresh_trace(job_id=job_id, assembly=assembly, refreshed=refreshed)
        logger.info("final_video_presigned_refreshed", extra={"job_id": job_id, "storage_key": storage_key})
    final_url = str(
        assembly.get("storage_delivery_url")
        or (assembly.get("storage_public_url") if is_public else None)
        or assembly.get("storage_presigned_url")
        or assembly.get("final_video_url")
        or _JOBS_STORE[job_id].get("output_url")
        or ""
    ).strip()
    if not final_url:
        raise HTTPException(404, "final video URL is not available for this job")
    return {
        "job_id": job_id,
        "final_video_url": final_url,
        "delivery_url": assembly.get("storage_delivery_url") or final_url,
        "storage_bucket": assembly.get("storage_bucket"),
        "storage_key": assembly.get("storage_key"),
        "storage_type": assembly.get("storage_type") or ("public" if is_public else "private"),
        "access_strategy": assembly.get("storage_access_strategy"),
        "storage_access_strategy": assembly.get("storage_access_strategy"),
        "cdn_url": assembly.get("storage_cdn_url") or assembly.get("storage_public_url"),
        "storage_delivery_url": assembly.get("storage_delivery_url") or final_url,
        "storage_cdn_url": assembly.get("storage_cdn_url") or assembly.get("storage_public_url"),
        "is_public": is_public,
        "storage_is_public": is_public,
        "storage_public_url": assembly.get("storage_public_url"),
        "storage_presigned_expires_s": assembly.get("storage_presigned_expires_s"),
        "presigned_expires_at": assembly.get("storage_presigned_expires_at"),
        "storage_presigned_expires_at": assembly.get("storage_presigned_expires_at"),
        "refresh_supported": refresh_supported,
        "storage_refresh_supported": refresh_supported,
        "refreshed": was_refreshed,
    }


def _append_final_video_refresh_trace(*, job_id: str, assembly: dict[str, Any], refreshed: dict[str, Any]) -> None:
    """Append an auditable trace entry when a private final-video URL is refreshed."""
    raw_trace = _JOBS_STORE.get(job_id, {}).get("pipeline_trace")
    if not isinstance(raw_trace, dict):
        return
    try:
        from pipeline.trace import PipelineTrace

        trace = PipelineTrace.model_validate(raw_trace)
        trace.append_stage(
            stage="final_video_url_refresh",
            stage_input={"job_id": job_id, "storage_key": assembly.get("storage_key")},
            stage_output={
                "storage_access_strategy": assembly.get("storage_access_strategy") or "private_presigned",
                "storage_presigned_expires_at": refreshed.get("storage_presigned_expires_at"),
                "refresh_supported": refreshed.get("refresh_supported"),
            },
            decision="refreshed private final-video delivery URL",
            reasoning_summary="A new presigned URL was generated from the persisted R2/S3 object key without exposing local files.",
            rules_applied=["phase10.final_video.private_url_refresh"],
        )
        _JOBS_STORE[job_id]["pipeline_trace"] = trace.model_dump(mode="json")
    except Exception:
        logger.warning("final_video_refresh_trace_append_failed", extra={"job_id": job_id}, exc_info=True)


def _private_url_refresh_needed(assembly: dict[str, Any]) -> bool:
    """Return true when a private presigned URL is absent or close to expiry."""
    if assembly.get("storage_is_public") or assembly.get("is_public"):
        return False
    if not assembly.get("storage_presigned_url"):
        return True
    expires_at = str(assembly.get("storage_presigned_expires_at") or "").strip()
    if not expires_at:
        return False
    try:
        parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed <= datetime.now(timezone.utc)


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """V5.1 — Set cancelled flag AND kill any in-flight AtlasCloud predictions.

    Without the vendor-side cancel call, AtlasCloud keeps rendering after the
    user clicks Hủy → the user still gets billed for $1-5 per cancelled job.
    We now look up `current_prediction_id` (latest submitted, possibly still
    running) and the full `prediction_ids` history (in case earlier shots are
    still queued). Cancel is best-effort: vendor returns no-op on already-done
    predictions, which is safe.
    """
    if job_id not in _JOBS_STORE:
        raise HTTPException(404, "job not found")

    rec = _JOBS_STORE[job_id]
    rec.update(status="cancelled")

    # Best-effort vendor-side kill (idempotent — already-done predictions no-op)
    pred_ids: list[str] = []
    current = rec.get("current_prediction_id")
    if current:
        pred_ids.append(current)
    history = rec.get("prediction_ids") or []
    for pid in history:
        if pid and pid not in pred_ids:
            pred_ids.append(pid)

    cancelled_count = 0
    if pred_ids:
        from vendors.atlascloud import atlas_client
        if atlas_client is not None:
            async def _kill_one(pid: str) -> bool:
                try:
                    await asyncio.to_thread(atlas_client.cancel_prediction, pid)
                    return True
                except Exception as e:
                    logger.warning(f"[/cancel] {job_id} cancel_prediction({pid}) fail: {e}")
                    return False
            results = await asyncio.gather(*(_kill_one(pid) for pid in pred_ids))
            cancelled_count = sum(1 for r in results if r)
        else:
            logger.warning(f"[/cancel] {job_id} atlas_client=None — flag-only cancel")

    logger.info(
        f"[/cancel] {job_id} cancelled — vendor predictions killed "
        f"{cancelled_count}/{len(pred_ids)}"
    )
    return {
        "job_id": job_id,
        "status": "cancelled",
        "vendor_cancelled_count": cancelled_count,
        "vendor_total_predictions": len(pred_ids),
    }


# ============================================================
# POST /reassemble — Timeline Editor re-concat clips
# ============================================================
class ReassembleRequest(BaseModel):
    """Re-concat existing clips theo thứ tự mới user chỉnh ở Timeline Editor.

    KHÔNG render lại từ AtlasCloud — chỉ FFmpeg concat + color pass + R2 upload.
    Cost: ~$0 (chỉ tốn compute server + R2 storage).

    Input:
      - parent_job_id: ID job render gốc (lấy plan + chain meta từ history)
      - clip_urls_in_order: clip URLs đã sắp theo Timeline order
      - aspect_ratio / resolution / audio_plan: optional overrides
    """
    parent_job_id: str
    clip_urls_in_order: list[str] = Field(..., min_length=1, max_length=30)
    aspect_ratio: str = "9:16"
    resolution: str = "720p"
    audio_plan: Optional[AudioPlan] = None


@router.post("/reassemble")
async def reassemble_timeline(request: ReassembleRequest):
    """Spawn reassemble job. Returns job_id polling URL giống /generate."""
    # Look up parent for color_grading hint
    parent = director_history.get_job(request.parent_job_id, include_plan=True)
    color_grading = ""
    if parent and parent.get("plan"):
        try:
            color_grading = parent["plan"]["continuity_bible"]["visual_style"]["color_grading"] or ""
        except (KeyError, TypeError):
            pass

    job_id = f"rasm_{uuid.uuid4().hex[:12]}"
    _JOBS_STORE[job_id] = {
        "status": "pending",
        "progress": 0,
        "current_step": "queued",
        "mode": "reassemble",
        "parent_job_id": request.parent_job_id,
        "created_at": datetime.now(timezone.utc).isoformat() + "Z",
    }

    async def _run():
        try:
            await reassemble_worker.reassemble(
                job_id=job_id,
                parent_job_id=request.parent_job_id,
                clip_urls_in_order=request.clip_urls_in_order,
                aspect_ratio=request.aspect_ratio,
                resolution=request.resolution,
                color_grading=color_grading,
                audio_plan=(
                    request.audio_plan.model_dump(exclude_none=True)
                    if request.audio_plan is not None else None
                ),
                jobs_store=_JOBS_STORE,
            )
        except Exception as e:
            logger.exception(f"[/director/reassemble] {job_id} failed")
            _JOBS_STORE[job_id].update(status="failed", error_message=_redact_error(e))
            await asyncio.to_thread(video_worker.cleanup_failed_job, job_id)  # Sprint3 B3

    _spawn(_run())
    return {
        "job_id": job_id,
        "polling_url": f"/api/v1/director/jobs/{job_id}",
        "mode": "reassemble",
        "parent_job_id": request.parent_job_id,
        "clip_count": len(request.clip_urls_in_order),
    }


# ============================================================
# Project History — list / detail / delete persisted jobs
# ============================================================
@router.get("/history")
async def list_history(limit: int = 50, status: Optional[str] = None):
    """List recent Director V3 jobs (persisted to data/director_history.db).

    Sorted by `finished_at` desc. Each item is a thin summary; full plan +
    chain meta available via GET /history/{job_id}.
    """
    items = director_history.list_jobs(limit=limit, status_filter=status)
    for item in items:
        item["feedback_summary"] = render_feedback_store.summarize_job_feedback(item["job_id"])
    return {"items": items}


@router.get("/history/{job_id}")
async def get_history(job_id: str):
    """Full snapshot incl. plan + chain — used by Fork / Replay."""
    item = director_history.get_job(job_id, include_plan=True)
    if not item:
        raise HTTPException(404, f"history job '{job_id}' not found")
    item["feedback_summary"] = render_feedback_store.summarize_job_feedback(job_id)
    item["feedback_entries"] = render_feedback_store.list_feedback(job_id)
    return item


@router.delete("/history/{job_id}")
async def delete_history(job_id: str):
    if not director_history.delete_job(job_id):
        raise HTTPException(404, f"history job '{job_id}' not found")
    return {"ok": True, "job_id": job_id}
