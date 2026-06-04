"""Prompt Execution Contract V3.

Phase 3 turns the approved producer shot graph into model-specific prompt
contracts. It is still a planning layer: no LLM calls, no AtlasCloud video
calls, and no paid retries are performed here.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any


_SCHEMA_VERSION = "cinejelly.prompt_execution_contract.v3"
_MIN_UNIT_S = 4
_MAX_UNIT_S = 15
_LONG_FORM_CLASSES = {"micro_film", "short_film", "episode"}
_HERO_PURPOSES = {"attention", "proof", "conversion_or_takeaway", "commercial_story"}


def build_prompt_execution_contract_v3(
    *,
    user_idea: str,
    creative_brief_contract: dict[str, Any],
    creative_producer_v2: dict[str, Any],
    decision: dict[str, Any],
    seedance_prompt_formula: dict[str, Any],
    seedance_reference_allocation: dict[str, Any],
    model_route_strategy: dict[str, Any],
    llm_brain_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile every producer shot into an inspectable render prompt contract."""
    producer_graph = (creative_producer_v2 or {}).get("shot_graph") or {}
    nodes = list(producer_graph.get("nodes") or [])
    parsed = (creative_brief_contract or {}).get("parsed") or {}
    readiness = (creative_brief_contract or {}).get("readiness") or {}
    runtime_class = str(decision.get("runtime_class") or producer_graph.get("runtime_class") or "short")
    target_platform = str(decision.get("target_platform") or parsed.get("target_platform") or "tiktok")
    target_market = str(decision.get("target_market") or "auto")
    refs = _reference_counts(seedance_reference_allocation)
    ref_catalog = _reference_catalog(seedance_reference_allocation)
    formula_template = (seedance_prompt_formula or {}).get("niche_template") or {}
    formula_rules = list((seedance_prompt_formula or {}).get("rewrite_rules") or [])
    route_summary = (model_route_strategy or {}).get("summary") or {}
    seedance_execution = (model_route_strategy or {}).get("seedance_execution") or {}
    primary_model = str(route_summary.get("primary_visual_model") or "seedance_2_0_fast_t2v")
    selected_angle = (creative_producer_v2 or {}).get("selected_angle") or {}
    continuity_seed = (creative_producer_v2 or {}).get("continuity_bible_seed") or {}
    producer_qa = (creative_producer_v2 or {}).get("qa_contract") or {}

    compiled_shots = [
        _compiled_shot(
            node=node,
            index=index,
            user_idea=user_idea,
            parsed=parsed,
            target_platform=target_platform,
            target_market=target_market,
            runtime_class=runtime_class,
            refs=refs,
            ref_catalog=ref_catalog,
            formula_template=formula_template,
            formula_rules=formula_rules,
            selected_angle=selected_angle,
            continuity_seed=continuity_seed,
            producer_qa=producer_qa,
            primary_model=primary_model,
            seedance_execution=seedance_execution,
        )
        for index, node in enumerate(nodes)
    ]
    warnings = _contract_warnings(
        nodes=nodes,
        compiled_shots=compiled_shots,
        refs=refs,
        runtime_class=runtime_class,
        readiness=readiness,
        allocation=seedance_reference_allocation,
    )
    model_counts = Counter(str(item["model_key"]) for item in compiled_shots)
    mode_counts = Counter(str(item["render_mode"]) for item in compiled_shots)
    prompt_fingerprint = _fingerprint(compiled_shots)
    return {
        "schema_version": _SCHEMA_VERSION,
        "vendor_calls_performed": False,
        "paid_video_vendor_calls_allowed": False,
        "contract_id": f"prompt_contract_{prompt_fingerprint}",
        "strategy": "compile_one_model_specific_prompt_per_producer_shot_before_paid_render",
        "readiness": {
            "status": "ready_for_approval_render" if compiled_shots and not warnings else "needs_contract_review",
            "compiled_shot_count": len(compiled_shots),
            "warning_count": len(warnings),
            "brief_completeness_score": readiness.get("completeness_score"),
        },
        "input_contracts": {
            "creative_brief_schema": (creative_brief_contract or {}).get("schema_version"),
            "creative_producer_schema": (creative_producer_v2 or {}).get("schema_version"),
            "shot_graph_schema": producer_graph.get("schema_version"),
            "prompt_formula_schema": (seedance_prompt_formula or {}).get("schema_version"),
            "model_route_schema": (model_route_strategy or {}).get("schema_version"),
        },
        "model_plan": {
            "primary_visual_model": primary_model,
            "continuity_model": str(route_summary.get("continuity_model") or "seedance_2_0_fast_i2v"),
            "draft_visual_model": str(route_summary.get("draft_visual_model") or primary_model),
            "premium_visual_model": str(route_summary.get("premium_visual_model") or "seedance_2_0_ref"),
            "model_counts": dict(model_counts),
            "render_mode_counts": dict(mode_counts),
            "llm_text_brain": ((llm_brain_policy or {}).get("route_summary") or {}).get("primary_text_model"),
            "llm_cost_mode": ((llm_brain_policy or {}).get("route_summary") or {}).get("cost_mode"),
        },
        "prompt_rules": {
            "formula_order": list((seedance_prompt_formula or {}).get("formula") or []),
            "unit_duration_s": [_MIN_UNIT_S, _MAX_UNIT_S],
            "one_action_per_unit": True,
            "reference_binding_rule": "Name each reference job in the prompt; never rely on unlabeled uploaded assets.",
            "continuity_rule": "Carry previous final frame and continuity handoff for adjacent or long-form shots.",
            "negative_constraints": _negative_constraints(refs=refs, runtime_class=runtime_class),
            "rewrite_rules": formula_rules[:8],
        },
        "compiled_shots": compiled_shots,
        "qa_plan": _qa_plan(
            compiled_shots=compiled_shots,
            producer_qa=producer_qa,
            refs=refs,
            runtime_class=runtime_class,
        ),
        "cost_guard": {
            "planning_only": True,
            "vendor_calls_performed": False,
            "paid_render_locked_until_user_approval": True,
            "paid_retry_vendor_calls_allowed": False,
            "pro_or_premium_llm_selected": bool(((llm_brain_policy or {}).get("route_summary") or {}).get("pro_selected"))
            or bool(((llm_brain_policy or {}).get("route_summary") or {}).get("premium_selected")),
            "why": "Phase 3 compiles prompts and QA contracts only; render execution remains approval-gated.",
        },
        "warnings": warnings,
    }


