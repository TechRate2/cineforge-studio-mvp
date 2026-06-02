"""Cross-shot diagnostics for autonomous multi-shot video plans.

Single-shot lint can prove each Seedance call is renderable, but it cannot prove
the assembled video will feel like one coherent film. This module scores the
between-shot layer: transitions, subject persistence, edit rhythm, and final
payoff. It is deterministic and pre-render, so it can run before paid vendor
work.
"""
from __future__ import annotations

from typing import Any

from agent.schemas import DirectorPlan, Shot


_PAYOFF_WORDS = {"payoff", "proof", "result", "reveal", "verdict", "close", "cta", "takeaway", "aftermath"}
_HOOK_WORDS = {"hook", "open", "cold", "result", "surprise", "question", "mistake", "reveal", "test", "proof"}
_TRANSITION_WORDS = {"transition", "cutaway", "establish", "location", "time", "chapter", "scene"}


def diagnose_cross_shot_coherence(*, plan: DirectorPlan) -> dict[str, Any]:
    """Return a DirectorBench/MSVBench-style diagnostic for shot-to-shot flow."""
    shots = sorted(plan.shot_list or [], key=lambda s: (s.index, s.start_s))
    duration_s = int(plan.continuity_bible.duration_s or sum(int(s.duration_s) for s in shots))
    runtime = (plan.continuity_bible.storytelling_meta or {}).get("runtime_structure") or {}
    runtime_class = str(runtime.get("runtime_class") or "")
    dimensions = [
        _transition_dimension(shots=shots, duration_s=duration_s, runtime_class=runtime_class),
        _subject_persistence_dimension(shots),
        _edit_rhythm_dimension(shots),
        _narrative_progression_dimension(shots=shots, duration_s=duration_s, runtime=runtime),
    ]
    score = round(sum(float(d["score"]) for d in dimensions) / max(1, len(dimensions)), 1)
    failed = [d for d in dimensions if d["status"] == "fail"]
    warned = [d for d in dimensions if d["status"] == "warn"]
    status = "fail" if failed or score < 62 else ("warn" if warned or score < 78 else "pass")
    top_issues = [issue for d in dimensions for issue in d.get("issues", [])][:8]
    return {
        "schema_version": "cinejelly.cross_shot_diagnostic.v1",
        "status": status,
        "score": score,
        "shot_count": len(shots),
        "duration_s": duration_s,
        "runtime_class": runtime_class or "unknown",
        "dimensions": dimensions,
        "top_issues": top_issues,
        "repair_hint": _repair_hint(top_issues),
    }


def _transition_dimension(*, shots: list[Shot], duration_s: int, runtime_class: str) -> dict[str, Any]:
    if len(shots) <= 1:
        return _dimension("transition_continuity", "warn", 72, ["single_shot_no_transition_diagnostics"], "Only one shot exists.")
    issues: list[str] = []
    required = 0
    missing = 0
    for prev, cur in zip(shots, shots[1:]):
        shared_identity = bool(
            set(prev.continuity.character_ids or []) & set(cur.continuity.character_ids or [])
            or set(prev.continuity.product_ids or []) & set(cur.continuity.product_ids or [])
            or set(prev.continuity.reference_indices or []) & set(cur.continuity.reference_indices or [])
        )
        intentional_cut = _contains_any(_shot_text(cur), _TRANSITION_WORDS) or _contains_any(_shot_text(prev), _TRANSITION_WORDS)
        if shared_identity and not intentional_cut:
            required += 1
            if cur.continuity.previous_shot_id != prev.shot_id:
                missing += 1
    if missing:
        issues.append(f"missing_adjacent_handoff:{missing}/{required}")
    if duration_s > 180 and required == 0:
        issues.append("long_form_has_no_required_transition_anchors")
    score = 100 - 22 * missing - (16 if "long_form_has_no_required_transition_anchors" in issues else 0)
    return _dimension(
        "transition_continuity",
        _status(score, fail_below=58 if duration_s > 180 or runtime_class in {"short_film", "episode"} else 45),
        score,
        issues,
        "Adjacent shots that share characters/products/references need explicit handoffs unless they are intentional cuts.",
    )


def _subject_persistence_dimension(shots: list[Shot]) -> dict[str, Any]:
    issues: list[str] = []
    char_shots = [s for s in shots if s.continuity.character_ids]
    product_shots = [s for s in shots if s.continuity.product_ids]
    if len(char_shots) >= 2:
        no_refs = [s.shot_id for s in char_shots if not s.continuity.reference_indices]
        if no_refs:
            issues.append(f"character_shots_without_reference_indices:{len(no_refs)}")
    if len(product_shots) >= 2:
        no_refs = [s.shot_id for s in product_shots if not s.continuity.reference_indices]
        if no_refs:
            issues.append(f"product_shots_without_reference_indices:{len(no_refs)}")
    if len(shots) >= 4 and not (char_shots or product_shots):
        issues.append("multi_shot_plan_has_no_subject_or_product_persistence")
    score = 100 - 20 * len(issues)
    return _dimension(
        "subject_persistence",
        _status(score, fail_below=55),
        score,
        issues,
        "Repeated characters/products should carry reference indices across their shots.",
    )


