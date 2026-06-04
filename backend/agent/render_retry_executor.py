"""Safe execution contract for render retry plans.

This module decides which retry items can be auto-executed in the current linear
worker. It intentionally avoids unsafe retries that would invalidate downstream
reference-chain continuity, and defers single-call/full-clip retries until the
future graph executor can replace chunks atomically.
"""
from __future__ import annotations

from typing import Any


def prepare_retry_execution(
    *,
    retry_plan: dict[str, Any],
    shots: list[Any],
) -> dict[str, Any]:
    items = list(retry_plan.get("items") or [])
    shot_ids = {str(getattr(s, "shot_id", "")) for s in shots}
    depended_on = {
        str(getattr(getattr(s, "continuity", None), "previous_shot_id", ""))
        for s in shots
        if getattr(getattr(s, "continuity", None), "previous_shot_id", None)
    }

    executable: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []

    for idx, item in enumerate(items):
        shot_id = str(item.get("shot_id") or "")
        candidate = {**item, "item_index": idx}
        if shot_id in {"", "ALL"} or item.get("scope") == "full_clip":
            deferred.append({**candidate, "defer_reason": "full_clip_or_single_call_retry_requires_chunk_graph"})
            continue
        if shot_id not in shot_ids:
            deferred.append({**candidate, "defer_reason": "shot_not_found_in_plan"})
            continue
        if shot_id in depended_on:
            deferred.append({**candidate, "defer_reason": "shot_is_chain_anchor_for_later_shots"})
            continue
        if int(item.get("attempts_done") or 0) >= int(item.get("max_retries") or 1):
            deferred.append({**candidate, "defer_reason": "max_retries_reached"})
            continue
        executable.append(candidate)

    return {
        "enabled": bool(executable),
        "executor_status": "ready" if executable else ("deferred" if deferred else "no_retries"),
        "executable_items": executable,
        "deferred_items": deferred,
        "summary": {
            "executable_count": len(executable),
            "deferred_count": len(deferred),
            "total_items": len(items),
        },
    }


__all__ = ["prepare_retry_execution"]
