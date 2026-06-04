"""Screenplay planning layer for long-form autonomous videos.

The scene planner decides how many scenes exist. This module adds the missing
film-writing layer between a raw idea and storyboard generation: act beats,
scene conflict, turning points, opening/closing images, and dialogue/VO intent.
It is deterministic so it can run before expensive LLM storyboard calls.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class SceneScript:
    scene_id: str
    act: int
    duration_s: int
    premise: str
    conflict: str
    turning_point: str
    opening_image: str
    closing_image: str
    dialogue_or_vo_intent: str
    reference_priorities: list[str]
    qa_focus: list[str]

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScreenplayPlan:
    logline: str
    act_beats: list[dict[str, Any]]
    scene_scripts: list[SceneScript]
    continuity_contract: list[str]
    editor_promise: str

    def model_dump(self) -> dict[str, Any]:
        return {
            "logline": self.logline,
            "act_beats": self.act_beats,
            "scene_scripts": [s.model_dump() for s in self.scene_scripts],
            "continuity_contract": self.continuity_contract,
            "editor_promise": self.editor_promise,
        }


def plan_screenplay(
    *,
    user_idea: str,
    runtime_structure: dict[str, Any],
    scene_blueprints: list[Any],
    niche_playbook: dict[str, Any],
    hook_first_3s: str,
    primary_emotion: str,
) -> ScreenplayPlan:
    """Create a structured screenplay plan for 3m-30m autonomous videos."""
    clean_idea = " ".join((user_idea or "").split())
    logline = _logline(clean_idea, hook_first_3s, primary_emotion)
    act_beats = _act_beats(runtime_structure, niche_playbook)
    beat_flow = niche_playbook.get("beat_flow") or ["hook", "setup", "escalation", "reveal", "payoff"]
    camera = niche_playbook.get("camera") or ["motivated close-up", "wide establishing", "slow push-in"]
    quality = niche_playbook.get("quality_bar") or ["continuity", "prompt adherence", "believable motion"]

    scenes: list[SceneScript] = []
    for i, scene in enumerate(scene_blueprints):
        beat = str(beat_flow[min(i, len(beat_flow) - 1)])
        cam = str(camera[i % len(camera)])
        scenes.append(SceneScript(
            scene_id=scene.scene_id,
            act=scene.act,
            duration_s=scene.duration_s,
            premise=f"{scene.purpose}: {scene.dramatic_question}",
            conflict=_conflict_for_scene(i, len(scene_blueprints), beat, clean_idea),
            turning_point=_turning_point_for_scene(i, len(scene_blueprints), beat),
            opening_image=scene.visual_hook if i == 0 else f"{cam} re-establishes the last scene consequence",
            closing_image=scene.handoff_to_next,
            dialogue_or_vo_intent=_dialogue_intent(beat, primary_emotion),
            reference_priorities=_reference_priorities(i, niche_playbook),
            qa_focus=[
                "character/product identity continuity",
                "scene purpose visible without explanation",
                *[str(q) for q in quality[:3]],
            ],
        ))

    return ScreenplayPlan(
        logline=logline,
        act_beats=act_beats,
        scene_scripts=scenes,
        continuity_contract=[
            "Every scene must preserve the same production bible unless the screenplay explicitly changes time/location.",
            "Every scene must end with a handoff image that motivates the next scene.",
            "Every shot must serve the scene conflict or turning point.",
            "Dialogue/VO supports the visual action; it cannot replace visual proof.",
        ],
        editor_promise=(
            "The final cut should feel like one continuous film: cold open, escalation, "
            "turning points, payoff, caption-ready moments, and no unexplained visual resets."
        ),
    )


def _logline(idea: str, hook: str, emotion: str) -> str:
    idea = idea[:160] or "an autonomous short film"
    hook = hook[:120] or "a strong visual incident"
    emotion = emotion or "curiosity"
    return f"After {hook}, {idea} builds toward a {emotion} payoff."


def _act_beats(runtime_structure: dict[str, Any], niche_playbook: dict[str, Any]) -> list[dict[str, Any]]:
    acts = runtime_structure.get("act_structure") or []
    beat_flow = niche_playbook.get("beat_flow") or []
    out: list[dict[str, Any]] = []
    for idx, act in enumerate(acts, start=1):
        out.append({
            "act": int(act.get("act") or idx),
            "name": act.get("name") or f"Act {idx}",
            "goal": act.get("goal") or "Advance the story with a visible change.",
            "ratio": act.get("ratio") or 0,
            "beat_palette": beat_flow,
        })
    return out


def _conflict_for_scene(i: int, n: int, beat: str, idea: str) -> str:
    if i == 0:
        return f"The viewer sees an immediate contradiction or unanswered question in: {idea[:120]}"
    if i == n - 1:
        return "The film must resolve the central promise with one final visual proof or emotional image."
    if i >= int(n * 0.7):
        return f"The {beat} beat forces a reveal, reversal, or decisive proof."
    return f"The {beat} beat changes the situation and raises stakes without losing continuity."


def _turning_point_for_scene(i: int, n: int, beat: str) -> str:
    if i == 0:
        return "The hook becomes a concrete mission, test, or emotional question."
    if i == n - 1:
        return "The unresolved question is answered through action, not explanation."
    return f"A visible {beat} outcome makes the next scene necessary."


def _dialogue_intent(beat: str, emotion: str) -> str:
    if beat in {"hook", "sensory hook", "result hook", "emotion close-up"}:
        return "One short line or caption-worthy phrase that sharpens the visual hook."
    if beat in {"proof", "demo", "feature action", "visual explanation"}:
        return "Concise explanatory VO only where the image cannot carry the detail."
    return f"Natural dialogue/VO that preserves {emotion or 'emotional'} tension and avoids exposition dumps."


def _reference_priorities(i: int, niche_playbook: dict[str, Any]) -> list[str]:
    priorities = ["character/product identity refs", "style reference"]
    if i > 0:
        priorities.insert(0, "previous scene final frame")
    if niche_playbook.get("audio"):
        priorities.append("audio rhythm/SFX reference")
    priorities.append("video reference for camera/motion when available")
    return priorities


__all__ = ["ScreenplayPlan", "SceneScript", "plan_screenplay"]
