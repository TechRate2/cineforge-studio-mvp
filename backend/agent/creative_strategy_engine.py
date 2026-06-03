"""Strategy candidate generation for Phase 6A."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from agent.creative_strategy_contracts import ShotBias, StrategyCandidate
from identity.identity_contracts import ConsistencyScore, IdentityBibleBundle


DEFAULT_PLAYBOOK_PATH = Path(__file__).resolve().parent / "strategy_playbooks" / "seedance_mvp.jsonl"
_REQUIRED_PLAYBOOK_KEYS = {
    "strategy_id",
    "name",
    "strategy_type",
    "niches",
    "intents",
    "hook_pattern",
    "narrative_structure",
    "shot_bias",
}
_FALLBACK_PLAYBOOKS: list[dict[str, Any]] = [
    {
        "strategy_id": "fallback_cinematic_single_unit",
        "name": "Fallback cinematic single unit",
        "strategy_type": "fallback",
        "niches": ["unknown", "cinematic", "product", "beauty", "drama", "ugc", "food", "tech"],
        "intents": ["unknown", "cinematic_sequence", "product_ad", "character_story", "ugc_clip"],
        "hook_pattern": "clear subject setup -> one readable action -> clean payoff frame",
        "narrative_structure": ["subject setup", "clear action", "payoff frame"],
        "pacing_profile": "safe readable pacing",
        "shot_bias": "adaptive",
        "preferred_asset_modes": ["t2v", "i2v", "multi_reference", "audio_driven"],
        "required_assets": [],
        "style_direction": "clean cinematic video with stable details",
        "audio_direction": "natural ambience",
        "prompt_implications": ["keep the prompt simple and avoid conflicting camera moves"],
        "base_risk": 0.28,
        "rules_applied": ["phase6a.strategy.built_in_fallback"],
        "_source": "built_in_fallback",
        "_source_hash": "built_in_fallback",
    }
]


class CreativeStrategyEngine:
    """Generate and rank creative strategy candidates from playbooks."""

    def __init__(self, *, playbook_path: Path | None = None) -> None:
        self.playbook_path = playbook_path or DEFAULT_PLAYBOOK_PATH
        self._playbooks = _load_playbooks(self.playbook_path)

    def generate_candidates(
        self,
        *,
        analyzed_input: Any,
        identity_bible: IdentityBibleBundle | None = None,
        consistency_score: ConsistencyScore | None = None,
        limit: int = 5,
    ) -> list[StrategyCandidate]:
        """Return ranked candidates for the analyzed request."""
        candidates = [
            _candidate_from_playbook(
                playbook,
                analyzed_input=analyzed_input,
                identity_bible=identity_bible,
                consistency_score=consistency_score,
            )
            for playbook in self._playbooks
        ]
        return sorted(
            candidates,
            key=lambda candidate: (
                -candidate.selection_score,
                candidate.risk_score,
                candidate.strategy_id,
            ),
        )[: max(1, int(limit))]

    def generate_fallback_candidates(self, *, analyzed_input: Any) -> list[StrategyCandidate]:
        """Return built-in candidates when external playbooks cannot be loaded."""
        return sorted(
            [
                _candidate_from_playbook(
                    playbook,
                    analyzed_input=analyzed_input,
                    identity_bible=None,
                    consistency_score=None,
                )
                for playbook in _FALLBACK_PLAYBOOKS
            ],
            key=lambda candidate: (-candidate.selection_score, candidate.risk_score, candidate.strategy_id),
        )


def _candidate_from_playbook(
    playbook: dict[str, Any],
    *,
    analyzed_input: Any,
    identity_bible: IdentityBibleBundle | None,
    consistency_score: ConsistencyScore | None,
) -> StrategyCandidate:
    fit_score, fit_reasons = _fit_score(playbook, analyzed_input)
    risk_score, rejection_reasons = _risk_score(
        playbook,
        analyzed_input=analyzed_input,
        identity_bible=identity_bible,
        consistency_score=consistency_score,
    )
    selection_score = max(0.0, min(1.0, fit_score - (risk_score * 0.35)))
    confidence_score = max(0.0, min(1.0, selection_score + 0.08 if fit_reasons else selection_score))
    return StrategyCandidate(
        strategy_id=str(playbook["strategy_id"]),
        name=str(playbook["name"]),
        strategy_type=str(playbook["strategy_type"]),
        fit_score=round(fit_score, 3),
        risk_score=round(risk_score, 3),
        selection_score=round(selection_score, 3),
        confidence_score=round(confidence_score, 3),
        shot_bias=_shot_bias(playbook.get("shot_bias")),
        expected_shot_count=_expected_shot_count(playbook, analyzed_input),
        hook_pattern=str(playbook.get("hook_pattern") or ""),
        narrative_structure=[str(item) for item in playbook.get("narrative_structure") or []],
        pacing_profile=str(playbook.get("pacing_profile") or ""),
        style_direction=str(playbook.get("style_direction") or ""),
        audio_direction=str(playbook.get("audio_direction") or ""),
        required_assets=[str(item) for item in playbook.get("required_assets") or []],
        prompt_implications=[str(item) for item in playbook.get("prompt_implications") or []],
        rejection_reasons=rejection_reasons,
        rules_applied=[str(item) for item in playbook.get("rules_applied") or []] + [
            "phase6a.strategy.rule_based_candidate_scoring"
        ],
        metadata={
            "fit_reasons": fit_reasons,
            "asset_mode": _asset_mode(analyzed_input),
            "playbook_source": str(playbook.get("_source") or DEFAULT_PLAYBOOK_PATH.name),
            "playbook_hash": str(playbook.get("_source_hash") or ""),
        },
    )


def _fit_score(playbook: dict[str, Any], analyzed_input: Any) -> tuple[float, list[str]]:
    score = 0.18
    reasons: list[str] = []
    niche = str(analyzed_input.detected_niche or "unknown").lower()
    intent = str(analyzed_input.intent or "unknown").lower()
    niches = {str(item).lower() for item in playbook.get("niches") or []}
    intents = {str(item).lower() for item in playbook.get("intents") or []}
    preferred_asset_modes = {str(item).lower() for item in playbook.get("preferred_asset_modes") or []}
    if niche in niches:
        score += 0.36
        reasons.append(f"exact_niche:{niche}")
    elif "unknown" in niches and niche == "unknown":
        score += 0.24
        reasons.append("unknown_niche_supported")
    elif "unknown" in niches:
        score += 0.08
        reasons.append("broad_strategy")
    if intent in intents:
        score += 0.2
        reasons.append(f"intent:{intent}")
    asset_mode = _asset_mode(analyzed_input)
    if asset_mode in preferred_asset_modes:
        score += 0.1
        reasons.append(f"asset_mode:{asset_mode}")
    duration_s = int(analyzed_input.duration_s or 8)
    if duration_s >= 10 and playbook.get("shot_bias") == "multi_shot":
        score += 0.08
        reasons.append("multi_shot_duration_fit")
    if duration_s <= 9 and playbook.get("shot_bias") in {"single_shot", "adaptive"}:
        score += 0.06
        reasons.append("short_duration_fit")
    idea = analyzed_input.normalized_idea
    if any(token in idea for token in ("hook", "reveal", "payoff")) and "reveal" in str(playbook.get("hook_pattern", "")):
        score += 0.05
        reasons.append("hook_reveal_language")
    if any(token in idea for token in ("learn", "education", "explain", "science")) and playbook.get("strategy_type") == "explain_then_show":
        score += 0.22
        reasons.append("education_language")
    return min(1.0, score), reasons


def _risk_score(
    playbook: dict[str, Any],
    *,
    analyzed_input: Any,
    identity_bible: IdentityBibleBundle | None,
    consistency_score: ConsistencyScore | None,
) -> tuple[float, list[str]]:
    risk = float(playbook.get("base_risk") or 0.25)
    reasons: list[str] = []
    required_assets = {str(item) for item in playbook.get("required_assets") or []}
    summary = analyzed_input.asset_summary
    if "character_anchor" in required_assets and not summary.get("has_character_anchor"):
        risk += 0.18
        reasons.append("missing_character_anchor_for_strategy")
    if "product_hero" in required_assets and not summary.get("has_product_anchor"):
        risk += 0.16
        reasons.append("missing_product_anchor_for_strategy")
    if consistency_score:
        consistency_risk = max(0.0, (100.0 - consistency_score.overall_score) / 100.0)
        risk += consistency_risk * 0.22
        if consistency_score.risk_flags:
            reasons.extend(consistency_score.risk_flags[:4])
    if identity_bible and identity_bible.character.required and playbook.get("strategy_type") in {"emotion_arc", "ugc_proof"}:
        if identity_bible.character.risk_level == "high":
            risk += 0.12
            reasons.append("high_character_identity_risk")
    duration_s = int(analyzed_input.duration_s or 8)
    if duration_s <= 5 and len(playbook.get("narrative_structure") or []) > 2:
        risk += 0.12
        reasons.append("too_many_beats_for_short_duration")
    return min(1.0, risk), list(dict.fromkeys(reasons))


def _expected_shot_count(playbook: dict[str, Any], analyzed_input: Any) -> int:
    duration_s = int(analyzed_input.duration_s or 8)
    max_seedance_shots = max(1, duration_s // 4)
    shot_bias = _shot_bias(playbook.get("shot_bias"))
    if shot_bias == "single_shot":
        return 1
    if shot_bias == "multi_shot":
        return min(5, max(3, min(max_seedance_shots, 3 if duration_s < 14 else 4)))
    return 1 if duration_s <= 9 else min(3, max_seedance_shots)


def _asset_mode(analyzed_input: Any) -> str:
    counts = analyzed_input.asset_summary.get("kind_counts") or {}
    active_kinds = {kind for kind in ("image", "video", "audio") if int(counts.get(kind) or 0) > 0}
    if not active_kinds:
        return "t2v"
    if active_kinds == {"image"}:
        return "i2v"
    if active_kinds == {"video"}:
        return "v2v"
    if active_kinds == {"audio"}:
        return "audio_driven"
    if "audio" in active_kinds:
        return "audio_driven"
    return "multi_reference"


def _shot_bias(value: Any) -> ShotBias:
    text = str(value or "adaptive")
    if text in {"single_shot", "multi_shot", "adaptive"}:
        return text  # type: ignore[return-value]
    return "adaptive"


def _load_playbooks(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return list(_FALLBACK_PLAYBOOKS)
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError:
        return list(_FALLBACK_PLAYBOOKS)
    source_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    for line in raw_text.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not _is_valid_playbook(row):
            continue
        row["_source"] = str(path.name)
        row["_source_hash"] = source_hash
        rows.append(row)
    return rows or list(_FALLBACK_PLAYBOOKS)


def _is_valid_playbook(value: Any) -> bool:
    return isinstance(value, dict) and _REQUIRED_PLAYBOOK_KEYS.issubset(value)


__all__ = ["CreativeStrategyEngine", "DEFAULT_PLAYBOOK_PATH"]
