"""Pre-render shot linting for Seedance-oriented plans.

The linter is deterministic and vendor-free. It catches common failures before
paid render calls: vague subjects/actions, missing camera/setting/audio cues,
shots outside Seedance's 4-15s practical range, and overloaded actions that
try to turn one model call into a whole scene.
"""
from __future__ import annotations

import re
from typing import Any

from agent.schemas import ContinuityBible, Shot


_ACTION_SPLIT_RE = re.compile(
    r"\b(?:then|after that|next|before|while|and then|,\s*then|->|→)\b",
    re.IGNORECASE,
)
_ACTION_VERBS = {
    "applies",
    "arrives",
    "bites",
    "checks",
    "cuts",
    "demonstrates",
    "drinks",
    "drops",
    "enters",
    "explains",
    "holds",
    "lifts",
    "looks",
    "opens",
    "pours",
    "pushes",
    "reacts",
    "reveals",
    "runs",
    "shows",
    "smiles",
    "sprays",
    "stirs",
    "tests",
    "turns",
    "walks",
    "zooms",
}
_GENERIC_SUBJECTS = {
    "person",
    "people",
    "someone",
    "subject",
    "main subject",
    "character",
    "product",
    "object",
    "scene",
}
_GENERIC_ACTIONS = {
    "does something",
    "shows product",
    "moves",
    "generic action",
    "beautiful cinematic moment",
    "nice scene",
    "viral hook",
}
_CAMERA_TOKENS = {
    "cu",
    "ecu",
    "ms",
    "ws",
    "pov",
    "macro",
    "close",
    "wide",
    "overhead",
    "handheld",
    "tracking",
    "dolly",
    "orbit",
    "push",
    "pull",
    "pan",
    "tilt",
    "static",
    "locked",
    "drone",
    "ots",
}


def lint_seedance_shot(*, bible: ContinuityBible, shot: Shot) -> dict[str, Any]:
    """Return pass/warn/fail lint result for one planned Seedance shot."""
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

    _lint_duration(add, shot)
    _lint_subject(add, shot)
    _lint_action(add, shot)
    _lint_camera(add, shot)
    _lint_setting(add, bible, shot)
    _lint_audio(add, bible, shot)
    _lint_continuity(add, bible, shot)

    status = "fail" if hard_failures else ("warn" if warnings else "pass")
    return {
        "schema_version": "cinejelly.seedance_shot_lint.v1",
        "shot_id": shot.shot_id,
        "status": status,
        "score": round(score, 1),
        "hard_failures": hard_failures,
        "warnings": warnings,
        "checks": checks,
        "repair_hint": _repair_hint(hard_failures, warnings),
    }


def lint_seedance_plan(*, bible: ContinuityBible, shots: list[Shot]) -> dict[str, Any]:
    """Return aggregate lint result for a DirectorPlan shot list."""
    shot_reports = [lint_seedance_shot(bible=bible, shot=shot) for shot in shots]
    failed = [r for r in shot_reports if r["status"] == "fail"]
    warned = [r for r in shot_reports if r["status"] == "warn"]
    status = "fail" if failed else ("warn" if warned else "pass")
    avg_score = (
        sum(float(r.get("score") or 0.0) for r in shot_reports) / len(shot_reports)
        if shot_reports else 0.0
    )
    return {
        "schema_version": "cinejelly.seedance_plan_lint.v1",
        "status": status,
        "score": round(avg_score, 1),
        "shot_count": len(shot_reports),
        "failed_shot_count": len(failed),
        "warned_shot_count": len(warned),
        "failed_shots": [r["shot_id"] for r in failed],
        "warned_shots": [r["shot_id"] for r in warned],
        "top_issues": _top_issues(shot_reports),
        "shot_reports": shot_reports,
    }


def _lint_duration(add: Any, shot: Shot) -> None:
    duration = int(shot.duration_s or 0)
    if duration > 15:
        add(
            "seedance_duration",
            "fail",
            f"Shot is {duration}s; split into <=15s Seedance render units.",
            penalty=35,
        )
    elif duration < 4:
        add(
            "seedance_duration",
            "warn",
            f"Shot is {duration}s; very short hooks are valid but may need strong visual clarity.",
            penalty=4,
        )
    else:
        add("seedance_duration", "pass", f"Shot duration {duration}s fits Seedance 4-15s unit.")


