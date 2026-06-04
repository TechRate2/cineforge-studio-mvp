"""Scene memory packs for long-form autonomous video.

Long videos fail when each Seedance call only sees an isolated shot prompt.
This module builds an inspectable scene-level memory layer: what each scene
must remember, which references it should prioritize, how it hands off to the
next scene, and how shots map back to that scene contract.
"""
from __future__ import annotations

from math import ceil
from typing import Any


def build_scene_memory_pack(
    *,
    runtime_structure: dict[str, Any],
    shots: list[Any],
    seedance_reference_allocation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return scene memory and shot mapping for autonomous long-form renders."""
    scenes = [
        scene for scene in runtime_structure.get("scene_blueprints") or []
        if isinstance(scene, dict)
    ]
    screenplay_scenes = {
        str(scene.get("scene_id") or ""): scene
        for scene in (runtime_structure.get("screenplay_plan") or {}).get("scene_scripts", [])
        if isinstance(scene, dict)
    }
    target_duration_s = int(runtime_structure.get("target_duration_s") or _shots_duration(shots) or 0)
    runtime_class = str(runtime_structure.get("runtime_class") or _runtime_class(target_duration_s))

    if not scenes:
        scenes = [_single_scene_from_shots(shots, target_duration_s)]

    boundaries = _scene_boundaries(scenes, target_duration_s)
    shot_map = [_shot_scene_map(shot, scenes, boundaries) for shot in shots]
    scene_memory = [
        _scene_memory(
            scene=scene,
            scene_script=screenplay_scenes.get(str(scene.get("scene_id") or ""), {}),
            index=i,
            scene_count=len(scenes),
            shot_map=shot_map,
            seedance_reference_allocation=seedance_reference_allocation or {},
        )
        for i, scene in enumerate(scenes)
    ]
    bridge_policy = _bridge_policy(scene_memory, runtime_class=runtime_class)
    return {
        "schema_version": "cinejelly.scene_memory_pack.v1",
        "runtime_class": runtime_class,
        "target_duration_s": target_duration_s,
        "scene_count": len(scene_memory),
        "shot_count": len(shots),
        "scene_memory": scene_memory,
        "shot_scene_map": shot_map,
        "bridge_policy": bridge_policy,
        "qa_contract": {
            "per_scene": [
                "opening image matches scene purpose",
                "closing image creates a usable handoff",
                "same character/product refs persist unless scene explicitly changes",
                "each Seedance unit stays 4-15s and has one physical action",
            ],
            "whole_film": [
                "cold open is visible in first 3 seconds",
                "every scene changes the story situation",
                "scene transitions do not reset identity, product geometry, location, or color language",
                "caption/audio choices match target market and niche",
            ],
        },
        "producer_note": (
            "Use this pack as the memory contract when regenerating a shot/chunk. "
            "Do not rewrite the full screenplay unless scene-level QA fails structurally."
        ),
    }


def _scene_memory(
    *,
    scene: dict[str, Any],
    scene_script: dict[str, Any],
    index: int,
    scene_count: int,
    shot_map: list[dict[str, Any]],
    seedance_reference_allocation: dict[str, Any],
) -> dict[str, Any]:
    scene_id = str(scene.get("scene_id") or f"SC{index + 1:02d}")
    duration_s = int(scene.get("duration_s") or scene_script.get("duration_s") or 60)
    shots = [item for item in shot_map if item.get("scene_id") == scene_id]
    reference_plan = seedance_reference_allocation.get("scene_reference_policy") or {}
    reference_manifest = seedance_reference_allocation.get("reference_manifest") or {}
    return {
        "scene_id": scene_id,
        "index": int(scene.get("index") if scene.get("index") is not None else index),
        "act": int(scene.get("act") or scene_script.get("act") or 1),
        "duration_s": duration_s,
        "purpose": scene.get("purpose") or scene_script.get("premise") or "advance_story",
        "dramatic_question": scene.get("dramatic_question") or "",
        "opening_image_intent": scene_script.get("opening_image") or scene.get("visual_hook") or "",
        "closing_image_intent": scene_script.get("closing_image") or scene.get("handoff_to_next") or "",
        "conflict": scene_script.get("conflict") or "",
        "turning_point": scene_script.get("turning_point") or "",
        "continuity_anchor": scene.get("continuity_anchor") or "",
        "handoff_to_next": scene.get("handoff_to_next") or "",
        "reference_priorities": scene_script.get("reference_priorities") or _reference_priorities(reference_manifest),
        "seedance_unit_policy": {
            "target_unit_duration_s": min(12, max(4, duration_s // max(1, ceil(duration_s / 12)))),
            "estimated_units": max(1, ceil(duration_s / 12)),
            "max_unit_duration_s": 15,
            "single_action_rule": "one subject, one action, one camera move, one clear audio cue per unit",
            "reference_policy": reference_plan,
        },
        "shot_ids": [str(item.get("shot_id")) for item in shots],
        "first_shot_id": str(shots[0].get("shot_id")) if shots else None,
        "last_shot_id": str(shots[-1].get("shot_id")) if shots else None,
        "previous_scene_final_frame_required": index > 0,
        "next_scene_bridge_required": index < scene_count - 1,
        "qa_focus": scene_script.get("qa_focus") or [
            "scene purpose visible",
            "identity/product continuity",
            "opening/closing image quality",
        ],
    }


def _shot_scene_map(shot: Any, scenes: list[dict[str, Any]], boundaries: list[tuple[str, float, float]]) -> dict[str, Any]:
    shot_id = str(getattr(shot, "shot_id", "shot"))
    start_s = float(getattr(shot, "start_s", 0.0) or 0.0)
    scene_id = boundaries[-1][0] if boundaries else "SC01"
    for candidate_scene_id, start, end in boundaries:
        if start_s >= start and start_s < end:
            scene_id = candidate_scene_id
            break
    scene_index = next((i for i, scene in enumerate(scenes) if str(scene.get("scene_id")) == scene_id), 0)
    continuity = getattr(shot, "continuity", None)
    visual = getattr(shot, "visual", None)
    return {
        "shot_id": shot_id,
        "scene_id": scene_id,
        "scene_index": scene_index,
        "start_s": start_s,
        "end_s": float(getattr(shot, "end_s", 0.0) or 0.0),
        "purpose": getattr(shot, "purpose", ""),
        "role_in_scene": _role_in_scene(start_s, scene_id, boundaries),
        "previous_shot_id": getattr(continuity, "previous_shot_id", None),
        "reference_indices": list(getattr(continuity, "reference_indices", []) or []),
        "subject": getattr(visual, "subject", None),
        "camera": " ".join(
            str(part)
            for part in [
                getattr(visual, "camera_shot", None),
                getattr(visual, "camera_movement", None),
            ]
            if part
        ),
    }


def _scene_boundaries(scenes: list[dict[str, Any]], total_duration_s: int) -> list[tuple[str, float, float]]:
    boundaries: list[tuple[str, float, float]] = []
    cursor = 0.0
    for i, scene in enumerate(scenes):
        scene_id = str(scene.get("scene_id") or f"SC{i + 1:02d}")
        dur = float(scene.get("duration_s") or max(1, total_duration_s // max(1, len(scenes))))
        boundaries.append((scene_id, cursor, cursor + dur))
        cursor += dur
    return boundaries


def _bridge_policy(scene_memory: list[dict[str, Any]], *, runtime_class: str) -> dict[str, Any]:
    bridges: list[dict[str, Any]] = []
    for current, nxt in zip(scene_memory, scene_memory[1:]):
        bridges.append({
            "from_scene_id": current["scene_id"],
            "to_scene_id": nxt["scene_id"],
            "source_last_shot_id": current.get("last_shot_id"),
            "target_first_shot_id": nxt.get("first_shot_id"),
            "preferred_bridge": "previous_scene_final_frame_plus_identity_refs",
            "repair_if_drift": "regenerate bridge first-frame/keyframe before re-rendering the full next scene",
            "risk": _bridge_risk(current, nxt),
        })
    return {
        "runtime_requires_scene_bridges": runtime_class in {"micro_film", "short_film", "episode"},
        "bridge_count": len(bridges),
        "bridges": bridges,
    }


def _bridge_risk(current: dict[str, Any], nxt: dict[str, Any]) -> str:
    text = " ".join([
        str(current.get("closing_image_intent") or ""),
        str(nxt.get("opening_image_intent") or ""),
        str(nxt.get("continuity_anchor") or ""),
    ]).lower()
    if any(token in text for token in ("new location", "new world", "time jump", "different location")):
        return "high_location_or_time_shift"
    if current.get("last_shot_id") and nxt.get("first_shot_id"):
        return "medium_identity_and_color_continuity"
    return "medium_missing_shot_bridge"


def _role_in_scene(start_s: float, scene_id: str, boundaries: list[tuple[str, float, float]]) -> str:
    for candidate_scene_id, start, end in boundaries:
        if candidate_scene_id != scene_id:
            continue
        span = max(1.0, end - start)
        pos = (start_s - start) / span
        if pos < 0.2:
            return "scene_opening"
        if pos > 0.8:
            return "scene_closing_handoff"
        return "scene_body"
    return "scene_body"


def _single_scene_from_shots(shots: list[Any], target_duration_s: int) -> dict[str, Any]:
    return {
        "scene_id": "SC01",
        "index": 0,
        "act": 1,
        "duration_s": target_duration_s or _shots_duration(shots) or 15,
        "purpose": "hook_to_payoff",
        "dramatic_question": "What visible change makes the viewer keep watching?",
        "visual_hook": "strongest first-frame visual proof",
        "continuity_anchor": "same production bible and references",
        "handoff_to_next": "final payoff image",
    }


def _reference_priorities(reference_manifest: dict[str, Any]) -> list[str]:
    priorities = ["previous scene final frame", "character/product identity refs", "style reference"]
    if reference_manifest.get("videos"):
        priorities.append("video reference for camera/motion")
    if reference_manifest.get("audios"):
        priorities.append("audio reference for rhythm/SFX/dialogue")
    return priorities


def _shots_duration(shots: list[Any]) -> int:
    return int(sum(float(getattr(shot, "duration_s", 0.0) or 0.0) for shot in shots))


def _runtime_class(duration_s: int) -> str:
    if duration_s <= 30:
        return "short"
    if duration_s <= 60:
        return "sequence"
    if duration_s <= 180:
        return "micro_film"
    if duration_s <= 600:
        return "short_film"
    return "episode"


__all__ = ["build_scene_memory_pack"]
