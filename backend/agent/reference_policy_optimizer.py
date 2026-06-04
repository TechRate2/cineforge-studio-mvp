"""Per-shot reference policy optimizer for Seedance 2.0.

Seedance 2.0 can accept many references, but better results usually come from
fewer references with clearer jobs. This module narrows image/video/audio refs
for one shot while preserving the production bible contract.
"""
from __future__ import annotations

from typing import Any

from agent.schemas import ContinuityBible, ReferenceAsset, Shot


_IMAGE_ROLE_ORDER = {
    "master_board": -1,
    "character_anchor": 0,
    "secondary_character": 1,
    "product_hero": 2,
    "product_detail": 3,
    "brand_asset": 4,
    "style_reference": 5,
    "environment": 6,
    "unknown": 8,
}


def optimize_shot_references(
    *,
    bible: ContinuityBible,
    shot: Shot,
    image_refs: list[ReferenceAsset],
    reference_videos: list[str] | None = None,
    reference_audios: list[str] | None = None,
    model_key: str = "",
    render_mode: str = "ref_to_video",
    max_image_refs: int = 9,
) -> dict[str, Any]:
    """Return a narrowed, role-aware reference set for a single shot."""
    reference_videos = list((reference_videos or [])[:3])
    reference_audios = list((reference_audios or [])[:3])
    max_image_refs = max(1, min(int(max_image_refs or 1), 9))

    selected_images = _select_image_refs(
        bible=bible,
        shot=shot,
        refs=image_refs,
        render_mode=render_mode,
        max_refs=max_image_refs,
    )
    selected_video_indices = _select_video_indices(
        bible=bible,
        shot=shot,
        n=len(reference_videos),
        model_key=model_key,
        render_mode=render_mode,
    )
    selected_audio_indices = _select_audio_indices(
        bible=bible,
        shot=shot,
        n=len(reference_audios),
        model_key=model_key,
    )
    selected_videos = [reference_videos[i] for i in selected_video_indices if i < len(reference_videos)]
    selected_audios = [reference_audios[i] for i in selected_audio_indices if i < len(reference_audios)]

    return {
        "image_refs": selected_images,
        "reference_videos": selected_videos,
        "reference_audios": selected_audios,
        "policy": {
            "schema_version": "cinejelly.reference_policy.v1",
            "shot_id": shot.shot_id,
            "model_key": model_key,
            "render_mode": render_mode,
            "image_roles": [_ref_role(r) for r in selected_images],
            "image_indices": [r.index for r in selected_images],
            "video_indices": selected_video_indices,
            "audio_indices": selected_audio_indices,
            "reason": _policy_reason(shot, selected_images, selected_video_indices, selected_audio_indices),
        },
    }


def _select_image_refs(
    *,
    bible: ContinuityBible,
    shot: Shot,
    refs: list[ReferenceAsset],
    render_mode: str,
    max_refs: int,
) -> list[ReferenceAsset]:
    if not refs:
        return []
    if render_mode == "i2v_chain":
        keep = [r for r in refs if _ref_role(r) in {"master_board", "style_reference", "environment", "brand_asset"}]
        return _dedupe_sorted(keep, max_refs=min(max_refs, 3))

    scored: list[tuple[int, ReferenceAsset]] = []
    needs_product = bool(shot.continuity.product_ids) or _contains_any(
        _shot_text(shot),
        ["product", "packaging", "logo", "label", "sku", "feature", "demo", "proof", "review", "unbox"],
    )
    needs_character = bool(shot.continuity.character_ids) or bool(bible.characters)
    needs_environment = _contains_any(
        _shot_text(shot),
        ["location", "room", "street", "home", "store", "restaurant", "travel", "hotel", "office", "scene"],
    )
    needs_style = True

    for ref in refs:
        role = _ref_role(ref)
        score = _IMAGE_ROLE_ORDER.get(role, 8) * 10
        if role == "master_board":
            score -= 80
        if role in {"character_anchor", "secondary_character"} and needs_character:
            score -= 35
        if role in {"product_hero", "product_detail", "brand_asset"} and needs_product:
            score -= 35
        if role == "environment" and needs_environment:
            score -= 25
        if role == "style_reference" and needs_style:
            score -= 10
        if ref.index in shot.continuity.reference_indices:
            score -= 5
        scored.append((score, ref))

    ordered = [ref for _, ref in sorted(scored, key=lambda item: (item[0], item[1].index))]
    selected = _dedupe_sorted(ordered, max_refs=max_refs)

    # Guarantee at least one style/environment ref when there is no visual anchor.
    if len(selected) < max_refs and not any(_ref_role(r) in {"style_reference", "environment"} for r in selected):
        for ref in refs:
            if _ref_role(ref) in {"style_reference", "environment"} and ref.index not in {r.index for r in selected}:
                selected.append(ref)
                break
    return selected[:max_refs]


