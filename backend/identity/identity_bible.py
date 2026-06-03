"""Build Phase 7A identity bibles from analyzed input."""
from __future__ import annotations

from typing import Any

from identity.identity_contracts import (
    CharacterIdentityBible,
    EmotionContinuityTrack,
    IdentityAnchor,
    IdentityBibleBundle,
    ProductIdentityBible,
    StyleBible,
)
from identity.reference_anchor_builder import ReferenceAnchorBuilder


class IdentityBibleBuilder:
    """Create first-class consistency contracts before creative strategy selection."""

    def __init__(self, *, anchor_builder: ReferenceAnchorBuilder | None = None) -> None:
        self.anchor_builder = anchor_builder or ReferenceAnchorBuilder()

    def build(self, analyzed_input: Any) -> IdentityBibleBundle:
        """Return a deterministic identity bible bundle for one analyzed request."""
        anchors = self.anchor_builder.build(analyzed_input)
        character = _build_character_bible(analyzed_input, anchors)
        product = _build_product_bible(analyzed_input, anchors)
        style = _build_style_bible(analyzed_input)
        emotion = _build_emotion_track(analyzed_input)
        anchor_warnings = list(getattr(self.anchor_builder, "last_warnings", []) or [])
        warnings = list(dict.fromkeys(
            anchor_warnings
            + character.warnings
            + product.warnings
            + ["style_drift_possible" if not style.visual_style else ""]
        ))
        warnings = [warning for warning in warnings if warning]
        return IdentityBibleBundle(
            analysis_id=analyzed_input.analysis_id,
            anchors=anchors,
            character=character,
            product=product,
            style=style,
            emotion=emotion,
            warnings=warnings,
            rules_applied=[
                "phase7a.identity.anchor_builder",
                "phase7a.identity.character_bible",
                "phase7a.identity.product_bible",
                "phase7a.identity.style_bible",
                "phase7a.identity.emotion_track",
            ],
            metadata={
                "phase": "7a",
                "detected_niche": analyzed_input.detected_niche,
                "reference_sufficiency": analyzed_input.asset_summary.get("reference_sufficiency"),
                "invalid_anchor_count": anchor_warnings.count("invalid_reference_asset_missing_asset_id"),
            },
        )


def _build_character_bible(
    analyzed_input: Any,
    anchors: list[IdentityAnchor],
) -> CharacterIdentityBible:
    required = bool(analyzed_input.asset_summary.get("needs_character_anchor"))
    character_anchors = [anchor for anchor in anchors if anchor.kind == "character"]
    face_anchor = next((anchor for anchor in character_anchors if "face close-up" in anchor.traits), None)
    full_body_anchor = next((anchor for anchor in character_anchors if "full-body silhouette" in anchor.traits), None)
    stable_traits = _dedupe_traits(character_anchors, fallback=[
        "same face identity",
        "same hairstyle",
        "same outfit silhouette",
    ] if required else [])
    wardrobe_traits = [
        trait
        for trait in stable_traits
        if "outfit" in trait or "wardrobe" in trait or "silhouette" in trait
    ]
    warnings: list[str] = []
    if required and not character_anchors:
        warnings.append("missing_character_anchor")
    if required and character_anchors and not face_anchor:
        warnings.append("missing_face_closeup_anchor")
    if required and character_anchors and not full_body_anchor:
        warnings.append("missing_full_body_anchor")
    risk_level = "high" if required and not character_anchors else "medium" if warnings else "low"
    return CharacterIdentityBible(
        required=required,
        anchor_asset_ids=[anchor.asset_id for anchor in character_anchors],
        face_anchor_asset_id=face_anchor.asset_id if face_anchor else None,
        full_body_anchor_asset_id=full_body_anchor.asset_id if full_body_anchor else None,
        stable_traits=stable_traits,
        wardrobe_traits=wardrobe_traits,
        forbidden_changes=[
            "do not change face identity",
            "do not change hairstyle or outfit silhouette",
            "do not create twins, clones, or duplicate identity copies",
        ] if required else [],
        risk_level=risk_level,
        warnings=warnings,
    )