def _edit_rhythm_dimension(shots: list[Shot]) -> dict[str, Any]:
    issues: list[str] = []
    if len(shots) < 3:
        return _dimension("edit_rhythm", "pass", 86, [], "Short shot list has limited rhythm risk.")
    repeated_camera_runs = 0
    current_run = 1
    previous_key = None
    for shot in shots:
        key = (_norm(shot.visual.camera_shot), _norm(shot.visual.camera_movement))
        if key == previous_key:
            current_run += 1
            if current_run >= 3:
                repeated_camera_runs += 1
        else:
            current_run = 1
        previous_key = key
    if repeated_camera_runs:
        issues.append(f"repeated_camera_language_run:{repeated_camera_runs}")
    durations = [float(s.duration_s or 0) for s in shots]
    if len(durations) >= 5 and max(durations) - min(durations) < 2:
        issues.append("all_shots_same_duration_rhythm_may_feel_mechanical")
    if any(d > 15 for d in durations):
        issues.append("shot_exceeds_seedance_duration_cap")
    score = 100 - 18 * len(issues)
    return _dimension("edit_rhythm", _status(score, fail_below=58), score, issues, "Shot size, movement, and duration should create a motivated edit rhythm.")


def _narrative_progression_dimension(*, shots: list[Shot], duration_s: int, runtime: dict[str, Any]) -> dict[str, Any]:
    if not shots:
        return _dimension("narrative_progression", "fail", 0, ["missing_shots"], "No shots exist.")
    issues: list[str] = []
    purposes = [_norm(s.purpose) for s in shots]
    first_text = _shot_text(shots[0])
    final_text = _shot_text(shots[-1])
    if "hook" not in purposes[0] and not _contains_any(first_text, _HOOK_WORDS):
        issues.append("first_shot_not_hook_or_opening")
    if not _contains_any(final_text, _PAYOFF_WORDS) and not _contains_any(purposes[-1], _PAYOFF_WORDS):
        issues.append("final_shot_not_payoff_or_takeaway")
    if len(shots) >= 4 and len(set(purposes)) < 3:
        issues.append("shot_purpose_progression_too_flat")
    if duration_s > 180:
        scene_count = int(runtime.get("scene_count") or len(runtime.get("scene_blueprints") or []))
        if scene_count < 3:
            issues.append("long_form_needs_at_least_three_scene_beats")
    score = 100 - 20 * len(issues)
    return _dimension("narrative_progression", _status(score, fail_below=58), score, issues, "A coherent video needs hook, changing middle beats, and payoff.")


def _dimension(name: str, status: str, score: float, issues: list[str], detail: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "score": max(0, round(float(score), 1)),
        "issues": issues,
        "detail": detail,
    }


def _status(score: float, *, fail_below: float) -> str:
    if score < fail_below:
        return "fail"
    if score < 82:
        return "warn"
    return "pass"


def _repair_hint(issues: list[str]) -> str:
    if not issues:
        return "cross_shot_flow_ready"
    first = issues[0]
    if "handoff" in first or "transition" in first:
        return "add_previous_shot_id_or_explicit_transition_cut_between_shared_subject_shots"
    if "reference" in first or "persistence" in first:
        return "bind_character_product_reference_indices_across_repeated_subject_shots"
    if "camera" in first or "rhythm" in first:
        return "vary_camera_size_movement_and_duration_to_create_edit_rhythm"
    if "payoff" in first or "progression" in first:
        return "rewrite_purpose_flow_as_hook_setup_escalation_payoff"
    return "tighten_cross_shot_continuity_rhythm_and_story_progression"


def _shot_text(shot: Shot) -> str:
    return " ".join([
        shot.shot_id or "",
        shot.purpose or "",
        shot.emotion_beat or "",
        shot.visual.subject or "",
        shot.visual.action or "",
        shot.visual.camera_shot or "",
        shot.visual.camera_movement or "",
        shot.visual.composition or "",
        shot.visual.background or "",
        shot.dynamic_description or "",
        shot.continuity.previous_shot_id or "",
    ]).lower()


def _contains_any(text: str, needles: set[str]) -> bool:
    normalized = _norm(text)
    return any(needle in normalized for needle in needles)


def _norm(value: str) -> str:
    return (value or "").strip().lower().replace(" ", "_").replace("-", "_")


__all__ = ["diagnose_cross_shot_coherence"]
