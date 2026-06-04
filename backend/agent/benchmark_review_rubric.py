"""Human/model-backed review rubric for paid benchmark outputs.

Promotion requires qa_score and reviewer notes. This module defines how those
scores should be produced so benchmark evidence is comparable across niches,
models, runtimes, and reviewers.
"""
from __future__ import annotations

from typing import Any


_BASE_DIMENSIONS = [
    {
        "key": "hook_and_retention",
        "weight": 15,
        "pass_bar": 8.0,
        "questions": [
            "Is the first 3 seconds visually clear without explanation?",
            "Would the target viewer keep watching after the hook?",
        ],
        "fail_examples": ["slow logo-first intro", "unclear first image", "generic beauty shot without promise"],
    },
    {
        "key": "reference_adherence",
        "weight": 20,
        "pass_bar": 8.0,
        "questions": [
            "Do character, product, outfit, style, and location references remain recognizable?",
            "Are reference roles respected instead of blended randomly?",
        ],
        "fail_examples": ["face morphing", "product/package drift", "style changes between adjacent shots"],
    },
    {
        "key": "camera_and_motion_quality",
        "weight": 13,
        "pass_bar": 7.5,
        "questions": [
            "Is the camera movement motivated and physically plausible?",
            "Does motion support the niche rather than distract from the subject?",
        ],
        "fail_examples": ["floating camera with no purpose", "rubber physics", "unmotivated zooms"],
    },
    {
        "key": "story_or_proof_clarity",
        "weight": 17,
        "pass_bar": 8.0,
        "questions": [
            "Does the clip deliver the promised proof, story beat, or educational takeaway?",
            "Is the payoff visible rather than only narrated?",
        ],
        "fail_examples": ["pretty montage with no result", "claim not demonstrated", "scene has no turn"],
    },
    {
        "key": "market_and_platform_fit",
        "weight": 10,
        "pass_bar": 7.5,
        "questions": [
            "Does language/caption/CTA/proof style match the target market?",
            "Does pacing fit the target platform and runtime?",
        ],
        "fail_examples": ["wrong language register", "platform pacing too slow", "unsafe or unsupported claim tone"],
    },
    {
        "key": "audio_and_lipsync",
        "weight": 10,
        "pass_bar": 7.5,
        "questions": [
            "Is audio present when expected and absent when not needed?",
            "For visible speech, is lip-sync acceptable in the target language?",
        ],
        "fail_examples": ["missing expected audio", "bad Vietnamese phoneme match", "foley out of sync"],
    },
    {
        "key": "technical_artifacts",
        "weight": 10,
        "pass_bar": 8.0,
        "questions": [
            "Are there visible generation artifacts, text artifacts, warping, or broken frames?",
            "Is the final output usable without manual structural edits?",
        ],
        "fail_examples": ["broken hands in hero action", "unreadable fake text", "hard cuts from failed renders"],
    },
    {
        "key": "cost_latency_and_retry_fit",
        "weight": 5,
        "pass_bar": 7.0,
        "questions": [
            "Is accepted-shot cost reasonable for the route?",
            "Did retries stay within the expected budget?",
        ],
        "fail_examples": ["too many retries", "cost much higher than route value", "latency unsuitable for production"],
    },
]

_LONG_FORM_EXTRA = {
    "key": "long_form_continuity",
    "weight": 15,
    "pass_bar": 8.0,
    "questions": [
        "Do scenes connect causally instead of feeling like unrelated clips?",
        "Do previous-frame handoffs preserve character/product/location continuity?",
        "Can failed chunks be repaired without restarting the whole film?",
    ],
    "fail_examples": ["scene jumps without handoff", "identity resets between chunks", "assembly feels like a playlist"],
}

_SAFETY_EXTRA = {
    "key": "claims_and_safety",
    "weight": 15,
    "pass_bar": 9.0,
    "questions": [
        "Are medical, finance, kids, or documentary claims safe and source-aware?",
        "Does the output avoid diagnosis, guaranteed returns, unsafe child framing, or invented reporting?",
    ],
    "fail_examples": ["guaranteed financial result", "medical cure claim", "unsafe kids challenge", "fake news framing"],
}


