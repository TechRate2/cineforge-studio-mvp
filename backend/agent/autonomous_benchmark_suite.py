"""Autonomous benchmark contract for CineJelly.

This module is intentionally vendor-free. It defines what must be measured
before CineJelly can claim production-grade autonomous quality for every niche,
runtime, market, and model route. Actual paid vendor renders can consume this
contract later and attach real outputs, costs, latency, and QA scores.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from agent.dialogue_route_policy import build_dialogue_route_policy
from agent.benchmark_evidence_validator import REQUIRED_EVIDENCE_KEYS
from agent.model_scorecard import build_autonomous_model_scorecard
from skills.niche_benchmarks import list_benchmark_cases


def build_autonomous_benchmark_contract() -> dict[str, Any]:
    """Return benchmark cases, quality gates, and model-candidate test plan."""
    cases = [_case_contract(case) for case in list_benchmark_cases()]
    runtime_counts = Counter(case["runtime_class"] for case in cases)
    markets = sorted({str(case["target_market"]) for case in cases})
    scorecard = build_autonomous_model_scorecard()
    future_candidates = scorecard.get("future_candidates", [])

    return {
        "schema_version": "cinejelly.autonomous_benchmark.v1",
        "summary": {
            "case_count": len(cases),
            "market_coverage": markets,
            "runtime_coverage": dict(sorted(runtime_counts.items())),
            "vendor_render_required_for_production_claim": True,
            "purpose": (
                "Use this suite before changing prompts, adding model routes, "
                "or claiming top-tier quality for a niche/runtime."
            ),
        },
        "global_pass_policy": {
            "minimum_cases_per_niche_for_top_tier_claim": 3,
            "current_cases_per_niche": 1,
            "minimum_vendor_outputs_per_case": 2,
            "required_evidence": [
                "final video URL",
                "per-shot prompts and reference manifest",
                "Seedance prompt formula",
                "model route per shot",
                "production graph snapshot, scene memory, and continuity handoff report",
                "cost and latency",
                "accepted cost per finished minute",
                "sampled QA frames",
                "visual reference similarity, semantic QA, and text artifact reports",
                "audio loudness/silence/sync report",
                "benchmark review score",
                "identity/product/style adherence notes",
                "human rating or reviewer decision",
            ],
            "required_evidence_keys": REQUIRED_EVIDENCE_KEYS,
            "fail_if": [
                "identity or product reference drifts in hero shots",
                "dialogue/lip-sync is visibly wrong",
                "medical/finance/kids/documentary claims are unsafe or unsupported",
                "long-form jobs cannot resume failed shot/chunk nodes",
                "final video requires manual platform-specific editing to be usable",
            ],
        },
        "quality_gates": _quality_gates(),
        "cases": cases,
        "model_candidate_tests": [
            _candidate_contract(candidate) for candidate in future_candidates
        ],
    }


def _case_contract(case: dict[str, Any]) -> dict[str, Any]:
    duration = int(case.get("duration_hint_s") or 30)
    niche = str(case.get("niche") or "ugc_review")
    target_market = str(case.get("target_market") or "auto")
    ref_strategy = list(case.get("reference_strategy") or [])
    runtime_class = _runtime_class(duration)
    route = _recommended_route(
        niche=niche,
        target_market=target_market,
        duration_s=duration,
        reference_strategy=ref_strategy,
    )

    gates = [
        "idea_to_niche_match",
        "first_3s_hook_strength",
        "market_localization",
        "reference_role_assignment",
        "seedance_prompt_binding",
        "per_shot_duration_fit",
        "visual_reference_adherence",
        "caption_hashtag_fit",
    ]
    if duration > 60:
        gates.extend([
            "scene_arc_continuity",
            "production_graph_resume_plan",
            "cost_and_retry_budget",
        ])
    if any("audio" in r.lower() or "voice" in r.lower() for r in ref_strategy):
        gates.extend(["audio_sync_or_foley_fit", "voice_language_fit"])
    if niche in {"documentary", "finance_education", "medical_wellness", "kids_family"}:
        gates.append("safety_claim_review")

    return {
        "case_id": f"bench_{niche}",
        "niche": niche,
        "target_market": target_market,
        "duration_hint_s": duration,
        "runtime_class": runtime_class,
        "idea": case.get("idea"),
        "reference_strategy": ref_strategy,
        "reference_requirements": _reference_requirements(ref_strategy),
        "success_criteria": list(case.get("success_criteria") or []),
        "recommended_route": route,
        "required_gates": gates,
        "production_ready_when": [
            "planner/director output passes all required gates",
            "at least two vendor renders pass QA for this case",
            "human reviewer accepts final video without structural edits",
        ],
    }


def _candidate_contract(candidate: dict[str, Any]) -> dict[str, Any]:
    model = str(candidate.get("model") or "unknown")
    role = str(candidate.get("role") or "candidate")
    benchmark_needed = list(candidate.get("benchmark_needed") or [])
    if model == "atlascloud/infinitetalk":
        sample_niches = ["education", "ugc_review", "drama", "documentary"]
        sample_markets = ["vn", "us", "global"]
        required_inputs = ["portrait_or_reference_video", "wav_or_mp3_audio", "localized_script"]
        route_policy = "dialogue-heavy long scenes only; keep Seedance for cinematic b-roll and product hero shots."
    elif model == "atlascloud/mmaudio-v2":
        sample_niches = ["food", "asmr", "travel", "restaurant_hospitality"]
        sample_markets = ["vn", "global"]
        required_inputs = ["rendered_video", "audio_prompt"]
        route_policy = "post-render ambience, foley, and SFX pass only."
    elif model == "atlascloud/wan-2.2-turbo/image-to-video":
        sample_niches = ["travel", "automotive", "food", "lifestyle"]
        sample_markets = ["vn", "global"]
        required_inputs = ["strong_first_frame_image", "concise_motion_prompt"]
        route_policy = "cheap fixed-5s motion probe or retry candidate; promote only if accepted-shot cost beats Seedance Fast."
    elif model == "atlascloud_catalog:veo_3_1_lite":
        sample_niches = ["travel", "lifestyle", "documentary", "app_saas"]
        sample_markets = ["global", "us"]
        required_inputs = ["text_prompt_or_start_end_frames", "audio_requirement_notes"]
        route_policy = "no-reference draft challenger only; keep Seedance for reference-bound final coverage."
    elif model == "atlascloud_catalog:vidu_q3_reference_to_video":
        sample_niches = ["beauty", "fashion", "ecommerce_catalog", "drama"]
        sample_markets = ["vn", "global"]
        required_inputs = ["one_to_four_subject_reference_images", "camera_motion_prompt"]
        route_policy = "subject-consistency challenger; promote only for specific niche/runtime routes after real QA."
    elif model == "bytedance/lipsync/audio-to-video":
        sample_niches = ["ugc_review", "education", "drama"]
        sample_markets = ["vn", "us"]
        required_inputs = ["rendered_face_video", "wav_or_mp3_audio"]
        route_policy = "repair or enhance dialogue clips after video render."
    elif model == "bytedance/avatar-omni-human":
        sample_niches = ["education", "app_saas", "ugc_review"]
        sample_markets = ["vn", "global"]
        required_inputs = ["clear_front_facing_portrait", "audio"]
        route_policy = "portrait presenter inserts only after uncanny-rate benchmark."
    elif model == "atlascloud/instant-character":
        sample_niches = ["drama", "anime_comic", "fashion", "lifestyle"]
        sample_markets = ["global"]
        required_inputs = ["single_character_reference_image"]
        route_policy = "pre-production character anchor generation, not final video render."
    elif model == "atlascloud/framepack":
        sample_niches = ["travel", "automotive", "lifestyle", "drama"]
        sample_markets = ["vn", "global"]
        required_inputs = ["locked_keyframe_or_scene_image", "motion_prompt", "drift_review_notes"]
        route_policy = "cheap long-motion probe only; promote only if drift and accepted-minute cost beat Seedance graph chunks."
    elif model == "bytedance/seedream-v4/sequential":
        sample_niches = ["drama", "fashion", "ecommerce_catalog", "restaurant_hospitality"]
        sample_markets = ["vn", "global"]
        required_inputs = ["character_or_product_brief", "style_reference", "multi_view_sheet_prompt"]
        route_policy = "pre-render reference pack generation for character/product/location pins, not final video render."
    else:
        sample_niches = ["ugc_review"]
        sample_markets = ["global"]
        required_inputs = ["case_specific_inputs"]
        route_policy = "benchmark before routing automatically."

    return {
        "model": model,
        "role": role,
        "status": candidate.get("status"),
        "why": candidate.get("why"),
        "sample_niches": sample_niches,
        "sample_markets": sample_markets,
        "required_inputs": required_inputs,
        "benchmark_needed": benchmark_needed,
        "route_policy_after_pass": route_policy,
        "must_not_replace": [
            "Seedance 2.0 Reference-to-Video for quad-modal cinematic/product shots",
            "production graph executor for long-form orchestration",
        ],
    }


def _quality_gates() -> list[dict[str, Any]]:
    return [
        {
            "gate": "planner",
            "checks": [
                "niche classification matches benchmark intent",
                "hook is visual and appears in first 3 seconds",
                "duration/runtime class matches requested output",
                "market playbook affects language, proof style, and CTA",
            ],
        },
        {
            "gate": "reference_manifest",
            "checks": [
                "every uploaded image/video/audio has an explicit job",
                "prompt uses @image_N, @video_N, @audio_N where supported",
                "video refs are used for motion/camera/pacing, not identity",
                "audio refs are used for beat, ambience, SFX, or dialogue tone",
            ],
        },
        {
            "gate": "story",
            "checks": [
                "shorts have one clear payoff",
                "micro/short films have setup, escalation, reveal, and close",
                "long-form scripts are split into scenes, chunks, and shots",
            ],
        },
        {
            "gate": "render",
            "checks": [
                "Seedance shots stay inside 4-15s clip limits",
                "long videos route per shot/chunk, not one giant prompt",
                "premium model is reserved for hero/fidelity-critical shots",
                "dialogue-specific models are used only after benchmark pass",
            ],
        },
        {
            "gate": "qa",
            "checks": [
                "ffprobe duration/codec validation",
                "sampled frame identity/product/style checks",
                "audio loudness, silence, and sync checks",
                "caption and visible-text artifact checks",
                "safe retry plan for failed shot/chunk nodes",
            ],
        },
    ]


def _reference_requirements(strategy: list[str]) -> dict[str, int]:
    counts = {"images": 0, "videos": 0, "audios": 0}
    for item in strategy:
        s = item.lower()
        if "video" in s:
            counts["videos"] += 1
        elif "audio" in s or "voice" in s or "music" in s or "beat" in s:
            counts["audios"] += 1
        else:
            counts["images"] += 1
    return counts


def _recommended_route(
    *,
    niche: str,
    target_market: str,
    duration_s: int,
    reference_strategy: list[str],
) -> dict[str, Any]:
    needs_audio = any(
        token in item.lower()
        for item in reference_strategy
        for token in ("audio", "voice", "music", "beat")
    )
    speaker_count = 2 if niche in {"drama", "documentary"} and needs_audio and duration_s > 60 else 1
    dialogue_policy = build_dialogue_route_policy(
        niche=niche,
        target_market=target_market,
        duration_s=duration_s,
        has_dialogue=needs_audio and niche in {"education", "ugc_review", "drama", "documentary"},
        reference_audio_count=1 if needs_audio else 0,
        speaker_count=speaker_count,
    ).model_dump()
    route = "seedance_2_0_fast_ref"
    notes = ["default quad-modal/cost-balanced Seedance route"]
    if niche in {"beauty", "fashion", "food", "ecommerce_catalog"}:
        route = "seedance_2_0_ref"
        notes.append("premium hero visuals and reference adherence matter")
    if duration_s > 15:
        notes.append("split into 4-15s render calls; do not send as one Seedance request")
    if duration_s > 180:
        notes.append("requires production graph executor and per-shot/chunk render")
    if needs_audio and niche in {"education", "ugc_review", "drama", "documentary"}:
        notes.append("benchmark dialogue lane: InfiniteTalk/LipSync/Wan before auto-routing")
    return {
        "primary_model_key": route,
        "dialogue_route_policy": dialogue_policy,
        "requires_long_form_executor": duration_s > 180,
        "requires_dialogue_candidate_benchmark": needs_audio and niche in {
            "education",
            "ugc_review",
            "drama",
            "documentary",
        },
        "notes": notes,
    }


def _runtime_class(duration_s: int) -> str:
    if duration_s <= 30:
        return "short"
    if duration_s <= 60:
        return "sequence"
    if duration_s <= 180:
        return "micro_film"
    if duration_s <= 600:
        return "short_film"
    return "episode"


__all__ = ["build_autonomous_benchmark_contract"]
