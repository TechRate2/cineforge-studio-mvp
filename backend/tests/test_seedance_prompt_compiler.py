"""Phase 1b tests for Seedance prompt formula, linter, and reference policy."""
from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_phase1b_linter_keeps_basic_checks_and_formula_checks() -> None:
    """The linter should retain Phase 1a basics and add Phase 1b formula checks."""
    from seedance.prompt_linter import PromptLinter

    issues = PromptLinter().lint("Subject: A perfume bottle\nDuration: 16s")
    rule_ids = {issue.rule_id for issue in issues}

    assert "seedance.basic.missing_action" in rule_ids
    assert "seedance.basic.missing_camera" in rule_ids
    assert "seedance.basic.duration_out_of_range" in rule_ids
    assert "lanshu.formula.missing_lighting" in rule_ids
    assert "lanshu.formula.missing_constraints" in rule_ids


def test_phase1b_linter_flags_reference_camera_duration_and_constraints() -> None:
    """Phase 1b linter should catch common dexhunter/Lanshu prompt mistakes."""
    from seedance.prompt_linter import PromptLinter

    prompt = "\n".join([
        "Subject: A glass perfume bottle with gold cap",
        "Action: rotates, then explodes into mist, after that cut to a new table",
        "Scene: reflective studio table",
        "Lighting: soft key light",
        "Camera: static locked orbit push pan",
        "Timing: Duration: 4s",
        "Style: clean commercial",
        "Quality: high clarity",
        "Constraints: keep it elegant",
        "Use @Image1.",
    ])

    rule_ids = {issue.rule_id for issue in PromptLinter().lint(prompt)}

    assert "dexhunter.reference.vague_assignment" in rule_ids
    assert "dexhunter.camera.static_motion_conflict" in rule_ids
    assert "lanshu.camera.too_many_movements" in rule_ids
    assert "dexhunter.duration.too_complex_for_short_unit" in rule_ids
    assert "lanshu.constraints.missing_negative_constraints" in rule_ids


def test_phase1b_prompt_formula_builds_8_element_seedance_structure() -> None:
    """Prompt formula should expose Lanshu 8 elements and dexhunter structure."""
    from pipeline.contracts import AnalyzedInput, CreativePlan, StoryboardScene, canonical_hash
    from seedance.prompt_formula import build_seedance_prompt_formula

    analyzed = AnalyzedInput(
        input_id="input_test",
        idea_hash=canonical_hash("Create a product video"),
        normalized_idea="Create a product video",
        duration_s=8,
    )
    creative = CreativePlan(
        analysis_id=analyzed.analysis_id,
        objective="A glass perfume bottle with gold cap",
        duration_s=8,
        style_direction="clean cinematic commercial",
        constraints=["preserve premium reflective material"],
        metadata={"lighting": "soft studio key light", "needs_product_consistency": True},
    )
    scene = StoryboardScene(
        index=0,
        duration_s=8,
        visual_intent="A glass perfume bottle with gold cap",
        action="rotates slowly on a reflective table",
        camera_movement="static medium close-up",
        spatial_change="minimal studio table",
    )

    formula = build_seedance_prompt_formula(
        creative_plan=creative,
        scene=scene,
        analyzed_input=analyzed,
    )
    prompt = formula.to_prompt()

    assert "lanshu.formula.8_elements" in formula.rule_ids
    assert "dexhunter.formula.prompt_structure" in formula.rule_ids
    assert "Subject: A glass perfume bottle with gold cap" in prompt
    assert "Lighting: soft studio key light" in prompt
    assert "Quality:" in prompt
    assert "no subtitles" in prompt
    assert "no logo" in prompt
    assert "no watermark" in prompt
    assert "preserve product geometry" in prompt


def test_phase1b_time_segments_for_multi_shot() -> None:
    """Long or multi-shot prompts should produce deterministic time segments."""
    from pipeline.contracts import StoryboardScene
    from seedance.prompt_formula import build_time_segment_plan

    segments = build_time_segment_plan(
        duration_s=12,
        scenes=[
            StoryboardScene(
                index=0,
                duration_s=6,
                beat="hero reveal",
                action="product rotates",
                camera_movement="slow push-in",
                spatial_change="studio plinth",
            ),
            StoryboardScene(
                index=1,
                duration_s=6,
                beat="detail finish",
                action="mist wraps around bottle",
                camera_movement="static macro",
                spatial_change="macro label detail",
            ),
        ],
        force_multi_shot=True,
    )

    assert [(segment.start_s, segment.end_s) for segment in segments] == [(0, 6), (6, 12)]
    assert segments[0].label == "hero reveal"
    assert "slow push-in" in segments[0].prompt


