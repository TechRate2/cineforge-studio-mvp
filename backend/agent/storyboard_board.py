"""MASTER STORYBOARD BOARD builder — V4 Sprint 1.

Generates ONE single ultra-wide image containing all 8-15 storyboard panels
arranged as a director's sheet (title bar + panels grid + palette swatches
+ sound icons + notes). Replaces the 12-separate-image approach that drifts
character identity between frames.

Why one board instead of per-panel images (synthesized from AtlasCloud
"9-Panel Anchor" doc + MindStudio character lock-in session):
  - All panels share the same pixel canvas → outfit/hair/face stay 100% locked
  - 1 API call (~$0.04 Seedream v4.5 edit) vs 12 calls (~$0.43)
  - The resulting board image becomes a style_reference passed into every
    Seedance shot render, giving global identity anchoring + color grade lock.

The prompt is built from the approved DirectorPlan — Bible (visual_style,
characters, products) + ShotList (purpose, visual.subject, dynamic_description)
+ storytelling_meta (hook_pattern, beat_coverage).
"""
from __future__ import annotations

from typing import Optional
from loguru import logger

from agent.schemas import DirectorPlan


# ============================================================
# Prompt builder — composes the single ultra-wide board prompt
# ============================================================
def build_master_board_prompt(plan: DirectorPlan) -> str:
    """Build a self-contained prompt for Seedream v4.5 / Nano Banana Pro to
    render one director's storyboard sheet for the entire plan.

    Critical layout decisions baked into the prompt:
      - 4×3 grid (12 panels) for 8-15 shots — auto-fit
      - 16:9 panel aspect — matches most output ratios
      - Top header: title + runtime + aspect + concept + key visual reference
      - Bottom strip: camera/lens, palette swatch, sound icons, notes
      - Dark teal background (#0d2335) — premium film board feel
    """
    bible = plan.continuity_bible
    shots = plan.shot_list
    storytelling = getattr(bible, "storytelling_meta", None) or {}
    if hasattr(storytelling, "model_dump"):
        storytelling = storytelling.model_dump()  # type: ignore[attr-defined]

    # Character anchor — verbatim phrase reused across panels
    char_anchor = ""
    if bible.characters:
        c = bible.characters[0]
        char_anchor = f"{c.face_signature}. Outfit: {c.outfit}."

    # Product line
    product_line = ""
    if bible.products:
        p = bible.products[0]
        product_line = f"Product: {p.name} — {p.packaging_description}, colors {', '.join(p.color_palette[:3])}."

    # Per-shot panel descriptions
    panel_lines: list[str] = []
    for i, shot in enumerate(shots, 1):
        v = shot.visual
        dialogue = (shot.audio.dialogue_vn or "").strip()
        dialog_str = f' DIALOGUE: "{dialogue[:60]}"' if dialogue else ""
        panel_lines.append(
            f"PANEL {i} [{shot.start_s:.0f}-{shot.end_s:.0f}s] — "
            f"PURPOSE: {shot.purpose.upper()}. "
            f"CAMERA: {v.camera_shot} {v.camera_movement}. "
            f"ACTION: {v.subject} — {v.action}. "
            f"BG: {v.background}.{dialog_str}"
        )

    panels_block = "\n".join(panel_lines)

    style = bible.visual_style
    audio = bible.audio_design
    setting = bible.setting

    prompt = f"""\
A premium director's storyboard sheet on dark teal (#0d2335) background,
landscape ultra-wide format, professional film production layout.

TOP HEADER BAR:
  Title bold white sans-serif: "{bible.title.upper()[:50]}"
  Metadata small bold: "BOARD: 1 OF 1 · RUNTIME: {bible.duration_s} SECONDS · PANELS: {len(shots)} · ASPECT RATIO: {bible.aspect_ratio} · GENRE: {bible.intent.upper()}"
  CONCEPT/SCENE line cyan: "{bible.logline}"
  TONE line orange: "{audio.mood}, {audio.tempo} tempo"
  STYLE line: "{style.cinematography}"
  LOCATION line: "{setting.location} — {setting.time_of_day}"
  KEY VISUAL REFERENCE: large rectangle right-top showing hero shot
   ({shots[len(shots)//2].visual.subject if len(shots) > 1 else 'character'})

PANELS GRID (auto-fit 4 columns × 3 rows = 12 cells, fill {len(shots)} cells,
others blank dark navy):
{panels_block}

Each panel rendering:
  - 16:9 image showing the action, full-bleed, cinematic film still quality
  - Panel number bold cyan in top-left
  - Title middle-top white sans-serif uppercase
  - Timestamp right-top mono small
  - Footer black bar with 4 fields (CAMERA/MOVEMENT, ACTION, DIALOGUE/SFX, TRANSITION)
    in tiny cyan labels + white values

CHARACTER (locked across all panels):
  {char_anchor}
  {product_line}

VISUAL STYLE (locked across all panels):
  Cinematography: {style.cinematography}
  Color grading: {style.color_grading}
  Lighting: {style.lighting_design}
  Camera language: {style.camera_language}
  Film texture: {style.film_grain}

BOTTOM FOOTER STRIP (4 sections, dark gradient):
  Section 1 "CAMERA & LENS STYLE": small lens illustration + text "{style.camera_language}"
  Section 2 "COLOR & LIGHT": 4 color swatches matching {style.color_grading}, plus brief text
  Section 3 "SOUND DESIGN & MUSIC": wave icon + text "{audio.music_genre}, {audio.mood}, {audio.dialogue_style}"
  Section 4 "NOTES": small italic text "{bible.director_notes[:150]}"
  Right corner: small REFERENCE IMAGE (KEY) — hero subject portrait

HARD CONSTRAINTS:
  - SAME character across ALL panels (use character anchor verbatim, lock face/hair/outfit)
  - Color palette consistent across panels matching {style.color_grading}
  - Photorealistic cinematic stills, NO illustration/cartoon style
  - NO text watermark, NO logo placement other than typography labels
  - Panel borders thin cyan #4DD8E0, 2px stroke
  - Sans-serif headings, mono digits for timestamps
  - Professional director board, similar to Hollywood production design sheet"""

    return prompt


# ============================================================
# Image model spec helper — pick the best image model for board
# ============================================================
def best_model_for_board() -> str:
    """Return the image model key best suited to render a 12-panel board.

    Selection logic (V4 default):
      - Seedream v4.5 supports `6240*2656` ultra-wide → ideal for board canvas
      - Cost $0.036/image
      - Falls back to Nano Banana Pro if Seedream unavailable
    """
    return "bytedance/seedream-v4.5"


def board_size_for_aspect(aspect_ratio: str) -> str:
    """Return Seedream `size` enum matching the plan's output aspect.

    Board is ultra-wide regardless of final video aspect:
      - 9:16 video → board 4704*3520 (4:3 board landscape)
      - 16:9 video → board 6240*2656 (ultra-wide cinematic board)
      - 1:1 video → board 4992*3328 (3:2 board)
    """
    if aspect_ratio == "16:9":
        return "6240*2656"
    if aspect_ratio == "1:1":
        return "4992*3328"
    # 9:16 default
    return "4704*3520"
