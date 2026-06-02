"""Seedance reference policy rules for Phase 1b.

This module integrates dexhunter's @Image/@Video/@Audio assignment guidance
and Lanshu's identity-anchor risk checks. It remains deterministic and only
works on supplied assets; curated example retrieval is Phase 2 work.
"""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from pipeline.contracts import AssetRef, ReferenceRole, StoryboardScene


PolicySeverity = Literal["info", "warning", "error"]

_REFERENCE_CAPS = {
    "image": 9,
    "video": 3,
    "audio": 3,
    "total_seedance": 12,
}

_ROLE_KEYWORDS: tuple[tuple[ReferenceRole, tuple[str, ...]], ...] = (
    (ReferenceRole.FIRST_FRAME, ("first frame", "starting frame", "opening frame")),
    (ReferenceRole.LAST_FRAME, ("last frame", "ending frame", "final frame")),
    (ReferenceRole.CHARACTER_ANCHOR, ("character", "identity", "face", "same person", "portrait", "headshot")),
    (ReferenceRole.SECONDARY_CHARACTER, ("secondary character", "supporting character", "extra person")),
    (ReferenceRole.PRODUCT_HERO, ("product hero", "hero product", "main product", "packaging", "bottle", "label")),
    (ReferenceRole.PRODUCT_DETAIL, ("product detail", "macro detail", "texture detail", "close-up detail")),
    (ReferenceRole.ENVIRONMENT, ("scene", "background", "location", "environment", "set design")),
    (ReferenceRole.CAMERA_MOTION, ("camera movement", "camera motion", "orbit", "pan", "tilt", "tracking", "dolly")),
    (ReferenceRole.ACTION_REFERENCE, ("action", "motion", "gesture", "choreography", "movement reference")),
    (ReferenceRole.VISUAL_EFFECT, ("effect", "transition", "vfx", "particle", "visual effect")),
    (ReferenceRole.MOTION_STYLE, ("rhythm", "tempo", "pacing", "movement style")),
    (ReferenceRole.OUTFIT_REFERENCE, ("outfit", "clothing", "wardrobe", "costume")),
    (ReferenceRole.BRAND_ASSET, ("brand", "logo", "brand asset")),
    (ReferenceRole.STYLE_REFERENCE, ("style", "mood", "color grade", "look reference", "aesthetic")),
    (ReferenceRole.AUDIO_VOICE, ("voice", "tone", "dialogue", "narration", "speaker")),
    (ReferenceRole.AUDIO_BGM, ("bgm", "music", "track", "song", "beat")),
    (ReferenceRole.AUDIO_SFX, ("sfx", "sound effect", "ambience", "foley")),
)

_IMAGE_ALLOWED = {
    ReferenceRole.FIRST_FRAME,
    ReferenceRole.LAST_FRAME,
    ReferenceRole.CHARACTER_ANCHOR,
    ReferenceRole.SECONDARY_CHARACTER,
    ReferenceRole.PRODUCT_HERO,
    ReferenceRole.PRODUCT_DETAIL,
    ReferenceRole.STYLE_REFERENCE,
    ReferenceRole.ENVIRONMENT,
    ReferenceRole.BRAND_ASSET,
    ReferenceRole.OUTFIT_REFERENCE,
    ReferenceRole.CONTINUITY_ANCHOR,
}
_VIDEO_ALLOWED = {
    ReferenceRole.CAMERA_MOTION,
    ReferenceRole.MOTION_STYLE,
    ReferenceRole.ACTION_REFERENCE,
    ReferenceRole.VISUAL_EFFECT,
    ReferenceRole.STYLE_REFERENCE,
    ReferenceRole.ENVIRONMENT,
    ReferenceRole.CONTINUITY_ANCHOR,
}
_AUDIO_ALLOWED = {
    ReferenceRole.AUDIO_VOICE,
    ReferenceRole.AUDIO_BGM,
    ReferenceRole.AUDIO_SFX,
}