def _compiled_shot(
    *,
    node: dict[str, Any],
    index: int,
    user_idea: str,
    parsed: dict[str, Any],
    target_platform: str,
    target_market: str,
    runtime_class: str,
    refs: dict[str, int],
    ref_catalog: dict[str, dict[str, str]],
    formula_template: dict[str, Any],
    formula_rules: list[str],
    selected_angle: dict[str, Any],
    continuity_seed: dict[str, Any],
    producer_qa: dict[str, Any],
    primary_model: str,
    seedance_execution: dict[str, Any],
) -> dict[str, Any]:
    duration_s = _unit_duration(node.get("duration_s"))
    handoff = node.get("continuity_handoff") or {}
    segment = node.get("seedance_segment_hint") or {}
    model_key, render_mode = _route_for_node(
        node=node,
        index=index,
        refs=refs,
        runtime_class=runtime_class,
        primary_model=primary_model,
        seedance_execution=seedance_execution,
    )
    reference_slots = _reference_slots(
        node=node,
        segment=segment,
        refs=refs,
        ref_catalog=ref_catalog,
        render_mode=render_mode,
        runtime_class=runtime_class,
    )
    qa_checks = _qa_checks(
        node=node,
        segment=segment,
        producer_qa=producer_qa,
        refs=refs,
        render_mode=render_mode,
        runtime_class=runtime_class,
    )
    prompt = _compile_prompt(
        node=node,
        segment=segment,
        user_idea=user_idea,
        parsed=parsed,
            selected_angle=selected_angle,
            continuity_seed=continuity_seed,
            formula_template=formula_template,
            formula_rules=formula_rules,
            refs=refs,
            reference_slots=reference_slots,
            target_platform=target_platform,
            target_market=target_market,
            runtime_class=runtime_class,
            duration_s=duration_s,
    )
    return {
        "shot_id": str(node.get("shot_id") or f"S{index + 1:03d}"),
        "beat_id": str(node.get("beat_id") or ""),
        "index": index,
        "duration_s": duration_s,
        "model_key": model_key,
        "render_mode": render_mode,
        "prompt": prompt,
        "negative_prompt": ", ".join(_negative_constraints(refs=refs, runtime_class=runtime_class)),
        "reference_jobs": list(node.get("reference_jobs") or []),
        "reference_slots": reference_slots,
        "model_parameters": {
            "duration_s": duration_s,
            "return_last_frame": bool(runtime_class in _LONG_FORM_CLASSES or handoff.get("from_previous_shot")),
            "requires_reference_upload": render_mode != "text_to_video",
            "seedance_unit_range_s": [_MIN_UNIT_S, _MAX_UNIT_S],
        },
        "qa_checks": qa_checks,
        "retry_policy": _retry_policy(model_key=model_key, render_mode=render_mode, runtime_class=runtime_class),
        "handoff": {
            "from_previous_shot": handoff.get("from_previous_shot"),
            "carry": list(handoff.get("carry") or []),
            "handoff_image": handoff.get("handoff_image"),
            "continuity_anchor": segment.get("continuity_anchor"),
        },
        "contract_checks": {
            "has_subject": bool(_subject_summary(parsed)),
            "has_action": bool(node.get("visual_intent") or ((segment.get("prompt_blocks") or {}).get("action"))),
            "has_camera": bool(node.get("camera_intent") or ((segment.get("prompt_blocks") or {}).get("camera"))),
            "duration_valid": _MIN_UNIT_S <= duration_s <= _MAX_UNIT_S,
            "references_valid_for_route": bool(render_mode == "text_to_video" or reference_slots),
        },
    }


