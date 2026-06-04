"""Deterministic producer/story critic for autonomous videos.

This is a pre-render gate for the "director/producer/editor" layer. It does
not judge pixels; it judges whether the planned story is worth rendering:
hook clarity, causality, payoff, niche proof, market fit, and reference intent.
"""
from __future__ import annotations

from typing import Any

from agent.schemas import DirectorPlan, Shot


_PRODUCT_NICHES = {"ugc_review", "ecommerce_catalog", "tech", "app_saas", "beauty", "fashion", "food"}
_SENSORY_NICHES = {"food", "beauty", "fashion", "asmr", "lifestyle", "travel", "restaurant_hospitality"}
_STORY_NICHES = {"drama", "anime_comic", "music_video"}
_EXPLAINER_NICHES = {"education", "finance_education", "medical_wellness", "documentary"}

_HOOK_WORDS = {
    "hook", "open", "cold", "result", "surprise", "question", "mistake",
    "myth", "reveal", "before", "after", "test", "proof",
}
_PAYOFF_WORDS = {"payoff", "result", "proof", "reveal", "verdict", "close", "cta", "takeaway", "aftermath"}
_VAGUE_WORDS = {"thing", "something", "stuff", "nice", "beautiful", "amazing", "cool", "generic"}


def critique_producer_story(
    *,
    plan: DirectorPlan,
    target_market: str,
    target_platform: str,
) -> dict[str, Any]:
    """Return a source-only producer critique for a DirectorPlan."""
    bible = plan.continuity_bible
    meta = bible.storytelling_meta or {}
    niche = str((meta.get("niche_playbook") or {}).get("niche") or meta.get("niche") or bible.intent or "ugc_review")
    runtime = meta.get("runtime_structure") or {}
    treatment = meta.get("production_treatment") or {}
    market = meta.get("market_playbook") or {}

    dimensions = [
        _hook_dimension(plan.shot_list, str(meta.get("hook_first_3s") or "")),
        _causality_dimension(plan.shot_list, runtime),
        _payoff_dimension(plan.shot_list),
        _niche_proof_dimension(plan.shot_list, niche, treatment),
        _market_fit_dimension(target_market, target_platform, market, treatment),
        _reference_intent_dimension(plan),
    ]
    score = round(sum(float(d["score"]) for d in dimensions) / max(1, len(dimensions)), 1)
    failed = [d for d in dimensions if d["status"] == "fail"]
    warned = [d for d in dimensions if d["status"] == "warn"]
    status = "fail" if failed or score < 70 else ("warn" if warned or score < 78 else "pass")
    top_issues = [issue for d in dimensions for issue in d.get("issues", [])][:6]
    return {
        "schema_version": "cinejelly.producer_story_critic.v1",
        "status": status,
        "score": score,
        "niche": niche,
        "target_market": target_market or "auto",
        "target_platform": target_platform or "tiktok",
        "dimensions": dimensions,
        "top_issues": top_issues,
        "repair_hint": _repair_hint(top_issues, niche),
    }


def _hook_dimension(shots: list[Shot], hook_first_3s: str) -> dict[str, Any]:
    if not shots:
        return _dimension("hook_3s", "fail", 0, ["missing_shots"], "No shot list exists.")
    first = shots[0]
    text = _shot_text(first, extra=hook_first_3s)
    issues: list[str] = []
    if first.start_s > 1:
        issues.append("first_shot_does_not_start_immediately")
    if "hook" not in _norm(first.purpose) and not _contains_any(text, list(_HOOK_WORDS)):
        issues.append("first_shot_lacks_explicit_hook")
    if len((first.visual.subject or "").strip()) < 8 or len((first.visual.action or "").strip()) < 8:
        issues.append("hook_missing_concrete_subject_or_action")
    if _contains_any(text, list(_VAGUE_WORDS)):
        issues.append("hook_contains_vague_language")
    score = 100 - 18 * len(issues)
    return _dimension("hook_3s", _status(score, fail_below=55), score, issues, "First 3 seconds should be a concrete visual incident.")


def _causality_dimension(shots: list[Shot], runtime: dict[str, Any]) -> dict[str, Any]:
    purposes = [_norm(s.purpose) for s in shots]
    duration = int(runtime.get("target_duration_s") or 0)
    is_long = duration > 60 or str(runtime.get("runtime_class") or "") in {"micro_film", "short_film", "episode"}
    issues: list[str] = []
    if len(shots) >= 3 and len(set(purposes)) < 3:
        issues.append("shot_purposes_do_not_progress")
    if is_long:
        scenes = runtime.get("scene_blueprints") or []
        if len(scenes) < 2:
            issues.append("long_form_missing_scene_blueprints")
        if not (runtime.get("screenplay_plan") or {}).get("continuity_contract"):
            issues.append("long_form_missing_continuity_contract")
    if any("transition" in p for p in purposes) and len(shots) < 4:
        issues.append("transition_without_enough_story_beats")
    score = 100 - 17 * len(issues)
    return _dimension("story_causality", _status(score, fail_below=55), score, issues, "Shots/scenes should change the situation, not repeat the same beat.")


