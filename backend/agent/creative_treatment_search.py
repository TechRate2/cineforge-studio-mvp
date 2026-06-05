"""Deterministic creative treatment search for autonomous video planning.

Top-tier agentic video systems do not commit to the first plausible idea. They
compare director treatments, score creative fit, production risk, reference
coverage, and runtime continuity, then render only the strongest route. This
module is vendor-free so it can run inside the read-only production decision
preview before any paid AtlasCloud call.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class _TreatmentProfile:
    """One production-director strategy the autonomous agent can select."""

    treatment_id: str
    label: str
    director_intent: str
    best_niches: set[str]
    camera_language: str
    edit_rhythm: str
    reference_policy: str
    platform_strength: str
    runtime_bias: set[str]
    market_bias: set[str]
    prompt_formula_bias: list[str]
    shot_design_priorities: list[str]
    qa_priorities: list[str]
    risk_controls: list[str]


_TREATMENTS: list[_TreatmentProfile] = [
    _TreatmentProfile(
        treatment_id="proof_first_ugc",
        label="Proof-first UGC",
        director_intent="Open with the result, then show a believable in-hand test.",
        best_niches={
            "ugc_review",
            "beauty",
            "food",
            "ecommerce_catalog",
            "app_saas",
            "tech",
            "fitness",
        },
        camera_language="handheld creator POV, macro proof inserts, quick reaction close-ups",
        edit_rhythm="fast hook, compact proof beats, soft CTA",
        reference_policy="prioritize product/creator identity refs and one audio rhythm ref",
        platform_strength="tiktok_reels_shorts",
        runtime_bias={"short", "sequence", "micro_film"},
        market_bias={"vn", "us", "sea", "global"},
        prompt_formula_bias=[
            "asset role",
            "visible proof result in first 1-2 seconds",
            "one in-hand product action per Seedance unit",
            "camera proof insert",
            "claim-safe constraint",
        ],
        shot_design_priorities=[
            "show result before explanation",
            "keep product large enough to read shape and color",
            "cut from hand proof to reaction, not random beauty shots",
        ],
        qa_priorities=[
            "product_visibility",
            "logo_label_similarity",
            "prompt_match",
            "hook_frame_clarity",
        ],
        risk_controls=[
            "avoid exaggerated claims",
            "avoid tiny product scale",
            "avoid unverified before/after implication",
        ],
    ),
    _TreatmentProfile(
        treatment_id="cinematic_premium",
        label="Cinematic premium",
        director_intent="Make the subject feel expensive through lighting, texture, and composed movement.",
        best_niches={
            "beauty",
            "fashion",
            "food",
            "automotive",
            "travel",
            "restaurant_hospitality",
            "real_estate",
            "music_video",
            "drama",
        },
        camera_language="controlled dolly/push-in, hero macro, motivated wide-to-close coverage",
        edit_rhythm="slower premium reveal, sensory detail, strong final hero frame",
        reference_policy="prioritize style refs, product/character anchors, and video refs for camera motion",
        platform_strength="brand_ads_short_films",
        runtime_bias={"short", "sequence", "micro_film", "short_film"},
        market_bias={"us", "jp", "kr", "global", "vn"},
        prompt_formula_bias=[
            "visual texture",
            "motivated light source",
            "controlled camera path",
            "hero frame",
            "consistent color grade",
        ],
        shot_design_priorities=[
            "start with an expensive texture or silhouette",
            "use wide-to-close coverage for spatial clarity",
            "end on a stable poster-worthy frame",
        ],
        qa_priorities=[
            "style_similarity",
            "temporal_style_stability",
            "product_visibility",
            "camera_motion_consistency",
        ],
        risk_controls=[
            "avoid generic luxury adjectives without concrete material detail",
            "avoid unmotivated fast zooms",
            "avoid lighting reset between cuts",
        ],
    ),
    _TreatmentProfile(
        treatment_id="documentary_testimonial",
        label="Documentary testimonial",
        director_intent="Build trust through human context, evidence, and restrained narration.",
        best_niches={
            "education",
            "documentary",
            "finance_education",
            "medical_wellness",
            "real_estate",
            "app_saas",
            "ugc_review",
        },
        camera_language="observational handheld, interview insert, evidence/detail coverage",
        edit_rhythm="context, proof, human beat, takeaway",
        reference_policy="prioritize person/location refs and audio/dialogue refs",
        platform_strength="youtube_long_tiktok_education",
        runtime_bias={"sequence", "micro_film", "short_film", "episode"},
        market_bias={"vn", "us", "global", "sea"},
        prompt_formula_bias=[
            "human context",
            "evidence shot",
            "restrained claim",
            "natural dialogue or VO timing",
            "takeaway frame",
        ],
        shot_design_priorities=[
            "anchor claims in visible evidence",
            "alternate person context with concrete object/location detail",
            "make captions support, not replace, the visual story",
        ],
        qa_priorities=[
            "face_similarity",
            "dialogue_route",
            "claim_safety",
            "location_continuity",
        ],
        risk_controls=[
            "avoid medical or financial overclaim",
            "avoid synthetic testimonial deception",
            "avoid unsupported authority cues",
        ],
    ),
    _TreatmentProfile(
        treatment_id="fast_social_hook",
        label="Fast social hook",
        director_intent="Compress the idea into high-retention mobile beats with immediate motion.",
        best_niches={
            "ugc_review",
            "gaming",
            "fashion",
            "fitness",
            "food",
            "travel",
            "music_video",
            "asmr",
            "lifestyle",
        },
        camera_language="snap zooms, POV reveals, beat-hit cuts, one clear action per shot",
        edit_rhythm="0-3s hook, escalation every 4-8s, save/share close",
        reference_policy="prioritize identity/style refs and audio beat/SFX timing",
        platform_strength="tiktok_reels",
        runtime_bias={"short", "sequence"},
        market_bias={"vn", "us", "sea", "global", "kr"},
        prompt_formula_bias=[
            "immediate motion",
            "one readable action",
            "beat-hit camera cue",
            "retention reset every unit",
            "save/share close",
        ],
        shot_design_priorities=[
            "first frame must already be moving",
            "each Seedance unit gets one action, not a montage list",
            "use audio beat to justify cuts",
        ],
        qa_priorities=[
            "hook_frame_clarity",
            "motion_readability",
            "style_similarity",
            "audio_sync_intent",
        ],
        risk_controls=[
            "avoid frantic motion blur",
            "avoid confusing multiple actions inside one 4-15s unit",
            "avoid style reset on every cut",
        ],
    ),
    _TreatmentProfile(
        treatment_id="short_drama_arc",
        label="Short-drama arc",
        director_intent="Turn the brief into conflict, escalation, reveal, and emotional aftertaste.",
        best_niches={
            "drama",
            "documentary",
            "education",
            "lifestyle",
            "travel",
            "restaurant_hospitality",
            "real_estate",
        },
        camera_language="emotion close-ups, object clues, motivated OTS, continuity handoffs",
        edit_rhythm="act-based scene progression with visual cliffhangers",
        reference_policy="prioritize character/location anchors and previous-scene final frames",
        platform_strength="short_film_episode",
        runtime_bias={"micro_film", "short_film", "episode"},
        market_bias={"vn", "kr", "jp", "global", "sea"},
        prompt_formula_bias=[
            "character state",
            "conflict beat",
            "object clue",
            "motivated OTS or close-up",
            "last-frame handoff",
        ],
        shot_design_priorities=[
            "each segment changes the emotional state",
            "handoff frame must preserve face, outfit, location and prop layout",
            "do not reveal future twists before the planned beat",
        ],
        qa_priorities=[
            "face_similarity",
            "emotion_similarity",
            "style_similarity",
            "handoff_frame_stability",
            "location_continuity",
        ],
        risk_controls=[
            "avoid random new locations without setup",
            "avoid face/outfit drift between emotional close-ups",
            "avoid dialogue route unless voice/lip-sync assets are ready",
        ],
    ),
]


def build_creative_treatment_search(
    *,
    user_idea: str,
    niche: str,
    target_market: str,
    target_platform: str,
    runtime_payload: dict[str, Any],
    reference_counts: dict[str, int],
    niche_playbook: dict[str, Any],
    market_playbook: dict[str, Any],
    has_dialogue: bool,
) -> dict[str, Any]:
    """Return ranked director treatments and the selected route."""
    runtime_class = str(runtime_payload.get("runtime_class") or "short")
    duration_s = int(runtime_payload.get("target_duration_s") or 30)
    refs = {
        "images": int(reference_counts.get("images") or 0),
        "videos": int(reference_counts.get("videos") or 0),
        "audios": int(reference_counts.get("audios") or 0),
        "pinned_assets": int(reference_counts.get("pinned_assets") or 0),
    }
    candidate_rows = [
        _score_treatment(
            treatment=t,
            user_idea=user_idea,
            niche=niche,
            target_market=target_market,
            target_platform=target_platform,
            runtime_class=runtime_class,
            duration_s=duration_s,
            reference_counts=refs,
            niche_playbook=niche_playbook,
            market_playbook=market_playbook,
            has_dialogue=has_dialogue,
        )
        for t in _TREATMENTS
    ]
    candidate_rows.sort(
        key=lambda item: (
            item["rank_score"],
            item["dimension_scores"]["creative_fit"],
            item["dimension_scores"]["reference_fit"],
            item["score"],
        ),
        reverse=True,
    )
    selected = candidate_rows[0] if candidate_rows else {}
    alternates = [row for row in candidate_rows[1:4]]
    return {
        "schema_version": "cinejelly.creative_treatment_search.v2",
        "strategy": "rank_director_treatments_by_creative_fit_reference_coverage_runtime_and_qa_risk",
        "selected_treatment_id": selected.get("treatment_id"),
        "selected_label": selected.get("label"),
        "selected_score": selected.get("score"),
        "selection_reason": selected.get("selection_reason"),
        "selected_strategy_fit": selected.get("strategy_fit"),
        "alternate_treatment_ids": [row.get("treatment_id") for row in alternates],
        "candidates": candidate_rows,
        "policy": [
            "Use the selected treatment as the default director route.",
            "Persist alternate treatments for regenerate-in-another-style actions.",
            "Convert treatment output into Seedance prompt blocks: reference jobs, time beat, action, camera, sound, constraints.",
            "Do not expose this as a manual model picker on the main one-click UI.",
        ],
    }


def _score_treatment(
    *,
    treatment: _TreatmentProfile,
    user_idea: str,
    niche: str,
    target_market: str,
    target_platform: str,
    runtime_class: str,
    duration_s: int,
    reference_counts: dict[str, int],
    niche_playbook: dict[str, Any],
    market_playbook: dict[str, Any],
    has_dialogue: bool,
) -> dict[str, Any]:
    text = (user_idea or "").lower()
    reasons: list[str] = []
    risks: list[str] = []

    creative_fit = 50.0
    if niche in treatment.best_niches:
        creative_fit += 22
        reasons.append("niche_fit")
    else:
        creative_fit -= 8
        risks.append("weaker_niche_fit")

    intent_bonus = _intent_bonus(text=text, treatment_id=treatment.treatment_id)
    if intent_bonus:
        creative_fit += intent_bonus
        reasons.append("brief_intent_fit")

    hook_moves = niche_playbook.get("hook_moves") or []
    if hook_moves and any(str(move).lower().split()[0] in treatment.director_intent.lower() for move in hook_moves[:2]):
        creative_fit += 3
        reasons.append("playbook_hook_alignment")

    runtime_fit = _runtime_fit(
        treatment=treatment,
        runtime_class=runtime_class,
        duration_s=duration_s,
        has_dialogue=has_dialogue,
        reasons=reasons,
        risks=risks,
    )
    reference_fit = _reference_fit(
        treatment=treatment,
        reference_counts=reference_counts,
        runtime_class=runtime_class,
        has_dialogue=has_dialogue,
        reasons=reasons,
        risks=risks,
    )
    platform_fit = _platform_fit(
        treatment=treatment,
        target_platform=target_platform,
        target_market=target_market,
        reasons=reasons,
    )
    qa_risk = _qa_risk_score(
        treatment=treatment,
        niche=niche,
        runtime_class=runtime_class,
        reference_counts=reference_counts,
        has_dialogue=has_dialogue,
        risks=risks,
    )

    raw_score = (
        creative_fit * 0.34
        + runtime_fit * 0.22
        + reference_fit * 0.22
        + platform_fit * 0.12
        + qa_risk * 0.10
    )
    if target_market in treatment.market_bias:
        raw_score += 3
        reasons.append("market_tone_fit")
    if target_market == "vn" and treatment.treatment_id in {"proof_first_ugc", "documentary_testimonial", "short_drama_arc"}:
        raw_score += 3
        reasons.append("vn_creator_or_drama_fit")
    if niche in {"finance_education", "medical_wellness", "kids_family", "documentary"}:
        if treatment.treatment_id == "documentary_testimonial":
            raw_score += 8
            reasons.append("review_sensitive_trust_fit")
        elif treatment.treatment_id == "fast_social_hook":
            raw_score -= 12
            risks.append("too_hype_for_review_sensitive_niche")

    rank_score = round(raw_score - (len(risks) * 1.5), 2)
    fit_score = _clamp_score(raw_score)
    risk_level = _risk_level(score=fit_score, risks=risks, qa_risk=qa_risk)
    selection_reason = ", ".join(dict.fromkeys(reasons[:5])) if reasons else "fallback_director_route"

    return {
        "treatment_id": treatment.treatment_id,
        "label": treatment.label,
        "score": fit_score,
        "fit_score": fit_score,
        "rank_score": rank_score,
        "risk_level": risk_level,
        "selection_reason": selection_reason,
        "reasons": list(dict.fromkeys(reasons)),
        "risks": list(dict.fromkeys(risks)),
        "director_intent": treatment.director_intent,
        "camera_language": treatment.camera_language,
        "edit_rhythm": treatment.edit_rhythm,
        "reference_policy": treatment.reference_policy,
        "market_hook_style": market_playbook.get("hook_style") or "visual proof first",
        "suggested_hook_move": hook_moves[0] if hook_moves else _fallback_hook_move(treatment.treatment_id),
        "duration_strategy": _duration_strategy(runtime_class, duration_s),
        "strategy_fit": _strategy_fit_summary(
            treatment=treatment,
            runtime_class=runtime_class,
            reference_counts=reference_counts,
            risk_level=risk_level,
        ),
        "dimension_scores": {
            "creative_fit": round(_clamp_float(creative_fit), 2),
            "runtime_fit": round(runtime_fit, 2),
            "reference_fit": round(reference_fit, 2),
            "platform_market_fit": round(platform_fit, 2),
            "qa_safety_fit": round(qa_risk, 2),
        },
        "prompt_formula_bias": treatment.prompt_formula_bias,
        "shot_design_priorities": treatment.shot_design_priorities,
        "qa_priorities": treatment.qa_priorities,
        "risk_controls": treatment.risk_controls,
        "continuity_plan": _continuity_plan(
            treatment=treatment,
            runtime_class=runtime_class,
            reference_counts=reference_counts,
        ),
    }


def _intent_bonus(*, text: str, treatment_id: str) -> float:
    tokens_by_treatment = {
        "proof_first_ugc": ("proof", "test", "review", "honest", "demo", "tiktok shop", "kiem chung", "danh gia"),
        "cinematic_premium": ("luxury", "premium", "cinematic", "hero", "fashion film", "high-end"),
        "documentary_testimonial": ("documentary", "true story", "interview", "explains", "case study", "phong su"),
        "fast_social_hook": ("viral", "fast", "trend", "beat", "satisfying", "loop", "retention"),
        "short_drama_arc": ("story", "film", "drama", "twist", "secret", "betrayal", "phim ngan", "bi mat", "cau chuyen"),
    }
    hits = sum(1 for token in tokens_by_treatment.get(treatment_id, ()) if token in text)
    return min(12.0, float(hits * 4))


def _runtime_fit(
    *,
    treatment: _TreatmentProfile,
    runtime_class: str,
    duration_s: int,
    has_dialogue: bool,
    reasons: list[str],
    risks: list[str],
) -> float:
    score = 58.0
    if runtime_class in treatment.runtime_bias:
        score += 22
        reasons.append("runtime_structure_fit")
    elif runtime_class in {"short_film", "episode"}:
        score -= 10
        risks.append("may_feel_too_short_form_for_runtime")
    else:
        score -= 4

    if runtime_class in {"short_film", "episode"} and treatment.treatment_id == "short_drama_arc":
        score += 10
        reasons.append("scene_handoff_fit")
    if runtime_class in {"short", "sequence"} and treatment.treatment_id in {"proof_first_ugc", "fast_social_hook", "cinematic_premium"}:
        score += 8
        reasons.append("short_form_retention_fit")
    if duration_s > 180 and treatment.treatment_id != "short_drama_arc":
        score -= 7
        risks.append("long_duration_requires_stronger_scene_memory")
    if has_dialogue and treatment.treatment_id in {"documentary_testimonial", "short_drama_arc"}:
        score += 6
        reasons.append("dialogue_friendly")
    elif has_dialogue:
        score -= 4
        risks.append("dialogue_may_need_insert_or_repair_lane")
    return _clamp_float(score)


def _reference_fit(
    *,
    treatment: _TreatmentProfile,
    reference_counts: dict[str, int],
    runtime_class: str,
    has_dialogue: bool,
    reasons: list[str],
    risks: list[str],
) -> float:
    score = 52.0
    image_refs = reference_counts["images"] + reference_counts["pinned_assets"]
    if image_refs:
        score += 18
        reasons.append("visual_anchor_refs_available")
    else:
        penalty = 18 if runtime_class in {"short_film", "episode"} else 8
        score -= penalty
        risks.append("no_visual_anchor_refs")

    if reference_counts["videos"]:
        score += 7
        reasons.append("motion_or_camera_ref_available")
    elif treatment.treatment_id in {"cinematic_premium", "fast_social_hook"}:
        score -= 4
        risks.append("camera_motion_ref_missing")

    if reference_counts["audios"]:
        score += 7
        reasons.append("audio_ref_available")
    elif has_dialogue:
        score -= 12
        risks.append("dialogue_audio_ref_missing")

    if treatment.treatment_id == "short_drama_arc" and image_refs < 2 and runtime_class in {"short_film", "episode"}:
        score -= 10
        risks.append("long_form_character_location_refs_thin")
    if treatment.treatment_id == "proof_first_ugc" and image_refs:
        score += 5
    return _clamp_float(score)


def _platform_fit(
    *,
    treatment: _TreatmentProfile,
    target_platform: str,
    target_market: str,
    reasons: list[str],
) -> float:
    platform = (target_platform or "tiktok").lower()
    score = 58.0
    if platform in {"tiktok", "reels", "youtube_shorts"}:
        if treatment.platform_strength in {"tiktok_reels", "tiktok_reels_shorts"}:
            score += 22
            reasons.append("platform_retention_fit")
        elif treatment.platform_strength == "brand_ads_short_films":
            score += 8
    elif platform in {"youtube_long", "facebook"}:
        if treatment.platform_strength in {"short_film_episode", "youtube_long_tiktok_education"}:
            score += 20
            reasons.append("long_platform_fit")
    if target_market in treatment.market_bias:
        score += 6
    return _clamp_float(score)


def _qa_risk_score(
    *,
    treatment: _TreatmentProfile,
    niche: str,
    runtime_class: str,
    reference_counts: dict[str, int],
    has_dialogue: bool,
    risks: list[str],
) -> float:
    score = 78.0
    image_refs = reference_counts["images"] + reference_counts["pinned_assets"]
    if runtime_class in {"short_film", "episode"}:
        score -= 8
        if image_refs < 2:
            score -= 16
            risks.append("high_continuity_risk_without_multiple_anchors")
    if niche in {"medical_wellness", "finance_education", "kids_family"}:
        score -= 8
    if has_dialogue and not reference_counts["audios"]:
        score -= 12
    if treatment.treatment_id == "fast_social_hook" and runtime_class in {"short_film", "episode"}:
        score -= 12
    if treatment.treatment_id == "short_drama_arc" and image_refs:
        score += 6
    return _clamp_float(score)


def _risk_level(*, score: int, risks: list[str], qa_risk: float) -> str:
    hard_risks = {
        "high_continuity_risk_without_multiple_anchors",
        "dialogue_audio_ref_missing",
        "long_form_character_location_refs_thin",
    }
    if any(risk in hard_risks for risk in risks) and score < 82:
        return "high"
    if score >= 82 and qa_risk >= 72 and len(risks) <= 2:
        return "low"
    if score >= 68:
        return "medium"
    return "high"


def _strategy_fit_summary(
    *,
    treatment: _TreatmentProfile,
    runtime_class: str,
    reference_counts: dict[str, int],
    risk_level: str,
) -> str:
    refs = []
    if reference_counts["images"] or reference_counts["pinned_assets"]:
        refs.append("visual anchors")
    if reference_counts["videos"]:
        refs.append("motion refs")
    if reference_counts["audios"]:
        refs.append("audio refs")
    ref_text = ", ".join(refs) if refs else "text-only refs"
    return (
        f"{treatment.label} fits {runtime_class} with {ref_text}; "
        f"risk={risk_level}; prompt bias={', '.join(treatment.prompt_formula_bias[:3])}"
    )


def _continuity_plan(
    *,
    treatment: _TreatmentProfile,
    runtime_class: str,
    reference_counts: dict[str, int],
) -> dict[str, Any]:
    is_long = runtime_class in {"micro_film", "short_film", "episode"}
    return {
        "requires_scene_memory": is_long,
        "requires_handoff_frames": is_long or treatment.treatment_id == "short_drama_arc",
        "primary_locks": _primary_locks(treatment=treatment, reference_counts=reference_counts),
        "handoff_policy": (
            "first frame repeats previous exit state; final second holds a stable identity/product/location frame"
            if is_long else
            "single-unit continuity; preserve refs throughout the clip"
        ),
        "probe_focus": treatment.qa_priorities[:4],
    }


def _primary_locks(
    *,
    treatment: _TreatmentProfile,
    reference_counts: dict[str, int],
) -> list[str]:
    locks: list[str] = []
    if reference_counts["images"] or reference_counts["pinned_assets"]:
        locks.append("visual_reference_identity")
    if treatment.treatment_id in {"proof_first_ugc", "cinematic_premium"}:
        locks.append("product_or_style_lock")
    if treatment.treatment_id in {"short_drama_arc", "documentary_testimonial"}:
        locks.append("character_emotion_lock")
    if reference_counts["videos"]:
        locks.append("camera_motion_lock")
    if reference_counts["audios"]:
        locks.append("audio_timing_lock")
    return list(dict.fromkeys(locks or ["style_prompt_lock"]))


def _fallback_hook_move(treatment_id: str) -> str:
    return {
        "proof_first_ugc": "visual proof cold open",
        "cinematic_premium": "premium texture reveal",
        "documentary_testimonial": "human-context trust setup",
        "fast_social_hook": "immediate motion retention hook",
        "short_drama_arc": "conflict clue cold open",
    }.get(treatment_id, "visual proof cold open")


def _duration_strategy(runtime_class: str, duration_s: int) -> str:
    if runtime_class in {"short", "sequence"}:
        return "compress into 1-6 Seedance units with one clear action per shot"
    if runtime_class == "micro_film":
        return "split into 2-3 scene beats and render 4-15s Seedance units with handoff frames"
    if runtime_class == "short_film":
        return "split into acts, scenes, chunks, and roughly 12s Seedance units with scene memory"
    return f"episode graph required for {duration_s}s with act checkpoints, resumable chunks, and QA retries"


def _clamp_score(value: float) -> int:
    return int(round(_clamp_float(value)))


def _clamp_float(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


__all__ = ["build_creative_treatment_search"]
