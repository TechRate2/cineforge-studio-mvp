"""AtlasCloud model integration matrix for autonomous routing.

This keeps model research out of the one-click UI while giving admin/API code a
clear contract for active routes, benchmark candidates, and promotion gates.
"""
from __future__ import annotations

from typing import Any

from agent.benchmark_evidence_validator import REQUIRED_EVIDENCE_KEYS
from agent.model_scorecard import build_autonomous_model_scorecard


def build_atlas_model_integration_matrix() -> dict[str, Any]:
    """Return source-backed AtlasCloud model lanes and proof gates."""
    scorecard = build_autonomous_model_scorecard()
    rows = [_active_lane(row) for row in scorecard.get("active_models", [])]
    rows.extend(_candidate_lane(row) for row in scorecard.get("future_candidates", []))
    return {
        "schema_version": "cinejelly.atlas_model_integration_matrix.v1",
        "verdict": {
            "default_user_experience": "autonomous_model_hidden",
            "primary_family": "Seedance 2.0",
            "top_tier_claim_allowed": False,
            "why": (
                "Seedance 2.0 remains the core visual director. AtlasCloud has strong "
                "dialogue, audio, cheap-motion, and challenger routes, but each new "
                "route must earn promotion through real benchmark evidence."
            ),
        },
        "recommendation": {
            "keep_ui_model_picker": False,
            "default_route": "seedance_2_0_fast_ref",
            "premium_route": "seedance_2_0_ref",
            "operator_rule": (
                "Keep Auto as the user-facing default. Market/language can be a light "
                "override, but model choice remains internal and evidence-gated."
            ),
            "vn_dialogue_priority": [
                "keep Seedance 2.0 for cinematic coverage and only cut dialogue inserts where visible speech matters",
                "use wan_2_7_i2v only for current short 5-10s driven-audio fallback",
                "benchmark atlascloud/infinitetalk for single-presenter Vietnamese education/UGC",
                "benchmark atlascloud/multitalk for two-person dialogue/drama",
                "benchmark bytedance/lipsync/audio-to-video as post-render repair",
                "benchmark kwaivgi/kling-lipsync/audio-to-video as alternate short-clip repair",
            ],
            "cheap_experiment_priority": [
                "atlascloud/wan-2.2-turbo/image-to-video for low-cost keyframe motion probes",
                "atlascloud/framepack for long-motion draft probes only",
                "Veo 3.1 Lite for no-reference cinematic drafts",
                "Vidu Q3 Reference-to-Video for 1-4 image subject-consistency challenger runs",
                "Seedream v4 sequential for reusable character/location reference packs",
            ],
            "cost_policy": [
                "Optimize for accepted finished minute, not catalog price per raw generation.",
                "A cheaper model is promoted only if retry rate, artifact rate, and QA score beat the Seedance baseline for the same niche.",
                "For Vietnamese dialogue, benchmark phoneme match and identity stability before cost wins.",
            ],
        },
        "source_backed_model_rules": [
            {
                "rule": "seedance_unit_length",
                "source": "AtlasCloud Seedance 2.0 guide and model pages",
                "contract": "Seedance jobs should be planned as 4-15 second renderable units.",
                "implementation": "Long-form jobs are split into graph-managed shots/chunks with handoff frames; never submit one 5-30m prompt.",
            },
            {
                "rule": "seedance_quad_modal_refs",
                "source": "AtlasCloud Seedance 2.0 guide; Seedance docs",
                "contract": "Use text plus image/video/audio references with explicit production jobs.",
                "implementation": "Allocate image refs to identity/product/style, video refs to camera/motion/pacing, audio refs to beat/SFX/dialogue.",
            },
            {
                "rule": "fast_then_premium",
                "source": "AtlasCloud pricing/model guidance",
                "contract": "Fast tier is for iteration and default throughput; full Seedance/Reference is for high-fidelity hero shots.",
                "implementation": "Default to seedance_2_0_fast_ref, upgrade beauty/food/fashion/product hero shots to seedance_2_0_ref.",
            },
            {
                "rule": "dialogue_is_insert_or_repair_lane",
                "source": "AtlasCloud InfiniteTalk/MultiTalk/LipSync model pages",
                "contract": "Speech-heavy outputs should not replace the visual director route; they are talking-head inserts or post-render lip-sync repair.",
                "implementation": "Benchmark InfiniteTalk/MultiTalk/LipSync for Vietnamese and global dialogue before auto-routing.",
            },
            {
                "rule": "accepted_minute_cost",
                "source": "AtlasCloud model catalog economics",
                "contract": "Cheap models are cheaper only if accepted output rate and retry rate beat the Seedance baseline.",
                "implementation": "Promotion gate requires real output URL, cost, latency, QA score, retry count, and reviewer notes.",
            },
        ],
        "source_urls": [
            "https://www.atlascloud.ai/docs",
            "https://www.atlascloud.ai/blog/guides/How-to-Use-Seedance-2.0-for-Video-Generation",
            "https://www.atlascloud.ai/es/blog/ai-updates/seedance-2-0-api-complete-guide-to-multimodal-video-generation-2026",
            "https://www.atlascloud.ai/docs/en/models/video",
            "https://www.atlascloud.ai/models/list",
            "https://www.atlascloud.ai/models/bytedance/seedance-2.0-fast/reference-to-video",
            "https://www.atlascloud.ai/models/atlascloud/infinitetalk",
            "https://www.atlascloud.ai/docs/en/more-models/atlascloud/multitalk/generateVideo",
            "https://www.atlascloud.ai/docs/more-models/atlascloud/mmaudio-v2/generateVideo",
            "https://www.atlascloud.ai/docs/de/more-models/bytedance/lipsync-audio-to-video/generateVideo",
            "https://www.atlascloud.ai/docs/es/more-models/kwaivgi/kling-lipsync-audio-to-video/generateVideo",
            "https://www.atlascloud.ai/docs/more-models/atlascloud/framepack/generateVideo",
            "https://www.atlascloud.ai/models/atlascloud/wan-2.2-turbo/image-to-video",
            "https://www.atlascloud.ai/blog/guides/veo-3-1-api-guide",
            "https://www.atlascloud.ai/blog/ai-updates/Kling-3-0-Live-on-Atlas-Cloud-The-All-in-One-AI-Video-Generator-with-Smart-Storyboarding-Native-Lip-Sync",
        ],
        "rows": rows,
        "lane_policy": {
            "core_visual_director": "Seedance 2.0 owns normal cinematic/product/story coverage.",
            "dialogue_or_lipsync": "Use as inserts or repair lanes after visual plan is stable; benchmark Vietnamese before auto-route.",
            "post_render_audio": "Run after visual QA only; never hide failed visuals with audio.",
            "cheap_motion_or_dialogue_probe": "Measure accepted-minute cost, not raw generation price.",
            "visual_challenger": "Compare against Seedance on same prompt, refs, niche, and market.",
            "asset_generation": "Create reusable pins/reference packs before long-form graph execution.",
        },
        "promotion_gate": {
            "minimum_real_outputs_per_route": 2,
            "required_fields": [
                "output_url",
                "model_key",
                "niche",
                "runtime_class",
                "target_market",
                "cost_usd",
                "latency_s",
                "qa_score",
                "reviewer_decision",
            ],
            "required_evidence_keys": REQUIRED_EVIDENCE_KEYS,
            "policy": (
                "Promote only after matching benchmark rows pass for the same model, "
                "niche, runtime, and market. Until then, new Atlas models stay "
                "benchmark_locked and hidden from the one-click UI."
            ),
        },
    }