def _route_for_node(
    *,
    node: dict[str, Any],
    index: int,
    refs: dict[str, int],
    runtime_class: str,
    primary_model: str,
    seedance_execution: dict[str, Any],
) -> tuple[str, str]:
    hint = str(node.get("model_route_hint") or "")
    segment_route = str((node.get("seedance_segment_hint") or {}).get("model_route") or "")
    purpose = str(node.get("purpose") or "")
    has_any_refs = bool(refs["images"] or refs["videos"] or refs["audios"] or refs["pinned_assets"])
    has_visual_refs = bool(refs["images"] or refs["videos"] or refs["pinned_assets"])
    has_previous = bool((node.get("continuity_handoff") or {}).get("from_previous_shot"))
    premium_hero = bool(seedance_execution.get("premium_ref_for_hero_shots")) and purpose in _HERO_PURPOSES

    if has_previous and runtime_class in _LONG_FORM_CLASSES and has_visual_refs:
        return "seedance_2_0_fast_i2v", "continuity_i2v"
    if premium_hero and has_visual_refs:
        return "seedance_2_0_ref", "reference_to_video"
    model_key = hint or segment_route or primary_model
    if not has_any_refs:
        return "seedance_2_0_fast_t2v", "text_to_video"
    if "t2v" in model_key:
        return model_key, "text_to_video"
    if "i2v" in model_key:
        return model_key, "image_to_video"
    if index > 0 and has_visual_refs and runtime_class in _LONG_FORM_CLASSES:
        return "seedance_2_0_fast_i2v", "continuity_i2v"
    return model_key, "reference_to_video"


