"""Brand kit and template application helpers for autonomous rendering."""
from __future__ import annotations

from typing import Any

from commercial.commercial_store import BrandKit, CommercialTemplate
from pipeline.contracts import CreativePlan, SeedanceExecutionPlan, SeedanceShotPlan


def apply_commercial_context_to_creative_plan(
    creative_plan: CreativePlan,
    *,
    brand_kit: BrandKit | None = None,
    template: CommercialTemplate | None = None,
) -> CreativePlan:
    """Apply brand and template constraints before storyboard/prompt compile."""
    metadata = dict(creative_plan.metadata or {})
    constraints = list(creative_plan.constraints or [])
    style_direction = creative_plan.style_direction
    hook_pattern = creative_plan.hook_pattern
    narrative_arc = list(creative_plan.narrative_arc or [])

    if template is not None:
        metadata["commercial_template"] = template.model_dump(mode="json")
        if template.hook_pattern:
            hook_pattern = template.hook_pattern
        if template.strategy:
            metadata["commercial_strategy_override"] = template.strategy
        if template.shot_structure:
            narrative_arc = template.shot_structure
        constraints.extend(template.prompt_constraints)
    if brand_kit is not None:
        metadata["brand_kit"] = brand_kit.model_dump(mode="json")
        brand_parts = []
        if brand_kit.style_guide:
            brand_parts.append(brand_kit.style_guide)
        if brand_kit.primary_colors:
            brand_parts.append("brand colors " + ", ".join(brand_kit.primary_colors[:4]))
        if brand_kit.fonts:
            brand_parts.append("brand fonts " + ", ".join(brand_kit.fonts[:3]))
        if brand_kit.voice:
            metadata["brand_voice"] = brand_kit.voice
        if brand_parts:
            style_direction = " | ".join(part for part in [style_direction, *brand_parts] if part)
        constraints.extend(brand_kit.negative_constraints)

    return creative_plan.model_copy(update={
        "metadata": metadata,
        "constraints": _dedupe(constraints),
        "style_direction": style_direction,
        "hook_pattern": hook_pattern,
        "narrative_arc": narrative_arc,
    })


def apply_commercial_context_to_execution_plan(
    execution_plan: SeedanceExecutionPlan,
    *,
    brand_kit: BrandKit | None = None,
    template: CommercialTemplate | None = None,
) -> SeedanceExecutionPlan:
    """Append a compact brand/template block to prompts and metadata."""
    prompt_block = _prompt_block(brand_kit=brand_kit, template=template)
    metadata = dict(execution_plan.metadata or {})
    if brand_kit is not None:
        metadata["brand_kit_id"] = brand_kit.brand_id
        metadata["brand_kit"] = brand_kit.model_dump(mode="json")
    if template is not None:
        metadata["template_id"] = template.template_id
        metadata["commercial_template"] = template.model_dump(mode="json")
    shots = [
        _apply_prompt_block_to_shot(shot, prompt_block=prompt_block, brand_kit=brand_kit, template=template)
        for shot in execution_plan.shots
    ]
    compiled_prompt = execution_plan.compiled_prompt
    if prompt_block and prompt_block not in compiled_prompt:
        compiled_prompt = f"{compiled_prompt}\n\n{prompt_block}".strip()
    return execution_plan.model_copy(update={
        "compiled_prompt": compiled_prompt,
        "shots": shots,
        "metadata": metadata,
    })


def _apply_prompt_block_to_shot(
    shot: SeedanceShotPlan,
    *,
    prompt_block: str,
    brand_kit: BrandKit | None,
    template: CommercialTemplate | None,
) -> SeedanceShotPlan:
    metadata = dict(shot.metadata or {})
    if brand_kit is not None:
        metadata["brand_kit_id"] = brand_kit.brand_id
        metadata["brand_kit"] = brand_kit.model_dump(mode="json")
    if template is not None:
        metadata["template_id"] = template.template_id
        metadata["commercial_template"] = template.model_dump(mode="json")
    prompt = shot.compiled_prompt
    if prompt_block and prompt_block not in prompt:
        prompt = f"{prompt}\n{prompt_block}".strip()
    negative = shot.negative_prompt
    if brand_kit is not None and brand_kit.negative_constraints:
        extra = ", ".join(brand_kit.negative_constraints)
        negative = f"{negative}, {extra}".strip(", ")
    return shot.model_copy(update={
        "compiled_prompt": prompt,
        "negative_prompt": negative,
        "metadata": metadata,
        "rules_applied": _dedupe(list(shot.rules_applied or []) + ["phase13.commercial.prompt_override"]),
    })


def _prompt_block(*, brand_kit: BrandKit | None, template: CommercialTemplate | None) -> str:
    lines: list[str] = []
    if brand_kit is not None:
        lines.append("Brand Kit:")
        if brand_kit.name:
            lines.append(f"- Brand: {brand_kit.name}")
        if brand_kit.primary_colors:
            lines.append(f"- Colors: {', '.join(brand_kit.primary_colors[:4])}")
        if brand_kit.fonts:
            lines.append(f"- Typography: {', '.join(brand_kit.fonts[:3])}")
        if brand_kit.voice:
            lines.append(f"- Voice: {brand_kit.voice}")
        if brand_kit.style_guide:
            lines.append(f"- Style guide: {brand_kit.style_guide}")
    if template is not None:
        lines.append("Template:")
        lines.append(f"- Pattern: {template.name} / {template.hook_pattern}")
        if template.prompt_constraints:
            lines.append(f"- Constraints: {', '.join(template.prompt_constraints[:6])}")
    return "\n".join(lines)


def _dedupe(values: list[Any]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value).strip()))


__all__ = [
    "apply_commercial_context_to_creative_plan",
    "apply_commercial_context_to_execution_plan",
]
