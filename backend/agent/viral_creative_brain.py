"""Viral Creative Brain 4A.

This module is the no-cost creative intelligence layer. It turns the existing
brief, producer graph, and prompt contract into platform-aware viral hooks,
retention moves, packaging, and variant strategy before any paid render.
"""
from __future__ import annotations

import hashlib
from typing import Any


_SCHEMA_VERSION = "cinejelly.viral_creative_brain.v1"

_PRODUCT_NICHES = {
    "beauty",
    "food",
    "fashion",
    "ecommerce_catalog",
    "tech",
    "app_saas",
    "automotive",
    "restaurant_hospitality",
    "fitness",
    "ugc_review",
}
_STORY_NICHES = {"drama", "documentary", "anime_comic", "travel", "lifestyle", "music_video"}
_TRUST_NICHES = {"education", "finance_education", "medical_wellness", "documentary", "kids_family"}
_SENSORY_NICHES = {"food", "asmr", "beauty", "restaurant_hospitality", "travel"}
_LONG_RUNTIME_CLASSES = {"micro_film", "short_film", "episode"}

_PATTERNS: list[dict[str, Any]] = [
    {
        "pattern_id": "proof_first_scroll_stop",
        "label": "Proof-first scroll stop",
        "best_intents": {"sell_product", "review_proof"},
        "best_niches": _PRODUCT_NICHES,
        "hook_formula": "result first -> contradiction -> proof path",
        "retention_engine": "viewer sees the payoff, then watches to understand why it happened",
        "risk": "can feel generic if the proof is not visibly specific",
    },
    {
        "pattern_id": "sensory_desire_loop",
        "label": "Sensory desire loop",
        "best_intents": {"sell_product", "review_proof", "general_video"},
        "best_niches": _SENSORY_NICHES | {"fashion", "automotive"},
        "hook_formula": "macro texture -> tactile action -> delayed hero reveal",
        "retention_engine": "sensory escalation keeps the viewer waiting for the final reveal",
        "risk": "weak for abstract SaaS or education unless tied to a concrete result",
    },
    {
        "pattern_id": "mistake_to_fix",
        "label": "Mistake-to-fix explainer",
        "best_intents": {"educate", "sell_product", "review_proof"},
        "best_niches": _TRUST_NICHES | {"app_saas", "tech", "fitness"},
        "hook_formula": "wrong assumption -> visible consequence -> simple fix",
        "retention_engine": "each beat resolves one confusion and opens the next question",
        "risk": "claims must stay safe and evidence-backed",
    },
    {
        "pattern_id": "short_drama_reversal_loop",
        "label": "Short-drama reversal loop",
        "best_intents": {"entertain", "brand_story"},
        "best_niches": _STORY_NICHES | {"app_saas", "restaurant_hospitality"},
        "hook_formula": "emotional contradiction -> object clue -> reveal/reversal",
        "retention_engine": "every scene ends before answering the emotional question",
        "risk": "needs character/location anchors to avoid generic melodrama",
    },
    {
        "pattern_id": "challenge_countdown",
        "label": "Challenge countdown",
        "best_intents": {"review_proof", "entertain", "sell_product"},
        "best_niches": {"fitness", "gaming", "food", "beauty", "ugc_review", "fashion", "travel"},
        "hook_formula": "challenge stated -> timer/attempts -> proof spike",
        "retention_engine": "countdown and escalating attempts create forward motion",
        "risk": "can look gimmicky for premium or sensitive niches",
    },
    {
        "pattern_id": "premium_world_reveal",
        "label": "Premium world reveal",
        "best_intents": {"sell_product", "brand_story", "general_video"},
        "best_niches": {"beauty", "fashion", "food", "automotive", "travel", "real_estate", "restaurant_hospitality"},
        "hook_formula": "atmospheric clue -> ritual/process -> full hero reveal",
        "retention_engine": "withheld context makes the viewer decode the world before the reveal",
        "risk": "too slow for aggressive short-form unless first frame is striking",
    },
]


