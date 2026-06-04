"""Seedance prompt compiler for Phase 1b integration.

The compiler stays deterministic and small. Phase 1b rule depth lives in the
formula, linter, and reference policy modules; this class only wires them into
SeedanceExecutionPlan contracts.
"""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from pipeline.contracts import (
    AnalyzedInput,
    AssetRef,
    CreativePlan,
    SeedanceExecutionPlan,
    SeedanceShotPlan,
    StoryboardContract,
    StoryboardScene,
)
from seedance.model_router import SeedanceModelRouter
from seedance.prompt_formula import SeedancePromptFormula
from seedance.prompt_linter import PromptLinter
from seedance.reference_policy import ReferencePolicy


class SeedancePromptCompiler:
    """Compile typed creative/storyboard inputs into Seedance render plans."""

    def __init__(
        self,
        *,
        prompt_formula: SeedancePromptFormula | None = None,
        linter: PromptLinter | None = None,
        reference_policy: ReferencePolicy | None = None,
        model_router: SeedanceModelRouter | None = None,
    ) -> None:
        self.prompt_formula = prompt_formula or SeedancePromptFormula()
        self.linter = linter or PromptLinter()
        self.reference_policy = reference_policy or ReferencePolicy()
        self.model_router = model_router or SeedanceModelRouter()

    def compile(
        self,
        creative_plan: CreativePlan,
        storyboard: StoryboardContract,
        analyzed_input: AnalyzedInput,
    ) -> SeedanceExecutionPlan:
        """Compile a SeedanceExecutionPlan from Phase 0 contracts."""
        scenes = storyboard.scenes or [_fallback_scene(creative_plan)]
        all_warnings: list[str] = []
        shot_plans: list[SeedanceShotPlan] = []
        available_assets = _metadata_asset_refs(analyzed_input)
        phase67_rule_ids = _phase67_rule_ids(creative_plan)
        strategy_id = _creative_strategy_id(creative_plan)
        identity_bible_id = str(creative_plan.consistency_plan.get("identity_bible_id") or "")
        consistency_score = creative_plan.consistency_plan.get("consistency_score")
        consistency_policy_action = creative_plan.consistency_plan.get("consistency_policy_action")
        consistency_policy_reasons = list(creative_plan.consistency_plan.get("consistency_policy_reasons") or [])
        consistency_risk_flags = list(creative_plan.consistency_plan.get("consistency_risk_flags") or [])
        long_form_readiness = creative_plan.metadata.get("long_form_readiness") or {}
        needs_identity_consistency = bool(creative_plan.metadata.get("needs_identity_consistency"))
        needs_product_consistency = bool(creative_plan.metadata.get("needs_product_consistency"))

        for index, scene in enumerate(scenes):
            references = self.reference_policy.select_references_for_scene(
                scene=scene,
                available_assets=available_assets,
            )
            model = self.model_router.route(
                creative_plan=creative_plan,
                scene=scene,
                references=references,
            )
            prompt = self.prompt_formula.build_prompt(
                creative_plan=creative_plan,
                scene=scene,
                analyzed_input=analyzed_input,
                storyboard=storyboard,
            )
            issues = self.linter.lint(prompt)
            warnings = [_format_issue(issue.rule_id, issue.message) for issue in issues]
            all_warnings.extend(warnings)
            shot_plans.append(SeedanceShotPlan(
                shot_id=scene.scene_id,
                index=index,
                duration_s=scene.duration_s,
                compiled_prompt=prompt,
                model=model,
                aspect_ratio=storyboard.aspect_ratio or creative_plan.aspect_ratio,
                resolution=str(creative_plan.metadata.get("resolution") or "1080p"),
                references=references,
                linter_warnings=warnings,
                rules_applied=phase67_rule_ids,
                metadata={
                    "creative_strategy_id": strategy_id,
                    "identity_bible_id": identity_bible_id or None,
                    "consistency_score": consistency_score,
                    "consistency_policy_action": consistency_policy_action,
                    "consistency_policy_reasons": consistency_policy_reasons,
                    "consistency_risk_flags": consistency_risk_flags,
                    "needs_identity_consistency": needs_identity_consistency,
                    "needs_product_consistency": needs_product_consistency,
                    "needs_style_consistency": True,
                    "scene_consistency_score": scene.metadata.get("consistency_score"),
                },
            ))

        return SeedanceExecutionPlan(
            storyboard_id=storyboard.storyboard_id,
            model=shot_plans[0].model if shot_plans else "seedance_2_0",
            aspect_ratio=storyboard.aspect_ratio or creative_plan.aspect_ratio,
            resolution=str(creative_plan.metadata.get("resolution") or "1080p"),
            duration_s=sum(shot.duration_s for shot in shot_plans) or storyboard.duration_s,
            compiled_prompt="\n\n".join(shot.compiled_prompt for shot in shot_plans),
            shots=shot_plans,
            reference_assets=available_assets,
            linter_warnings=all_warnings,
            rules_applied=phase67_rule_ids,
            metadata={
                "phase": "1b",
                "phase_extensions": ["6a", "7a"],
                "compiler": "rule_integrated",
                "advanced_rules_applied": True,
                "creative_strategy_id": strategy_id,
                "identity_bible_id": identity_bible_id or None,
                "consistency_score": consistency_score,
                "consistency_policy_action": consistency_policy_action,
                "consistency_policy_reasons": consistency_policy_reasons,
                "consistency_risk_flags": consistency_risk_flags,
                "long_form_readiness": long_form_readiness,
            },
        )


