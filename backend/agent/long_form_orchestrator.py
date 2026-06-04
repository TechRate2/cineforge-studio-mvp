"""Deterministic long-form structure planner for CineJelly.

This module does not call an LLM. It gives the autonomous chain a production
map for anything from a 15s short to a 30m episode: act shape, scene count,
chunk count, render strategy, and quality gates. The concrete script/shot text
still comes from Planner + Storyboard; this module supplies the film grammar.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from math import ceil
from typing import Any, Literal


RuntimeClass = Literal["short", "sequence", "micro_film", "short_film", "episode"]


@dataclass(frozen=True)
class RuntimeStructure:
    runtime_class: RuntimeClass
    target_duration_s: int
    act_count: int
    scene_count: int
    chunk_count: int
    target_scene_duration_s: int
    target_chunk_duration_s: int
    shot_budget: tuple[int, int]
    act_structure: list[dict[str, Any]]
    render_strategy_hint: str
    continuity_rules: list[str]
    quality_gates: list[str]

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def plan_runtime_structure(duration_s: int, niche: str = "", platform: str = "tiktok") -> RuntimeStructure:
    """Return a production structure for 15s-30m videos.

    Duration is clamped to 30 minutes because Seedance-class render workflows
    should be episode/job based beyond that; a single request should not become
    an unbounded render graph.
    """
    duration_s = max(4, min(int(duration_s or 15), 1800))
    runtime_class = _classify(duration_s)

    if runtime_class == "short":
        act_count, scene_count, scene_dur, shot_budget = 1, 1, duration_s, (3, 6)
    elif runtime_class == "sequence":
        act_count, scene_count, scene_dur, shot_budget = 1, 2, max(20, duration_s // 2), (6, 12)
    elif runtime_class == "micro_film":
        act_count, scene_count, scene_dur, shot_budget = 3, max(3, ceil(duration_s / 60)), 45, (10, 24)
    elif runtime_class == "short_film":
        act_count, scene_count, scene_dur, shot_budget = 3, max(5, ceil(duration_s / 75)), 60, (20, 80)
    else:
        act_count, scene_count, scene_dur, shot_budget = 5, max(8, ceil(duration_s / 90)), 75, (60, 240)

    chunk_count = max(1, ceil(duration_s / 60))
    act_structure = _act_structure(runtime_class, duration_s, niche)

    return RuntimeStructure(
        runtime_class=runtime_class,
        target_duration_s=duration_s,
        act_count=act_count,
        scene_count=scene_count,
        chunk_count=chunk_count,
        target_scene_duration_s=scene_dur,
        target_chunk_duration_s=60,
        shot_budget=shot_budget,
        act_structure=act_structure,
        render_strategy_hint=_render_hint(runtime_class, platform),
        continuity_rules=[
            "Lock character face, outfit, product, and location in the Production Bible before rendering.",
            "Each scene needs one stable visual anchor: reference image, master board, or previous last frame.",
            "Only cross location/time at scene boundaries, never mid-shot.",
            "Render every model call as a 4-15s shot; group shots into scene/chunk units for progress, QA, and resume.",
            "For >60s jobs, render scene/chunk groups independently and carry last_frame_url forward when continuity matters.",
            "Retry bad shots/chunks instead of regenerating the whole film.",
        ],
        quality_gates=[
            "Script gate: hook, stakes, payoff, and scene purpose are explicit.",
            "Continuity gate: character/product/location bible is present before render.",
            "Prompt gate: every shot has subject, action, setting, lighting, camera, audio cue.",
            "Render QA gate: score identity, product accuracy, motion, audio sync, and prompt adherence.",
            "Assembly gate: check pacing, transitions, aspect, caption safety, and final duration.",
        ],
    )


def _classify(duration_s: int) -> RuntimeClass:
    if duration_s <= 30:
        return "short"
    if duration_s <= 60:
        return "sequence"
    if duration_s <= 180:
        return "micro_film"
    if duration_s <= 600:
        return "short_film"
    return "episode"


def _act_structure(runtime_class: RuntimeClass, duration_s: int, niche: str) -> list[dict[str, Any]]:
    if runtime_class in ("short", "sequence"):
        return [
            {"act": 1, "name": "Hook-to-payoff", "goal": "Stop scroll, prove the idea, land one memorable payoff.", "ratio": 1.0},
        ]
    if runtime_class == "micro_film":
        return [
            {"act": 1, "name": "Hook and setup", "goal": "Open with the strongest visual incident and define stakes.", "ratio": 0.25},
            {"act": 2, "name": "Escalation", "goal": "Build problem, test, tension, or transformation through visual beats.", "ratio": 0.50},
            {"act": 3, "name": "Payoff", "goal": "Deliver reveal, proof, twist, or emotional close.", "ratio": 0.25},
        ]
    if runtime_class == "short_film":
        return [
            {"act": 1, "name": "Inciting incident", "goal": "Make viewer care and introduce the core conflict/product promise.", "ratio": 0.20},
            {"act": 2, "name": "Complications", "goal": "Escalate with 3-5 scenes, each changing the situation.", "ratio": 0.55},
            {"act": 3, "name": "Climax and aftertaste", "goal": "Resolve with a strong visual payoff and final emotional image.", "ratio": 0.25},
        ]
    return [
        {"act": 1, "name": "Cold open", "goal": "Viral opening scene with unresolved question.", "ratio": 0.10},
        {"act": 2, "name": "Setup", "goal": "Characters, desire, stakes, world rules.", "ratio": 0.20},
        {"act": 3, "name": "Rising action", "goal": "Scene chain of reversals and proof beats.", "ratio": 0.35},
        {"act": 4, "name": "Crisis", "goal": "Highest tension, twist, or decisive product proof.", "ratio": 0.20},
        {"act": 5, "name": "Resolution", "goal": "Emotional close plus platform-native final beat.", "ratio": 0.15},
    ]


def _render_hint(runtime_class: RuntimeClass, platform: str) -> str:
    if runtime_class == "short":
        return "Prefer Seedance single-call multi-shot only when the total request is <=15s and no cross-location cut exists."
    if runtime_class == "sequence":
        return "Use per-shot chain for 31-60s sequences; single-call is only for <=15s coherent openings."
    return (
        "Use scene/chunk orchestration: generate script and scene bible first, "
        "then render 4-15s shots inside 30-60s scene groups with last-frame continuity and QA/retry."
    )


__all__ = ["RuntimeStructure", "plan_runtime_structure"]
