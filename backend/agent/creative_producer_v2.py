"""Creative Producer + Script/Shot Graph 2.0.

This Phase 2 layer sits after Phase 1 input understanding and before any paid
render. It creates multiple producer angles, selects the strongest one, and
builds a script beat graph plus shot graph that can be inspected by UI,
preflight, and future prompt compilers.
"""
from __future__ import annotations

import hashlib
from typing import Any


_MIN_RENDER_UNIT_S = 4
_MAX_RENDER_UNIT_S = 15

_ANGLE_LIBRARY: list[dict[str, Any]] = [
    {
        "angle_id": "proof_first_transformation",
        "label": "Proof-first transformation",
        "best_intents": {"sell_product", "review_proof"},
        "best_niches": {"beauty", "food", "ugc_review", "ecommerce_catalog", "tech", "app_saas", "fitness"},
        "hook": "Show the result or contradiction before explaining anything.",
        "story_engine": "result -> problem -> proof -> transformation -> soft CTA",
        "retention_move": "open-loop proof: viewer sees outcome, then watches to understand why",
    },
    {
        "angle_id": "cinematic_desire_reveal",
        "label": "Cinematic desire reveal",
        "best_intents": {"sell_product", "brand_story", "general_video"},
        "best_niches": {"beauty", "fashion", "restaurant_hospitality", "food", "automotive", "travel", "real_estate"},
        "hook": "Open on texture, atmosphere, or a premium object clue.",
        "story_engine": "sensory clue -> ritual/process -> reveal -> aspirational payoff",
        "retention_move": "withhold the full hero reveal until the viewer has felt the world",
    },
    {
        "angle_id": "short_drama_reversal",
        "label": "Short-drama reversal",
        "best_intents": {"entertain", "brand_story"},
        "best_niches": {"drama", "documentary", "lifestyle", "restaurant_hospitality", "travel"},
        "hook": "Start with a visual contradiction or emotional decision.",
        "story_engine": "cold open -> conflict -> escalation -> reveal -> emotional aftertaste",
        "retention_move": "each scene ends with a question that forces the next scene",
    },
    {
        "angle_id": "clarity_explainer",
        "label": "Clarity explainer",
        "best_intents": {"educate", "brand_story"},
        "best_niches": {"education", "finance_education", "medical_wellness", "documentary", "app_saas"},
        "hook": "Begin with the viewer's wrong assumption or urgent question.",
        "story_engine": "question -> misconception -> visual explanation -> safe takeaway",
        "retention_move": "replace abstract explanation with visible examples every beat",
    },
    {
        "angle_id": "fast_social_challenge",
        "label": "Fast social challenge",
        "best_intents": {"review_proof", "entertain", "general_video"},
        "best_niches": {"ugc_review", "fitness", "gaming", "fashion", "food", "travel", "asmr"},
        "hook": "Use immediate motion, challenge framing, or before/after contrast.",
        "story_engine": "challenge -> attempts -> proof spike -> payoff loop",
        "retention_move": "visible escalation every 4-8 seconds",
    },
]


