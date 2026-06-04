"""Seedance 2.0 reference manifest helpers.

Seedance 2.0 is strongest when each image/video/audio reference has one clear
job in the prompt. This module turns the media pool into explicit @image_N,
@video_N, and @audio_N bindings that can be passed to both LLM and deterministic
prompt builders.
"""
from __future__ import annotations

from typing import Any, Optional

from agent.schemas import ReferenceAsset


IMAGE_ROLE_LABELS: dict[str, str] = {
    "character_anchor": "primary character identity: face, hair, outfit, body language",
    "secondary_character": "secondary character identity: exact appearance",
    "product_hero": "product hero: packaging, geometry, colors, label fidelity",
    "product_detail": "product detail: texture, material, close-up label fidelity",
    "style_reference": "visual style: mood, color grade, lighting, composition",
    "environment": "environment: location, atmosphere, spatial layout",
    "brand_asset": "brand asset: logo, typography, color system",
    "unknown": "general visual reference",
}

VIDEO_ROLE_LABELS_BY_ROLE: dict[str, str] = {
    "camera_motion": "camera movement reference: dolly, pan, push-in, orbit, handheld feel",
    "motion_style": "motion style reference: action timing, body movement, physical rhythm",
    "shot_pacing": "edit pacing reference: cut rhythm, transition timing, tempo",
    "unknown": "video reference: visual motion and timing",
}

VIDEO_ROLE_FALLBACKS: list[str] = ["camera_motion", "motion_style", "shot_pacing"]

AUDIO_ROLE_LABELS_BY_ROLE: dict[str, str] = {
    "beat_reference": "beat reference: tempo, rhythm, emotional pacing",
    "sfx_layer": "sound design reference: foley texture, impact moments, ambience",
    "lip_sync_source": "voice/dialogue reference: pacing and emotion, not identity cloning",
    "unknown": "audio reference: sound mood and timing",
}

AUDIO_ROLE_FALLBACKS: list[str] = ["beat_reference", "sfx_layer", "lip_sync_source"]


def build_reference_manifest(
    *,
    image_refs: Optional[list[ReferenceAsset]] = None,
    video_count: int = 0,
    audio_count: int = 0,
    video_roles: Optional[list[str]] = None,
    audio_roles: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Build a compact manifest for prompt injection and LLM payloads."""
    images: list[dict[str, str]] = []
    for i, ref in enumerate(image_refs or [], start=1):
        role = (ref.role or "unknown").lower()
        label = IMAGE_ROLE_LABELS.get(role, IMAGE_ROLE_LABELS["unknown"])
        notes = (getattr(ref, "notes", "") or "").strip()
        if "MASTER BOARD" in notes:
            label = "master board: global character, wardrobe, lighting, and color DNA"
        images.append({
            "tag": f"@image_{i}",
            "role": role,
            "label": label,
            "notes": notes[:120],
        })

    videos: list[dict[str, str]] = []
    for i in range(max(0, min(video_count, 3))):
        role = _role_at(video_roles, VIDEO_ROLE_FALLBACKS, i)
        videos.append({
            "tag": f"@video_{i + 1}",
            "role": role,
            "label": VIDEO_ROLE_LABELS_BY_ROLE.get(role, VIDEO_ROLE_LABELS_BY_ROLE["unknown"]),
        })

    audios: list[dict[str, str]] = []
    for i in range(max(0, min(audio_count, 3))):
        role = _role_at(audio_roles, AUDIO_ROLE_FALLBACKS, i)
        audios.append({
            "tag": f"@audio_{i + 1}",
            "role": role,
            "label": AUDIO_ROLE_LABELS_BY_ROLE.get(role, AUDIO_ROLE_LABELS_BY_ROLE["unknown"]),
        })

    return {
        "images": images,
        "videos": videos,
        "audios": audios,
        "instruction": (
            "Use each @reference only for its assigned role. Do not mix identity, "
            "product, camera, and audio responsibilities across references."
        ),
    }


def format_reference_manifest(manifest: dict[str, Any]) -> str:
    """Format a concise Seedance prompt block."""
    lines: list[str] = ["[REFERENCE MANIFEST]"]
    for item in manifest.get("images") or []:
        note = f" Notes: {item['notes']}" if item.get("notes") else ""
        lines.append(f"{item['tag']} = {item['label']}.{note}")
    for item in manifest.get("videos") or []:
        lines.append(f"{item['tag']} = {item.get('label') or item['role']}.")
    for item in manifest.get("audios") or []:
        lines.append(f"{item['tag']} = {item.get('label') or item['role']}.")
    lines.append(str(manifest.get("instruction") or "").strip())
    return "\n".join(line for line in lines if line.strip())


def format_reference_manifest_inline(manifest: dict[str, Any]) -> str:
    """Format a shorter one-line block for prompt suffixes."""
    parts: list[str] = []
    for item in manifest.get("images") or []:
        parts.append(f"{item['tag']} as {item['label']}")
    for item in manifest.get("videos") or []:
        parts.append(f"{item['tag']} as {item.get('label') or item['role']}")
    for item in manifest.get("audios") or []:
        parts.append(f"{item['tag']} as {item.get('label') or item['role']}")
    if not parts:
        return ""
    return "Reference manifest: " + "; ".join(parts) + "."


def _role_at(
    explicit_roles: Optional[list[str]],
    fallback_roles: list[str],
    index: int,
) -> str:
    if explicit_roles and index < len(explicit_roles):
        role = str(explicit_roles[index] or "").strip().lower()
        if role:
            return role
    if index < len(fallback_roles):
        return fallback_roles[index]
    return "unknown"


__all__ = [
    "build_reference_manifest",
    "format_reference_manifest",
    "format_reference_manifest_inline",
]
