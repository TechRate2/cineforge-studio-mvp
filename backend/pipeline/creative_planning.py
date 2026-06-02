"""Creative planning for Phase 2.

The planner decides shot mode, reference strategy, consistency locks, and a
niche playbook before storyboard generation. It avoids render execution and
keeps decisions visible in CreativePlan metadata.
"""
from __future__ import annotations

import re
from typing import Any

from pipeline.contracts import AnalyzedInput, CreativePlan


_PLAYBOOKS: dict[str, dict[str, Any]] = {
    "product": {
        "hook_pattern": "problem/detail hook -> hero product reveal -> clear payoff frame",
        "style": "clean cinematic product commercial, premium lighting, stable product geometry",
        "audio": "subtle commercial music bed with tactile product sound details",
        "arc": ["detail/problem hook", "hero product reveal", "clear payoff frame"],
    },
    "beauty": {
        "hook_pattern": "macro texture hook -> product reveal -> payoff beauty frame",
        "style": "clean cinematic commercial, premium reflective materials, soft studio light",
        "audio": "subtle premium ambience with light product handling sounds",
        "arc": ["sensory macro hook", "hero product reveal", "benefit/payoff frame"],
    },
    "food": {
        "hook_pattern": "sensory preparation -> texture macro -> serve/eat payoff",
        "style": "documentary food commercial, warm natural light, tactile macro detail",
        "audio": "cooking ASMR, natural room tone, soft music bed",
        "arc": ["ingredient hook", "craft/process detail", "serve moment"],
    },
    "fashion": {
        "hook_pattern": "entrance silhouette -> material transformation -> editorial hero",
        "style": "high-fashion editorial, cinematic runway lighting, controlled movement",
        "audio": "stylized fashion pulse, fabric and step details",
        "arc": ["silhouette entrance", "material/action transformation", "hero editorial finish"],
    },
    "drama": {
        "hook_pattern": "quiet tension -> emotional reveal -> reaction payoff",
        "style": "cinematic drama, shallow depth of field, natural micro-expression focus",
        "audio": "room tone, restrained dialogue, emotional ambience",
        "arc": ["setup tension", "character reveal", "emotional payoff"],
    },
    "anime": {
        "hook_pattern": "power stance -> fast clash -> impact frame",
        "style": "anime/live-action hybrid energy, clear silhouettes, controlled effects",
        "audio": "impact hits, energy build, crowd or ambience as needed",
        "arc": ["charge-up", "motion clash", "impact resolution"],
    },
    "ugc": {
        "hook_pattern": "human hook -> proof/demo -> reaction",
        "style": "phone-camera realism, natural light, candid handheld energy",
        "audio": "natural spoken delivery with light room tone",
        "arc": ["creator hook", "proof/demo", "reaction or CTA"],
    },
    "sports": {
        "hook_pattern": "pre-action tension -> explosive move -> hero result",
        "style": "premium sports commercial, high contrast lighting, dynamic motion",
        "audio": "crowd swell, impact hits, rhythmic build",
        "arc": ["tension setup", "action escalation", "hero result"],
    },
    "cinematic": {
        "hook_pattern": "establishing image -> escalation -> cinematic climax",
        "style": "high-fidelity cinematic realism, motivated camera, strong atmosphere",
        "audio": "cinematic ambience and action-synced sound design",
        "arc": ["establish world", "escalate motion", "climax image"],
    },
}


class CreativePlanner:
    """Plan creative structure from AnalyzedInput without rendering anything."""

    def plan(self, analyzed_input: AnalyzedInput) -> CreativePlan:
        """Return a CreativePlan with Phase 2 creative decisions in metadata."""
        niche = _normalize_niche(analyzed_input.detected_niche)
        playbook = _PLAYBOOKS.get(niche, _PLAYBOOKS["cinematic"])
        duration_s = _seedance_duration(analyzed_input.duration_s)
        complexity = _complexity_score(analyzed_input)
        shot_mode = "multi_shot" if complexity >= 2 else "single_shot"
        shot_count = _decide_shot_count(duration_s=duration_s, complexity=complexity, niche=niche)
        if shot_count <= 1:
            shot_mode = "single_shot"

        asset_mode = _asset_mode(analyzed_input.asset_summary)
        reference_strategy = _reference_strategy(
            analyzed_input=analyzed_input,
            asset_mode=asset_mode,
            shot_mode=shot_mode,
        )
        consistency_plan = _consistency_plan(analyzed_input, niche=niche)

        return CreativePlan(
            analysis_id=analyzed_input.analysis_id,
            target_niche=niche,
            objective=str(analyzed_input.metadata.get("objective") or analyzed_input.normalized_idea),
            hook_pattern=playbook["hook_pattern"],
            narrative_arc=list(playbook["arc"]) if shot_mode == "multi_shot" else [playbook["arc"][0]],
            shot_count=shot_count,
            duration_s=duration_s,
            aspect_ratio=analyzed_input.aspect_ratio or "9:16",
            reference_strategy=reference_strategy,
            consistency_plan=consistency_plan,
            style_direction=playbook["style"],
            audio_direction=playbook["audio"],
            constraints=_planning_constraints(consistency_plan),
            metadata={
                "phase": "2",
                "shot_mode": shot_mode,
                "asset_mode": asset_mode,
                "niche_playbook": niche,
                "complexity_score": complexity,
                "reference_sufficiency": analyzed_input.asset_summary.get("reference_sufficiency"),
                "planning_rules": [
                    "phase2.planner.single_vs_multi_shot",
                    "phase2.planner.reference_strategy",
                    "phase2.planner.consistency_locks",
                    "phase2.planner.niche_playbook",
                ],
            },
        )