def _lint_subject(add: Any, shot: Shot) -> None:
    subject = _norm(shot.visual.subject)
    if len(subject) < 4:
        add("subject", "fail", "Shot subject is missing.", penalty=25)
    elif subject in _GENERIC_SUBJECTS:
        add("subject", "warn", f"Shot subject is too generic: {subject!r}.", penalty=10)
    else:
        add("subject", "pass", "Shot has a concrete subject.")


def _lint_action(add: Any, shot: Shot) -> None:
    action = _norm(shot.visual.action)
    if len(action) < 8:
        add("action", "fail", "Shot action is missing or too thin.", penalty=28)
        return
    if action in _GENERIC_ACTIONS:
        add("action_specificity", "warn", f"Shot action is generic: {action!r}.", penalty=10)
    else:
        add("action_specificity", "pass", "Shot action is specific enough.")

    transitions = len(_ACTION_SPLIT_RE.findall(action))
    verb_hits = sum(1 for token in re.findall(r"[a-zA-Z]+", action) if token.lower() in _ACTION_VERBS)
    if transitions >= 2 or verb_hits >= 4:
        add(
            "one_physical_action",
            "fail",
            "Shot contains too many sequential actions; split into multiple shots.",
            penalty=30,
        )
    elif transitions == 1 or verb_hits == 3:
        add(
            "one_physical_action",
            "warn",
            "Shot may contain more than one physical action; simplify before render if output drifts.",
            penalty=8,
        )
    else:
        add("one_physical_action", "pass", "Shot appears to contain one filmable action.")


def _lint_camera(add: Any, shot: Shot) -> None:
    camera = _norm(f"{shot.visual.camera_shot} {shot.visual.camera_movement}")
    if len(camera) < 3:
        add("camera", "fail", "Camera shot/movement is missing.", penalty=24)
        return
    if not any(token in camera for token in _CAMERA_TOKENS):
        add("camera", "warn", f"Camera language may be too vague: {camera!r}.", penalty=8)
    else:
        add("camera", "pass", "Camera language is explicit.")


def _lint_setting(add: Any, bible: ContinuityBible, shot: Shot) -> None:
    setting = _norm(shot.visual.background or bible.setting.location)
    if len(setting) < 4:
        add("setting", "warn", "Shot has no explicit setting/background.", penalty=7)
    else:
        add("setting", "pass", "Shot has a usable setting/background.")


def _lint_audio(add: Any, bible: ContinuityBible, shot: Shot) -> None:
    has_audio = bool(
        (shot.audio.dialogue_vn or "").strip()
        or (shot.audio.caption_on_screen or "").strip()
        or shot.audio.sfx
        or (shot.audio.music_cue or "").strip()
        or bible.audio_design.sfx_emphasis
        or (bible.audio_design.music_genre or "").strip()
    )
    if has_audio:
        add("audio_cue", "pass", "Shot has dialogue, SFX, music, or inherited audio cue.")
    else:
        add("audio_cue", "warn", "Shot lacks audio/SFX/music cue; output may feel generic.", penalty=5)


def _lint_continuity(add: Any, bible: ContinuityBible, shot: Shot) -> None:
    needs_anchor = bool(bible.characters or bible.products or bible.reference_assets)
    has_anchor = bool(
        shot.continuity.character_ids
        or shot.continuity.product_ids
        or shot.continuity.reference_indices
        or shot.continuity.previous_shot_id
        or shot.continuity.style_anchor
    )
    if needs_anchor and not has_anchor:
        add("continuity_anchor", "warn", "Plan has characters/products/refs but this shot lacks continuity anchors.", penalty=10)
    else:
        add("continuity_anchor", "pass", "Shot continuity anchors are plausible.")


def _repair_hint(hard_failures: list[str], warnings: list[str]) -> str:
    issues = hard_failures or warnings
    if not issues:
        return "shot_ready_for_seedance_prompt_compile"
    if "seedance_duration" in issues:
        return "split_long_shot_into_4_15s_render_units"
    if "one_physical_action" in issues:
        return "split_sequential_actions_into_separate_shots"
    if "action" in issues or "action_specificity" in issues:
        return "rewrite_action_as_one_visible_physical_verb"
    if "subject" in issues:
        return "replace_generic_subject_with_named_character_product_or_object"
    return "tighten_subject_action_camera_setting_audio_before_render"


def _top_issues(reports: list[dict[str, Any]], limit: int = 8) -> list[str]:
    counts: dict[str, int] = {}
    for report in reports:
        for name in [*report.get("hard_failures", []), *report.get("warnings", [])]:
            counts[name] = counts.get(name, 0) + 1
    return [
        f"{name}:{count}"
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


__all__ = ["lint_seedance_shot", "lint_seedance_plan"]