def _select_video_indices(
    *,
    bible: ContinuityBible,
    shot: Shot,
    n: int,
    model_key: str,
    render_mode: str,
) -> list[int]:
    if n <= 0 or "seedance_2_0" not in model_key:
        return []
    if render_mode == "t2v":
        return []
    roles = _modal_roles(bible, "videos", n)
    text = _shot_text(shot)
    wanted: list[str] = []
    if shot.visual.camera_movement and shot.visual.camera_movement.lower() not in {"static", "locked"}:
        wanted.append("camera_motion")
    if _contains_any(text, ["walk", "run", "dance", "pour", "open", "move", "transition", "gesture", "hands"]):
        wanted.append("motion_style")
    if _contains_any(text, ["cut", "beat", "music", "transition", "montage", "reveal"]):
        wanted.append("shot_pacing")
    if not wanted:
        wanted = ["camera_motion"]
    return _indices_for_roles(roles, wanted, limit=min(n, 2))


def _select_audio_indices(
    *,
    bible: ContinuityBible,
    shot: Shot,
    n: int,
    model_key: str,
) -> list[int]:
    if n <= 0 or "seedance_2_0" not in model_key:
        return []
    roles = _modal_roles(bible, "audios", n)
    wanted: list[str] = []
    if shot.audio.dialogue_vn or "dialogue" in (bible.audio_design.dialogue_style or "").lower():
        wanted.append("lip_sync_source")
    if shot.audio.sfx:
        wanted.append("sfx_layer")
    if shot.audio.music_cue or bible.audio_design.music_genre:
        wanted.append("beat_reference")
    if not wanted:
        wanted = ["beat_reference"]
    return _indices_for_roles(roles, wanted, limit=min(n, 2))


def _modal_roles(bible: ContinuityBible, key: str, n: int) -> list[str]:
    role_meta = ((bible.storytelling_meta or {}).get("quad_modal_reference_roles") or {}).get(key) or []
    roles = ["unknown" for _ in range(n)]
    for item in role_meta:
        if not isinstance(item, dict):
            continue
        idx = int(item.get("index") or 0)
        if 0 <= idx < n:
            roles[idx] = str(item.get("role") or "unknown")
    return roles


def _indices_for_roles(roles: list[str], wanted: list[str], *, limit: int) -> list[int]:
    selected: list[int] = []
    for role in wanted:
        for idx, candidate in enumerate(roles):
            if candidate == role and idx not in selected:
                selected.append(idx)
                break
    if not selected and roles:
        selected.append(0)
    return selected[:limit]


def _dedupe_sorted(refs: list[ReferenceAsset], *, max_refs: int) -> list[ReferenceAsset]:
    selected: list[ReferenceAsset] = []
    seen: set[int] = set()
    for ref in refs:
        if ref.index in seen:
            continue
        selected.append(ref)
        seen.add(ref.index)
        if len(selected) >= max_refs:
            break
    return selected


def _ref_role(ref: ReferenceAsset) -> str:
    notes = (getattr(ref, "notes", "") or "")
    if "MASTER BOARD" in notes:
        return "master_board"
    return str(ref.role or "unknown")


def _shot_text(shot: Shot) -> str:
    return " ".join(
        [
            shot.purpose or "",
            shot.emotion_beat or "",
            shot.visual.subject or "",
            shot.visual.action or "",
            shot.visual.camera_shot or "",
            shot.visual.camera_movement or "",
            shot.visual.composition or "",
            shot.visual.background or "",
            shot.dynamic_description or "",
        ]
    ).lower()


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _policy_reason(
    shot: Shot,
    images: list[ReferenceAsset],
    video_indices: list[int],
    audio_indices: list[int],
) -> str:
    return (
        f"{shot.shot_id}: selected {len(images)} image refs, "
        f"{len(video_indices)} video refs, {len(audio_indices)} audio refs "
        "to reduce competing reference jobs while preserving identity/product/style anchors."
    )


__all__ = ["optimize_shot_references"]
