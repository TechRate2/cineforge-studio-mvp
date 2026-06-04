"""Phase 5 regression tests for storyboard generation contracts."""
from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_storyboard_generator_keeps_complex_requests_in_3_to_5_shots() -> None:
    """Complex requests should use the Lanshu-style 3-5 shot structure."""
    from pipeline.contracts import AssetRef, InputContract, ReferenceRole
    from pipeline.creative_planning import CreativePlanner
    from pipeline.input_analysis import InputAnalyzer
    from pipeline.storyboard_generation import StoryboardGenerator

    analyzed = InputAnalyzer().analyze(InputContract(
        user_idea=(
            "Create a 15s beauty serum ad: macro texture hook, hero product reveal, "
            "then final payoff frame with premium reflective lighting."
        ),
        duration_hint_s=15,
        assets=[
            AssetRef(
                kind="image",
                tag="@Image1",
                role=ReferenceRole.PRODUCT_HERO,
                role_locked=True,
                notes="serum bottle product hero reference",
            )
        ],
    ))
    creative_plan = CreativePlanner().plan(analyzed)
    storyboard = StoryboardGenerator().generate(creative_plan, analyzed)

    assert 3 <= len(storyboard.scenes) <= 5
    assert storyboard.duration_s == 15
    assert storyboard.metadata["rules_applied"][0] == "lanshu.storyboard.3_5_shot_structure"
    assert [scene.index for scene in storyboard.scenes] == list(range(len(storyboard.scenes)))
    for scene in storyboard.scenes:
        assert scene.beat
        assert scene.camera_movement
        assert scene.action
        assert scene.spatial_change
        assert scene.audio_intent
        assert scene.continuity_notes
        assert "@Image1" in scene.reference_bindings


def test_storyboard_generator_keeps_simple_t2v_as_single_shot() -> None:
    """Simple no-reference T2V requests should not be inflated into a sequence."""
    from pipeline.contracts import InputContract
    from pipeline.creative_planning import CreativePlanner
    from pipeline.input_analysis import InputAnalyzer
    from pipeline.storyboard_generation import StoryboardGenerator

    analyzed = InputAnalyzer().analyze(InputContract(
        user_idea="Create an 8s cinematic mountain sunrise shot with a slow push-in.",
        duration_hint_s=8,
        assets=[],
    ))
    creative_plan = CreativePlanner().plan(analyzed)
    storyboard = StoryboardGenerator().generate(creative_plan, analyzed)

    assert len(storyboard.scenes) == 1
    assert storyboard.scenes[0].duration_s == 8
    assert storyboard.scenes[0].reference_bindings == []
    assert storyboard.metadata["rules_applied"][0] == "phase2.storyboard.single_shot"


def test_storyboard_reference_bindings_follow_priority_roles() -> None:
    """Character, product, and audio anchors should bind across all planned shots."""
    from pipeline.contracts import AssetRef, InputContract, ReferenceRole
    from pipeline.creative_planning import CreativePlanner
    from pipeline.input_analysis import InputAnalyzer
    from pipeline.storyboard_generation import StoryboardGenerator

    analyzed = InputAnalyzer().analyze(InputContract(
        user_idea="Create a 12s creator product story with the same presenter and product.",
        duration_hint_s=12,
        assets=[
            AssetRef(kind="image", tag="@Image1", role=ReferenceRole.CHARACTER_ANCHOR, notes="presenter face close-up"),
            AssetRef(kind="image", tag="@Image2", role=ReferenceRole.PRODUCT_HERO, notes="main product packaging"),
            AssetRef(kind="audio", tag="@Audio1", role=ReferenceRole.AUDIO_VOICE, notes="presenter voice reference"),
        ],
    ))
    creative_plan = CreativePlanner().plan(analyzed)
    storyboard = StoryboardGenerator().generate(creative_plan, analyzed)

    assert len(storyboard.scenes) >= 3
    for scene in storyboard.scenes:
        assert {"@Image1", "@Image2", "@Audio1"}.issubset(set(scene.reference_bindings))
