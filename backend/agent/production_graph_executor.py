"""Dependency-safe production graph executor primitive.

The graph store can persist, lease, and acknowledge tasks. This module adds the
orchestration loop that a real background worker can use: claim ready tasks,
dispatch them to injected handlers, record each result, and return the next
batch. The default HTTP usage is preview-only so an API call never starts paid
vendor renders by accident.
"""
from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from core import production_graph_store


GraphTaskHandler = Callable[[dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]]


async def run_graph_executor_once(
    *,
    job_id: str,
    worker_id: str = "autonomous_graph_executor",
    limit: int = 1,
    lease_ttl_s: int = 900,
    handlers: Optional[dict[str, GraphTaskHandler]] = None,
    preview: bool = True,
) -> dict[str, Any]:
    """Run one dependency-safe graph executor cycle.

    `handlers` can be keyed by task action (`render_shot`, `run_qa`,
    `assemble_final`) or node kind (`shot`, `qa`, `assembly`). Each handler
    returns `{outcome, payload_patch}`. Outcomes are normalized by
    `production_graph_store.record_task_result`.
    """
    graph = production_graph_store.load_graph(job_id)
    if not graph:
        return {
            "schema_version": "cinejelly.graph_executor.v1",
            "job_id": job_id,
            "ok": False,
            "reason": "graph_not_found",
        }

    if preview:
        return {
            "schema_version": "cinejelly.graph_executor.v1",
            "job_id": job_id,
            "ok": True,
            "mode": "preview",
            "execution_batch": production_graph_store.build_execution_batch(graph, limit=limit),
            "resume_plan": production_graph_store.build_resume_plan(graph),
        }

    claim = production_graph_store.claim_execution_batch(
        job_id=job_id,
        worker_id=worker_id,
        limit=limit,
        lease_ttl_s=lease_ttl_s,
    )
    if not claim or not claim.get("claimed"):
        return {
            "schema_version": "cinejelly.graph_executor.v1",
            "job_id": job_id,
            "ok": True,
            "mode": "idle",
            "claim": claim,
        }

    results: list[dict[str, Any]] = []
    active_handlers = handlers or {}
    for task in claim.get("tasks") or []:
        handler = _handler_for_task(task, active_handlers)
        if not handler:
            result = production_graph_store.record_task_result(
                job_id=job_id,
                node_id=str(task.get("node_id") or ""),
                outcome="failed",
                lease_id=task.get("lease_id"),
                worker_id=worker_id,
                payload_patch={
                    "executor_status": "handler_missing",
                    "executor_error": f"missing handler for action={task.get('action')} kind={task.get('kind')}",
                },
            )
            results.append({"task": task, "handler": "missing", "result": result})
            continue

        try:
            handler_out = handler(task)
            if inspect.isawaitable(handler_out):
                handler_out = await handler_out
            outcome = str((handler_out or {}).get("outcome") or "success")
            payload_patch = dict((handler_out or {}).get("payload_patch") or {})
        except Exception as exc:
            outcome = "failed"
            payload_patch = {
                "executor_status": "handler_exception",
                "executor_error": str(exc)[:1000],
            }

        result = production_graph_store.record_task_result(
            job_id=job_id,
            node_id=str(task.get("node_id") or ""),
            outcome=outcome,
            lease_id=task.get("lease_id"),
            worker_id=worker_id,
            payload_patch=payload_patch,
        )
        results.append({
            "task": task,
            "handler": getattr(handler, "__name__", "handler"),
            "result": result,
        })

    graph_after = production_graph_store.load_graph(job_id) or {}
    return {
        "schema_version": "cinejelly.graph_executor.v1",
        "job_id": job_id,
        "ok": True,
        "mode": "executed",
        "claim": claim,
        "results": results,
        "next_batch": (
            production_graph_store.build_execution_batch(graph_after, limit=limit)
            if graph_after else None
        ),
        "resume_plan": (
            production_graph_store.build_resume_plan(graph_after)
            if graph_after else None
        ),
    }


async def run_graph_executor_until_idle(
    *,
    job_id: str,
    worker_id: str = "autonomous_graph_executor",
    limit: int = 1,
    lease_ttl_s: int = 900,
    handlers: Optional[dict[str, GraphTaskHandler]] = None,
    max_cycles: int = 100,
) -> dict[str, Any]:
    """Advance a graph repeatedly until idle/noop/blocked or `max_cycles`.

    This is the background-loop primitive. It remains handler-injected so the
    caller controls whether the loop uses paid vendor render handlers, metadata
    stubs, or test doubles.
    """
    cycles: list[dict[str, Any]] = []
    for _ in range(max(1, min(int(max_cycles or 100), 1000))):
        result = await run_graph_executor_once(
            job_id=job_id,
            worker_id=worker_id,
            limit=limit,
            lease_ttl_s=lease_ttl_s,
            handlers=handlers,
            preview=False,
        )
        cycles.append(result)
        if not result.get("ok"):
            break
        if result.get("mode") == "idle":
            break
        next_batch = result.get("next_batch") or {}
        if next_batch.get("mode") in {"noop", "wait"} or not next_batch.get("tasks"):
            break

    graph = production_graph_store.load_graph(job_id)
    resume_plan = production_graph_store.build_resume_plan(graph) if graph else None
    final_batch = production_graph_store.build_execution_batch(graph) if graph else None
    return {
        "schema_version": "cinejelly.graph_executor_loop.v1",
        "job_id": job_id,
        "ok": bool(graph),
        "cycle_count": len(cycles),
        "cycles": cycles,
        "final_batch": final_batch,
        "resume_plan": resume_plan,
        "completed": bool(final_batch and final_batch.get("mode") == "noop"),
    }


def metadata_stub_handlers() -> dict[str, GraphTaskHandler]:
    """Return metadata-only handlers for local executor smoke tests only.

    These handlers advance graph state for dependency smoke tests, but never
    write synthetic output URLs, QA passes, render URLs, or delivery evidence.
    """
    def _shot(task: dict[str, Any]) -> dict[str, Any]:
        return {
            "outcome": "accepted",
            "payload_patch": {
                "executor_status": "metadata_stub",
                "metadata_only": True,
                "real_render_required": True,
            },
        }

    def _qa(task: dict[str, Any]) -> dict[str, Any]:
        return {
            "outcome": "accepted",
            "payload_patch": {
                "executor_status": "metadata_stub",
                "metadata_only": True,
                "quality_status": "metadata_only_no_real_qa",
                "real_qa_required": True,
            },
        }

    def _assembly(task: dict[str, Any]) -> dict[str, Any]:
        return {
            "outcome": "accepted",
            "payload_patch": {
                "executor_status": "metadata_stub",
                "metadata_only": True,
                "real_delivery_required": True,
            },
        }

    return {
        "render_shot": _shot,
        "retry_shot": _shot,
        "run_qa": _qa,
        "assemble_final": _assembly,
    }


def _handler_for_task(
    task: dict[str, Any],
    handlers: dict[str, GraphTaskHandler],
) -> Optional[GraphTaskHandler]:
    action = str(task.get("action") or "")
    kind = str(task.get("kind") or "")
    return handlers.get(action) or handlers.get(kind)


__all__ = [
    "GraphTaskHandler",
    "metadata_stub_handlers",
    "run_graph_executor_once",
    "run_graph_executor_until_idle",
]
