"""Evaluation Layer — self-critique cho Director Plan.

1 LLM call (analyzer tier) → EvaluationReport JSON.
Fail-soft: nếu LLM lỗi → trả EvaluationReport zeros + ghi log.
"""
from __future__ import annotations

import json
import re

from loguru import logger

from agent.schemas import EvaluationReport
from system_prompts import load as load_system_prompt
from vendors.llm_router import llm


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _parse(raw: str) -> dict:
    cleaned = _FENCE_RE.sub("", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        s, e = cleaned.find("{"), cleaned.rfind("}")
        if s >= 0 and e > s:
            return json.loads(cleaned[s:e + 1])
        raise


def evaluate_plan(plan_dict: dict, user_brief: str, tech_config: dict) -> EvaluationReport:
    """Sync — caller wrap qua asyncio.to_thread."""
    system = load_system_prompt("evaluation")
    user_payload = {
        "director_plan": {
            "continuity_bible": plan_dict.get("continuity_bible"),
            "shot_list": plan_dict.get("shot_list"),
            "storyboard_grid": plan_dict.get("storyboard_grid"),
        },
        "user_brief": user_brief,
        "tech_config": tech_config,
    }
    user_msg = json.dumps(user_payload, ensure_ascii=False)

    raw = llm.complete(
        system_prompt=system,
        user_message=user_msg,
        task="analyzer",
        max_tokens=2000,
        temperature=0.3,
    )
    try:
        data = _parse(raw)
    except Exception as e:
        logger.warning(f"[EvaluationLayer] parse fail: {e} — raw head: {raw[:200]}")
        return EvaluationReport(
            consistency_score=0, viral_potential_score=0, cinematic_score=0,
            pacing_score=0, brand_safety_score=0, overall_score=0,
            weaknesses=["evaluation_parse_failed"],
        )

    try:
        return EvaluationReport(**data)
    except Exception as e:
        logger.warning(f"[EvaluationLayer] schema fail: {e}")
        # Best-effort coerce
        def f(key: str, default: float = 0.0) -> float:
            try:
                return max(0.0, min(10.0, float(data.get(key, default))))
            except (TypeError, ValueError):
                return default
        return EvaluationReport(
            consistency_score=f("consistency_score"),
            viral_potential_score=f("viral_potential_score"),
            cinematic_score=f("cinematic_score"),
            pacing_score=f("pacing_score"),
            brand_safety_score=f("brand_safety_score"),
            overall_score=f("overall_score"),
            strengths=list(data.get("strengths") or [])[:8],
            weaknesses=list(data.get("weaknesses") or [])[:8],
            suggestions=list(data.get("suggestions") or [])[:8],
            red_flags=list(data.get("red_flags") or [])[:5],
        )