def build_viral_creative_brain(
    *,
    user_idea: str,
    creative_brief_contract: dict[str, Any],
    creative_producer_v2: dict[str, Any],
    prompt_execution_contract_v3: dict[str, Any],
    decision: dict[str, Any],
    creative_treatment_search: dict[str, Any],
    niche_playbook: dict[str, Any],
    market_playbook: dict[str, Any],
) -> dict[str, Any]:
    """Return no-cost viral creative guidance for every niche/runtime."""
    parsed = (creative_brief_contract or {}).get("parsed") or {}
    readiness = (creative_brief_contract or {}).get("readiness") or {}
    producer_angle = (creative_producer_v2 or {}).get("selected_angle") or {}
    script_beats = list((creative_producer_v2 or {}).get("script_beats") or [])
    shot_graph = (creative_producer_v2 or {}).get("shot_graph") or {}
    prompt_readiness = (prompt_execution_contract_v3 or {}).get("readiness") or {}
    model_plan = (prompt_execution_contract_v3 or {}).get("model_plan") or {}
    niche = str(decision.get("niche") or niche_playbook.get("niche") or "ugc_review")
    runtime_class = str(decision.get("runtime_class") or shot_graph.get("runtime_class") or "short")
    duration_s = _safe_int(decision.get("target_duration_s"), 30)
    target_platform = str(decision.get("target_platform") or parsed.get("target_platform") or "tiktok")
    target_market = str(decision.get("target_market") or market_playbook.get("target_market") or "auto")
    output_intent = str(parsed.get("output_intent") or "general_video")
    subject = _subject(parsed, niche)
    refs = ((parsed.get("reference_expectation") or {}).get("status") or "optional")
    candidates = _rank_patterns(
        output_intent=output_intent,
        niche=niche,
        runtime_class=runtime_class,
        duration_s=duration_s,
        target_platform=target_platform,
        producer_angle=producer_angle,
        treatment_id=str(creative_treatment_search.get("selected_treatment_id") or ""),
        reference_status=str(refs),
        readiness_score=_safe_int(readiness.get("completeness_score"), 0),
    )
    selected = candidates[0] if candidates else {}
    hook_variants = _hook_variants(
        selected_pattern=selected,
        subject=subject,
        niche=niche,
        target_platform=target_platform,
        target_market=target_market,
        niche_playbook=niche_playbook,
        producer_angle=producer_angle,
        script_beats=script_beats,
    )
    retention_plan = _retention_plan(
        selected_pattern=selected,
        script_beats=script_beats,
        duration_s=duration_s,
        runtime_class=runtime_class,
        target_platform=target_platform,
        shot_count=_safe_int(shot_graph.get("node_count"), 0),
    )
    platform_package = _platform_package(
        selected_pattern=selected,
        hook_variants=hook_variants,
        subject=subject,
        niche=niche,
        target_platform=target_platform,
        target_market=target_market,
        market_playbook=market_playbook,
        duration_s=duration_s,
    )
    variant_matrix = _variant_matrix(
        selected_pattern=selected,
        candidates=candidates,
        subject=subject,
        niche=niche,
        target_platform=target_platform,
        duration_s=duration_s,
    )
    risk_guards = _risk_guards(
        niche=niche,
        runtime_class=runtime_class,
        duration_s=duration_s,
        readiness=readiness,
        prompt_readiness=prompt_readiness,
        model_plan=model_plan,
        selected_pattern=selected,
    )
    score = _creative_score(
        readiness_score=_safe_int(readiness.get("completeness_score"), 0),
        selected_score=_safe_int(selected.get("score"), 0),
        prompt_warning_count=_safe_int(prompt_readiness.get("warning_count"), 0),
        hook_count=len(hook_variants),
        risk_count=len([item for item in risk_guards if item.get("severity") == "blocking"]),
    )
    return {
        "schema_version": _SCHEMA_VERSION,
        "vendor_calls_performed": False,
        "paid_video_vendor_calls_allowed": False,
        "brain_id": _brain_id(user_idea=user_idea, niche=niche, platform=target_platform, duration_s=duration_s),
        "strategy": "rank_viral_patterns_then_package_hooks_retention_and_variants_before_paid_render",
        "readiness": {
            "status": "viral_plan_ready" if score >= 75 and not any(item.get("severity") == "blocking" for item in risk_guards) else "needs_creative_review",
            "creative_score": score,
            "hook_variant_count": len(hook_variants),
            "variant_count": len(variant_matrix),
        },
        "route_context": {
            "niche": niche,
            "output_intent": output_intent,
            "runtime_class": runtime_class,
            "duration_s": duration_s,
            "target_platform": target_platform,
            "target_market": target_market,
            "subject": subject,
            "primary_visual_model": model_plan.get("primary_visual_model"),
            "producer_angle_id": producer_angle.get("angle_id"),
        },
        "selected_viral_pattern": selected,
        "pattern_candidates": candidates,
        "hook_variants": hook_variants,
        "retention_plan": retention_plan,
        "platform_package": platform_package,
        "variant_matrix": variant_matrix,
        "risk_guards": risk_guards,
        "operator_notes": [
            "This is a planning contract only; do not spend render credits from this layer.",
            "Use hook variants for cheap A/B preflight, then render only approved candidates.",
            "Promote a pattern only after real output QA proves higher accepted-minute quality.",
        ],
    }