_ROLE_PRIORITY = {
    ReferenceRole.CHARACTER_ANCHOR: 0,
    ReferenceRole.CONTINUITY_ANCHOR: 1,
    ReferenceRole.PRODUCT_HERO: 2,
    ReferenceRole.PRODUCT_DETAIL: 3,
    ReferenceRole.FIRST_FRAME: 4,
    ReferenceRole.LAST_FRAME: 5,
    ReferenceRole.OUTFIT_REFERENCE: 6,
    ReferenceRole.ENVIRONMENT: 7,
    ReferenceRole.CAMERA_MOTION: 8,
    ReferenceRole.ACTION_REFERENCE: 9,
    ReferenceRole.MOTION_STYLE: 10,
    ReferenceRole.VISUAL_EFFECT: 11,
    ReferenceRole.AUDIO_VOICE: 12,
    ReferenceRole.AUDIO_BGM: 13,
    ReferenceRole.AUDIO_SFX: 14,
    ReferenceRole.STYLE_REFERENCE: 15,
    ReferenceRole.BRAND_ASSET: 16,
    ReferenceRole.SECONDARY_CHARACTER: 17,
    ReferenceRole.UNKNOWN: 99,
}


class ReferencePolicyIssue(BaseModel):
    """One deterministic issue from reference policy validation."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    message: str
    severity: PolicySeverity = "warning"
    asset_id: str | None = None
    tag: str | None = None


class ReferencePolicy:
    """Reference validation, role assignment, and prioritization for Seedance."""

    def select_references_for_scene(
        self,
        *,
        scene: StoryboardScene,
        available_assets: list[AssetRef],
    ) -> list[AssetRef]:
        """Return prioritized scene references with Phase 1b role assignment."""
        if not scene.reference_bindings:
            return []
        binding_set = {str(binding) for binding in scene.reference_bindings}
        selected = [
            asset
            for asset in available_assets
            if str(asset.tag or "") in binding_set or str(asset.asset_id) in binding_set
        ]
        assigned = self.assign_reference_roles(
            selected,
            prompt=" ".join([
                scene.visual_intent,
                scene.action,
                scene.camera_movement,
                scene.spatial_change,
                scene.audio_intent,
                scene.continuity_notes,
            ]),
        )
        return self.prioritize_reference_assets(assigned)

    def validate_reference_caps(self, assets: list[AssetRef]) -> list[ReferencePolicyIssue]:
        """Validate dexhunter Seedance caps: image<=9, video<=3, audio<=3, total<=12."""
        counts = {
            "image": sum(1 for asset in assets if asset.kind == "image"),
            "video": sum(1 for asset in assets if asset.kind == "video"),
            "audio": sum(1 for asset in assets if asset.kind == "audio"),
        }
        seedance_total = counts["image"] + counts["video"] + counts["audio"]
        issues: list[ReferencePolicyIssue] = []
        for kind in ("image", "video", "audio"):
            cap = _REFERENCE_CAPS[kind]
            if counts[kind] > cap:
                issues.append(ReferencePolicyIssue(
                    rule_id=f"dexhunter.reference.cap_{kind}",
                    severity="error",
                    message=f"Seedance supports at most {cap} {kind} references; received {counts[kind]}.",
                ))
        if seedance_total > _REFERENCE_CAPS["total_seedance"]:
            issues.append(ReferencePolicyIssue(
                rule_id="dexhunter.reference.cap_total",
                severity="error",
                message=(
                    "Seedance supports at most 12 image/video/audio references in one request; "
                    f"received {seedance_total}."
                ),
            ))
        return issues

    def assign_reference_roles(
        self,
        assets: list[AssetRef],
        *,
        prompt: str = "",
        user_role_hints: dict[str, ReferenceRole | str] | None = None,
    ) -> list[AssetRef]:
        """Assign primary @Image/@Video/@Audio roles without mutating source assets.

        Explicit locked roles and user hints win. Otherwise the role is inferred
        from the asset tag/name/notes/metadata and nearby prompt intent.
        """
        hints = user_role_hints or {}
        assigned: list[AssetRef] = []
        for asset in assets:
            if asset.role_locked and asset.role != ReferenceRole.UNKNOWN:
                assigned.append(asset)
                continue

            hint = hints.get(asset.asset_id) or hints.get(str(asset.tag or ""))
            hinted_role = _coerce_role(hint)
            role = hinted_role or asset.role
            confidence = asset.role_confidence
            if role == ReferenceRole.UNKNOWN:
                role = _infer_role(asset, prompt=prompt)
                confidence = 0.72 if role != ReferenceRole.UNKNOWN else asset.role_confidence
            if role != ReferenceRole.UNKNOWN and not _role_allowed_for_kind(asset.kind, role):
                role = _fallback_role_for_kind(asset.kind)
                confidence = 0.55
            assigned.append(asset.model_copy(update={
                "role": role,
                "role_confidence": confidence,
            }))
        return assigned

    def validate_reference_role_conflicts(
        self,
        assets: list[AssetRef],
    ) -> list[ReferencePolicyIssue]:
        """Detect assets assigned too many incompatible jobs."""
        issues: list[ReferencePolicyIssue] = []
        for asset in assets:
            text = _asset_text(asset)
            inferred_roles = {role for role, keywords in _ROLE_KEYWORDS if any(keyword in text for keyword in keywords)}
            if len(inferred_roles) >= 4:
                issues.append(ReferencePolicyIssue(
                    rule_id="dexhunter.reference.too_many_jobs",
                    asset_id=asset.asset_id,
                    tag=asset.tag,
                    severity="warning",
                    message="One reference appears to carry too many jobs; split identity, scene, motion, and style refs.",
                ))
            if asset.kind == "image" and asset.role not in _IMAGE_ALLOWED and asset.role != ReferenceRole.UNKNOWN:
                issues.append(ReferencePolicyIssue(
                    rule_id="dexhunter.reference.image_role_conflict",
                    asset_id=asset.asset_id,
                    tag=asset.tag,
                    severity="error",
                    message=f"Image reference cannot reliably serve role '{asset.role.value}'.",
                ))
            if asset.kind == "video" and asset.role not in _VIDEO_ALLOWED and asset.role != ReferenceRole.UNKNOWN:
                issues.append(ReferencePolicyIssue(
                    rule_id="dexhunter.reference.video_role_conflict",
                    asset_id=asset.asset_id,
                    tag=asset.tag,
                    severity="error",
                    message=f"Video reference cannot reliably serve role '{asset.role.value}'.",
                ))
            if asset.kind == "audio" and asset.role not in _AUDIO_ALLOWED and asset.role != ReferenceRole.UNKNOWN:
                issues.append(ReferencePolicyIssue(
                    rule_id="dexhunter.reference.audio_role_conflict",
                    asset_id=asset.asset_id,
                    tag=asset.tag,
                    severity="error",
                    message=f"Audio reference cannot reliably serve role '{asset.role.value}'.",
                ))
        return issues

    def prioritize_reference_assets(self, assets: list[AssetRef]) -> list[AssetRef]:
        """Sort important references first, favoring character lock anchors."""
        return sorted(
            assets,
            key=lambda asset: (
                _ROLE_PRIORITY.get(asset.role, 99),
                _identity_anchor_rank(asset),
                0 if asset.role_locked else 1,
                str(asset.tag or asset.asset_id),
            ),
        )

    def detect_identity_anchor_risks(
        self,
        assets: list[AssetRef],
    ) -> list[ReferencePolicyIssue]:
        """Detect Lanshu identity risks: weak anchors, too many characters, multi-view drift."""
        issues: list[ReferencePolicyIssue] = []
        character_assets = [
            asset
            for asset in assets
            if asset.role in {ReferenceRole.CHARACTER_ANCHOR, ReferenceRole.SECONDARY_CHARACTER}
            or any(word in _asset_text(asset) for word in ("character", "face", "person", "identity"))
        ]
        if len(character_assets) > 4:
            issues.append(ReferencePolicyIssue(
                rule_id="lanshu.identity.too_many_characters",
                severity="warning",
                message="More than four character references increases identity drift risk.",
            ))

        has_face_closeup = any(_has_face_closeup(asset) for asset in character_assets)
        has_full_body = any(_has_full_body(asset) for asset in character_assets)
        if character_assets and not (has_face_closeup and has_full_body):
            issues.append(ReferencePolicyIssue(
                rule_id="lanshu.identity.weak_character_lock",
                severity="warning",
                message="Character lock should include a clear face close-up and a full-body reference.",
            ))

        for asset in character_assets:
            text = _asset_text(asset)
            if any(term in text for term in ("multi-view", "multiple views", "front side back", "turnaround", "contact sheet")):
                issues.append(ReferencePolicyIssue(
                    rule_id="lanshu.identity.multi_view_anchor_risk",
                    asset_id=asset.asset_id,
                    tag=asset.tag,
                    severity="warning",
                    message="Multi-view identity anchors can confuse Seedance; prioritize one clear face and one full-body ref.",
                ))
        return issues


def _infer_role(asset: AssetRef, *, prompt: str) -> ReferenceRole:
    text = _asset_text(asset) + " " + _norm(prompt)
    role_matches = [role for role, keywords in _ROLE_KEYWORDS if any(keyword in text for keyword in keywords)]
    if role_matches:
        for role in role_matches:
            if _role_allowed_for_kind(asset.kind, role):
                return role
    return _fallback_role_for_kind(asset.kind)


def _coerce_role(value: ReferenceRole | str | None) -> ReferenceRole | None:
    if value is None:
        return None
    if isinstance(value, ReferenceRole):
        return value
    try:
        return ReferenceRole(str(value))
    except ValueError:
        return None


def _role_allowed_for_kind(kind: str, role: ReferenceRole) -> bool:
    if kind == "image":
        return role in _IMAGE_ALLOWED
    if kind == "video":
        return role in _VIDEO_ALLOWED
    if kind == "audio":
        return role in _AUDIO_ALLOWED
    return True


def _fallback_role_for_kind(kind: str) -> ReferenceRole:
    if kind == "image":
        return ReferenceRole.STYLE_REFERENCE
    if kind == "video":
        return ReferenceRole.MOTION_STYLE
    if kind == "audio":
        return ReferenceRole.AUDIO_BGM
    return ReferenceRole.UNKNOWN


def _identity_anchor_rank(asset: AssetRef) -> int:
    if _has_face_closeup(asset):
        return 0
    if _has_full_body(asset):
        return 1
    if asset.role == ReferenceRole.CHARACTER_ANCHOR:
        return 2
    return 3


def _has_face_closeup(asset: AssetRef) -> bool:
    text = _asset_text(asset)
    return bool(re.search(r"\b(face|close[- ]?up|headshot|portrait)\b", text))


def _has_full_body(asset: AssetRef) -> bool:
    text = _asset_text(asset)
    return bool(re.search(r"\b(full[- ]?body|full length|head to toe|entire body|silhouette)\b", text))


def _asset_text(asset: AssetRef) -> str:
    metadata_values = " ".join(_flatten_metadata(asset.metadata))
    return _norm(" ".join([
        str(asset.tag or ""),
        asset.name,
        asset.notes,
        metadata_values,
    ]))


def _flatten_metadata(value: Any) -> list[str]:
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(_flatten_metadata(item))
        return out
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for item in value:
            out.extend(_flatten_metadata(item))
        return out
    return [str(value)] if value is not None else []


def _norm(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


__all__ = [
    "PolicySeverity",
    "ReferencePolicy",
    "ReferencePolicyIssue",
]
