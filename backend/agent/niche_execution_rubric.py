"""Niche-specific execution rubric for autonomous video plans.

Producer story critic checks the general film contract. This rubric checks
whether the plan speaks the language of the selected niche: hook move, beat
flow, camera grammar, audio texture, proof/payoff, and safety rules.
"""
from __future__ import annotations

from typing import Any

from agent.schemas import DirectorPlan
from skills.niche_playbooks import get_niche_playbook


def build_niche_execution_rubric(
    *,
    niche: str,
    runtime_payload: dict[str, Any] | None = None,
    target_market: str = "auto",
) -> dict[str, Any]:
    """Return the source-backed execution contract for a niche."""
    playbook = get_niche_playbook(niche)
    runtime = runtime_payload or {}
    return {
        "schema_version": "cinejelly.niche_execution_rubric.v1",
        "niche": playbook.get("niche") or niche,
        "target_market": target_market or "auto",
        "runtime_class": runtime.get("runtime_class") or "short",
        "target_duration_s": runtime.get("target_duration_s"),
        "best_for": playbook.get("best_for"),
        "required_hook_moves": list(playbook.get("hook_moves") or [])[:4],
        "required_beat_flow": list(playbook.get("beat_flow") or []),
        "camera_grammar": list(playbook.get("camera") or [])[:6],
        "audio_texture": playbook.get("audio") or "",
        "quality_bar": list(playbook.get("quality_bar") or []),
        "safety_rules": list(playbook.get("safety_rules") or []),
        "seedance_notes": list(playbook.get("seedance_notes") or []),
        "pass_policy": [
            "first shot should match one hook move or a concrete equivalent",
            "shot purposes should cover at least three niche beat-flow roles for videos longer than 20s",
            "camera language should include niche-specific shot sizes or movement",
            "audio/SFX cues should match the niche texture unless intentionally silent",
            "final shot should deliver proof, reveal, takeaway, or emotional aftertaste",
        ],
    }


def score_plan_against_niche_rubric(
    *,
    plan: DirectorPlan,
    target_market: str,
    target_platform: str,
) -> dict[str, Any]:
    """Score a DirectorPlan against the selected niche playbook."""
    bible = plan.continuity_bible
    meta = bible.storytelling_meta or {}
    niche = str((meta.get("niche_playbook") or {}).get("niche") or meta.get("niche") or bible.intent or "ugc_review")
    runtime = meta.get("runtime_structure") or {}
    rubric = build_niche_execution_rubric(
        niche=niche,
        runtime_payload=runtime,
        target_market=target_market,
    )
    dimensions = [
        _hook_fit(plan, rubric),
        _beat_flow_fit(plan, rubric),
        _camera_fit(plan, rubric),
        _audio_fit(plan, rubric),
        _quality_safety_fit(plan, rubric, target_platform=target_platform),
    ]
    score = round(sum(float(item["score"]) for item in dimensions) / max(1, len(dimensions)), 1)
    failed = [item for item in dimensions if item["status"] == "fail"]
    warned = [item for item in dimensions if item["status"] == "warn"]
    status = "fail" if failed or score < 60 else ("warn" if warned or score < 82 else "pass")
    return {
        **rubric,
        "status": status,
        "score": score,
        "top_issues": [issue for item in dimensions for issue in item.get("issues", [])][:6],
        "dimensions": dimensions,
        "next_best_action": _next_best_action(dimensions),
    }


def _hook_fit(plan: DirectorPlan, rubric: dict[str, Any]) -> dict[str, Any]:
    if not plan.shot_list:
        return _dimension("niche_hook_fit", "fail", 0, ["missing_shot_list"], "No shot list exists.")
    first = plan.shot_list[0]
    text = _shot_text(first)
    hooks = list(rubric.get("required_hook_moves") or [])
    matches = _phrase_matches(text, hooks)
    issues: list[str] = []
    if not matches and "hook" not in _norm(first.purpose):
        issues.append("first_shot_does_not_match_niche_hook_language")
    if len((first.visual.action or "").strip()) < 10:
        issues.append("first_shot_action_too_thin")
    score = 100 - 22 * len(issues)
    return _dimension("niche_hook_fit", _status(score), score, issues, f"Expected hook moves: {', '.join(hooks[:3])}.")


def _beat_flow_fit(plan: DirectorPlan, rubric: dict[str, Any]) -> dict[str, Any]:
    beat_flow = [str(item).lower() for item in rubric.get("required_beat_flow") or []]
    purposes = " ".join(_norm(shot.purpose) for shot in plan.shot_list)
    shot_text = " ".join(_shot_text(shot) for shot in plan.shot_list)
    matched = [beat for beat in beat_flow if _loose_tokens_match(beat, purposes + " " + shot_text)]
    required = 2 if len(plan.shot_list) <= 3 else min(3, len(beat_flow))
    issues: list[str] = []
    if len(matched) < required:
        issues.append("shot_list_underuses_niche_beat_flow")
    if len(plan.shot_list) > 4 and len(set(_norm(shot.purpose) for shot in plan.shot_list)) < 3:
        issues.append("shot_purposes_too_repetitive_for_niche")
    score = 100 - 20 * len(issues) - max(0, required - len(matched)) * 8
    return _dimension(
        "niche_beat_flow",
        _status(score),
        score,
        issues,
        f"Matched {len(matched)}/{len(beat_flow)} niche beat-flow cues.",
    )