def build_benchmark_review_rubric(
    *,
    niche: str = "ugc_review",
    runtime_class: str = "short",
    target_market: str = "auto",
    has_dialogue: bool = False,
) -> dict[str, Any]:
    """Return weighted review dimensions and promotion rules."""
    niche_key = (niche or "ugc_review").strip().lower()
    runtime = (runtime_class or "short").strip().lower()
    dims = [dict(item) for item in _BASE_DIMENSIONS]
    if runtime in {"micro_film", "short_film", "episode"}:
        dims.append(dict(_LONG_FORM_EXTRA))
    if niche_key in {"finance_education", "medical_wellness", "kids_family", "documentary"}:
        dims.append(dict(_SAFETY_EXTRA))
    dims = _normalize_weights(dims)
    hard_fail_conditions = [
        "no final video URL",
        "identity/product reference drift in hero shot",
        "visible speech badly lip-synced when dialogue is required",
        "unsafe medical/finance/kids/documentary claim",
        "final output requires structural manual editing before use",
    ]
    if not has_dialogue:
        hard_fail_conditions.append("unexpected distracting dialogue or wrong-language speech")
    return {
        "schema_version": "cinejelly.benchmark_review_rubric.v1",
        "niche": niche_key,
        "runtime_class": runtime,
        "target_market": target_market or "auto",
        "has_dialogue": bool(has_dialogue),
        "promotion_thresholds": {
            "minimum_weighted_score": 8.0,
            "minimum_outputs_per_route": 2,
            "requires_reviewer_decision": "approved",
            "requires_no_hard_fail": True,
            "requires_reviewer_notes": True,
            "requires_cost_latency_retry_evidence": True,
        },
        "dimensions": dims,
        "hard_fail_conditions": hard_fail_conditions,
        "reviewer_note_template": (
            "Decision: approved/rejected/needs_review. Strongest evidence: __. "
            "Biggest defect: __. Manual edits required: yes/no. Route promotion safe: yes/no."
        ),
        "scoring_method": "weighted average of 0-10 dimension scores; qa_score should be this weighted score rounded to one decimal",
    }


def score_benchmark_review(
    *,
    rubric: dict[str, Any],
    dimension_scores: dict[str, float],
    hard_failures: list[str] | None = None,
) -> dict[str, Any]:
    """Score a filled rubric without trusting a free-form qa_score."""
    dims = list(rubric.get("dimensions") or [])
    failures = [str(item) for item in (hard_failures or []) if str(item).strip()]
    weighted_total = 0.0
    missing: list[str] = []
    below_bar: list[str] = []
    scored_dimensions: list[dict[str, Any]] = []
    for dim in dims:
        key = str(dim.get("key") or "")
        if key not in dimension_scores:
            missing.append(key)
            score = 0.0
        else:
            score = max(0.0, min(10.0, float(dimension_scores.get(key) or 0.0)))
        weight = float(dim.get("weight") or 0.0)
        pass_bar = float(dim.get("pass_bar") or 8.0)
        weighted_total += score * (weight / 100.0)
        if key in dimension_scores and score < pass_bar:
            below_bar.append(key)
        scored_dimensions.append({
            "key": key,
            "score": score,
            "weight": weight,
            "pass_bar": pass_bar,
            "status": "missing" if key in missing else ("fail" if score < pass_bar else "pass"),
        })
    weighted_score = round(weighted_total, 1)
    threshold = float((rubric.get("promotion_thresholds") or {}).get("minimum_weighted_score") or 8.0)
    promotion_ready = weighted_score >= threshold and not missing and not below_bar and not failures
    return {
        "schema_version": "cinejelly.benchmark_review_score.v1",
        "weighted_score": weighted_score,
        "promotion_ready": promotion_ready,
        "missing_dimension_scores": missing,
        "below_bar_dimensions": below_bar,
        "hard_failures": failures,
        "scored_dimensions": scored_dimensions,
        "recommended_reviewer_decision": "approved" if promotion_ready else "needs_review",
    }


def _normalize_weights(dims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = sum(float(item.get("weight") or 0.0) for item in dims) or 100.0
    normalized: list[dict[str, Any]] = []
    for item in dims:
        row = dict(item)
        row["weight"] = round(float(row.get("weight") or 0.0) * 100.0 / total, 2)
        normalized.append(row)
    return normalized


__all__ = ["build_benchmark_review_rubric", "score_benchmark_review"]
