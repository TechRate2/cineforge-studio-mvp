"""SQLite persistence for autonomous production graphs.

The in-plan graph artifact is useful for debugging, but long-form production
needs queryable node/edge state: scenes, chunks, shots, QA gates, retries, and
assembly must survive process restarts. This store is intentionally small and
append-safe so the current linear worker can persist graph state today, while a
future graph executor can update node statuses as work completes.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger


_DB_PATH = Path(__file__).parent.parent / "data" / "production_graphs.db"
_LOCK = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS production_graphs (
    job_id       TEXT PRIMARY KEY,
    plan_id      TEXT NOT NULL,
    graph_id     TEXT NOT NULL,
    runtime_class TEXT,
    duration_s   INTEGER,
    summary      TEXT NOT NULL DEFAULT '{}',
    graph_blob   TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_production_graphs_plan ON production_graphs(plan_id);
CREATE INDEX IF NOT EXISTS idx_production_graphs_updated ON production_graphs(updated_at DESC);

CREATE TABLE IF NOT EXISTS production_graph_nodes (
    job_id      TEXT NOT NULL,
    node_id     TEXT NOT NULL,
    kind        TEXT NOT NULL,
    status      TEXT NOT NULL,
    payload     TEXT NOT NULL DEFAULT '{}',
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (job_id, node_id)
);
CREATE INDEX IF NOT EXISTS idx_production_graph_nodes_kind ON production_graph_nodes(kind);
CREATE INDEX IF NOT EXISTS idx_production_graph_nodes_status ON production_graph_nodes(status);

CREATE TABLE IF NOT EXISTS production_graph_edges (
    job_id    TEXT NOT NULL,
    source    TEXT NOT NULL,
    target    TEXT NOT NULL,
    relation  TEXT NOT NULL,
    PRIMARY KEY (job_id, source, target, relation)
);
"""


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=10.0)
    c.execute("PRAGMA journal_mode=WAL")
    c.row_factory = sqlite3.Row
    return c


def _init() -> None:
    with _LOCK:
        with _conn() as c:
            c.executescript(_SCHEMA)


_init()


def save_graph(
    *,
    job_id: str,
    plan_id: str,
    graph: dict[str, Any],
) -> dict[str, Any]:
    """Persist graph, nodes, and edges; return lightweight metadata."""
    if not isinstance(graph, dict) or not graph:
        return {"persisted": False, "reason": "missing_graph"}

    graph_id = str(graph.get("graph_id") or f"graph_{plan_id}")
    runtime_class = str(graph.get("runtime_class") or "")
    duration_s = int(graph.get("duration_s") or 0)
    nodes = [n for n in (graph.get("nodes") or []) if isinstance(n, dict)]
    edges = [e for e in (graph.get("edges") or []) if isinstance(e, dict)]
    summary = graph.get("summary") if isinstance(graph.get("summary"), dict) else {}
    now = datetime.now(timezone.utc).isoformat()

    with _LOCK:
        with _conn() as c:
            c.execute(
                """
                INSERT OR REPLACE INTO production_graphs
                    (job_id, plan_id, graph_id, runtime_class, duration_s,
                     summary, graph_blob, created_at, updated_at)
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    COALESCE((SELECT created_at FROM production_graphs WHERE job_id = ?), ?),
                    ?
                )
                """,
                (
                    job_id,
                    plan_id,
                    graph_id,
                    runtime_class,
                    duration_s,
                    json.dumps(summary, ensure_ascii=False, default=str),
                    json.dumps(graph, ensure_ascii=False, default=str),
                    job_id,
                    now,
                    now,
                ),
            )
            c.execute("DELETE FROM production_graph_nodes WHERE job_id = ?", (job_id,))
            c.execute("DELETE FROM production_graph_edges WHERE job_id = ?", (job_id,))
            c.executemany(
                """
                INSERT INTO production_graph_nodes
                    (job_id, node_id, kind, status, payload, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        job_id,
                        str(node.get("id") or ""),
                        str(node.get("kind") or "unknown"),
                        str(node.get("status") or "pending"),
                        json.dumps(node.get("payload") or {}, ensure_ascii=False, default=str),
                        now,
                    )
                    for node in nodes
                    if node.get("id")
                ],
            )
            c.executemany(
                """
                INSERT INTO production_graph_edges (job_id, source, target, relation)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        job_id,
                        str(edge.get("source") or ""),
                        str(edge.get("target") or ""),
                        str(edge.get("relation") or "links"),
                    )
                    for edge in edges
                    if edge.get("source") and edge.get("target")
                ],
            )
    logger.info(
        f"[production_graph_store] saved job={job_id} graph={graph_id} nodes={len(nodes)} edges={len(edges)}"
    )
    return {
        "persisted": True,
        "job_id": job_id,
        "plan_id": plan_id,
        "graph_id": graph_id,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "runtime_class": runtime_class,
        "duration_s": duration_s,
    }


