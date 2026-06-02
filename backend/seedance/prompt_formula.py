"""Seedance prompt formula builders for Phase 1b.

This module integrates the Phase 1b rule surface from dexhunter's Seedance
prompt structure and Lanshu's 8-element prompt formula. It does not retrieve
curated examples or generate advanced storyboards; those remain Phase 2 work.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pipeline.contracts import AnalyzedInput, CreativePlan, StoryboardContract, StoryboardScene


LANSHU_FORMULA_ELEMENTS = (
    "subject",
    "action",
    "scene",
    "lighting",
    "camera",
    "style",
    "quality",
    "constraints",
)

DEXHUNTER_STRUCTURE_ELEMENTS = (
    "subject_setup",
    "scene",
    "action",
    "camera",
    "timing",
    "transition_effects",
    "audio",
    "style_mood",
)


class TimeSegment(BaseModel):
    """One time-bounded prompt segment for longer or multi-shot Seedance prompts."""

    model_config = ConfigDict(extra="forbid")

    start_s: int = Field(..., ge=0)
    end_s: int = Field(..., ge=1)
    label: str
    prompt: str


class SeedancePromptFormulaPlan(BaseModel):
    """Structured prompt formula before it is serialized into prompt text."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "cineforge.seedance.prompt_formula.v1"
    rule_ids: list[str] = Field(default_factory=list)
    subject: str
    action: str
    scene: str
    lighting: str
    camera: str
    style: str
    quality: str
    constraints: list[str] = Field(default_factory=list)
    timing: str = ""
    transition_effects: str = ""
    audio: str = ""
    style_mood: str = ""
    time_segments: list[TimeSegment] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_prompt(self) -> str:
        """Serialize this formula into a labelled Seedance prompt."""
        lines = [
            f"Subject: {self.subject}",
            f"Action: {self.action}",
            f"Scene: {self.scene}",
            f"Lighting: {self.lighting}",
            f"Camera: {self.camera}",
            f"Timing: {self.timing}",
            f"Transition Effects: {self.transition_effects}",
            f"Audio: {self.audio}",
            f"Style: {self.style}",
            f"Style Mood: {self.style_mood}",
            f"Quality: {self.quality}",
            "Constraints: " + "; ".join(self.constraints),
        ]
        if self.time_segments:
            lines.append("Time Segments:")
            for segment in self.time_segments:
                lines.append(
                    f"{segment.start_s}-{segment.end_s}s: {segment.label}: {segment.prompt}"
                )
        return "\n".join(line for line in lines if line.strip())


class SeedancePromptFormula:
    """Prompt formula facade used by SeedancePromptCompiler."""

    def build_prompt(
        self,
        *,
        creative_plan: CreativePlan,
        scene: StoryboardScene,
        analyzed_input: AnalyzedInput,
        storyboard: StoryboardContract | None = None,
    ) -> str:
        """Build a Phase 1b prompt from pipeline contracts."""
        return build_seedance_prompt_formula(
            creative_plan=creative_plan,
            scene=scene,
            analyzed_input=analyzed_input,
            storyboard=storyboard,
        ).to_prompt()


def build_seedance_prompt_formula(
    *,
    creative_plan: CreativePlan,
    scene: StoryboardScene,
    analyzed_input: AnalyzedInput,
    storyboard: StoryboardContract | None = None,
) -> SeedancePromptFormulaPlan:
    """Build a structured Seedance prompt formula for one scene.

    The formula combines Lanshu's 8 required elements with dexhunter's prompt
    structure fields. It intentionally avoids curated example retrieval and
    advanced storyboard generation.
    """
    duration_s = int(scene.duration_s or creative_plan.duration_s or analyzed_input.duration_s or 8)
    subject = _first_non_empty(
        scene.visual_intent,
        creative_plan.objective,
        analyzed_input.normalized_idea,
    )
    action = _first_non_empty(scene.action, scene.beat, "one clear physical action")
    scene_space = _first_non_empty(scene.spatial_change, "controlled cinematic environment")
    lighting = _extract_metadata_value(
        creative_plan.metadata,
        "lighting",
        "lighting_design",
        default="consistent natural or studio lighting",
    )
    camera = _first_non_empty(scene.camera_movement, "controlled medium shot")
    style = _first_non_empty(creative_plan.style_direction, "clean cinematic video")
    quality = _extract_metadata_value(
        creative_plan.metadata,
        "quality",
        "quality_target",
        default="high clarity, stable details, production-ready image quality",
    )
    constraints = build_negative_constraints(
        extra_constraints=creative_plan.constraints,
        needs_identity_consistency=_metadata_bool(creative_plan.metadata, "needs_identity_consistency"),
        needs_product_consistency=_metadata_bool(creative_plan.metadata, "needs_product_consistency"),
    )
    time_segments = build_time_segment_plan(
        duration_s=duration_s,
        scenes=storyboard.scenes if storyboard else [scene],
        force_multi_shot=bool(storyboard and len(storyboard.scenes) > 1),
    )
    return SeedancePromptFormulaPlan(
        rule_ids=[
            "lanshu.formula.8_elements",
            "dexhunter.formula.prompt_structure",
            "dexhunter.formula.time_segments" if time_segments else "dexhunter.formula.single_unit",
            "lanshu.constraints.no_text_logo_watermark",
        ],
        subject=subject,
        action=action,
        scene=scene_space,
        lighting=lighting,
        camera=camera,
        style=style,
        quality=quality,
        constraints=constraints,
        timing=f"Duration: {duration_s}s",
        transition_effects=_first_non_empty(
            scene.continuity_notes,
            str(creative_plan.metadata.get("transition_effects") or ""),
            "no abrupt unmotivated scene jumps",
        ),
        audio=_first_non_empty(scene.audio_intent, creative_plan.audio_direction, "natural ambience"),
        style_mood=_first_non_empty(
            str(creative_plan.metadata.get("mood") or ""),
            creative_plan.hook_pattern,
            style,
        ),
        time_segments=time_segments,
        metadata={
            "lanshu_elements": list(LANSHU_FORMULA_ELEMENTS),
            "dexhunter_structure": list(DEXHUNTER_STRUCTURE_ELEMENTS),
            "phase": "1b",
        },
    )