def _reference_slots(
    *,
    node: dict[str, Any],
    segment: dict[str, Any],
    refs: dict[str, int],
    ref_catalog: dict[str, dict[str, str]],
    render_mode: str,
    runtime_class: str,
) -> list[dict[str, str]]:
    if render_mode == "text_to_video":
        return []
    tags = [str(item) for item in (segment.get("use_refs") or []) if str(item).strip()]
    if not tags:
        tags = _tags_for_jobs(list(node.get("reference_jobs") or []), ref_catalog)
    if runtime_class in _LONG_FORM_CLASSES and (node.get("continuity_handoff") or {}).get("from_previous_shot"):
        tags.append("previous_scene_final_frame")
    slots: list[dict[str, str]] = []
    for tag in list(dict.fromkeys(tags)):
        item = ref_catalog.get(tag)
        if not item:
            continue
        slots.append({
            "tag": tag,
            "asset_type": item.get("asset_type", "reference"),
            "role": item.get("role", "reference"),
            "job": item.get("job", "guide this shot"),
            "required_for": render_mode,
        })
    if slots:
        return slots[:12]
    if refs["images"] or refs["pinned_assets"]:
        return _first_catalog_slots(ref_catalog, {"image", "pinned"}, 3, render_mode)
    if refs["videos"]:
        return _first_catalog_slots(ref_catalog, {"video"}, 2, render_mode)
    if refs["audios"]:
        return _first_catalog_slots(ref_catalog, {"audio"}, 1, render_mode)
    return []


def _tags_for_jobs(jobs: list[str], ref_catalog: dict[str, dict[str, str]]) -> list[str]:
    wanted_roles: set[str] = set()
    for job in jobs:
        key = str(job)
        if "identity" in key or "product" in key:
            wanted_roles.update({"approved_asset_anchor", "character_anchor", "product_hero", "product_detail"})
        if "motion" in key or "camera" in key:
            wanted_roles.update({"camera_motion", "motion_style", "shot_pacing"})
        if "audio" in key or "voice" in key or "rhythm" in key:
            wanted_roles.update({"lip_sync_source", "beat_reference", "sfx_layer"})
    return [
        tag
        for tag, item in ref_catalog.items()
        if item.get("role") in wanted_roles
    ][:8]


def _compile_prompt(
    *,
    node: dict[str, Any],
    segment: dict[str, Any],
    user_idea: str,
    parsed: dict[str, Any],
    selected_angle: dict[str, Any],
    continuity_seed: dict[str, Any],
    formula_template: dict[str, Any],
    formula_rules: list[str],
    refs: dict[str, int],
    reference_slots: list[dict[str, str]],
    target_platform: str,
    target_market: str,
    runtime_class: str,
    duration_s: int,
) -> str:
    prompt_blocks = segment.get("prompt_blocks") or {}
    subject = _subject_summary(parsed) or _clip(user_idea, 120)
    reference_line = _reference_line(reference_slots)
    story_intent = (
        prompt_blocks.get("story_intent")
        or formula_template.get("story_intent")
        or selected_angle.get("story_engine")
        or node.get("purpose")
        or "make the viewer promise visually readable"
    )
    action = (
        prompt_blocks.get("action")
        or node.get("visual_intent")
        or node.get("script")
        or formula_template.get("action")
        or subject
    )
    camera = (
        prompt_blocks.get("camera")
        or node.get("camera_intent")
        or formula_template.get("camera")
        or "motivated cinematic camera movement"
    )
    sound = prompt_blocks.get("sound") or formula_template.get("sound") or "natural foley and restrained music"
    handoff = node.get("continuity_handoff") or {}
    carry = ", ".join(str(item) for item in list(handoff.get("carry") or [])[:4])
    constraints = "; ".join(_negative_constraints(refs=refs, runtime_class=runtime_class)[:5])
    rules = "; ".join(str(item) for item in formula_rules[:3])
    lines = [
        f"[REFERENCE JOBS] {reference_line}",
        f"[TIMELINE] {duration_s}s Seedance 2.0 unit for {target_platform}; one physically filmable action.",
        f"[SUBJECT] {subject}.",
        f"[STORY INTENT] {_clip(str(story_intent), 240)}.",
        f"[ACTION] {_clip(str(action), 320)}.",
        f"[CAMERA] {_clip(str(camera), 220)}.",
        f"[SOUND] {_clip(str(sound), 180)}.",
        f"[CONTINUITY] Preserve {carry or continuity_seed.get('story_engine') or 'the same subject promise and visual style'}. Market: {target_market}.",
        f"[SHOT CONTRACT] {_clip(str(node.get('script') or selected_angle.get('retention_move') or ''), 260)}",
        f"[CONSTRAINTS] {constraints}.",
    ]
    if rules:
        lines.append(f"[REWRITE RULES] {rules}.")
    return _clip(" ".join(line for line in lines if line.strip()), 1600)


