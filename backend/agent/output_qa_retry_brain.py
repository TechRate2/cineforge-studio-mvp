"""Output QA + Retry Brain 4B.

This is a vendor-free post-render intelligence contract. It does not inspect
pixels or call AtlasCloud. It prepares the per-shot QA rubric, issue taxonomy,
retry recipes, and output-intake schema that the renderer can use after real
videos exist.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any


_SCHEMA_VERSION = "cinejelly.output_qa_retry_brain.v1"
_LONG_RUNTIME_CLASSES = {"micro_film", "short_film", "episode"}
_PRODUCT_CHECKS = {"product_recognition", "reference_identity_or_product_match", "identity_or_product_consistency"}
_CONTINUITY_CHECKS = {"continuity_handoff_match", "previous_final_frame_consistency", "cross_shot_continuity"}


def build_output_qa_retry_brain(
    *,
    user_idea: str,
    creative_brief_contract: dict[str, Any],
    creative_producer_v2: dict[str, Any],
    prompt_execution_contract_v3: dict[str, Any],
    viral_creative_brain: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    """Return a no-vendor-call QA and retry contract for rendered outputs."""
    parsed = (creative_brief_contract or {}).get("parsed") or {}
    readiness = (creative_brief_contract or {}).get("readiness") or {}
    prompt_readiness = (prompt_execution_contract_v3 or {}).get("readiness") or {}
    prompt_qa_plan = (prompt_execution_contract_v3 or {}).get("qa_plan") or {}
    compiled_shots = list((prompt_execution_contract_v3 or {}).get("compiled_shots") or [])
    producer_qa = (creative_producer_v2 or {}).get("qa_contract") or {}
    viral_readiness = (viral_creative_brain or {}).get("readiness") or {}
    viral_pattern = (viral_creative_brain or {}).get("selected_viral_pattern") or {}
    runtime_class = str(decision.get("runtime_class") or "short")
    duration_s = _safe_int(decision.get("target_duration_s"), 30)
    niche = str(decision.get("niche") or "auto")
    output_intent = str(parsed.get("output_intent") or "general_video")
    target_platform = str(decision.get("target_platform") or parsed.get("target_platform") or "tiktok")
    subject = _subject(parsed, niche)

    per_shot_qa = [
        _shot_qa_node(
            shot=shot,
            index=index,
            niche=niche,
            runtime_class=runtime_class,
            output_intent=output_intent,
            subject=subject,
            viral_pattern=viral_pattern,
        )
        for index, shot in enumerate(compiled_shots)
    ]
    sequence_qa = _sequence_qa(
        per_shot_qa=per_shot_qa,
        runtime_class=runtime_class,
        duration_s=duration_s,
        target_platform=target_platform,
        viral_creative_brain=viral_creative_brain,
        prompt_qa_plan=prompt_qa_plan,
    )
    warnings = _warnings(
        compiled_shots=compiled_shots,
        readiness=readiness,
        prompt_readiness=prompt_readiness,
        viral_readiness=viral_readiness,
        per_shot_qa=per_shot_qa,
        runtime_class=runtime_class,
    )
    recipe_counts = Counter(item["retry_recipe"]["primary_issue_tag"] for item in per_shot_qa)
    qa_confidence = _qa_confidence_score(
        brief_score=_safe_int(readiness.get("completeness_score"), 0),
        prompt_warning_count=_safe_int(prompt_readiness.get("warning_count"), 0),
        viral_score=_safe_int(viral_readiness.get("creative_score"), 0),
        qa_node_count=len(per_shot_qa),
        warning_count=len(warnings),
    )
    return {
        "schema_version": _SCHEMA_VERSION,
        "vendor_calls_performed": False,
        "paid_video_vendor_calls_allowed": False,
        "brain_id": _brain_id(user_idea=user_idea, niche=niche, duration_s=duration_s, platform=target_platform),
        "strategy": "prepare_post_render_qa_rubric_and_retry_recipes_without_running_paid_retries",
        "readiness": {
            "status": "qa_retry_plan_ready" if per_shot_qa and not _has_blocking_warning(warnings) else "needs_qa_contract_review",
            "qa_confidence_score": qa_confidence,
            "qa_node_count": len(per_shot_qa),
            "retry_recipe_count": len(per_shot_qa),
            "warning_count": len(warnings),
            "automation_level": "plan_only_until_render_output_exists",
        },
        "route_context": {
            "niche": niche,
            "output_intent": output_intent,
            "runtime_class": runtime_class,
            "duration_s": duration_s,
            "target_platform": target_platform,
            "subject": subject,
            "graph_required": bool(decision.get("graph_required")),
            "dialogue_required": bool(decision.get("dialogue_required")),
        },
        "issue_taxonomy": _issue_taxonomy(
            niche=niche,
            runtime_class=runtime_class,
            output_intent=output_intent,
            dialogue_required=bool(decision.get("dialogue_required")),
        ),
        "per_shot_qa": per_shot_qa,
        "sequence_qa": sequence_qa,
        "retry_policy": {
            "enabled_before_paid_render": False,
            "paid_retry_vendor_calls_allowed": False,
            "max_retries_per_shot": 2,
            "retry_scope": "failed_shot_only",
            "retry_order": ["hard_failures", "identity_or_product", "continuity", "text_artifacts", "weak_hook_or_pacing"],
            "requires_user_approval_before_paid_retry": True,
            "recipe_counts": dict(recipe_counts),
        },
        "post_render_intake_contract": _post_render_intake_contract(),
        "acceptance_gate": {
            "minimum_sequence_score": 82 if runtime_class in _LONG_RUNTIME_CLASSES else 78,
            "minimum_shot_score": 78,
            "hard_failures_block_delivery": True,
            "model_backed_gates_still_required": [
                "face_or_character_embedding_match",
                "product_logo_and_packaging_match",
                "semantic_prompt_adherence",
                "speech_lip_sync_alignment",
            ],
        },
        "warnings": warnings,
        "source_contracts": {
            "producer_qa_checks": list(producer_qa.get("checks") or [])[:12],
            "prompt_qa_checks": list(prompt_qa_plan.get("checks") or [])[:12],
            "viral_pattern_id": viral_pattern.get("pattern_id"),
        },
    }


def _shot_qa_node(
    *,
    shot: dict[str, Any],
    index: int,
    niche: str,
    runtime_class: str,
    output_intent: str,
    subject: str,
    viral_pattern: dict[str, Any],
) -> dict[str, Any]:
    shot_id = str(shot.get("shot_id") or f"S{index + 1:03d}")
    model_key = str(shot.get("model_key") or "seedance_2_0_fast_t2v")
    render_mode = str(shot.get("render_mode") or "text_to_video")
    checks = list(dict.fromkeys(str(item) for item in (shot.get("qa_checks") or [])))
    hard_failures = _hard_failures_for(checks=checks, render_mode=render_mode, runtime_class=runtime_class, output_intent=output_intent)
    likely_failures = _likely_failure_modes(
        checks=checks,
        render_mode=render_mode,
        runtime_class=runtime_class,
        model_key=model_key,
        shot=shot,
    )
    primary_issue = likely_failures[0]["issue_tag"] if likely_failures else "prompt_adherence"
    return {
        "shot_id": shot_id,
        "beat_id": shot.get("beat_id"),
        "index": index,
        "duration_s": _safe_int(shot.get("duration_s"), 0),
        "model_key": model_key,
        "render_mode": render_mode,
        "expected_output": {
            "subject": subject,
            "one_action": True,
            "must_match_prompt_blocks": ["reference_jobs", "timeline", "subject", "action", "camera", "continuity", "constraints"],
            "reference_slot_count": len(shot.get("reference_slots") or []),
            "return_last_frame": bool((shot.get("model_parameters") or {}).get("return_last_frame")),
        },
        "acceptance_threshold": {
            "minimum_score": 82 if index == 0 or runtime_class in _LONG_RUNTIME_CLASSES else 78,
            "hard_failures_block_delivery": True,
            "manual_review_required_if_warn": True,
        },
        "qa_checks": checks,
        "hard_failures": hard_failures,
        "likely_failure_modes": likely_failures,
        "retry_recipe": _retry_recipe(
            shot=shot,
            issue_tag=primary_issue,
            runtime_class=runtime_class,
            viral_pattern=viral_pattern,
        ),
        "output_fields_to_collect": ["output_url", "prediction_id", "duration_s", "media_probe", "frame_samples", "reviewer_issue_tags"],
    }


def _issue_taxonomy(*, niche: str, runtime_class: str, output_intent: str, dialogue_required: bool) -> list[dict[str, str]]:
    issues = [
        _issue("missing_video_url", "critical", "vendor result has no playable video", "retry same shot after checking provider response"),
        _issue("prompt_mismatch", "high", "output does not show the requested action/subject", "simplify prompt to one visible action and preserve subject line"),
        _issue("text_artifacts", "high", "unrequested text/logo/subtitle appears", "ban text overlays and move captions to post-production"),
        _issue("camera_motion_mismatch", "medium", "camera does not follow the shot contract", "rewrite camera as shot size plus one physical movement"),
        _issue("duration_mismatch", "medium", "output duration is outside target tolerance", "retry with exact duration and shorter action"),
    ]
    if output_intent in {"sell_product", "review_proof"} or niche in {"beauty", "food", "fashion", "ecommerce_catalog", "app_saas", "tech"}:
        issues.append(_issue("product_identity_drift", "critical", "product/packaging/label/geometry changed", "prioritize product_hero reference and ban geometry drift"))
    if runtime_class in _LONG_RUNTIME_CLASSES:
        issues.extend([
            _issue("continuity_break", "critical", "adjacent shot does not match previous final frame/state", "retry with previous final frame and carry continuity handoff"),
            _issue("scene_payoff_break", "high", "scene does not advance hook/conflict/payoff", "rewrite beat purpose and exit question before retry"),
        ])
    if dialogue_required:
        issues.append(_issue("lip_sync_or_audio_mismatch", "high", "visible speech/audio does not align", "use dialogue insert or post-render lipsync repair after visual QA"))
    return issues


def _sequence_qa(
    *,
    per_shot_qa: list[dict[str, Any]],
    runtime_class: str,
    duration_s: int,
    target_platform: str,
    viral_creative_brain: dict[str, Any],
    prompt_qa_plan: dict[str, Any],
) -> dict[str, Any]:
    viral_retention = (viral_creative_brain or {}).get("retention_plan") or {}
    checks = [
        "first_3s_hook_matches_viral_plan",
        "shot_order_matches_script_beats",
        "final_payoff_or_cta_present",
        "caption_cover_cta_package_matches_platform",
    ]
    checks.extend(str(item) for item in prompt_qa_plan.get("checks") or [])
    if runtime_class in _LONG_RUNTIME_CLASSES:
        checks.extend(["cross_shot_continuity", "scene_cliffhanger_payoff_tracking", "handoff_frame_consistency"])
    return {
        "runtime_class": runtime_class,
        "duration_s": duration_s,
        "target_platform": target_platform,
        "shot_count": len(per_shot_qa),
        "checks": list(dict.fromkeys(checks))[:18],
        "retention_checkpoints_s": list(viral_retention.get("checkpoints_s") or [])[:12],
        "assembly_review_order": ["technical_media", "shot_prompt_match", "reference_identity", "continuity", "viral_retention", "delivery_package"],
        "delivery_blockers": [
            "any critical shot failure",
            "first shot misses hook",
            "wrong product/character",
            "long-form continuity break",
            "unsafe or policy-sensitive output",
        ],
    }


def _retry_recipe(*, shot: dict[str, Any], issue_tag: str, runtime_class: str, viral_pattern: dict[str, Any]) -> dict[str, Any]:
    model_key = str(shot.get("model_key") or "")
    render_mode = str(shot.get("render_mode") or "")
    base = {
        "primary_issue_tag": issue_tag,
        "current_model": model_key,
        "current_render_mode": render_mode,
        "paid_retry_allowed_by_contract": False,
        "requires_user_approval": True,
        "preserve": {
            "shot_id": shot.get("shot_id"),
            "beat_id": shot.get("beat_id"),
            "duration_s": shot.get("duration_s"),
            "reference_slots": list(shot.get("reference_slots") or [])[:6],
            "handoff": shot.get("handoff") or {},
        },
    }
    if issue_tag == "product_identity_drift":
        base.update({
            "prompt_repair": "Move product_hero reference to the first line; repeat exact geometry, packaging, color, and label; remove competing identity refs.",
            "model_route_repair": "prefer seedance_2_0_ref for hero/proof retry when budget is approved",
            "negative_repair": "wrong packaging, label drift, warped product, extra logo, unreadable text",
        })
    elif issue_tag == "continuity_break":
        base.update({
            "prompt_repair": "Use previous final frame as the first continuity anchor and restate pose, lighting, location, and emotional state.",
            "model_route_repair": "prefer seedance_2_0_fast_i2v continuity retry",
            "negative_repair": "scene reset, changed wardrobe, changed location, broken eyeline",
        })
    elif issue_tag == "text_artifacts":
        base.update({
            "prompt_repair": "Remove all text instructions from visual prompt; keep captions/title outside the rendered frames.",
            "model_route_repair": "same model is acceptable after prompt cleanup",
            "negative_repair": "text overlay, captions, watermark, fake UI text, misspelled label",
        })
    elif issue_tag == "camera_motion_mismatch":
        base.update({
            "prompt_repair": "Reduce to one physical action and one camera movement; name shot size, movement, and end frame.",
            "model_route_repair": "use video motion reference only if available and labelled",
            "negative_repair": "camera teleport, random zoom, impossible motion, unrelated action",
        })
    elif issue_tag == "scene_payoff_break":
        base.update({
            "prompt_repair": f"Rebuild the shot around the viral pattern '{viral_pattern.get('label') or 'selected pattern'}' and make the exit question visible.",
            "model_route_repair": "retry only the failed scene/shot, then re-check sequence pacing",
            "negative_repair": "flat middle beat, no reveal, no payoff, generic filler",
        })
    else:
        base.update({
            "prompt_repair": "Simplify to one visible subject-action-camera contract; remove adjectives that do not change the frame.",
            "model_route_repair": "keep current model unless the same issue repeats twice",
            "negative_repair": "prompt mismatch, generic filler, unrelated subject, broken action",
        })
    if runtime_class in _LONG_RUNTIME_CLASSES and issue_tag != "continuity_break":
        base["sequence_recheck_after_retry"] = "re-run continuity and retention checks for adjacent shots after replacement"
    return base


def _likely_failure_modes(
    *,
    checks: list[str],
    render_mode: str,
    runtime_class: str,
    model_key: str,
    shot: dict[str, Any],
) -> list[dict[str, str]]:
    modes: list[dict[str, str]] = []
    check_set = set(checks)
    if check_set & _PRODUCT_CHECKS:
        modes.append(_mode("product_identity_drift", "critical", "reference/product checks are required for this shot"))
    if render_mode in {"continuity_i2v", "image_to_video"} or check_set & _CONTINUITY_CHECKS:
        modes.append(_mode("continuity_break", "critical" if runtime_class in _LONG_RUNTIME_CLASSES else "high", "shot depends on prior frame or reference handoff"))
    if "text_artifacts" in check_set or "no_unrequested_text_or_logo" in check_set:
        modes.append(_mode("text_artifacts", "high", "generated text/logos can break commercial polish"))
    if "camera_motion_matches_prompt" in check_set or "motion_physics" in check_set:
        modes.append(_mode("camera_motion_mismatch", "medium", "Seedance shot needs precise motion/camera adherence"))
    if runtime_class in _LONG_RUNTIME_CLASSES and _safe_int(shot.get("index"), 0) > 0:
        modes.append(_mode("scene_payoff_break", "high", "long-form replacement must preserve scene purpose and cliffhanger/payoff"))
    if not modes:
        modes.append(_mode("prompt_mismatch", "medium", f"default risk for {model_key} {render_mode}"))
    return modes[:5]


def _hard_failures_for(*, checks: list[str], render_mode: str, runtime_class: str, output_intent: str) -> list[str]:
    failures = ["missing output video", "wrong subject", "unsafe or blocked content", "severe prompt mismatch"]
    if set(checks) & _PRODUCT_CHECKS or output_intent in {"sell_product", "review_proof"}:
        failures.append("wrong product or packaging")
    if render_mode != "text_to_video":
        failures.append("reference identity/style mismatch")
    if runtime_class in _LONG_RUNTIME_CLASSES:
        failures.append("severe continuity break across adjacent shots")
    if "text_artifacts" in checks or "no_unrequested_text_or_logo" in checks:
        failures.append("unrequested text/logo artifacts")
    return list(dict.fromkeys(failures))


def _post_render_intake_contract() -> dict[str, Any]:
    return {
        "required_per_shot_fields": [
            "shot_id",
            "output_url",
            "prediction_id",
            "actual_duration_s",
            "model_key",
            "render_mode",
            "prompt_fingerprint",
        ],
        "optional_probe_fields": [
            "media_probe",
            "frame_samples",
            "semantic_quality",
            "text_artifacts",
            "visual_reference_probe",
            "reviewer_issue_tags",
            "reviewer_notes",
        ],
        "feedback_tags": [
            "prompt_mismatch",
            "product_identity_drift",
            "continuity_break",
            "text_artifacts",
            "camera_motion_mismatch",
            "duration_mismatch",
            "weak_hook_or_pacing",
            "lip_sync_or_audio_mismatch",
        ],
    }


def _warnings(
    *,
    compiled_shots: list[dict[str, Any]],
    readiness: dict[str, Any],
    prompt_readiness: dict[str, Any],
    viral_readiness: dict[str, Any],
    per_shot_qa: list[dict[str, Any]],
    runtime_class: str,
) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if not compiled_shots:
        warnings.append({"severity": "blocking", "risk": "no_compiled_shots", "fix": "build prompt execution contract before render"})
    if _safe_int(readiness.get("completeness_score"), 0) < 55:
        warnings.append({"severity": "blocking", "risk": "brief_too_thin_for_qa_retry", "fix": "ask a clarifying question before paid render"})
    if _safe_int(prompt_readiness.get("warning_count"), 0) > 0:
        warnings.append({"severity": "recommended", "risk": "prompt_contract_has_warnings", "fix": "review prompt warnings before render"})
    if _safe_int(viral_readiness.get("creative_score"), 0) < 70:
        warnings.append({"severity": "recommended", "risk": "viral_plan_low_score", "fix": "improve hook/retention plan before paid render"})
    if runtime_class in _LONG_RUNTIME_CLASSES and len(per_shot_qa) < 10:
        warnings.append({"severity": "recommended", "risk": "long_form_low_shot_count", "fix": "verify long-form graph splits every scene into 4-15s units"})
    return warnings[:8]


def _qa_confidence_score(*, brief_score: int, prompt_warning_count: int, viral_score: int, qa_node_count: int, warning_count: int) -> int:
    score = 25 + int(brief_score * 0.25) + int(viral_score * 0.25)
    score += min(20, qa_node_count * 2)
    score -= prompt_warning_count * 6
    score -= warning_count * 5
    return max(0, min(100, score))


def _issue(issue_tag: str, severity: str, detection: str, retry_action: str) -> dict[str, str]:
    return {
        "issue_tag": issue_tag,
        "severity": severity,
        "detection": detection,
        "retry_action": retry_action,
    }


def _mode(issue_tag: str, severity: str, why: str) -> dict[str, str]:
    return {"issue_tag": issue_tag, "severity": severity, "why": why}


def _subject(parsed: dict[str, Any], niche: str) -> str:
    subject = parsed.get("subject") or {}
    return str(subject.get("summary") or (subject.get("hints") or [niche])[0] or niche)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _has_blocking_warning(warnings: list[dict[str, str]]) -> bool:
    return any(item.get("severity") == "blocking" for item in warnings)


def _brain_id(*, user_idea: str, niche: str, duration_s: int, platform: str) -> str:
    raw = f"{user_idea}|{niche}|{duration_s}|{platform}|qa_retry"
    return "qa_retry_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


__all__ = ["build_output_qa_retry_brain"]
