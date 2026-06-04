"""Structured workflow contract for CineJelly Autonomous Director.

The user-facing product is one-click, but the production system must be
inspectable. This module describes the actual autonomous pipeline as a stable
contract: stages, agent roles, artifacts, gates, runtime strategy, and known
production gaps. It is used by API/admin surfaces and by future regression
tests so workflow claims stay tied to source behavior.
"""
from __future__ import annotations

from typing import Any

from agent.model_scorecard import build_autonomous_model_scorecard


def build_autonomous_workflow_contract() -> dict[str, Any]:
    """Return the current source-of-truth workflow contract."""
    scorecard = build_autonomous_model_scorecard()
    return {
        "schema_version": "cinejelly.autonomous_workflow.v1",
        "product_mode": "autonomous_director_only",
        "one_click_contract": {
            "user_inputs": [
                "short idea or brief",
                "optional target runtime",
                "optional target market",
                "0-9 image references",
                "0-3 video references",
                "0-3 audio references",
            ],
            "user_should_not_choose": [
                "model endpoint",
                "shot count",
                "manual duration per shot",
                "render strategy",
                "reference role labels",
            ],
            "system_promises": [
                "infer niche and viral hook",
                "localize script/caption/proof style",
                "assign every reference a production job",
                "build screenplay/storyboard/shot list",
                "route models internally",
                "render and assemble final MP4",
                "return caption, hashtags, QA metadata, and production graph",
            ],
            "read_only_preview_endpoint": "/api/v1/director/autonomous/production-decision",
        },
        "pipeline": _pipeline_stages(),
        "runtime_strategy": _runtime_strategy(),
        "model_strategy": {
            "active_routes": scorecard.get("active_models", []),
            "future_candidates": scorecard.get("future_candidates", []),
            "routing_rules": scorecard.get("routing_rules", []),
            "dialogue_route_policy": scorecard.get("dialogue_route_policy", {}),
        },
        "niche_strategy": {
            "high_readiness": [
                "ugc_review",
                "beauty",
                "food",
                "ecommerce_catalog",
                "fashion",
                "asmr",
                "app_saas",
                "tech",
                "lifestyle",
            ],
            "medium_readiness": [
                "drama",
                "education",
                "documentary",
                "real_estate",
                "restaurant_hospitality",
                "travel",
                "gaming",
                "automotive",
                "fitness",
                "music_video",
                "anime_comic",
            ],
            "review_required": [
                "finance_education",
                "medical_wellness",
                "kids_family",
                "documentary/news/current-events",
            ],
        },
        "input_upgrade_policy": {
            "schema": "cinejelly.autonomous_input_upgrade_plan.v1",
            "purpose": (
                "Translate reference sufficiency, niche recipe, route quality, "
                "and segment preview into optional user guidance without "
                "reintroducing manual model/settings controls."
            ),
            "renderable_vs_top_tier": [
                "Renderable now means the route can proceed without blocking reference-cap errors.",
                "Top-tier ready means reference quality and route gates are strong enough for the selected niche/runtime.",
                "Premium/top-app claims still require real benchmark evidence even when inputs are strong.",
            ],
            "user_surface": [
                "show one short user_message",
                "show required/recommended/benchmark/review priority actions",
                "show missing minimum refs and missing best-quality refs",
                "never ask the user to pick model endpoint, shot count, or Seedance parameters",
            ],
        },
        "production_gaps": [
            {
                "gap": "true_graph_executor",
                "why_it_matters": "5-30 minute jobs must resume failed scene/chunk/shot nodes after crashes or vendor failures.",
                "current_state": "graph is persisted, worker updates node statuses, execution_batch exposes dependency-safe next tasks, claim_execution_batch leases ready nodes, task result acknowledgement records success/failure, expired leases can be released for retry, run-once and run-loop executor primitives can dispatch injected handlers, artifacts now persist the full DirectorPlan plus reference URLs, a concise agent-readable production report summarizes storyboard/design/graph/QA context for resume/debug, video_worker exposes paid per-shot render, strong graph QA, and final assembly handlers for graph tasks, continuity_handoff_policy makes required previous-frame shot chains auditable before render, and dynamic_keyframe_memory defines how accepted outputs become reusable keyframe anchors; /director/autonomous can route long-form jobs through graph_executor_long_form when CINEJELLY_ENABLE_GRAPH_LONG_FORM=1, while the default remains the legacy linear worker until paid benchmarks validate graph mode.",
                "next_code_step": "run paid long-form benchmark jobs with CINEJELLY_ENABLE_GRAPH_LONG_FORM=1, then promote graph executor mode as default after validation.",
            },
            {
                "gap": "real_benchmark_outputs",
                "why_it_matters": "Top-tier claims require actual vendor clips, cost, latency, QA frames, and human ratings.",
                "current_state": "deterministic benchmark contract, benchmark result store, and non-vendor benchmark runner exist; paid AtlasCloud output URLs, costs, latency, QA frames, and reviewer ratings still need to be attached.",
                "next_code_step": "run selected benchmark cases with paid AtlasCloud renders and PATCH each benchmark row with output evidence.",
            },
            {
                "gap": "asset_pin_management_ui",
                "why_it_matters": "Series/brand consistency needs approved character/product/location/voice/style anchors.",
            "current_state": "asset memory stores suggestions, autonomous_asset_pins persists approved anchors, /studio can approve uploaded image refs as character/product/style memory pins, filter active/paused/archived pins, filter and assign pins by series/campaign key, pause/archive/activate pins, edit role and priority, select active pins, and the autonomous API injects explicit pinned_asset_ids plus safely auto-selected approved pins into the Seedance image reference pool; seedance_reference_allocation previews image/video/audio jobs and long-form last-frame handoff policy before render.",
                "next_code_step": "add full Asset Library admin controls for editing market/niche metadata, location/voice anchors, batch cleanup, dedicated series organization views, and analytics-driven auto-pin scoring.",
            },
            {
                "gap": "strong_visual_audio_qa",
                "why_it_matters": "Agent must catch face drift, product drift, bad captions, silence, loudness, and lip-sync problems.",
                "current_state": "pre-render producer_story_critic scores hook clarity, story causality, payoff, niche proof, market fit, and reference intent; screenplay scene lint catches missing long-form purpose, conflict, turning point, continuity anchor, and scene handoff; pre-render continuity_handoff_policy catches missing previous-frame chains for long-form adjacent shots that share character/product/reference anchors; cross_shot_diagnostic scores transition continuity, subject/product persistence, edit rhythm, and narrative progression across the assembled shot list; pre-render Seedance shot lint catches overlong shots, missing subject/action/camera/setting/audio cues, generic prompts, and overloaded multi-action shots before paid render; media probe, audio loudness/silence probe, frame sampling, optional OCR text-artifact probe, visual reference similarity baseline, semantic QA, and deterministic strong_quality_gate now produce pass/warn/fail scores, retry reasons, duration/audio/reference/caption gates, and retry planner hints; model-backed identity/product/lip-sync validation is still needed for top-tier claims.",
                "next_code_step": "add identity/product embedding checks, robust multilingual OCR/text detection, and lip-sync alignment.",
            },
        ],
        "external_patterns_to_match": [
            "Jellyfish-style durable characters/scenes/props and task tracking",
            "Alibaba LumenX-style script/entity/storyboard/video SOP",
            "ViMax-style director/screenwriter/producer/generator multi-agent orchestration",
            "LumenX/Pixelle-style script-to-storyboard-to-assets-to-video chain",
            "Co-Director-style global creative direction search before committing to a render route",
            "DreamShot-style storyboard/keyframe role conditioning for multi-shot consistency",
            "Huobao-style one-sentence drama agents with skill extensibility",
            "Seedance 2.0 explicit omni-reference prompting and 4-15s shot decomposition",
        ],
    }


