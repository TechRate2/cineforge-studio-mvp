"""Deterministic creative treatment search for autonomous video planning.

Top-tier agentic video systems do not commit to the first plausible idea. They
compare a few director treatments, score risk and fit, then render only the
strongest route. This module is vendor-free so it can run inside the read-only
production decision preview before any paid AtlasCloud call.
"""
from __future__ import annotations

from typing import Any


_TREATMENTS: list[dict[str, Any]] = [
    {
        "treatment_id": "proof_first_ugc",
        "label": "Proof-first UGC",
        "director_intent": "Open with the result, then show a believable in-hand test.",
        "best_niches": {
            "ugc_review",
            "beauty",
            "food",
            "ecommerce_catalog",
            "app_saas",
            "tech",
            "fitness",
        },
        "camera_language": "handheld creator POV, macro proof inserts, quick reaction close-ups",
        "edit_rhythm": "fast hook, compact proof beats, soft CTA",
        "reference_policy": "prioritize product/creator identity refs and one audio rhythm ref",
        "platform_strength": "tiktok_reels_shorts",
    },
    {
        "treatment_id": "cinematic_premium",
        "label": "Cinematic premium",
        "director_intent": "Make the subject feel expensive through lighting, texture, and composed movement.",
        "best_niches": {
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
        "camera_language": "controlled dolly/push-in, hero macro, motivated wide-to-close coverage",
        "edit_rhythm": "slower premium reveal, sensory detail, strong final hero frame",
        "reference_policy": "prioritize style refs, product/character anchors, and video refs for camera motion",
        "platform_strength": "brand_ads_short_films",
    },
    {
        "treatment_id": "documentary_testimonial",
        "label": "Documentary testimonial",
        "director_intent": "Build trust through human context, evidence, and restrained narration.",
        "best_niches": {
            "education",
            "documentary",
            "finance_education",
            "medical_wellness",
            "real_estate",
            "app_saas",
            "ugc_review",
        },
        "camera_language": "observational handheld, interview insert, evidence/detail coverage",
        "edit_rhythm": "context, proof, human beat, takeaway",
        "reference_policy": "prioritize person/location refs and audio/dialogue refs",
        "platform_strength": "youtube_long_tiktok_education",
    },
    {
        "treatment_id": "fast_social_hook",
        "label": "Fast social hook",
        "director_intent": "Compress the idea into high-retention mobile beats with immediate motion.",
        "best_niches": {
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
        "camera_language": "snap zooms, POV reveals, beat-hit cuts, one clear action per shot",
        "edit_rhythm": "0-3s hook, escalation every 4-8s, save/share close",
        "reference_policy": "prioritize identity/style refs and audio beat/SFX timing",
        "platform_strength": "tiktok_reels",
    },
    {
        "treatment_id": "short_drama_arc",
        "label": "Short-drama arc",
        "director_intent": "Turn the brief into conflict, escalation, reveal, and emotional aftertaste.",
        "best_niches": {
            "drama",
            "documentary",
            "education",
            "lifestyle",
            "travel",
            "restaurant_hospitality",
            "real_estate",
        },
        "camera_language": "emotion close-ups, object clues, motivated OTS, continuity handoffs",
        "edit_rhythm": "act-based scene progression with visual cliffhangers",
        "reference_policy": "prioritize character/location anchors and previous-scene final frames",
        "platform_strength": "short_film_episode",
    },
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
    candidates = [
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
    candidates.sort(key=lambda item: (item["rank_score"], item["score"]), reverse=True)
    selected = candidates[0] if candidates else {}
    return {
        "schema_version": "cinejelly.creative_treatment_search.v1",
        "strategy": "rank_3_to_5_director_treatments_before_paid_render",
        "selected_treatment_id": selected.get("treatment_id"),
        "selected_label": selected.get("label"),
        "selected_score": selected.get("score"),
        "selection_reason": selected.get("selection_reason"),
        "candidates": candidates,
        "policy": [
            "Use the selected treatment as the default director route.",
            "Keep alternate treatments for future regenerate-in-another-style actions.",
            "Do not expose this as a manual model picker on the main one-click UI.",
        ],
    }


def _score_treatment(
    *,
    treatment: dict[str, Any],
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
    score = 55
    reasons: list[str] = []
    risks: list[str] = []

    if niche in treatment["best_niches"]:
        score += 18
        reasons.append("niche_fit")
    else:
        score -= 4
        risks.append("weaker_niche_fit")

    if runtime_class in {"short_film", "episode"}:
        if treatment["treatment_id"] in {"short_drama_arc", "documentary_testimonial", "cinematic_premium"}:
            score += 12
            reasons.append("long_form_structure_fit")
        else:
            score -= 5
            risks.append("may_feel_too_short_form_for_runtime")
    elif runtime_class in {"short", "sequence"}:
        if treatment["treatment_id"] in {"proof_first_ugc", "fast_social_hook", "cinematic_premium"}:
            score += 8
            reasons.append("short_form_retention_fit")

    if reference_counts["images"] or reference_counts["pinned_assets"]:
        score += 7
        reasons.append("identity_or_product_refs_available")
    else:
        risks.append("no_visual_anchor_refs")
        score -= 7 if runtime_class in {"short_film", "episode"} else 3

    if reference_counts["videos"]:
        score += 4
        reasons.append("motion_or_camera_ref_available")
    if reference_counts["audios"]:
        score += 4
        reasons.append("audio_ref_available")

    if has_dialogue:
        if treatment["treatment_id"] in {"documentary_testimonial", "short_drama_arc"}:
            score += 6
            reasons.append("dialogue_friendly")
        else:
            risks.append("dialogue_may_need_insert_or_repair_lane")
            score -= 2

    if target_platform in {"tiktok", "reels", "youtube_shorts"}:
        if treatment["platform_strength"] in {"tiktok_reels", "tiktok_reels_shorts"}:
            score += 5
            reasons.append("platform_retention_fit")
    elif target_platform in {"youtube_long", "facebook"}:
        if treatment["platform_strength"] in {"short_film_episode", "youtube_long_tiktok_education"}:
            score += 5
            reasons.append("long_platform_fit")

    if target_market == "vn" and treatment["treatment_id"] in {"proof_first_ugc", "documentary_testimonial"}:
        score += 3
        reasons.append("vn_creator_or_trust_fit")

    if niche in {"finance_education", "medical_wellness", "kids_family", "documentary"}:
        if treatment["treatment_id"] == "documentary_testimonial":
            score += 8
            reasons.append("review_sensitive_trust_fit")
        elif treatment["treatment_id"] == "fast_social_hook":
            score -= 10
            risks.append("too_hype_for_review_sensitive_niche")

    text = (user_idea or "").lower()
    if any(token in text for token in ("luxury", "premium", "cinematic", "hero")):
        if treatment["treatment_id"] == "cinematic_premium":
            score += 7
            reasons.append("premium_intent_detected")
    if any(token in text for token in ("story", "film", "drama", "twist")):
        if treatment["treatment_id"] == "short_drama_arc":
            score += 7
            reasons.append("story_arc_intent_detected")

    rank_score = score
    fit_score = max(0, min(100, score))
    risk_level = "low" if fit_score >= 82 and not risks else "medium" if fit_score >= 68 else "high"
    hook_moves = niche_playbook.get("hook_moves") or []
    market_hook = market_playbook.get("hook_style") or "visual proof first"
    selection_reason = ", ".join(reasons[:4]) if reasons else "fallback_director_route"

    return {
        "treatment_id": treatment["treatment_id"],
        "label": treatment["label"],
        "score": fit_score,
        "fit_score": fit_score,
        "rank_score": rank_score,
        "risk_level": risk_level,
        "selection_reason": selection_reason,
        "reasons": reasons,
        "risks": risks,
        "director_intent": treatment["director_intent"],
        "camera_language": treatment["camera_language"],
        "edit_rhythm": treatment["edit_rhythm"],
        "reference_policy": treatment["reference_policy"],
        "market_hook_style": market_hook,
        "suggested_hook_move": hook_moves[0] if hook_moves else "visual proof cold open",
        "duration_strategy": _duration_strategy(runtime_class, duration_s),
    }


def _duration_strategy(runtime_class: str, duration_s: int) -> str:
    if runtime_class in {"short", "sequence"}:
        return "compress into 1-6 Seedance units with one clear action per shot"
    if runtime_class == "micro_film":
        return "split into 2-3 scene beats and render 4-15s units"
    if runtime_class == "short_film":
        return "split into acts, scenes, chunks, and roughly 12s Seedance units"
    return f"episode graph required for {duration_s}s with act checkpoints and resumable chunks"


__all__ = ["build_creative_treatment_search"]
