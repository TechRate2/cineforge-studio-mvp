"""MULTI-SHOT PROMPT BUILDER — Seedance 2.0 single-call multi-shot rendering.

V6 — 7-model core. Only Seedance 2.0 family supports native multi-shot inline
notation (`[Shot N | Xs | ...]` markers in a single API call). Wan 2.7 is i2v
only and renders per-shot.

| Model            | Multi-shot inline | Per-shot chain | Max dur |
|------------------|-------------------|----------------|---------|
| seedance_2_0     | ✅ NATIVE         | (alt)          | 15s     |
| seedance_2_0_fast| ✅ NATIVE         | (alt)          | 15s     |
| wan_2_7          | ❌ (i2v only)     | ✅ REQUIRED    | 5/10s   |

Strategy dispatch:
    seedance_2_0[_fast] + duration ≤ 15s + 1-6 shots → SINGLE_CALL_MULTI_SHOT
    All other combos                                  → PER_SHOT_CHAIN

Sources:
  - Byteplus official Dreamina Seedance 2.0 docs (Apr 2026)
  - WaveSpeed Seedance 2.0 template (Feb 2026)
  - awesome-seedance-2-prompts repo
  - AtlasCloud drama workflow (3-section + multi-shot)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Literal
from loguru import logger

from agent.schemas import ContinuityBible, Shot, ReferenceAsset
from agent import continuity_manager


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

    # SEEDANCE 2.0 CORE PATH — single-call multi-shot
    if user_model in ("seedance_2_0", "seedance_2_0_fast") and total_duration_s <= 15 and 1 <= num_shots <= 6:
        return "single_call_multi_shot"

    # FALLBACK PATH — Wan 2.7 + edge cases
    return "per_shot_chain"


# ============================================================
# Seedance 2.0 — multi-shot inline notation (3-section template)
# ============================================================
def build_seedance_2_multi_shot(
    bible: ContinuityBible,
    shots: list[Shot],
    reference_images: list[str],
    *,
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
    # ---- 1. Bound references (union across shots, dedup, preserve order) ----
    seen_indices: set[int] = set()
    ordered_refs: list[ReferenceAsset] = []
    for shot in shots:
        for r in continuity_manager.references_for_shot(bible, shot):
            if r.index not in seen_indices and 0 <= r.index < len(reference_images):
                ordered_refs.append(r)
                seen_indices.add(r.index)
    ref_urls = [reference_images[r.index] for r in ordered_refs]

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