def _build_product_bible(
    analyzed_input: Any,
    anchors: list[IdentityAnchor],
) -> ProductIdentityBible:
    required = bool(analyzed_input.asset_summary.get("needs_product_anchor"))
    product_anchors = [anchor for anchor in anchors if anchor.kind == "product"]
    hero_anchor = product_anchors[0] if product_anchors else None
    detail_anchor = next(
        (anchor for anchor in product_anchors if any("geometry" in trait or "color" in trait for trait in anchor.traits)),
        None,
    )
    warnings: list[str] = []
    if required and not product_anchors:
        warnings.append("missing_product_anchor")
    if required and product_anchors and not hero_anchor:
        warnings.append("missing_product_hero_anchor")
    risk_level = "high" if required and not product_anchors else "medium" if warnings else "low"
    return ProductIdentityBible(
        required=required,
        anchor_asset_ids=[anchor.asset_id for anchor in product_anchors],
        hero_anchor_asset_id=hero_anchor.asset_id if hero_anchor else None,
        detail_anchor_asset_id=detail_anchor.asset_id if detail_anchor else None,
        package_shape="preserve product silhouette and packaging geometry" if required else "",
        color_palette=_palette_from_text(analyzed_input.normalized_idea),
        logo_label_rules=[
            "preserve label placement if visible",
            "do not invent unreadable logos or new brand marks",
        ] if required else [],
        forbidden_changes=[
            "do not change product geometry",
            "do not change packaging color or material",
            "do not move or hallucinate label details",
        ] if required else [],
        risk_level=risk_level,
        warnings=warnings,
    )


def _build_style_bible(analyzed_input: Any) -> StyleBible:
    niche = str(analyzed_input.detected_niche or "cinematic")
    style = {
        "beauty": "premium clean commercial",
        "product": "clean cinematic product commercial",
        "food": "warm tactile food commercial",
        "fashion": "high-fashion editorial",
        "drama": "cinematic naturalistic drama",
        "ugc": "phone-camera realistic UGC",
        "tech": "clean SaaS product demo",
        "cinematic": "high-fidelity cinematic realism",
    }.get(niche, "high-fidelity cinematic realism")
    return StyleBible(
        visual_style=style,
        lighting="consistent motivated lighting across shots",
        color_palette=_palette_from_text(analyzed_input.normalized_idea),
        camera_language="one primary camera movement per shot",
        forbidden_style_drift=[
            "do not switch between unrelated visual styles",
            "do not change lighting language between adjacent shots",
        ],
    )


def _build_emotion_track(analyzed_input: Any) -> EmotionContinuityTrack:
    idea = analyzed_input.normalized_idea
    required = analyzed_input.detected_niche in {"drama", "ugc"} or "emotion" in idea or "reaction" in idea
    if "tension" in idea or "reveal" in idea:
        start, target = "restrained tension", "clear emotional reveal"
    elif "reaction" in idea:
        start, target = "curiosity", "reaction payoff"
    else:
        start, target = "neutral setup", "clear payoff"
    return EmotionContinuityTrack(
        required=required,
        starting_emotion=start if required else "",
        target_emotion=target if required else "",
        allowed_transitions=[f"{start} -> {target}"] if required else [],
        forbidden_emotion_jumps=["avoid unmotivated emotional jumps"] if required else [],
    )


def _dedupe_traits(anchors: list[IdentityAnchor], *, fallback: list[str]) -> list[str]:
    traits: list[str] = []
    for anchor in anchors:
        traits.extend(anchor.traits)
    traits.extend(fallback)
    return list(dict.fromkeys(trait for trait in traits if trait))


def _palette_from_text(text: str) -> list[str]:
    colors = [
        "red",
        "blue",
        "green",
        "black",
        "white",
        "gold",
        "silver",
        "pink",
        "cream",
        "warm",
        "cool",
    ]
    return [color for color in colors if color in str(text or "").lower()][:4]


__all__ = ["IdentityBibleBuilder"]
