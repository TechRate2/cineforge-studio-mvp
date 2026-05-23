"""Scene Generation Agent — Layer 2.

Takes ONE (ContinuityBible, Shot) pair and produces a model-ready
`SceneRenderJob` that can be fed straight into `atlascloud.generate_video()`.

Two modes:
    - **llm_mode (default)**: 1 LLM call per shot using `system_prompts/scene.md`.
      The LLM returns a JSON `SceneLLMOutput` (see _SceneLLMOutput below) which
      the agent validates, sanitizes, and merges with the deterministic baseline.
    - **deterministic mode** (`llm_mode=False`): pure-function build directly
      from Bible + Shot — no LLM, no network. Useful for cost-sensitive batches.

Reference Chaining is honored on both paths: if the shot has
`continuity.previous_shot_id` set AND the caller supplies a `last_frame_url`,
the job is upgraded to `render_mode="i2v_chain"` and character refs are dropped
(the chain frame already carries identity).

Universal Reference binding is resolved through
`continuity_manager.references_for_shot()` so the same ref pool is shared by
every shot (no need to duplicate bindings per shot).

Sprint5 — 5 additive improvements (C1-C5) for Seedance 2.0 best practices:
    C1: @video_N reference tags (Seedance 2.0 supports 0-3 video refs)
    C2: Role-aware @image_N tag labels ("@image_1 as primary character …")
    C3: Cinematic vocabulary palette in scene.md (LLM-side improvement)
    C4: "Continue from previous frame:" scaffold prefix on i2v_chain mode
    C5: Full multi-shot inline notation in deterministic build
        ([Shot N | Xs | <movement> | @image_1 as <role> + @image_2 as <role>])
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional, Literal

from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from agent.schemas import ContinuityBible, Shot, ReferenceAsset
from agent import continuity_manager
from system_prompts import load as load_system_prompt
from vendors.llm_router import llm


RenderMode = Literal["ref_to_video", "i2v_chain", "t2v"]


# ============================================================
# Model-key → prompt format hint
# ============================================================
MODEL_FORMAT_HINTS: dict[str, str] = {
    "seedance_2_0_ref": "multi_shot_inline",
    "seedance_2_0_fast_ref": "multi_shot_inline",
    "seedance_2_0_i2v": "i2v_motion",
    "seedance_2_0_fast_i2v": "i2v_motion",
    "seedance_v15_pro_i2v": "time_coded",
    "vidu_q3_ref": "single_descriptive",
    "vidu_q3_mix_ref": "multi_ref_tagged",
    "wan_2_7_i2v": "i2v_motion",
}

_PROMPT_MAX_LEN = {
    "multi_shot_inline": 1200,
    "multi_ref_tagged": 1000,
    "time_coded": 800,
    "i2v_motion": 600,
    "single_descriptive": 600,
}

# Models that natively understand `@image_N` / `@imageN` token references
# in the prompt body (per AtlasCloud spec). For these we render explicit tags.
_MODELS_SUPPORT_IMAGE_TAGS = {
    "seedance_2_0_ref",
    "seedance_2_0_fast_ref",
    "vidu_q3_mix_ref",
}

# Sprint5 C1 — Models that support @video_N reference tags (camera / motion /
# pacing refs). Per Seedance 2.0 docs: 0-3 video refs via @video_1..@video_3.
# Vidu Q3 / Wan 2.7 / Seedance 1.5 do NOT support video refs.
_MODELS_SUPPORT_VIDEO_TAGS = {
    "seedance_2_0_ref",
    "seedance_2_0_fast_ref",
}

# Sprint5 C2 — Role-aware @image_N tag labels. Mirrors scene.md mapping so the
# deterministic + auto-injection path stays consistent with what the LLM is
# instructed to produce.
_ROLE_LABELS: dict[str, str] = {
    "character_anchor": "primary character (exact face, hair, outfit from reference)",
    "secondary_character": "secondary character (exact appearance from reference)",
    "product_hero": "product (exact packaging and color)",
    "product_detail": "product detail (exact texture and label)",
    "style_reference": "style reference (mood, color grade — do not copy subject)",
    "environment": "environment / setting (exact location and atmosphere)",
    "brand_asset": "brand asset / logo (preserve typography and color)",
    "unknown": "reference",
}

# Sprint5 C1 — Default labels for @video_N tags by positional slot. Seedance
# convention is: 1st video = camera movement, 2nd = motion style, 3rd = pacing.
_VIDEO_TAG_DEFAULT_LABELS: list[str] = [
    "camera movement reference (match this dolly / pan / push-in trajectory)",
    "motion style reference (match tempo and easing)",
    "shot pacing reference (match cut rhythm)",
]

# Sprint5 C4 — Chain scaffold prefix prepended to prompts in i2v_chain mode.
_CHAIN_SCAFFOLD_PREFIX = (
    "Continue from previous frame: same character, same wardrobe, same lighting, "
    "same color grade. Now: "
)


# ============================================================
# Output dataclass — what Layer 3 (video_worker) consumes
# ============================================================
@dataclass
class SceneRenderJob:
    """Output for ONE shot — feed directly into `atlascloud.generate_video()`."""

    shot_id: str
    prompt: str
    negative_prompt: str
    reference_image_urls: list[str] = field(default_factory=list)
    render_mode: RenderMode = "ref_to_video"
    chain_input_url: Optional[str] = None
    duration_s: int = 5
    resolution: str = "720p"
    aspect_ratio: str = "9:16"
    generate_audio: bool = False
    movement_amplitude: str = "auto"
    return_last_frame: bool = True
    model_key: str = "seedance_2_0_ref"
    # BUG #1 fix — driven-audio URL for Wan 2.7 lip-sync.
    # Set ONLY when audio_capability=="driven". Renderer passes via field `audio`.
    audio_url: Optional[str] = None
    # Sprint5 C1 — 0-3 reference video URLs for Seedance 2.0 (@video_N tags).
    # Models not in _MODELS_SUPPORT_VIDEO_TAGS ignore this field entirely.
    # Tags `@video_1`..`@video_3` are injected into the prompt; the URLs
    # themselves will be wired to AtlasCloud when the vendor adds the field
    # to the payload schema (build_payload is the surface area to update).
    reference_video_urls: list[str] = field(default_factory=list)

    def to_atlas_kwargs(self) -> dict:
        """Convert to kwargs for `atlas_client.generate_video()`.

        Note (Sprint5 C1): `reference_video_urls` is intentionally NOT passed
        through here yet — the AtlasCloud Python wrapper doesn't expose a
        `reference_videos` kwarg today. The @video_N tags already live in the
        prompt body so Seedance can resolve them once the payload-side wiring
        lands (see `agent/model_specs.py::build_payload`).
        """
        kwargs: dict = {
            "model_key": self.model_key,
            "prompt": self.prompt,
            "duration_s": self.duration_s,
            "resolution": self.resolution,
            "aspect_ratio": self.aspect_ratio,
            "negative_prompt": self.negative_prompt or None,
            "return_last_frame": self.return_last_frame,
            "generate_audio": self.generate_audio,
            "movement_amplitude": self.movement_amplitude,
            "audio_url": self.audio_url,
        }
        if self.render_mode == "i2v_chain" and self.chain_input_url:
            kwargs["image"] = self.chain_input_url
        elif self.reference_image_urls:
            if len(self.reference_image_urls) == 1:
                kwargs["image"] = self.reference_image_urls[0]
                kwargs["images"] = self.reference_image_urls
            else:
                kwargs["images"] = self.reference_image_urls
        return {k: v for k, v in kwargs.items() if v is not None}


# ============================================================
# LLM response schema — what scene.md is contracted to return
# ============================================================
class _SceneLLMOutput(BaseModel):
    """Strict Pydantic gate for the Layer 2 LLM JSON response."""

    prompt: str
    negative_prompt: str = ""
    reference_image_indices: list[int] = Field(default_factory=list)
    render_mode: Optional[RenderMode] = None
    chain_input_url: Optional[str] = None
    model_params: dict = Field(default_factory=dict)


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _safe_parse_json(raw: str) -> dict:
    cleaned = _FENCE_RE.sub("", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        s, e = cleaned.find("{"), cleaned.rfind("}")
        if s >= 0 and e > s:
            return json.loads(cleaned[s:e + 1])
        raise


# ============================================================
# Reference filtering — chain frame carries identity, drop char refs
# ============================================================
def _filter_refs_for_chain(
    bible: ContinuityBible,
    refs: list,
) -> list:
    """When a shot chains from a previous shot's last frame, character +
    product anchors are already baked in. Keep only style/environment refs to
    avoid the model double-binding identity (which causes drift).
    """
    keep_roles = {"style_reference", "environment", "brand_asset"}
    return [r for r in refs if r.role in keep_roles]


# ============================================================
# Sprint5 C2 — Role-aware @image_N tag builder
# ============================================================
def _build_role_aware_image_tags(bound_refs: list[ReferenceAsset]) -> str:
    """Sprint5 C2 — Build a role-labeled tag suffix for the prompt.

    Returns a sentence like:
        "Use references: @image_1 as primary character (exact face, hair, outfit from reference), "
        "@image_2 as product (exact packaging and color)."

    The order matches `bound_refs` (which is already sorted character→product
    →style by `continuity_manager.references_for_shot`).
    """
    parts: list[str] = []
    for i, r in enumerate(bound_refs, start=1):
        label = _ROLE_LABELS.get(r.role, _ROLE_LABELS["unknown"])
        tag = f"@image_{i} as {label}"
        if getattr(r, "notes", None):
            # Keep notes short — avoid blowing the per-model prompt cap.
            note = r.notes.strip()
            if note and len(note) <= 60:
                tag = f"{tag} — {note}"
        parts.append(tag)
    return "Use references: " + ", ".join(parts) + "."


def _build_video_tags(video_urls: list[str]) -> str:
    """Sprint5 C1 — Build a `@video_N` tag suffix for Seedance 2.0 ref models.

    Returns a sentence like:
        "Video references: @video_1 as camera movement reference (...), @video_2 as motion style reference (...)."
    """
    n = min(len(video_urls), 3)
    if n == 0:
        return ""
    parts: list[str] = []
    for i in range(n):
        label = _VIDEO_TAG_DEFAULT_LABELS[i] if i < len(_VIDEO_TAG_DEFAULT_LABELS) else "reference video"
        parts.append(f"@video_{i + 1} as {label}")
    return "Video references: " + ", ".join(parts) + "."


# ============================================================
# Public entry — single shot
# ============================================================
def generate_scene(
    bible: ContinuityBible,
    shot: Shot,
    model_key: str,
    reference_images: list[str],
    last_frame_url: Optional[str] = None,
    *,
    llm_mode: bool = True,
    resolution: str = "720p",
    is_last_shot: bool = False,
    driven_audio_url: Optional[str] = None,
    reference_videos: Optional[list[str]] = None,
) -> SceneRenderJob:
    """Build a `SceneRenderJob` for one shot.

    Args:
        bible:              ContinuityBible (global state).
        shot:               One `Shot` entry.
        model_key:          AtlasCloud model key (e.g. `seedance_2_0_ref`).
        reference_images:   Full ordered list of uploaded refs (indexed by
                            `Bible.reference_assets[].index`).
        last_frame_url:     Optional — caller passes the previous shot's last
                            frame URL when this shot is chained.
        llm_mode:           True (default) = 1 LLM call. False = deterministic.
        resolution:         Output resolution (e.g. `720p`).
        is_last_shot:       If True, `return_last_frame=False` (no chain after).
        driven_audio_url:   Optional pre-rendered TTS / audio URL for models
                            with `audio_capability=="driven"` (Wan 2.7). When
                            supplied, the renderer passes it as the `audio`
                            field so Wan does true lip-sync — otherwise mouth
                            movements are random and don't match the dialogue.
        reference_videos:   Sprint5 C1 — Optional 0-3 video URLs for Seedance
                            2.0 (@video_N tags: camera movement / motion style /
                            shot pacing). Ignored by all other models.
    """
    reference_videos = reference_videos or []

    # ---- Resolve render_mode -------------------------------------------------
    is_chain = bool(shot.continuity.previous_shot_id) and bool(last_frame_url)
    bound_refs = continuity_manager.references_for_shot(bible, shot)
    if is_chain:
        bound_refs = _filter_refs_for_chain(bible, bound_refs)
    ref_urls = [
        reference_images[r.index]
        for r in bound_refs
        if 0 <= r.index < len(reference_images)
    ]
    # Sprint5 C2 — Keep parallel list of ReferenceAsset for role-aware tagging
    bound_refs_filtered: list[ReferenceAsset] = [
        r for r in bound_refs if 0 <= r.index < len(reference_images)
    ]
    render_mode: RenderMode = (
        "i2v_chain" if is_chain
        else ("ref_to_video" if ref_urls else "t2v")
    )

    # ---- Audio decision (from Bible.audio_design × model capability) --------
    # Only set `generate_audio=true` for models with NATIVE audio support.
    # Wan 2.7 uses driven audio via the `audio` field — do not set
    # `generate_audio` for it (the AtlasCloud payload would be ignored at best).
    from agent.model_specs import VIDEO_MODEL_SPECS as _SPECS
    _model_spec = _SPECS.get(model_key) or {}
    _audio_cap = _model_spec.get("audio_capability", "none")
    dialogue_style = (bible.audio_design.dialogue_style or "silent").lower()
    wants_audio = dialogue_style not in ("silent", "")
    generate_audio = wants_audio and (_audio_cap == "native")

    # ---- Negative prompt baseline (deterministic) ----------------------------
    negative = continuity_manager.build_negative_prompt(bible)

    # ---- Prompt build -------------------------------------------------------
    prompt: str
    llm_negative: Optional[str] = None
    llm_render_mode: Optional[RenderMode] = None
    llm_model_params: dict = {}

    if llm_mode:
        try:
            llm_out = _llm_build(
                bible=bible, shot=shot, model_key=model_key,
                ref_urls=ref_urls,
                last_frame_url=last_frame_url if is_chain else None,
                reference_videos=reference_videos,
            )
            prompt = llm_out.prompt.strip()
            if llm_out.negative_prompt:
                llm_negative = llm_out.negative_prompt.strip()
            llm_render_mode = llm_out.render_mode
            llm_model_params = llm_out.model_params or {}

            # Allow LLM to narrow render_mode (e.g. ref→t2v if it sees nothing
            # usable), but never let it FALSELY claim "i2v_chain" when no chain
            # input is available.
            if llm_render_mode == "i2v_chain" and not last_frame_url:
                llm_render_mode = None
            if llm_render_mode in ("ref_to_video", "i2v_chain", "t2v"):
                render_mode = llm_render_mode
        except Exception as e:
            logger.warning(
                f"[SceneGen] LLM build fail for {shot.shot_id} "
                f"({type(e).__name__}: {e}) → deterministic fallback"
            )
            prompt = _deterministic_build_prompt(
                bible, shot, model_key, bound_refs_filtered, reference_videos,
            )
    else:
        prompt = _deterministic_build_prompt(
            bible, shot, model_key, bound_refs_filtered, reference_videos,
        )

    # ---- Inject @image_N tags for models that support them -------------------
    # AtlasCloud Seedance 2.0 ref + Vidu Q3 Mix bind references positionally via
    # `@image_N` tokens in the prompt body. If the LLM didn't already include
    # them (and refs are present), append a role-aware tag suffix (Sprint5 C2)
    # so the renderer knows which image to map to which subject role.
    if (
        render_mode == "ref_to_video"
        and ref_urls
        and model_key in _MODELS_SUPPORT_IMAGE_TAGS
        and "@image" not in prompt.lower()
    ):
        tag_sentence = _build_role_aware_image_tags(bound_refs_filtered)
        prompt = f"{prompt.rstrip()} {tag_sentence}"

    # Sprint5 C1 — Inject @video_N tags for Seedance 2.0 ref models when the
    # caller supplied reference videos AND the prompt doesn't already mention
    # them. Other models silently ignore reference_videos.
    if (
        render_mode in ("ref_to_video", "i2v_chain")
        and reference_videos
        and model_key in _MODELS_SUPPORT_VIDEO_TAGS
        and "@video" not in prompt.lower()
    ):
        video_sentence = _build_video_tags(reference_videos)
        if video_sentence:
            prompt = f"{prompt.rstrip()} {video_sentence}"

    # Sprint5 C4 — Chain scaffold: prepend the "Continue from previous frame:"
    # context anchor when in i2v_chain mode so the model treats the last-frame
    # as a hard anchor instead of a loose hint. Skip if the prompt already
    # starts with that prefix (LLM may have already added it per scene.md).
    if render_mode == "i2v_chain" and not prompt.lstrip().lower().startswith(
        "continue from previous frame"
    ):
        prompt = _CHAIN_SCAFFOLD_PREFIX + prompt.lstrip()

    # ---- Clamp prompt length per model ---------------------------------------
    hint = MODEL_FORMAT_HINTS.get(model_key, "single_descriptive")
    cap = _PROMPT_MAX_LEN.get(hint, 600)
    if len(prompt) > cap:
        prompt = prompt[:cap - 1].rstrip() + "…"

    # ---- Merge LLM model_params (only known/safe keys) ----------------------
    movement_amplitude = "auto"
    if isinstance(llm_model_params.get("movement_amplitude"), str):
        movement_amplitude = llm_model_params["movement_amplitude"]
    if isinstance(llm_model_params.get("generate_audio"), bool):
        generate_audio = llm_model_params["generate_audio"]

    # Wan-style driven audio: only attach when the model needs it.
    # Other models ignore this field; build_payload also drops it via spec check.
    attached_audio_url = driven_audio_url if _audio_cap == "driven" else None

    # Sprint5 C1 — Only carry reference_video_urls when the model can act on
    # them; passing them on other models is wasted bytes and a footgun for the
    # eventual build_payload wiring.
    effective_video_urls = (
        list(reference_videos[:3])
        if (reference_videos and model_key in _MODELS_SUPPORT_VIDEO_TAGS)
        else []
    )

    return SceneRenderJob(
        shot_id=shot.shot_id,
        prompt=prompt,
        negative_prompt=(llm_negative or negative),
        reference_image_urls=ref_urls if render_mode != "i2v_chain" else [],
        render_mode=render_mode,
        chain_input_url=last_frame_url if render_mode == "i2v_chain" else None,
        duration_s=shot.duration_s,
        resolution=resolution,
        aspect_ratio=bible.aspect_ratio,
        generate_audio=generate_audio,
        movement_amplitude=movement_amplitude,
        return_last_frame=not is_last_shot,
        model_key=model_key,
        audio_url=attached_audio_url,
        reference_video_urls=effective_video_urls,
    )


# ============================================================
# LLM build — with one retry on parse failure
# ============================================================
def _llm_build(
    bible: ContinuityBible,
    shot: Shot,
    model_key: str,
    ref_urls: list[str],
    last_frame_url: Optional[str],
    *,
    max_attempts: int = 2,
    reference_videos: Optional[list[str]] = None,
) -> _SceneLLMOutput:
    """Run the Layer 2 LLM call. Retry once on JSON or schema validation error.

    The system prompt is `system_prompts/scene.md` which dictates the strict
    JSON contract. We never tolerate fences or prose.
    """
    system = load_system_prompt("scene")
    payload = {
        "bible": bible.model_dump(),
        "shot": shot.model_dump(),
        "model_key": model_key,
        "model_format_hint": MODEL_FORMAT_HINTS.get(model_key, "single_descriptive"),
        "last_frame_url": last_frame_url,
        "reference_images": ref_urls,
        # Sprint5 C1 — expose video refs to the LLM so it can place @video_N
        # tags in the prompt where they make narrative sense.
        "reference_videos": reference_videos or [],
    }
    user_msg = json.dumps(payload, ensure_ascii=False)

    last_err: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            raw = llm.complete(
                system_prompt=system,
                user_message=user_msg,
                task="generator",
                max_tokens=1500,
                temperature=0.55 if attempt == 1 else 0.35,  # tighten on retry
            )
            data = _safe_parse_json(raw)
            out = _SceneLLMOutput(**data)
            if not out.prompt.strip():
                raise ValueError("empty prompt")
            return out
        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            last_err = e
            logger.warning(
                f"[SceneGen] LLM parse fail attempt {attempt}/{max_attempts} "
                f"for {shot.shot_id}: {type(e).__name__}: {str(e)[:120]}"
            )
            continue
    assert last_err is not None
    raise last_err


# ============================================================
# Deterministic build — pure function, no LLM
# ============================================================
def _deterministic_build_prompt(
    bible: ContinuityBible,
    shot: Shot,
    model_key: str,
    bound_refs: Optional[list[ReferenceAsset]] = None,
    reference_videos: Optional[list[str]] = None,
) -> str:
    """Pure-function fallback. Model-aware formatting via `MODEL_FORMAT_HINTS`.

    - `multi_shot_inline` (Seedance 2.0):    Full notation
      `[Shot N | Xs | <camera_movement> | @image_1 as <role> + @image_2 as <role>] subject. action. style.`
      (Sprint5 C5)
    - `time_coded`        (Seedance 1.5 Pro): `[0-Xs] subject. action.`
    - `i2v_motion`        (Wan / *_i2v):      motion-only phrasing.
    - `single_descriptive`(Vidu):             1 long descriptive sentence.

    Args:
        bound_refs:        Sprint5 C5 — optional list of ReferenceAsset already
                           filtered for this shot. Used to build the inline
                           `@image_N as <role>` slug in multi_shot_inline mode.
                           If None / empty, the slug is omitted.
        reference_videos:  Sprint5 C1 — optional 0-3 video URLs. Adds a
                           "@video_N as ..." suffix sentence when the model
                           supports it.
    """
    hint = MODEL_FORMAT_HINTS.get(model_key, "single_descriptive")
    bound_refs = bound_refs or []
    reference_videos = reference_videos or []

    base = (
        f"{shot.visual.subject}. {shot.visual.action}. "
        f"{shot.visual.camera_shot} {shot.visual.camera_movement}. "
        f"{shot.visual.composition}. {shot.visual.background}."
    )
    base = continuity_manager.inject_bible_context_into_prompt(bible, shot, base)

    lighting = (shot.visual.lighting_override or bible.visual_style.lighting_design or "").strip()
    if lighting:
        base += f" Lighting: {lighting}."

    if shot.audio.dialogue_vn:
        base += f' Character speaks: "{shot.audio.dialogue_vn}".'

    if hint == "multi_shot_inline":
        # Sprint5 C5 — full Seedance multi-shot inline notation.
        # Format: [Shot N | Xs | <camera_movement> | @image_1 as <role> + @image_2 as <role>]
        movement = (shot.visual.camera_movement or "static").strip()
        if bound_refs and model_key in _MODELS_SUPPORT_IMAGE_TAGS:
            ref_slug = " + ".join(
                f"@image_{i} as {_ROLE_LABELS.get(r.role, _ROLE_LABELS['unknown'])}"
                for i, r in enumerate(bound_refs, start=1)
            )
            header = f"[Shot {shot.index + 1} | {shot.duration_s}s | {movement} | {ref_slug}]"
        else:
            header = f"[Shot {shot.index + 1} | {shot.duration_s}s | {movement}]"
        return f"{header} {base}"
    if hint == "time_coded":
        return f"[{shot.start_s:.0f}-{shot.end_s:.0f}s] {base}"
    if hint == "i2v_motion":
        return (
            f"Motion: {shot.visual.action}. {shot.visual.camera_movement}. "
            f"{shot.continuity.style_anchor or bible.visual_style.camera_language}."
        ).strip()
    return base


# ============================================================
# Batch — all shots in a plan
# ============================================================
def generate_all_scenes(
    bible: ContinuityBible,
    shots: list[Shot],
    reference_images: list[str],
    model_key_per_shot: dict[str, str],
    last_frame_urls: Optional[dict[str, str]] = None,
    *,
    resolution: str = "720p",
    llm_mode: bool = True,
    reference_videos: Optional[list[str]] = None,
) -> list[SceneRenderJob]:
    """Build a `SceneRenderJob` for every shot in `shots`.

    NOTE on Reference Chaining:
        At plan-build time the caller usually does NOT know the previous shot's
        `last_frame_url` (it only exists after the previous render call). So
        `last_frame_urls` will typically be empty during planning. The render
        loop in `workers/video_worker.py` therefore re-invokes
        `generate_scene()` per shot as it walks the chain — supplying the live
        `last_frame_url` at that moment.

        This batch entry is still useful for:
          • cost/length preview before render
          • offline export of all per-shot prompts (eg. for human review)
          • running with `llm_mode=False` to get deterministic baselines.

    Args:
        bible:                Continuity Bible.
        shots:                Shot list (post-validate).
        reference_images:     Full ordered ref pool.
        model_key_per_shot:   Map `shot_id → AtlasCloud model_key`.
        last_frame_urls:      Optional map `shot_id → URL`. Empty if not chained yet.
        resolution:           Render resolution.
        llm_mode:             True = LLM per shot. False = deterministic.
        reference_videos:     Sprint5 C1 — optional 0-3 video refs shared across
                              all shots (Seedance 2.0 only).
    """
    last_frame_urls = last_frame_urls or {}
    jobs: list[SceneRenderJob] = []
    n = len(shots)
    for i, s in enumerate(shots):
        model_key = model_key_per_shot.get(s.shot_id, "seedance_2_0_ref")
        lfu = last_frame_urls.get(s.shot_id)
        jobs.append(generate_scene(
            bible=bible,
            shot=s,
            model_key=model_key,
            reference_images=reference_images,
            last_frame_url=lfu,
            llm_mode=llm_mode,
            resolution=resolution,
            is_last_shot=(i == n - 1),
            reference_videos=reference_videos,
        ))
    return jobs


__all__ = [
    "SceneRenderJob",
    "RenderMode",
    "MODEL_FORMAT_HINTS",
    "generate_scene",
    "generate_all_scenes",
]
