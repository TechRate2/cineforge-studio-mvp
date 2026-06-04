"""Long-form screenplay and scene continuity linting.

Shot lint protects individual 4-15s Seedance calls. This module protects the
layer above it: for 3m-30m videos, every scene needs purpose, conflict/stakes,
turning point, continuity anchor, and a handoff image. Without those fields,
the final video may render valid clips that still feel like unrelated shorts.
"""
from __future__ import annotations

from typing import Any


_GENERIC_VALUES = {
    "",
    "n/a",
    "none",
    "tbd",
    "scene",
    "setup",
    "continue",
    "continuity",
    "good scene",
    "nice moment",
    "visual hook",
}


def lint_screenplay_scene_structure(
    *,
    duration_s: int,
    runtime_structure: dict[str, Any],
) -> dict[str, Any]:
    """Return pass/warn/fail diagnostics for long-form scene structure."""
    runtime_class = str(runtime_structure.get("runtime_class") or "")
    is_long_form = int(duration_s or 0) > 180 or runtime_class in {"short_film", "episode"}
    scene_blueprints = _as_list(runtime_structure.get("scene_blueprints"))
    screenplay_plan = runtime_structure.get("screenplay_plan") if isinstance(runtime_structure.get("screenplay_plan"), dict) else {}
    scene_scripts = _as_list(screenplay_plan.get("scene_scripts"))

    checks: list[dict[str, Any]] = []
    hard_failures: list[str] = []
    warnings: list[str] = []
    score = 100.0

    def add(name: str, status: str, detail: str, *, penalty: float = 0.0) -> None:
        nonlocal score
        checks.append({"name": name, "status": status, "detail": detail})
        if status == "fail":
            hard_failures.append(name)
        elif status == "warn":
            warnings.append(name)
        score = max(0.0, score - penalty)

    if not is_long_form:
        add("screenplay_scene_lint_scope", "pass", "Short-form job does not require screenplay scene lint.")
        return _result("pass", score, hard_failures, warnings, checks, [], [])

    if not runtime_structure:
        add("runtime_structure", "fail", "Long-form job has no runtime structure.", penalty=40)
        return _result("fail", score, hard_failures, warnings, checks, [], [])

    _check_scene_blueprints(add, scene_blueprints)
    _check_screenplay_plan(add, screenplay_plan, scene_blueprints, scene_scripts)
    scene_reports = _scene_reports(scene_blueprints, scene_scripts)
    for report in scene_reports:
        if report["status"] == "fail":
            hard_failures.append(f"scene:{report['scene_id']}")
            score = max(0.0, score - 10)
        elif report["status"] == "warn":
            warnings.append(f"scene:{report['scene_id']}")
            score = max(0.0, score - 4)

    status = "fail" if hard_failures else ("warn" if warnings else "pass")
    return _result(status, score, hard_failures, warnings, checks, scene_reports, _top_scene_issues(scene_reports))


def _check_scene_blueprints(add: Any, scenes: list[dict[str, Any]]) -> None:
    if not scenes:
        add("scene_blueprints", "fail", "Long-form job is missing scene blueprints.", penalty=35)
        return
    if len(scenes) < 3:
        add("scene_blueprints", "warn", "Long-form job has fewer than 3 scenes; pacing may feel underdeveloped.", penalty=8)
    else:
        add("scene_blueprints", "pass", f"{len(scenes)} scene blueprints are present.")


def _check_screenplay_plan(
    add: Any,
    screenplay: dict[str, Any],
    scenes: list[dict[str, Any]],
    scripts: list[dict[str, Any]],
) -> None:
    if not screenplay:
        add("screenplay_plan", "fail", "Long-form job is missing screenplay_plan.", penalty=35)
        return
    if not _useful(screenplay.get("logline"), 18):
        add("screenplay_logline", "warn", "Screenplay logline is too thin.", penalty=6)
    else:
        add("screenplay_logline", "pass", "Screenplay logline is present.")
    if not _as_list(screenplay.get("continuity_contract")):
        add("continuity_contract", "fail", "Screenplay plan is missing continuity contract.", penalty=22)
    else:
        add("continuity_contract", "pass", "Continuity contract exists.")
    if not _useful(screenplay.get("editor_promise"), 24):
        add("editor_promise", "warn", "Editor promise is missing or too thin.", penalty=5)
    else:
        add("editor_promise", "pass", "Editor promise is present.")
    if scenes and len(scripts) != len(scenes):
        add(
            "scene_script_count",
            "fail",
            f"Scene script count {len(scripts)} does not match blueprint count {len(scenes)}.",
            penalty=25,
        )
    elif scripts:
        add("scene_script_count", "pass", "Every scene blueprint has a screenplay scene.")


