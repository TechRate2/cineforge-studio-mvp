"""Seedance prompt compiler for Phase 1b integration.

The compiler stays deterministic and production-oriented. It serializes the
Seedance formula, binds reference jobs, lints prompt/reference readiness, writes
negative prompts, and stores an execution preflight summary directly on the
compiled plan. Paid render workers can then reject bad payloads before vendor
calls instead of discovering obvious issues after spending credits.
"""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from pipeline.contracts import (
    AnalyzedInput,
    AssetRef,
    CreativePlan,
    ReferenceRole,
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
        shot_preflight: list[dict[str, Any]] = []
        available_assets = _metadata_asset_refs(analyzed_input)
        phase67_rule_ids = _phase67_rule_ids(creative_plan)
        strategy_id = _creative_strategy_id(creative_plan)
        identity_bible_id = str(creative_plan.consistency_plan.get("identity_bible_id") or "")
        consistency_score = creative_plan.consistency_plan.get("consistency_score")
        consistency_policy_action = creative_plan.consistency_plan.get("consistency_policy_action")
        consistency_policy_reasons = list(creative_plan.consistency_plan.get("consistency_policy_reasons") or [])
        consistency_risk_flags = list(creative_plan.consistency_plan.get("consistency_risk_flags") or [])
        long_form_readiness = creative_plan.metadata.get("long_form_readiness") or {}
        needs_identity_consistency = bool(
            creative_plan.metadata.get("needs_identity_consistency")
            or creative_plan.consistency_plan.get("character_lock")
        )
        needs_product_consistency = bool(
            creative_plan.metadata.get("needs_product_consistency")
            or creative_plan.consistency_plan.get("product_lock")
        )
        plan_reference_issues = [
            *self.reference_policy.validate_reference_caps(available_assets),
            *self.reference_policy.validate_identity_bible_assets(
                assets=available_assets,
                needs_character_lock=needs_identity_consistency,
                needs_product_lock=needs_product_consistency,
            ),
        ]
        plan_reference_warnings = [_format_policy_issue(issue) for issue in plan_reference_issues]
        all_warnings.extend(plan_reference_warnings)

        for index, scene in enumerate(scenes):
            references = self.reference_policy.select_references_for_scene(
                scene=scene,
                available_assets=available_assets,
            )
            if not references and len(scenes) == 1:
                # One-shot jobs should still expose available references to the compiler;
                # ReferencePolicy caps and role checks decide whether they are usable.
                references = self.reference_policy.prioritize_reference_assets(available_assets)
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
            prompt = _append_reference_jobs(prompt, references)
            issues = self.linter.lint(prompt)
            prompt_warnings = [_format_issue(issue.rule_id, issue.message) for issue in issues]
            reference_issues = [
                *self.reference_policy.validate_reference_caps(references),
                *self.reference_policy.validate_reference_role_conflicts(references),
            ]
            reference_warnings = [_format_policy_issue(issue) for issue in reference_issues]
            warnings = list(dict.fromkeys([*prompt_warnings, *reference_warnings]))
            all_warnings.extend(warnings)
            reference_bindings = {str(asset.tag or asset.asset_id): asset.role for asset in references if asset.tag or asset.asset_id}
            preflight_summary = _shot_preflight_summary(
                scene_id=scene.scene_id,
                prompt_warnings=prompt_warnings,
                reference_warnings=reference_warnings,
            )
            shot_preflight.append(preflight_summary)
            shot_plans.append(SeedanceShotPlan(
                shot_id=scene.scene_id,
                index=index,
                duration_s=scene.duration_s,
                compiled_prompt=prompt,
                negative_prompt=_negative_prompt(
                    needs_identity_consistency=needs_identity_consistency,
                    needs_product_consistency=needs_product_consistency,
                    extra_constraints=creative_plan.constraints,
                ),
                model=model,
                aspect_ratio=storyboard.aspect_ratio or creative_plan.aspect_ratio,
                resolution=str(creative_plan.metadata.get("resolution") or "1080p"),
                references=references,
                reference_bindings=reference_bindings,
                linter_warnings=warnings,
                rules_applied=list(dict.fromkeys([
                    *phase67_rule_ids,
                    "seedance_prompt_os.reference_jobs",
                    "seedance_prompt_os.negative_prompt_policy",
                    "seedance_prompt_os.preflight_summary",
                ])),
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
                    "seedance_preflight": preflight_summary,
                },
            ))

        reference_sufficiency = self.reference_policy.score_reference_sufficiency(
            assets=available_assets,
            needs_character_lock=needs_identity_consistency,
            needs_product_lock=needs_product_consistency,
        )
        plan_preflight = _plan_preflight_summary(
            shot_preflight=shot_preflight,
            reference_sufficiency=reference_sufficiency,
            plan_reference_warnings=plan_reference_warnings,
        )
        return SeedanceExecutionPlan(
            storyboard_id=storyboard.storyboard_id,
            model=shot_plans[0].model if shot_plans else "seedance_2_0",
            aspect_ratio=storyboard.aspect_ratio or creative_plan.aspect_ratio,
            resolution=str(creative_plan.metadata.get("resolution") or "1080p"),
            duration_s=sum(shot.duration_s for shot in shot_plans) or storyboard.duration_s,
            compiled_prompt="\n\n".join(shot.compiled_prompt for shot in shot_plans),
            shots=shot_plans,
            reference_assets=available_assets,
            linter_warnings=list(dict.fromkeys(all_warnings)),
            rules_applied=list(dict.fromkeys([
                *phase67_rule_ids,
                "seedance_prompt_os.plan_preflight_summary",
                "seedance_prompt_os.reference_sufficiency_score",
            ])),
            metadata={
                "phase": "1b",
                "phase_extensions": ["6a", "7a", "prompt_os_preflight"],
                "compiler": "rule_integrated_prompt_os",
                "advanced_rules_applied": True,
                "creative_strategy_id": strategy_id,
                "identity_bible_id": identity_bible_id or None,
                "consistency_score": consistency_score,
                "consistency_policy_action": consistency_policy_action,
                "consistency_policy_reasons": consistency_policy_reasons,
                "consistency_risk_flags": consistency_risk_flags,
                "long_form_readiness": long_form_readiness,
                "needs_identity_consistency": needs_identity_consistency,
                "needs_product_consistency": needs_product_consistency,
                "seedance_preflight": plan_preflight,
                "reference_sufficiency": reference_sufficiency,
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


def _append_reference_jobs(prompt: str, references: list[AssetRef]) -> str:
    if not references:
        return prompt
    lines = ["Reference Jobs:"]
    for asset in references[:12]:
        tag = str(asset.tag or asset.asset_id)
        role = asset.role.value if isinstance(asset.role, ReferenceRole) else str(asset.role)
        name = str(asset.name or asset.notes or "reference").strip()[:120]
        lines.append(f"{tag}: use as {role}; preserve its assigned job only. {name}".strip())
    block = "\n".join(lines)
    if "Reference Jobs:" in prompt:
        return prompt
    return f"{prompt}\n{block}".strip()


def _negative_prompt(
    *,
    needs_identity_consistency: bool,
    needs_product_consistency: bool,
    extra_constraints: list[str] | tuple[str, ...] | None,
) -> str:
    values = [
        "no subtitles",
        "no text overlays",
        "no watermark",
        "no random new characters",
        "no malformed hands or faces",
        "no abrupt unmotivated scene jumps",
        "no fake unreadable labels",
    ]
    if needs_identity_consistency:
        values.extend([
            "no face morphing",
            "no outfit drift",
            "no duplicate identity clones",
        ])
    if needs_product_consistency:
        values.extend([
            "no product redesign",
            "no logo drift",
            "no packaging geometry changes",
        ])
    values.extend(str(item).strip() for item in (extra_constraints or []) if str(item).strip().lower().startswith("no "))
    return ", ".join(dict.fromkeys(values))


def _shot_preflight_summary(
    *,
    scene_id: str,
    prompt_warnings: list[str],
    reference_warnings: list[str],
) -> dict[str, Any]:
    hard_failures = [item for item in [*prompt_warnings, *reference_warnings] if _is_error_warning(item)]
    warnings = [item for item in [*prompt_warnings, *reference_warnings] if item not in hard_failures]
    return {
        "schema_version": "cineforge.seedance_shot_preflight.v1",
        "scene_id": scene_id,
        "status": "fail" if hard_failures else "warn" if warnings else "pass",
        "hard_failures": hard_failures,
        "warnings": warnings,
        "prompt_warning_count": len(prompt_warnings),
        "reference_warning_count": len(reference_warnings),
    }


def _plan_preflight_summary(
    *,
    shot_preflight: list[dict[str, Any]],
    reference_sufficiency: dict[str, Any],
    plan_reference_warnings: list[str],
) -> dict[str, Any]:
    hard_failures = list(plan_reference_warnings)
    for report in shot_preflight:
        hard_failures.extend(str(item) for item in report.get("hard_failures") or [])
    hard_failures = [item for item in hard_failures if _is_error_warning(item)]
    warnings = list(plan_reference_warnings)
    for report in shot_preflight:
        warnings.extend(str(item) for item in report.get("warnings") or [])
    warnings = [item for item in warnings if item not in hard_failures]
    return {
        "schema_version": "cineforge.seedance_plan_preflight.v1",
        "status": "fail" if hard_failures else "warn" if warnings else "pass",
        "hard_failures": list(dict.fromkeys(hard_failures)),
        "warnings": list(dict.fromkeys(warnings)),
        "shot_count": len(shot_preflight),
        "reference_sufficiency": reference_sufficiency,
        "shot_reports": shot_preflight,
    }


def _is_error_warning(value: str) -> bool:
    text = value.lower()
    return any(token in text for token in (
        "missing_subject",
        "missing_action",
        "missing_camera",
        "missing a clear subject",
        "missing a clear action",
        "missing a clear camera",
        "duration_out_of_range",
        "duration must",
        "cap_image",
        "cap_video",
        "cap_audio",
        "cap_total",
        "supports at most",
        "cannot reliably serve",
    ))


def _format_issue(rule_id: str, message: str) -> str:
    return f"{rule_id}: {message}"


def _format_policy_issue(issue: Any) -> str:
    suffix = f" ({issue.tag or issue.asset_id})" if getattr(issue, "tag", None) or getattr(issue, "asset_id", None) else ""
    return f"{issue.rule_id}: {issue.message}{suffix}"


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
