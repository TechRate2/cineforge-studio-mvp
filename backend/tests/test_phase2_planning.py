"""Phase 2 tests for planning, storyboard generation, and example retrieval."""
from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_phase2_input_analyzer_detects_niche_and_reference_risks() -> None:
    """InputAnalyzer should expose niche, reference sufficiency, and risks."""
    from pipeline.contracts import InputContract
    from pipeline.input_analysis import InputAnalyzer

    input_contract = InputContract(
        user_idea="Create a 12s premium perfume product ad with macro bottle shots",
        duration_hint_s=12,
        assets=[],
    )

    analyzed = InputAnalyzer().analyze(input_contract)

    assert analyzed.detected_niche == "beauty"
    assert analyzed.intent == "product_ad"
    assert analyzed.asset_summary["reference_sufficiency"] == "insufficient"
    assert "weak_product_lock" in analyzed.metadata["primary_risks"]


def test_phase2_creative_planner_decides_multi_shot_and_locks() -> None:
    """CreativePlanner should make useful shot and consistency decisions."""
    from pipeline.contracts import AssetRef, InputContract, ReferenceRole
    from pipeline.creative_planning import CreativePlanner
    from pipeline.input_analysis import InputAnalyzer

    analyzed = InputAnalyzer().analyze(InputContract(
        user_idea="Create a 15s perfume ad: macro texture, hero reveal, final payoff",
        duration_hint_s=15,
        assets=[
            AssetRef(
                kind="image",
                tag="@Image1",
                role=ReferenceRole.PRODUCT_HERO,
                notes="perfume bottle product hero reference",
            )
        ],
    ))

    plan = CreativePlanner().plan(analyzed)

    assert plan.metadata["phase"] == "2"
    assert plan.metadata["shot_mode"] == "multi_shot"
    assert plan.shot_count == 3
    assert plan.reference_strategy["asset_mode"] == "i2v"
    assert plan.consistency_plan["product_lock"] is True
    assert "macro texture hook" in plan.hook_pattern


def test_phase2_storyboard_generator_builds_required_scene_fields() -> None:
    """StoryboardGenerator should build 3-5 structured shots for complex plans."""
    from pipeline.contracts import AssetRef, InputContract, ReferenceRole
    from pipeline.creative_planning import CreativePlanner
    from pipeline.input_analysis import InputAnalyzer
    from pipeline.storyboard_generation import StoryboardGenerator

    analyzed = InputAnalyzer().analyze(InputContract(
        user_idea="Create a 15s food video with ingredient hook, cooking macro, serve payoff",
        duration_hint_s=15,
        assets=[
            AssetRef(
                kind="image",
                tag="@Image1",
                role=ReferenceRole.PRODUCT_HERO,
                notes="finished dish product hero reference",
            )
        ],
    ))
    plan = CreativePlanner().plan(analyzed)
    storyboard = StoryboardGenerator().generate(plan, analyzed)

    assert storyboard.metadata["phase"] == "2"
    assert len(storyboard.scenes) == 3
    assert sum(scene.duration_s for scene in storyboard.scenes) == 15
    for scene in storyboard.scenes:
        assert scene.beat
        assert scene.camera_movement
        assert scene.action
        assert scene.spatial_change
        assert scene.audio_intent
        assert scene.continuity_notes
        assert "@Image1" in scene.reference_bindings


def test_phase2_example_retriever_ranks_by_priority_order() -> None:
    """ExampleRetriever should prioritize exact niche before secondary signals."""
    from seedance.example_retriever import ExampleRetriever

    retriever = ExampleRetriever.from_jsonl()
    examples = retriever.retrieve(
        niche="beauty",
        asset_mode="multi_reference",
        shot_count=3,
        duration_s=15,
        continuity_tags=["product_lock", "reference_role_assignment"],
        style_tags=["commercial"],
        audio_tags=["voiceover"],
        limit=4,
    )

    assert 2 <= len(examples) <= 4
    assert examples[0].example_id == "zerolu_perfume_multiref_ad_15s"
    assert examples[0].source_repo == "ZeroLu/awesome-seedance"
    assert examples[0].source_url.startswith("https://github.com/ZeroLu/awesome-seedance")
    assert examples[0].license == "CC BY 4.0"
