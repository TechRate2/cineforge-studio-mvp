"""Phase 1a skeleton loader for curated Seedance examples."""
from __future__ import annotations

from seedance.contracts import CuratedExample


class CuratedExampleStore:
    """Minimal in-memory example store for Phase 2 retrieval work."""

    def __init__(self, examples: list[CuratedExample] | None = None) -> None:
        self._examples = list(examples or [])

    def add(self, example: CuratedExample) -> CuratedExample:
        """Add one curated example without ranking or few-shot selection."""
        self._examples.append(example)
        return example

    def list_examples(self) -> list[CuratedExample]:
        """Return stored examples in insertion order."""
        return list(self._examples)


__all__ = ["CuratedExampleStore"]
