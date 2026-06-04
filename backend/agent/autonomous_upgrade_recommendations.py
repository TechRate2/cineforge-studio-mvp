"""Source-backed upgrade recommendations for CineJelly Autonomous Agent.

The product target is an autonomous video production crew: director, producer,
cinematographer, editor, QA supervisor, and distribution strategist. This module
keeps the next build decisions explicit so roadmap/API/UI claims stay tied to
what the source actually supports.
"""
from __future__ import annotations

from typing import Any

from agent.autonomous_readiness_report import build_autonomous_readiness_report
from agent.autonomous_competitive_research import build_autonomous_competitive_research
from agent.autonomous_workflow_contract import build_autonomous_workflow_contract
from agent.dialogue_route_policy import build_dialogue_route_policy
from agent.benchmark_promotion_policy import build_benchmark_promotion_policy
from agent.model_scorecard import build_autonomous_model_scorecard
from skills.niche_readiness import build_niche_readiness_matrix


def build_autonomous_upgrade_recommendations() -> dict[str, Any]:
    readiness = build_autonomous_readiness_report()
    workflow = build_autonomous_workflow_contract()
    capabilities = build_niche_readiness_matrix()
    scorecard = build_autonomous_model_scorecard()
    promotion_policy = build_benchmark_promotion_policy()
    competitive_research = build_autonomous_competitive_research()

    return {
        "schema_version": "cinejelly.autonomous_upgrade_recommendations.v1",
        "current_verdict": readiness["verdict"],
        "what_is_already_strong": [
            "Autonomous-only /studio intake with idea, runtime, target market, multimodal refs, memory pins, and job result modal.",
            "Planner/director/storyboard/editor skill chain builds Production Bible, shot list, preview hook, caption, and hashtags.",
            "Production treatment now locks runtime-specific story engine, camera grammar, edit rhythm, dialogue policy, reference policy, Seedance execution rules, and QA risks before rendering.",
            "Per-shot reference policy optimizer narrows Seedance 2.0 image/video/audio refs so each shot gets the strongest identity/product/style/motion/audio anchors instead of every uploaded asset.",
            "Autonomous preflight gate checks plan structure, runtime/graph coverage, producer story critic, screenplay scene lint, treatment, reference caps, model contract, Seedance shot lint, market, and niche safety before paid render.",
            "Read-only production decision preview can explain niche, runtime, graph requirement, Seedance route, dialogue lane, QA gates, and benchmark requirement before paid rendering.",
            "Backend smoke tests now validate production decisions across all 23 canonical niche benchmark cases without calling vendors.",
            "Seedance 2.0 quad-modal reference routing is the default path for reference-heavy short-form jobs.",
            "Niche and market playbooks cover 23 categories and localize hooks, proof style, camera language, and safety rules.",
            "Editor now emits a platform distribution package with title, cover-frame cue, CTA style, posting hint, hashtag policy, and platform checks.",
            "Production graph, artifact persistence, graph executor primitives, benchmark store/runner, and strong QA gate are in place.",
        ],
        "not_top_tier_yet": readiness["verdict"]["why_not_top_tier_yet"],
        "best_current_niches": readiness["niche_groups"]["high_readiness"],
        "usable_with_review_niches": readiness["niche_groups"]["medium_readiness"],
        "human_review_required_niches": readiness["niche_groups"]["review_required"],
        "long_form_rule": {
            "principle": "Never ask one video model for a 5-30 minute film in one call.",
            "pipeline": [
                "turn user idea into screenplay beats",
                "split into acts/scenes/chunks/shots",
                "lock character/product/location/style memory pins",
                "render 4-15s Seedance shots or benchmarked dialogue inserts",
                "QA every shot before assembly",
                "retry failed shots only",
                "assemble, sound-design, caption, upscale if needed",
            ],
            "source_status": [
                item for item in workflow["runtime_strategy"]
                if item["class"] in {"micro_film", "short_film", "episode"}
            ],
        },
        "dialogue_and_voice_rule": {
            "principle": "Treat visible speech as a separate production lane, not as a generic Seedance prompt detail.",
            "default": build_dialogue_route_policy(
                niche="ugc_review",
                target_market="vn",
                duration_s=10,
                has_dialogue=True,
                reference_audio_count=1,
            ).model_dump(),
            "long_presenter": build_dialogue_route_policy(
                niche="education",
                target_market="vn",
                duration_s=300,
                has_dialogue=True,
                reference_audio_count=1,
            ).model_dump(),
            "two_speaker": build_dialogue_route_policy(
                niche="drama",
                target_market="global",
                duration_s=120,
                has_dialogue=True,
                reference_audio_count=2,
                speaker_count=2,
            ).model_dump(),
        },
        "benchmark_evaluation_standard": {
            "principle": "Use diagnostic long-form evaluation, not one aggregate vibe score.",
            "dimensions": [
                "script: hook, stakes, causality, payoff, market fit",
                "visual: identity/product/location stability, camera grammar, artifact rate",
                "audio: speech presence, loudness, silence, SFX/music fit, lip-sync for dialogue",
                "cross_modal: refs are used for the intended job, captions match content",
                "stability: transitions, scene continuity, retry count, cost and latency",
            ],
            "acceptance_gate": (
                "A niche/model route becomes production-default only after stored AtlasCloud "
                "outputs pass QA and human review across the relevant market/runtime cases."
            ),
        },
        "top_tier_maturity_ladder": [
            {
                "level": "L1",
                "name": "Autonomous short-form foundation",
                "status": "implemented",
                "scope": "15-60s UGC, beauty, food, ecommerce, fashion, app/SaaS, tech, lifestyle",
                "proof_required": [
                    "one-click UI stays autonomous-only",
                    "production decision exposes niche, market, refs, route, QA, segment inspector, and input upgrade plan",
                    "backend smoke tests cover canonical niche decisions without vendor calls",
                ],
                "promotion_gate": "already source-backed; still needs paid outputs before marketing as top-tier",
            },
            {
                "level": "L2",
                "name": "Evidence-backed sell-first routes",
                "status": "next_p0",
                "scope": "high-readiness commercial/social niches",
                "proof_required": [
                    "2+ real AtlasCloud outputs per sell-first route",
                    "cost_usd, latency_s, retry_count, output_url, QA score, reviewer notes",
                    "benchmark_promotion_policy marks the route eligible",
                ],
                "promotion_gate": "route may be called production-ready only after benchmark store promotion",
            },
            {
                "level": "L3",
                "name": "Dialogue and localized presenter routes",
                "status": "next_p1",
                "scope": "Vietnamese/global UGC, education, app/SaaS explainers, drama inserts",
                "proof_required": [
                    "InfiniteTalk single-presenter VN/EN benchmark",
                    "MultiTalk two-speaker VN/EN benchmark",
                    "LipSync repair benchmark on visible speech",
                    "phoneme match, identity stability, body/hand stability, cost per accepted minute",
                ],
                "promotion_gate": "dialogue candidates remain benchmark_locked until same-market outputs pass review",
            },
            {
                "level": "L4",
                "name": "Graph-backed 5-10 minute short films",
                "status": "next_p1",
                "scope": "short film, education, documentary-lite, brand mini-film",
                "proof_required": [
                    "CINEJELLY_ENABLE_GRAPH_LONG_FORM paid runs",
                    "scene memory packs and previous-frame handoffs attached to every scene",
                    "crash/retry/resume test with accepted final assembly",
                    "act/scene continuity reviewer score above threshold",
                ],
                "promotion_gate": "long-form graph executor becomes default only after paid graph benchmarks pass",
            },
            {
                "level": "L5",
                "name": "Model-backed QA and self-correction",
                "status": "next_p1",
                "scope": "all premium routes",
                "proof_required": [
                    "identity/product embedding checks",
                    "multilingual OCR/text-artifact checks",
                    "lip-sync alignment checks",
                    "retry planner improves acceptance rate without excess cost",
                ],
                "promotion_gate": "top-tier claim remains false until QA catches visual/audio failures automatically",
            },
            {
                "level": "L6",
                "name": "30-minute episode production",
                "status": "research_gated",
                "scope": "multi-scene episodes, multi-character drama, documentary series",
                "proof_required": [
                    "asset library with character/product/location/style/voice anchors",
                    "episode graph with 60-180 render units",
                    "checkpoint review after each act",
                    "budget ceiling and resumable render leases",
                ],
                "promotion_gate": "do not sell as default until L2-L5 are proven and stored as evidence",
            },
        ],
        "benchmark_promotion_policy": promotion_policy,
        "model_integration_order": [
            {
                "priority": "P0",
                "model_or_system": "real AtlasCloud benchmark lane",
                "why": "Without paid output evidence, no model should be promoted as production-grade for every niche.",
                "acceptance_gate": "Each high-readiness niche has output URL, cost, latency, QA frames, reviewer rating, and retry count.",
            },
            {
                "priority": "P1",
                "model_or_system": "atlascloud/infinitetalk",
                "why": "Best candidate for long multilingual talking-head/dialogue inserts up to long durations.",
                "acceptance_gate": "Vietnamese and English tests pass lip-sync, identity, body stability, cost/minute.",
            },
            {
                "priority": "P1",
                "model_or_system": "atlascloud/multitalk",
                "why": "Potentially lower-cost multi-person dialogue lane for short drama/podcast/product conversations.",
                "acceptance_gate": "Two-speaker Vietnamese benchmark beats Wan 2.7 on cost without worse sync/artifacts.",
            },
            {
                "priority": "P1",
                "model_or_system": "identity/product/OCR/audio QA",
                "why": "Top apps win by rejecting bad outputs automatically, not by generating more random clips.",
                "acceptance_gate": "Face/product drift, visible fake text, silence/loudness, and lip-sync failures become hard gates.",
            },
            {
                "priority": "P2",
                "model_or_system": "atlascloud/mmaudio-v2 + video-upscaler",
                "why": "Post-render sound design and final polish make assembled clips feel more finished.",
                "acceptance_gate": "Only runs after shot QA passes and improves reviewer score without adding artifacts.",
            },
        ],
        "ui_recommendations": [
            "Keep the user-facing UI autonomous-only; do not bring back model/aspect/shot/manual controls.",
            "Keep Target Market as an optional selector with Auto default because market affects script, props, proof style, dialogue, and captions.",
            "Add an Asset Library view for recurring characters, products, locations, voices, and style anchors.",
            "Add a Production Inspector lane for screenplay, graph progress, failed QA reasons, retry count, and cost estimate.",
            "Add benchmark/admin pages separately; do not expose experimental model switches to end users.",
        ],
        "source_patterns_to_keep_matching": [
            {
                "name": "ByteDance Moyin / AI short-drama agent",
                "url": "https://pandaily.com/byte-dance-launches-ai-short-drama-agent-powered-by-seedance-2-0",
                "pattern": "one-sentence to plot, characters, shots, voice, music, and finished short drama",
            },
            {
                "name": "Jellyfish",
                "url": "https://github.com/Forget-C/Jellyfish",
                "pattern": "script to storyboard to reusable assets to trackable generation tasks",
            },
            {
                "name": "Seedance 2.0 paper",
                "url": "https://arxiv.org/abs/2604.14148",
                "pattern": "quad-modal references, world complexity, 4-15s clip decomposition",
            },
            {
                "name": "The Script is All You Need",
                "url": "https://arxiv.org/abs/2601.17737",
                "pattern": "script-centric long-horizon agent with critic/evaluation loop",
            },
            {
                "name": "Co-Director",
                "url": "https://co-director-agent.github.io/",
                "pattern": "explore multiple creative directions while preserving semantic coherence",
            },
            {
                "name": "Camera Artist",
                "url": "https://arxiv.org/abs/2604.09195",
                "pattern": "dedicated cinematography-shot agent for stronger film language",
            },
            {
                "name": "DirectorBench / CameraBench style evaluation",
                "url": "https://arxiv.org/abs/2604.11879",
                "pattern": "score camera language, temporal coherence, instruction following, and edit rhythm instead of only checking clip existence",
            },
            {
                "name": "ComfyUI workflow graph pattern",
                "url": "https://github.com/comfyanonymous/ComfyUI",
                "pattern": "durable node graph with explicit artifacts and retryable expensive steps",
            },
        ],
        "competitive_research": {
            "implementation_score": competitive_research["implementation_score"],
            "best_patterns_to_apply_next": competitive_research["best_patterns_to_apply_next"],
            "sources": competitive_research["sources"],
        },
        "active_model_scorecard": scorecard,
    }


__all__ = ["build_autonomous_upgrade_recommendations"]
