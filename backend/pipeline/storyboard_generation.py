"""Storyboard generation for Phase 2.

The generator converts a CreativePlan into a structured StoryboardContract.
For complex videos it follows the Lanshu-style 3-5 shot method: clear beat,
camera movement, action, spatial change, audio intent, references, and
continuity notes per scene.
"""
from __future__ import annotations

from typing import Any

from pipeline.contracts import AnalyzedInput, CreativePlan, StoryboardContract, StoryboardScene


_SHOT_TEMPLATES: dict[str, list[dict[str, str]]] = {
    "product": [
        {
            "beat": "detail/problem hook",
            "camera": "macro close-up with stable product framing",
            "action": "product detail, material, or problem cue becomes visible",
            "space": "clean commercial surface with controlled reflections",
            "audio": "subtle tactile product sound and light music bed",
        },
        {
            "beat": "hero product reveal",
            "camera": "slow push-in to medium hero shot",
            "action": "product rotates, opens, or enters the hero position",
            "space": "same set with product centered and background simplified",
            "audio": "music lift and precise product handling sound",
        },
        {
            "beat": "clear payoff frame",
            "camera": "locked final hero composition",
            "action": "benefit, label, or final usage moment lands cleanly",
            "space": "stable final frame preserving packaging and geometry",
            "audio": "short resolve with clean ambience",
        },
    ],
    "beauty": [
        {
            "beat": "macro sensory hook",
            "camera": "static macro close-up with shallow depth of field",
            "action": "product texture or liquid detail catches the light",
            "space": "premium studio surface with controlled reflections",
            "audio": "soft tactile product handling and subtle ambience",
        },
        {
            "beat": "hero product reveal",
            "camera": "slow push-in to medium close-up",
            "action": "hero product rotates or settles into frame",
            "space": "clean commercial set with stable background",
            "audio": "light music lift with polished room tone",
        },
        {
            "beat": "benefit payoff frame",
            "camera": "locked hero shot with tiny parallax",
            "action": "final beauty effect or premium detail becomes clear",
            "space": "same set, tighter product framing",
            "audio": "soft resolve and gentle sparkle detail",
        },
    ],
    "food": [
        {
            "beat": "fresh ingredient hook",
            "camera": "handheld macro close-up",
            "action": "fresh ingredient is picked, poured, or revealed",
            "space": "warm prep area with natural light",
            "audio": "crisp cooking ASMR and ambient room tone",
        },
        {
            "beat": "craft/process detail",
            "camera": "macro tracking shot over hands and tools",
            "action": "precise cutting, stirring, frying, or plating motion",
            "space": "active cooking surface with steam and texture",
            "audio": "sizzle, knife, steam, and light rhythmic music",
        },
        {
            "beat": "serve/eat payoff",
            "camera": "medium shot with calm push-in",
            "action": "dish is served and enjoyed or presented",
            "space": "serving table with appetizing background depth",
            "audio": "music resolves with subtle ambience",
        },
    ],
    "fashion": [
        {
            "beat": "silhouette entrance",
            "camera": "low-angle controlled push-in",
            "action": "model enters with clear garment silhouette",
            "space": "minimal editorial set with strong reflective plane",
            "audio": "stylized pulse and footsteps",
        },
        {
            "beat": "material transformation",
            "camera": "close-up to pull-back transition",
            "action": "fabric, surface, or effect transforms around the model",
            "space": "same set with controlled VFX focus",
            "audio": "fabric detail, snap, or transformation hit",
        },
        {
            "beat": "editorial hero finish",
            "camera": "overhead or frontal hero composition",
            "action": "model lands in final pose with stable identity",
            "space": "wide editorial frame preserving color palette",
            "audio": "music resolves on the hero pose",
        },
    ],
    "drama": [
        {
            "beat": "quiet tension setup",
            "camera": "slow push-in from medium shot",
            "action": "character stays restrained while small gestures reveal tension",
            "space": "intimate everyday location with motivated light",
            "audio": "room tone and subtle breathing",
        },
        {
            "beat": "emotional reveal",
            "camera": "close-up on eyes or hands",
            "action": "micro-expression or dialogue changes the emotional state",
            "space": "same location, tighter emotional frame",
            "audio": "restrained dialogue and small environmental sounds",
        },
        {
            "beat": "reaction payoff",
            "camera": "locked close two-shot or slow pull-away",
            "action": "reaction lands and the relationship changes",
            "space": "background melts into soft depth of field",
            "audio": "soft musical or ambient resolve",
        },
    ],
    "anime": [
        {
            "beat": "power stance",
            "camera": "low-angle wide shot",
            "action": "characters prepare with clear silhouettes and energy build",
            "space": "readable arena or environment with stable geography",
            "audio": "energy swell and environmental tension",
        },
        {
            "beat": "fast clash",
            "camera": "tracking shot with one primary whip-pan transition",
            "action": "main motion crosses frame with controlled effects",
            "space": "same arena, spatial direction remains clear",
            "audio": "impact hits and rising rhythm",
        },
        {
            "beat": "impact frame",
            "camera": "locked impact close-up then wide release",
            "action": "final collision or move resolves without extra characters",
            "space": "effects dissipate while geography remains readable",
            "audio": "impact hit, short silence, then resolve",
        },
    ],
    "cinematic": [
        {
            "beat": "establish world",
            "camera": "wide establishing shot with controlled movement",
            "action": "world, subject, and stakes are introduced clearly",
            "space": "atmospheric cinematic environment",
            "audio": "ambient bed establishes tone",
        },
        {
            "beat": "escalate motion",
            "camera": "motivated tracking or push-in",
            "action": "subject action escalates with one clear spatial change",
            "space": "same world, stronger motion and foreground depth",
            "audio": "sound design builds with action",
        },
        {
            "beat": "climax image",
            "camera": "hero wide or close-up hold",
            "action": "final visual payoff lands cleanly",
            "space": "most readable version of the environment",
            "audio": "final hit or fade",
        },
    ],
    "ugc": [
        {
            "beat": "creator hook",
            "camera": "handheld phone-camera medium close-up",
            "action": "creator opens with a natural hook or reaction",
            "space": "realistic everyday setting",
            "audio": "natural spoken line and room tone",
        },
        {
            "beat": "proof/demo",
            "camera": "handheld close-up or over-the-shoulder",
            "action": "show proof, demo, or surprising detail",
            "space": "same setting with clearer object focus",
            "audio": "natural voice, handling sounds, small emphasis",
        },
        {
            "beat": "reaction payoff",
            "camera": "selfie-style or medium reaction frame",
            "action": "creator reacts or closes the idea",
            "space": "return to original framing",
            "audio": "spoken payoff and room tone",
        },
    ],
}


