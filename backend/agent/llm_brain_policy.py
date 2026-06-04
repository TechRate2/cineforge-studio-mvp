"""Vendor-free LLM brain routing policy for autonomous video planning.

Phase 1 goal: understand any chat-style user input while keeping cost low.
This module decides which LLM lane should be used before any live LLM call is
made. It does not call AtlasCloud or Anthropic.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from core.config import settings


_FLASH_MODEL = "deepseek-ai/deepseek-v4-flash"
_PRO_MODEL = "deepseek-ai/deepseek-v4-pro"
_VISION_MODEL = "qwen/qwen3-vl-30b-a3b-instruct"
_PREMIUM_MODEL = "anthropic/claude-sonnet-4.6"
_PRO_MODEL_IDS = {_PRO_MODEL}

_LONG_FORM_SIGNALS = {
    "short film",
    "short drama",
    "episode",
    "series",
    "web drama",
    "documentary",
    "founder story",
    "character arc",
    "plot",
    "twist",
    "phim ngan",
    "tap phim",
    "cau chuyen",
    "cot truyen",
}

_HIGH_REASONING_NICHES = {
    "drama",
    "documentary",
    "education",
    "finance_education",
    "medical_wellness",
    "app_saas",
}


def build_llm_brain_policy(
    *,
    user_idea: str,
    target_market: str = "auto",
    target_platform: str = "tiktok",
    duration_s: Optional[int] = None,
    runtime_class: Optional[str] = None,
    reference_counts: Optional[dict[str, int]] = None,
    niche: Optional[str] = None,
    has_dialogue: bool = False,
    speaker_count: int = 1,
    graph_required: bool = False,
    niche_resolution_review_required: bool = False,
    responsible_review_required: bool = False,
    allow_expensive_reasoning: bool = False,
    allow_premium_brain: bool = False,
) -> dict[str, Any]:
    """Return a deterministic, no-vendor-call LLM routing contract.

    Default policy is intentionally cheap:
    - Flash for analyzer/generator.
    - Qwen3-VL only when visual references exist.
    - Pro is only selected for complex briefs when explicitly enabled.
    - Premium Claude brain is only selected when explicitly enabled.
    """
    idea = (user_idea or "").strip()
    refs = _normalize_reference_counts(reference_counts or {})
    duration = _safe_int(duration_s, default=30)
    runtime = (runtime_class or _runtime_from_duration(duration)).strip() or "short"
    selected_niche = (niche or "auto").strip() or "auto"
    complexity = _score_complexity(
        idea=idea,
        duration_s=duration,
        runtime_class=runtime,
        refs=refs,
        niche=selected_niche,
        has_dialogue=has_dialogue,
        speaker_count=speaker_count,
        graph_required=graph_required,
        niche_resolution_review_required=niche_resolution_review_required,
        responsible_review_required=responsible_review_required,
        target_market=target_market,
    )
    band = complexity["band"]
    vision_required = refs["images"] > 0 or refs["pinned_assets"] > 0
    pro_candidate = band in {"complex", "critical"}
    pro_allowed = bool(allow_expensive_reasoning or settings.llm_allow_pro_for_complex_brief)
    pro_selected = bool(pro_candidate and pro_allowed)
    premium_candidate = bool(
        band == "critical"
        or (duration >= 300 and selected_niche in {"drama", "documentary"})
        or responsible_review_required
    )
    premium_allowed = bool(allow_premium_brain or settings.llm_allow_premium_brain)
    premium_selected = bool(premium_candidate and premium_allowed)

    analyzer_model = settings.llm_model_analyzer or _FLASH_MODEL
    configured_generator_model = settings.llm_model_generator or _FLASH_MODEL
    if configured_generator_model in _PRO_MODEL_IDS and not pro_selected:
        configured_generator_model = _FLASH_MODEL
    generator_model = _PRO_MODEL if pro_selected else configured_generator_model
    vision_model = settings.llm_model_vision or _VISION_MODEL
    premium_model = settings.llm_model_premium or _PREMIUM_MODEL

    routes: dict[str, Any] = {
        "insight_extraction": {
            "task": "analyzer",
            "model": analyzer_model,
            "selected": True,
            "reason": "cheap first-pass intent, niche, market, duration, and missing-info extraction",
        },
        "creative_generation": {
            "task": "generator",
            "model": generator_model,
            "selected": True,
            "reason": (
                "complex brief with explicit Pro approval"
                if pro_selected
                else "low-cost default generator; validators and deterministic guards handle most structure"
            ),
            "pro_candidate": pro_candidate,
            "pro_selected": pro_selected,
            "pro_requires_explicit_approval": bool(pro_candidate and not pro_selected),
            "upgrade_candidate": _PRO_MODEL if pro_candidate and not pro_selected else None,
        },
        "premium_director": {
            "task": "premium",
            "model": premium_model,
            "selected": premium_selected,
            "reason": (
                "critical story/review route explicitly approved"
                if premium_selected
                else "locked by default; reserve for final director/critic on critical jobs"
            ),
            "premium_candidate": premium_candidate,
            "premium_requires_explicit_approval": bool(premium_candidate and not premium_selected),
        },
    }
    if vision_required:
        routes["vision_reference_scan"] = {
            "task": "vision",
            "model": vision_model,
            "selected": True,
            "reason": "image or pinned visual references need product/character/style extraction",
        }
    else:
        routes["vision_reference_scan"] = {
            "task": "vision",
            "model": None,
            "selected": False,
            "reason": "no image or pinned visual references",
        }

    execution_order = ["insight_extraction"]
    if vision_required:
        execution_order.append("vision_reference_scan")
    execution_order.append("creative_generation")
    if premium_selected:
        execution_order.append("premium_director")

    cost_mode = (
        "premium_approved"
        if premium_selected
        else "pro_approved"
        if pro_selected
        else "low_cost_flash_qwen"
    )
    return {
        "schema_version": "cinejelly.llm_brain_policy.v1",
        "vendor_calls_performed": False,
        "paid_video_vendor_calls_allowed": False,
        "policy_name": "low_cost_flash_qwen_first",
        "cost_guard": {
            "default_text_model": _FLASH_MODEL,
            "default_vision_model": _VISION_MODEL,
            "pro_default_allowed": bool(settings.llm_allow_pro_for_complex_brief),
            "premium_default_allowed": bool(settings.llm_allow_premium_brain),
            "pro_requires_explicit_approval": True,
            "premium_requires_explicit_approval": True,
            "selected_cost_mode": cost_mode,
        },
        "input_summary": {
            "idea_chars": len(idea),
            "target_market": target_market or "auto",
            "target_platform": target_platform or "tiktok",
            "duration_s": duration,
            "runtime_class": runtime,
            "niche": selected_niche,
            "reference_counts": refs,
            "has_dialogue": bool(has_dialogue),
            "speaker_count": int(max(1, speaker_count or 1)),
            "graph_required": bool(graph_required),
        },
        "complexity": complexity,
        "routes": routes,
        "execution_order": execution_order,
        "route_summary": {
            "complexity_score": complexity["score"],
            "complexity_band": band,
            "primary_text_model": generator_model,
            "analyzer_model": analyzer_model,
            "vision_model": vision_model if vision_required else None,
            "pro_candidate": _PRO_MODEL if pro_candidate else None,
            "pro_selected": pro_selected,
            "premium_candidate": premium_model if premium_candidate else None,
            "premium_selected": premium_selected,
            "cost_mode": cost_mode,
            "safe_default": not pro_selected and not premium_selected,
        },
        "recommended_next_step": _recommended_next_step(
            band=band,
            vision_required=vision_required,
            pro_candidate=pro_candidate,
            pro_selected=pro_selected,
            premium_candidate=premium_candidate,
            premium_selected=premium_selected,
            niche_resolution_review_required=niche_resolution_review_required,
        ),
    }


def _score_complexity(
    *,
    idea: str,
    duration_s: int,
    runtime_class: str,
    refs: dict[str, int],
    niche: str,
    has_dialogue: bool,
    speaker_count: int,
    graph_required: bool,
    niche_resolution_review_required: bool,
    responsible_review_required: bool,
    target_market: str,
) -> dict[str, Any]:
    factors: list[dict[str, Any]] = []

    def add(key: str, points: int, reason: str) -> None:
        if points <= 0:
            return
        factors.append({"key": key, "points": points, "reason": reason})

    words = [w for w in re.split(r"\s+", idea.strip()) if len(w) > 1]
    normalized = _normalize_text(idea)
    if len(words) < 8:
        add("sparse_brief", 12, "brief is short; agent may need clarification or stronger inference")
    elif len(words) > 90:
        add("dense_brief", 8, "brief has many constraints to reconcile")

    if duration_s >= 300:
        add("long_form", 30, "5m+ output needs story, scene memory, and continuity planning")
    elif duration_s >= 180:
        add("micro_film", 24, "3m+ output needs multi-scene graph planning")
    elif duration_s >= 60:
        add("long_short", 12, "60s+ output needs more structured beats than a simple short")

    if graph_required or runtime_class in {"short_film", "episode", "long_form"}:
        add("graph_required", 18, "graph execution and resumable units increase planning complexity")
    if refs["images"] > 0 or refs["pinned_assets"] > 0:
        add("visual_refs", 8, "visual references need Qwen3-VL extraction")
    if refs["videos"] > 0:
        add("motion_refs", 6, "video references add motion/style constraints")
    if refs["audios"] > 0:
        add("audio_refs", 5, "audio references add voice/music timing constraints")
    if sum(refs.values()) >= 5:
        add("many_refs", 8, "many references require role assignment and conflict resolution")
    if has_dialogue:
        add("dialogue", 10, "dialogue/voice/lipsync needs extra script and model routing")
    if speaker_count > 1:
        add("multi_speaker", 8, "multi-speaker scenes increase consistency and dialogue risk")
    if niche in _HIGH_REASONING_NICHES:
        add("high_reasoning_niche", 8, "niche benefits from deeper reasoning and guardrails")
    if any(signal in normalized for signal in _LONG_FORM_SIGNALS):
        add("story_signal", 8, "story/episode signals need narrative arc handling")
    if niche_resolution_review_required:
        add("niche_ambiguous", 18, "niche intent is ambiguous and should be resolved before render")
    if responsible_review_required:
        add("responsible_review", 20, "safety-sensitive request needs conservative handling")
    if (target_market or "auto").lower() == "auto":
        add("market_auto", 3, "market must be inferred from language and context")

    score = min(100, sum(item["points"] for item in factors))
    band = "simple"
    if score >= 75:
        band = "critical"
    elif score >= 50:
        band = "complex"
    elif score >= 25:
        band = "standard"
    return {
        "score": score,
        "band": band,
        "factors": factors,
        "requires_human_clarification": bool(niche_resolution_review_required or score >= 75),
    }


def _recommended_next_step(
    *,
    band: str,
    vision_required: bool,
    pro_candidate: bool,
    pro_selected: bool,
    premium_candidate: bool,
    premium_selected: bool,
    niche_resolution_review_required: bool,
) -> str:
    if niche_resolution_review_required:
        return "ask one clarifying question before paid render"
    if premium_candidate and not premium_selected:
        return "keep Flash/Qwen plan; request explicit premium-brain approval only if final script quality is insufficient"
    if pro_candidate and not pro_selected:
        return "run low-cost Flash/Qwen first; offer Pro upgrade only after user approves extra LLM spend"
    if pro_selected or premium_selected:
        return "run approved higher-reasoning planner, then keep paid video render gated"
    if vision_required:
        return "run Flash analyzer plus Qwen3-VL reference scan, then produce the approval plan"
    if band == "simple":
        return "run Flash-only planning and keep render locked behind approval"
    return "run Flash planning with deterministic validators"


def _normalize_reference_counts(counts: dict[str, int]) -> dict[str, int]:
    return {
        "images": _safe_int(counts.get("images", counts.get("image", 0)), default=0),
        "videos": _safe_int(counts.get("videos", counts.get("video", 0)), default=0),
        "audios": _safe_int(counts.get("audios", counts.get("audio", 0)), default=0),
        "pinned_assets": _safe_int(counts.get("pinned_assets", counts.get("pinned", 0)), default=0),
    }


def _runtime_from_duration(duration_s: int) -> str:
    if duration_s >= 180:
        return "short_film"
    if duration_s >= 60:
        return "extended_short"
    return "short"


def _safe_int(value: Any, *, default: int) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _normalize_text(value: str) -> str:
    return " ".join((value or "").lower().split())


__all__ = ["build_llm_brain_policy"]