def _qa_checks(
    *,
    node: dict[str, Any],
    segment: dict[str, Any],
    producer_qa: dict[str, Any],
    refs: dict[str, int],
    render_mode: str,
    runtime_class: str,
) -> list[str]:
    checks = [
        "prompt_adherence",
        "single_action_readability",
        "duration_4_15s",
        "camera_motion_matches_prompt",
        "no_unrequested_text_or_logo",
    ]
    checks.extend(str(item) for item in producer_qa.get("checks") or [])
    checks.extend(str(item) for item in segment.get("qa_checks") or [])
    if render_mode != "text_to_video" or refs["images"] or refs["pinned_assets"]:
        checks.extend(["reference_identity_or_product_match", "reference_style_match"])
    if (node.get("continuity_handoff") or {}).get("from_previous_shot") or runtime_class in _LONG_FORM_CLASSES:
        checks.extend(["continuity_handoff_match", "previous_final_frame_consistency"])
    return list(dict.fromkeys(checks))[:16]


def _qa_plan(
    *,
    compiled_shots: list[dict[str, Any]],
    producer_qa: dict[str, Any],
    refs: dict[str, int],
    runtime_class: str,
) -> dict[str, Any]:
    checks = ["prompt_adherence", "duration", "technical_artifacts", "motion_physics"]
    checks.extend(str(item) for item in producer_qa.get("checks") or [])
    if refs["images"] or refs["pinned_assets"]:
        checks.append("identity_or_product_consistency")
    if runtime_class in _LONG_FORM_CLASSES:
        checks.extend(["cross_shot_continuity", "handoff_frame_consistency", "assembly_pacing"])
    return {
        "checks": list(dict.fromkeys(checks))[:18],
        "hard_failures": list(dict.fromkeys([
            "missing output video",
            "wrong subject/product",
            "severe identity drift",
            "unreadable generated text",
            "multi-action blob shot",
            "shot duration outside 4-15s",
            *list(producer_qa.get("hard_failures") or []),
        ])),
        "review_scope": "per_shot_then_sequence",
        "compiled_shots_to_review": len(compiled_shots),
    }


def _retry_policy(*, model_key: str, render_mode: str, runtime_class: str) -> dict[str, Any]:
    return {
        "retry_scope": "shot_node",
        "max_planned_retries": 2,
        "paid_retry_vendor_calls_allowed_in_contract": False,
        "first_retry": "rewrite prompt by simplifying to one action and tightening reference jobs",
        "second_retry": (
            "switch to previous-final-frame i2v continuity route"
            if runtime_class in _LONG_FORM_CLASSES
            else "switch between fast_ref and fast_i2v only after user-approved render budget"
        ),
        "fallback_model_candidate": "seedance_2_0_fast_i2v" if render_mode != "text_to_video" else "seedance_2_0_fast_t2v",
        "current_model": model_key,
    }


