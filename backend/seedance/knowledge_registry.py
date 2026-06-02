"""Phase 1a skeleton registry for Seedance knowledge provenance."""
from __future__ import annotations

from seedance.contracts import KnowledgeSource, SeedanceKnowledgeRule


class SeedanceKnowledgeRegistry:
    """In-memory provenance registry; rule application starts in Phase 1b."""

    def __init__(self) -> None:
        self._sources: dict[str, KnowledgeSource] = {}
        self._rules: dict[str, SeedanceKnowledgeRule] = {}

    def register_source(self, source: KnowledgeSource) -> KnowledgeSource:
        """Register a knowledge source and return it unchanged."""
        self._sources[source.source_id] = source
        return source

    def register_rule(self, rule: SeedanceKnowledgeRule) -> SeedanceKnowledgeRule:
        """Register a rule for later Phase 1b lookup."""
        self._rules[rule.rule_id] = rule
        return rule

    def list_rules(self) -> list[SeedanceKnowledgeRule]:
        """Return all registered rules without applying them."""
        return list(self._rules.values())


__all__ = ["SeedanceKnowledgeRegistry"]