def _active_lane(row: dict[str, Any]) -> dict[str, Any]:
    model_key = str(row.get("model_key") or "")
    return {
        "model_key": model_key,
        "endpoint": row.get("endpoint"),
        "lane": _lane_for_model(model_key),
        "route_type": "active_default" if row.get("tier") == "default" else "active_specialized",
        "status": "active",
        "cost_per_second_usd": row.get("cost_per_second_usd"),
        "best_for": row.get("use_for", []),
        "avoid_for": row.get("avoid_for", []),
        "integration_rule": row.get("routing_note"),
        "benchmark_before": _benchmark_before_active(model_key),
    }


def _candidate_lane(row: dict[str, Any]) -> dict[str, Any]:
    model = str(row.get("model") or "")
    return {
        "model_key": model,
        "endpoint": None,
        "lane": _lane_for_model(model),
        "route_type": "candidate",
        "status": row.get("status") or "benchmark_required",
        "source_url": _candidate_source_url(model),
        "operational_limits": _candidate_operational_limits(model),
        "cost_per_second_usd": None,
        "best_for": [row.get("why")] if row.get("why") else [],
        "avoid_for": _candidate_avoid_for(model),
        "integration_rule": _candidate_rule(model),
        "benchmark_before": row.get("benchmark_needed", []),
    }


def _lane_for_model(model_key: str) -> str:
    key = model_key.lower()
    if any(token in key for token in ("infinitetalk", "multitalk", "lipsync", "avatar")):
        return "dialogue_or_lipsync"
    if "mmaudio" in key:
        return "post_render_audio"
    if "upscaler" in key:
        return "final_polish"
    if "wan-2.2" in key or "wan_2_7" in key or "framepack" in key:
        return "cheap_motion_or_dialogue_probe"
    if any(token in key for token in ("veo", "vidu", "kling")):
        return "visual_challenger"
    if "seedance" in key:
        return "core_visual_director"
    if "character" in key or "seedream" in key:
        return "asset_generation"
    return "research_candidate"