def _fallback_scene(creative_plan: CreativePlan) -> StoryboardScene:
    return StoryboardScene(
        index=0,
        duration_s=creative_plan.duration_s,
        beat=creative_plan.hook_pattern or "single seedance shot",
        visual_intent=creative_plan.objective,
        action="perform one clear visual action",
        camera_movement="static medium shot",
        spatial_change=creative_plan.style_direction,
        audio_intent=creative_plan.audio_direction,
    )


def _format_issue(rule_id: str, message: str) -> str:
    return f"{rule_id}: {message}"


def _metadata_asset_refs(analyzed_input: AnalyzedInput) -> list[AssetRef]:
    assets: list[AssetRef] = []
    for item in analyzed_input.metadata.get("assets") or []:
        if isinstance(item, AssetRef):
            assets.append(item)
        elif isinstance(item, dict):
            try:
                assets.append(AssetRef.model_validate(item))
            except ValidationError:
                continue
    return assets


def _phase67_rule_ids(creative_plan: CreativePlan) -> list[str]:
    metadata = creative_plan.metadata
    rule_ids: list[str] = []
    strategy = metadata.get("creative_strategy") or {}
    if isinstance(strategy, dict):
        rule_ids.extend(str(item) for item in strategy.get("rules_applied") or [])
        selected = strategy.get("selected_strategy") or {}
        if isinstance(selected, dict):
            rule_ids.extend(str(item) for item in selected.get("rules_applied") or [])
    consistency = metadata.get("consistency_score") or {}
    if isinstance(consistency, dict):
        rule_ids.extend(str(item) for item in consistency.get("rules_applied") or [])
    rule_ids.extend(str(item) for item in metadata.get("planning_rules") or [])
    return list(dict.fromkeys(item for item in rule_ids if item.strip()))


def _creative_strategy_id(creative_plan: CreativePlan) -> str | None:
    strategy = creative_plan.metadata.get("creative_strategy") or {}
    if not isinstance(strategy, dict):
        return None
    selected: Any = strategy.get("selected_strategy") or {}
    if not isinstance(selected, dict):
        return None
    return str(selected.get("strategy_id") or "") or None


__all__ = ["SeedancePromptCompiler"]