def build_time_segment_plan(
    *,
    duration_s: int,
    scenes: list[StoryboardScene] | tuple[StoryboardScene, ...] | None = None,
    force_multi_shot: bool = False,
) -> list[TimeSegment]:
    """Create simple time segments for long or multi-shot Seedance prompts.

    Dexhunter recommends timed segments for longer videos. This function only
    segments existing scenes; it does not invent a new storyboard.
    """
    scene_list = list(scenes or [])
    if not force_multi_shot and duration_s < 10 and len(scene_list) <= 1:
        return []
    if not scene_list:
        return [
            TimeSegment(
                start_s=0,
                end_s=max(1, duration_s),
                label="single segment",
                prompt="Keep one coherent action, camera, audio, and style across the full duration.",
            )
        ]

    segments: list[TimeSegment] = []
    cursor = 0
    for index, scene in enumerate(scene_list):
        scene_duration = max(1, int(scene.duration_s or duration_s // max(1, len(scene_list))))
        end = min(max(cursor + scene_duration, cursor + 1), max(duration_s, cursor + 1))
        if index == len(scene_list) - 1:
            end = max(end, duration_s)
        segments.append(TimeSegment(
            start_s=cursor,
            end_s=end,
            label=scene.beat or f"shot {index + 1}",
            prompt=_segment_prompt(scene),
        ))
        cursor = end
    return segments


def build_negative_constraints(
    *,
    extra_constraints: list[str] | tuple[str, ...] | None = None,
    needs_identity_consistency: bool = False,
    needs_product_consistency: bool = False,
) -> list[str]:
    """Build standard negative constraints for Seedance prompts."""
    constraints = [
        "no subtitles",
        "no text overlays",
        "no logo",
        "no watermark",
        "no distorted faces, hands, or body proportions",
        "no unrequested characters or scene jumps",
    ]
    if needs_identity_consistency:
        constraints.append("preserve character face, hair, outfit, and silhouette consistently")
        constraints.append("no clones, twins, or duplicate identity copies")
    if needs_product_consistency:
        constraints.append("preserve product geometry, material, color, packaging, and label placement")
    constraints.extend(str(item).strip() for item in (extra_constraints or []) if str(item).strip())
    return list(dict.fromkeys(constraints))


def _segment_prompt(scene: StoryboardScene) -> str:
    parts = [
        _first_non_empty(scene.camera_movement, "controlled camera"),
        _first_non_empty(scene.action, scene.beat, "clear action"),
        _first_non_empty(scene.spatial_change, "stable scene space"),
        _first_non_empty(scene.audio_intent, "natural ambience"),
    ]
    return "; ".join(part for part in parts if part)


def _first_non_empty(*values: str | None) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _extract_metadata_value(
    metadata: dict[str, Any],
    *keys: str,
    default: str,
) -> str:
    for key in keys:
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return default


def _metadata_bool(metadata: dict[str, Any], key: str) -> bool:
    value = metadata.get(key)
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


__all__ = [
    "DEXHUNTER_STRUCTURE_ELEMENTS",
    "LANSHU_FORMULA_ELEMENTS",
    "SeedancePromptFormula",
    "SeedancePromptFormulaPlan",
    "TimeSegment",
    "build_negative_constraints",
    "build_seedance_prompt_formula",
    "build_time_segment_plan",
]