def _rank_patterns(
    *,
    output_intent: str,
    niche: str,
    runtime_class: str,
    duration_s: int,
    target_platform: str,
    producer_angle: dict[str, Any],
    treatment_id: str,
    reference_status: str,
    readiness_score: int,
) -> list[dict[str, Any]]:
    rows = []
    for pattern in _PATTERNS:
        score = 50
        reasons: list[str] = []
        risks: list[str] = []
        if output_intent in pattern["best_intents"]:
            score += 18
            reasons.append("intent_fit")
        else:
            score -= 4
            risks.append("weaker_intent_fit")
        if niche in pattern["best_niches"]:
            score += 18
            reasons.append("niche_fit")
        else:
            score -= 5
            risks.append("weaker_niche_fit")
        if runtime_class in _LONG_RUNTIME_CLASSES:
            if pattern["pattern_id"] in {"short_drama_reversal_loop", "mistake_to_fix", "premium_world_reveal"}:
                score += 10
                reasons.append("long_runtime_fit")
            else:
                score -= 4
                risks.append("may_need_scene_level_bridge")
        elif target_platform in {"tiktok", "reels", "youtube_short", "youtube_shorts"}:
            if pattern["pattern_id"] in {"proof_first_scroll_stop", "challenge_countdown", "sensory_desire_loop"}:
                score += 8
                reasons.append("short_platform_retention_fit")
        if duration_s <= 30 and pattern["pattern_id"] == "premium_world_reveal":
            score -= 4
            risks.append("premium_reveal_may_be_slow_for_short_runtime")
        if "visual_refs_present" in reference_status:
            score += 4
            reasons.append("reference_anchor_available")
        elif runtime_class in _LONG_RUNTIME_CLASSES or pattern["pattern_id"] in {"short_drama_reversal_loop", "premium_world_reveal"}:
            score -= 6
            risks.append("needs_visual_anchor_for_best_result")
        if readiness_score < 60:
            score -= 10
            risks.append("brief_incomplete_for_precise_viral_plan")
        angle_id = str(producer_angle.get("angle_id") or "")
        if pattern["pattern_id"] == "proof_first_scroll_stop" and angle_id == "proof_first_transformation":
            score += 6
            reasons.append("matches_producer_angle")
        if pattern["pattern_id"] == "short_drama_reversal_loop" and angle_id == "short_drama_reversal":
            score += 6
            reasons.append("matches_producer_angle")
        if pattern["pattern_id"] == "premium_world_reveal" and treatment_id == "cinematic_premium":
            score += 5
            reasons.append("matches_director_treatment")
        fit_score = max(0, min(100, score))
        rows.append({
            "pattern_id": pattern["pattern_id"],
            "label": pattern["label"],
            "score": fit_score,
            "rank_score": score,
            "risk_level": "low" if fit_score >= 82 and not risks else "medium" if fit_score >= 66 else "high",
            "hook_formula": pattern["hook_formula"],
            "retention_engine": pattern["retention_engine"],
            "selection_reason": ", ".join(reasons[:5]) if reasons else "fallback_pattern",
            "reasons": reasons,
            "risks": risks,
            "known_risk": pattern["risk"],
        })
    rows.sort(key=lambda item: (item["rank_score"], item["score"]), reverse=True)
    return rows


