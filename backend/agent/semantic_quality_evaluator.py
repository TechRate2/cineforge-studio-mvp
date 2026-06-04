"""Vision-based semantic QA for rendered video frame samples.

This evaluator consumes persisted QA frame URLs and checks whether the clip
appears to satisfy the shot contract. It is fail-soft: render should still
complete if the vision model is unavailable.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from loguru import logger

from agent.schemas import ContinuityBible, Shot
from vendors.llm_router import llm


_SYSTEM_PROMPT = """You are a strict AI video QA supervisor.

You receive first/middle/last frame samples from one rendered video shot plus
the production contract. Judge only what is visible in the frames. Do not invent
facts you cannot see.

Return exactly one JSON object:
{
  "status": "pass" | "warn" | "fail",
  "score": 0-10,
  "visible_summary": "...",
  "failures": ["..."],
  "retry_recommended": true | false,
  "retry_reason": null | "...",
  "checks": {
    "identity_continuity": "pass|warn|fail|unknown",
    "product_fidelity": "pass|warn|fail|unknown",
    "prompt_adherence": "pass|warn|fail|unknown",
    "caption_artifacts": "pass|warn|fail|unknown",
    "cinematic_quality": "pass|warn|fail|unknown"
  }
}
"""

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def evaluate_render_frames(
    *,
    bible: ContinuityBible,
    shot: Optional[Shot],
    frame_samples: dict[str, Any],
    output_scope: str = "shot",
) -> dict[str, Any]:
    """Run vision QA over sampled frames. Returns fail-soft structured report."""
    frame_urls = [
        str(f.get("url") or "")
        for f in (frame_samples.get("frames") or [])
        if str(f.get("url") or "").startswith(("http://", "https://", "data:image"))
    ][:3]
    base_report = {
        "status": "unavailable",
        "score": None,
        "retry_recommended": False,
        "retry_reason": None,
        "frame_count": len(frame_urls),
        "failures": [],
        "checks": {},
    }
    if not frame_urls:
        return {
            **base_report,
            "reason": "no_public_frame_urls",
        }

    payload = {
        "scope": output_scope,
        "shot": shot.model_dump() if shot else None,
        "bible_contract": {
            "title": bible.title,
            "logline": bible.logline,
            "characters": [c.model_dump() for c in bible.characters],
            "products": [p.model_dump() for p in bible.products],
            "visual_style": bible.visual_style.model_dump(),
            "setting": bible.setting.model_dump(),
            "must_have": bible.constraints.must_have,
            "must_avoid": bible.constraints.must_avoid,
        },
        "instruction": (
            "Inspect the attached frame samples as one rendered clip. "
            "Flag face/product drift, prompt mismatch, text/caption artifacts, "
            "broken anatomy, bad composition, or obvious continuity issues."
        ),
    }
    try:
        raw = llm.complete_with_image(
            system_prompt=_SYSTEM_PROMPT,
            user_message=json.dumps(payload, ensure_ascii=False),
            image_urls=frame_urls,
            task="vision",
            max_tokens=1200,
        )
        data = _parse_json(raw)
        return _normalize_report(data, len(frame_urls))
    except Exception as exc:
        logger.warning(f"[SemanticQA] vision evaluator unavailable: {type(exc).__name__}: {exc}")
        return {
            **base_report,
            "reason": f"vision_evaluator_error:{type(exc).__name__}",
        }


def _parse_json(raw: str) -> dict[str, Any]:
    cleaned = _FENCE_RE.sub("", raw or "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        s, e = cleaned.find("{"), cleaned.rfind("}")
        if s >= 0 and e > s:
            return json.loads(cleaned[s:e + 1])
        raise


def _normalize_report(data: dict[str, Any], frame_count: int) -> dict[str, Any]:
    status = str(data.get("status") or "warn").lower()
    if status not in {"pass", "warn", "fail"}:
        status = "warn"
    try:
        score = max(0.0, min(10.0, float(data.get("score"))))
    except (TypeError, ValueError):
        score = None
    failures = [str(x) for x in (data.get("failures") or [])][:8]
    retry_recommended = bool(data.get("retry_recommended")) or status == "fail"
    return {
        "status": status,
        "score": score,
        "visible_summary": str(data.get("visible_summary") or "")[:500],
        "failures": failures,
        "retry_recommended": retry_recommended,
        "retry_reason": data.get("retry_reason") if retry_recommended else None,
        "checks": data.get("checks") if isinstance(data.get("checks"), dict) else {},
        "frame_count": frame_count,
    }


__all__ = ["evaluate_render_frames"]
