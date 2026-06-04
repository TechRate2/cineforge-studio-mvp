"""Phase 5 golden cases for Seedance planning, compiling, and knowledge data."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

KNOWLEDGE_DIR = BACKEND_ROOT / "seedance" / "knowledge"
RULES_PATH = KNOWLEDGE_DIR / "rules.jsonl"
EXAMPLES_PATH = KNOWLEDGE_DIR / "examples.jsonl"


@dataclass(frozen=True)
class GoldenCase:
    """One expected end-to-end deterministic Seedance pipeline behavior."""

    name: str
    idea: str
    duration_s: int
    expected_niche: str
    expected_asset_mode: str
    expected_shot_count: int
    expected_reference_tags: tuple[str, ...] = ()
    assets: tuple[object, ...] = field(default_factory=tuple)
    expected_model: str = "seedance_2_0"


def _golden_cases() -> list[GoldenCase]:
    from pipeline.contracts import AssetRef, ReferenceRole

    return [
        GoldenCase(
            name="beauty_product_ad",
            idea=(
                "Create a 15s beauty serum ad with macro texture hook, hero product reveal, "
                "then premium payoff frame."
            ),
            duration_s=15,
            expected_niche="beauty",
            expected_asset_mode="i2v",
            expected_shot_count=3,
            expected_reference_tags=("@Image1",),
            assets=(
                AssetRef(kind="image", tag="@Image1", role=ReferenceRole.PRODUCT_HERO, notes="serum product bottle hero reference"),
            ),
        ),
        GoldenCase(
            name="short_drama",
            idea="Create a 12s short drama story: quiet tension, then a whispered reveal, then reaction payoff.",
            duration_s=12,
            expected_niche="drama",
            expected_asset_mode="t2v",
            expected_shot_count=3,
        ),
        GoldenCase(
            name="food_advertisement",
            idea="Create a 15s restaurant food advertisement with ingredient hook, cooking macro, and serve payoff.",
            duration_s=15,
            expected_niche="food",
            expected_asset_mode="i2v",
            expected_shot_count=3,
            expected_reference_tags=("@Image1",),
            assets=(
                AssetRef(kind="image", tag="@Image1", role=ReferenceRole.PRODUCT_HERO, notes="finished dish product hero reference"),
            ),
        ),
        GoldenCase(
            name="saas_demo",
            idea="Create a 12s SaaS app demo: dashboard pain point, then workflow automation, then value payoff.",
            duration_s=12,
            expected_niche="tech",
            expected_asset_mode="t2v",
            expected_shot_count=3,
        ),
        GoldenCase(
            name="education_content",
            idea="Create a 12s education science explainer scene: concept setup, then visual cause effect, then final learning frame.",
            duration_s=12,
            expected_niche="unknown",
            expected_asset_mode="t2v",
            expected_shot_count=3,
        ),
        GoldenCase(
            name="travel_vlog_style",
            idea="Create a 10s travel vlog: handheld arrival hook, then street market food detail, then warm creator reaction.",
            duration_s=10,
            expected_niche="ugc",
            expected_asset_mode="t2v",
            expected_shot_count=2,
        ),
        GoldenCase(
            name="character_reference",
            idea="Create a 12s drama scene with the same woman character, emotional reveal, and consistent clothing.",
            duration_s=12,
            expected_niche="drama",
            expected_asset_mode="i2v",
            expected_shot_count=3,
            expected_reference_tags=("@Image1", "@Image2"),
            assets=(
                AssetRef(kind="image", tag="@Image1", role=ReferenceRole.CHARACTER_ANCHOR, notes="woman face close-up portrait"),
                AssetRef(kind="image", tag="@Image2", role=ReferenceRole.CHARACTER_ANCHOR, notes="woman full-body outfit silhouette"),
            ),
        ),
        GoldenCase(
            name="product_reference",
            idea="Create a 12s smart water bottle product commercial: problem detail, hero product reveal, payoff frame.",
            duration_s=12,
            expected_niche="product",
            expected_asset_mode="i2v",
            expected_shot_count=3,
            expected_reference_tags=("@Image1",),
            assets=(
                AssetRef(kind="image", tag="@Image1", role=ReferenceRole.PRODUCT_HERO, notes="smart water bottle packaging label product hero"),
            ),
        ),
        GoldenCase(
            name="no_reference_t2v",
            idea="Create an 8s cinematic mountain sunrise shot with a slow push-in and stable atmosphere.",
            duration_s=8,
            expected_niche="cinematic",
            expected_asset_mode="t2v",
            expected_shot_count=1,
        ),
    ]


GOLDEN_CASES = _golden_cases()




def test_phase5_knowledge_rules_jsonl_has_provenance_and_targets() -> None:
    """Rules should be traceable to repo/source and exact implementation targets."""
    from seedance.contracts import SeedanceKnowledgeRule

    rows = _read_jsonl(RULES_PATH)

    assert len(rows) >= 8
    required = {
        "rule_id",
        "source_repo",
        "source_url",
        "license",
        "description",
        "applied_to_file",
        "applied_to_function",
    }
    seen_ids: set[str] = set()
    for row in rows:
        assert required.issubset(row), row
        assert row["rule_id"] not in seen_ids
        seen_ids.add(row["rule_id"])
        assert row["source_url"].startswith("https://github.com/")
        assert row["applied_to_file"].startswith("backend/")
        assert row["applied_to_function"]

        SeedanceKnowledgeRule(
            rule_id=row["rule_id"],
            source_repo=row["source_repo"],
            source_url=row["source_url"],
            license=row["license"],
            rule_type=row["rule_type"],
            applies_to_files=row["applies_to_files"],
            target_functions=row["target_functions"],
            summary=row["summary"],
            implementation_notes=row.get("implementation_notes", ""),
            phase=row.get("phase", "5"),
            severity=row.get("severity", "info"),
            tags=row.get("tags", []),
        )

    assert "dexhunter.reference_role_assignment.v1" in seen_ids
    assert "lanshu.formula_8_elements.v1" in seen_ids
    assert "lanshu.storyboard_3_5_shot.v1" in seen_ids


def test_phase5_knowledge_registry_loads_canonical_rules_jsonl() -> None:
    """Runtime registry should use rules.jsonl as the single rule source."""
    from seedance.knowledge_registry import SeedanceKnowledgeRegistry

    registry = SeedanceKnowledgeRegistry.from_jsonl(RULES_PATH)
    registry.require_rule_ids(["lanshu.formula_8_elements.v1"])

    formula_rules = registry.rules_for_file("backend/seedance/prompt_formula.py")
    function_rules = registry.rules_for_function("build_seedance_prompt_formula")

    assert any(rule.rule_id == "lanshu.formula_8_elements.v1" for rule in formula_rules)
    assert any(rule.rule_id == "dexhunter.prompt_time_segments.v1" for rule in function_rules)
    assert {source.source_repo for source in registry.list_sources()} >= {
        "dexhunter/seedance2-skill",
        "cclank/lanshu-awesome-ai-video-kit",
    }


def test_phase5_examples_jsonl_has_metadata_and_retriever_coverage() -> None:
    """Curated examples should keep source attribution and ranking metadata."""
    from seedance.example_retriever import ExampleRetriever

    rows = _read_jsonl(EXAMPLES_PATH)

    assert len(rows) >= 9
    required = {
        "example_id",
        "source_repo",
        "source_url",
        "license",
        "niche",
        "duration_s",
        "asset_mode",
        "shot_count",
        "prompt_excerpt",
        "prompt_hash",
    }
    niches = {row["niche"] for row in rows}
    for row in rows:
        assert required.issubset(row), row
        assert row["source_url"].startswith("https://github.com/")
        assert len(row["prompt_hash"]) == 64
        assert isinstance(row["duration_s"], int)
        assert isinstance(row["shot_count"], int)

    assert {"beauty", "drama", "food", "tech", "education", "ugc", "cinematic"}.issubset(niches)

    retriever = ExampleRetriever.from_jsonl(EXAMPLES_PATH)
    examples = retriever.retrieve(
        niche="beauty",
        asset_mode="multi_reference",
        shot_count=3,
        duration_s=15,
        continuity_tags=["product_lock"],
        limit=4,
    )
    assert 2 <= len(examples) <= 4
    assert examples[0].example_id == "zerolu_perfume_multiref_ad_15s"
    assert all(example.source_repo and example.source_url for example in examples)


def test_phase5_curated_example_store_loads_canonical_examples_jsonl() -> None:
    """CuratedExampleStore should read examples.jsonl without legacy fallback files."""
    from seedance.curated_examples import CuratedExampleStore

    store = CuratedExampleStore.from_jsonl(EXAMPLES_PATH)
    beauty_examples = store.by_niche("beauty")

    assert store.get("zerolu_perfume_multiref_ad_15s") is not None
    assert beauty_examples
    assert all(example.source_repo for example in store.list_examples())


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda case: case.name)
def test_seedance_golden_case_pipeline_contracts(case: GoldenCase) -> None:
    """Golden cases lock core regression signals across the full planning path."""
    from pipeline.approval_lock import ApprovalLock
    from pipeline.contracts import canonical_hash
    from seedance.prompt_linter import PromptLinter

    result = _run_golden_case(case)
    analyzed = result["analyzed"]
    creative_plan = result["creative_plan"]
    storyboard = result["storyboard"]
    execution_plan = result["execution_plan"]

    assert analyzed.detected_niche == case.expected_niche
    assert creative_plan.reference_strategy["asset_mode"] == case.expected_asset_mode
    assert len(storyboard.scenes) == case.expected_shot_count
    assert len(execution_plan.shots) == case.expected_shot_count
    assert execution_plan.model == case.expected_model
    assert all(shot.model == case.expected_model for shot in execution_plan.shots)

    for expected_tag in case.expected_reference_tags:
        assert any(expected_tag in scene.reference_bindings for scene in storyboard.scenes)
        assert any(asset.tag == expected_tag for shot in execution_plan.shots for asset in shot.references)
    if not case.expected_reference_tags:
        assert all(scene.reference_bindings == [] for scene in storyboard.scenes)
        assert all(shot.references == [] for shot in execution_plan.shots)

    assert "Subject:" in execution_plan.compiled_prompt
    assert "Action:" in execution_plan.compiled_prompt
    assert "Camera:" in execution_plan.compiled_prompt
    assert "Quality:" in execution_plan.compiled_prompt
    assert "Constraints:" in execution_plan.compiled_prompt
    assert "no watermark" in execution_plan.compiled_prompt
    assert len(execution_plan.compiled_prompt) > 250

    lint_issues = PromptLinter().lint(execution_plan.compiled_prompt)
    assert not any(issue.severity == "error" for issue in lint_issues)
    assert not any(warning.startswith("seedance.basic.missing") for warning in execution_plan.linter_warnings)

    approval_lock = ApprovalLock.from_execution_plan(
        idea=case.idea,
        execution_plan=execution_plan,
        approved_by="phase5-golden",
        approval_source="prompt_preview",
    )
    approval_hash = canonical_hash(approval_lock.model_dump(mode="json"))
    verification = approval_lock.verify_against(idea=case.idea, execution_plan=execution_plan)

    assert len(approval_hash) == 64
    assert len(approval_lock.execution_plan_hash) == 64
    assert verification.valid is True
    assert verification.mismatched_fields == []


def _run_golden_case(case: GoldenCase) -> dict[str, object]:
    from pipeline.contracts import InputContract
    from pipeline.creative_planning import CreativePlanner
    from pipeline.input_analysis import InputAnalyzer
    from pipeline.storyboard_generation import StoryboardGenerator
    from seedance.prompt_compiler import SeedancePromptCompiler

    input_contract = InputContract(
        user_idea=case.idea,
        duration_hint_s=case.duration_s,
        aspect_ratio="9:16",
        resolution="1080p",
        assets=list(case.assets),
    )
    analyzed = InputAnalyzer().analyze(input_contract)
    analyzed = analyzed.model_copy(update={
        "metadata": {
            **analyzed.metadata,
            "assets": [
                asset.model_dump(mode="json", exclude_none=True)
                for asset in case.assets
                if hasattr(asset, "model_dump")
            ],
        }
    })
    creative_plan = CreativePlanner().plan(analyzed)
    storyboard = StoryboardGenerator().generate(creative_plan, analyzed)
    execution_plan = SeedancePromptCompiler().compile(creative_plan, storyboard, analyzed)
    execution_plan = execution_plan.model_copy(update={
        "cost_estimate": {
            "total_cost_usd": round(execution_plan.duration_s * 0.06, 2),
            "currency": "USD",
        },
    })
    return {
        "input_contract": input_contract,
        "analyzed": analyzed,
        "creative_plan": creative_plan,
        "storyboard": storyboard,
        "execution_plan": execution_plan,
    }


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        rows.append(json.loads(text))
    return rows
