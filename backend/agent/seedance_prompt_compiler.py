"""Seedance 2.0 prompt compiler.

Seedance performs best when every media asset has a clear job and each shot is
described as a small piece of direction instead of a vague paragraph. This
compiler normalizes LLM or deterministic shot prompts into a stable format:

    reference jobs -> timeline -> environment -> visual style -> physical action
    -> camera/sound -> shot contract -> constraints

The output stays plain text because AtlasCloud/Seedance prompt fields are text,
but the sections make the intent easy for the vendor-side prompt parser to
follow and easy for QA/benchmarks to inspect later.
"""
from __future__ import annotations

from typing import Any, Optional

from agent.schemas import ContinuityBible, Shot


def compile_seedance_scene_prompt(
    *,
    bible: ContinuityBible,
    shot: Shot,
    base_prompt: str,
    reference_manifest: Optional[dict[str, Any]] = None,
    render_mode: str = "ref_to_video",
    model_key: str = "",
    last_frame_url: Optional[str] = None,
) -> str:
    """Return a concise, role-explicit Seedance prompt for one shot."""
    if not model_key.startswith("seedance_2_0"):
        return base_prompt

    if "[REFERENCE JOBS]" in base_prompt.upper():
        return base_prompt

    manifest = reference_manifest or {}
    lines: list[str] = []

    reference_jobs = _reference_jobs(manifest, render_mode, last_frame_url)
    if reference_jobs:
        lines.append("[REFERENCE JOBS]")
        lines.extend(reference_jobs)

    formula_lines = _prompt_formula_lines(bible)
    if formula_lines:
        lines.append("[PROMPT FORMULA]")
        lines.extend(formula_lines)

    lines.append("[TIMELINE]")
    lines.append(
        f"{_fmt_mmss(shot.start_s)}-{_fmt_mmss(shot.end_s)} "
        f"({int(shot.duration_s)}s): {shot.purpose or 'story beat'}."
    )

    environment = _environment_line(bible, shot)
    if environment:
        lines.append("[ENVIRONMENT]")
        lines.append(environment)

    visual_style = _visual_style_lines(bible, shot)
    if visual_style:
        lines.append("[VISUAL STYLE]")
        lines.extend(visual_style)

    lines.append("[SHOT DIRECTION]")
    lines.append(f"Subject: {_clean(shot.visual.subject, 160)}.")
    lines.append(f"Action: {_clean(shot.visual.action, 220)}.")
    if shot.visual.background or bible.setting.location:
        lines.append(
            f"Setting: {_clean(shot.visual.background or bible.setting.location, 180)}."
        )
    lighting = shot.visual.lighting_override or bible.visual_style.lighting_design
    if lighting:
        lines.append(f"Lighting: {_clean(lighting, 160)}.")

    lines.append("[CAMERA AND SOUND]")
    camera = " ".join(
        part for part in [shot.visual.camera_shot, shot.visual.camera_movement]
        if part
    ).strip() or "controlled cinematic camera"
    lines.append(f"Camera: {_clean(camera, 140)}.")
    if shot.visual.composition:
        lines.append(f"Composition: {_clean(shot.visual.composition, 160)}.")
    sound = _sound_line(bible, shot)
    if sound:
        lines.append(f"Sound: {sound}.")

    contract = _shot_contract_lines(bible, shot, render_mode, bool(reference_jobs))
    if contract:
        lines.append("[SHOT CONTRACT]")
        lines.extend(contract)

    director_intent = _clean(base_prompt, 320)
    if director_intent:
        lines.append("[DIRECTOR INTENT]")
        lines.append(director_intent)

    constraints = _constraints(bible)
    if constraints:
        lines.append("[CONSTRAINTS]")
        lines.append(constraints)

    return "\n".join(line for line in lines if line.strip())


def _prompt_formula_lines(bible: ContinuityBible) -> list[str]:
    meta = bible.storytelling_meta or {}
    formula = meta.get("seedance_prompt_formula")
    if not isinstance(formula, dict):
        return []
    sequence = [
        str(item).replace("_", " ")
        for item in (formula.get("formula") or [])
        if str(item).strip()
    ][:9]
    lines: list[str] = []
    if sequence:
        lines.append("Follow this order: " + " -> ".join(sequence) + ".")
    template = formula.get("niche_template") or {}
    if isinstance(template, dict):
        intent = _clean(template.get("story_intent"), 160)
        action = _clean(template.get("action"), 140)
        camera = _clean(template.get("camera"), 120)
        if intent:
            lines.append(f"Niche intent: {intent}.")
        if action:
            lines.append(f"Niche action rule: {action}.")
        if camera:
            lines.append(f"Niche camera rule: {camera}.")
    return lines[:4]


