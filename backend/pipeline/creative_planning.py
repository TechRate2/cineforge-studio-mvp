"""Creative planning for Phase 2.

The planner decides shot mode, reference strategy, consistency locks, and a
niche playbook before storyboard generation. It avoids render execution and
keeps decisions visible in CreativePlan metadata.
"""
from __future__ import annotations

import re
from typing import Any

from agent.creative_reasoning_engine import CreativeReasoningEngine
from identity.consistency_scorer import ConsistencyScorer
from identity.identity_bible import IdentityBibleBuilder
from identity.identity_contracts import ConsistencyPolicyResult, ConsistencyScore, IdentityBibleBundle
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

    def __init__(
        self,
        *,
        identity_bible_builder: IdentityBibleBuilder | None = None,
        consistency_scorer: ConsistencyScorer | None = None,
        creative_reasoning_engine: CreativeReasoningEngine | None = None,
    ) -> None:
        self.identity_bible_builder = identity_bible_builder or IdentityBibleBuilder()
        self.consistency_scorer = consistency_scorer or ConsistencyScorer()
        self.creative_reasoning_engine = creative_reasoning_engine or CreativeReasoningEngine()

    def plan(self, analyzed_input: AnalyzedInput) -> CreativePlan:
        """Return a CreativePlan with Phase 6A/7A strategy and consistency metadata."""
        niche = _normalize_niche(analyzed_input.detected_niche)
        playbook = _PLAYBOOKS.get(niche, _PLAYBOOKS["cinematic"])
        identity_bible = self.identity_bible_builder.build(analyzed_input)
        baseline_consistency_score = self.consistency_scorer.score(
            analyzed_input=analyzed_input,
            identity_bible=identity_bible,
        )
        baseline_consistency_policy = self.consistency_scorer.evaluate_policy(baseline_consistency_score)
        strategy_contract = self.creative_reasoning_engine.select_strategy(
            analyzed_input=analyzed_input,
            identity_bible=identity_bible,
            consistency_score=baseline_consistency_score,
        )
        selected_strategy = strategy_contract.selected_strategy
        consistency_score = self.consistency_scorer.score(
            analyzed_input=analyzed_input,
            identity_bible=identity_bible,
            strategy=selected_strategy,
        )
        consistency_policy = self.consistency_scorer.evaluate_policy(consistency_score)
        consistency_delta = round(
            consistency_score.overall_score - baseline_consistency_score.overall_score,
            2,
        )
        duration_s = _planning_duration(analyzed_input.duration_s)
        render_path = "long_form_segmented" if duration_s > 15 else "short_form_seedance"
        complexity = _complexity_score(analyzed_input)
        shot_mode = "multi_shot" if complexity >= 2 or duration_s > 15 else "single_shot"
        shot_count = _decide_shot_count(duration_s=duration_s, complexity=complexity, niche=niche)
        shot_count = _apply_strategy_shot_bias(
            shot_count=shot_count,
            duration_s=duration_s,
            strategy_shot_count=selected_strategy.expected_shot_count,
            shot_bias=selected_strategy.shot_bias,
        )
        if shot_count <= 1:
            shot_mode = "single_shot"

        asset_mode = _asset_mode(analyzed_input.asset_summary)
        reference_strategy = _reference_strategy(
            analyzed_input=analyzed_input,
            asset_mode=asset_mode,
            shot_mode=shot_mode,
        )
        reference_strategy.update({
            "creative_strategy_id": selected_strategy.strategy_id,
            "identity_requirements": strategy_contract.identity_requirements,
            "consistency_score": consistency_score.overall_score,
            "consistency_policy_action": consistency_policy.action,
        })
        consistency_plan = _consistency_plan(
            analyzed_input,
            niche=niche,
            identity_bible=identity_bible,
            consistency_score=consistency_score,
            consistency_policy=consistency_policy,
        )
        narrative_arc = (
            selected_strategy.narrative_structure
            or list(playbook["arc"])
        )

        return CreativePlan(
            analysis_id=analyzed_input.analysis_id,
            target_niche=niche,
            objective=str(analyzed_input.metadata.get("objective") or analyzed_input.normalized_idea),
            hook_pattern=_hook_pattern_for_plan(
                niche=niche,
                playbook=playbook,
                selected_strategy_hook=selected_strategy.hook_pattern,
            ),
            narrative_arc=list(narrative_arc) if shot_mode == "multi_shot" else [narrative_arc[0]],
            shot_count=shot_count,
            duration_s=duration_s,
            aspect_ratio=analyzed_input.aspect_ratio or "9:16",
            reference_strategy=reference_strategy,
            consistency_plan=consistency_plan,
            style_direction=selected_strategy.style_direction or playbook["style"],
            audio_direction=selected_strategy.audio_direction or playbook["audio"],
            constraints=_planning_constraints(
                consistency_plan,
                strategy_prompt_implications=selected_strategy.prompt_implications,
            ),
            metadata={
                "phase": "2",
                "phase_extensions": ["6a", "7a"],
                "render_path": render_path,
                "shot_mode": shot_mode,
                "asset_mode": asset_mode,
                "niche_playbook": niche,
                "complexity_score": complexity,
                "reference_sufficiency": analyzed_input.asset_summary.get("reference_sufficiency"),
                "creative_strategy": strategy_contract.model_dump(mode="json", exclude_none=True),
                "creative_reasoning_summary": strategy_contract.reasoning_summary,
                "creative_decision_factors": strategy_contract.decision_factors,
                "identity_bible": identity_bible.model_dump(mode="json", exclude_none=True),
                "baseline_consistency_score": baseline_consistency_score.model_dump(mode="json", exclude_none=True),
                "baseline_consistency_policy": baseline_consistency_policy.model_dump(mode="json", exclude_none=True),
                "strategy_adjusted_consistency_score": consistency_score.model_dump(mode="json", exclude_none=True),
                "consistency_score": consistency_score.model_dump(mode="json", exclude_none=True),
                "consistency_delta": consistency_delta,
                "consistency_policy": consistency_policy.model_dump(mode="json", exclude_none=True),
                "long_form_readiness": _long_form_readiness(
                    analyzed_input=analyzed_input,
                    identity_bible=identity_bible,
                    consistency_score=consistency_score,
                    selected_strategy_id=selected_strategy.strategy_id,
                    shot_count=shot_count,
                ),
                "needs_identity_consistency": bool(consistency_plan.get("character_lock")),
                "needs_product_consistency": bool(consistency_plan.get("product_lock")),
                "planning_rules": [
                    "phase2.planner.single_vs_multi_shot",
                    "phase2.planner.reference_strategy",
                    "phase2.planner.consistency_locks",
                    "phase2.planner.niche_playbook",
                    "phase6a.reasoning.rule_first_strategy_selection",
                    "phase6a.strategy.rule_based_candidate_scoring",
                    "phase7a.identity.bible_bundle",
                    "phase7a.consistency.pre_render_score",
                    "phase7a.consistency.policy_action",
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


def _consistency_plan(
    analyzed_input: AnalyzedInput,
    *,
    niche: str,
    identity_bible: IdentityBibleBundle,
    consistency_score: ConsistencyScore,
    consistency_policy: ConsistencyPolicyResult,
) -> dict[str, Any]:
    summary = analyzed_input.asset_summary
    character_lock = bool(
        summary.get("needs_character_anchor")
        or identity_bible.character.required
        or niche in {"drama", "anime", "ugc"}
    )
    product_lock = bool(
        summary.get("needs_product_anchor")
        or identity_bible.product.required
        or niche in {"beauty", "food", "fashion", "product"}
    )
    lock_notes = [
        note
        for note in [
            "preserve face, hair, outfit, and silhouette" if character_lock else "",
            "preserve product geometry, packaging, color, and label placement" if product_lock else "",
            "maintain one visual style across all shots",
            *_identity_lock_notes(identity_bible),
        ]
        if note
    ]
    return {
        "character_lock": character_lock,
        "product_lock": product_lock,
        "style_lock": True,
        "audio_lock": bool(summary.get("has_audio")),
        "identity_bible_id": identity_bible.bible_id,
        "consistency_score": consistency_score.overall_score,
        "consistency_policy_action": consistency_policy.action,
        "consistency_policy_reasons": list(consistency_policy.reason_ids),
        "consistency_risk_flags": list(consistency_score.risk_flags),
        "lock_notes": list(dict.fromkeys(lock_notes)),
    }


def _planning_constraints(
    consistency_plan: dict[str, Any],
    *,
    strategy_prompt_implications: list[str] | None = None,
) -> list[str]:
    constraints = ["no subtitles", "no logo", "no watermark"]
    constraints.extend(consistency_plan.get("lock_notes") or [])
    constraints.extend(strategy_prompt_implications or [])
    return list(dict.fromkeys(str(item) for item in constraints if str(item).strip()))


def _hook_pattern_for_plan(
    *,
    niche: str,
    playbook: dict[str, Any],
    selected_strategy_hook: str,
) -> str:
    if niche in _PLAYBOOKS:
        return str(playbook["hook_pattern"])
    return selected_strategy_hook or str(playbook["hook_pattern"])


def _apply_strategy_shot_bias(
    *,
    shot_count: int,
    duration_s: int,
    strategy_shot_count: int | None,
    shot_bias: str,
) -> int:
    max_seedance_shots = max(1, duration_s // 4)
    if shot_bias == "multi_shot" and duration_s >= 10:
        return min(max_seedance_shots, max(shot_count, strategy_shot_count or 3))
    if shot_bias == "single_shot" and duration_s <= 9:
        return 1
    return shot_count


def _identity_lock_notes(identity_bible: IdentityBibleBundle) -> list[str]:
    notes: list[str] = []
    if identity_bible.character.required and identity_bible.character.stable_traits:
        notes.append("character stable traits: " + ", ".join(identity_bible.character.stable_traits[:4]))
    if identity_bible.product.required:
        product_bits = [
            identity_bible.product.package_shape,
            *identity_bible.product.logo_label_rules[:2],
        ]
        notes.append("product lock: " + "; ".join(bit for bit in product_bits if bit))
    if identity_bible.style.visual_style:
        notes.append(f"style bible: {identity_bible.style.visual_style}")
    if identity_bible.emotion.required and identity_bible.emotion.allowed_transitions:
        notes.append("emotion continuity: " + ", ".join(identity_bible.emotion.allowed_transitions[:2]))
    return notes


def _long_form_readiness(
    *,
    analyzed_input: AnalyzedInput,
    identity_bible: IdentityBibleBundle,
    consistency_score: ConsistencyScore,
    selected_strategy_id: str,
    shot_count: int,
) -> dict[str, Any]:
    requested_duration = int(analyzed_input.duration_s or 8)
    continuity_pressure = (
        "high" if requested_duration > 15 or shot_count >= 4 else
        "medium" if requested_duration >= 12 or shot_count >= 3 else
        "low"
    )
    return {
        "phase9a_ready": 30 <= requested_duration <= 60,
        "requested_duration_s": requested_duration,
        "continuity_pressure": continuity_pressure,
        "selected_strategy_id": selected_strategy_id,
        "identity_bible_snapshot": {
            "bible_id": identity_bible.bible_id,
            "character_anchor_asset_ids": identity_bible.character.anchor_asset_ids,
            "product_anchor_asset_ids": identity_bible.product.anchor_asset_ids,
            "style_id": identity_bible.style.style_id,
            "emotion_track_id": identity_bible.emotion.track_id,
            "stable_character_traits": identity_bible.character.stable_traits[:5],
            "product_rules": identity_bible.product.logo_label_rules[:5],
        },
        "segment_handoff_requirements": [
            "carry identity_bible_snapshot into each segment",
            "store entry_state and exit_state per segment",
            "capture last_frame_anchor between adjacent segments",
            "rerun consistency policy before continuing paid segment chain",
        ],
        "pre_render_consistency_score": consistency_score.overall_score,
    }


def _seedance_duration(value: int | None) -> int:
    if value is None:
        return 8
    return min(15, max(4, int(value)))


def _planning_duration(value: int | None) -> int:
    """Keep short-form Seedance behavior while allowing Phase 9A planning."""
    if value is None or int(value) <= 15:
        return _seedance_duration(value)
    return min(60, max(16, int(value)))


def _normalize_niche(value: str) -> str:
    return str(value or "unknown").strip().lower() or "unknown"


__all__ = ["CreativePlanner"]
