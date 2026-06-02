"""Autonomous model scorecard for CineJelly.

This is not a live benchmark runner. It is a deterministic routing contract
that turns the current AtlasCloud model specs into product-facing guidance:
which model is default, which one is premium, which one is dialogue-only, and
which future Atlas models need benchmark evidence before being added.
"""
from __future__ import annotations

from typing import Any

from agent.dialogue_route_policy import build_dialogue_route_policy
from agent.model_specs import VIDEO_MODEL_SPECS


def build_autonomous_model_scorecard() -> dict[str, Any]:
    """Return current model routing policy and benchmark gaps."""
    return {
        "schema_version": "cinejelly.model_scorecard.v1",
        "active_models": [
            _active_row(
                "seedance_2_0_fast_ref",
                tier="default",
                use_for=[
                    "most short-form autonomous jobs",
                    "UGC/product/lifestyle with references",
                    "draft-first gates for costly renders",
                ],
                avoid_for=[
                    "critical brand/product hero renders where cost is secondary",
                    "driven lip-sync from exact Vietnamese TTS audio",
                ],
                routing_note=(
                    "Use as default because it keeps Seedance 2.0 quad-modal refs "
                    "while reducing cost versus the premium tier."
                ),
            ),
            _active_row(
                "seedance_2_0_ref",
                tier="premium",
                use_for=[
                    "beauty, fashion, food, product hero, cinematic drama shots",
                    "jobs with many image/video/audio references",
                    "final high-fidelity rerenders after draft approval",
                ],
                avoid_for=[
                    "cheap exploratory drafts",
                    "long full-film rendering without graph/chunk budget control",
                    "driven lip-sync from exact TTS audio",
                ],
                routing_note=(
                    "Use when visual fidelity and reference adherence matter more "
                    "than cost."
                ),
            ),
            _active_row(
                "seedance_2_0_fast_i2v",
                tier="chain",
                use_for=[
                    "previous-frame continuation in long-form shot chains",
                    "single-image motion shots",
                    "retrying one failed shot cheaply",
                ],
                avoid_for=[
                    "multi-reference scenes needing @image_N/@video_N roles",
                    "multi-shot single-call prompts",
                ],
                routing_note="Use for chained continuity when a previous last-frame is the strongest anchor.",
            ),
            _active_row(
                "seedance_2_0_i2v",
                tier="premium_chain",
                use_for=[
                    "premium previous-frame continuation",
                    "high-fidelity motion from a locked keyframe",
                    "important character/product continuity shots",
                ],
                avoid_for=[
                    "low-cost draft chains",
                    "scenes requiring multiple independent image references",
                ],
                routing_note="Use when keyframe/last-frame fidelity beats cost.",
            ),
            _active_row(
                "seedance_2_0_fast_t2v",
                tier="draft_text",
                use_for=[
                    "no-reference drafts",
                    "abstract b-roll",
                    "fast storyboard motion probes",
                ],
                avoid_for=[
                    "character or product consistency",
                    "brand-specific scenes",
                ],
                routing_note="Use only when no usable references exist.",
            ),
            _active_row(
                "wan_2_7_i2v",
                tier="dialogue_fallback",
                use_for=[
                    "Vietnamese talking-head/lip-sync close-ups",
                    "driven-audio dialogue shots",
                    "short presenter/interview inserts",
                ],
                avoid_for=[
                    "long cinematic coverage",
                    "multi-reference product/style scenes",
                    "non-dialogue shots where Seedance 2.0 is stronger",
                ],
                routing_note=(
                    "Keep as narrow fallback: it has driven audio, but does not "
                    "replace Seedance 2.0 for cinematic coverage."
                ),
            ),
        ],
        "future_candidates": [
            {
                "model": "atlascloud/infinitetalk",
                "role": "long_dialogue_avatar",
                "why": (
                    "portrait/audio driven talking-head or two-speaker inserts "
                    "for education, product spokesperson, and Vietnamese/localized "
                    "dialogue where Seedance's 4-15s clip limit is inefficient"
                ),
                "status": "priority_benchmark_required",
                "benchmark_needed": [
                    "Vietnamese phoneme match",
                    "10-minute identity stability",
                    "body/hand stability",
                    "dual-speaker quality",
                    "cost per finished minute",
                ],
            },
            {
                "model": "atlascloud/multitalk",
                "role": "low_cost_multi_person_dialogue",
                "why": (
                    "candidate for cheaper audio-driven multi-person dialogue scenes "
                    "where the output is a talking/interacting insert rather than a "
                    "cinematic Seedance shot"
                ),
                "status": "priority_benchmark_required",
                "benchmark_needed": [
                    "Vietnamese phoneme match",
                    "two-speaker turn taking",
                    "body/hand stability",
                    "120-second segment stability",
                    "cost per finished minute versus Wan 2.7 and InfiniteTalk",
                ],
            },
            {
                "model": "atlascloud/mmaudio-v2",
                "role": "post_render_audio",
                "why": "ambience, foley, and SFX pass after video render",
                "status": "benchmark_required",
                "benchmark_needed": ["audio sync", "loudness", "SFX realism", "cost per finished minute"],
            },
            {
                "model": "atlascloud/video-upscaler",
                "role": "final_polish",
                "why": "optional final pass for premium exports after assembly and QA",
                "status": "benchmark_required",
                "benchmark_needed": ["artifact increase", "latency", "cost per finished minute", "perceived quality lift"],
            },
            {
                "model": "atlascloud/wan-2.2-turbo/image-to-video",
                "role": "cheap_keyframe_motion_or_draft_chain",
                "why": (
                    "AtlasCloud lists Wan 2.2 Turbo I2V as a fast fixed-5s image-to-video "
                    "route with low per-second pricing; test it for cheap motion probes, "
                    "never as a replacement for Seedance quad-modal reference shots"
                ),
                "status": "benchmark_required",
                "benchmark_needed": [
                    "previous-frame continuity",
                    "visual quality drop versus Seedance Fast",
                    "cost savings per accepted shot",
                    "retry rate",
                ],
            },
            {
                "model": "atlascloud_catalog:veo_3_1_lite",
                "role": "text_or_image_to_video_challenger",
                "why": (
                    "AtlasCloud lists Veo 3.1 Lite at a low $/sec tier with synchronized "
                    "audio; benchmark only for no-reference drafts or start/end-frame clips"
                ),
                "status": "benchmark_required",
                "benchmark_needed": [
                    "prompt adherence",
                    "cost per usable draft",
                    "style controllability",
                    "Seedance handoff compatibility",
                ],
            },
            {
                "model": "atlascloud_catalog:vidu_q3_reference_to_video",
                "role": "subject_consistency_challenger",
                "why": (
                    "AtlasCloud lists Vidu Q3 reference-to-video as a low-cost "
                    "1-4 reference-image consistency candidate; compare it against "
                    "Seedance for character/product adherence before any route promotion"
                ),
                "status": "benchmark_required",
                "benchmark_needed": [
                    "identity/product adherence",
                    "motion realism",
                    "cost versus Seedance Fast",
                    "retry rate",
                ],
            },
            {
                "model": "bytedance/lipsync/audio-to-video",
                "role": "post_render_lipsync",
                "why": "repair or enhance dialogue shots using existing video + audio",
                "status": "benchmark_required",
                "benchmark_needed": ["Vietnamese phoneme match", "face stability", "latency", "artifact rate"],
            },
            {
                "model": "kwaivgi/kling-lipsync/audio-to-video",
                "role": "alternate_post_render_lipsync",
                "why": (
                    "AtlasCloud exposes Kling lip-sync audio-to-video as another "
                    "repair lane for short 2-10s speech clips; benchmark it "
                    "against ByteDance LipSync before using it for Vietnamese "
                    "dialogue repair"
                ),
                "status": "benchmark_required",
                "benchmark_needed": [
                    "Vietnamese phoneme match",
                    "2-10s clip artifact rate",
                    "720p/1080p input compatibility",
                    "cost and latency versus ByteDance LipSync",
                ],
            },
            {
                "model": "bytedance/avatar-omni-human",
                "role": "portrait_dialogue",
                "why": "cheap/controlled portrait dialogue inserts",
                "status": "benchmark_required",
                "benchmark_needed": ["VN voice compatibility", "identity preservation", "uncanny rate"],
            },
            {
                "model": "atlascloud/instant-character",
                "role": "character_anchor",
                "why": "generate reusable character sheets before long-form runs",
                "status": "benchmark_required",
                "benchmark_needed": ["multi-angle consistency", "style transfer", "reuse across scenes"],
            },
            {
                "model": "atlascloud/framepack",
                "role": "long_motion_draft_or_probe",
                "why": (
                    "AtlasCloud FramePack supports image-driven video with many "
                    "frames; test it only as a cheap long-motion probe or draft "
                    "lane, not as a replacement for Seedance reference-bound shots"
                ),
                "status": "benchmark_required",
                "benchmark_needed": [
                    "long-shot visual drift",
                    "previous-frame handoff compatibility",
                    "cost per accepted minute",
                    "quality drop versus Seedance graph chunks",
                ],
            },
            {
                "model": "bytedance/seedream-v4/sequential",
                "role": "reference_pack_generation",
                "why": (
                    "Use sequential image generation to create character, outfit, "
                    "prop, and location reference packs before long-form graph runs"
                ),
                "status": "benchmark_required",
                "benchmark_needed": [
                    "multi-image identity consistency",
                    "character sheet usefulness",
                    "prompt-to-reference reuse rate",
                ],
            },
        ],
        "routing_rules": [
            "Do not expose model choices in the one-click UI; route internally.",
            "Default to Seedance 2.0 Fast Reference when references exist.",
            "Upgrade to Seedance 2.0 Reference for premium/product/beauty/fashion/food hero shots.",
            "Use Seedance i2v variants for previous-frame/keyframe chained shots.",
            "Use Wan 2.7 only for driven-audio dialogue/lip-sync inserts.",
            "Benchmark InfiniteTalk before routing long talking-head or education scenes to it.",
            "Benchmark MultiTalk as the lower-cost dialogue candidate before using it for Vietnamese two-person scenes.",
            "Use MMAudio only as a post-render sound-design pass after visual QA succeeds.",
            "Use video-upscaler only after final assembly, never as a substitute for fixing bad shots.",
            "Benchmark ByteDance and Kling lip-sync repair lanes side by side before choosing a Vietnamese default.",
            "Use FramePack only for cheap long-motion probes until it proves continuity and accepted-minute cost.",
            "Use Seedream sequential image routes to build reusable reference packs for long-form, not as a video route.",
            "For 5-30m jobs, route per shot/chunk; never send one long prompt as one render.",
        ],
        "dialogue_route_policy": {
            "no_dialogue": build_dialogue_route_policy(
                niche="ugc_review",
                target_market="auto",
                duration_s=30,
                has_dialogue=False,
                reference_audio_count=0,
            ).model_dump(),
            "short_vn_lipsync": build_dialogue_route_policy(
                niche="ugc_review",
                target_market="vn",
                duration_s=10,
                has_dialogue=True,
                reference_audio_count=1,
            ).model_dump(),
            "long_single_presenter": build_dialogue_route_policy(
                niche="education",
                target_market="vn",
                duration_s=300,
                has_dialogue=True,
                reference_audio_count=1,
            ).model_dump(),
            "two_person_dialogue": build_dialogue_route_policy(
                niche="drama",
                target_market="global",
                duration_s=120,
                has_dialogue=True,
                reference_audio_count=2,
                speaker_count=2,
            ).model_dump(),
        },
    }


def _active_row(
    model_key: str,
    *,
    tier: str,
    use_for: list[str],
    avoid_for: list[str],
    routing_note: str,
) -> dict[str, Any]:
    spec = VIDEO_MODEL_SPECS.get(model_key, {})
    return {
        "model_key": model_key,
        "endpoint": spec.get("endpoint"),
        "tier": tier,
        "cost_per_second_usd": spec.get("cost_per_second_usd"),
        "duration": spec.get("duration"),
        "resolution_default": (spec.get("resolution") or {}).get("default"),
        "max_references": spec.get("max_references"),
        "audio_capability": spec.get("audio_capability"),
        "supports_multi_shot": bool(spec.get("supports_multi_shot")),
        "supports_quad_modal": bool(spec.get("supports_quad_modal")),
        "use_for": use_for,
        "avoid_for": avoid_for,
        "routing_note": routing_note,
    }


__all__ = ["build_autonomous_model_scorecard"]