def _complexity_score(analyzed_input: AnalyzedInput) -> int:
    text = analyzed_input.normalized_idea.lower()
    score = 0
    if (analyzed_input.duration_s or 0) >= 10:
        score += 1
    if re.search(r"\b(then|after|next|cut to|scene|sequence|story|dialogue)\b", text):
        score += 1
    if analyzed_input.detected_niche in {"drama", "anime", "sports", "cinematic", "fashion"}:
        score += 1
    if (analyzed_input.duration_s or 0) >= 12 and analyzed_input.detected_niche in {"beauty", "food", "fashion", "product"}:
        score += 1
    if re.search(r"\b(macro|reveal|payoff|process|craft|serve|hero)\b", text):
        score += 1
    if (analyzed_input.asset_summary.get("asset_count") or 0) >= 2:
        score += 1
    return score


def _decide_shot_count(*, duration_s: int, complexity: int, niche: str) -> int:
    max_seedance_shots = max(1, duration_s // 4)
    if complexity < 2 and duration_s <= 9:
        return 1
    if niche == "ugc" and duration_s <= 10:
        return min(2, max_seedance_shots)
    if duration_s >= 14 and complexity >= 4:
        return min(5, max_seedance_shots)
    if duration_s >= 10 or complexity >= 2:
        return min(3 if complexity <= 3 else 4, max_seedance_shots)
    return 1


def _asset_mode(asset_summary: dict[str, Any]) -> str:
    counts = asset_summary.get("kind_counts") or {}
    active_kinds = {kind for kind in ("image", "video", "audio") if int(counts.get(kind) or 0) > 0}
    if not active_kinds:
        return "t2v"
    if active_kinds == {"image"}:
        return "i2v"
    if active_kinds == {"video"}:
        return "v2v"
    if active_kinds == {"audio"}:
        return "audio_driven"
    if "audio" in active_kinds and len(active_kinds) == 2:
        return "audio_driven"
    if len(active_kinds) > 1:
        return "multi_reference"
    return "mixed"


def _reference_strategy(
    *,
    analyzed_input: AnalyzedInput,
    asset_mode: str,
    shot_mode: str,
) -> dict[str, Any]:
    summary = analyzed_input.asset_summary
    return {
        "asset_mode": asset_mode,
        "shot_mode": shot_mode,
        "sufficiency": summary.get("reference_sufficiency"),
        "missing_roles": list(summary.get("missing_roles") or []),
        "priority_bindings": summary.get("tags_by_role") or {},
        "use_examples": True,
        "example_query": {
            "niche": analyzed_input.detected_niche,
            "asset_mode": asset_mode,
            "shot_count": None,
            "duration_s": analyzed_input.duration_s,
        },
    }


def _consistency_plan(analyzed_input: AnalyzedInput, *, niche: str) -> dict[str, Any]:
    summary = analyzed_input.asset_summary
    character_lock = bool(summary.get("needs_character_anchor") or niche in {"drama", "anime", "ugc"})
    product_lock = bool(summary.get("needs_product_anchor") or niche in {"beauty", "food", "fashion"})
    return {
        "character_lock": character_lock,
        "product_lock": product_lock,
        "style_lock": True,
        "audio_lock": bool(summary.get("has_audio")),
        "lock_notes": [
            note
            for note in [
                "preserve face, hair, outfit, and silhouette" if character_lock else "",
                "preserve product geometry, packaging, color, and label placement" if product_lock else "",
                "maintain one visual style across all shots",
            ]
            if note
        ],
    }


def _planning_constraints(consistency_plan: dict[str, Any]) -> list[str]:
    constraints = ["no subtitles", "no logo", "no watermark"]
    constraints.extend(consistency_plan.get("lock_notes") or [])
    return list(dict.fromkeys(str(item) for item in constraints if str(item).strip()))


def _seedance_duration(value: int | None) -> int:
    if value is None:
        return 8
    return min(15, max(4, int(value)))


def _normalize_niche(value: str) -> str:
    return str(value or "unknown").strip().lower() or "unknown"


__all__ = ["CreativePlanner"]
