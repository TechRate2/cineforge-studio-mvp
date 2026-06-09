"""Production graph artifact for autonomous long-form rendering.

This is not a queue runner yet. It is the canonical graph contract that the
future queue/worker layer can execute: screenplay -> scenes -> chunks -> shots
-> QA -> assembly. Storing it inside DirectorPlan.storytelling_meta makes every
autonomous run inspectable and replayable from history.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class ProductionNode:
    id: str
    kind: str
    status: str
    payload: dict[str, Any]

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProductionEdge:
    source: str
    target: str
    relation: str

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProductionGraph:
    graph_id: str
    runtime_class: str
    duration_s: int
    nodes: list[ProductionNode]
    edges: list[ProductionEdge]
    retry_policy: dict[str, Any]
    role_stages: list[dict[str, Any]]
    approval_policy: dict[str, Any]
    evidence_policy: dict[str, Any]

    def model_dump(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "runtime_class": self.runtime_class,
            "duration_s": self.duration_s,
            "nodes": [n.model_dump() for n in self.nodes],
            "edges": [e.model_dump() for e in self.edges],
            "retry_policy": self.retry_policy,
            "role_stages": self.role_stages,
            "approval_policy": self.approval_policy,
            "evidence_policy": self.evidence_policy,
            "summary": {
                "node_count": len(self.nodes),
                "edge_count": len(self.edges),
                "shot_count": len([n for n in self.nodes if n.kind == "shot"]),
                "chunk_count": len([n for n in self.nodes if n.kind == "chunk"]),
                "scene_count": len([n for n in self.nodes if n.kind == "scene"]),
                "role_stage_count": len([n for n in self.nodes if n.kind == "role_stage"]),
            },
        }


def build_production_graph(
    *,
    plan_id: str,
    duration_s: int,
    runtime_structure: dict[str, Any],
    shots: list[Any],
    scene_memory_pack: dict[str, Any] | None = None,
    prompt_formula: dict[str, Any] | None = None,
    reference_contract: dict[str, Any] | None = None,
) -> ProductionGraph:
    """Build an inspectable graph from current autonomous planning artifacts."""
    runtime_class = str(runtime_structure.get("runtime_class") or "short")
    graph_id = f"graph_{plan_id}"
    nodes: list[ProductionNode] = []
    edges: list[ProductionEdge] = []

    role_stages = _role_stage_contract()
    _role_stage_nodes(nodes, edges, role_stages)

    nodes.append(ProductionNode(
        id="screenplay",
        kind="screenplay",
        status="planned",
        payload={
            "screenplay_plan": runtime_structure.get("screenplay_plan"),
            "act_structure": runtime_structure.get("act_structure") or [],
        },
    ))
    edges.append(ProductionEdge("role_screenwriter", "screenplay", "owns_contract"))

    scene_ids = _scene_nodes(nodes, edges, runtime_structure, scene_memory_pack=scene_memory_pack)
    chunk_ids = _chunk_nodes(nodes, edges, runtime_structure, duration_s, scene_ids, scene_memory_pack=scene_memory_pack)
    _shot_nodes(
        nodes,
        edges,
        shots,
        chunk_ids,
        scene_memory_pack=scene_memory_pack,
        prompt_formula=prompt_formula,
        reference_contract=reference_contract,
    )

    nodes.append(ProductionNode(
        id="assembly_final",
        kind="assembly",
        status="pending",
        payload={
            "requires": "all shot QA nodes pass or are accepted by policy",
            "deliverables": ["final_mp4", "caption", "hashtags", "render_quality"],
        },
    ))
    for node in nodes:
        if node.kind == "qa":
            edges.append(ProductionEdge(node.id, "assembly_final", "gates"))
    edges.append(ProductionEdge("role_editor_delivery", "assembly_final", "owns_contract"))
    edges.append(ProductionEdge("assembly_final", "role_benchmark_analyst", "feeds_evidence"))

    return ProductionGraph(
        graph_id=graph_id,
        runtime_class=runtime_class,
        duration_s=int(duration_s or 0),
        nodes=nodes,
        edges=edges,
        retry_policy={
            "max_retries_per_shot": 2,
            "retry_scope": "shot",
            "do_not_regenerate": ["screenplay", "production_bible", "approved_reference_manifest"],
            "retry_triggers": [
                "missing video_url",
                "duration mismatch",
                "identity/product drift",
                "caption/text artifact",
                "audio silence or desync",
                "prompt adherence failure",
            ],
        },
        role_stages=role_stages,
        approval_policy={
            "schema_version": "cinejelly.production_graph_approval.v2",
            "paid_render_requires": [
                "approval_lock_verified",
                "approved_reference_manifest",
                "confirmed_reference_roles",
                "cost_gate_passed",
                "deliverable_url_required",
            ],
            "long_form_requires": [
                "persisted_graph_record",
                "resume_plan",
                "segment_or_shot_level_approval",
                "benchmark_gate_for_5_to_10_minutes",
            ],
        },
        evidence_policy={
            "schema_version": "cinejelly.production_graph_evidence.v2",
            "principle": "Evidence beats claims; missing evidence stays pending or needs_review.",
            "required_for_promotion": [
                "real_output_url",
                "clean_final_delivery_qa",
                "reference_manifest",
                "qa_checkpoint_report",
                "cost_usd",
                "latency_s",
                "human_or_model_review_notes",
            ],
        },
    )


def _role_stage_contract() -> list[dict[str, Any]]:
    return [
        {
            "id": "role_intake_producer",
            "label": "Intake Producer",
            "owns": ["input_contract", "duration_policy", "market_platform_intent"],
        },
        {
            "id": "role_research_strategist",
            "label": "Research Strategist",
            "owns": ["niche_playbook", "competitive_patterns", "treatment_selection"],
        },
        {
            "id": "role_screenwriter",
            "label": "Screenwriter",
            "owns": ["screenplay", "acts", "scene_scripts", "dialogue_policy"],
        },
        {
            "id": "role_asset_librarian",
            "label": "Asset Librarian",
            "owns": ["reference_manifest", "asset_bible", "user_confirmed_roles"],
        },
        {
            "id": "role_storyboard_director",
            "label": "Storyboard Director",
            "owns": ["scene_blueprints", "shot_list", "visual_beats"],
        },
        {
            "id": "role_prompt_compiler",
            "label": "Prompt Compiler",
            "owns": ["seedance_prompt_formula", "reference_jobs", "negative_prompt"],
        },
        {
            "id": "role_render_producer",
            "label": "Render Producer",
            "owns": ["cost_gate", "approval_lock", "render_execution_plan"],
        },
        {
            "id": "role_continuity_supervisor",
            "label": "Continuity Supervisor",
            "owns": ["scene_memory", "last_frame_handoff", "downstream_invalidation"],
        },
        {
            "id": "role_critic_qa",
            "label": "Critic QA",
            "owns": ["deterministic_qa", "model_backed_qa", "repair_policy"],
        },
        {
            "id": "role_editor_delivery",
            "label": "Editor Delivery",
            "owns": ["assembly", "delivery_url", "final_delivery_qa"],
        },
        {
            "id": "role_benchmark_analyst",
            "label": "Benchmark Analyst",
            "owns": ["benchmark_evidence_pack", "promotion_readiness", "feedback_integrity"],
        },
    ]


def _role_stage_nodes(
    nodes: list[ProductionNode],
    edges: list[ProductionEdge],
    role_stages: list[dict[str, Any]],
) -> None:
    previous: str | None = None
    for index, stage in enumerate(role_stages):
        node_id = str(stage["id"])
        nodes.append(ProductionNode(
            id=node_id,
            kind="role_stage",
            status="planned",
            payload={
                "index": index,
                "label": stage["label"],
                "owns": stage["owns"],
                "execution_rule": "role nodes describe accountability only; shot/qa/assembly nodes remain the executable units",
            },
        ))
        if previous:
            edges.append(ProductionEdge(previous, node_id, "hands_off_to"))
        previous = node_id


def _scene_nodes(
    nodes: list[ProductionNode],
    edges: list[ProductionEdge],
    runtime_structure: dict[str, Any],
    *,
    scene_memory_pack: dict[str, Any] | None = None,
) -> list[str]:
    scene_blueprints = runtime_structure.get("scene_blueprints") or []
    if not scene_blueprints and scene_memory_pack:
        scene_blueprints = [
            {
                "scene_id": item.get("scene_id"),
                "index": item.get("index"),
                "act": item.get("act"),
                "duration_s": item.get("duration_s"),
                "purpose": item.get("purpose"),
                "dramatic_question": item.get("dramatic_question"),
                "visual_hook": item.get("opening_image_intent"),
                "continuity_anchor": item.get("continuity_anchor"),
                "handoff_to_next": item.get("handoff_to_next"),
            }
            for item in scene_memory_pack.get("scene_memory", [])
            if isinstance(item, dict)
        ]
    screenplay_scenes = {
        s.get("scene_id"): s
        for s in (runtime_structure.get("screenplay_plan") or {}).get("scene_scripts", [])
        if isinstance(s, dict)
    }
    scene_ids: list[str] = []
    memory_by_scene = {
        item.get("scene_id"): item
        for item in (scene_memory_pack or {}).get("scene_memory", [])
        if isinstance(item, dict)
    }
    for i, scene in enumerate(scene_blueprints):
        if not isinstance(scene, dict):
            continue
        scene_id = str(scene.get("scene_id") or f"SC{i + 1:02d}")
        node_id = f"scene_{scene_id}"
        scene_ids.append(node_id)
        nodes.append(ProductionNode(
            id=node_id,
            kind="scene",
            status="planned",
            payload={
                "blueprint": scene,
                "screenplay_scene": screenplay_scenes.get(scene_id, {}),
                "scene_memory": memory_by_scene.get(scene_id, {}),
            },
        ))
        edges.append(ProductionEdge("screenplay", node_id, "expands_to"))
        edges.append(ProductionEdge("role_storyboard_director", node_id, "owns_contract"))
    return scene_ids


def _chunk_nodes(
    nodes: list[ProductionNode],
    edges: list[ProductionEdge],
    runtime_structure: dict[str, Any],
    duration_s: int,
    scene_ids: list[str],
    *,
    scene_memory_pack: dict[str, Any] | None = None,
) -> list[str]:
    chunk_count = max(1, int(runtime_structure.get("chunk_count") or runtime_structure.get("n_chunks") or 1))
    chunk_ids: list[str] = []
    chunk_duration = max(1, int(runtime_structure.get("target_chunk_duration_s") or 60))
    for i in range(chunk_count):
        start_s = i * chunk_duration
        end_s = min(int(duration_s or 0), start_s + chunk_duration)
        node_id = f"chunk_{i:03d}"
        chunk_ids.append(node_id)
        nodes.append(ProductionNode(
            id=node_id,
            kind="chunk",
            status="pending",
            payload={
                "index": i,
                "start_s": start_s,
                "end_s": end_s,
                "target_duration_s": max(0, end_s - start_s),
                "render_strategy": runtime_structure.get("render_strategy_hint"),
                "scene_bridge_policy": _chunk_bridge_policy(
                    scene_memory_pack=scene_memory_pack,
                    scene_node_id=scene_ids[min(len(scene_ids) - 1, int(i * len(scene_ids) / max(1, chunk_count)))] if scene_ids else None,
                ),
            },
        ))
        if scene_ids:
            scene_idx = min(len(scene_ids) - 1, int(i * len(scene_ids) / max(1, chunk_count)))
            edges.append(ProductionEdge(scene_ids[scene_idx], node_id, "scheduled_as"))
        else:
            edges.append(ProductionEdge("screenplay", node_id, "scheduled_as"))
        edges.append(ProductionEdge("role_render_producer", node_id, "owns_schedule"))
    return chunk_ids


def _shot_nodes(
    nodes: list[ProductionNode],
    edges: list[ProductionEdge],
    shots: list[Any],
    chunk_ids: list[str],
    *,
    scene_memory_pack: dict[str, Any] | None = None,
    prompt_formula: dict[str, Any] | None = None,
    reference_contract: dict[str, Any] | None = None,
) -> None:
    shot_scene_map = {
        item.get("shot_id"): item
        for item in (scene_memory_pack or {}).get("shot_scene_map", [])
        if isinstance(item, dict)
    }
    for shot in shots:
        shot_id = str(getattr(shot, "shot_id", "shot"))
        start_s = float(getattr(shot, "start_s", 0.0) or 0.0)
        chunk_idx = min(len(chunk_ids) - 1, max(0, int(start_s // 60))) if chunk_ids else 0
        chunk_id = chunk_ids[chunk_idx] if chunk_ids else "chunk_000"
        node_id = f"shot_{shot_id}"
        nodes.append(ProductionNode(
            id=node_id,
            kind="shot",
            status="pending_render",
            payload={
                "shot_id": shot_id,
                "start_s": start_s,
                "end_s": float(getattr(shot, "end_s", 0.0) or 0.0),
                "duration_s": int(getattr(shot, "duration_s", 0) or 0),
                "purpose": getattr(shot, "purpose", ""),
                "previous_shot_id": getattr(getattr(shot, "continuity", None), "previous_shot_id", None),
                "scene_memory": shot_scene_map.get(shot_id, {}),
                "prompt_formula": _shot_prompt_formula(prompt_formula),
                "reference_contract": _shot_reference_contract(
                    reference_contract=reference_contract,
                    shot=shot,
                ),
                "render_contract": {
                    "unit_duration_s": [4, 15],
                    "one_action_rule": "one physically filmable action per Seedance unit",
                    "resume_rule": "rerender this shot with the same prompt formula, reference contract, and previous-frame anchor unless the graph explicitly changes upstream memory",
                },
                "approval_evidence": {
                    "requires_approval_lock": True,
                    "requires_confirmed_reference_manifest": True,
                    "requires_cost_gate": True,
                    "missing_evidence_policy": "pending_or_needs_review_never_pass",
                },
            },
        ))
        edges.append(ProductionEdge(chunk_id, node_id, "contains"))
        edges.append(ProductionEdge("role_prompt_compiler", node_id, "owns_prompt_contract"))
        edges.append(ProductionEdge("role_asset_librarian", node_id, "owns_reference_contract"))
        edges.append(ProductionEdge("role_continuity_supervisor", node_id, "owns_handoff_policy"))
        qa_id = f"qa_{shot_id}"
        nodes.append(ProductionNode(
            id=qa_id,
            kind="qa",
            status="pending",
            payload={
                "shot_id": shot_id,
                "checks": [
                    "video_url",
                    "duration",
                    "identity",
                    "product",
                    "caption",
                    "motion",
                    "audio",
                ],
            },
        ))
        edges.append(ProductionEdge(node_id, qa_id, "must_pass"))
        edges.append(ProductionEdge("role_critic_qa", qa_id, "owns_contract"))


def _chunk_bridge_policy(
    *,
    scene_memory_pack: dict[str, Any] | None,
    scene_node_id: str | None,
) -> dict[str, Any]:
    if not scene_memory_pack or not scene_node_id:
        return {}
    scene_id = scene_node_id.replace("scene_", "", 1)
    bridges = [
        item for item in ((scene_memory_pack.get("bridge_policy") or {}).get("bridges") or [])
        if isinstance(item, dict)
        and (item.get("from_scene_id") == scene_id or item.get("to_scene_id") == scene_id)
    ]
    return {
        "scene_id": scene_id,
        "bridges": bridges,
        "runtime_requires_scene_bridges": bool((scene_memory_pack.get("bridge_policy") or {}).get("runtime_requires_scene_bridges")),
    }


def _shot_prompt_formula(prompt_formula: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(prompt_formula, dict):
        return {}
    return {
        "schema_version": prompt_formula.get("schema_version"),
        "source_pattern": prompt_formula.get("source_pattern"),
        "formula": prompt_formula.get("formula") or [],
        "niche_template": prompt_formula.get("niche_template") or {},
        "rewrite_rules": (prompt_formula.get("rewrite_rules") or [])[:6],
    }


def _shot_reference_contract(
    *,
    reference_contract: dict[str, Any] | None,
    shot: Any,
) -> dict[str, Any]:
    continuity = getattr(shot, "continuity", None)
    indices = list(getattr(continuity, "reference_indices", []) or [])
    if not isinstance(reference_contract, dict):
        return {"reference_indices": indices}
    policy = reference_contract.get("reference_job_policy") or {}
    return {
        "required_reference_jobs": policy.get("required_reference_jobs") or [],
        "slot_priority": policy.get("slot_priority") or [],
        "assignment_rule": policy.get("assignment_rule"),
        "reference_indices": indices,
    }


__all__ = ["ProductionGraph", "ProductionNode", "ProductionEdge", "build_production_graph"]
