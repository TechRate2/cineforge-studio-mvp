"""Curated Seedance example store."""
from __future__ import annotations

from pathlib import Path

from seedance.contracts import CuratedExample
from seedance.example_retriever import DEFAULT_EXAMPLES_PATH, ExampleRetriever


class CuratedExampleStore:
    """Repository-backed store for curated examples.

    This small wrapper keeps simple list/filter operations close to the
    provenance contracts while `ExampleRetriever` owns ranking and few-shot
    selection.
    """

    def __init__(self, examples: list[CuratedExample] | None = None) -> None:
        self._examples = list(examples or [])

    @classmethod
    def from_jsonl(cls, path: str | Path = DEFAULT_EXAMPLES_PATH) -> "CuratedExampleStore":
        """Load curated examples from the canonical JSONL knowledge file."""
        return cls(ExampleRetriever.from_jsonl(path).list_examples())

    def add(self, example: CuratedExample) -> CuratedExample:
        """Add one curated example after ensuring its prompt hash exists."""
        example.ensure_prompt_hash()
        if any(existing.example_id == example.example_id for existing in self._examples):
            raise ValueError(f"Duplicate curated example: {example.example_id}")
        self._examples.append(example)
        return example

    def list_examples(self) -> list[CuratedExample]:
        """Return stored examples in insertion order."""
        return list(self._examples)

    def by_niche(self, niche: str) -> list[CuratedExample]:
        """Return examples for a normalized niche."""
        target = " ".join(str(niche or "").strip().lower().split())
        return [example for example in self._examples if example.metadata.niche == target]

    def get(self, example_id: str) -> CuratedExample | None:
        """Return one curated example by ID."""
        return next((example for example in self._examples if example.example_id == example_id), None)


__all__ = ["CuratedExampleStore"]
