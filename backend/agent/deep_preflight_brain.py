"""Opt-in deep preflight brain for the autonomous Studio.

The normal Send/preflight path remains vendor-free. This module is called only
from an explicit UI action and can optionally use low-cost LLM/Vision models to
turn a loose user request into stronger creative directions before approval.
"""
from __future__ import annotations

import json
import re
from typing import Any

from agent.autonomous_production_decision import build_autonomous_production_decision
from core.config import settings


_IMAGE_ROLES = {
    "product_hero",
    "product_detail",
    "character_anchor",
    "secondary_character",
    "style_reference",
    "environment",
    "brand_asset",
}
_VIDEO_ROLES = {"camera_motion", "motion_style", "shot_pacing"}
_AUDIO_ROLES = {"beat_reference", "sfx_layer", "lip_sync_source"}


def build_deep_preflight_brain(
    *,
    user_idea: str,
    target_market: str = "auto",
    target_platform: str = "tiktok",
    duration_hint_s: int | None = None,
    aspect_ratio: str | None = None,
    reference_counts: dict[str, int] | None = None,
    reference_image_urls: list[str] | None = None,
    reference_video_urls: list[str] | None = None,
    reference_audio_urls: list[str] | None = None,
    reference_manifest: dict[str, Any] | None = None,
    speaker_count: int = 1,
    allow_live_llm: bool = False,
    allow_vision_llm: bool = False,
    product_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deep brief/shot/reference guidance, with optional live LLM calls."""
    idea = (user_idea or "").strip()
    refs = reference_counts or {}
    images = list(reference_image_urls or [])[:9]
    videos = list(reference_video_urls or [])[:3]
    audios = list(reference_audio_urls or [])[:3]
    manifest = reference_manifest or {}
    decision_wrap = build_autonomous_production_decision(
        user_idea=_idea_with_product_context(idea, product_context or {}),
        target_market=target_market,
        target_platform=target_platform,
        duration_hint_s=duration_hint_s,
        reference_counts=refs,
        reference_image_urls=images,
        reference_video_urls=videos,
        reference_audio_urls=audios,
        reference_manifest=manifest,
        speaker_count=speaker_count,
    )
    deterministic = _deterministic_payload(
        idea=idea,
        decision_wrap=decision_wrap,
        reference_manifest=manifest,
        product_context=product_context or {},
        aspect_ratio=aspect_ratio,
    )
    llm_payload: dict[str, Any] = {}
    vision_payload: dict[str, Any] = {}
    errors: list[dict[str, str]] = []
    vendor_calls = False

    if allow_live_llm:
        try:
            llm_payload = _run_text_brain(
                idea=idea,
                decision_wrap=decision_wrap,
                reference_manifest=manifest,
                product_context=product_context or {},
            )
            vendor_calls = True
        except Exception as exc:  # pragma: no cover - depends on external LLM availability
            errors.append({"stage": "text_llm", "error": f"{type(exc).__name__}: {str(exc)[:180]}"})

    if allow_live_llm and allow_vision_llm and images:
        try:
            vision_payload = _run_vision_brain(
                idea=idea,
                image_urls=images,
                reference_manifest=manifest,
            )
            vendor_calls = True
        except Exception as exc:  # pragma: no cover - depends on external LLM availability
            errors.append({"stage": "vision_llm", "error": f"{type(exc).__name__}: {str(exc)[:180]}"})

    merged = _merge_live_payload(deterministic, llm_payload, vision_payload)
    return {
        "schema_version": "cinejelly.deep_preflight_brain.v1",
        "mode": "live_llm_opt_in" if vendor_calls else "deterministic_companion",
        "vendor_calls_performed": vendor_calls,
        "llm_calls_performed": vendor_calls,
        "paid_video_vendor_calls_allowed": False,
        "cost_guard": {
            "trigger": "explicit_user_button_only",
            "text_model": settings.llm_model_generator,
            "vision_model": settings.llm_model_vision if images and allow_vision_llm else None,
            "pro_or_premium_used": False,
            "paid_video_render_started": False,
        },
        "decision_snapshot": _decision_snapshot(decision_wrap),
        "route_source_of_truth": _route_source_of_truth(decision_wrap),
        "deep_brief": merged["deep_brief"],
        "concepts": merged["concepts"],
        "script_upgrade": merged["script_upgrade"],
        "shot_strategy": merged["shot_strategy"],
        "reference_brain": merged["reference_brain"],
        "missing_inputs": merged["missing_inputs"],
        "user_message": merged["user_message"],
        "errors": errors,
        "production_decision": decision_wrap,
    }


def _idea_with_product_context(idea: str, product_context: dict[str, Any]) -> str:
    addition = str(product_context.get("brief_addition") or "").strip()
    if not addition:
        return idea
    combined = f"{idea}\n{addition}".strip()
    return combined[:3000]


def _deterministic_payload(
    *,
    idea: str,
    decision_wrap: dict[str, Any],
    reference_manifest: dict[str, Any],
    product_context: dict[str, Any],
    aspect_ratio: str | None,
) -> dict[str, Any]:
    decision = decision_wrap.get("decision") or {}
    producer = decision_wrap.get("creative_producer_v2") or {}
    viral = decision_wrap.get("viral_creative_brain") or {}
    prompt_contract = decision_wrap.get("prompt_execution_contract_v3") or {}
    route = _route_source_of_truth(decision_wrap)
    niche = str(decision.get("niche") or "ugc_review")
    duration = int(decision.get("target_duration_s") or 30)
    angle = producer.get("selected_angle") or {}
    viral_pattern = viral.get("selected_viral_pattern") or {}
    shots = list((prompt_contract.get("compiled_shots") or [])[:6])
    return {
        "deep_brief": {
            "one_sentence_goal": _goal_sentence(idea, niche, duration),
            "target_viewer": _target_viewer(decision_wrap),
            "viewer_payoff": _viewer_payoff(niche),
            "creative_angle": angle.get("label") or viral_pattern.get("label") or "Proof-first story",
            "tone": _tone_for(niche, duration),
            "output_frame": aspect_ratio or "auto",
            "product_context_used": bool(product_context.get("brief_addition")),
        },
        "concepts": _concepts(niche=niche, duration=duration, producer=producer, viral=viral),
        "script_upgrade": {
            "hook_rule": "Show the visual proof or contradiction first, then explain.",
            "retention_rule": "Every 4-8 seconds must reveal a new proof, conflict, or payoff clue.",
            "payoff_rule": "End with a concrete result, emotional turn, or CTA tied to the user's original ask.",
            "beat_count": len(producer.get("script_beats") or []),
        },
        "shot_strategy": {
            "runtime_class": decision.get("runtime_class"),
            "target_duration_s": duration,
            "aspect_ratio": aspect_ratio or "auto",
            "graph_required": bool(decision.get("graph_required")),
            "primary_visual_model": route.get("primary_visual_model"),
            "unit_rule": "Split into 4-15s physically filmable Seedance units.",
            "first_shots": [
                {
                    "shot_id": shot.get("shot_id"),
                    "duration_s": shot.get("duration_s"),
                    "model_key": shot.get("model_key"),
                    "render_mode": shot.get("render_mode"),
                    "prompt_preview": str(shot.get("prompt") or "")[:240],
                }
                for shot in shots
            ],
        },
        "reference_brain": _reference_brain_from_manifest(reference_manifest),
        "missing_inputs": _missing_inputs(decision_wrap),
        "user_message": _user_message(decision_wrap),
    }


def _run_text_brain(
    *,
    idea: str,
    decision_wrap: dict[str, Any],
    reference_manifest: dict[str, Any],
    product_context: dict[str, Any],
) -> dict[str, Any]:
    from vendors.llm_router import llm

    compact = {
        "user_idea": idea[:2000],
        "decision": decision_wrap.get("decision"),
        "creative_plan": (decision_wrap.get("creative_producer_v2") or {}).get("selected_angle"),
        "viral_pattern": (decision_wrap.get("viral_creative_brain") or {}).get("selected_viral_pattern"),
        "prompt_model_plan": (decision_wrap.get("prompt_execution_contract_v3") or {}).get("model_plan"),
        "reference_manifest": reference_manifest,
        "product_context": {
            "title": product_context.get("title"),
            "description": product_context.get("description"),
            "keywords": product_context.get("product_keywords"),
        },
    }
    system = (
        "You are a senior AI video creative producer. Return only compact JSON. "
        "Do not call tools. Do not invent paid renders. Improve the video brief, "
        "hook, shot strategy, missing inputs, and reference usage."
    )
    user = (
        "Return JSON with keys: deep_brief, concepts, script_upgrade, "
        "shot_strategy, missing_inputs, user_message. Keep it practical for a "
        "Seedance autonomous render.\n\nCONTEXT:\n"
        + json.dumps(compact, ensure_ascii=False)
    )
    raw = llm.complete(system, user, task="generator", max_tokens=1800, temperature=0.35)
    parsed = _parse_json_object(raw)
    return parsed if isinstance(parsed, dict) else {}


def _run_vision_brain(
    *,
    idea: str,
    image_urls: list[str],
    reference_manifest: dict[str, Any],
) -> dict[str, Any]:
    from vendors.llm_router import llm

    system = (
        "Classify uploaded video references for a Seedance prompt. Return only JSON. "
        "Allowed image roles: product_hero, product_detail, character_anchor, "
        "secondary_character, style_reference, environment, brand_asset."
    )
    user = (
        "For each image in order, return {tag, role, confidence, reason}. "
        "Do not confirm the role; only suggest. User idea: "
        f"{idea[:1200]}\nExisting manifest:\n"
        + json.dumps(reference_manifest, ensure_ascii=False)
    )
    raw = llm.complete_with_image(system, user, image_urls[:9], max_tokens=900)
    parsed = _parse_json_object(raw)
    suggestions = parsed.get("suggestions") if isinstance(parsed, dict) else parsed
    if not isinstance(suggestions, list):
        suggestions = []
    return {"reference_brain": {"vision_suggestions": _sanitize_vision_suggestions(suggestions)}}


def _merge_live_payload(
    deterministic: dict[str, Any],
    llm_payload: dict[str, Any],
    vision_payload: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(deterministic)
    for key in ("deep_brief", "script_upgrade", "shot_strategy"):
        if isinstance(llm_payload.get(key), dict):
            merged[key] = {**merged.get(key, {}), **llm_payload[key]}
    if isinstance(llm_payload.get("concepts"), list) and llm_payload["concepts"]:
        merged["concepts"] = llm_payload["concepts"][:4]
    if isinstance(llm_payload.get("missing_inputs"), list):
        merged["missing_inputs"] = llm_payload["missing_inputs"][:8]
    if isinstance(llm_payload.get("user_message"), str) and llm_payload["user_message"].strip():
        merged["user_message"] = llm_payload["user_message"].strip()[:800]
    vision_ref = (vision_payload.get("reference_brain") or {}) if isinstance(vision_payload, dict) else {}
    if vision_ref.get("vision_suggestions"):
        merged["reference_brain"] = {
            **(merged.get("reference_brain") or {}),
            "vision_suggestions": vision_ref["vision_suggestions"],
            "source": "qwen_vision_llm_suggestion",
        }
    return merged


def _parse_json_object(raw: str) -> Any:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"(\{.*\}|\[.*\])", text, flags=re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(1))
        except Exception:
            return {}


def _sanitize_vision_suggestions(items: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, item in enumerate(items[:9], start=1):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        if role not in _IMAGE_ROLES:
            role = "style_reference"
        try:
            confidence = float(item.get("confidence") or 0.65)
        except Exception:
            confidence = 0.65
        tag = str(item.get("tag") or f"@image_{idx}").strip()
        if tag and not tag.startswith("@"):
            tag = f"@{tag}"
        out.append({
            "tag": tag or f"@image_{idx}",
            "role": role,
            "confidence": max(0.0, min(1.0, confidence)),
            "reason": str(item.get("reason") or "Vision model role suggestion.")[:180],
            "role_confirmed": False,
        })
    return out


def _reference_brain_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    items = manifest.get("items") if isinstance(manifest, dict) else []
    rows: list[dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip().lower()
        role = str(item.get("role") or "unknown").strip().lower()
        allowed = _IMAGE_ROLES if kind == "image" else _VIDEO_ROLES if kind == "video" else _AUDIO_ROLES
        status = "confirmed" if item.get("role_confirmed") and role in allowed else "needs_user_confirm"
        rows.append({
            "tag": item.get("tag"),
            "kind": kind,
            "role": role if role in allowed else "unknown",
            "status": status,
            "confidence": 1.0 if status == "confirmed" else 0.55,
            "prompt_binding": item.get("prompt_binding") or "",
        })
    return {
        "source": "confirmed_manifest" if manifest.get("confirmed") else "ui_auto_manifest",
        "role_mix_safe_for_paid_render": bool(manifest.get("confirmed")) if rows else True,
        "items": rows,
        "policy": "Never use an unconfirmed @reference as product, character, camera, motion, beat, SFX or voice in paid render.",
    }


def _decision_snapshot(decision_wrap: dict[str, Any]) -> dict[str, Any]:
    decision = decision_wrap.get("decision") or {}
    return {
        "niche": decision.get("niche"),
        "target_market": decision.get("target_market"),
        "target_platform": decision.get("target_platform"),
        "runtime_class": decision.get("runtime_class"),
        "target_duration_s": decision.get("target_duration_s"),
        "graph_required": decision.get("graph_required"),
        "dialogue_required": decision.get("dialogue_required"),
    }


def _route_source_of_truth(decision_wrap: dict[str, Any]) -> dict[str, Any]:
    strategy = decision_wrap.get("model_route_strategy") or {}
    summary = strategy.get("summary") or {}
    prompt_plan = (decision_wrap.get("prompt_execution_contract_v3") or {}).get("model_plan") or {}
    return {
        "primary_visual_model": summary.get("primary_visual_model") or prompt_plan.get("primary_visual_model"),
        "continuity_model": summary.get("continuity_model") or prompt_plan.get("continuity_model"),
        "draft_visual_model": summary.get("draft_visual_model"),
        "premium_visual_model": summary.get("premium_visual_model"),
        "route_mode": summary.get("route_mode"),
        "source": "model_route_strategy.summary",
    }


def _goal_sentence(idea: str, niche: str, duration: int) -> str:
    subject = (idea or "").strip().split("\n")[0][:140] or niche.replace("_", " ")
    return f"Create a {duration}s {niche.replace('_', ' ')} video that turns '{subject}' into a clear hook, proof sequence, and payoff."


def _target_viewer(decision_wrap: dict[str, Any]) -> str:
    market = ((decision_wrap.get("market_playbook") or {}).get("target_market") or "auto").upper()
    niche = ((decision_wrap.get("decision") or {}).get("niche") or "ugc").replace("_", " ")
    return f"{market} viewers who care about {niche} proof, emotion, or transformation."


def _viewer_payoff(niche: str) -> str:
    if niche in {"beauty", "food", "fashion", "ecommerce_catalog"}:
        return "See credible product proof, texture, and result fast."
    if niche in {"drama", "documentary", "restaurant_hospitality"}:
        return "Feel a clear emotional turn and remember the final reveal."
    if niche in {"app_saas", "education", "finance_education"}:
        return "Understand the problem and see the useful result without friction."
    return "Get one clear visual reason to watch, trust, and act."


def _tone_for(niche: str, duration: int) -> str:
    if duration >= 180:
        return "cinematic, coherent, emotionally paced"
    if niche in {"beauty", "fashion", "food"}:
        return "premium UGC, tactile, fast proof"
    if niche in {"app_saas", "education"}:
        return "sharp, clear, proof-led"
    return "high-retention social, visual-first"


def _concepts(*, niche: str, duration: int, producer: dict[str, Any], viral: dict[str, Any]) -> list[dict[str, Any]]:
    angle = producer.get("selected_angle") or {}
    pattern = viral.get("selected_viral_pattern") or {}
    return [
        {
            "id": "primary",
            "label": angle.get("label") or "Proof-first transformation",
            "hook": angle.get("hook") or pattern.get("hook_formula") or "Show the result before explaining.",
            "engine": angle.get("story_engine") or pattern.get("retention_engine") or "hook -> proof -> payoff",
            "best_for": f"{niche.replace('_', ' ')} / {duration}s",
        },
        {
            "id": "safer_variant",
            "label": "Clarity-first fallback",
            "hook": "Start with the user's problem in one readable visual.",
            "engine": "problem -> proof -> simple resolution -> CTA",
            "best_for": "When references are weak or budget is limited.",
        },
    ]


def _missing_inputs(decision_wrap: dict[str, Any]) -> list[dict[str, str]]:
    report = decision_wrap.get("autonomous_input_upgrade_plan") or {}
    actions = report.get("priority_actions") or []
    out: list[dict[str, str]] = []
    for action in actions[:6]:
        if not isinstance(action, dict):
            continue
        out.append({
            "priority": str(action.get("priority") or "recommended"),
            "kind": str(action.get("kind") or "input"),
            "action": str(action.get("action") or ""),
            "why": str(action.get("why") or ""),
        })
    return out


def _user_message(decision_wrap: dict[str, Any]) -> str:
    plan = decision_wrap.get("autonomous_input_upgrade_plan") or {}
    message = str(plan.get("user_message") or "").strip()
    if message:
        return message[:700]
    decision = decision_wrap.get("decision") or {}
    return (
        f"Deep preflight is ready for {decision.get('niche')} / "
        f"{decision.get('target_duration_s')}s. Review references and approve only when the shot contract is acceptable."
    )


__all__ = ["build_deep_preflight_brain"]
