"""Model Capabilities — derived view of model_specs.py for the Director Agent.

The Director needs to know each model's hard constraints (max refs, allowed
durations, native vs driven audio, whether `@image_N` tags work, etc.) BEFORE
it plans a video — otherwise it produces a plan that the renderer can't
execute (e.g. a 7s shot routed to Wan 2.7 which only accepts 5 or 10).

This module is a small adapter on top of `model_specs.VIDEO_MODEL_SPECS`. It
exposes:

    - `capabilities_for(user_model)`         → ModelCapability dataclass
    - `validate_shot_against_model(shot, c)` → list[str] of violations
    - `summary_for_director_prompt(user_model)` → human-readable string the
                                                   Director LLM consumes

KHÔNG hardcode — read from the verified `VIDEO_MODEL_SPECS` source.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from agent.model_specs import VIDEO_MODEL_SPECS


# Map user-facing model alias → (ref_variant_key, i2v_variant_key)
USER_MODEL_VARIANTS: dict[str, dict[str, str]] = {
    "vidu_q3": {
        "ref": "vidu_q3_ref",
        # Vidu has NO native i2v — for chaining, re-use vidu_q3_ref and pass
        # the previous shot's last frame INSIDE the `images` array as an
        # additional reference. Cross-family fallback to wan_2_7_i2v causes
        # identity drift and must be avoided.
        "i2v": "vidu_q3_ref",
    },
    "vidu_q3_mix": {
        "ref": "vidu_q3_mix_ref",
        "i2v": "vidu_q3_mix_ref",  # same — chain via ref array
    },
    "wan_2_7": {
        "ref": "wan_2_7_i2v",   # Wan only has i2v
        "i2v": "wan_2_7_i2v",
    },
    "seedance_1_5_pro": {
        "ref": "seedance_v15_pro_i2v",
        "i2v": "seedance_v15_pro_i2v",
    },
    "seedance_2_0": {
        "ref": "seedance_2_0_ref",
        "i2v": "seedance_2_0_i2v",
    },
    "seedance_2_0_fast": {
        "ref": "seedance_2_0_fast_ref",
        "i2v": "seedance_2_0_fast_i2v",
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
    aspect_field_name: str                    # "ratio" or "aspect_ratio"
    resolutions: list[str]

    audio_mode: AudioMode                     # native | driven | none
    supports_image_tags: bool                 # `@image_N` in prompt body
    supports_multi_shot_prompting: bool       # `[Shot N — Xs]` markers respected
    supports_return_last_frame: bool          # for Reference Chaining

    cost_per_second_usd: float
    cost_note: str = ""

    # Free-form notes the Director LLM can quote verbatim
    director_notes: list[str] = field(default_factory=list)


def capabilities_for(user_model: str) -> ModelCapability:
    """Build the capability bundle for a user model. Falls back to seedance_2_0."""
    if user_model == "auto" or user_model not in USER_MODEL_VARIANTS:
        user_model = "seedance_2_0"

    keys = USER_MODEL_VARIANTS[user_model]
    spec_ref = VIDEO_MODEL_SPECS[keys["ref"]]
    spec_i2v = VIDEO_MODEL_SPECS.get(keys["i2v"], spec_ref)

    ar_spec = spec_ref.get("aspect_ratio") or {"field_name": "ratio", "options": []}

    # Audio capability
    cap = spec_ref.get("audio_capability", "none")
    if cap not in ("native", "driven", "none"):
        cap = "none"

    # Image tag support (only Seedance 2.0 ref + Vidu Q3 Mix per AtlasCloud spec)
    tags = keys["ref"] in {
        "seedance_2_0_ref", "seedance_2_0_fast_ref", "vidu_q3_mix_ref",
    }

    # Director notes that explain the model in 1–2 lines
    notes: list[str] = []
    if user_model.startswith("seedance_2_0"):
        notes.append(
            "Seedance 2.0 understands `@image_1`…`@image_9` tokens inline in the prompt; "
            "use them to bind each reference to a specific subject."
        )
        notes.append(
            "Multi-shot inline markers like `[Shot 1 — 3s] … [Shot 2 — 4s] …` "
            "work natively (single API call → multi-cut clip)."
        )
    if user_model == "wan_2_7":
        notes.append(
            "Wan 2.7 accepts EXACTLY 5 or 10 second clips. Plan shot durations "
            "as multiples of 5 or split into chained shots."
        )
        notes.append(
            "Wan 2.7 audio is DRIVEN by an `audio` URL (lip-sync) — do NOT use "
            "`generate_audio` flag, supply a pre-rendered TTS clip instead."
        )
    if user_model.startswith("vidu_q3") and user_model != "vidu_q3_mix":
        notes.append(
            "Vidu Q3 (non-Mix) does NOT parse `@image_N` tags. References bind by "
            "ARRAY ORDER — put the primary subject first."
        )
    if user_model == "vidu_q3_mix":
        notes.append(
            "Vidu Q3 Mix DOES understand `@image_N` tags. Use them for clarity "
            "when binding multiple subjects."
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
        supports_return_last_frame=("return_last_frame" in spec_ref.get("extra_fields", {})),
        cost_per_second_usd=spec_ref["cost_per_second_usd"],
    )


def validate_shot_against_model(shot_dict: dict, cap: ModelCapability) -> list[str]:
    """Return a list of human-readable violations (empty = valid).

    Caller (Director Agent / Continuity Manager) uses this to flag plans that
    cannot be rendered as-is. We do NOT raise — return warnings so the
    Director can re-plan in a single LLM round-trip.
    """
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
    """Compact capability string the Director LLM can read in its input.

    Embedded into `tech_config.model_capability_notes` so the system prompt
    can quote the constraints without needing a separate fine-tune.
    """
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
        f"return_last_frame={'yes' if c.supports_return_last_frame else 'no'}",
        f"aspect_ratios={c.aspect_ratios}",
    ]
    summary = "; ".join(parts)
    if c.director_notes:
        summary += " || notes: " + " ".join(c.director_notes)
    return summary
