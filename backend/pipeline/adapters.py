"""Adapters from legacy flow dictionaries/models into Phase 0 contracts."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from pydantic import BaseModel

from pipeline.contracts import (
    AnalyzedInput,
    AssetRef,
    InputContract,
    ReferenceRole,
    StoryboardContract,
    StoryboardScene,
    canonical_hash,
)


def build_input_contract_from_legacy_request(
    *,
    user_idea: str,
    target_platform: str = "tiktok",
    target_market: str = "auto",
    duration_hint_s: int | None = None,
    aspect_ratio: str | None = None,
    resolution: str | None = None,
    reference_image_urls: Sequence[str] | None = None,
    reference_video_urls: Sequence[str] | None = None,
    reference_audio_urls: Sequence[str] | None = None,
    reference_manifest: Mapping[str, Any] | None = None,
    settings: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> InputContract:
    """Create an InputContract from the current Studio/autonomous request shape."""
    assets = assets_from_legacy_references(
        reference_image_urls=reference_image_urls or [],
        reference_video_urls=reference_video_urls or [],
        reference_audio_urls=reference_audio_urls or [],
        reference_manifest=reference_manifest or {},
    )
    return InputContract(
        user_idea=user_idea,
        target_platform=target_platform,
        target_market=target_market,
        duration_hint_s=duration_hint_s,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        assets=assets,
        settings=dict(settings or {}),
        metadata=dict(metadata or {}),
    )


def assets_from_legacy_references(
    *,
    reference_image_urls: Sequence[str],
    reference_video_urls: Sequence[str],
    reference_audio_urls: Sequence[str],
    reference_manifest: Mapping[str, Any] | None = None,
) -> list[AssetRef]:
    """Normalize legacy image/video/audio URL arrays into AssetRef items."""
    manifest_items = {
        str(item.get("tag") or ""): item
        for item in (reference_manifest or {}).get("items", [])
        if isinstance(item, Mapping)
    }
    assets: list[AssetRef] = []
    for kind, urls in (
        ("image", reference_image_urls),
        ("video", reference_video_urls),
        ("audio", reference_audio_urls),
    ):
        for idx, url in enumerate(urls, start=1):
            tag = f"@{kind}_{idx}"
            manifest_item = manifest_items.get(tag, {})
            assets.append(
                AssetRef(
                    kind=kind,
                    url=str(url),
                    tag=tag,
                    role=_coerce_reference_role(manifest_item.get("role")),
                    role_locked=bool(manifest_item.get("role_confirmed")),
                    name=str(manifest_item.get("name") or ""),
                    notes=str(manifest_item.get("prompt_binding") or ""),
                    metadata={"legacy_manifest": dict(manifest_item)} if manifest_item else {},
                )
            )
    return assets


def analyzed_input_from_contract(
    input_contract: InputContract,
    *,
    normalized_idea: str | None = None,
    detected_niche: str = "unknown",
    intent: str = "unknown",
    asset_summary: Mapping[str, Any] | None = None,
    blockers: Sequence[str] | None = None,
    warnings: Sequence[str] | None = None,
) -> AnalyzedInput:
    """Build a minimal AnalyzedInput while deeper analysis is still legacy-owned."""
    return AnalyzedInput(
        input_id=input_contract.input_id,
        idea_hash=canonical_hash(input_contract.user_idea),
        normalized_idea=normalized_idea or input_contract.user_idea.strip(),
        detected_niche=detected_niche,
        intent=intent,
        target_platform=input_contract.target_platform,
        target_market=input_contract.target_market,
        duration_s=input_contract.duration_hint_s,
        aspect_ratio=input_contract.aspect_ratio,
        asset_summary=dict(asset_summary or {}),
        blockers=list(blockers or []),
        warnings=list(warnings or []),
    )


def storyboard_contract_from_legacy_plan(
    legacy_plan: Any,
    *,
    creative_plan_id: str,
) -> StoryboardContract:
    """Adapt an existing DirectorPlan-like object into StoryboardContract."""
    data = _model_dump(legacy_plan)
    shots = data.get("shot_list") or data.get("shots") or []
    scenes: list[StoryboardScene] = []
    for idx, shot in enumerate(shots):
        if not isinstance(shot, Mapping):
            continue
        visual = shot.get("visual") or {}
        audio = shot.get("audio") or {}
        continuity = shot.get("continuity") or {}
        scenes.append(
            StoryboardScene(
                scene_id=str(shot.get("shot_id") or f"scene_{idx + 1}"),
                index=int(shot.get("index") if shot.get("index") is not None else idx),
                duration_s=int(shot.get("duration_s") or 1),
                beat=str(shot.get("purpose") or shot.get("emotion_beat") or ""),
                visual_intent=str(shot.get("dynamic_description") or ""),
                action=str(visual.get("action") or ""),
                camera_movement=" ".join(
                    part
                    for part in [
                        str(visual.get("camera_shot") or "").strip(),
                        str(visual.get("camera_movement") or "").strip(),
                    ]
                    if part
                ),
                spatial_change=str(visual.get("background") or ""),
                audio_intent=_legacy_audio_intent(audio),
                reference_bindings=[str(item) for item in continuity.get("reference_indices") or []],
                continuity_notes=str(continuity.get("style_anchor") or ""),
                metadata={"legacy_shot": shot},
            )
        )
    return StoryboardContract(
        creative_plan_id=creative_plan_id,
        scenes=scenes,
        duration_s=sum(scene.duration_s for scene in scenes) or int(data.get("duration_s") or 1),
        aspect_ratio=str(
            data.get("aspect_ratio")
            or ((data.get("continuity_bible") or {}).get("aspect_ratio"))
            or "9:16"
        ),
        title=str((data.get("continuity_bible") or {}).get("title") or ""),
        summary=str((data.get("continuity_bible") or {}).get("logline") or ""),
        metadata={"legacy_plan_id": data.get("plan_id")},
    )


def _legacy_audio_intent(audio: Mapping[str, Any]) -> str:
    parts: list[str] = []
    if audio.get("dialogue_vn"):
        parts.append(f"dialogue: {audio['dialogue_vn']}")
    if audio.get("music_cue"):
        parts.append(f"music: {audio['music_cue']}")
    if audio.get("sfx"):
        parts.append("sfx: " + ", ".join(str(item) for item in audio["sfx"]))
    return "; ".join(parts)


def _coerce_reference_role(value: Any) -> ReferenceRole:
    aliases = {
        "shot_pacing": ReferenceRole.CAMERA_MOTION,
        "beat_reference": ReferenceRole.AUDIO_BGM,
        "lip_sync_source": ReferenceRole.AUDIO_VOICE,
        "sfx_layer": ReferenceRole.AUDIO_SFX,
        "portrait": ReferenceRole.CHARACTER_ANCHOR,
        "product": ReferenceRole.PRODUCT_HERO,
        "scene": ReferenceRole.ENVIRONMENT,
        "style": ReferenceRole.STYLE_REFERENCE,
    }
    normalized = str(value or "unknown").strip().lower()
    if normalized in aliases:
        return aliases[normalized]
    try:
        return ReferenceRole(normalized)
    except ValueError:
        return ReferenceRole.UNKNOWN


def _model_dump(value: Any) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    return {}


__all__ = [
    "analyzed_input_from_contract",
    "assets_from_legacy_references",
    "build_input_contract_from_legacy_request",
    "storyboard_contract_from_legacy_plan",
]
