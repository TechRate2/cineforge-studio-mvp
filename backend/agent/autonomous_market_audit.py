"""Market/localization audit for the autonomous one-click workflow.

The UI should stay simple: idea, references, language/market guidance when the
user cares, and one generate button. This module verifies that the backend can
still localize the production chain by market without exposing a model picker or
manual mode.
"""
from __future__ import annotations

from typing import Any

from agent.autonomous_production_decision import build_autonomous_production_decision


_MARKETS = ("auto", "vn", "us", "sea", "jp", "kr", "global")

_SHORT_IDEAS = {
    "auto": "Vietnamese TikTok review for a skincare serum, visible texture proof, creator voice",
    "vn": "Đánh giá serum dưỡng da cho TikTok Việt Nam, có proof cận mặt và caption tiếng Việt",
    "us": "US creator review for a skincare serum with fast visible texture proof",
    "sea": "Southeast Asia value-aware skincare serum review for mobile commerce",
    "jp": "Japanese skincare serum ritual with restrained curiosity and close product detail",
    "kr": "Korean beauty serum reveal with polished trend-aware pacing",
    "global": "Global skincare serum review with visual proof and simple English captions",
}

_LONG_IDEAS = {
    "auto": "phim ngắn 5 phút có thoại tiếng Việt về bí mật gia đình, cảm xúc mạnh, cú twist cuối",
    "vn": "Phim ngắn 5 phút có thoại tiếng Việt về bí mật gia đình, cảm xúc mạnh, cú twist cuối",
    "us": "Five-minute English short drama about a family secret with natural dialogue and a final twist",
    "sea": "Five-minute Southeast Asia short drama about a family secret with warm practical realism",
    "jp": "Five-minute Japanese-style quiet short drama about a family secret and restrained emotional reveal",
    "kr": "Five-minute Korean-style polished short drama about a family secret and emotional reveal",
    "global": "Five-minute global English short drama about a family secret with a clear emotional twist",
}


def build_autonomous_market_audit() -> dict[str, Any]:
    """Return a source-backed market x runtime audit without LLM/vendor calls."""
    short_rows = [_audit_case(market=market, long_form=False) for market in _MARKETS]
    long_rows = [_audit_case(market=market, long_form=True) for market in _MARKETS]
    rows = [*short_rows, *long_rows]
    vn_long = next(row for row in long_rows if row["requested_market"] == "vn")

    return {
        "schema_version": "cinejelly.autonomous_market_audit.v1",
        "summary": {
            "market_count": len(_MARKETS),
            "auto_default_recommended": True,
            "override_supported": True,
            "model_choice_hidden": True,
            "short_auto_allowed_count": len([row for row in short_rows if row["auto_route_allowed"] and not row["blocked"]]),
            "long_graph_required_count": len([row for row in long_rows if row["graph_required"]]),
            "manual_review_count": len([row for row in rows if row["manual_review_required"]]),
            "vn_dialogue_candidate": vn_long.get("dialogue_candidate"),
            "vn_post_process_candidate": vn_long.get("post_process_candidate"),
            "top_tier_claim_allowed": any(row["top_tier_claim_allowed"] for row in rows),
        },
        "policy": {
            "ux_default": "Keep market on Auto by default. Add optional target audience/language control only as script-localization guidance.",
            "model_policy": "Hide model selection from users; route Seedance/dialogue/lipsync internally through evidence gates.",
            "vietnam_policy": "Vietnamese dialogue and lip-sync can be planned now, but automatic routing stays benchmark-gated until real outputs pass QA.",
            "long_form_policy": "Anything around 5 minutes or longer must be graph-planned into Seedance-sized shots with continuity handoffs and QA gates.",
            "top_tier_policy": "This audit may show route readiness, never top-tier parity, until paid benchmark evidence is promoted.",
        },
        "short_30s": short_rows,
        "long_5m": long_rows,
    }


def _audit_case(*, market: str, long_form: bool) -> dict[str, Any]:
    decision = build_autonomous_production_decision(
        user_idea=(_LONG_IDEAS if long_form else _SHORT_IDEAS)[market],
        target_market=market,
        target_platform="youtube_long" if long_form else "tiktok",
        duration_hint_s=300 if long_form else 30,
        reference_counts=(
            {"images": 4, "videos": 1, "audios": 1, "pinned_assets": 1}
            if long_form
            else {"images": 3, "videos": 1, "audios": 1}
        ),
        niche_hint="drama" if long_form else "beauty",
        speaker_count=2 if long_form else 1,
    )
    d = decision.get("decision") or {}
    route = d.get("primary_model_route") or {}
    dialogue = d.get("dialogue_route_policy") or {}
    market_playbook = decision.get("market_playbook") or {}
    inference = (
        market_playbook.get("market_inference")
        or (decision.get("input_summary") or {}).get("market_inference")
        or {}
    )
    score = decision.get("route_quality_scorecard") or {}
    safety = decision.get("responsible_content_gate") or {}

    return {
        "requested_market": market,
        "effective_market": market_playbook.get("target_market") or d.get("target_market"),
        "inference_source": inference.get("source"),
        "inference_confidence": inference.get("confidence"),
        "inference_reasons": inference.get("reasons") or [],
        "runtime_class": d.get("runtime_class"),
        "duration_s": d.get("target_duration_s"),
        "niche": d.get("niche"),
        "primary_language": market_playbook.get("primary_language"),
        "caption_language": market_playbook.get("caption_language"),
        "hook_style": market_playbook.get("hook_style"),
        "dialogue_style": market_playbook.get("dialogue_style"),
        "claim_style": market_playbook.get("claim_style"),
        "primary_visual_model": route.get("primary_visual_model"),
        "continuity_model": route.get("continuity_model"),
        "dialogue_required": bool(d.get("dialogue_required")),
        "dialogue_route": dialogue.get("route_type"),
        "dialogue_language": dialogue.get("target_language"),
        "dialogue_candidate": dialogue.get("dialogue_candidate"),
        "post_process_candidate": dialogue.get("post_process_candidate"),
        "graph_required": bool(d.get("graph_required")),
        "auto_route_allowed": bool(score.get("auto_route_allowed")),
        "top_tier_claim_allowed": bool(score.get("top_tier_claim_allowed")),
        "manual_review_required": bool(
            safety.get("manual_review_required")
            or d.get("responsible_review_required")
            or dialogue.get("requires_benchmark_before_auto_route")
        ),
        "blocked": bool(
            safety.get("render_allowed") is False
            or d.get("render_blocked_by_responsible_gate")
        ),
    }


__all__ = ["build_autonomous_market_audit"]
