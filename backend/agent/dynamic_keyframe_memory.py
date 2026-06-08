"""Dynamic keyframe memory contract for long-form autonomous video.

Scene memory is the pre-render plan. This module defines the post-render memory
bank that should be populated from accepted Seedance outputs: keyframes, final
frames, scene bridge anchors, and negative drift notes. Keeping this contract in
source makes the long-form workflow inspectable before the paid worker is fully
promoted.
"""
from __future__ import annotations

from typing import Any

from core.deliverable_url import deliverable_http_url


def build_dynamic_keyframe_memory_contract(
    *,
    scene_memory_pack: dict[str, Any] | None,
    production_graph: dict[str, Any] | None,
    accepted_outputs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return the keyframe memory bank policy for a planned or rendered graph."""
    memory = scene_memory_pack if isinstance(scene_memory_pack, dict) else {}
    graph = production_graph if isinstance(production_graph, dict) else {}
    outputs = [item for item in (accepted_outputs or []) if isinstance(item, dict)]
    scene_memory = [item for item in (memory.get("scene_memory") or []) if isinstance(item, dict)]
    shot_scene_map = [item for item in (memory.get("shot_scene_map") or []) if isinstance(item, dict)]
    bridge_policy = memory.get("bridge_policy") if isinstance(memory.get("bridge_policy"), dict) else {}
    rendered_anchors = [
        anchor
        for anchor in (_rendered_anchor(item, shot_scene_map=shot_scene_map) for item in outputs)
        if anchor["video_url"]
    ]
    planned_anchors = _planned_anchors(scene_memory=scene_memory, shot_scene_map=shot_scene_map)
    bridge_anchors = _bridge_anchors(bridge_policy)
    graph_summary = graph.get("summary") if isinstance(graph.get("summary"), dict) else {}
    return {
        "schema_version": "cinejelly.dynamic_keyframe_memory.v1",
        "status": "planned" if not rendered_anchors else "partially_populated",
        "source_pattern": "StoryMem memory-to-video plus VideoGen-of-Thought keyframe pipeline",
        "graph_id": graph.get("graph_id"),
        "runtime_class": memory.get("runtime_class") or graph.get("runtime_class"),
        "scene_count": int(memory.get("scene_count") or graph_summary.get("scene_count") or len(scene_memory)),
        "shot_count": int(memory.get("shot_count") or graph_summary.get("shot_count") or len(shot_scene_map)),
        "memory_bank": {
            "planned_anchors": planned_anchors,
            "rendered_anchors": rendered_anchors,
            "bridge_anchors": bridge_anchors,
            "negative_memory": [],
        },
        "update_policy": {
            "when_to_write": [
                "after shot QA passes or is explicitly accepted",
                "after a scene bridge frame is approved",
                "after a retry fixes identity/product/location drift",
            ],
            "write_fields": [
                "shot_id",
                "scene_id",
                "video_url",
                "first_frame_url",
                "last_frame_url",
                "keyframe_url",
                "identity_anchor",
                "product_anchor",
                "location_anchor",
                "qa_score",
                "drift_notes",
            ],
            "do_not_write": [
                "failed outputs",
                "stub URLs as production evidence",
                "frames with visible identity/product/location drift",
            ],
        },
        "read_policy": {
            "shot_prompt": "inject closest same-scene accepted keyframe plus approved identity/product/style refs",
            "scene_opening": "prefer previous scene final frame only when continuity bridge is required",
            "scene_closing": "request a clean final frame that can seed the next scene",
            "retry": "use negative_memory to avoid repeating failed pose, layout, text, or artifact patterns",
        },
        "promotion_gate": {
            "required_before_top_tier_long_form_claim": [
                "accepted keyframe memory exists for every scene",
                "bridge anchor exists for every required scene transition",
                "rendered anchors are populated from real output URLs",
                "identity/product/location drift notes are reviewed",
            ],
            "top_tier_claim_allowed": False,
        },
    }


def _planned_anchors(*, scene_memory: list[dict[str, Any]], shot_scene_map: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_scene: dict[str, list[dict[str, Any]]] = {}
    for shot in shot_scene_map:
        by_scene.setdefault(str(shot.get("scene_id") or "SC01"), []).append(shot)
    anchors: list[dict[str, Any]] = []
    for scene in scene_memory:
        scene_id = str(scene.get("scene_id") or "SC01")
        shots = by_scene.get(scene_id, [])
        anchors.append({
            "scene_id": scene_id,
            "opening_anchor": scene.get("opening_image_intent") or "planned opening image",
            "closing_anchor": scene.get("closing_image_intent") or "planned closing handoff image",
            "continuity_anchor": scene.get("continuity_anchor") or "scene continuity state",
            "first_shot_id": scene.get("first_shot_id") or (shots[0].get("shot_id") if shots else None),
            "last_shot_id": scene.get("last_shot_id") or (shots[-1].get("shot_id") if shots else None),
            "reference_priorities": scene.get("reference_priorities") or [],
            "required_memory_roles": [
                "identity_keyframe",
                "location_keyframe",
                "style_keyframe",
                "scene_final_frame",
            ],
        })
    return anchors


def _rendered_anchor(output: dict[str, Any], *, shot_scene_map: list[dict[str, Any]]) -> dict[str, Any]:
    shot_id = str(output.get("shot_id") or output.get("id") or "")
    shot = next((item for item in shot_scene_map if str(item.get("shot_id") or "") == shot_id), {})
    video_url = deliverable_http_url(output.get("video_url")) or deliverable_http_url(output.get("output_url"))
    first_frame_url = deliverable_http_url(output.get("first_frame_url"))
    last_frame_url = deliverable_http_url(output.get("last_frame_url")) or deliverable_http_url(output.get("keyframe_url"))
    return {
        "shot_id": shot_id or None,
        "scene_id": output.get("scene_id") or shot.get("scene_id"),
        "video_url": video_url,
        "first_frame_url": first_frame_url,
        "last_frame_url": last_frame_url,
        "keyframe_url": deliverable_http_url(output.get("keyframe_url")) or last_frame_url,
        "qa_score": output.get("qa_score"),
        "accepted": bool(output.get("accepted", True)),
        "drift_notes": output.get("drift_notes") or [],
    }


def _bridge_anchors(bridge_policy: dict[str, Any]) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    for bridge in bridge_policy.get("bridges") or []:
        if not isinstance(bridge, dict):
            continue
        anchors.append({
            "from_scene_id": bridge.get("from_scene_id"),
            "to_scene_id": bridge.get("to_scene_id"),
            "source_last_shot_id": bridge.get("source_last_shot_id"),
            "target_first_shot_id": bridge.get("target_first_shot_id"),
            "required_anchor": "previous_scene_final_frame_plus_identity_refs",
            "status": "planned",
            "risk": bridge.get("risk"),
        })
    return anchors


__all__ = ["build_dynamic_keyframe_memory_contract"]