def _hook_variants(
    *,
    selected_pattern: dict[str, Any],
    subject: str,
    niche: str,
    target_platform: str,
    target_market: str,
    niche_playbook: dict[str, Any],
    producer_angle: dict[str, Any],
    script_beats: list[dict[str, Any]],
) -> list[dict[str, str]]:
    hook_moves = [str(item) for item in (niche_playbook.get("hook_moves") or [])[:3]]
    if not hook_moves:
        hook_moves = ["result first", "visual contradiction", "close-up reveal"]
    first_script = str((script_beats[0] or {}).get("script") or producer_angle.get("hook") or "") if script_beats else str(producer_angle.get("hook") or "")
    pattern_id = str(selected_pattern.get("pattern_id") or "proof_first_scroll_stop")
    base_lines = _localized_hook_lines(subject=subject, niche=niche, market=target_market, pattern_id=pattern_id)
    variants: list[dict[str, str]] = []
    for idx, move in enumerate(hook_moves[:3]):
        variants.append({
            "id": f"H{idx + 1}",
            "type": "visual_first",
            "opening_frame": _opening_frame(move=move, subject=subject, niche=niche),
            "first_3s_line": base_lines[idx % len(base_lines)],
            "camera": _hook_camera(move=move, niche=niche),
            "why_it_can_work": f"{move} gives the viewer a concrete reason to stop scrolling on {target_platform}.",
        })
    variants.append({
        "id": "H4",
        "type": "contradiction",
        "opening_frame": f"Show {subject} already at the result, before revealing the process.",
        "first_3s_line": base_lines[-1],
        "camera": "tight readable close-up, immediate motion, no slow intro",
        "why_it_can_work": "A visible contradiction creates an open loop without requiring the user to write a hook.",
    })
    if first_script:
        variants.append({
            "id": "H5",
            "type": "producer_angle",
            "opening_frame": _clip(first_script, 120),
            "first_3s_line": base_lines[0],
            "camera": str(producer_angle.get("camera_language") or "match producer angle with a mobile-readable frame"),
            "why_it_can_work": "Uses the selected producer strategy instead of inventing a separate hook.",
        })
    return variants[:5]


def _retention_plan(
    *,
    selected_pattern: dict[str, Any],
    script_beats: list[dict[str, Any]],
    duration_s: int,
    runtime_class: str,
    target_platform: str,
    shot_count: int,
) -> dict[str, Any]:
    beat_moves = []
    for idx, beat in enumerate(script_beats[:8]):
        beat_moves.append({
            "beat_id": str(beat.get("beat_id") or f"B{idx + 1:02d}"),
            "beat": str(beat.get("beat") or f"Beat {idx + 1}"),
            "retention_move": _retention_move_for(idx=idx, beat=beat, selected_pattern=selected_pattern),
            "exit_question": _exit_question(idx=idx, beat=beat, selected_pattern=selected_pattern),
        })
    checkpoints = [3, 8, 15]
    if duration_s >= 45:
        checkpoints.extend([30, 45])
    if duration_s >= 180:
        checkpoints.extend([60, 120, 180])
    return {
        "pattern_engine": selected_pattern.get("retention_engine"),
        "target_platform": target_platform,
        "shot_count": shot_count,
        "checkpoints_s": [point for point in checkpoints if point < duration_s],
        "beat_moves": beat_moves,
        "long_form_rule": (
            "close every scene with an unresolved emotional or proof question"
            if runtime_class in _LONG_RUNTIME_CLASSES
            else "escalate proof or motion every 4-8 seconds"
        ),
    }