def test_phase1b_reference_policy_caps_roles_priority_and_risks() -> None:
    """Reference policy should implement caps, roles, priority, and identity risks."""
    from pipeline.contracts import AssetRef, ReferenceRole
    from seedance.reference_policy import ReferencePolicy

    policy = ReferencePolicy()
    too_many_images = [AssetRef(kind="image", tag=f"@Image{i}") for i in range(10)]
    cap_rule_ids = {issue.rule_id for issue in policy.validate_reference_caps(too_many_images)}
    assert "dexhunter.reference.cap_image" in cap_rule_ids

    assets = [
        AssetRef(kind="video", tag="@Video1", notes="orbit camera movement reference"),
        AssetRef(kind="audio", tag="@Audio1", notes="BGM music beat"),
        AssetRef(kind="image", tag="@Image1", notes="main character face close-up portrait"),
        AssetRef(kind="image", tag="@Image2", notes="main character full-body outfit silhouette"),
    ]
    assigned = policy.assign_reference_roles(
        assets,
        prompt="@Image1 is the character face anchor, @Video1 provides camera movement, @Audio1 provides BGM.",
    )
    roles_by_tag = {asset.tag: asset.role for asset in assigned}
    assert roles_by_tag["@Image1"] == ReferenceRole.CHARACTER_ANCHOR
    assert roles_by_tag["@Video1"] == ReferenceRole.CAMERA_MOTION
    assert roles_by_tag["@Audio1"] == ReferenceRole.AUDIO_BGM

    prioritized = policy.prioritize_reference_assets(assigned)
    assert prioritized[0].tag == "@Image1"
    assert policy.detect_identity_anchor_risks(assigned) == []

    risky = assigned + [
        AssetRef(
            kind="image",
            tag="@Image3",
            role=ReferenceRole.CHARACTER_ANCHOR,
            notes="multi-view front side back character turnaround",
        )
    ]
    risk_rule_ids = {issue.rule_id for issue in policy.detect_identity_anchor_risks(risky)}
    assert "lanshu.identity.multi_view_anchor_risk" in risk_rule_ids


def test_phase1b_compiler_builds_execution_plan_with_rule_metadata() -> None:
    """Compiler should wire Phase 1b modules without taking over their rule logic."""
    from pipeline.contracts import (
        AnalyzedInput,
        AssetRef,
        CreativePlan,
        ReferenceRole,
        StoryboardContract,
        StoryboardScene,
        canonical_hash,
    )
    from seedance.prompt_compiler import SeedancePromptCompiler

    analyzed = AnalyzedInput(
        input_id="input_test",
        idea_hash=canonical_hash("Create a product video"),
        normalized_idea="Create a product video",
        detected_niche="beauty",
        duration_s=12,
        metadata={
            "assets": [
                AssetRef(
                    kind="image",
                    url="https://cdn.test/perfume-bottle.png",
                    tag="@Image1",
                    role=ReferenceRole.PRODUCT_HERO,
                    notes="glass perfume bottle with gold cap product hero reference",
                ).model_dump(mode="json")
            ]
        },
    )
    creative = CreativePlan(
        analysis_id=analyzed.analysis_id,
        objective="A glass perfume bottle with gold cap",
        duration_s=12,
        shot_count=2,
        style_direction="clean cinematic commercial",
        metadata={"lighting": "soft studio key light", "needs_product_consistency": True},
    )
    storyboard = StoryboardContract(
        creative_plan_id=creative.creative_plan_id,
        duration_s=12,
        scenes=[
            StoryboardScene(
                index=0,
                duration_s=6,
                beat="hero reveal",
                visual_intent="A glass perfume bottle with gold cap",
                action="rotates slowly on a reflective table",
                camera_movement="static medium shot",
                spatial_change="minimal studio table",
            ),
            StoryboardScene(
                index=1,
                duration_s=6,
                beat="macro finish",
                visual_intent="A glass perfume bottle with gold cap",
                action="mist wraps around the bottle label",
                camera_movement="static macro shot",
                spatial_change="macro label detail",
            ),
        ],
    )

    plan = SeedancePromptCompiler().compile(creative, storyboard, analyzed)

    assert plan.schema_version == "cineforge.seedance_execution_plan.v1"
    assert plan.metadata["phase"] == "1b"
    assert plan.metadata["advanced_rules_applied"] is True
    assert len(plan.shots) == 2
    assert "Lighting: soft studio key light" in plan.shots[0].compiled_prompt
    assert "Time Segments:" in plan.shots[0].compiled_prompt
    assert "no watermark" in plan.compiled_prompt
    assert plan.linter_warnings == []


def test_model_router_uses_real_deterministic_complexity_rules() -> None:
    """Model router should use deterministic complexity rules."""
    from pipeline.contracts import AssetRef, CreativePlan, ReferenceRole
    from seedance.model_router import SeedanceModelRouter

    router = SeedanceModelRouter()
    low_risk = CreativePlan(
        analysis_id="analysis_low",
        objective="A simple landscape sunrise",
        duration_s=6,
        shot_count=1,
        metadata={"budget_tier": "draft"},
    )
    premium = CreativePlan(
        analysis_id="analysis_premium",
        target_niche="beauty",
        objective="Premium perfume hero product ad",
        duration_s=12,
        shot_count=3,
        consistency_plan={"product_lock": True},
    )
    product_ref = AssetRef(
        kind="image",
        role=ReferenceRole.PRODUCT_HERO,
        url="https://cdn.test/p.png",
    )

    assert router.route(creative_plan=low_risk) == "seedance_2_0_fast"
    assert router.route(creative_plan=premium, references=[product_ref]) == "seedance_2_0"
