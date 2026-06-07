from pipeline.contracts import (
    AnalyzedInput,
    AssetRef,
    CreativePlan,
    ReferenceRole,
    StoryboardContract,
    StoryboardScene,
)
from seedance.prompt_compiler import SeedancePromptCompiler


def test_seedance_prompt_compiler_persists_prompt_os_metadata_for_one_shot_refs() -> None:
    product_ref = AssetRef(
        asset_id="asset_product",
        kind="image",
        url="https://cdn.example.com/product.png",
        tag="@image_1",
        role=ReferenceRole.PRODUCT_HERO,
        role_locked=True,
        role_confidence=0.96,
        name="Serum bottle packshot",
    )
    analyzed = AnalyzedInput(
        input_id="input_prompt_os",
        idea_hash="idea_hash_prompt_os",
        normalized_idea="Create an 8 second premium product demo for a serum bottle.",
        detected_niche="beauty",
        intent="product_demo",
        target_platform="tiktok",
        target_market="vn",
        duration_s=8,
        metadata={"assets": [product_ref]},
    )
    creative_plan = CreativePlan(
        analysis_id=analyzed.analysis_id,
        target_niche="beauty",
        objective="Show the serum bottle as the hero product with a clean texture proof.",
        hook_pattern="product hero reveal",
        duration_s=8,
        aspect_ratio="9:16",
        style_direction="premium macro beauty lighting, clean background, stable camera",
        audio_direction="soft premium product reveal beat",
        constraints=["no watermark"],
        consistency_plan={"product_lock": True},
        metadata={"resolution": "1080p"},
    )
    storyboard = StoryboardContract(
        creative_plan_id=creative_plan.creative_plan_id,
        duration_s=8,
        aspect_ratio="9:16",
        scenes=[
            StoryboardScene(
                index=0,
                duration_s=8,
                beat="hero product reveal",
                visual_intent="serum bottle is large, readable, and cleanly lit",
                action="slowly reveal product texture and hold the bottle steady",
                camera_movement="slow macro push-in",
                spatial_change="start close, settle into hero frame",
                audio_intent="soft premium beat",
            )
        ],
    )

    plan = SeedancePromptCompiler().compile(
        creative_plan=creative_plan,
        storyboard=storyboard,
        analyzed_input=analyzed,
    )

    assert plan.shots
    shot = plan.shots[0]
    assert shot.references and shot.references[0].asset_id == "asset_product"
    assert "Reference Jobs:" in shot.compiled_prompt
    assert "@image_1" in shot.compiled_prompt
    assert "product_hero" in shot.compiled_prompt
    assert "no product redesign" in shot.negative_prompt
    assert "no logo drift" in shot.negative_prompt
    assert "seedance_preflight" in shot.metadata
    assert "seedance_preflight" in plan.metadata
    assert "reference_sufficiency" in plan.metadata
    assert plan.metadata["needs_product_consistency"] is True
    assert "seedance_prompt_os.reference_jobs" in shot.rules_applied
    assert "seedance_prompt_os.plan_preflight_summary" in plan.rules_applied