def build_creative_producer_v2(
    *,
    user_idea: str,
    creative_brief_contract: dict[str, Any],
    decision: dict[str, Any],
    creative_treatment_search: dict[str, Any],
    seedance_segment_inspector: dict[str, Any] | None = None,
    reference_counts: dict[str, int] | None = None,
    revision_notes: str | None = None,
) -> dict[str, Any]:
    """Return a non-paid creative producer contract for any runtime/niche."""
    refs = _normalize_refs(reference_counts or {})
    parsed = creative_brief_contract.get("parsed") or {}
    readiness = creative_brief_contract.get("readiness") or {}
    output_intent = str(parsed.get("output_intent") or "general_video")
    goals = parsed.get("goals") or []
    style_signals = parsed.get("style_signals") or []
    niche = str(decision.get("niche") or "ugc_review")
    runtime_class = str(decision.get("runtime_class") or "short")
    duration_s = int(decision.get("target_duration_s") or _duration_from_contract(parsed) or 30)
    target_platform = str(decision.get("target_platform") or parsed.get("target_platform") or "tiktok")
    selected_treatment_id = str(creative_treatment_search.get("selected_treatment_id") or "")
    treatment_label = str(creative_treatment_search.get("selected_label") or "")
    angles = [
        _score_angle(
            angle=angle,
            output_intent=output_intent,
            niche=niche,
            runtime_class=runtime_class,
            duration_s=duration_s,
            refs=refs,
            style_signals=style_signals,
            selected_treatment_id=selected_treatment_id,
            completeness_score=int(readiness.get("completeness_score") or 0),
        )
        for angle in _ANGLE_LIBRARY
    ]
    angles.sort(key=lambda item: (item["rank_score"], item["score"]), reverse=True)
    selected = angles[0] if angles else {}
    script_beats = _script_beats(
        selected_angle=selected,
        output_intent=output_intent,
        niche=niche,
        runtime_class=runtime_class,
        duration_s=duration_s,
        target_platform=target_platform,
        creative_brief_contract=creative_brief_contract,
        treatment_label=treatment_label,
        revision_notes=revision_notes or "",
    )
    shot_graph = _shot_graph(
        script_beats=script_beats,
        selected_angle=selected,
        runtime_class=runtime_class,
        duration_s=duration_s,
        refs=refs,
        seedance_segment_inspector=seedance_segment_inspector or {},
    )
    producer_id = _producer_id(user_idea, selected.get("angle_id"), duration_s, target_platform)
    return {
        "schema_version": "cinejelly.creative_producer_v2.v1",
        "vendor_calls_performed": False,
        "paid_video_vendor_calls_allowed": False,
        "producer_id": producer_id,
        "strategy": "rank_angles_then_build_script_and_shot_graph_before_paid_render",
        "selected_angle": selected,
        "angle_candidates": angles,
        "script_beats": script_beats,
        "shot_graph": shot_graph,
        "continuity_bible_seed": _continuity_bible_seed(
            user_idea=user_idea,
            selected_angle=selected,
            creative_brief_contract=creative_brief_contract,
            runtime_class=runtime_class,
            duration_s=duration_s,
            refs=refs,
        ),
        "prompt_compiler_handoff": _prompt_compiler_handoff(selected, shot_graph, refs),
        "qa_contract": _qa_contract(
            selected_angle=selected,
            runtime_class=runtime_class,
            duration_s=duration_s,
            refs=refs,
            output_intent=output_intent,
        ),
    }


def _score_angle(
    *,
    angle: dict[str, Any],
    output_intent: str,
    niche: str,
    runtime_class: str,
    duration_s: int,
    refs: dict[str, int],
    style_signals: list[dict[str, Any]],
    selected_treatment_id: str,
    completeness_score: int,
) -> dict[str, Any]:
    score = 50
    reasons: list[str] = []
    risks: list[str] = []
    if output_intent in angle["best_intents"]:
        score += 18
        reasons.append("intent_fit")
    else:
        score -= 3
        risks.append("weaker_intent_fit")
    if niche in angle["best_niches"]:
        score += 16
        reasons.append("niche_fit")
    else:
        score -= 4
        risks.append("weaker_niche_fit")
    if runtime_class in {"short_film", "episode", "micro_film"}:
        if angle["angle_id"] in {"short_drama_reversal", "clarity_explainer", "cinematic_desire_reveal"}:
            score += 10
            reasons.append("runtime_structure_fit")
        else:
            score -= 5
            risks.append("angle_may_need_more_scene_structure")
    else:
        if angle["angle_id"] in {"proof_first_transformation", "fast_social_challenge", "cinematic_desire_reveal"}:
            score += 8
            reasons.append("short_form_retention_fit")
    style_keys = {str(item.get("key") or "") for item in style_signals}
    if "cinematic" in style_keys and angle["angle_id"] in {"cinematic_desire_reveal", "short_drama_reversal"}:
        score += 6
        reasons.append("cinematic_style_fit")
    if "ugc" in style_keys and angle["angle_id"] == "proof_first_transformation":
        score += 6
        reasons.append("ugc_style_fit")
    if refs["images"] or refs["pinned_assets"]:
        score += 5
        reasons.append("visual_refs_available")
    elif duration_s >= 180:
        score -= 8
        risks.append("long_form_without_visual_anchor")
    if refs["videos"]:
        score += 3
        reasons.append("motion_reference_available")
    if completeness_score < 55:
        score -= 12
        risks.append("brief_incomplete")
    if selected_treatment_id:
        if _angle_matches_treatment(angle["angle_id"], selected_treatment_id):
            score += 5
            reasons.append("matches_selected_treatment")
    fit_score = max(0, min(100, score))
    return {
        "angle_id": angle["angle_id"],
        "label": angle["label"],
        "score": fit_score,
        "rank_score": score,
        "risk_level": "low" if fit_score >= 82 and not risks else "medium" if fit_score >= 65 else "high",
        "selection_reason": ", ".join(reasons[:5]) if reasons else "fallback_angle",
        "reasons": reasons,
        "risks": risks,
        "hook": angle["hook"],
        "story_engine": angle["story_engine"],
        "retention_move": angle["retention_move"],
    }


