"""Plan shot-level retries from render quality reports.

This is the producer/QA bridge between semantic evaluation and an eventual
auto-retry executor. It decides which shots are retry candidates and records
prompt repair hints without re-rendering anything by itself.
"""
from __future__ import annotations

from typing import Any, Optional


def build_retry_plan(
    *,
    render_quality: list[dict[str, Any]],
    production_graph: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    retry_policy = (production_graph or {}).get("retry_policy") or {}
    max_retries = int(retry_policy.get("max_retries_per_shot") or 1)
    items: list[dict[str, Any]] = []

    for report in render_quality:
        if not report.get("retry_recommended"):
            continue
        criteria = report.get("criteria") or {}
        shot_id = str(criteria.get("shot_id") or "ALL")
        semantic = criteria.get("semantic_quality") or {}
        media_probe = criteria.get("media_probe") or {}
        strong_gate = criteria.get("strong_quality_gate") or {}
        failures = [
            *list(strong_gate.get("hard_failures") or []),
            *list(semantic.get("failures") or []),
        ]
        retry_reason = report.get("retry_reason") or semantic.get("retry_reason")
        if not retry_reason:
            retry_reason = _fallback_reason(report, media_probe, failures)

        items.append({
            "shot_id": shot_id,
            "scope": criteria.get("scope") or "shot",
            "status": "queued",
            "max_retries": max_retries,
            "attempts_done": 0,
            "reason": retry_reason,
            "severity": "high" if report.get("status") == "fail" else "medium",
            "score": report.get("score"),
            "prompt_repair_hint": _repair_hint(retry_reason, failures, criteria),
            "preserve": {
                "model_key": criteria.get("model_key"),
                "render_mode": criteria.get("render_mode"),
                "style_anchor": criteria.get("style_anchor"),
                "character_ids": criteria.get("character_ids") or [],
                "product_ids": criteria.get("product_ids") or [],
            },
        })

    return {
        "enabled": False,
        "executor_status": "not_implemented",
        "retry_scope": retry_policy.get("retry_scope") or "shot",
        "max_retries_per_shot": max_retries,
        "items": items,
        "summary": {
            "retry_count": len(items),
            "has_retries": bool(items),
            "high_severity_count": len([i for i in items if i["severity"] == "high"]),
        },
        "next_step": (
            "Execute queued retry items by regenerating only failed shots, then "
            "replace their clip paths before final assembly."
        ),
    }


def _fallback_reason(report: dict[str, Any], media_probe: dict[str, Any], failures: list[str]) -> str:
    if failures:
        return failures[0]
    if media_probe.get("errors"):
        return str(media_probe["errors"][0])
    for check in report.get("checks") or []:
        if check.get("status") in {"fail", "warn"}:
            return str(check.get("detail") or check.get("name"))
    return "quality_gate_retry_recommended"


def _repair_hint(reason: str, failures: list[str], criteria: dict[str, Any]) -> str:
    text = " ".join([reason, *failures]).lower()
    if "identity" in text or "face" in text or "character" in text:
        return (
            "Re-render with stronger @image character binding, repeat exact face/outfit, "
            "reduce competing refs, and use previous last_frame when continuity matters."
        )
    if "product" in text or "logo" in text or "packaging" in text:
        return (
            "Re-render with product hero reference prioritized, explicit packaging/color/label "
            "instructions, and ban product/logo drift."
        )
    if "caption" in text or "text" in text or "watermark" in text:
        return "Re-render with no text overlay, no duplicated caption, no watermark, and keep captions for post-production only."
    if "duration" in text:
        return f"Re-render at exact target duration for {criteria.get('shot_id') or 'shot'} and avoid overlong actions."
    if "motion" in text or "camera" in text:
        return "Re-render with one simple physically filmable action and explicit camera movement from the reference manifest."
    return (
        "Re-render preserving the production bible, reference manifest, style anchor, "
        "and shot purpose while simplifying the action."
    )


__all__ = ["build_retry_plan"]