def load_graph(job_id: str) -> Optional[dict[str, Any]]:
    """Load a persisted graph with current node statuses, if present."""
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM production_graphs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if not row:
            return None
        nodes = c.execute(
            """
            SELECT node_id, kind, status, payload, updated_at
              FROM production_graph_nodes
             WHERE job_id = ?
             ORDER BY node_id ASC
            """,
            (job_id,),
        ).fetchall()
        edges = c.execute(
            """
            SELECT source, target, relation
              FROM production_graph_edges
             WHERE job_id = ?
             ORDER BY source ASC, target ASC
            """,
            (job_id,),
        ).fetchall()
    return {
        "job_id": row["job_id"],
        "plan_id": row["plan_id"],
        "graph_id": row["graph_id"],
        "runtime_class": row["runtime_class"],
        "duration_s": row["duration_s"],
        "summary": json.loads(row["summary"] or "{}"),
        "graph": json.loads(row["graph_blob"] or "{}"),
        "nodes": [
            {
                "id": n["node_id"],
                "kind": n["kind"],
                "status": n["status"],
                "payload": json.loads(n["payload"] or "{}"),
                "updated_at": n["updated_at"],
            }
            for n in nodes
        ],
        "edges": [dict(e) for e in edges],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def build_resume_plan(graph_record: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic resume/diagnostic plan for a persisted graph.

    This does not execute work. It gives the API/UI/future queue runner a clear
    answer to: what failed, what is running, which shot can safely resume next,
    and whether final assembly is unblocked.
    """
    nodes = [
        node for node in (graph_record or {}).get("nodes", [])
        if isinstance(node, dict)
    ]
    by_id = {str(node.get("id")): node for node in nodes if node.get("id")}
    counts: dict[str, int] = {}
    for node in nodes:
        status = str(node.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1

    failed_nodes = [_node_summary(n) for n in nodes if _node_status(n) in _FAILED_STATUSES]
    running_nodes = [_node_summary(n) for n in nodes if _node_status(n) in _RUNNING_STATUSES]
    pending_shots = _pending_shot_actions(nodes, by_id)
    assembly = by_id.get("assembly_final")
    assembly_ready = bool(assembly) and not pending_shots and not failed_nodes and not running_nodes

    if failed_nodes:
        next_action = "retry_or_repair_failed_nodes"
    elif running_nodes:
        next_action = "wait_for_running_nodes"
    elif pending_shots:
        next_action = pending_shots[0]["action"]
    elif assembly_ready and _node_status(assembly) not in _DONE_STATUSES:
        next_action = "assemble_final"
    else:
        next_action = "complete_or_noop"

    return {
        "schema_version": "cinejelly.graph_resume.v1",
        "job_id": graph_record.get("job_id"),
        "plan_id": graph_record.get("plan_id"),
        "graph_id": graph_record.get("graph_id"),
        "runtime_class": graph_record.get("runtime_class"),
        "duration_s": graph_record.get("duration_s"),
        "next_action": next_action,
        "status_counts": counts,
        "failed_nodes": failed_nodes[:20],
        "running_nodes": running_nodes[:20],
        "next_pending_shots": pending_shots[:20],
        "assembly_ready": assembly_ready,
        "can_resume": bool(failed_nodes or pending_shots or assembly_ready),
        "resume_policy": {
            "unit": "shot",
            "preserve": ["screenplay", "production_bible", "reference_roles", "completed_shots"],
            "rerender": "failed or pending shot nodes only; rerender downstream chained shots when their previous_shot_id anchor changes",
        },
    }


def build_execution_batch(
    graph_record: dict[str, Any],
    *,
    limit: int = 4,
) -> dict[str, Any]:
    """Return the next graph nodes a queue runner can execute safely.

    This still does not render anything. It turns graph state into a concrete
    execution batch with dependency-safe shot tasks, QA tasks, or final assembly.
    A future worker can consume this directly instead of re-planning the whole
    autonomous job.
    """
    nodes = [
        node for node in (graph_record or {}).get("nodes", [])
        if isinstance(node, dict)
    ]
    by_id = {str(node.get("id")): node for node in nodes if node.get("id")}
    max_items = max(1, min(int(limit or 4), 25))
    resume = build_resume_plan(graph_record)

    if resume["running_nodes"]:
        return _execution_response(
            graph_record,
            mode="wait",
            reason="running_nodes_present",
            tasks=[],
            resume_plan=resume,
        )

    failed = [
        node for node in nodes
        if str(node.get("kind") or "") == "shot"
        and _node_status(node) in _FAILED_STATUSES
    ]
    failed.sort(key=_shot_sort_key)
    retry_tasks = [
        _task_for_shot(node, action="retry_shot", priority="high", by_id=by_id)
        for node in failed
        if not _blocked_by_previous_shot(node, by_id)
    ][:max_items]
    if retry_tasks:
        return _execution_response(
            graph_record,
            mode="retry",
            reason="failed_shots_ready",
            tasks=retry_tasks,
            resume_plan=resume,
        )

    pending = [
        node for node in nodes
        if str(node.get("kind") or "") == "shot"
        and _node_status(node) in _PENDING_STATUSES
    ]
    pending.sort(key=_shot_sort_key)
    render_tasks = [
        _task_for_shot(node, action="render_shot", priority="normal", by_id=by_id)
        for node in pending
        if not _blocked_by_previous_shot(node, by_id)
    ][:max_items]
    if render_tasks:
        return _execution_response(
            graph_record,
            mode="render",
            reason="pending_shots_ready",
            tasks=render_tasks,
            resume_plan=resume,
        )

    qa_tasks = _ready_qa_tasks(nodes, by_id, max_items)
    if qa_tasks:
        return _execution_response(
            graph_record,
            mode="qa",
            reason="qa_nodes_ready",
            tasks=qa_tasks,
            resume_plan=resume,
        )

    assembly = by_id.get("assembly_final")
    if assembly and _node_status(assembly) in _PENDING_STATUSES and _all_qa_done(nodes):
        return _execution_response(
            graph_record,
            mode="assembly",
            reason="all_qa_passed_or_accepted",
            tasks=[{
                "node_id": "assembly_final",
                "kind": "assembly",
                "action": "assemble_final",
                "priority": "normal",
                "blocked_by": [],
                "payload": assembly.get("payload") or {},
            }],
            resume_plan=resume,
        )

    return _execution_response(
        graph_record,
        mode="noop",
        reason="no_ready_nodes",
        tasks=[],
        resume_plan=resume,
    )


def claim_execution_batch(
    *,
    job_id: str,
    worker_id: str = "autonomous_executor",
    limit: int = 4,
    lease_ttl_s: int = 900,
) -> Optional[dict[str, Any]]:
    """Lease the next executable graph tasks for a future queue worker.

    This is the first non-rendering executor primitive: it atomically marks the
    selected ready nodes as `leased` with a lease id and worker metadata so a
    second worker does not start the same shot/QA/assembly task.
    """
    release_expired_leases(job_id)
    graph_record = load_graph(job_id)
    if not graph_record:
        return None

    batch = build_execution_batch(graph_record, limit=limit)
    tasks = list(batch.get("tasks") or [])
    if not tasks:
        return {
            "schema_version": "cinejelly.graph_execution_claim.v1",
            "job_id": job_id,
            "claimed": False,
            "claimed_count": 0,
            "reason": batch.get("reason"),
            "execution_batch": batch,
        }

    lease_id = f"lease_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    claimed: list[dict[str, Any]] = []
    for task in tasks:
        node_id = str(task.get("node_id") or "")
        if not node_id:
            continue
        current_node = next(
            (node for node in (graph_record.get("nodes") or []) if node.get("id") == node_id),
            {},
        )
        ok = update_node_status(
            job_id=job_id,
            node_id=node_id,
            status="leased",
            payload_patch={
                "lease_id": lease_id,
                "lease_worker_id": worker_id,
                "lease_action": task.get("action"),
                "lease_previous_status": current_node.get("status"),
                "lease_claimed_at": now,
                "lease_ttl_s": max(30, int(lease_ttl_s or 900)),
            },
        )
        if ok:
            claimed.append({**task, "lease_id": lease_id, "lease_worker_id": worker_id})

    return {
        "schema_version": "cinejelly.graph_execution_claim.v1",
        "job_id": job_id,
        "plan_id": graph_record.get("plan_id"),
        "graph_id": graph_record.get("graph_id"),
        "claimed": bool(claimed),
        "claimed_count": len(claimed),
        "lease_id": lease_id,
        "worker_id": worker_id,
        "lease_ttl_s": max(30, int(lease_ttl_s or 900)),
        "claimed_at": now,
        "tasks": claimed,
        "execution_batch": batch,
    }


def release_expired_leases(job_id: str) -> dict[str, Any]:
    """Release expired leased nodes back to their previous executable status."""
    now = datetime.now(timezone.utc)
    released: list[dict[str, Any]] = []
    with _LOCK:
        with _conn() as c:
            rows = c.execute(
                """
                SELECT node_id, kind, status, payload
                  FROM production_graph_nodes
                 WHERE job_id = ? AND status = 'leased'
                """,
                (job_id,),
            ).fetchall()
            for row in rows:
                payload = json.loads(row["payload"] or "{}")
                if not _lease_is_expired(payload, now):
                    continue
                previous_status = str(payload.get("lease_previous_status") or "")
                if not previous_status or previous_status == "leased":
                    previous_status = _fallback_status_for_kind(row["kind"])
                payload.update({
                    "lease_released_at": now.isoformat(),
                    "lease_release_reason": "expired",
                    "last_lease_id": payload.get("lease_id"),
                })
                for key in (
                    "lease_id",
                    "lease_worker_id",
                    "lease_action",
                    "lease_claimed_at",
                    "lease_ttl_s",
                    "lease_previous_status",
                ):
                    payload.pop(key, None)
                c.execute(
                    """
                    UPDATE production_graph_nodes
                       SET status = ?, payload = ?, updated_at = ?
                     WHERE job_id = ? AND node_id = ?
                    """,
                    (
                        previous_status,
                        json.dumps(payload, ensure_ascii=False, default=str),
                        now.isoformat(),
                        job_id,
                        row["node_id"],
                    ),
                )
                released.append({
                    "node_id": row["node_id"],
                    "kind": row["kind"],
                    "restored_status": previous_status,
                })
            if released:
                c.execute(
                    "UPDATE production_graphs SET updated_at = ? WHERE job_id = ?",
                    (now.isoformat(), job_id),
                )
    return {
        "schema_version": "cinejelly.graph_lease_release.v1",
        "job_id": job_id,
        "released_count": len(released),
        "released": released,
    }


def update_node_status(
    *,
    job_id: str,
    node_id: str,
    status: str,
    payload_patch: Optional[dict[str, Any]] = None,
) -> bool:
    """Patch one node status/payload. Returns False when node is absent."""
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        with _conn() as c:
            row = c.execute(
                "SELECT payload FROM production_graph_nodes WHERE job_id = ? AND node_id = ?",
                (job_id, node_id),
            ).fetchone()
            if not row:
                return False
            payload = json.loads(row["payload"] or "{}")
            if payload_patch:
                payload.update(payload_patch)
            c.execute(
                """
                UPDATE production_graph_nodes
                   SET status = ?, payload = ?, updated_at = ?
                 WHERE job_id = ? AND node_id = ?
                """,
                (
                    status,
                    json.dumps(payload, ensure_ascii=False, default=str),
                    now,
                    job_id,
                    node_id,
                ),
            )
            c.execute(
                "UPDATE production_graphs SET updated_at = ? WHERE job_id = ?",
                (now, job_id),
            )
    return True


def record_task_result(
    *,
    job_id: str,
    node_id: str,
    outcome: str,
    payload_patch: Optional[dict[str, Any]] = None,
    lease_id: Optional[str] = None,
    worker_id: Optional[str] = None,
) -> dict[str, Any]:
    """Finalize one leased graph task and return the next execution batch.

    Queue workers need a single, safe write path after a render/QA/assembly
    handler finishes. This validates the lease when present, maps task outcome
    to the correct node status, clears active lease metadata, and exposes the
    next dependency-safe batch so the caller can continue without re-planning.
    """
    normalized_outcome = _normalize_task_outcome(outcome)
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        with _conn() as c:
            row = c.execute(
                """
                SELECT node_id, kind, status, payload
                  FROM production_graph_nodes
                 WHERE job_id = ? AND node_id = ?
                """,
                (job_id, node_id),
            ).fetchone()
            if not row:
                return {
                    "schema_version": "cinejelly.graph_task_result.v1",
                    "job_id": job_id,
                    "node_id": node_id,
                    "recorded": False,
                    "reason": "node_not_found",
                }

            payload = json.loads(row["payload"] or "{}")
            current_lease_id = payload.get("lease_id")
            current_worker_id = payload.get("lease_worker_id")
            if row["status"] == "leased":
                if lease_id and current_lease_id and lease_id != current_lease_id:
                    raise ValueError(
                        f"lease mismatch for {node_id}: expected {current_lease_id}, got {lease_id}"
                    )
                if worker_id and current_worker_id and worker_id != current_worker_id:
                    raise ValueError(
                        f"worker mismatch for {node_id}: expected {current_worker_id}, got {worker_id}"
                    )

            next_status = _status_for_task_result(
                kind=row["kind"],
                outcome=normalized_outcome,
                requested_status=(payload_patch or {}).get("status"),
            )
            payload.update(payload_patch or {})
            payload.update({
                "task_outcome": normalized_outcome,
                "task_completed_at": now,
                "last_lease_id": current_lease_id or lease_id,
                "last_worker_id": current_worker_id or worker_id,
            })
            for key in (
                "lease_id",
                "lease_worker_id",
                "lease_action",
                "lease_claimed_at",
                "lease_ttl_s",
                "lease_previous_status",
            ):
                payload.pop(key, None)

            c.execute(
                """
                UPDATE production_graph_nodes
                   SET status = ?, payload = ?, updated_at = ?
                 WHERE job_id = ? AND node_id = ?
                """,
                (
                    next_status,
                    json.dumps(payload, ensure_ascii=False, default=str),
                    now,
                    job_id,
                    node_id,
                ),
            )
            c.execute(
                "UPDATE production_graphs SET updated_at = ? WHERE job_id = ?",
                (now, job_id),
            )

    graph = load_graph(job_id) or {}
    return {
        "schema_version": "cinejelly.graph_task_result.v1",
        "job_id": job_id,
        "node_id": node_id,
        "recorded": True,
        "outcome": normalized_outcome,
        "status": next_status,
        "next_batch": build_execution_batch(graph) if graph else None,
        "resume_plan": build_resume_plan(graph) if graph else None,
    }


def delete_graph(job_id: str) -> bool:
    """Delete a graph and its node/edge rows. Intended for tests/admin cleanup."""
    with _LOCK:
        with _conn() as c:
            c.execute("DELETE FROM production_graph_nodes WHERE job_id = ?", (job_id,))
            c.execute("DELETE FROM production_graph_edges WHERE job_id = ?", (job_id,))
            cur = c.execute("DELETE FROM production_graphs WHERE job_id = ?", (job_id,))
            return cur.rowcount > 0


_DONE_STATUSES = {"planned", "rendered", "passed", "warn", "completed", "accepted"}
_FAILED_STATUSES = {"failed", "retry_failed"}
_RUNNING_STATUSES = {"leased", "rendering", "retrying", "assembling", "uploading"}
_PENDING_STATUSES = {"pending", "pending_render", "queued"}


def _pending_shot_actions(
    nodes: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    shots = [
        n for n in nodes
        if str(n.get("kind") or "") == "shot"
        and _node_status(n) in (_PENDING_STATUSES | _FAILED_STATUSES)
    ]
    shots.sort(key=lambda n: (
        float((n.get("payload") or {}).get("start_s") or 0),
        str(n.get("id") or ""),
    ))
    out: list[dict[str, Any]] = []
    for node in shots:
        payload = node.get("payload") or {}
        previous_shot_id = payload.get("previous_shot_id")
        blocked_by: list[str] = []
        if previous_shot_id:
            prev_node = by_id.get(f"shot_{previous_shot_id}")
            if not prev_node or _node_status(prev_node) not in {"rendered", "accepted"}:
                blocked_by.append(f"shot_{previous_shot_id}")
        status = _node_status(node)
        out.append({
            **_node_summary(node),
            "shot_id": payload.get("shot_id"),
            "start_s": payload.get("start_s"),
            "end_s": payload.get("end_s"),
            "duration_s": payload.get("duration_s"),
            "previous_shot_id": previous_shot_id,
            "blocked_by": blocked_by,
            "action": (
                "repair_failed_shot" if status in _FAILED_STATUSES
                else "wait_for_dependency" if blocked_by
                else "render_next_shot"
            ),
        })
    return out


def _execution_response(
    graph_record: dict[str, Any],
    *,
    mode: str,
    reason: str,
    tasks: list[dict[str, Any]],
    resume_plan: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "cinejelly.graph_execution_batch.v1",
        "job_id": graph_record.get("job_id"),
        "plan_id": graph_record.get("plan_id"),
        "graph_id": graph_record.get("graph_id"),
        "runtime_class": graph_record.get("runtime_class"),
        "duration_s": graph_record.get("duration_s"),
        "mode": mode,
        "reason": reason,
        "ready_count": len(tasks),
        "tasks": tasks,
        "resume_plan": resume_plan,
        "executor_policy": {
            "preserve": ["screenplay", "production_bible", "reference_roles", "completed_shots"],
            "max_parallelism": "bounded by caller limit and dependency readiness",
            "dependency_rule": "a chained shot cannot run until previous_shot_id is rendered or accepted",
        },
    }


def _task_for_shot(
    node: dict[str, Any],
    *,
    action: str,
    priority: str,
    by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    payload = node.get("payload") or {}
    previous_shot_id = payload.get("previous_shot_id")
    blocked_by = _blocked_by_previous_shot(node, by_id)
    return {
        "node_id": node.get("id"),
        "kind": "shot",
        "action": action,
        "priority": priority,
        "shot_id": payload.get("shot_id"),
        "start_s": payload.get("start_s"),
        "end_s": payload.get("end_s"),
        "duration_s": payload.get("duration_s"),
        "previous_shot_id": previous_shot_id,
        "blocked_by": blocked_by,
        "payload": {
            key: payload.get(key)
            for key in ("shot_id", "purpose", "start_s", "end_s", "duration_s", "previous_shot_id")
            if key in payload
        },
    }


def _blocked_by_previous_shot(
    node: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
) -> list[str]:
    payload = node.get("payload") or {}
    previous_shot_id = payload.get("previous_shot_id")
    if not previous_shot_id:
        return []
    prev_id = f"shot_{previous_shot_id}"
    prev_node = by_id.get(prev_id)
    if prev_node and _node_status(prev_node) in {"rendered", "accepted"}:
        return []
    return [prev_id]


def _ready_qa_tasks(
    nodes: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for node in sorted(nodes, key=lambda n: str(n.get("id") or "")):
        if str(node.get("kind") or "") != "qa" or _node_status(node) not in _PENDING_STATUSES:
            continue
        payload = node.get("payload") or {}
        shot_id = payload.get("shot_id")
        shot_node = by_id.get(f"shot_{shot_id}")
        if not shot_node or _node_status(shot_node) not in {"rendered", "accepted"}:
            continue
        tasks.append({
            "node_id": node.get("id"),
            "kind": "qa",
            "action": "run_qa",
            "priority": "normal",
            "shot_id": shot_id,
            "blocked_by": [],
            "payload": payload,
        })
        if len(tasks) >= limit:
            break
    return tasks


def _all_qa_done(nodes: list[dict[str, Any]]) -> bool:
    qa_nodes = [n for n in nodes if str(n.get("kind") or "") == "qa"]
    return bool(qa_nodes) and all(
        _node_status(n) in {"passed", "warn", "accepted", "completed"}
        for n in qa_nodes
    )


def _shot_sort_key(node: dict[str, Any]) -> tuple[float, str]:
    payload = node.get("payload") or {}
    return (
        float(payload.get("start_s") or 0),
        str(node.get("id") or ""),
    )


def _node_status(node: Optional[dict[str, Any]]) -> str:
    if not node:
        return "missing"
    return str(node.get("status") or "unknown")


def _node_summary(node: dict[str, Any]) -> dict[str, Any]:
    payload = node.get("payload") or {}
    return {
        "id": node.get("id"),
        "kind": node.get("kind"),
        "status": node.get("status"),
        "updated_at": node.get("updated_at"),
        "payload": {
            key: payload.get(key)
            for key in (
                "shot_id",
                "purpose",
                "start_s",
                "end_s",
                "duration_s",
                "model_key",
                "render_mode",
                "quality_status",
                "retry_error",
            )
            if key in payload
        },
    }


def _lease_is_expired(payload: dict[str, Any], now: datetime) -> bool:
    claimed_at_raw = payload.get("lease_claimed_at")
    ttl_s = int(payload.get("lease_ttl_s") or 900)
    if not claimed_at_raw:
        return True
    try:
        claimed_at = datetime.fromisoformat(str(claimed_at_raw).replace("Z", "+00:00"))
        if claimed_at.tzinfo is None:
            claimed_at = claimed_at.replace(tzinfo=timezone.utc)
    except Exception:
        return True
    return (now - claimed_at).total_seconds() > max(30, ttl_s)


def _fallback_status_for_kind(kind: str) -> str:
    if kind == "shot":
        return "pending_render"
    if kind == "qa":
        return "pending"
    if kind == "assembly":
        return "pending"
    return "pending"


def _normalize_task_outcome(outcome: str) -> str:
    out = (outcome or "").strip().lower()
    allowed = {"success", "passed", "warn", "accepted", "failed", "retry_failed", "completed"}
    if out not in allowed:
        raise ValueError(f"invalid graph task outcome: {outcome}")
    return out


def _status_for_task_result(
    *,
    kind: str,
    outcome: str,
    requested_status: Optional[str] = None,
) -> str:
    if requested_status:
        return str(requested_status)
    if outcome in {"failed", "retry_failed"}:
        return outcome
    if kind == "shot":
        return "rendered" if outcome in {"success", "passed", "completed"} else outcome
    if kind == "qa":
        if outcome == "success":
            return "passed"
        return outcome
    if kind == "assembly":
        return "completed" if outcome in {"success", "passed"} else outcome
    return "completed" if outcome in {"success", "passed"} else outcome


__all__ = [
    "save_graph",
    "load_graph",
    "build_resume_plan",
    "build_execution_batch",
    "claim_execution_batch",
    "release_expired_leases",
    "update_node_status",
    "record_task_result",
    "delete_graph",
]
