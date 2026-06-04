"""MULTI-SHOT PROMPT BUILDER — Seedance 2.0 single-call multi-shot rendering.

V6 — 7-model core. Only Seedance 2.0 family supports native multi-shot inline
notation (`[Shot N | Xs | ...]` markers in a single API call). Wan 2.7 is i2v
only and renders per-shot.

| Model            | Multi-shot inline | Per-shot chain | Max dur single-call |
|------------------|-------------------|----------------|---------------------|
| seedance_2_0     | ✅ NATIVE         | (alt)          | 15s                 |
| seedance_2_0_fast| ✅ NATIVE         | (alt)          | 15s                 |
| wan_2_7          | ❌ (i2v only)     | ✅ REQUIRED    | 5/10s               |

Strategy dispatch (V6.1 — updated for long-form):
    seedance_2_0[_fast] + duration ≤ 15s + 1-6 shots → SINGLE_CALL_MULTI_SHOT
    > 15s OR > 6 shots                                → PER_SHOT_CHAIN
    Wan 2.7                                            → PER_SHOT_CHAIN

V6.1 — Long-form support:
    Autonomous Director splits longer plans into 4-15s shots and scene/chunk
    groups, then feeds them via per_shot_chain — last_frame of shot/chunk N
    can become first frame of N+1 when continuity matters.

Sources:
  - Byteplus official Dreamina Seedance 2.0 docs (Apr 2026)
  - WaveSpeed Seedance 2.0 template (Feb 2026)
  - AtlasCloud/Seedance 2.0 docs (4-15s generation, 9img+3vid+3aud refs)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Literal
from loguru import logger

from agent.schemas import ContinuityBible, Shot, ReferenceAsset
from agent import continuity_manager
from agent.reference_manifest import build_reference_manifest, format_reference_manifest
from agent.reference_policy_optimizer import optimize_shot_references
from agent.model_specs import get_video_model_family


RenderStrategy = Literal[
    "single_call_multi_shot",   # SEEDANCE 2.0 CORE PATH — ≤15s single API call
    "per_shot_chain",           # FALLBACK PATH — Wan 2.7, long-form, cross-location
]


@dataclass
class SingleCallSpec:
    """Output of multi-shot builder — ready to feed atlas_client.generate_video."""
    prompt: str
    negative_prompt: str
    reference_image_indices: list[int]
    reference_image_urls: list[str]
    total_duration_s: int
    aspect_ratio: str
    resolution: str
    generate_audio: bool
    model_key: str
    strategy: RenderStrategy
    # Per-shot timing map (kept for downstream audio_timeline to overlay
    # TTS at correct start_s within the single rendered video)
    shot_timing: list[dict]  # [{"shot_id", "start_s", "end_s", "duration_s"}, ...]
    # SEEDANCE 2.0 CORE PATH — quad-modal refs (0-3 each)
    reference_video_urls: list[str] = field(default_factory=list)
    reference_audio_urls: list[str] = field(default_factory=list)


# ============================================================
# Strategy dispatcher — decides per-model + per-plan
# ============================================================
def pick_strategy(
    user_model: str,
    total_duration_s: int,
    num_shots: int,
    has_cross_location_cut: bool = False,
) -> RenderStrategy:
    """Decide which render strategy is optimal for this combination.

    has_cross_location_cut: if True, force per_shot mode even on Seedance
    because hard location cuts confuse single-call generators (Seedance may
    blend the two environments). Detected upstream from shot.continuity.
    previous_shot_id=None on a non-first shot (intentional cut signal).
    """
    if has_cross_location_cut:
        return "per_shot_chain"

    family = get_video_model_family(user_model)

    # SEEDANCE 2.0 CORE PATH — single-call multi-shot up to one generation.
    if family in ("seedance_2_0", "seedance_2_0_fast") and total_duration_s <= 15 and 1 <= num_shots <= 6:
        return "single_call_multi_shot"

    # FALLBACK PATH — Wan 2.7 + longer Seedance plans, auto-chunked upstream
    return "per_shot_chain"


# ============================================================
# Seedance 2.0 — multi-shot inline notation (3-section template)
# ============================================================
def build_seedance_2_multi_shot(
    bible: ContinuityBible,
    shots: list[Shot],
    reference_images: list[str],
    *,
    reference_videos: Optional[list[str]] = None,
    reference_audios: Optional[list[str]] = None,
    model_key: str = "seedance_2_0_ref",  # or seedance_2_0_fast_ref
    resolution: str = "720p",
) -> SingleCallSpec:
    """Build a SINGLE multi-shot inline prompt for Seedance 2.0 (≤15s).

    Format (industry-canonical from Byteplus/WaveSpeed/AtlasCloud):

    [STYLE & MOOD]
    <bible.visual_style block>

    [DYNAMIC DESCRIPTION]
    [Shot 1 | 2s | handheld MCU | @image_1 as primary character]
    0:00-0:02 Linh half-smile side profile, warm rim light...
    [Shot 2 | 4s | WS push-in | @image_1]
    0:02-0:06 Linh seated at desk wiping old lipstick...
    [Shot 3 | 4s | ECU pull-out | @image_2 as product]
    0:06-0:10 Lipstick on desk under golden hour light...
    [Shot 4 | 5s | MCU static | @image_1 + @image_2]
    0:10-0:15 Linh applies lipstick, confident smile...

    [STATIC DESCRIPTION]
    Same character verbatim: <face_signature>. Outfit: <invariant>.
    Location: <single environment>. NO CTA frame, NO sales imperatives.
    """
    reference_videos = list((reference_videos or [])[:3])
    reference_audios = list((reference_audios or [])[:3])

    # ---- 1. Bound references (union across shots, dedup, preserve order) ----
    seen_indices: set[int] = set()
    ordered_refs: list[ReferenceAsset] = []
    for shot in shots:
        raw_refs = continuity_manager.references_for_shot(bible, shot)
        ref_policy = optimize_shot_references(
            bible=bible,
            shot=shot,
            image_refs=raw_refs,
            reference_videos=reference_videos,
            reference_audios=reference_audios,
            model_key=model_key,
            render_mode="ref_to_video",
            max_image_refs=4,
        )
        for r in ref_policy.get("image_refs") or []:
            if r.index not in seen_indices and 0 <= r.index < len(reference_images):
                ordered_refs.append(r)
                seen_indices.add(r.index)
            if len(ordered_refs) >= 9:
                break
        if len(ordered_refs) >= 9:
            break
    ref_urls = [reference_images[r.index] for r in ordered_refs]
    reference_manifest = build_reference_manifest(
        image_refs=ordered_refs,
        video_count=len(reference_videos),
        audio_count=len(reference_audios),
        video_roles=_reference_roles_from_bible(bible, "videos"),
        audio_roles=_reference_roles_from_bible(bible, "audios"),
    )
    prompt_formula = _prompt_formula_block(bible)

    # ---- 2. Build [STYLE & MOOD] section ----
    vs = bible.visual_style
    style_block = (
        f"Photorealistic cinematic, {vs.cinematography or 'handheld UGC iPhone'}, "
        f"{vs.film_grain or 'subtle 35mm grain'}, shallow depth of field. "
        f"Palette: {vs.color_grading or 'warm filmic teal-and-orange'}. "
        f"Lighting: {vs.lighting_design or 'soft golden hour window light'}."
    )

    # ---- 3. Build [DYNAMIC DESCRIPTION] with [Shot N | Xs | ...] notation ----
    dynamic_lines: list[str] = []
    for i, shot in enumerate(shots, 1):
        v = shot.visual
        # Role-tagged @image_N references for this shot
        shot_refs = continuity_manager.references_for_shot(bible, shot)
        shot_ref_idxs = sorted({
            ordered_refs.index(r) + 1
            for r in shot_refs
            if r in ordered_refs
        })
        ref_tags = " + ".join(
            f"@image_{idx} as {_role_label(ordered_refs[idx-1].role)}"
            for idx in shot_ref_idxs
        ) if shot_ref_idxs else ""

        # Header line — the [Shot N | duration | camera | refs] markers
        header_parts = [f"Shot {i}", f"{shot.duration_s}s"]
        if v.camera_movement and v.camera_movement != "static":
            header_parts.append(f"{v.camera_shot} {v.camera_movement}")
        else:
            header_parts.append(v.camera_shot or "MCU")
        if ref_tags:
            header_parts.append(ref_tags)
        dynamic_lines.append(f"[{' | '.join(header_parts)}]")

        # V5.11 — MindStudio 6-slot beat format (Subject / Action / Setting /
        # Lighting / Camera / Style). Industry research confirms strict slot
        # ordering helps vendor LLM parse the beat → more consistent output
        # vs. the prior loose comma-separated sentence.
        dialogue_clip = ""
        if shot.audio.dialogue_vn:
            dialogue_clip = f' DIALOGUE: "{shot.audio.dialogue_vn}".'
        setting = (v.background or bible.setting.location or "neutral background").strip(". ")
        lighting = (v.lighting_override or bible.visual_style.lighting_design or "natural light").strip(". ")
        camera = f"{v.camera_shot or 'MCU'} {v.camera_movement or 'static'}".strip()
        style_brief = (bible.visual_style.cinematography or "cinematic UGC").strip(". ")
        beat_text = (
            f"{_fmt_mmss(shot.start_s)}-{_fmt_mmss(shot.end_s)} | "
            f"SUBJECT: {v.subject}. "
            f"ACTION: {v.action}. "
            f"SETTING: {setting}. "
            f"LIGHTING: {lighting}. "
            f"CAMERA: {camera}. "
            f"STYLE: {style_brief}."
            f"{dialogue_clip}"
        ).strip()
        dynamic_lines.append(beat_text)
        dynamic_lines.append("")  # blank line between shots

    dynamic_block = "\n".join(dynamic_lines).rstrip()
    if reference_videos:
        video_tags = ", ".join(
            f"@video_{i + 1} as {label}"
            for i, label in enumerate([
                "camera movement reference",
                "motion style reference",
                "shot pacing reference",
            ][:len(reference_videos)])
        )
        dynamic_block = f"{dynamic_block}\n\n[VIDEO REFERENCES]\nUse {video_tags}."
    if reference_audios:
        audio_tags = ", ".join(
            f"@audio_{i + 1} as {label}"
            for i, label in enumerate([
                "beat reference",
                "sound design reference",
                "dialogue or voice pacing reference",
            ][:len(reference_audios)])
        )
        dynamic_block = f"{dynamic_block}\n\n[AUDIO REFERENCES]\nUse {audio_tags}."

    # ---- 4. Build [STATIC DESCRIPTION] — CHARACTER_BLOCK reusable ----
    static_parts: list[str] = []
    if bible.characters:
        c = bible.characters[0]
        static_parts.append(
            f"Same character across all shots: {c.face_signature}. "
            f"Outfit: {c.outfit}. Posture: confident, relaxed."
        )
    if bible.setting and bible.setting.location:
        static_parts.append(
            f"Location: {bible.setting.location}, {bible.setting.time_of_day or ''}."
        )
    # Negatives baked in. V5.11 — added AtlasCloud Drama Workflow anti-drift
    # directives that the source code's prior anti-cuts list missed:
    #   • biomechanics violations — Seedance occasionally renders impossible
    #     elbow/knee bends on long actions; explicit ban improves anatomy.
    #   • reflection artifacts — mirrors / glass surfaces glitch the model;
    #     ban tells the model to skip when uncertain.
    #   • exit+reentry — character disappearing mid-shot then teleporting
    #     back into frame is a common multi-shot bug; this directive forces
    #     intentional stay-in-frame or clean exit.
    static_parts.append(
        "NO text overlay duplication, NO watermark, NO sudden shake, "
        "NO lens distortion, NO extra fingers, NO age indicators. "
        "NO CTA frame, NO sales imperatives in any caption. "
        "NO joint biomechanics violations (no impossible elbow/knee bends, "
        "no broken anatomy). NO impossible reflections, NO mirror artifacts. "
        "NO character exit+reentry across cuts (character must stay in frame "
        "throughout the shot, or exit cleanly without sudden reappearance)."
    )
    static_block = "\n".join(static_parts)

    # V4.7 — "one continuous shot" directive pixel-locks continuity
    # V5.11 — added double-contrast cut directive (AtlasCloud Drama Workflow):
    # between cuts, BOTH shot size AND camera mode should change simultaneously
    # so the cut reads as intentional editorial decision, not a model glitch.
    prompt = (
        f"[STYLE & MOOD]\n{style_block}\n\n"
        f"{format_reference_manifest(reference_manifest)}\n\n"
        f"{prompt_formula}"
        f"[DYNAMIC DESCRIPTION]\n{dynamic_block}\n\n"
        f"[STATIC DESCRIPTION]\n{static_block}\n\n"
        f"One continuous shot with hard cuts between timeline markers. "
        f"Maintain exact face, outfit, lighting, and color grade across all cuts. "
        f"Double-contrast cuts: between adjacent shots, change BOTH shot size "
        f"(e.g. WS→CU) AND camera mode (e.g. handheld→static) simultaneously. "
        f"Same-size or same-mode cuts read as unintentional glitches; mix both axes."
    )

    negative = continuity_manager.build_negative_prompt(bible)
    # Append phase-specific negatives (Grok V2 case studies):
    #   - "no product close-up in opening shot" — CrePal product-later rule
    #   - "no face morphing across cuts" — SkipTheEnd YouTube + awesome-seedance
    #   - "no lighting flicker between segments" — multi-shot consistency hack
    negative = (
        f"{negative}, no product close-up in opening shot, no logo in opening shot, "
        f"no face morphing across cuts, no lighting flicker between segments, "
        f"no outfit change mid-video"
    )

    # Audio decision — Seedance 2.0 native audio
    dialogue_style = (bible.audio_design.dialogue_style or "silent").lower()
    generate_audio = dialogue_style not in ("silent", "")

    shot_timing = [
        {
            "shot_id": s.shot_id,
            "start_s": s.start_s,
            "end_s": s.end_s,
            "duration_s": s.duration_s,
        }
        for s in shots
    ]

    return SingleCallSpec(
        prompt=prompt,
        negative_prompt=negative,
        reference_image_indices=[r.index for r in ordered_refs],
        reference_image_urls=ref_urls,
        total_duration_s=sum(s.duration_s for s in shots),
        aspect_ratio=bible.aspect_ratio or "9:16",
        resolution=resolution,
        generate_audio=generate_audio,
        model_key=model_key,
        strategy="single_call_multi_shot",
        shot_timing=shot_timing,
        reference_video_urls=reference_videos,
        reference_audio_urls=reference_audios,
    )


# ============================================================
# Helpers
# ============================================================
_ROLE_LABEL = {
    "character_anchor":    "primary character (exact face, hair, outfit from reference)",
    "secondary_character": "secondary character (exact appearance from reference)",
    "product_hero":        "product (exact packaging and color)",
    "product_detail":      "product detail (exact texture and label)",
    "style_reference":     "style reference (mood, color grade — do not copy subject)",
    "environment":         "environment / setting (exact location and atmosphere)",
    "brand_asset":         "brand asset / logo (preserve typography and color)",
    "unknown":             "reference",
}


def _role_label(role: Optional[str]) -> str:
    return _ROLE_LABEL.get((role or "").lower(), "reference")


def _prompt_formula_block(bible: ContinuityBible) -> str:
    meta = bible.storytelling_meta or {}
    formula = meta.get("seedance_prompt_formula")
    if not isinstance(formula, dict):
        return ""
    sequence = [
        str(item).replace("_", " ")
        for item in (formula.get("formula") or [])
        if str(item).strip()
    ][:9]
    template = formula.get("niche_template") or {}
    lines: list[str] = []
    if sequence:
        lines.append("Order: " + " -> ".join(sequence) + ".")
    if isinstance(template, dict):
        story_intent = str(template.get("story_intent") or "").strip()
        action = str(template.get("action") or "").strip()
        camera = str(template.get("camera") or "").strip()
        if story_intent:
            lines.append("Intent: " + story_intent[:180] + ".")
        if action:
            lines.append("Action rule: " + action[:160] + ".")
        if camera:
            lines.append("Camera rule: " + camera[:140] + ".")
    if not lines:
        return ""
    return "[PROMPT FORMULA]\n" + "\n".join(lines[:4]) + "\n\n"


def _fmt_mmss(seconds: float) -> str:
    """Format seconds as M:SS (industry convention for Seedance time anchors).

    Examples:
      0.0  -> "0:00"
      2.5  -> "0:02"
      15.0 -> "0:15"
      75.0 -> "1:15"
    """
    total = int(seconds)
    m = total // 60
    ss = total % 60
    return f"{m}:{ss:02d}"


# ============================================================
# Cross-location detector — force per-shot mode when needed
# ============================================================
def detect_cross_location_cut(shots: list[Shot]) -> bool:
    """Return True if the shot list has intentional hard-cuts (location/POV
    changes) that single-call Seedance cannot render cleanly.

    Heuristic: a non-first shot with `previous_shot_id == None` is the
    Director's explicit chain-reset signal. Single-call mode can't reset
    chain mid-generation, so we fall back to per_shot.
    """
    for i, s in enumerate(shots):
        if i > 0 and s.continuity.previous_shot_id is None:
            return True
    return False


def _reference_roles_from_bible(bible: ContinuityBible, modality_key: str) -> list[str]:
    """Return autonomous video/audio role assignments for prompt manifests."""
    meta = bible.storytelling_meta or {}
    role_meta = meta.get("quad_modal_reference_roles") or {}
    items = role_meta.get(modality_key) or []
    if not isinstance(items, list):
        return []
    sorted_items = sorted(
        [item for item in items if isinstance(item, dict)],
        key=lambda item: int(item.get("index") or 0),
    )
    return [str(item.get("role") or "unknown") for item in sorted_items]