def _pipeline_stages() -> list[dict[str, Any]]:
    return [
        {
            "id": "intake",
            "agent_role": "producer",
            "code": ["app/studio/page.tsx", "backend/api/routes/director.py"],
            "input": ["user_idea", "runtime_hint", "target_market", "image/video/audio refs"],
            "output": ["AutonomousGenerateRequest", "uploaded reference URLs"],
            "quality_gate": ["brief >= 5 chars", "reference limits enforced", "market remains optional Auto by default"],
            "status": "implemented",
        },
        {
            "id": "planner",
            "agent_role": "strategist/director",
            "code": ["backend/skills/planner.py", "backend/skills/market_playbooks.py", "backend/skills/niche_playbooks.py"],
            "input": ["idea", "refs", "target_market", "runtime_hint"],
            "output": ["niche", "hook_first_3s", "mood", "suggested_duration", "aspect", "audio_mode"],
            "quality_gate": ["niche matches intent", "hook is visual", "market guidance changes language/proof style"],
            "status": "implemented",
        },
        {
            "id": "reference_role_tagger",
            "agent_role": "casting/art director",
            "code": ["backend/skills/role_tagger.py", "backend/agent/reference_manifest.py", "backend/agent/reference_policy_optimizer.py"],
            "input": ["image refs", "video refs", "audio refs", "niche"],
            "output": ["@image_N roles", "@video_N roles", "@audio_N roles", "per-shot reference policy"],
            "quality_gate": ["every uploaded reference has a job", "production preview exposes Seedance 9/3/3 cap fit", "each shot receives only the strongest needed refs", "video refs guide motion/camera", "audio refs guide beat/SFX/dialogue"],
            "status": "implemented",
        },
        {
            "id": "story_and_screenplay",
            "agent_role": "screenwriter/storyboard director",
            "code": ["backend/skills/storyboard.py", "backend/agent/long_form_orchestrator.py", "backend/agent/scene_planner.py", "backend/agent/screenplay_planner.py"],
            "input": ["planner output", "niche playbook", "runtime class"],
            "output": ["storyboard panels", "scene blueprints", "screenplay plan for >180s"],
            "quality_gate": ["clear beat flow", "long-form split into scenes/chunks/shots", "one physical action per Seedance shot"],
            "status": "implemented_for_planning",
        },
        {
            "id": "director_plan",
            "agent_role": "director/producer",
            "code": ["backend/skills/director.py", "backend/agent/autonomous_director.py", "backend/agent/production_treatment.py", "backend/agent/autonomous_preflight_gate.py", "backend/agent/screenplay_scene_linter.py", "backend/agent/seedance_shot_linter.py", "backend/agent/production_graph.py"],
            "input": ["storyboard", "runtime structure", "roles"],
            "output": ["DirectorPlan", "Production Bible", "production treatment", "preflight report", "shot list", "production graph"],
            "quality_gate": ["shot durations fit model limits", "references are bound into bible", "treatment locks story/camera/edit/reference policy", "preflight checks runtime/ref/model/niche risks", "screenplay scene lint catches weak long-form continuity", "Seedance shot lint catches generic or overpacked shots", "graph has shots/QA/assembly nodes"],
            "status": "implemented",
        },
        {
            "id": "prompt_compiler",
            "agent_role": "cinematographer/prompt engineer",
            "code": ["backend/agent/seedance_prompt_compiler.py", "backend/agent/screenplay_scene_linter.py", "backend/agent/seedance_shot_linter.py", "backend/agent/multi_shot_prompt_builder.py", "backend/agent/scene_generation_agent.py"],
            "input": ["Production Bible", "shot", "reference manifest"],
            "output": ["Seedance-ready prompt sections", "segment inspector preview", "shot contract", "negative prompt", "reference URLs"],
            "quality_gate": ["reference jobs first", "timeline/environment/style/action/camera/sound explicit", "one physical action per shot", "continuity and reference roles locked", "no generic prompt-only scenes"],
            "status": "implemented",
        },
        {
            "id": "model_router",
            "agent_role": "technical producer",
            "code": ["backend/agent/model_picker.py", "backend/agent/model_scorecard.py", "backend/agent/model_specs.py", "backend/agent/dialogue_route_policy.py"],
            "input": ["shot list", "refs", "audio/dialogue needs", "budget"],
            "output": ["Seedance Fast/Premium/i2v/t2v/Wan route", "dialogue insert/repair candidate policy"],
            "quality_gate": ["no model picker UI", "default Seedance Fast Reference", "premium only for hero/fidelity shots", "dialogue models stay benchmark-gated before auto-routing"],
            "status": "implemented_for_active_models",
        },
        {
            "id": "render_worker",
            "agent_role": "render producer",
            "code": ["backend/workers/video_worker.py", "backend/vendors/atlascloud.py"],
            "input": ["DirectorPlan", "model route", "refs"],
            "output": ["per-shot clips", "last-frame chain anchors", "render metadata"],
            "quality_gate": ["Atlas async submit/poll", "Seedance 4-15s clip decomposition", "graph node status updates"],
            "status": "implemented_linear_worker_graph_executor_flagged_for_long_form",
        },
        {
            "id": "qa_retry",
            "agent_role": "QA supervisor",
            "code": ["backend/agent/media_quality_probe.py", "backend/agent/text_artifact_probe.py", "backend/agent/visual_reference_probe.py", "backend/agent/semantic_quality_evaluator.py", "backend/agent/cross_shot_diagnostic.py", "backend/agent/strong_quality_gate.py", "backend/agent/render_retry_planner.py", "backend/agent/render_retry_executor.py"],
            "input": ["rendered clips", "bible", "QA frames"],
            "output": ["render_quality", "retry_plan", "retry_execution"],
            "quality_gate": ["duration/probe checks", "expected audio stream", "audio loudness/silence metrics", "OCR text-artifact probe when available", "visual reference similarity baseline", "cross-shot transition/rhythm/payoff diagnostics", "reference binding", "sample frames", "semantic QA status", "retry only failed safe scopes"],
            "status": "implemented_with_deterministic_gate_needs_model_backed_identity_audio",
        },
        {
            "id": "assembly_and_editor",
            "agent_role": "editor/distribution producer",
            "code": ["backend/workers/assemble_worker.py", "backend/skills/editor.py", "backend/agent/distribution_package.py", "components/studio/JobResultModal.tsx"],
            "input": ["clips", "audio plan", "caption/hashtags", "QA metadata"],
            "output": ["final MP4", "caption", "hashtags", "platform distribution package", "Production Inspector"],
            "quality_gate": ["FFmpeg concat success", "final URL", "user-visible job result, graph inspector, and distribution package"],
            "status": "implemented",
        },
    ]