def _camera_fit(plan: DirectorPlan, rubric: dict[str, Any]) -> dict[str, Any]:
    camera_grammar = list(rubric.get("camera_grammar") or [])
    text = " ".join(
        " ".join([
            shot.visual.camera_shot or "",
            shot.visual.camera_movement or "",
            shot.visual.composition or "",
            shot.dynamic_description or "",
        ])
        for shot in plan.shot_list
    ).lower()
    matches = _phrase_matches(text, camera_grammar)
    issues: list[str] = []
    if not matches and camera_grammar:
        issues.append("camera_language_not_niche_specific")
    if len(plan.shot_list) >= 3:
        shot_sizes = {str(shot.visual.camera_shot or "").lower() for shot in plan.shot_list}
        if len(shot_sizes) < 2:
            issues.append("camera_shot_size_variety_too_low")
    score = 100 - 18 * len(issues)
    return _dimension("niche_camera_language", _status(score), score, issues, f"Camera grammar: {', '.join(camera_grammar[:3])}.")


def _audio_fit(plan: DirectorPlan, rubric: dict[str, Any]) -> dict[str, Any]:
    expected = str(rubric.get("audio_texture") or "")
    text = " ".join(
        " ".join([
            " ".join(shot.audio.sfx or []),
            shot.audio.music_cue or "",
            shot.audio.dialogue_vn or "",
            shot.dynamic_description or "",
        ])
        for shot in plan.shot_list
    ).lower()
    issues: list[str] = []
    if expected and not _loose_tokens_match(expected, text):
        issues.append("audio_texture_not_reflected_in_shots")
    if any(token in expected.lower() for token in ("sfx", "asmr", "sizzle", "crunch", "foley", "beat")):
        if not any(shot.audio.sfx or shot.audio.music_cue for shot in plan.shot_list):
            issues.append("niche_audio_cues_missing")
    score = 100 - 16 * len(issues)
    return _dimension("niche_audio_texture", _status(score), score, issues, f"Audio target: {expected}.")


def _quality_safety_fit(plan: DirectorPlan, rubric: dict[str, Any], *, target_platform: str) -> dict[str, Any]:
    quality = list(rubric.get("quality_bar") or [])
    safety = list(rubric.get("safety_rules") or [])
    constraints = " ".join([
        " ".join(plan.continuity_bible.constraints.must_avoid or []),
        " ".join(plan.continuity_bible.constraints.must_have or []),
        " ".join(plan.continuity_bible.constraints.brand_safety or []),
    ]).lower()
    issues: list[str] = []
    if quality and not _phrase_matches(constraints, quality):
        issues.append("quality_bar_not_reflected_in_constraints")
    if safety and not _phrase_matches(constraints, safety):
        issues.append("safety_rules_not_reflected_in_constraints")
    if target_platform in {"tiktok", "reels", "youtube_shorts"} and int(plan.continuity_bible.duration_s or 0) <= 60:
        if not any("hook" in _norm(shot.purpose) for shot in plan.shot_list[:2]):
            issues.append("short_platform_lacks_front_loaded_hook")
    score = 100 - 20 * len(issues)
    return _dimension("niche_quality_safety", _status(score), score, issues, "Quality bar and safety rules should survive into the production bible.")


def _dimension(name: str, status: str, score: float, issues: list[str], detail: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "score": max(0, round(float(score), 1)),
        "issues": issues,
        "detail": detail,
    }


def _status(score: float) -> str:
    if score < 60:
        return "fail"
    if score < 82:
        return "warn"
    return "pass"


def _next_best_action(dimensions: list[dict[str, Any]]) -> str:
    for item in dimensions:
        issues = item.get("issues") or []
        if issues:
            issue = str(issues[0])
            if "hook" in issue:
                return "rewrite_first_shot_to_match_niche_hook_move"
            if "beat" in issue or "purpose" in issue:
                return "rebalance_shot_purposes_against_niche_beat_flow"
            if "camera" in issue:
                return "inject_niche_camera_grammar_into_shots"
            if "audio" in issue:
                return "add_niche_specific_sfx_music_or_dialogue_cues"
            if "quality" in issue or "safety" in issue:
                return "add_niche_quality_and_safety_constraints_to_bible"
    return "niche_execution_contract_ready"


def _shot_text(shot: Any) -> str:
    return " ".join([
        shot.purpose or "",
        shot.emotion_beat or "",
        shot.visual.subject or "",
        shot.visual.action or "",
        shot.visual.camera_shot or "",
        shot.visual.camera_movement or "",
        shot.visual.composition or "",
        shot.visual.background or "",
        shot.dynamic_description or "",
        shot.audio.dialogue_vn or "",
        shot.audio.caption_on_screen or "",
        " ".join(shot.audio.sfx or []),
        shot.audio.music_cue or "",
    ]).lower()


def _phrase_matches(text: str, phrases: list[str]) -> list[str]:
    return [phrase for phrase in phrases if _loose_tokens_match(str(phrase), text)]


def _loose_tokens_match(phrase: str, text: str) -> bool:
    tokens = [
        token for token in _norm(phrase).replace("_", " ").split()
        if len(token) >= 4 and token not in {"with", "through", "from", "into", "shot"}
    ]
    if not tokens:
        return False
    return any(token in text for token in tokens[:5])


def _norm(value: str) -> str:
    return (value or "").strip().lower().replace("-", " ").replace("/", " ").replace(" ", "_")


__all__ = ["build_niche_execution_rubric", "score_plan_against_niche_rubric"]