def _platform_package(
    *,
    selected_pattern: dict[str, Any],
    hook_variants: list[dict[str, str]],
    subject: str,
    niche: str,
    target_platform: str,
    target_market: str,
    market_playbook: dict[str, Any],
    duration_s: int,
) -> dict[str, Any]:
    market = (target_market or "global").lower()
    primary_hook = (hook_variants[0] or {}).get("first_3s_line") if hook_variants else ""
    title_variants = _title_variants(subject=subject, niche=niche, pattern=selected_pattern, market=market, duration_s=duration_s)
    hashtags = _hashtags(niche=niche, market=market, target_platform=target_platform)
    return {
        "title_variants": title_variants,
        "caption_draft": _caption(subject=subject, primary_hook=primary_hook, market=market),
        "cover_text_variants": _cover_texts(subject=subject, pattern=selected_pattern, market=market),
        "cover_frame_cue": _cover_frame(subject=subject, niche=niche, pattern=selected_pattern),
        "cta": _cta(market=market, target_platform=target_platform, duration_s=duration_s),
        "hashtags": hashtags,
        "posting_hint": market_playbook.get("posting_hint") or _posting_hint(target_platform),
    }


def _variant_matrix(
    *,
    selected_pattern: dict[str, Any],
    candidates: list[dict[str, Any]],
    subject: str,
    niche: str,
    target_platform: str,
    duration_s: int,
) -> list[dict[str, Any]]:
    labels = [
        ("safe_winner", selected_pattern, "most likely to match the current brief and references"),
        ("bold_scroll_stop", _candidate_by_id(candidates, "challenge_countdown") or selected_pattern, "stronger first-frame interruption for short-form testing"),
        ("premium_brand", _candidate_by_id(candidates, "premium_world_reveal") or selected_pattern, "higher perceived production value and cover frame quality"),
    ]
    if niche in _STORY_NICHES or duration_s >= 180:
        labels[1] = ("drama_reversal", _candidate_by_id(candidates, "short_drama_reversal_loop") or selected_pattern, "stronger conflict and cliffhanger structure")
    return [
        {
            "variant_id": variant_id,
            "pattern_id": pattern.get("pattern_id"),
            "label": pattern.get("label"),
            "why": why,
            "change_from_default": _variant_change(variant_id, subject=subject, target_platform=target_platform),
            "paid_render_allowed": False,
        }
        for variant_id, pattern, why in labels
    ]


def _risk_guards(
    *,
    niche: str,
    runtime_class: str,
    duration_s: int,
    readiness: dict[str, Any],
    prompt_readiness: dict[str, Any],
    model_plan: dict[str, Any],
    selected_pattern: dict[str, Any],
) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    if _safe_int(readiness.get("completeness_score"), 0) < 55:
        risks.append({
            "severity": "blocking",
            "risk": "brief_too_thin_for_viral_claim",
            "fix": "ask one clarifying question before paid render",
        })
    if _safe_int(prompt_readiness.get("warning_count"), 0) > 0:
        risks.append({
            "severity": "recommended",
            "risk": "prompt_contract_has_warnings",
            "fix": "review prompt execution contract warnings before rendering",
        })
    if runtime_class in _LONG_RUNTIME_CLASSES and duration_s >= 300:
        risks.append({
            "severity": "recommended",
            "risk": "long_form_needs_scene_level_payoff_tracking",
            "fix": "review retention checkpoints and scene cliffhangers before render",
        })
    if niche in {"finance_education", "medical_wellness", "kids_family", "documentary"}:
        risks.append({
            "severity": "recommended",
            "risk": "sensitive_niche_overhype",
            "fix": "use trust-first hook and avoid guaranteed claims",
        })
    if not model_plan.get("primary_visual_model"):
        risks.append({
            "severity": "recommended",
            "risk": "model_plan_missing",
            "fix": "build prompt execution contract before paid render",
        })
    if selected_pattern.get("risk_level") == "high":
        risks.append({
            "severity": "recommended",
            "risk": "viral_pattern_low_fit",
            "fix": "choose alternate pattern candidate or improve brief specificity",
        })
    return risks[:8]


def _creative_score(
    *,
    readiness_score: int,
    selected_score: int,
    prompt_warning_count: int,
    hook_count: int,
    risk_count: int,
) -> int:
    score = 20 + int(readiness_score * 0.35) + int(selected_score * 0.35)
    score += min(12, hook_count * 2)
    score -= prompt_warning_count * 6
    score -= risk_count * 18
    return max(0, min(100, score))


