"""RoleTagger — Skill 4/5: quad-modal role binding (@image_N as main_character,
@video_N as camera_motion, @audio_N as lip-sync).

Input: list reference URLs (image / video / audio) + planner context.
Output: list TaggedReference — mỗi ref có role + canonical tag string ready
to inject into Seedance 2.0 prompt.

═══════════════════════════════════════════════════════════════════════════
ROLE TAXONOMY (sync với agent/schemas.py:ReferenceAsset.role enum):
  IMAGE roles:
    character_anchor      — primary character, face DNA
    secondary_character   — phụ
    product_hero          — sản phẩm chính
    product_detail        — sản phẩm chi tiết / macro
    style_reference       — mood / color grade reference
    environment           — setting / location
    brand_asset           — logo / packaging

  VIDEO roles (Seedance 2.0 only):
    camera_motion         — camera trajectory reference
    motion_style          — subject motion tempo/easing
    shot_pacing           — cut rhythm reference

  AUDIO roles (Seedance 2.0 only):
    beat_reference        — BGM / rhythm
    lip_sync_source       — driving audio (Wan 2.7 style)
    sfx_layer             — ambient / FX reference

═══════════════════════════════════════════════════════════════════════════
STRATEGY:
  - Default path is deterministic metadata/position fallback; no vision call.
  - Opt-in Vision LLM (Qwen3-VL via llm_router) can suggest image roles.
  - Video/audio refs: position-based default + LLM context (e.g., user mention
    "this is the camera motion" → camera_motion role)
  - Deterministic fallback: image[0]=character_anchor, image[1]=product_hero,
    image[2+]=style_reference; video[0]=camera_motion; audio[0]=beat_reference
═══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Literal, Optional

from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from vendors.llm_router import llm


# ============================================================
# Pydantic schemas
# ============================================================

ImageRole = Literal[
    "character_anchor", "secondary_character",
    "product_hero", "product_detail",
    "style_reference", "environment", "brand_asset",
    "unknown",
]
VideoRole = Literal["camera_motion", "motion_style", "shot_pacing", "unknown"]
AudioRole = Literal["beat_reference", "lip_sync_source", "sfx_layer", "unknown"]


class TaggedReference(BaseModel):
    """1 ref + assigned role + canonical Seedance tag string."""

    modality: Literal["image", "video", "audio"]
    index: int = Field(..., ge=0)
    url: str
    role: str  # one of ImageRole/VideoRole/AudioRole literals
    tag: str = Field(..., description="vd: '@image_1 as primary character'")
    confidence: float = Field(0.5, ge=0, le=1)
    notes: str = ""


class RoleTaggerInput(BaseModel):
    image_urls: list[str] = Field(default_factory=list, max_length=9)
    video_urls: list[str] = Field(default_factory=list, max_length=3)
    audio_urls: list[str] = Field(default_factory=list, max_length=3)
    # Context hints from planner + user
    niche: str = ""
    user_idea: str = ""
    use_vision_llm: bool = Field(
        False,
        description="Opt-in only. False skips vision calls and uses deterministic metadata/position fallback.",
    )


class RoleTaggerOutput(BaseModel):
    tagged: list[TaggedReference]
    # Pre-built tag suffix sentence ready to append to prompt
    prompt_tag_suffix: str = Field(
        "", description="vd: 'Use references: @image_1 as primary character, @image_2 as product.'",
    )


# ============================================================
# Role label dictionary — canonical English phrasing for Seedance prompt
# ============================================================

_IMAGE_ROLE_LABELS: dict[str, str] = {
    "character_anchor": "primary character (exact face, hair, outfit from reference)",
    "secondary_character": "secondary character (exact appearance from reference)",
    "product_hero": "product (exact packaging and color)",
    "product_detail": "product detail (exact texture and label)",
    "style_reference": "style reference (mood, color grade — do not copy subject)",
    "environment": "environment / setting (exact location and atmosphere)",
    "brand_asset": "brand asset / logo (preserve typography and color)",
    "unknown": "reference",
}

_VIDEO_ROLE_LABELS: dict[str, str] = {
    "camera_motion": "camera movement reference (match this dolly / pan / push-in trajectory)",
    "motion_style": "motion style reference (match tempo and easing)",
    "shot_pacing": "shot pacing reference (match cut rhythm)",
    "unknown": "reference video",
}

_AUDIO_ROLE_LABELS: dict[str, str] = {
    "beat_reference": "audio beat reference (match BGM rhythm)",
    "lip_sync_source": "lip-sync source audio (sync mouth to this dialogue)",
    "sfx_layer": "SFX / ambient layer reference",
    "unknown": "reference audio",
}


# ============================================================
# Vision LLM prompt for image role classification
# ============================================================

_VISION_SYSTEM_PROMPT = """Bạn là Reference Image Classifier cho Seedance 2.0 video generation.