def _contract_warnings(
    *,
    nodes: list[dict[str, Any]],
    compiled_shots: list[dict[str, Any]],
    refs: dict[str, int],
    runtime_class: str,
    readiness: dict[str, Any],
    allocation: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    if not nodes:
        warnings.append("shot_graph_empty")
    if readiness.get("should_ask_before_paid_render"):
        warnings.append("brief_has_questions_before_paid_render")
    if runtime_class in _LONG_FORM_CLASSES and refs["images"] + refs["pinned_assets"] == 0:
        warnings.append("long_form_without_visual_anchor")
    warnings.extend(str(item) for item in allocation.get("warnings") or [])
    for shot in compiled_shots:
        checks = shot.get("contract_checks") or {}
        if not checks.get("duration_valid"):
            warnings.append(f"{shot.get('shot_id')}:duration_outside_seedance_unit_range")
        if not checks.get("has_action") or not checks.get("has_camera"):
            warnings.append(f"{shot.get('shot_id')}:prompt_missing_action_or_camera")
        if not checks.get("references_valid_for_route"):
            warnings.append(f"{shot.get('shot_id')}:reference_route_without_slots")
    return list(dict.fromkeys(warnings))[:24]


def _negative_constraints(*, refs: dict[str, int], runtime_class: str) -> list[str]:
    constraints = [
        "unreadable generated text",
        "extra logos or subtitles",
        "warped hands or faces",
        "camera teleport",
        "multiple unrelated actions",
        "generic stock-video filler",
    ]
    if refs.get("images") or refs.get("pinned_assets"):
        constraints.extend(["identity drift", "wrong product geometry", "label or packaging mismatch"])
    if runtime_class in _LONG_FORM_CLASSES:
        constraints.extend(["scene reset", "broken eyeline", "handoff mismatch"])
    return list(dict.fromkeys(constraints))


def _reference_catalog(allocation: dict[str, Any]) -> dict[str, dict[str, str]]:
    catalog: dict[str, dict[str, str]] = {}
    for key, asset_type in (
        ("image_role_plan", "image"),
        ("video_role_plan", "video"),
        ("audio_role_plan", "audio"),
    ):
        for item in allocation.get(key) or []:
            tag = str(item.get("tag") or "").strip()
            if not tag:
                continue
            catalog[tag] = {
                "asset_type": asset_type,
                "role": str(item.get("role") or asset_type),
                "job": str(item.get("job") or "guide this shot"),
            }
    if (allocation.get("long_form_handoff_policy") or {}).get("enabled"):
        catalog["previous_scene_final_frame"] = {
            "asset_type": "handoff_frame",
            "role": "continuity_anchor",
            "job": "match accepted final frame pose, layout, lighting, and scene state",
        }
    return catalog


def _first_catalog_slots(
    ref_catalog: dict[str, dict[str, str]],
    asset_types: set[str],
    limit: int,
    render_mode: str,
) -> list[dict[str, str]]:
    slots = []
    for tag, item in ref_catalog.items():
        if item.get("asset_type") not in asset_types:
            continue
        slots.append({
            "tag": tag,
            "asset_type": item.get("asset_type", "reference"),
            "role": item.get("role", "reference"),
            "job": item.get("job", "guide this shot"),
            "required_for": render_mode,
        })
        if len(slots) >= limit:
            break
    return slots


def _reference_counts(allocation: dict[str, Any]) -> dict[str, int]:
    counts = allocation.get("reference_counts") or {}
    return {
        "images": _safe_int(counts.get("images")),
        "videos": _safe_int(counts.get("videos")),
        "audios": _safe_int(counts.get("audios")),
        "pinned_assets": _safe_int(counts.get("pinned_assets")),
    }


def _reference_line(reference_slots: list[dict[str, str]]) -> str:
    if not reference_slots:
        return "no uploaded reference; use prompt-only generation conservatively"
    return "; ".join(
        f"{item['tag']} as {item['role']} ({item['job']})"
        for item in reference_slots[:6]
    )


def _subject_summary(parsed: dict[str, Any]) -> str:
    subject = parsed.get("subject") or {}
    return str(subject.get("summary") or "").strip()


def _unit_duration(value: Any) -> int:
    return max(_MIN_UNIT_S, min(_MAX_UNIT_S, _safe_int(value, default=12)))


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _fingerprint(compiled_shots: list[dict[str, Any]]) -> str:
    raw = "|".join(
        f"{shot.get('shot_id')}:{shot.get('model_key')}:{shot.get('duration_s')}:{hashlib.sha1(str(shot.get('prompt') or '').encode('utf-8')).hexdigest()[:10]}"
        for shot in compiled_shots
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _clip(value: str, limit: int) -> str:
    value = " ".join((value or "").split())
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


__all__ = ["build_prompt_execution_contract_v3"]