def _script_beats(
    *,
    selected_angle: dict[str, Any],
    output_intent: str,
    niche: str,
    runtime_class: str,
    duration_s: int,
    target_platform: str,
    creative_brief_contract: dict[str, Any],
    treatment_label: str,
    revision_notes: str,
) -> list[dict[str, Any]]:
    beat_names = _fit_beat_palette(
        _beat_palette(output_intent, runtime_class),
        duration_s=duration_s,
        output_intent=output_intent,
    )
    durations = _split_duration(duration_s, len(beat_names), runtime_class=runtime_class)
    subject = ((creative_brief_contract.get("parsed") or {}).get("subject") or {}).get("summary") or niche
    beats: list[dict[str, Any]] = []
    cursor = 0
    for idx, (name, dur) in enumerate(zip(beat_names, durations)):
        start_s = cursor
        end_s = cursor + dur
        cursor = end_s
        purpose = _beat_purpose(name, output_intent)
        beats.append({
            "beat_id": f"B{idx + 1:02d}",
            "index": idx,
            "beat": name,
            "start_s": start_s,
            "end_s": end_s,
            "duration_s": dur,
            "purpose": purpose,
            "script": _beat_script(
                beat=name,
                subject=str(subject),
                selected_angle=selected_angle,
                treatment_label=treatment_label,
                target_platform=target_platform,
                revision_notes=revision_notes,
            ),
            "turn": _beat_turn(name, idx, len(beat_names)),
            "retention_device": _retention_device(name, selected_angle),
        })
    return beats


def _shot_graph(
    *,
    script_beats: list[dict[str, Any]],
    selected_angle: dict[str, Any],
    runtime_class: str,
    duration_s: int,
    refs: dict[str, int],
    seedance_segment_inspector: dict[str, Any],
) -> dict[str, Any]:
    segments = seedance_segment_inspector.get("segments") or []
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    previous_id = ""
    shot_index = 0
    for beat in script_beats:
        units = _units_for_beat(int(beat["duration_s"]), runtime_class)
        for unit_idx, unit_duration in enumerate(units):
            shot_index += 1
            node_id = f"S{shot_index:03d}"
            segment = segments[shot_index - 1] if shot_index - 1 < len(segments) else {}
            nodes.append({
                "shot_id": node_id,
                "beat_id": beat["beat_id"],
                "index": shot_index - 1,
                "duration_s": unit_duration,
                "purpose": beat["purpose"],
                "script": beat["script"],
                "visual_intent": _visual_intent(beat, unit_idx, selected_angle),
                "camera_intent": _camera_intent(beat, unit_idx, selected_angle),
                "reference_jobs": _reference_jobs(refs, beat, unit_idx),
                "model_route_hint": _model_route_hint(refs, unit_duration),
                "seedance_segment_hint": segment,
                "continuity_handoff": {
                    "from_previous_shot": previous_id or None,
                    "carry": _continuity_carry(beat, refs),
                    "handoff_image": beat["turn"],
                },
            })
            if previous_id:
                edges.append({"source": previous_id, "target": node_id, "relation": "continues_to"})
            previous_id = node_id
    return {
        "schema_version": "cinejelly.script_shot_graph.v2",
        "runtime_class": runtime_class,
        "duration_s": duration_s,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "render_unit_policy": {
            "min_unit_s": _MIN_RENDER_UNIT_S,
            "max_unit_s": _MAX_RENDER_UNIT_S,
            "one_action_per_unit": True,
            "long_form_resume_scope": "shot",
        },
    }


