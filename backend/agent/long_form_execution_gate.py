"""Long-form execution gate for autonomous video production.

This module turns the long-form architecture into an enforceable contract. A
5m/30m job should not silently fall back to a weak linear path unless the graph,
scene memory, and handoff evidence are visible to preflight and the UI.
"""
from __future__ import annotations

from typing import Any, Optional


_LONG_FORM_RUNTIME_CLASSES = {"short_film", "episode"}
_SCENE_MEMORY_RUNTIME_CLASSES = {"micro_film", "short_film", "episode"}


def build_long_form_execution_gate(
    *,
    duration_s: int,
    runtime_payload: dict[str, Any],
    production_graph: Optional[dict[str, Any]] = None,
    scene_memory_pack: Optional[dict[str, Any]] = None,
    shots: Optional[list[Any]] = None,
    graph_executor_enabled: Optional[bool] = None,
    route_quality_scorecard: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Return a source-backed execution readiness report for longer videos."""
    runtime_class = str(runtime_payload.get("runtime_class") or "")
    duration = int(duration_s or runtime_payload.get("target_duration_s") or 0)
    is_long_form = duration > 180 or runtime_class in _LONG_FORM_RUNTIME_CLASSES
    needs_scene_memory = duration > 60 or runtime_class in _SCENE_MEMORY_RUNTIME_CLASSES
    graph_required = is_long_form
    graph = production_graph if isinstance(production_graph, dict) else {}
    memory = scene_memory_pack if isinstance(scene_memory_pack, dict) else {}
    requirements: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []

    def add(
        name: str,
        status: str,
        detail: str,
        *,
        blocking: bool = False,
    ) -> None:
        requirements.append({"name": name, "status": status, "detail": detail})
        if status == "fail" and blocking:
            blockers.append(name)
        elif status == "warn":
            warnings.append(name)

    if not is_long_form and not needs_scene_memory:
        add("runtime_scope", "pass", "Short-form job can use the normal autonomous route.")
        return {
            "schema_version": "cinejelly.long_form_execution_gate.v1",
            "enabled": False,
            "status": "pass",
            "runtime_class": runtime_class or "short",
            "target_duration_s": duration,
            "render_route": "single_or_linear_short_form",
            "default_route_allowed": True,
            "graph_executor_ready": False,
            "long_form_claim_allowed": False,
            "blockers": [],
            "warnings": [],
            "requirements": requirements,
            "execution_contract": _execution_contract(
                graph=graph,
                memory=memory,
                shots=shots,
                runtime_payload=runtime_payload,
            ),
            "required_before_default": [],
            "next_action": "render_short_form",
        }

    graph_summary = graph.get("summary") if isinstance(graph.get("summary"), dict) else {}
    graph_nodes = [n for n in (graph.get("nodes") or []) if isinstance(n, dict)]
    graph_shots = [n for n in graph_nodes if n.get("kind") == "shot"]
    graph_qa = [n for n in graph_nodes if n.get("kind") == "qa"]
    scene_memory = [s for s in (memory.get("scene_memory") or []) if isinstance(s, dict)]
    bridge_policy = memory.get("bridge_policy") if isinstance(memory.get("bridge_policy"), dict) else {}
    bridge_count = int(bridge_policy.get("bridge_count") or len(bridge_policy.get("bridges") or []))
    shot_count = _shot_count(shots, graph_summary, graph_shots)
    active_handoffs = _active_handoff_count(shots, graph_shots)
    required_handoffs = _required_handoff_count(duration, runtime_class, shot_count)

    add(
        "runtime_scope",
        "pass",
        f"{runtime_class or 'unknown'} runtime at {duration}s requires chunked Seedance execution.",
    )
    if graph_required:
        if graph_summary and graph_shots and graph_qa:
            add(
                "production_graph",
                "pass",
                f"Graph has {graph_summary.get('node_count', len(graph_nodes))} nodes, {len(graph_shots)} shot nodes, and {len(graph_qa)} QA nodes.",
            )
        elif graph_summary:
            add(
                "production_graph",
                "warn",
                "Graph summary exists, but executable shot/QA nodes are not fully visible.",
            )
        else:
            add(
                "production_graph",
                "fail",
                "Long-form jobs need a persisted screenplay -> scene -> shot -> QA -> assembly graph before render.",
                blocking=True,
            )

    if needs_scene_memory:
        if scene_memory:
            add(
                "scene_memory_pack",
                "pass",
                f"Scene memory has {len(scene_memory)} scene record(s) for anchors, opening/closing images, and QA focus.",
            )
        else:
            add(
                "scene_memory_pack",
                "fail" if graph_required else "warn",
                "Longer jobs need scene memory so every chunk preserves character/product/location state.",
                blocking=graph_required,
            )

    if graph_required and len(scene_memory) > 1:
        if bridge_count >= len(scene_memory) - 1:
            add("scene_bridge_policy", "pass", f"Bridge policy covers {bridge_count} scene transition(s).")
        else:
            add(
                "scene_bridge_policy",
                "fail",
                "Scene bridges are incomplete; later scenes may feel disconnected or drift visually.",
                blocking=True,
            )
    elif graph_required:
        add("scene_bridge_policy", "warn", "Scene bridge policy cannot be proven until scene memory has multiple scenes.")

    if graph_required and shot_count:
        if active_handoffs >= required_handoffs:
            add(
                "last_frame_handoffs",
                "pass",
                f"{active_handoffs}/{required_handoffs} required previous-shot handoff(s) are active.",
            )
        else:
            add(
                "last_frame_handoffs",
                "fail",
                f"Only {active_handoffs}/{required_handoffs} required previous-shot handoff(s) are active.",
                blocking=True,
            )
    elif graph_required:
        add(
            "last_frame_handoffs",
            "warn",
            "Shot-level handoffs cannot be proven until the DirectorPlan shot list is available.",
        )

    if graph_required:
        if graph_executor_enabled is True:
            add("graph_executor_flag", "pass", "Graph executor is enabled for this environment.")
        elif graph_executor_enabled is False:
            add(
                "graph_executor_flag",
                "warn",
                "Graph executor is available in source, but the environment flag is off; render will use the linear worker fallback.",
            )
        else:
            add(
                "graph_executor_flag",
                "warn",
                "Graph executor environment state is not known in this planning preview.",
            )

    route = route_quality_scorecard if isinstance(route_quality_scorecard, dict) else {}
    if graph_required and route:
        if route.get("top_tier_claim_allowed"):
            add("benchmark_evidence", "pass", "Route has benchmark evidence for top-tier claim.")
        else:
            add(
                "benchmark_evidence",
                "warn",
                "Route is not benchmark-promoted yet; do not market this long-form path as top-tier.",
            )

    graph_executor_ready = bool(graph_required and graph_summary and graph_shots and graph_qa and scene_memory and not blockers)
    default_route_allowed = bool(
        (not graph_required)
        or (
            graph_executor_ready
            and graph_executor_enabled is True
            and not bool(route.get("requires_human_review"))
        )
    )
    status = "fail" if blockers else ("warn" if warnings or graph_required else "pass")
    required_before_default = _required_before_default(
        blockers=blockers,
        warnings=warnings,
        graph_required=graph_required,
        graph_executor_enabled=graph_executor_enabled,
        route=route,
    )
    return {
        "schema_version": "cinejelly.long_form_execution_gate.v1",
        "enabled": True,
        "status": status,
        "runtime_class": runtime_class or "unknown",
        "target_duration_s": duration,
        "render_route": (
            "graph_executor_required"
            if graph_required else "scene_memory_linear_allowed"
        ),
        "default_route_allowed": default_route_allowed,
        "graph_executor_ready": graph_executor_ready,
        "long_form_claim_allowed": bool(route.get("top_tier_claim_allowed")) and graph_executor_ready,
        "blockers": blockers,
        "warnings": warnings,
        "requirements": requirements,
        "execution_contract": _execution_contract(
            graph=graph,
            memory=memory,
            shots=shots,
            runtime_payload=runtime_payload,
            graph_shot_count=len(graph_shots),
            graph_qa_count=len(graph_qa),
            active_handoffs=active_handoffs,
            required_handoffs=required_handoffs,
        ),
        "required_before_default": required_before_default,
        "next_action": (
            "fix_long_form_plan_before_render" if blockers
            else "enable_graph_executor_and_run_benchmarks" if graph_required and graph_executor_enabled is not True
            else "render_with_graph_executor_and_visible_qa" if default_route_allowed
            else "manual_review_or_benchmark_before_default"
        ),
    }


def _execution_contract(
    *,
    graph: dict[str, Any],
    memory: dict[str, Any],
    shots: Optional[list[Any]],
    runtime_payload: dict[str, Any],
    graph_shot_count: Optional[int] = None,
    graph_qa_count: Optional[int] = None,
    active_handoffs: Optional[int] = None,
    required_handoffs: Optional[int] = None,
) -> dict[str, Any]:
    graph_summary = graph.get("summary") if isinstance(graph.get("summary"), dict) else {}
    bridge_policy = memory.get("bridge_policy") if isinstance(memory.get("bridge_policy"), dict) else {}
    unit_duration = int(runtime_payload.get("target_chunk_duration_s") or 60)
    return {
        "unit_duration_s": [4, 15],
        "target_chunk_duration_s": unit_duration,
        "graph_node_count": int(graph_summary.get("node_count") or len(graph.get("nodes") or [])),
        "graph_shot_count": int(graph_shot_count if graph_shot_count is not None else graph_summary.get("shot_count") or 0),
        "graph_qa_count": int(graph_qa_count if graph_qa_count is not None else 0),
        "shot_count": _shot_count(shots, graph_summary, []),
        "scene_count": int(memory.get("scene_count") or graph_summary.get("scene_count") or runtime_payload.get("scene_count") or 0),
        "scene_bridge_count": int(bridge_policy.get("bridge_count") or len(bridge_policy.get("bridges") or [])),
        "active_handoffs": int(active_handoffs if active_handoffs is not None else 0),
        "required_handoffs": int(required_handoffs if required_handoffs is not None else 0),
        "doctrine": [
            "never ask a video model for one 5m/30m clip",
            "render 4-15s Seedance units",
            "chain prior final frames for continuity",
            "run per-shot QA/retry before final assembly",
        ],
    }


def _shot_count(
    shots: Optional[list[Any]],
    graph_summary: dict[str, Any],
    graph_shots: list[dict[str, Any]],
) -> int:
    if shots is not None:
        return len(shots)
    return int(graph_summary.get("shot_count") or len(graph_shots) or 0)


def _active_handoff_count(shots: Optional[list[Any]], graph_shots: list[dict[str, Any]]) -> int:
    if shots is not None:
        return sum(
            1
            for shot in shots
            if getattr(getattr(shot, "continuity", None), "previous_shot_id", None)
        )
    return sum(
        1
        for node in graph_shots
        if (node.get("payload") or {}).get("previous_shot_id")
    )


def _required_handoff_count(duration_s: int, runtime_class: str, shot_count: int) -> int:
    if duration_s > 600 or runtime_class == "episode":
        return max(2, min(max(shot_count - 1, 0), shot_count // 2))
    if duration_s > 180 or runtime_class == "short_film":
        return max(1, min(max(shot_count - 1, 0), shot_count // 3))
    if duration_s > 60 or runtime_class == "micro_film":
        return 1 if shot_count > 1 else 0
    return 0


def _required_before_default(
    *,
    blockers: list[str],
    warnings: list[str],
    graph_required: bool,
    graph_executor_enabled: Optional[bool],
    route: dict[str, Any],
) -> list[str]:
    items: list[str] = []
    for blocker in blockers:
        if blocker == "production_graph":
            items.append("persist executable production_graph with shot and QA nodes")
        elif blocker == "scene_memory_pack":
            items.append("attach scene_memory_pack with opening/closing images and continuity anchors")
        elif blocker == "scene_bridge_policy":
            items.append("complete scene bridge policy for every scene transition")
        elif blocker == "last_frame_handoffs":
            items.append("add previous_shot_id handoffs for required chained shots")
        else:
            items.append(f"resolve {blocker}")
    if graph_required and graph_executor_enabled is not True:
        items.append("enable CINEJELLY_ENABLE_GRAPH_LONG_FORM only after paid graph smoke tests pass")
    if route and not route.get("top_tier_claim_allowed"):
        items.append("run two approved benchmark outputs for this route before top-tier claim")
    if "benchmark_evidence" in warnings and "run two approved benchmark outputs for this route before top-tier claim" not in items:
        items.append("collect benchmark evidence before public top-tier claim")
    return list(dict.fromkeys(items))


__all__ = ["build_long_form_execution_gate"]