def _reference_jobs(
    manifest: dict[str, Any],
    render_mode: str,
    last_frame_url: Optional[str],
) -> list[str]:
    if render_mode == "i2v_chain" and last_frame_url:
        return [
            "Use the previous last frame as the hard continuity anchor: same identity, wardrobe, lighting, and color grade.",
        ]

    jobs: list[str] = []
    for item in manifest.get("images") or []:
        tag = str(item.get("tag") or "").strip()
        label = str(item.get("label") or "").strip()
        if tag and label:
            jobs.append(f"{tag}: {label}.")
    for item in manifest.get("videos") or []:
        tag = str(item.get("tag") or "").strip()
        label = str(item.get("label") or item.get("role") or "").strip()
        if tag and label:
            jobs.append(f"{tag}: {label}.")
    for item in manifest.get("audios") or []:
        tag = str(item.get("tag") or "").strip()
        label = str(item.get("label") or item.get("role") or "").strip()
        if tag and label:
            jobs.append(f"{tag}: {label}.")

    if jobs:
        jobs.append(
            "Use each reference only for its assigned job; do not mix identity, product, camera, and audio roles."
        )
    return jobs


def _environment_line(bible: ContinuityBible, shot: Shot) -> str:
    parts: list[str] = []
    background = _clean(shot.visual.background, 120)
    if background:
        parts.append(f"Shot space: {background}")
    location = _clean(bible.setting.location, 100)
    if location:
        parts.append(f"Location anchor: {location}")
    if bible.setting.time_of_day:
        parts.append(f"Time: {_clean(bible.setting.time_of_day, 60)}")
    if bible.setting.atmosphere:
        parts.append(f"Atmosphere: {_clean(bible.setting.atmosphere, 90)}")
    if not parts:
        return ""
    return "; ".join(parts) + "."


def _visual_style_lines(bible: ContinuityBible, shot: Shot) -> list[str]:
    style = bible.visual_style
    lines: list[str] = []
    if style.cinematography:
        lines.append(f"Cinematography: {_clean(style.cinematography, 120)}.")
    if style.color_grading:
        lines.append(f"Color grade: {_clean(style.color_grading, 100)}.")
    camera_language = shot.continuity.style_anchor or style.camera_language
    if camera_language:
        lines.append(f"Continuity style anchor: {_clean(camera_language, 140)}.")
    return lines


def _sound_line(bible: ContinuityBible, shot: Shot) -> str:
    parts: list[str] = []
    if shot.audio.dialogue_vn:
        parts.append(f'dialogue "{_clean(shot.audio.dialogue_vn, 120)}"')
    if shot.audio.sfx:
        parts.append("SFX " + ", ".join(_clean(x, 40) for x in shot.audio.sfx[:3]))
    if shot.audio.music_cue:
        parts.append("music " + _clean(shot.audio.music_cue, 80))
    elif bible.audio_design.music_genre:
        parts.append("music " + _clean(bible.audio_design.music_genre, 80))
    return "; ".join(parts)


def _shot_contract_lines(
    bible: ContinuityBible,
    shot: Shot,
    render_mode: str,
    has_reference_jobs: bool,
) -> list[str]:
    lines = [
        "Render exactly one physically filmable action in this 4-15s Seedance unit.",
        "Preserve identity, product geometry, wardrobe, lighting, and color grade across the full shot.",
        "Do not introduce unrequested characters, logos, text overlays, locations, claims, or scene jumps.",
    ]
    if shot.continuity.previous_shot_id:
        lines.append(
            f"Continue from previous shot {shot.continuity.previous_shot_id}; match final-frame pose, screen direction, camera height, and scene state."
        )
    if has_reference_jobs or shot.continuity.reference_indices:
        lines.append("Use assigned references as anchors only; keep identity, camera, product, and audio roles separate.")
    if render_mode == "i2v_chain":
        lines.append("Treat the input image or last frame as the first frame of this shot, not as loose inspiration.")
    avoid = [
        _clean(x, 80)
        for x in (bible.constraints.must_avoid or [])
        if str(x).strip()
    ][:4]
    if avoid:
        lines.append("Avoid: " + "; ".join(avoid) + ".")
    return lines


def _constraints(bible: ContinuityBible) -> str:
    keep = [
        "keep one physically filmable action per shot",
        "preserve identity, product geometry, wardrobe, lighting, and style continuity",
    ]
    avoid = [
        _clean(x, 56)
        for x in (bible.constraints.must_avoid or [])
        if str(x).strip()
    ][:6]
    if avoid:
        keep.append("avoid " + "; ".join(avoid))
    return ". ".join(keep) + "."


def _clean(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").replace("\n", " ").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _fmt_mmss(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    return f"{total // 60}:{total % 60:02d}"


__all__ = ["compile_seedance_scene_prompt"]
