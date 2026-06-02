"""Seedance 2.0 reference allocation preview.

The production renderer has a per-shot optimizer, but the autonomous preview
also needs a high-level contract for how image/video/audio references will be
used. This makes Seedance's omni-reference strength explicit before a paid job:
identity/product/style images, camera/motion videos, beat/SFX/dialogue audio,
and last-frame chaining for long-form continuity.
"""
from __future__ import annotations

from typing import Any

from agent.reference_sufficiency_gate import build_reference_sufficiency_report


_PRODUCT_NICHES = {"beauty", "food", "fashion", "ecommerce_catalog", "ugc_review", "tech", "app_saas", "automotive"}
_LOCATION_NICHES = {"real_estate", "restaurant_hospitality", "travel", "documentary"}
_DIALOGUE_NICHES = {"education", "documentary", "finance_education", "medical_wellness", "drama"}


def build_seedance_reference_allocation(
    *,
    niche: str,
    runtime_payload: dict[str, Any],
    reference_counts: dict[str, int],
    has_dialogue: bool,
    creative_treatment: dict[str, Any] | None = None,
    reference_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return an inspectable reference-role plan for Seedance jobs."""
    images = max(0, int(reference_counts.get("images") or 0))
    videos = max(0, int(reference_counts.get("videos") or 0))
    audios = max(0, int(reference_counts.get("audios") or 0))
    pinned = max(0, int(reference_counts.get("pinned_assets") or 0))
    runtime_class = str(runtime_payload.get("runtime_class") or "short")
    is_long_form = runtime_class in {"micro_film", "short_film", "episode"}
    treatment_id = str((creative_treatment or {}).get("treatment_id") or "")

    image_roles = _image_roles(niche=niche, count=images, pinned_count=pinned, treatment_id=treatment_id)
    video_roles = _video_roles(niche=niche, count=videos, treatment_id=treatment_id)
    audio_roles = _audio_roles(niche=niche, count=audios, has_dialogue=has_dialogue, treatment_id=treatment_id)
    manifest_plan = _manifest_role_plan(reference_manifest or {})
    if manifest_plan["images"]:
        image_roles = _merge_manifest_role_plan(image_roles, manifest_plan["images"], kind="image", count=images)
    if manifest_plan["videos"]:
        video_roles = _merge_manifest_role_plan(video_roles, manifest_plan["videos"], kind="video", count=videos)
    if manifest_plan["audios"]:
        audio_roles = _merge_manifest_role_plan(audio_roles, manifest_plan["audios"], kind="audio", count=audios)
    warnings = _cap_warnings(images=images, videos=videos, audios=audios)
    if is_long_form and images + pinned == 0:
        warnings.append("long_form_without_visual_identity_anchor")
    if has_dialogue and audios == 0:
        warnings.append("dialogue_route_without_audio_reference")
    reference_sufficiency = build_reference_sufficiency_report(
        niche=niche,
        runtime_payload=runtime_payload,
        reference_counts={
            "images": images,
            "videos": videos,
            "audios": audios,
            "pinned_assets": pinned,
        },
        has_dialogue=has_dialogue,
        target_market=str(runtime_payload.get("target_market") or "auto"),
    )

    return {
        "schema_version": "cinejelly.seedance_reference_allocation.v1",
        "runtime_class": runtime_class,
        "reference_counts": {
            "images": images,
            "videos": videos,
            "audios": audios,
            "pinned_assets": pinned,
        },
        "caps": {
            "image_reference_cap": 9,
            "video_reference_cap": 3,
            "audio_reference_cap": 3,
            "mixed_reference_cap": 12,
        },
        "fits_seedance_caps": images <= 9 and videos <= 3 and audios <= 3 and images + videos + audios <= 12,
        "warnings": warnings,
        "reference_manifest": _compact_reference_manifest(reference_manifest or {}),
        "reference_sufficiency": reference_sufficiency,
        "image_role_plan": image_roles,
        "video_role_plan": video_roles,
        "audio_role_plan": audio_roles,
        "per_shot_policy": _per_shot_policy(
            niche=niche,
            runtime_class=runtime_class,
            has_dialogue=has_dialogue,
            image_roles=image_roles,
            video_roles=video_roles,
            audio_roles=audio_roles,
        ),
        "long_form_handoff_policy": {
            "enabled": is_long_form,
            "first_scene": "establish image/pinned identity anchors and style refs",
            "later_scenes": "use previous scene final frame plus strongest identity/product/style refs",
            "retry_scope": "retry failed 4-15s units only; preserve approved anchors",
        },
    }


def _image_roles(*, niche: str, count: int, pinned_count: int, treatment_id: str) -> list[dict[str, Any]]:
    roles: list[str] = []
    if count <= 0:
        return []
    if pinned_count:
        roles.append("approved_asset_anchor")
    if niche in _PRODUCT_NICHES:
        roles.extend(["product_hero", "product_detail", "character_anchor", "style_reference", "environment"])
    elif niche in _LOCATION_NICHES:
        roles.extend(["environment", "character_anchor", "style_reference", "product_hero", "brand_asset"])
    elif niche in {"drama", "anime_comic", "music_video"}:
        roles.extend(["character_anchor", "secondary_character", "environment", "style_reference", "brand_asset"])
    else:
        roles.extend(["character_anchor", "style_reference", "environment", "product_hero", "brand_asset"])
    if treatment_id == "cinematic_premium":
        roles = _prioritize(roles, ["style_reference", "product_hero", "character_anchor"])
    elif treatment_id == "documentary_testimonial":
        roles = _prioritize(roles, ["character_anchor", "environment", "style_reference"])
    elif treatment_id == "short_drama_arc":
        roles = _prioritize(roles, ["character_anchor", "environment", "secondary_character", "style_reference"])
    return [
        {
            "tag": f"@image_{idx + 1}",
            "role": role,
            "job": _image_job(role),
            "priority": idx + 1,
        }
        for idx, role in enumerate(_expand_roles(roles, count))
    ]


def _video_roles(*, niche: str, count: int, treatment_id: str) -> list[dict[str, Any]]:
    if count <= 0:
        return []
    roles = ["camera_motion", "motion_style", "shot_pacing"]
    if treatment_id == "fast_social_hook":
        roles = ["shot_pacing", "motion_style", "camera_motion"]
    elif niche in {"drama", "real_estate", "travel"} or treatment_id in {"cinematic_premium", "short_drama_arc"}:
        roles = ["camera_motion", "shot_pacing", "motion_style"]
    return [
        {
            "tag": f"@video_{idx + 1}",
            "role": role,
            "job": _video_job(role),
            "priority": idx + 1,
        }
        for idx, role in enumerate(_expand_roles(roles, min(count, 3)))
    ]


def _audio_roles(*, niche: str, count: int, has_dialogue: bool, treatment_id: str) -> list[dict[str, Any]]:
    if count <= 0:
        return []
    if has_dialogue or niche in _DIALOGUE_NICHES or treatment_id in {"documentary_testimonial", "short_drama_arc"}:
        roles = ["lip_sync_source", "beat_reference", "sfx_layer"]
    elif niche in {"asmr", "food", "beauty"}:
        roles = ["sfx_layer", "beat_reference", "lip_sync_source"]
    else:
        roles = ["beat_reference", "sfx_layer", "lip_sync_source"]
    return [
        {
            "tag": f"@audio_{idx + 1}",
            "role": role,
            "job": _audio_job(role),
            "priority": idx + 1,
        }
        for idx, role in enumerate(_expand_roles(roles, min(count, 3)))
    ]


def _per_shot_policy(
    *,
    niche: str,
    runtime_class: str,
    has_dialogue: bool,
    image_roles: list[dict[str, Any]],
    video_roles: list[dict[str, Any]],
    audio_roles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    policy = [
        {
            "shot_type": "hook",
            "use_refs": _tags_for_roles(image_roles, {"character_anchor", "product_hero", "style_reference"}) + _tags_for_roles(video_roles, {"camera_motion", "shot_pacing"})[:1],
            "goal": "lock identity/product/style while making the first visual action readable",
        },
        {
            "shot_type": "proof_or_demo",
            "use_refs": _tags_for_roles(image_roles, {"product_hero", "product_detail", "character_anchor"}) + _tags_for_roles(audio_roles, {"sfx_layer", "beat_reference"})[:1],
            "goal": "show the claim through visible action, texture, or result",
        },
        {
            "shot_type": "style_or_environment",
            "use_refs": _tags_for_roles(image_roles, {"style_reference", "environment"}) + _tags_for_roles(video_roles, {"camera_motion"})[:1],
            "goal": "preserve location, mood, lighting, and camera grammar",
        },
    ]
    if has_dialogue:
        policy.append({
            "shot_type": "dialogue_insert",
            "use_refs": _tags_for_roles(image_roles, {"character_anchor"}) + _tags_for_roles(audio_roles, {"lip_sync_source"}),
            "goal": "keep speech short, natural, and cut back into Seedance visual coverage",
        })
    if runtime_class in {"micro_film", "short_film", "episode"}:
        policy.append({
            "shot_type": "scene_handoff",
            "use_refs": ["previous_scene_final_frame", *_tags_for_roles(image_roles, {"character_anchor", "product_hero", "style_reference", "environment"})[:3]],
            "goal": "carry continuity across scenes without overloading a single Seedance call",
        })
    return policy


def _tags_for_roles(items: list[dict[str, Any]], roles: set[str]) -> list[str]:
    return [str(item["tag"]) for item in items if item.get("role") in roles]


def _manifest_role_plan(manifest: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    allowed = {
        "image": {
            "character_anchor", "secondary_character", "product_hero", "product_detail",
            "style_reference", "environment", "brand_asset",
        },
        "video": {"camera_motion", "motion_style", "shot_pacing"},
        "audio": {"beat_reference", "lip_sync_source", "sfx_layer"},
    }
    out: dict[str, list[dict[str, Any]]] = {"images": [], "videos": [], "audios": []}
    items = manifest.get("items") if isinstance(manifest, dict) else []
    if not isinstance(items, list):
        return out
    for item in items[:12]:
        if not isinstance(item, dict) or not item.get("role_confirmed"):
            continue
        kind = str(item.get("kind") or "").strip().lower()
        role = str(item.get("role") or "").strip().lower()
        tag = str(item.get("tag") or "").strip()
        if kind not in allowed or role not in allowed[kind] or not tag:
            continue
        index = _tag_index(tag, kind)
        if index is None:
            continue
        row = {
            "tag": tag,
            "role": role,
            "job": _job_for_kind(kind, role),
            "priority": index + 1,
            "source": "confirmed_reference_manifest",
            "role_confirmed": True,
            "name": str(item.get("name") or "").strip()[:120],
            "prompt_binding": str(item.get("prompt_binding") or "").strip()[:220],
        }
        out[f"{kind}s"].append(row)
    for values in out.values():
        values.sort(key=lambda row: int(row.get("priority") or 999))
    return out


def _merge_manifest_role_plan(
    base: list[dict[str, Any]],
    manifest_items: list[dict[str, Any]],
    *,
    kind: str,
    count: int,
) -> list[dict[str, Any]]:
    by_tag = {str(item.get("tag") or ""): item for item in base}
    for item in manifest_items:
        by_tag[str(item.get("tag") or "")] = item
    merged: list[dict[str, Any]] = []
    for idx in range(max(0, min(count, 9 if kind == "image" else 3))):
        tag = f"@{kind}_{idx + 1}"
        if tag in by_tag:
            merged.append(by_tag[tag])
    return merged


def _compact_reference_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        return {}
    items = manifest.get("items") or []
    if not isinstance(items, list):
        items = []
    compact_items = []
    for item in items[:12]:
        if not isinstance(item, dict):
            continue
        compact_items.append({
            "tag": str(item.get("tag") or "").strip()[:24],
            "kind": str(item.get("kind") or "").strip().lower()[:12],
            "role": str(item.get("role") or "unknown").strip().lower()[:60],
            "role_confirmed": bool(item.get("role_confirmed")),
            "name": str(item.get("name") or "").strip()[:120],
        })
    return {
        "schema_version": "cinejelly.reference_manifest.v1",
        "confirmed": bool(manifest.get("confirmed")) and all(item["role_confirmed"] for item in compact_items),
        "items": compact_items,
    }


def _tag_index(tag: str, kind: str) -> int | None:
    prefix = f"@{kind}_"
    if not tag.startswith(prefix):
        return None
    try:
        parsed = int(tag[len(prefix):])
    except ValueError:
        return None
    if parsed <= 0:
        return None
    return parsed - 1


def _job_for_kind(kind: str, role: str) -> str:
    if kind == "image":
        return _image_job(role)
    if kind == "video":
        return _video_job(role)
    return _audio_job(role)


def _cap_warnings(*, images: int, videos: int, audios: int) -> list[str]:
    warnings: list[str] = []
    if images > 9:
        warnings.append("image_refs_exceed_seedance_cap_9")
    if videos > 3:
        warnings.append("video_refs_exceed_seedance_cap_3")
    if audios > 3:
        warnings.append("audio_refs_exceed_seedance_cap_3")
    if images + videos + audios > 12:
        warnings.append("mixed_refs_exceed_seedance_cap_12")
    return warnings


def _prioritize(roles: list[str], priority: list[str]) -> list[str]:
    return [*priority, *[role for role in roles if role not in priority]]


def _expand_roles(roles: list[str], count: int) -> list[str]:
    if count <= len(roles):
        return roles[:count]
    return [*roles, *(["style_reference"] * (count - len(roles)))]


def _image_job(role: str) -> str:
    jobs = {
        "approved_asset_anchor": "reuse approved character/product/style memory from prior jobs",
        "character_anchor": "preserve exact face, hair, outfit, body language",
        "secondary_character": "preserve supporting character identity",
        "product_hero": "preserve exact product geometry, packaging, color, label",
        "product_detail": "preserve macro texture, material, close-up detail",
        "style_reference": "guide mood, color grade, lighting, composition",
        "environment": "anchor location, layout, atmosphere",
        "brand_asset": "preserve brand colors, typography, logo treatment",
    }
    return jobs.get(role, "general visual reference")


def _video_job(role: str) -> str:
    jobs = {
        "camera_motion": "guide dolly, pan, orbit, handheld, or push-in trajectory",
        "motion_style": "guide gesture, body movement, physical timing",
        "shot_pacing": "guide cut rhythm, reveal timing, transition tempo",
    }
    return jobs.get(role, "general motion reference")


def _audio_job(role: str) -> str:
    jobs = {
        "beat_reference": "guide music tempo, rhythm, emotional pacing",
        "sfx_layer": "guide foley, tactile sound, ambience, impact timing",
        "lip_sync_source": "guide dialogue timing and lip-sync candidate lane",
    }
    return jobs.get(role, "general audio reference")


__all__ = ["build_seedance_reference_allocation"]