def _scene_reports(
    scenes: list[dict[str, Any]],
    scripts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    scripts_by_id = {str(s.get("scene_id") or ""): s for s in scripts}
    reports: list[dict[str, Any]] = []
    for scene in scenes:
        scene_id = str(scene.get("scene_id") or f"scene_{len(reports) + 1}")
        script = scripts_by_id.get(scene_id) or {}
        issues: list[str] = []
        warnings: list[str] = []

        for field, min_len in [
            ("purpose", 10),
            ("dramatic_question", 20),
            ("visual_hook", 12),
            ("continuity_anchor", 18),
            ("handoff_to_next", 18),
        ]:
            if not _useful(scene.get(field), min_len):
                issues.append(f"missing_{field}")

        for field, min_len in [
            ("premise", 18),
            ("conflict", 18),
            ("turning_point", 18),
            ("opening_image", 12),
            ("closing_image", 12),
        ]:
            if not _useful(script.get(field), min_len):
                issues.append(f"missing_{field}")

        if not _useful(script.get("dialogue_or_vo_intent"), 18):
            warnings.append("thin_dialogue_or_vo_intent")
        if not _as_list(script.get("reference_priorities")):
            warnings.append("missing_reference_priorities")
        if not _as_list(script.get("qa_focus")):
            warnings.append("missing_qa_focus")

        status = "fail" if issues else ("warn" if warnings else "pass")
        reports.append({
            "scene_id": scene_id,
            "status": status,
            "issues": issues,
            "warnings": warnings,
            "repair_hint": _scene_repair_hint(issues, warnings),
        })
    return reports


def _scene_repair_hint(issues: list[str], warnings: list[str]) -> str:
    all_issues = issues or warnings
    if not all_issues:
        return "scene_ready_for_storyboard_and_shot_graph"
    if any("conflict" in issue for issue in all_issues):
        return "add_scene_conflict_or_stakes_that_change_the_story"
    if any("turning_point" in issue for issue in all_issues):
        return "add_visible_turning_point_that_makes_next_scene_necessary"
    if any("continuity_anchor" in issue for issue in all_issues):
        return "add_character_product_location_or_last_frame_continuity_anchor"
    if any("handoff" in issue or "closing_image" in issue for issue in all_issues):
        return "add_handoff_image_to_motivate_the_next_scene"
    return "tighten_scene_purpose_visual_hook_dialogue_refs_and_qa_focus"


def _top_scene_issues(reports: list[dict[str, Any]], limit: int = 8) -> list[str]:
    counts: dict[str, int] = {}
    for report in reports:
        for issue in [*report.get("issues", []), *report.get("warnings", [])]:
            counts[issue] = counts.get(issue, 0) + 1
    return [
        f"{issue}:{count}"
        for issue, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def _result(
    status: str,
    score: float,
    hard_failures: list[str],
    warnings: list[str],
    checks: list[dict[str, Any]],
    scene_reports: list[dict[str, Any]],
    top_issues: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": "cinejelly.screenplay_scene_lint.v1",
        "status": status,
        "score": round(score, 1),
        "hard_failures": hard_failures,
        "warnings": warnings,
        "checks": checks,
        "scene_count": len(scene_reports),
        "failed_scene_count": len([r for r in scene_reports if r["status"] == "fail"]),
        "warned_scene_count": len([r for r in scene_reports if r["status"] == "warn"]),
        "top_issues": top_issues,
        "scene_reports": scene_reports,
    }


def _as_list(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _useful(value: Any, min_len: int) -> bool:
    text = " ".join(str(value or "").strip().lower().split())
    return len(text) >= min_len and text not in _GENERIC_VALUES


__all__ = ["lint_screenplay_scene_structure"]