def _payoff_dimension(shots: list[Shot]) -> dict[str, Any]:
    if not shots:
        return _dimension("payoff", "fail", 0, ["missing_final_shot"], "No final shot exists.")
    final = shots[-1]
    text = _shot_text(final)
    issues: list[str] = []
    if not _contains_any(_norm(final.purpose), list(_PAYOFF_WORDS)) and not _contains_any(text, list(_PAYOFF_WORDS)):
        issues.append("final_shot_lacks_payoff_or_takeaway")
    if len((final.visual.action or "").strip()) < 12:
        issues.append("final_action_too_thin")
    score = 100 - 22 * len(issues)
    return _dimension("payoff", _status(score, fail_below=50), score, issues, "Final shot should resolve the promise with visual proof or emotional aftertaste.")


def _niche_proof_dimension(shots: list[Shot], niche: str, treatment: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(_shot_text(s) for s in shots)
    purposes = {_norm(s.purpose) for s in shots}
    issues: list[str] = []
    if niche in _PRODUCT_NICHES:
        has_product_anchor = any(s.continuity.product_ids for s in shots) or _contains_any(text, ["product", "packaging", "feature", "test", "proof", "demo", "result"])
        has_proof = bool(purposes & {"proof", "demo", "result", "reveal"}) or _contains_any(text, ["prove", "test", "result", "before", "after", "comparison"])
        if not has_product_anchor:
            issues.append("product_niche_missing_product_anchor")
        if not has_proof:
            issues.append("product_niche_missing_visual_proof")
    elif niche in _STORY_NICHES:
        if not _contains_any(text, ["tension", "conflict", "reveal", "emotion", "choice", "secret", "aftermath"]):
            issues.append("story_niche_missing_conflict_or_emotional_turn")
    elif niche in _EXPLAINER_NICHES:
        if not _contains_any(text, ["question", "explain", "mistake", "example", "visual", "takeaway", "model"]):
            issues.append("explainer_niche_missing_visual_explanation")
    elif niche in _SENSORY_NICHES:
        if not _contains_any(text, ["macro", "texture", "sizzle", "steam", "touch", "pour", "fabric", "ritual", "sound"]):
            issues.append("sensory_niche_missing_sensory_payoff")
    if not treatment.get("story_engine"):
        issues.append("missing_story_engine")
    score = 100 - 20 * len(issues)
    return _dimension("niche_proof", _status(score, fail_below=50), score, issues, "Plan should satisfy the selected niche's proof/story promise.")


def _market_fit_dimension(
    target_market: str,
    target_platform: str,
    market: dict[str, Any],
    treatment: dict[str, Any],
) -> dict[str, Any]:
    issues: list[str] = []
    if not target_market:
        issues.append("missing_target_market")
    if target_market and target_market != "auto" and market.get("target_market") not in {target_market, None}:
        issues.append("market_playbook_mismatch")
    if not market.get("hook_style"):
        issues.append("missing_market_hook_style")
    if not treatment.get("delivery_notes"):
        issues.append("missing_delivery_notes")
    if target_platform not in {"tiktok", "reels", "youtube_shorts", "youtube_long", "xhs", "bilibili", "auto"}:
        issues.append("unknown_target_platform")
    score = 100 - 16 * len(issues)
    return _dimension("market_fit", _status(score, fail_below=50), score, issues, "Market should guide hook style, proof style, caption language, and delivery.")


def _reference_intent_dimension(plan: DirectorPlan) -> dict[str, Any]:
    refs = plan.continuity_bible.reference_assets or []
    shots = plan.shot_list
    issues: list[str] = []
    if refs and not any(s.continuity.reference_indices for s in shots):
        issues.append("uploaded_refs_not_bound_to_any_shot")
    if (plan.continuity_bible.characters or plan.continuity_bible.products) and not refs:
        issues.append("identity_or_product_bible_without_visual_refs")
    if any(s.continuity.reference_indices for s in shots) and not refs:
        issues.append("shot_references_indices_without_bible_refs")
    score = 100 - 18 * len(issues)
    return _dimension("reference_intent", _status(score, fail_below=55), score, issues, "References should have explicit jobs: character, product, style, motion, audio, or environment.")


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


def _repair_hint(issues: list[str], niche: str) -> str:
    if not issues:
        return "ready_for_pre_render_story_contract"
    first = issues[0]
    if "hook" in first:
        return "rewrite_first_shot_as_concrete_scroll_stop_visual_action"
    if "payoff" in first or "final" in first:
        return "add_final_visual_proof_or_emotional_aftertaste"
    if "product" in first or "proof" in first:
        return "add_visible_product_test_demo_or_result_shot"
    if "market" in first:
        return "attach_market_playbook_and_caption_delivery_notes"
    if "reference" in first:
        return "bind_reference_assets_to_specific_shot_jobs"
    if niche in _EXPLAINER_NICHES:
        return "add_visual_question_example_and_safe_takeaway"
    return "tighten_hook_causality_payoff_niche_proof_and_market_fit"


def _shot_text(shot: Shot, *, extra: str = "") -> str:
    return " ".join([
        extra or "",
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


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _norm(value: str) -> str:
    return (value or "").strip().lower().replace(" ", "_")


__all__ = ["critique_producer_story"]
