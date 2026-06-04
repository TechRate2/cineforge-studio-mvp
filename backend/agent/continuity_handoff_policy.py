"""Continuity handoff policy for autonomous long-form video.

Seedance 2.0 works best when a long video is rendered as 4-15 second units
with explicit continuity handoffs. This module makes that contract observable:
which adjacent shots should chain from the previous last frame, which shots are
intentional cuts, and which required handoffs are missing.
"""
from __future__ import annotations

from typing import Any

from agent.schemas import Shot


_CUT_PURPOSES = {"transition", "scene_break", "chapter_break", "montage_reset", "new_location"}
_OPEN_PURPOSES = {"hook", "cold_open", "establishing", "intro"}
_CLOSE_PURPOSES = {"cta", "outro", "closing", "payoff"}


def apply_continuity_handoffs(
    shots: list[Shot],
    *,
    duration_s: int,
    runtime_class: str = "",
) -> dict[str, Any]:
    """Fill missing previous-shot chains when continuity is required.

    The function mutates `shots` intentionally, because the render worker reads
    `shot.continuity.previous_shot_id` to decide whether to use the previous
    last frame as an i2v anchor.
    """
    for item in _handoff_rows(shots, duration_s=duration_s, runtime_class=runtime_class):
        if item["required"] and item["status"] == "missing":
            shot = item["_shot"]
            shot.continuity.previous_shot_id = item["expected_previous_shot_id"]
    return build_continuity_handoff_policy(
        shots,
        duration_s=duration_s,
        runtime_class=runtime_class,
    )


def build_continuity_handoff_policy(
    shots: list[Shot],
    *,
    duration_s: int,
    runtime_class: str = "",
) -> dict[str, Any]:
    """Return an auditable continuity handoff policy for a shot list."""
    rows = _handoff_rows(shots, duration_s=duration_s, runtime_class=runtime_class)
    public_rows = [{k: v for k, v in row.items() if k != "_shot"} for row in rows]
    required = [row for row in public_rows if row["required"]]
    missing = [row for row in required if row["status"] == "missing"]
    active = [row for row in required if row["status"] == "chained"]
    intentional_cuts = [row for row in public_rows if row["status"] == "intentional_cut"]
    score = 1.0 if not required else max(0.0, round(len(active) / len(required), 3))
    return {
        "schema_version": "cinejelly.continuity_handoff_policy.v1",
        "duration_s": int(duration_s or 0),
        "runtime_class": runtime_class or _runtime_class(duration_s),
        "shot_count": len(shots),
        "required_handoffs": len(required),
        "active_handoffs": len(active),
        "missing_required_handoffs": len(missing),
        "intentional_cuts": len(intentional_cuts),
        "score": score,
        "handoffs": public_rows,
        "summary": _summary(required=len(required), active=len(active), missing=len(missing), intentional=len(intentional_cuts)),
    }


def _handoff_rows(shots: list[Shot], *, duration_s: int, runtime_class: str) -> list[dict[str, Any]]:
    ordered = sorted(shots, key=lambda s: int(getattr(s, "index", 0) or 0))
    rows: list[dict[str, Any]] = []
    for i in range(1, len(ordered)):
        prev = ordered[i - 1]
        cur = ordered[i]
        expected = prev.shot_id
        current = cur.continuity.previous_shot_id
        reason = _reason(prev, cur, duration_s=duration_s, runtime_class=runtime_class)
        required = reason["required"]
        if reason["intentional_cut"]:
            status = "intentional_cut"
        elif required and current == expected:
            status = "chained"
        elif required and current:
            status = "chained_non_adjacent"
        elif required:
            status = "missing"
        else:
            status = "not_required"
        rows.append({
            "_shot": cur,
            "shot_id": cur.shot_id,
            "expected_previous_shot_id": expected if required else None,
            "current_previous_shot_id": current,
            "required": required,
            "status": status,
            "reason": reason["reason"],
            "shared_character_ids": sorted(reason["shared_character_ids"]),
            "shared_product_ids": sorted(reason["shared_product_ids"]),
            "shared_reference_indices": sorted(reason["shared_reference_indices"]),
        })
    return rows


def _reason(prev: Shot, cur: Shot, *, duration_s: int, runtime_class: str) -> dict[str, Any]:
    prev_purpose = _norm(prev.purpose)
    cur_purpose = _norm(cur.purpose)
    intentional_cut = (
        prev_purpose in _CUT_PURPOSES
        or cur_purpose in _CUT_PURPOSES
        or (prev_purpose in _CLOSE_PURPOSES and cur_purpose in _OPEN_PURPOSES)
    )
    shared_chars = set(prev.continuity.character_ids) & set(cur.continuity.character_ids)
    shared_products = set(prev.continuity.product_ids) & set(cur.continuity.product_ids)
    shared_refs = set(prev.continuity.reference_indices) & set(cur.continuity.reference_indices)
    long_form = int(duration_s or 0) > 60 or runtime_class in {"micro_film", "short_film", "episode"}
    same_anchor = bool(shared_chars or shared_products or shared_refs)
    adjacent_story = (
        prev_purpose not in _CLOSE_PURPOSES
        and cur_purpose not in _OPEN_PURPOSES
        and cur_purpose not in _CUT_PURPOSES
    )
    required = bool(not intentional_cut and same_anchor and (long_form or adjacent_story))
    reason = "not_needed"
    if intentional_cut:
        reason = "purpose_marks_scene_or_story_cut"
    elif shared_chars:
        reason = "same_character_identity_should_continue"
    elif shared_products:
        reason = "same_product_geometry_should_continue"
    elif shared_refs:
        reason = "same_reference_anchor_should_continue"
    elif long_form and adjacent_story:
        reason = "long_form_adjacent_story_cut_without_shared_anchor"
    return {
        "required": required,
        "intentional_cut": intentional_cut,
        "reason": reason,
        "shared_character_ids": shared_chars,
        "shared_product_ids": shared_products,
        "shared_reference_indices": shared_refs,
    }


def _runtime_class(duration_s: int) -> str:
    duration = int(duration_s or 0)
    if duration <= 30:
        return "short"
    if duration <= 60:
        return "sequence"
    if duration <= 180:
        return "micro_film"
    if duration <= 600:
        return "short_film"
    return "episode"


def _summary(*, required: int, active: int, missing: int, intentional: int) -> str:
    if missing:
        return f"{missing}/{required} required continuity handoff(s) missing; review long-form chaining before render."
    if required:
        return f"{active}/{required} required continuity handoff(s) active; {intentional} intentional cut(s)."
    return f"No required continuity handoffs; {intentional} intentional cut(s)."


def _norm(value: str) -> str:
    return (value or "").strip().lower().replace(" ", "_")


__all__ = ["apply_continuity_handoffs", "build_continuity_handoff_policy"]