def _continuity_bible_seed(
    *,
    user_idea: str,
    selected_angle: dict[str, Any],
    creative_brief_contract: dict[str, Any],
    runtime_class: str,
    duration_s: int,
    refs: dict[str, int],
) -> dict[str, Any]:
    parsed = creative_brief_contract.get("parsed") or {}
    subject = parsed.get("subject") or {}
    return {
        "title_seed": _clip(str(subject.get("summary") or selected_angle.get("label") or "Autonomous video"), 80),
        "logline_seed": _clip(user_idea, 220),
        "angle": selected_angle.get("label"),
        "story_engine": selected_angle.get("story_engine"),
        "runtime_class": runtime_class,
        "duration_s": duration_s,
        "must_preserve": _must_preserve(parsed, refs),
        "must_avoid": [
            "unreadable generated text",
            "identity/product drift",
            "unmotivated scene reset",
            "generic stock-video filler",
        ],
    }


def _prompt_compiler_handoff(selected_angle: dict[str, Any], shot_graph: dict[str, Any], refs: dict[str, int]) -> dict[str, Any]:
    return {
        "selected_angle_id": selected_angle.get("angle_id"),
        "prompt_formula": [
            "subject",
            "action",
            "setting",
            "camera",
            "lighting",
            "motion",
            "reference role",
            "negative constraints",
        ],
        "shot_count": shot_graph.get("node_count"),
        "reference_policy": _reference_policy(refs),
        "compiler_rule": "compile one Seedance/Wan/audio prompt per shot graph node; never use one generic prompt for a multi-beat story",
    }


def _qa_contract(
    *,
    selected_angle: dict[str, Any],
    runtime_class: str,
    duration_s: int,
    refs: dict[str, int],
    output_intent: str,
) -> dict[str, Any]:
    checks = ["prompt_adherence", "duration", "motion_physics", "text_artifacts"]
    if refs["images"] or refs["pinned_assets"]:
        checks.extend(["identity_consistency", "reference_style_match"])
    if output_intent in {"sell_product", "review_proof"}:
        checks.append("product_recognition")
    if runtime_class not in {"short", "sequence"} or duration_s >= 180:
        checks.extend(["scene_continuity", "handoff_consistency", "assembly_pacing"])
    return {
        "angle_id": selected_angle.get("angle_id"),
        "checks": checks,
        "hard_failures": [
            "missing output video",
            "wrong subject/product",
            "unsafe or blocked content",
            "severe identity drift across adjacent shots",
        ],
        "retry_scope": "shot_node",
    }


def _beat_palette(output_intent: str, runtime_class: str) -> list[str]:
    if runtime_class in {"short_film", "episode"}:
        if output_intent in {"entertain", "brand_story"}:
            return ["Cold open", "Setup", "Conflict", "Escalation", "Reveal", "Aftertaste"]
        return ["Question", "Context", "Proof", "Human beat", "Takeaway", "Final image"]
    if output_intent in {"sell_product", "review_proof"}:
        return ["Hook", "Problem", "Proof", "Transformation", "CTA"]
    if output_intent == "educate":
        return ["Question", "Misconception", "Explanation", "Example", "Takeaway"]
    if output_intent in {"entertain", "brand_story"}:
        return ["Hook", "Setup", "Tension", "Reveal", "Payoff"]
    return ["Hook", "Value", "Proof", "Payoff"]