def _localized_hook_lines(*, subject: str, niche: str, market: str, pattern_id: str) -> list[str]:
    if market == "vn":
        if pattern_id == "short_drama_reversal_loop":
            return [
                f"Khong ai ngo {subject} lai bat dau tu khoanh khac nay.",
                "Xem den cuoi vi chi tiet nay se dao nguoc tat ca.",
                "Mot quyet dinh nho, nhung cai ket khong nho.",
            ]
        if pattern_id == "mistake_to_fix":
            return [
                f"Neu ban dang lam {subject} theo cach nay, co the ban dang mat ket qua.",
                "Sai mot buoc nho, ket qua khac han.",
                "Day la cach nhin don gian hon.",
            ]
        return [
            f"Ket qua cua {subject} xuat hien truoc, ly do nam o phia sau.",
            "Dung luot qua neu ban muon thay bang chung that.",
            "Thu nay trong 3 giay dau da noi len tat ca.",
        ]
    if pattern_id == "short_drama_reversal_loop":
        return [
            f"Nobody expected {subject} to start with this choice.",
            "Watch the small clue that changes the ending.",
            "One quiet decision turns the whole story.",
        ]
    if pattern_id == "mistake_to_fix":
        return [
            f"If you use {subject} this way, you may be missing the real payoff.",
            "One small mistake changes the result.",
            "Here is the simple fix viewers remember.",
        ]
    return [
        f"Show the result of {subject} first, then reveal the proof.",
        "The proof is visible before the explanation.",
        "This first frame should stop the scroll.",
    ]


def _opening_frame(*, move: str, subject: str, niche: str) -> str:
    if niche in _SENSORY_NICHES:
        return f"{move} close-up with {subject} texture, motion, and payoff visible immediately"
    if niche in _STORY_NICHES:
        return f"{move} with character emotion or object clue tied to {subject}"
    if niche in _TRUST_NICHES:
        return f"{move} showing the mistake or result of {subject} before explanation"
    return f"{move} showing {subject} result before any setup"


def _hook_camera(*, move: str, niche: str) -> str:
    if niche in _SENSORY_NICHES:
        return "ECU/macro, tactile motion, stable enough to verify texture"
    if niche in _STORY_NICHES:
        return "emotion close-up or object insert, motivated push-in"
    if niche in _TRUST_NICHES:
        return "clean explanatory close-up, no clutter, one visible concept"
    return "mobile-readable close-up, immediate action, no dead air"


def _retention_move_for(*, idx: int, beat: dict[str, Any], selected_pattern: dict[str, Any]) -> str:
    beat_name = str(beat.get("beat") or "").lower()
    pattern_id = str(selected_pattern.get("pattern_id") or "")
    if idx == 0:
        return "open with the strongest visual proof or contradiction"
    if "proof" in beat_name or "example" in beat_name:
        return "make the claim visible, then cut before over-explaining"
    if pattern_id == "short_drama_reversal_loop":
        return "end the beat with a new unanswered emotional question"
    if pattern_id == "challenge_countdown":
        return "increase difficulty or stakes before the viewer settles"
    return "show visible change and carry one open loop into the next beat"


def _exit_question(*, idx: int, beat: dict[str, Any], selected_pattern: dict[str, Any]) -> str:
    if idx == 0:
        return "Why did this result happen?"
    if selected_pattern.get("pattern_id") == "short_drama_reversal_loop":
        return "What is the character hiding or about to lose?"
    if str(beat.get("purpose") or "") == "conversion_or_takeaway":
        return "What should the viewer do or remember now?"
    return "What changes in the next shot?"


def _title_variants(*, subject: str, niche: str, pattern: dict[str, Any], market: str, duration_s: int) -> list[str]:
    if market == "vn":
        base = [
            f"{subject}: ket qua nhin thay trong vai giay",
            f"Thu nghiem {subject} ma ban nen xem den cuoi",
            f"Vi sao {subject} lai dang chu y?",
        ]
        if duration_s >= 180:
            base[0] = f"Cau chuyen {subject}: chi tiet thay doi tat ca"
        return base
    base = [
        f"{subject}: the result appears first",
        f"The {niche.replace('_', ' ')} proof worth watching",
        f"Why {subject} changes the outcome",
    ]
    if duration_s >= 180:
        base[0] = f"The {subject} detail that changes the story"
    return base


