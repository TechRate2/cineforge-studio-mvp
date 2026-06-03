"""Deterministic Seedance model router.

The router is intentionally rule-based. It keeps model selection explainable
and testable before any paid render request is assembled.
"""
from __future__ import annotations

from pipeline.contracts import AssetRef, CreativePlan, StoryboardScene


class SeedanceModelRouter:
    """Choose a Seedance model from plan complexity, budget, and references."""

    FAST_MODEL = "seedance_2_0_fast"
    QUALITY_MODEL = "seedance_2_0"
    ALLOWED_MODELS = {FAST_MODEL, QUALITY_MODEL, "auto"}

    def route(
        self,
        *,
        creative_plan: CreativePlan,
        scene: StoryboardScene | None = None,
        references: list[AssetRef] | None = None,
    ) -> str:
        """Return the safest deterministic model route for one shot.

        Explicit user or planner choices win when they are known Seedance
        family names. Otherwise the router keeps low-risk text-to-video work on
        Fast and upgrades reference-heavy, identity-sensitive, or premium
        product/story shots to the quality route.
        """
        requested = str(
            creative_plan.metadata.get("model")
            or creative_plan.metadata.get("requested_model")
            or ""
        ).strip()
        if requested and requested != "auto":
            return requested

        refs = references or []
        risk_text = " ".join([
            creative_plan.target_niche,
            creative_plan.objective,
            creative_plan.style_direction,
            " ".join(creative_plan.constraints),
            str(creative_plan.consistency_plan),
            str(creative_plan.reference_strategy),
            str(creative_plan.metadata),
            scene.beat if scene else "",
            scene.visual_intent if scene else "",
            scene.continuity_notes if scene else "",
        ]).lower()
        has_references = bool(refs)
        has_locked_identity = any(
            token in risk_text
            for token in (
                "character_lock",
                "product_lock",
                "identity",
                "face",
                "same character",
                "consistent character",
                "premium",
                "hero product",
                "beauty",
                "fashion",
                "food",
                "drama",
            )
        )
        complex_shot = creative_plan.shot_count >= 3 or creative_plan.duration_s >= 10
        budget_tier = str(creative_plan.metadata.get("budget_tier") or "").lower()

        if budget_tier in {"fast", "draft", "low", "budget"} and not has_locked_identity:
            return self.FAST_MODEL
        if has_references or has_locked_identity or complex_shot:
            return self.QUALITY_MODEL
        return self.FAST_MODEL


__all__ = ["SeedanceModelRouter"]
