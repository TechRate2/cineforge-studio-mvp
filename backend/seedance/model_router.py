"""Phase 1a skeleton model router for Seedance execution plans."""
from __future__ import annotations

from pipeline.contracts import AssetRef, CreativePlan, StoryboardScene


class SeedanceModelRouter:
    """Minimal deterministic router reserved for richer Phase 1b logic."""

    def route(
        self,
        *,
        creative_plan: CreativePlan,
        scene: StoryboardScene | None = None,
        references: list[AssetRef] | None = None,
    ) -> str:
        """Return an explicit model if provided, otherwise a stable default."""
        requested = str(creative_plan.metadata.get("model") or "").strip()
        if requested:
            return requested
        return "seedance_2_0"


__all__ = ["SeedanceModelRouter"]
