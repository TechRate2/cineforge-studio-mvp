"""Input analysis for Phase 2 creative planning.

The analyzer is deterministic by design. It turns the Phase 0 InputContract
into an AnalyzedInput with enough niche, reference, and risk metadata for the
planner to make useful decisions without introducing render execution.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from pipeline.contracts import AnalyzedInput, AssetRef, InputContract, ReferenceRole, canonical_hash


_NICHE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "product": ("product", "brand", "packaging", "label", "launch", "commercial", "ad"),
    "beauty": ("beauty", "cosmetic", "skincare", "perfume", "lipstick", "serum", "makeup"),
    "food": ("food", "recipe", "restaurant", "cooking", "street food", "takoyaki", "coffee", "drink"),
    "fashion": ("fashion", "couture", "runway", "model", "outfit", "dress", "haute couture"),
    "anime": ("anime", "manga", "samurai", "volleyball", "mappa", "duel", "mecha"),
    "drama": ("drama", "romance", "short film", "dialogue", "character", "story", "emotional"),
    "ugc": ("ugc", "vlog", "review", "selfie", "phone camera", "testimonial", "creator"),
    "sports": ("sport", "football", "racing", "race", "world cup", "volleyball"),
    "cinematic": ("cinematic", "film", "trailer", "imax", "noir", "rain", "chase"),
    "tech": ("app", "software", "saas", "device", "gadget", "ai tool", "dashboard"),
}

_PRODUCT_WORDS = {
    "product",
    "perfume",
    "bottle",
    "cosmetic",
    "skincare",
    "serum",
    "packaging",
    "brand",
    "label",
    "drink",
    "food",
}
_CHARACTER_WORDS = {
    "character",
    "person",
    "woman",
    "man",
    "girl",
    "boy",
    "actor",
    "model",
    "creator",
    "samurai",
    "driver",
}


class InputAnalyzer:
    """Analyze a user request into a stable AnalyzedInput contract."""

    def analyze(self, input_contract: InputContract) -> AnalyzedInput:
        """Return deterministic analysis for downstream creative planning."""
        idea = _normalize_text(input_contract.user_idea)
        niche = _detect_niche(idea)
        intent = _detect_intent(idea, niche)
        duration_s = _infer_duration_s(input_contract)
        asset_summary = _summarize_assets(input_contract.assets, idea=idea, niche=niche)
        warnings = _analysis_warnings(
            idea=idea,
            niche=niche,
            duration_s=duration_s,
            asset_summary=asset_summary,
        )
        blockers: list[str] = []
        if not idea:
            blockers.append("empty_user_idea")

        return AnalyzedInput(
            input_id=input_contract.input_id,
            idea_hash=canonical_hash(input_contract.user_idea),
            normalized_idea=idea,
            detected_niche=niche,
            intent=intent,
            target_platform=input_contract.target_platform,
            target_market=input_contract.target_market,
            duration_s=duration_s,
            aspect_ratio=input_contract.aspect_ratio,
            asset_summary=asset_summary,
            blockers=blockers,
            warnings=warnings,
            metadata={
                "phase": "2",
                "objective": _objective_from_idea(idea),
                "assets": [asset.model_dump(mode="json", exclude_none=True) for asset in input_contract.assets],
                "primary_risks": _primary_risks(warnings, asset_summary),
                "reference_sufficiency": asset_summary.get("reference_sufficiency"),
                "analysis_rules": [
                    "phase2.input.niche_keyword_score",
                    "phase2.input.reference_sufficiency",
                    "phase2.input.duration_inference",
                ],
            },
        )


def _detect_niche(idea: str) -> str:
    if any(word in idea for word in ("perfume", "cosmetic", "skincare", "lipstick", "serum", "makeup")):
        return "beauty"
    if any(word in idea for word in ("recipe", "restaurant", "cooking", "street food", "takoyaki", "coffee")):
        return "food"
    if any(word in idea for word in ("fashion", "couture", "runway", "outfit", "dress", "haute couture")):
        return "fashion"
    scores = {
        niche: sum(1 for token in keywords if token in idea)
        for niche, keywords in _NICHE_KEYWORDS.items()
    }
    best_niche, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score <= 0:
        return "unknown"
    if best_score <= 0 and any(word in idea for word in _PRODUCT_WORDS):
        return "product"
    if best_niche == "cinematic" and any(word in idea for word in _PRODUCT_WORDS):
        return "beauty" if any(word in idea for word in ("perfume", "cosmetic", "skincare")) else "product"
    return best_niche


def _detect_intent(idea: str, niche: str) -> str:
    if any(word in idea for word in _PRODUCT_WORDS):
        return "product_ad"
    if niche in {"drama", "anime"} or any(word in idea for word in ("story", "dialogue", "scene")):
        return "character_story"
    if niche == "ugc":
        return "ugc_clip"
    if niche == "food":
        return "sensory_food_video"
    if niche == "sports":
        return "action_sequence"
    return "cinematic_sequence"


def _infer_duration_s(input_contract: InputContract) -> int:
    if input_contract.duration_hint_s:
        return int(input_contract.duration_hint_s)
    idea = input_contract.user_idea.lower()
    match = re.search(r"\b(\d{1,2})\s*(?:s|sec|second|seconds)\b", idea)
    if match:
        return int(match.group(1))
    if any(word in idea for word in ("story", "multi-shot", "three shot", "dialogue", "sequence")):
        return 12
    return 8


def _summarize_assets(assets: list[AssetRef], *, idea: str, niche: str) -> dict[str, Any]:
    kind_counts = Counter(asset.kind for asset in assets)
    role_counts = Counter(asset.role.value for asset in assets)
    tags_by_role: dict[str, list[str]] = {}
    for asset in assets:
        if asset.tag:
            tags_by_role.setdefault(asset.role.value, []).append(asset.tag)

    needs_product = niche in {"beauty", "food", "fashion", "product"} or any(word in idea for word in _PRODUCT_WORDS)
    needs_character = niche in {"drama", "anime", "ugc", "sports"} or any(word in idea for word in _CHARACTER_WORDS)
    has_product_anchor = any(
        asset.role in {ReferenceRole.PRODUCT_HERO, ReferenceRole.PRODUCT_DETAIL}
        or any(word in _asset_text(asset) for word in ("product", "bottle", "packaging", "label"))
        for asset in assets
    )
    has_character_anchor = any(
        asset.role in {ReferenceRole.CHARACTER_ANCHOR, ReferenceRole.SECONDARY_CHARACTER}
        or any(word in _asset_text(asset) for word in ("character", "face", "portrait", "person"))
        for asset in assets
    )
    missing_roles: list[str] = []
    if needs_product and not has_product_anchor:
        missing_roles.append("product_hero")
    if needs_character and not has_character_anchor:
        missing_roles.append("character_anchor")

    sufficiency = "sufficient"
    if missing_roles and assets:
        sufficiency = "partial"
    elif missing_roles:
        sufficiency = "insufficient"

    return {
        "asset_count": len(assets),
        "kind_counts": dict(kind_counts),
        "role_counts": dict(role_counts),
        "tags_by_role": tags_by_role,
        "needs_product_anchor": needs_product,
        "needs_character_anchor": needs_character,
        "has_product_anchor": has_product_anchor,
        "has_character_anchor": has_character_anchor,
        "has_audio": kind_counts.get("audio", 0) > 0,
        "missing_roles": missing_roles,
        "reference_sufficiency": sufficiency,
    }


def _analysis_warnings(
    *,
    idea: str,
    niche: str,
    duration_s: int,
    asset_summary: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    if duration_s < 4 or duration_s > 15:
        warnings.append("seedance_duration_outside_4_15s")
    if asset_summary.get("reference_sufficiency") == "insufficient":
        warnings.append("missing_key_reference_assets")
    if niche == "unknown":
        warnings.append("niche_uncertain")
    if "too many characters" in idea:
        warnings.append("identity_drift_risk")
    return warnings


def _primary_risks(warnings: list[str], asset_summary: dict[str, Any]) -> list[str]:
    risks = list(warnings)
    if asset_summary.get("needs_character_anchor") and not asset_summary.get("has_character_anchor"):
        risks.append("weak_character_lock")
    if asset_summary.get("needs_product_anchor") and not asset_summary.get("has_product_anchor"):
        risks.append("weak_product_lock")
    return list(dict.fromkeys(risks))


def _objective_from_idea(idea: str) -> str:
    if len(idea) <= 160:
        return idea
    return idea[:157].rstrip() + "..."


def _asset_text(asset: AssetRef) -> str:
    return _normalize_text(" ".join([
        str(asset.tag or ""),
        asset.name,
        asset.notes,
        str(asset.metadata),
    ]))


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


__all__ = ["InputAnalyzer"]