NHIỆM VỤ: Cho danh sách ảnh tham chiếu user upload, classify role mỗi ảnh.

CONTEXT: user_idea + niche cho biết video gen về gì. Dùng thông tin này quyết role.

ROLES (chỉ pick 1 trong):
- character_anchor   : ảnh có người làm nhân vật chính (face + outfit cần preserve)
- secondary_character: nhân vật phụ
- product_hero       : sản phẩm chính (full bottle, hero shot)
- product_detail     : sản phẩm chi tiết (macro, texture, label close-up)
- style_reference    : mood/color/lighting reference (không copy subject)
- environment        : setting / location ảnh
- brand_asset        : logo / packaging close-up

OUTPUT: JSON object {"roles": ["role_1", "role_2", ...]} — list length = số ảnh,
mỗi entry là role string cho ảnh tương ứng theo thứ tự.
KHÔNG markdown fence, KHÔNG text thêm.
"""


# ============================================================
# Skill class
# ============================================================

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


class RoleTagger:
    """Skill 4/5 — Quad-modal Role Tagger."""

    name = "role_tagger"
    description = "@image_N / @video_N / @audio_N role binding for Seedance 2.0"

    async def run(self, inp: RoleTaggerInput) -> RoleTaggerOutput:
        """Tag all refs. Image roles are deterministic unless vision is explicitly enabled."""

        # ---- Image roles via vision LLM ----
        image_roles: list[str] = []
        if inp.image_urls:
            if inp.use_vision_llm:
                try:
                    image_roles = await self._classify_images_vision(inp)
                except Exception as e:
                    logger.warning(
                        f"[RoleTagger] vision LLM failed ({type(e).__name__}: {e}) "
                        f"→ deterministic fallback"
                    )
                    image_roles = self._deterministic_image_roles(len(inp.image_urls))
            else:
                image_roles = self._deterministic_image_roles(len(inp.image_urls))

        # ---- Video roles (deterministic positional) ----
        video_roles = self._deterministic_video_roles(len(inp.video_urls))

        # ---- Audio roles (deterministic positional, niche-aware) ----
        audio_roles = self._deterministic_audio_roles(
            len(inp.audio_urls), planner_audio_mode_hint=inp.niche,
        )

        # ---- Build TaggedReference list ----
        tagged: list[TaggedReference] = []
        for i, url in enumerate(inp.image_urls):
            role = image_roles[i] if i < len(image_roles) else "unknown"
            label = _IMAGE_ROLE_LABELS.get(role, _IMAGE_ROLE_LABELS["unknown"])
            tag = f"@image_{i + 1} as {label}"
            tagged.append(TaggedReference(
                modality="image", index=i, url=url, role=role, tag=tag,
                confidence=0.8 if inp.use_vision_llm else 0.5,
            ))

        for i, url in enumerate(inp.video_urls):
            role = video_roles[i] if i < len(video_roles) else "unknown"
            label = _VIDEO_ROLE_LABELS.get(role, _VIDEO_ROLE_LABELS["unknown"])
            tag = f"@video_{i + 1} as {label}"
            tagged.append(TaggedReference(
                modality="video", index=i, url=url, role=role, tag=tag,
                confidence=0.6,
            ))

        for i, url in enumerate(inp.audio_urls):
            role = audio_roles[i] if i < len(audio_roles) else "unknown"
            label = _AUDIO_ROLE_LABELS.get(role, _AUDIO_ROLE_LABELS["unknown"])
            tag = f"@audio_{i + 1} as {label}"
            tagged.append(TaggedReference(
                modality="audio", index=i, url=url, role=role, tag=tag,
                confidence=0.6,
            ))

        # ---- Build prompt tag suffix (1 sentence) ----
        if tagged:
            tag_strs = [t.tag for t in tagged]
            suffix = "Use references: " + ", ".join(tag_strs) + "."
        else:
            suffix = ""

        logger.info(
            f"[RoleTagger] images={len(inp.image_urls)} videos={len(inp.video_urls)} "
            f"audios={len(inp.audio_urls)} vision={inp.use_vision_llm}"
        )
        return RoleTaggerOutput(tagged=tagged, prompt_tag_suffix=suffix)

    # ------------------------------------------------------------
    # Vision LLM image classification
    # ------------------------------------------------------------

    async def _classify_images_vision(self, inp: RoleTaggerInput) -> list[str]:
        """Use vision LLM to classify all image refs in 1 call."""
        user_msg = json.dumps({
            "user_idea": inp.user_idea,
            "niche": inp.niche,
            "n_images": len(inp.image_urls),
            "instruction": (
                f"Classify each of the {len(inp.image_urls)} images. "
                f"Return roles list in EXACT order of input image URLs."
            ),
        }, ensure_ascii=False)

        raw = await asyncio.to_thread(
            llm.complete_with_image,
            system_prompt=_VISION_SYSTEM_PROMPT,
            user_message=user_msg,
            image_urls=inp.image_urls,
            task="vision",
            max_tokens=500,
        )
        data = _safe_parse_json(raw)
        roles = data.get("roles", [])
        if not isinstance(roles, list):
            raise ValueError(f"Vision LLM returned non-list roles: {type(roles)}")

        # Validate & coerce unknown values
        valid_roles = set(_IMAGE_ROLE_LABELS.keys())
        out = []
        for r in roles:
            r_str = str(r).strip().lower()
            if r_str in valid_roles:
                out.append(r_str)
            else:
                out.append("unknown")

        # Pad if vision LLM returned fewer than expected
        while len(out) < len(inp.image_urls):
            out.append("unknown")
        return out[:len(inp.image_urls)]

    # ------------------------------------------------------------
    # Deterministic fallbacks
    # ------------------------------------------------------------

    @staticmethod
    def _deterministic_image_roles(n: int) -> list[str]:
        """Positional fallback when vision LLM unavailable.

        Pattern: img[0] = character_anchor (most common case for UGC),
                 img[1] = product_hero, img[2+] = style_reference.
        """
        if n == 0:
            return []
        roles = ["character_anchor"]
        if n >= 2:
            roles.append("product_hero")
        roles.extend(["style_reference"] * (n - len(roles)))
        return roles[:n]

    @staticmethod
    def _deterministic_video_roles(n: int) -> list[str]:
        """Seedance convention: 1st = camera_motion, 2nd = motion_style, 3rd = shot_pacing."""
        default = ["camera_motion", "motion_style", "shot_pacing"]
        return default[:n]

    @staticmethod
    def _deterministic_audio_roles(n: int, planner_audio_mode_hint: str = "") -> list[str]:
        """Audio positional default. If niche suggests dialogue → lip_sync_source first."""
        if "drama" in planner_audio_mode_hint.lower() or "talking" in planner_audio_mode_hint.lower():
            default = ["lip_sync_source", "beat_reference", "sfx_layer"]
        else:
            default = ["beat_reference", "sfx_layer", "lip_sync_source"]
        return default[:n]


__all__ = [
    "RoleTagger", "RoleTaggerInput", "RoleTaggerOutput", "TaggedReference",
    "ImageRole", "VideoRole", "AudioRole",
]