def _runtime_strategy() -> list[dict[str, Any]]:
    return [
        {
            "class": "short",
            "duration_s": "4-30",
            "strategy": "single-call Seedance multi-shot only for <=15s coherent shots; otherwise 2-6 per-shot clips.",
            "production_status": "strong_candidate",
        },
        {
            "class": "sequence",
            "duration_s": "31-60",
            "strategy": "per-shot chain with reference-to-video and i2v continuity anchors.",
            "production_status": "strong_candidate_with_qa",
        },
        {
            "class": "micro_film",
            "duration_s": "61-180",
            "strategy": "scene beats and per-shot render; needs stricter QA before broad production claims.",
            "production_status": "usable_but_needs_benchmark_outputs",
        },
        {
            "class": "short_film",
            "duration_s": "181-600",
            "strategy": "screenplay -> scenes -> chunks -> shots -> QA -> assembly graph.",
            "production_status": "graph_executor_available_behind_benchmark_flag",
        },
        {
            "class": "episode",
            "duration_s": "601-1800",
            "strategy": "episode graph with resumable chunks, asset pinning, dialogue lanes, and benchmarked model routing.",
            "production_status": "graph_executor_available_needs_paid_benchmarks",
        },
    ]


__all__ = ["build_autonomous_workflow_contract"]