def _caption(*, subject: str, primary_hook: str, market: str) -> str:
    if market == "vn":
        return _clip(f"{primary_hook} Ke hoach nay duoc chia thanh hook, bang chung va payoff de nguoi xem khong bi roi.", 180)
    return _clip(f"{primary_hook} Built as hook, proof, and payoff so the viewer understands the value fast.", 180)


def _cover_texts(*, subject: str, pattern: dict[str, Any], market: str) -> list[str]:
    if market == "vn":
        return [
            "Ket qua that?",
            "Dung bo lo chi tiet nay",
            f"{_clip(subject, 18)} thay doi gi?",
        ]
    return [
        "Real proof?",
        "Do not miss this detail",
        f"Why {_clip(subject, 18)} works",
    ]


def _cover_frame(*, subject: str, niche: str, pattern: dict[str, Any]) -> str:
    if pattern.get("pattern_id") == "short_drama_reversal_loop":
        return f"emotion close-up or object clue that implies the hidden truth behind {subject}"
    if niche in _SENSORY_NICHES:
        return f"macro frame where {subject} texture/result is instantly readable"
    return f"clearest proof frame where {subject} and result are visible together"


def _cta(*, market: str, target_platform: str, duration_s: int) -> str:
    if duration_s >= 180:
        return "Ask for the next episode or deeper breakdown." if market != "vn" else "Goi mo tap tiep theo hoac phan tiep theo."
    if target_platform in {"tiktok", "reels", "youtube_short", "youtube_shorts"}:
        return "Prompt save/comment/share after proof, not before." if market != "vn" else "Keu goi luu/binh luan sau khi da thay bang chung."
    return "Use a soft next-step CTA tied to the payoff."


def _hashtags(*, niche: str, market: str, target_platform: str) -> list[str]:
    tags = ["aivideo", niche.replace("_", ""), "storytelling"]
    if niche in _PRODUCT_NICHES:
        tags.extend(["productvideo", "ugc", "proof"])
    if niche in _STORY_NICHES:
        tags.extend(["shortfilm", "drama", "cinematic"])
    if niche in _TRUST_NICHES:
        tags.extend(["learn", "explainer", "tips"])
    if market == "vn":
        tags = ["xuhuong", "videoai", *tags]
    if target_platform in {"tiktok", "reels"}:
        tags.append("viral")
    cleaned = []
    seen = set()
    for tag in tags:
        key = "".join(ch.lower() for ch in tag if ch.isalnum())
        if key and key not in seen:
            cleaned.append(f"#{key}")
            seen.add(key)
    return cleaned[:8]


def _posting_hint(platform: str) -> str:
    if platform == "youtube_long":
        return "publish consistently and test title/thumbnail before paid traffic"
    if platform in {"tiktok", "reels", "youtube_short", "youtube_shorts"}:
        return "test 2-3 hooks in the same creative family before scaling"
    return "publish with a clear cover and localized caption"


def _candidate_by_id(candidates: list[dict[str, Any]], pattern_id: str) -> dict[str, Any] | None:
    for item in candidates:
        if item.get("pattern_id") == pattern_id:
            return item
    return None


def _variant_change(variant_id: str, *, subject: str, target_platform: str) -> str:
    if variant_id == "safe_winner":
        return f"Keep the selected pattern and render only one approved {subject} route."
    if variant_id == "bold_scroll_stop":
        return f"Make first frame more aggressive for {target_platform}: faster motion, clearer contradiction."
    if variant_id == "drama_reversal":
        return "Increase conflict, object clues, and cliffhanger handoffs."
    return "Slow the pacing slightly, raise lighting/composition quality, and make the cover frame more premium."


def _subject(parsed: dict[str, Any], niche: str) -> str:
    subject = parsed.get("subject") or {}
    summary = str(subject.get("summary") or "").strip()
    if summary:
        return summary
    hints = subject.get("hints") or []
    if hints:
        return str(hints[0])
    return niche.replace("_", " ")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _brain_id(*, user_idea: str, niche: str, platform: str, duration_s: int) -> str:
    raw = f"{user_idea}|{niche}|{platform}|{duration_s}"
    return "viral_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _clip(value: str, limit: int) -> str:
    value = " ".join((value or "").split())
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


__all__ = ["build_viral_creative_brain"]
