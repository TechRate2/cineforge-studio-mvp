"""Model Capabilities — derived view of model_specs.py for the Director Agent.

═══════════════════════════════════════════════════════════════════════════
V6 — 3 user-facing models only:
    seedance_2_0       — Seedance 2.0 (premium tier, $0.096/s, 9 refs, multi-shot)
    seedance_2_0_fast  — Seedance 2.0 Fast (mid tier, $0.076/s, same capability)
    wan_2_7            — Wan 2.7 i2v (driven-audio lip-sync VN, $0.10/s, 5 or 10s)
═══════════════════════════════════════════════════════════════════════════

Each user_model maps to a (ref_variant, i2v_variant, t2v_variant) triple from
VIDEO_MODEL_SPECS. The Director Agent uses `summary_for_director_prompt()` to
embed hard constraints into its LLM input so generated plans always validate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from agent.model_specs import VIDEO_MODEL_SPECS, get_video_model_family


# Map user-facing model alias → atlas spec keys per render mode
USER_MODEL_VARIANTS: dict[str, dict[str, str]] = {
    # SEEDANCE 2.0 CORE PATH
    "seedance_2_0": {
        "ref": "seedance_2_0_ref",
        "i2v": "seedance_2_0_i2v",
        "t2v": "seedance_2_0_t2v",
    },
    "seedance_2_0_fast": {
        "ref": "seedance_2_0_fast_ref",
        "i2v": "seedance_2_0_fast_i2v",
        "t2v": "seedance_2_0_fast_t2v",
    },
    # FALLBACK PATH — Wan 2.7 only has i2v (driven-audio lip-sync)
    "wan_2_7": {
        "ref": "wan_2_7_i2v",
        "i2v": "wan_2_7_i2v",
        "t2v": "wan_2_7_i2v",  # no native t2v — fall back to i2v with placeholder
    },
}


AudioMode = Literal["native", "driven", "none"]


@dataclass
class ModelCapability:
    """Aggregated capability surface for ONE user-facing model choice."""

    user_model: str
    ref_key: str
    i2v_key: str

    max_refs: int
    min_refs: int
    duration_min_s: int
    duration_max_s: int
    duration_discrete: Optional[list[int]]   # e.g. Wan = [5, 10]

    aspect_ratios: list[str]
    aspect_field_name: str
    resolutions: list[str]

    audio_mode: AudioMode
    supports_image_tags: bool                # `@image_N` in prompt body
    supports_multi_shot_prompting: bool      # `[Shot N — Xs]` markers respected
    supports_quad_modal: bool                # img + video + audio refs in 1 call
    supports_return_last_frame: bool         # for Reference Chaining

    cost_per_second_usd: float
    cost_note: str = ""

    director_notes: list[str] = field(default_factory=list)


def capabilities_for(user_model: str) -> ModelCapability:
    """Build the capability bundle for a user model. Falls back to seedance_2_0."""
    user_model = get_video_model_family(user_model)
    if user_model not in USER_MODEL_VARIANTS:
        user_model = "seedance_2_0"

    keys = USER_MODEL_VARIANTS[user_model]
    spec_ref = VIDEO_MODEL_SPECS[keys["ref"]]
    spec_i2v = VIDEO_MODEL_SPECS.get(keys["i2v"], spec_ref)

    ar_spec = spec_ref.get("aspect_ratio") or {"field_name": "ratio", "options": []}

    cap = spec_ref.get("audio_capability", "none")
    if cap not in ("native", "driven", "none"):
        cap = "none"

    # SEEDANCE 2.0 CORE PATH: image tag support
    tags = user_model.startswith("seedance_2_0")

    notes: list[str] = []
    if user_model.startswith("seedance_2_0"):
        notes.append(
            "Seedance 2.0 understands `@image_1`…`@image_9` and `@video_1`…`@video_3` "
            "tokens inline. Use them to bind each reference to a specific subject/motion."
        )
        notes.append(
            "Multi-shot inline markers `[Shot 1 — 3s] … [Shot 2 — 4s] …` "
            "work natively (single API call → multi-cut clip up to 15s)."
        )
        notes.append(
            "Quad-modal refs: pass reference_videos (camera/motion) + reference_audios "
            "(beat/lip-sync source) alongside reference_images in the same call."
        )
    elif user_model == "wan_2_7":
        notes.append(
            "FALLBACK PATH — Wan 2.7 i2v accepts EXACTLY 5 or 10 second clips. "
            "Plan shot durations as multiples of 5 or chain shots."
        )
        notes.append(
            "Wan 2.7 audio is DRIVEN by an `audio` URL (lip-sync TTS). Use this for "
            "Vietnamese talking-head dialogue — Seedance cannot lip-sync from audio URL."
        )

    duration = spec_ref["duration"]
    discrete = duration.get("discrete_values")

    return ModelCapability(
        user_model=user_model,
        ref_key=keys["ref"],
        i2v_key=keys["i2v"],
        max_refs=spec_ref.get("max_references", 1),
        min_refs=spec_ref.get("min_references", 0),
        duration_min_s=duration["min"],
        duration_max_s=duration["max"],
        duration_discrete=discrete,
        aspect_ratios=ar_spec.get("options", []),
        aspect_field_name=ar_spec.get("field_name", "ratio"),
        resolutions=spec_ref["resolution"]["options"],
        audio_mode=cap,
        supports_image_tags=tags,
        supports_multi_shot_prompting=bool(spec_ref.get("supports_multi_shot")),
        supports_quad_modal=bool(spec_ref.get("supports_quad_modal")),
        supports_return_last_frame=("return_last_frame" in spec_ref.get("extra_fields", {})),
        cost_per_second_usd=spec_ref["cost_per_second_usd"],
        director_notes=notes,
    )


def validate_shot_against_model(shot_dict: dict, cap: ModelCapability) -> list[str]:
    """Return a list of human-readable violations (empty = valid)."""
    out: list[str] = []
    dur = int(shot_dict.get("duration_s", 0))

    if dur < cap.duration_min_s or dur > cap.duration_max_s:
        out.append(
            f"duration_s={dur} ngoài range {cap.duration_min_s}-{cap.duration_max_s}s "
            f"cho model {cap.user_model}"
        )
    if cap.duration_discrete and dur not in cap.duration_discrete:
        out.append(
            f"duration_s={dur} không hợp lệ — model {cap.user_model} chỉ chấp nhận "
            f"discrete {cap.duration_discrete}s"
        )

    ref_count = len(shot_dict.get("continuity", {}).get("reference_indices") or [])
    if ref_count > cap.max_refs:
        out.append(
            f"reference_indices có {ref_count} refs nhưng {cap.user_model} max {cap.max_refs}"
        )

    return out


def summary_for_director_prompt(user_model: str) -> str:
    """Compact capability string the Director LLM can read in its input."""
    c = capabilities_for(user_model)
    parts = [
        f"user_model={c.user_model}",
        f"max_refs_per_shot={c.max_refs}",
        f"min_refs_per_shot={c.min_refs}",
        (
            f"allowed_durations={c.duration_discrete}s discrete"
            if c.duration_discrete
            else f"duration_range={c.duration_min_s}-{c.duration_max_s}s"
        ),
        f"audio_mode={c.audio_mode}",
        f"image_tags={'yes' if c.supports_image_tags else 'no'}",
        f"multi_shot_inline={'yes' if c.supports_multi_shot_prompting else 'no'}",
        f"quad_modal={'yes' if c.supports_quad_modal else 'no'}",
        f"return_last_frame={'yes' if c.supports_return_last_frame else 'no'}",
        f"aspect_ratios={c.aspect_ratios}",
    ]
    summary = "; ".join(parts)
    if c.director_notes:
        summary += " || notes: " + " ".join(c.director_notes)
    return summary
