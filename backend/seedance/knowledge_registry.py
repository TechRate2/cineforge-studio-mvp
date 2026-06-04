"""Seedance knowledge provenance registry."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from seedance.contracts import KnowledgeSource, SeedanceKnowledgeRule
from pipeline.contracts import canonical_hash


DEFAULT_RULES_PATH = Path(__file__).resolve().parent / "knowledge" / "rules.jsonl"


class SeedanceKnowledgeRegistry:
    """Load and query provenance-backed Seedance rules.

    The registry is deliberately read-only after loading unless callers
    explicitly register a rule or source. This keeps rule IDs traceable to the
    JSONL knowledge base used by tests and import scripts.
    """

    def __init__(self) -> None:
        self._sources: dict[str, KnowledgeSource] = {}
        self._rules: dict[str, SeedanceKnowledgeRule] = {}

    @classmethod
    def from_jsonl(cls, path: str | Path = DEFAULT_RULES_PATH) -> "SeedanceKnowledgeRegistry":
        """Load normalized rules from a JSONL knowledge file."""
        registry = cls()
        file_path = Path(path)
        if not file_path.exists():
            return registry
        for line_number, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), start=1):
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            try:
                raw = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{file_path}:{line_number} invalid JSON: {exc.msg}") from exc
            registry.register_rule(_rule_from_raw(raw))
            registry.register_source(_source_from_raw(raw))
        return registry

    def register_source(self, source: KnowledgeSource) -> KnowledgeSource:
        """Register a knowledge source and return it unchanged."""
        self._sources[source.source_id] = source
        return source

    def register_rule(self, rule: SeedanceKnowledgeRule) -> SeedanceKnowledgeRule:
        """Register a rule and make future duplicate IDs fail loudly."""
        if rule.rule_id in self._rules:
            raise ValueError(f"Duplicate Seedance knowledge rule: {rule.rule_id}")
        self._rules[rule.rule_id] = rule
        return rule

    def get_rule(self, rule_id: str) -> SeedanceKnowledgeRule | None:
        """Return one rule by ID, or None when the registry does not know it."""
        return self._rules.get(rule_id)

    def list_rules(self) -> list[SeedanceKnowledgeRule]:
        """Return all registered rules sorted by rule ID."""
        return [self._rules[key] for key in sorted(self._rules)]

    def list_sources(self) -> list[KnowledgeSource]:
        """Return all source repositories used by registered rules."""
        return [self._sources[key] for key in sorted(self._sources)]

    def rules_for_file(self, file_path: str) -> list[SeedanceKnowledgeRule]:
        """Return rules that declare they apply to a repository file path."""
        target = file_path.replace("\\", "/")
        return [
            rule
            for rule in self.list_rules()
            if target in {item.replace("\\", "/") for item in rule.applies_to_files}
        ]

    def rules_for_function(self, function_name: str) -> list[SeedanceKnowledgeRule]:
        """Return rules that declare they apply to a specific function."""
        return [
            rule
            for rule in self.list_rules()
            if function_name in rule.target_functions
        ]

    def require_rule_ids(self, rule_ids: list[str]) -> None:
        """Raise when code emits a rule ID missing from the knowledge base."""
        missing = [rule_id for rule_id in rule_ids if rule_id not in self._rules]
        if missing:
            raise KeyError(f"Unknown Seedance knowledge rule IDs: {', '.join(sorted(missing))}")


def _rule_from_raw(raw: dict[str, Any]) -> SeedanceKnowledgeRule:
    applies_to_files = raw.get("applies_to_files") or [raw.get("applied_to_file")]
    target_functions = raw.get("target_functions") or [raw.get("applied_to_function")]
    return SeedanceKnowledgeRule(
        rule_id=str(raw["rule_id"]),
        source_repo=str(raw["source_repo"]),
        source_url=str(raw["source_url"]),
        license=str(raw["license"]),
        rule_type=str(raw.get("rule_type") or "quality_gate"),
        applies_to_files=[str(item) for item in applies_to_files if item],
        target_functions=[str(item) for item in target_functions if item],
        summary=str(raw.get("summary") or raw.get("description") or raw["rule_id"]),
        implementation_notes=str(raw.get("implementation_notes") or ""),
        phase=str(raw.get("phase") or "5"),
        severity=str(raw.get("severity") or "info"),
        tags=[str(item) for item in raw.get("tags") or []],
        metadata={
            "description": raw.get("description") or "",
            "applied_to_file": raw.get("applied_to_file") or "",
            "applied_to_function": raw.get("applied_to_function") or "",
            "source_commit": raw.get("source_commit") or "",
        },
    )


def _source_from_raw(raw: dict[str, Any]) -> KnowledgeSource:
    source_id = f"source_{canonical_hash([raw.get('source_repo'), raw.get('source_url')])[:12]}"
    return KnowledgeSource(
        source_id=source_id,
        source_repo=str(raw["source_repo"]),
        source_url=str(raw["source_url"]),
        license=str(raw["license"]),
        commit_sha=raw.get("source_commit"),
        description=str(raw.get("source_description") or raw.get("source_repo") or ""),
    )


__all__ = ["DEFAULT_RULES_PATH", "SeedanceKnowledgeRegistry"]