def _benchmark_before_active(model_key: str) -> list[str]:
    if model_key == "seedance_2_0_fast_ref":
        return ["top-tier marketing claim", "long-form default", "premium brand hero route"]
    if model_key == "seedance_2_0_ref":
        return ["long-form default", "new niche default", "high-cost automatic rerender"]
    if model_key.startswith("seedance_2_0") and "i2v" in model_key:
        return ["episode-scale continuity default", "product/face-critical final route"]
    if model_key == "wan_2_7_i2v":
        return ["long dialogue", "multi-speaker dialogue", "premium lip-sync claim"]
    return ["automatic route promotion"]


def _candidate_avoid_for(model_key: str) -> list[str]:
    key = model_key.lower()
    if "infinitetalk" in key or "multitalk" in key:
        return ["cinematic coverage", "product hero shots", "high-motion action"]
    if "lipsync" in key:
        return ["new video generation", "clips longer than the vendor limit", "fixing identity drift without visual QA"]
    if "mmaudio" in key:
        return ["fixing failed visuals", "unreviewed dialogue claims"]
    if "wan-2.2" in key or "framepack" in key:
        return ["final premium route before accepted-shot cost is proven"]
    if "veo" in key or "vidu" in key or "kling" in key:
        return ["automatic default routing before same-niche evidence"]
    if "seedream" in key:
        return ["final video render", "claiming motion continuity"]
    return ["user-facing default before benchmark evidence"]


def _candidate_rule(model_key: str) -> str:
    key = model_key.lower()
    if "infinitetalk" in key:
        return "Benchmark as Vietnamese/global presenter lane; cut inserts back into Seedance scene graph."
    if "multitalk" in key:
        return "Benchmark as two-speaker dialogue lane before drama/interview promotion."
    if "mmaudio" in key:
        return "Run only after visual QA passes; score action-sync and loudness."
    if "wan-2.2" in key:
        return "Use for low-cost motion probes or retry candidates; compare accepted-shot cost."
    if "framepack" in key:
        return "Use as long-motion draft/probe; compare drift and handoff quality against Seedance graph chunks."
    if "veo" in key:
        return "Use as no-reference cinematic draft challenger, not reference-bound default."
    if "vidu" in key:
        return "Use as subject-consistency challenger for 1-4 image cases."
    if "lipsync" in key:
        return "Use as post-render repair candidate for visible speech; score Vietnamese phonemes and artifact rate."
    if "seedream" in key:
        return "Use before rendering to create reusable character, outfit, prop, and location reference packs."
    return "Keep benchmark-locked until route evidence proves value."


def _candidate_operational_limits(model_key: str) -> list[str]:
    key = model_key.lower()
    if "infinitetalk" in key:
        return [
            "portrait or reference video plus speech audio",
            "single-presenter or dual-person dialogue lane",
            "up to 10-minute talking-head runs per Atlas model page",
        ]
    if "multitalk" in key:
        return ["requires image plus audio", "best tested as two-person dialogue insert"]
    if "bytedance/lipsync" in key:
        return ["requires existing video plus audio URL", "post-process only"]
    if "kling-lipsync" in key:
        return [
            "requires existing video plus audio URL",
            "video duration 2-10s in Atlas docs",
            "audio file max 5MB in Atlas docs",
            "720p/1080p input only in Atlas docs",
        ]
    if "mmaudio" in key:
        return ["requires existing video", "audio duration 1-30s in Atlas docs"]
    if "framepack" in key:
        return [
            "image-to-video prompt route",
            "30-1800 frame range in Atlas docs",
            "480p or 720p, 16:9 or 9:16",
        ]
    if "seedream" in key:
        return ["image/reference generation only", "use outputs as approved asset pins"]
    return ["benchmark with real outputs before user-facing promotion"]


def _candidate_source_url(model_key: str) -> str | None:
    key = model_key.lower()
    if "infinitetalk" in key:
        return "https://www.atlascloud.ai/models/atlascloud/infinitetalk"
    if "multitalk" in key:
        return "https://www.atlascloud.ai/docs/en/more-models/atlascloud/multitalk/generateVideo"
    if "mmaudio" in key:
        return "https://www.atlascloud.ai/docs/more-models/atlascloud/mmaudio-v2/generateVideo"
    if "bytedance/lipsync" in key:
        return "https://www.atlascloud.ai/docs/de/more-models/bytedance/lipsync-audio-to-video/generateVideo"
    if "kling-lipsync" in key:
        return "https://www.atlascloud.ai/docs/es/more-models/kwaivgi/kling-lipsync-audio-to-video/generateVideo"
    if "framepack" in key:
        return "https://www.atlascloud.ai/docs/more-models/atlascloud/framepack/generateVideo"
    if "veo" in key:
        return "https://www.atlascloud.ai/models/explore"
    if "vidu" in key:
        return "https://www.atlascloud.ai/models/explore"
    if "seedream" in key:
        return "https://www.atlascloud.ai/docs/en/openapi-index"
    return None


__all__ = ["build_atlas_model_integration_matrix"]
