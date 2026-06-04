"""Reference anchor selection for Phase 7A consistency."""
from __future__ import annotations

import re
from typing import Any

from identity.identity_contracts import AnchorKind, IdentityAnchor


class ReferenceAnchorBuilder:
    """Build identity anchors from analyzed input assets without vendor calls."""

    def __init__(self) -> None:
        self.last_warnings: list[str] = []

    def build(self, analyzed_input: Any) -> list[IdentityAnchor]:
        """Return anchors sorted by consistency importance."""
        self.last_warnings = []
        anchors: list[IdentityAnchor] = []
        for asset in _assets_from_analysis(analyzed_input):
            anchor = _anchor_from_asset(asset)
            if anchor is None:
                self.last_warnings.append("invalid_reference_asset_missing_asset_id")
                continue
            anchors.append(anchor)
        useful = [anchor for anchor in anchors if anchor.kind != "unknown"]
        return sorted(
            useful,
            key=lambda anchor: (
                _kind_priority(anchor.kind),
                -anchor.confidence_score,
                str(anchor.tag or anchor.asset_id),
            ),
        )


def _anchor_from_asset(asset: Any) -> IdentityAnchor | None:
    asset_id = str(_field(asset, "asset_id") or "").strip()
    if not asset_id:
        return None
    text = _asset_text(asset)
    kind = _anchor_kind(asset, text)
    traits = _extract_traits(text, kind=kind)
    warnings: list[str] = []
    confidence = 0.55
    role = _role_value(asset)
    if _bool_field(asset, "role_locked"):
        confidence += 0.2
    if role != "unknown":
        confidence += 0.15
    if traits:
        confidence += 0.1
    if kind == "character" and not (_has_face_closeup(text) or _has_full_body(text)):
        warnings.append("character_anchor_missing_face_or_full_body_hint")
        confidence -= 0.1
    if kind == "product" and not any(word in text for word in ("product", "packaging", "label", "bottle", "logo")):
        warnings.append("product_anchor_missing_packaging_or_label_hint")
        confidence -= 0.08
    return IdentityAnchor(
        asset_id=asset_id,
        tag=_optional_str(_field(asset, "tag")),
        kind=kind,
        role=role,
        confidence_score=max(0.0, min(1.0, round(confidence, 3))),
        traits=traits,
        warnings=warnings,
    )


def _assets_from_analysis(analyzed_input: Any) -> list[Any]:
    assets: list[Any] = []
    for item in analyzed_input.metadata.get("assets") or []:
        assets.append(item)
    return assets


def _anchor_kind(asset: Any, text: str) -> AnchorKind:
    role = _role_value(asset)
    if role in {"character_anchor", "secondary_character", "outfit_reference"}:
        return "character"
    if role in {"product_hero", "product_detail", "brand_asset"}:
        return "product"
    if role in {"style_reference", "environment"}:
        return "style"
    if role in {"audio_voice", "audio_bgm", "audio_sfx"}:
        return "audio"
    if any(word in text for word in ("face", "portrait", "person", "woman", "man", "character", "full-body", "outfit")):
        return "character"
    if any(word in text for word in ("product", "packaging", "label", "bottle", "logo", "serum", "dish", "food")):
        return "product"
    if any(word in text for word in ("style", "mood", "color grade", "lighting", "environment", "background")):
        return "style"
    return "unknown"


def _extract_traits(text: str, *, kind: AnchorKind) -> list[str]:
    traits: list[str] = []
    if kind == "character":
        patterns = (
            ("face close-up", r"\b(face|close[- ]?up|headshot|portrait)\b"),
            ("full-body silhouette", r"\b(full[- ]?body|full length|head to toe|silhouette)\b"),
            ("wardrobe/outfit", r"\b(outfit|wardrobe|dress|jacket|clothing|costume)\b"),
            ("hair/face identity", r"\b(hair|eyes|face|identity)\b"),
        )
    elif kind == "product":
        patterns = (
            ("packaging/label", r"\b(packaging|label|logo|bottle|box)\b"),
            ("product geometry", r"\b(shape|geometry|silhouette|material)\b"),
            ("product color", r"\b(color|palette|red|blue|green|black|white|gold|silver|pink)\b"),
        )
    else:
        patterns = (
            ("style reference", r"\b(style|mood|aesthetic|cinematic|commercial|ugc)\b"),
            ("lighting/color", r"\b(lighting|color|palette|grade)\b"),
        )
    for label, pattern in patterns:
        if re.search(pattern, text):
            traits.append(label)
    return list(dict.fromkeys(traits))


def _kind_priority(kind: AnchorKind) -> int:
    return {
        "character": 0,
        "product": 1,
        "style": 2,
        "environment": 3,
        "audio": 4,
        "unknown": 9,
    }[kind]


def _has_face_closeup(text: str) -> bool:
    return bool(re.search(r"\b(face|close[- ]?up|headshot|portrait)\b", text))


def _has_full_body(text: str) -> bool:
    return bool(re.search(r"\b(full[- ]?body|full length|head to toe|silhouette)\b", text))


def _asset_text(asset: Any) -> str:
    metadata_values = " ".join(_flatten_metadata(_field(asset, "metadata") or {}))
    return _normalize(" ".join([
        str(_field(asset, "tag") or ""),
        str(_field(asset, "name") or ""),
        str(_field(asset, "notes") or ""),
        metadata_values,
    ]))


def _role_value(asset: Any) -> str:
    role = _field(asset, "role")
    if hasattr(role, "value"):
        return str(role.value)
    return str(role or "unknown")


def _field(asset: Any, name: str) -> Any:
    if isinstance(asset, dict):
        return asset.get(name)
    return getattr(asset, name, None)


def _bool_field(asset: Any, name: str) -> bool:
    value = _field(asset, name)
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


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


def _normalize(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


__all__ = ["ReferenceAnchorBuilder"]