def _fit_beat_palette(beat_names: list[str], *, duration_s: int, output_intent: str) -> list[str]:
    """Keep beat count compatible with the minimum render-unit duration."""
    if not beat_names:
        return []
    max_beats = max(1, duration_s // _MIN_RENDER_UNIT_S)
    if len(beat_names) <= max_beats:
        return beat_names
    priorities = _compressed_beat_priorities(output_intent)
    chosen: list[str] = []
    lower_to_original = {beat.lower(): beat for beat in beat_names}
    for key in priorities:
        beat = lower_to_original.get(key.lower())
        if beat and beat not in chosen:
            chosen.append(beat)
        if len(chosen) >= max_beats:
            break
    for beat in beat_names:
        if len(chosen) >= max_beats:
            break
        if beat not in chosen:
            chosen.append(beat)
    chosen.sort(key=beat_names.index)
    return chosen


def _compressed_beat_priorities(output_intent: str) -> list[str]:
    if output_intent in {"sell_product", "review_proof"}:
        return ["Hook", "Proof", "CTA", "Transformation", "Problem"]
    if output_intent == "educate":
        return ["Question", "Explanation", "Takeaway", "Example", "Misconception"]
    if output_intent in {"entertain", "brand_story"}:
        return ["Cold open", "Hook", "Conflict", "Tension", "Reveal", "Payoff", "Aftertaste"]
    return ["Hook", "Proof", "Payoff", "Value"]


def _split_duration(total_s: int, count: int, *, runtime_class: str) -> list[int]:
    if count <= 0:
        return []
    if total_s <= 0:
        total_s = 30
    total_s = max(total_s, count * _MIN_RENDER_UNIT_S)
    if runtime_class in {"short", "sequence"}:
        weights = [0.13, 0.22, 0.28, 0.24, 0.13][:count]
    else:
        weights = [1 / count for _ in range(count)]
    if len(weights) < count:
        weights.extend([1 / count for _ in range(count - len(weights))])
    weights = weights[:count]
    weight_sum = sum(weights) or 1
    normalized_weights = [weight / weight_sum for weight in weights]
    raw = [max(_MIN_RENDER_UNIT_S, int(round(total_s * w))) for w in normalized_weights]
    diff = total_s - sum(raw)
    idx = 0
    while diff != 0:
        step = 1 if diff > 0 else -1
        if raw[idx % count] + step >= _MIN_RENDER_UNIT_S:
            raw[idx % count] += step
            diff -= step
        idx += 1
    return raw


def _units_for_beat(duration_s: int, runtime_class: str) -> list[int]:
    if runtime_class in {"short", "sequence"} and duration_s <= _MAX_RENDER_UNIT_S:
        return [max(_MIN_RENDER_UNIT_S, duration_s)]
    units: list[int] = []
    remaining = max(_MIN_RENDER_UNIT_S, duration_s)
    while remaining > 0:
        unit = min(_MAX_RENDER_UNIT_S, remaining)
        if remaining - unit and remaining - unit < _MIN_RENDER_UNIT_S:
            unit = max(_MIN_RENDER_UNIT_S, unit - (_MIN_RENDER_UNIT_S - (remaining - unit)))
        units.append(unit)
        remaining -= unit
    return units


def _beat_purpose(beat: str, output_intent: str) -> str:
    key = beat.lower()
    if "hook" in key or "cold" in key or "question" in key:
        return "attention"
    if "proof" in key or "example" in key or "explanation" in key:
        return "proof"
    if "cta" in key or "takeaway" in key:
        return "conversion_or_takeaway"
    if "conflict" in key or "tension" in key or "escalation" in key:
        return "tension"
    if output_intent == "sell_product":
        return "commercial_story"
    return "story_progression"


def _beat_script(
    *,
    beat: str,
    subject: str,
    selected_angle: dict[str, Any],
    treatment_label: str,
    target_platform: str,
    revision_notes: str,
) -> str:
    base = (
        f"{beat}: use {selected_angle.get('label') or 'selected angle'} for {subject}; "
        f"{selected_angle.get('retention_move') or 'keep visible change on screen'}."
    )
    if treatment_label:
        base += f" Director treatment: {treatment_label}."
    if target_platform in {"tiktok", "reels", "youtube_short"}:
        base += " Keep the beat readable on a vertical mobile feed."
    if revision_notes:
        base += f" Revision focus: {_clip(revision_notes, 140)}."
    return _clip(base, 320)


def _beat_turn(beat: str, idx: int, count: int) -> str:
    if idx == count - 1:
        return "Close on the strongest final image and make the viewer remember the promise."
    if idx == 0:
        return "End before answering the open question."
    if "proof" in beat.lower():
        return "Make the proof visible, then cut before over-explaining."
    return "Create a visual reason to continue to the next beat."


def _retention_device(beat: str, selected_angle: dict[str, Any]) -> str:
    if "hook" in beat.lower() or "cold" in beat.lower():
        return str(selected_angle.get("hook") or "visual interruption")
    return str(selected_angle.get("retention_move") or "visible change")


def _visual_intent(beat: dict[str, Any], unit_idx: int, selected_angle: dict[str, Any]) -> str:
    prefix = "primary" if unit_idx == 0 else "continuation"
    return _clip(f"{prefix} visual for {beat['beat']}: {beat['script']}", 360)


def _camera_intent(beat: dict[str, Any], unit_idx: int, selected_angle: dict[str, Any]) -> str:
    purpose = str(beat.get("purpose") or "")
    if purpose == "attention":
        return "ECU/CU, immediate readable action, pattern interrupt framing"
    if purpose == "proof":
        return "macro/detail coverage, stable enough to verify the claim"
    if purpose == "tension":
        return "reaction close-up, motivated push-in, continuity-aware eyeline"
    if unit_idx > 0:
        return "continue previous movement with a clear handoff"
    return "medium-to-close motivated camera movement"


def _reference_jobs(refs: dict[str, int], beat: dict[str, Any], unit_idx: int) -> list[str]:
    jobs: list[str] = []
    if refs["images"] or refs["pinned_assets"]:
        jobs.append("identity_or_product_anchor")
    if refs["videos"] and unit_idx == 0:
        jobs.append("motion_or_camera_reference")
    if refs["audios"] and beat.get("purpose") in {"attention", "tension"}:
        jobs.append("audio_rhythm_or_voice_reference")
    if not jobs:
        jobs.append("style_from_prompt_only")
    return jobs


def _model_route_hint(refs: dict[str, int], unit_duration: int) -> str:
    if refs["videos"] or refs["audios"] or refs["images"] + refs["pinned_assets"] > 1:
        return "seedance_2_0_fast_ref"
    if refs["images"] or refs["pinned_assets"]:
        return "seedance_2_0_fast_i2v"
    return "seedance_2_0_fast_t2v"


def _continuity_carry(beat: dict[str, Any], refs: dict[str, int]) -> list[str]:
    carry = ["same visual style", "same subject promise"]
    if refs["images"] or refs["pinned_assets"]:
        carry.append("reference identity/product")
    if beat.get("purpose") == "tension":
        carry.append("emotional state")
    return carry


def _must_preserve(parsed: dict[str, Any], refs: dict[str, int]) -> list[str]:
    out = ["viewer promise", "selected producer angle"]
    subject = parsed.get("subject") or {}
    if subject.get("summary"):
        out.append(f"subject: {subject['summary']}")
    if refs["images"] or refs["pinned_assets"]:
        out.append("visual reference identity/style")
    return out


def _reference_policy(refs: dict[str, int]) -> list[str]:
    policy = []
    if refs["images"] or refs["pinned_assets"]:
        policy.append("bind product/character/style references before prompt expansion")
    if refs["videos"]:
        policy.append("use video refs for camera/motion, not identity unless labeled")
    if refs["audios"]:
        policy.append("use audio refs for rhythm/voice/SFX lane")
    if not policy:
        policy.append("text-only route must avoid top-tier consistency claims")
    return policy


def _angle_matches_treatment(angle_id: str, treatment_id: str) -> bool:
    pairs = {
        "proof_first_transformation": {"proof_first_ugc"},
        "cinematic_desire_reveal": {"cinematic_premium"},
        "short_drama_reversal": {"short_drama_arc"},
        "clarity_explainer": {"documentary_testimonial"},
        "fast_social_challenge": {"fast_social_hook"},
    }
    return treatment_id in pairs.get(angle_id, set())


def _duration_from_contract(parsed: dict[str, Any]) -> int:
    duration = parsed.get("duration") or {}
    try:
        return int(duration.get("requested_s") or 0)
    except (TypeError, ValueError):
        return 0


def _normalize_refs(counts: dict[str, int]) -> dict[str, int]:
    out = {}
    for key in ("images", "videos", "audios", "pinned_assets"):
        try:
            out[key] = max(0, int(counts.get(key) or 0))
        except (TypeError, ValueError):
            out[key] = 0
    return out


def _producer_id(user_idea: str, angle_id: Any, duration_s: int, target_platform: str) -> str:
    raw = f"{user_idea}|{angle_id}|{duration_s}|{target_platform}"
    return "producer_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _clip(value: str, limit: int) -> str:
    value = " ".join((value or "").split())
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


__all__ = ["build_creative_producer_v2"]