class StoryboardGenerator:
    """Generate StoryboardContract instances from Phase 2 creative plans."""

    def generate(
        self,
        creative_plan: CreativePlan,
        analyzed_input: AnalyzedInput,
    ) -> StoryboardContract:
        """Build a storyboard using the plan's shot mode and niche playbook."""
        shot_count = _effective_shot_count(creative_plan)
        durations = _allocate_durations(creative_plan.duration_s, shot_count)
        templates = _templates_for(creative_plan.target_niche)
        reference_bindings = _reference_bindings_by_scene(creative_plan.reference_strategy, shot_count)
        scenes: list[StoryboardScene] = []

        for index in range(shot_count):
            template = templates[min(index, len(templates) - 1)]
            scenes.append(StoryboardScene(
                index=index,
                duration_s=durations[index],
                beat=_arc_value(creative_plan, index, template["beat"]),
                visual_intent=_visual_intent(creative_plan, template),
                action=template["action"],
                camera_movement=template["camera"],
                spatial_change=template["space"],
                audio_intent=template["audio"] or creative_plan.audio_direction,
                reference_bindings=reference_bindings[index],
                continuity_notes=_continuity_notes(creative_plan),
                metadata={
                    "phase": "2",
                    "storyboard_method": "lanshu_3_5_shot" if shot_count > 1 else "single_shot",
                    "template_niche": _template_key(creative_plan.target_niche),
                },
            ))

        return StoryboardContract(
            creative_plan_id=creative_plan.creative_plan_id,
            scenes=scenes,
            duration_s=sum(scene.duration_s for scene in scenes),
            aspect_ratio=creative_plan.aspect_ratio,
            title=f"{creative_plan.target_niche.title()} Seedance Storyboard",
            summary=f"{shot_count}-shot plan for: {creative_plan.objective}",
            metadata={
                "phase": "2",
                "rules_applied": [
                    "lanshu.storyboard.3_5_shot_structure" if shot_count > 1 else "phase2.storyboard.single_shot",
                    "phase2.storyboard.reference_bindings",
                    "phase2.storyboard.continuity_notes",
                ],
                "source_analysis_id": analyzed_input.analysis_id,
            },
        )


def _effective_shot_count(creative_plan: CreativePlan) -> int:
    requested = max(1, int(creative_plan.shot_count or 1))
    max_seedance_shots = max(1, int(creative_plan.duration_s or 1) // 4)
    if creative_plan.metadata.get("shot_mode") == "multi_shot":
        if max_seedance_shots < 3:
            return min(requested, max_seedance_shots)
        return min(5, max_seedance_shots, max(3, requested))
    return 1


def _allocate_durations(total_duration_s: int, shot_count: int) -> list[int]:
    total = max(shot_count, int(total_duration_s or shot_count))
    base = total // shot_count
    remainder = total % shot_count
    return [base + (1 if index < remainder else 0) for index in range(shot_count)]


def _templates_for(niche: str) -> list[dict[str, str]]:
    return _SHOT_TEMPLATES[_template_key(niche)]


def _template_key(niche: str) -> str:
    normalized = str(niche or "").lower()
    return normalized if normalized in _SHOT_TEMPLATES else "cinematic"


def _reference_bindings_by_scene(reference_strategy: dict[str, Any], shot_count: int) -> list[list[str]]:
    priority = reference_strategy.get("priority_bindings") or {}
    always_roles = ("character_anchor", "product_hero", "continuity_anchor", "audio_bgm", "audio_voice")
    first_roles = ("style_reference", "environment", "first_frame")
    last_roles = ("last_frame",)
    bindings: list[list[str]] = []
    for index in range(shot_count):
        tags: list[str] = []
        for role in always_roles:
            tags.extend(str(tag) for tag in priority.get(role, []))
        if index == 0:
            for role in first_roles:
                tags.extend(str(tag) for tag in priority.get(role, []))
        if index == shot_count - 1:
            for role in last_roles:
                tags.extend(str(tag) for tag in priority.get(role, []))
        bindings.append(list(dict.fromkeys(tag for tag in tags if tag)))
    return bindings


def _arc_value(creative_plan: CreativePlan, index: int, fallback: str) -> str:
    if index < len(creative_plan.narrative_arc):
        return creative_plan.narrative_arc[index]
    return fallback


def _visual_intent(creative_plan: CreativePlan, template: dict[str, str]) -> str:
    return f"{creative_plan.objective}; {template['beat']}; {creative_plan.style_direction}"


def _continuity_notes(creative_plan: CreativePlan) -> str:
    notes = creative_plan.consistency_plan.get("lock_notes") or []
    if notes:
        return "; ".join(str(note) for note in notes)
    return "Maintain subject, style, lighting, and spatial continuity across the shot."


__all__ = ["StoryboardGenerator"]
