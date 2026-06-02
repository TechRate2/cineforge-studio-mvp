"""Scene blueprint planner for long-form autonomous videos.

The LLM Storyboard skill is intentionally scoped to one scene/sequence at a
time. This module breaks a long requested runtime into scene blueprints so the
AutonomousDirector can storyboard each scene and merge them into one film.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class SceneBlueprint:
    scene_id: str
    index: int
    act: int
    duration_s: int
    purpose: str
    dramatic_question: str
    visual_hook: str
    continuity_anchor: str
    handoff_to_next: str

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def plan_scene_blueprints(
    *,
    user_idea: str,
    runtime_structure: dict[str, Any],
    niche_playbook: dict[str, Any],
    planner_hook: str,
) -> list[SceneBlueprint]:
    target_duration = int(runtime_structure.get("target_duration_s") or 15)
    scene_count = max(1, int(runtime_structure.get("scene_count") or 1))
    act_structure = runtime_structure.get("act_structure") or []
    beat_flow = niche_playbook.get("beat_flow") or ["hook", "setup", "escalation", "reveal", "payoff"]
    hook_moves = niche_playbook.get("hook_moves") or ["visual incident"]

    durations = _split_duration(target_duration, scene_count)
    scenes: list[SceneBlueprint] = []
    for i, dur in enumerate(durations):
        act = _act_for_scene(i, scene_count, act_structure)
        beat = str(beat_flow[min(i, len(beat_flow) - 1)])
        scene_id = f"SC{i + 1:02d}"
        visual_hook = planner_hook if i == 0 else f"{hook_moves[i % len(hook_moves)]} advancing {beat}"
        purpose = _scene_purpose(i, scene_count, beat)
        scenes.append(SceneBlueprint(
            scene_id=scene_id,
            index=i,
            act=act,
            duration_s=dur,
            purpose=purpose,
            dramatic_question=_dramatic_question(i, scene_count, user_idea, beat),
            visual_hook=visual_hook,
            continuity_anchor=(
                "Carry forward same character/product/location bible from previous scene"
                if i > 0 else
                "Establish the primary visual identity and core promise"
            ),
            handoff_to_next=(
                "End with an unresolved visual question that motivates the next scene"
                if i < scene_count - 1 else
                "End with a memorable final image and emotional payoff"
            ),
        ))
    return scenes


def _split_duration(total_s: int, n: int) -> list[int]:
    base = max(15, total_s // n)
    durations = [base for _ in range(n)]
    diff = total_s - sum(durations)
    i = 0
    while diff != 0 and durations:
        step = 1 if diff > 0 else -1
        if durations[i % n] + step >= 15:
            durations[i % n] += step
            diff -= step
        i += 1
    return durations


def _act_for_scene(scene_index: int, scene_count: int, act_structure: list[dict[str, Any]]) -> int:
    if not act_structure:
        return 1
    cursor = 0.0
    pos = (scene_index + 0.5) / max(1, scene_count)
    for idx, act in enumerate(act_structure, start=1):
        cursor += float(act.get("ratio") or 0)
        if pos <= cursor:
            return int(act.get("act") or idx)
    return int(act_structure[-1].get("act") or len(act_structure))


def _scene_purpose(i: int, n: int, beat: str) -> str:
    if i == 0:
        return f"cold_open_{beat}"
    if i == n - 1:
        return f"final_payoff_{beat}"
    if i >= int(n * 0.7):
        return f"crisis_or_reveal_{beat}"
    return f"escalation_{beat}"


def _dramatic_question(i: int, n: int, idea: str, beat: str) -> str:
    clipped = " ".join((idea or "").split())[:120]
    if i == 0:
        return f"What surprising visual incident makes the viewer care about: {clipped}?"
    if i == n - 1:
        return f"What final image resolves or reframes the promise of: {clipped}?"
    return f"How does this {beat} scene change the viewer's understanding of the story?"


__all__ = ["SceneBlueprint", "plan_scene_blueprints"]
