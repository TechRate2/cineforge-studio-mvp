"""Benchmark case catalog for launch-readiness runs.

Cases compile through the real CineForge planning and Seedance Prompt OS stack.
They do not contain vendor output, scores, or fabricated evidence.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pipeline.contracts import AssetRef, InputContract, ReferenceRole
from pipeline.creative_planning import CreativePlanner
from pipeline.input_analysis import InputAnalyzer
from pipeline.storyboard_generation import StoryboardGenerator
from seedance.prompt_compiler import SeedancePromptCompiler

from benchmark.runner import BenchmarkRenderCase


class BenchmarkCaseDefinition(BaseModel):
    """One deterministic benchmark brief before prompt compilation."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    idea: str
    niche: str
    runtime_class: str = "short"
    duration_s: int = Field(8, ge=1)
    target_platform: str = "tiktok"
    target_market: str = "auto"
    creative_treatment_id: str | None = None
    assets: list[AssetRef] = Field(default_factory=list)
    max_total_cost_usd: float | None = Field(None, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


def load_benchmark_case_definitions() -> list[BenchmarkCaseDefinition]:
    """Return the built-in launch benchmark catalog."""
    return [
        BenchmarkCaseDefinition(
            case_id="bench_beauty_product_ugc_12s",
            niche="beauty",
            runtime_class="short",
            duration_s=12,
            creative_treatment_id="proof_first_ugc",
            idea="Create a 12s TikTok beauty serum UGC ad: creator hook, texture proof, product hero payoff, Vietnamese market.",
            assets=[
                _asset(
                    "bench_beauty_serum",
                    ReferenceRole.PRODUCT_HERO,
                    "https://cdn.test/bench/beauty-serum-product.png",
                    "serum bottle product packaging hero reference",
                )
            ],
            metadata={"benchmark_goal": "product_ugc_shortform"},
        ),
        BenchmarkCaseDefinition(
            case_id="bench_food_restaurant_12s",
            niche="food",
            runtime_class="short",
            duration_s=12,
            creative_treatment_id="fast_social_hook",
            idea="Create a 12s restaurant food video: sizzling prep macro, plating texture, final table payoff for TikTok.",
            metadata={"benchmark_goal": "food_sensory_shortform"},
        ),
        BenchmarkCaseDefinition(
            case_id="bench_app_saas_demo_15s",
            niche="app_saas",
            runtime_class="short",
            duration_s=15,
            creative_treatment_id="proof_first_ugc",
            idea="Create a 15s SaaS app demo video: dashboard problem, one-click workflow, clear productivity payoff.",
            metadata={"benchmark_goal": "app_demo_shortform"},
        ),
        BenchmarkCaseDefinition(
            case_id="bench_fashion_editorial_12s",
            niche="fashion",
            runtime_class="short",
            duration_s=12,
            creative_treatment_id="cinematic_premium",
            idea="Create a 12s high-fashion editorial clip: silhouette entrance, fabric motion, premium hero pose.",
            assets=[
                _asset(
                    "bench_fashion_style",
                    ReferenceRole.STYLE_REFERENCE,
                    "https://cdn.test/bench/fashion-editorial-style.png",
                    "editorial lighting and color style reference",
                )
            ],
            metadata={"benchmark_goal": "fashion_cinematic_shortform"},
        ),
        BenchmarkCaseDefinition(
            case_id="bench_travel_lifestyle_12s",
            niche="travel_lifestyle",
            runtime_class="short",
            duration_s=12,
            creative_treatment_id="cinematic_premium",
            idea="Create a 12s travel lifestyle clip: destination reveal, human moment, cinematic sunset payoff.",
            metadata={"benchmark_goal": "travel_lifestyle_shortform"},
        ),
        BenchmarkCaseDefinition(
            case_id="bench_real_estate_15s",
            niche="real_estate",
            runtime_class="short",
            duration_s=15,
            creative_treatment_id="cinematic_premium",
            idea="Create a 15s real estate walkthrough: exterior hook, interior living space, premium listing payoff.",
            metadata={"benchmark_goal": "real_estate_shortform"},
        ),
        BenchmarkCaseDefinition(
            case_id="bench_short_drama_45s",
            niche="drama",
            runtime_class="short_film",
            duration_s=45,
            creative_treatment_id="short_drama_arc",
            idea="Create a controlled 45s short drama: quiet tension, emotional reveal, reaction payoff, clear scene handoffs.",
            assets=[
                _asset(
                    "bench_drama_character",
                    ReferenceRole.CHARACTER_ANCHOR,
                    "https://cdn.test/bench/drama-character-anchor.png",
                    "main character face and outfit anchor reference",
                )
            ],
            metadata={"benchmark_goal": "controlled_short_drama"},
        ),
    ]


def compile_benchmark_case(definition: BenchmarkCaseDefinition) -> BenchmarkRenderCase:
    """Compile one benchmark definition through the real planning pipeline."""
    input_contract = InputContract(
        user_idea=definition.idea,
        target_platform=definition.target_platform,
        target_market=definition.target_market,
        duration_hint_s=definition.duration_s,
        assets=definition.assets,
    )
    analyzed = InputAnalyzer().analyze(input_contract)
    creative_plan = CreativePlanner().plan(analyzed)
    storyboard = StoryboardGenerator().generate(creative_plan, analyzed)
    execution_plan = SeedancePromptCompiler().compile(creative_plan, storyboard, analyzed)
    return BenchmarkRenderCase(
        case_id=definition.case_id,
        idea=analyzed.normalized_idea,
        niche=definition.niche,
        runtime_class=definition.runtime_class,
        target_platform=definition.target_platform,
        target_market=definition.target_market,
        creative_treatment_id=definition.creative_treatment_id,
        execution_plan=execution_plan,
        max_total_cost_usd=definition.max_total_cost_usd,
        metadata={
            **definition.metadata,
            "case_definition_id": definition.case_id,
            "compiled_analysis_id": analyzed.analysis_id,
            "compiled_creative_plan_id": creative_plan.creative_plan_id,
            "compiled_storyboard_id": storyboard.storyboard_id,
        },
    )


def compile_benchmark_cases(case_ids: set[str] | None = None) -> list[BenchmarkRenderCase]:
    """Compile selected benchmark cases by id, or the full catalog."""
    definitions = load_benchmark_case_definitions()
    if case_ids:
        definitions = [case for case in definitions if case.case_id in case_ids]
    return [compile_benchmark_case(definition) for definition in definitions]


def _asset(asset_id: str, role: ReferenceRole, url: str, notes: str) -> AssetRef:
    return AssetRef(
        asset_id=asset_id,
        kind="image",
        url=url,
        tag="@Image1",
        role=role,
        role_locked=True,
        role_confidence=0.95,
        notes=notes,
    )


__all__ = [
    "BenchmarkCaseDefinition",
    "compile_benchmark_case",
    "compile_benchmark_cases",
    "load_benchmark_case_definitions",
]
