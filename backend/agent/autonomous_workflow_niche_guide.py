"""Operator-facing workflow and niche guide for CineJelly Autonomous Agent.

This is a compact, source-backed answer to the product question: how does the
agent work today, which niches are strongest, what happens for long-form, and
which proof gates still block top-tier claims?
"""
from __future__ import annotations

from typing import Any

from agent.atlas_model_integration_matrix import build_atlas_model_integration_matrix
from agent.autonomous_market_audit import build_autonomous_market_audit
from agent.autonomous_niche_audit import build_autonomous_niche_audit
from agent.autonomous_niche_launch_matrix import build_autonomous_niche_launch_matrix
from agent.autonomous_niche_playbook_catalog import build_autonomous_niche_playbook_catalog
from agent.autonomous_production_decision import build_autonomous_production_decision
from agent.autonomous_top_tier_completion_gate import build_autonomous_top_tier_completion_gate
from agent.autonomous_workflow_contract import build_autonomous_workflow_contract


def build_autonomous_workflow_niche_guide() -> dict[str, Any]:
    """Return a concise guide composed from current workflow contracts."""
    workflow = build_autonomous_workflow_contract()
    catalog = build_autonomous_niche_playbook_catalog()
    launch = build_autonomous_niche_launch_matrix()
    niche_audit = build_autonomous_niche_audit()
    market_audit = build_autonomous_market_audit()
    atlas = build_atlas_model_integration_matrix()
    gate = build_autonomous_top_tier_completion_gate()

    tiers = launch.get("tiers") or {}
    launch_rows = launch.get("rows") or []
    audit_summary = niche_audit.get("summary") or {}
    market_summary = market_audit.get("summary") or {}

    return {
        "schema_version": "cinejelly.autonomous_workflow_niche_guide.v1",
        "plain_answer": (
            "The project now has a strong autonomous-director architecture for "
            "short-form and a credible graph-based long-form pipeline, but it is "
            "not top-tier proven until real AtlasCloud outputs and reviewer QA "
            "evidence promote the routes."
        ),
        "current_position": {
            "architecture_shape": "close_to_top_autonomous_video_agent",
            "output_claim": "benchmark_gated_not_top_tier_proven",
            "ui_mode": workflow.get("product_mode"),
            "top_tier_proven": bool((gate.get("verdict") or {}).get("top_app_parity_proven")),
            "why_not_proven": (gate.get("verdict") or {}).get("plain_answer"),
        },
        "workflow_steps": [
            {
                "step": index,
                "id": stage.get("id"),
                "role": stage.get("agent_role"),
                "produces": stage.get("output", []),
                "quality_gate": stage.get("quality_gate", []),
                "status": stage.get("status"),
            }
            for index, stage in enumerate(workflow.get("pipeline") or [], start=1)
        ],
        "duration_strategy": catalog.get("duration_templates", []),
        "long_form_rule": {
            "hard_rule": "Never generate 5-30 minutes as one model call.",
            "method": [
                "screenplay first",
                "act/scene/chunk decomposition",
                "4-15s Seedance render units",
                "previous-frame and keyframe handoffs",
                "production graph leases/retries",
                "QA and selective rerender before final assembly",
            ],
            "status": "implemented_architecture_benchmark_gated",
            "proof_needed": [
                "paid graph-mode 5-10m outputs",
                "accepted continuity across scenes",
                "cost/latency/retry evidence",
                "reviewer notes and QA score",
            ],
        },
        "long_form_blueprints": _long_form_blueprints(),
        "niche_fit": {
            "sell_first": tiers.get("sell_first", []),
            "benchmark_next": tiers.get("benchmark_next", []),
            "review_locked": tiers.get("review_locked", []),
            "cards": _niche_cards(launch_rows),
            "audit_summary": audit_summary,
            "rule": (
                "Sell short-form first, benchmark long/dialogue/fact-heavy routes, "
                "and keep regulated or child-facing niches review-locked."
            ),
        },
        "market_and_language": {
            "recommendation": "Keep Auto as default; expose market as optional audience/language guidance only.",
            "summary": market_summary,
            "policy": market_audit.get("policy", {}),
            "vietnam_status": {
                "dialogue_candidate": market_summary.get("vn_dialogue_candidate"),
                "post_process_candidate": market_summary.get("vn_post_process_candidate"),
                "auto_route_status": "benchmark_gated",
            },
        },
        "seedance_2_usage": {
            "core_rules": atlas.get("source_backed_model_rules", []),
            "default_route": (atlas.get("recommendation") or {}).get("default_route"),
            "premium_route": (atlas.get("recommendation") or {}).get("premium_route"),
            "model_picker_visible_to_user": bool((atlas.get("recommendation") or {}).get("keep_ui_model_picker")),
            "lane_policy": atlas.get("lane_policy", {}),
        },
        "scenario_route_examples": _scenario_route_examples(),
        "qa_evidence_plan": _qa_evidence_plan(),
        "user_input_guidance": [
            {
                "case": "product/UGC/social short",
                "best_refs": ["creator or product hero image", "product/detail/style image", "optional motion or SFX/audio ref"],
                "expected_result": "15-60s hook, proof/demo, payoff, caption, hashtags",
            },
            {
                "case": "beauty/food/fashion",
                "best_refs": ["macro material/texture image", "hero product image", "lighting/style image", "beat/SFX ref"],
                "expected_result": "premium visual route for hero shots; still benchmark before top-tier claim",
            },
            {
                "case": "real estate/travel/restaurant",
                "best_refs": ["location/environment images", "walkthrough/camera-motion video", "ambience audio"],
                "expected_result": "spatially readable tour with motion/camera guidance",
            },
            {
                "case": "drama/short film/long form",
                "best_refs": ["character face/outfit", "location/style", "approved pins", "voice/dialogue sample if speech matters"],
                "expected_result": "screenplay, scenes, graph chunks, handoffs, dialogue inserts, QA",
            },
        ],
        "upgrade_order": [
            "Run paid AtlasCloud benchmark manifest for sell-first niches.",
            "Run VN dialogue benchmark for InfiniteTalk, MultiTalk, Wan, ByteDance/Kling lipsync.",
            "Run 5-10m graph-mode short film benchmarks with CINEJELLY_ENABLE_GRAPH_LONG_FORM=1.",
            "Add model-backed identity/product/OCR/audio/lipsync QA evidence to benchmark rows.",
            "Expand asset library from pins into character/product/location/style/voice memory with analytics.",
            "Promote only routes that pass two real outputs per model/niche/runtime/market.",
        ],
        "evidence_endpoints": [
            "/api/v1/director/autonomous/workflow-niche-guide",
            "/api/v1/director/autonomous/production-decision",
            "/api/v1/director/autonomous/niche-audit",
            "/api/v1/director/autonomous/market-audit",
            "/api/v1/director/autonomous/atlas-model-matrix",
            "/api/v1/director/autonomous/top-tier-completion-gate",
            "/api/v1/director/jobs/{job_id}/production-report",
            "/api/v1/director/jobs/{job_id}/benchmark-evidence-pack",
        ],
    }


def _niche_cards(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return compact niche cards ordered by launch priority."""
    priority = {"sell_first": 0, "benchmark_next": 1, "review_locked": 2}
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            priority.get(str(row.get("launch_tier")), 9),
            str(row.get("niche") or ""),
        ),
    )
    return [
        {
            "niche": row.get("niche"),
            "launch_tier": row.get("launch_tier"),
            "readiness": row.get("readiness"),
            "best_for": row.get("best_for"),
            "default_user_promise": row.get("default_user_promise"),
            "best_runtime_today": row.get("best_runtime_today"),
            "max_default_duration_s": row.get("max_default_duration_s"),
            "long_form_status": row.get("long_form_status"),
            "primary_visual_model": row.get("primary_visual_model"),
            "continuity_model": row.get("continuity_model"),
            "reference_contract": row.get("reference_contract"),
            "hook_moves": row.get("hook_moves", [])[:3],
            "benchmark_before": row.get("benchmark_before", [])[:4],
            "operator_action": row.get("operator_action"),
        }
        for row in sorted_rows
    ]


def _scenario_route_examples() -> list[dict[str, Any]]:
    """Show concrete route behavior for representative real product cases."""
    scenarios = [
        {
            "id": "vn_beauty_short",
            "label": "Vietnam beauty short",
            "idea": "Đánh giá serum dưỡng da TikTok Việt Nam, cận texture, before-after nhẹ, caption tiếng Việt",
            "target_market": "vn",
            "target_platform": "tiktok",
            "duration_s": 30,
            "niche_hint": "beauty",
            "refs": {"images": 3, "videos": 1, "audios": 1},
            "speakers": 1,
        },
        {
            "id": "global_saas_launch",
            "label": "Global SaaS launch",
            "idea": "AI workflow app launch video showing manual task versus automated dashboard result",
            "target_market": "global",
            "target_platform": "linkedin",
            "duration_s": 45,
            "niche_hint": "app_saas",
            "refs": {"images": 2, "videos": 1, "audios": 0},
            "speakers": 1,
        },
        {
            "id": "real_estate_tour",
            "label": "Real-estate tour",
            "idea": "Luxury apartment walkthrough with balcony reveal and calm premium camera movement",
            "target_market": "sea",
            "target_platform": "youtube_shorts",
            "duration_s": 60,
            "niche_hint": "real_estate",
            "refs": {"images": 4, "videos": 1, "audios": 0},
            "speakers": 1,
        },
        {
            "id": "vn_drama_5m",
            "label": "Vietnamese 5m drama",
            "idea": "Phim ngắn 5 phút có thoại tiếng Việt về bí mật gia đình, cảm xúc mạnh, cú twist cuối",
            "target_market": "vn",
            "target_platform": "youtube_long",
            "duration_s": 300,
            "niche_hint": "drama",
            "refs": {"images": 4, "videos": 1, "audios": 1, "pinned_assets": 1},
            "speakers": 2,
        },
        {
            "id": "medical_wellness_explainer",
            "label": "Medical wellness explainer",
            "idea": "Sleep wellness explainer with safe routine tips, no diagnosis or cure claim",
            "target_market": "us",
            "target_platform": "tiktok",
            "duration_s": 45,
            "niche_hint": "medical_wellness",
            "refs": {"images": 2, "videos": 0, "audios": 1},
            "speakers": 1,
        },
    ]
    return [_scenario_row(scenario) for scenario in scenarios]


def _long_form_blueprints() -> list[dict[str, Any]]:
    """Return concrete long-form planning examples backed by production decisions."""
    blueprints = [
        {
            "id": "three_minute_product_story",
            "label": "3m product micro-film",
            "idea": "Three-minute product story showing problem, proof, creator use, and payoff",
            "target_market": "global",
            "target_platform": "youtube_shorts",
            "duration_s": 180,
            "niche_hint": "ugc_review",
            "refs": {"images": 3, "videos": 1, "audios": 1},
            "speakers": 1,
        },
        {
            "id": "five_minute_short_film",
            "label": "5m short film",
            "idea": "Phim ngắn 5 phút có nhân vật chính, bí mật gia đình, xung đột, cú twist cuối",
            "target_market": "vn",
            "target_platform": "youtube_long",
            "duration_s": 300,
            "niche_hint": "drama",
            "refs": {"images": 4, "videos": 1, "audios": 1, "pinned_assets": 1},
            "speakers": 2,
        },
        {
            "id": "thirty_minute_episode",
            "label": "30m episode",
            "idea": "Thirty-minute episodic founder documentary with recurring characters, locations, voiceover, conflict and resolution",
            "target_market": "global",
            "target_platform": "youtube_long",
            "duration_s": 1800,
            "niche_hint": "documentary",
            "refs": {"images": 5, "videos": 2, "audios": 1, "pinned_assets": 2},
            "speakers": 2,
        },
    ]
    return [_long_form_blueprint_row(item) for item in blueprints]


def _long_form_blueprint_row(item: dict[str, Any]) -> dict[str, Any]:
    decision = build_autonomous_production_decision(
        user_idea=str(item["idea"]),
        target_market=str(item["target_market"]),
        target_platform=str(item["target_platform"]),
        duration_hint_s=int(item["duration_s"]),
        reference_counts=dict(item["refs"]),
        niche_hint=str(item["niche_hint"]),
        speaker_count=int(item["speakers"]),
    )
    d = decision.get("decision") or {}
    runtime = decision.get("runtime_structure") or {}
    segment = decision.get("seedance_segment_inspector") or {}
    graph_gate = decision.get("long_form_execution_gate") or {}
    route = d.get("primary_model_route") or {}
    dialogue = d.get("dialogue_route_policy") or {}
    return {
        "id": item["id"],
        "label": item["label"],
        "niche": d.get("niche"),
        "runtime_class": d.get("runtime_class"),
        "duration_s": d.get("target_duration_s"),
        "act_count": runtime.get("act_count"),
        "scene_count": runtime.get("scene_count"),
        "chunk_count": runtime.get("chunk_count"),
        "estimated_seedance_units": segment.get("estimated_total_units"),
        "preview_segment_count": segment.get("preview_segment_count"),
        "primary_visual_model": route.get("primary_visual_model"),
        "continuity_model": route.get("continuity_model"),
        "graph_required": bool(d.get("graph_required")),
        "graph_gate_status": graph_gate.get("status"),
        "dialogue_required": bool(d.get("dialogue_required")),
        "dialogue_candidate": dialogue.get("dialogue_candidate"),
        "auto_route_allowed": bool((decision.get("route_quality_scorecard") or {}).get("auto_route_allowed")),
        "top_tier_claim_allowed": bool((decision.get("route_quality_scorecard") or {}).get("top_tier_claim_allowed")),
        "method": [
            "write screenplay and scene purpose before rendering",
            "split into 4-15s Seedance units",
            "carry accepted final frames/keyframes into later shots",
            "QA and selectively rerender failed units before assembly",
        ],
        "proof_needed": [
            "paid output URL",
            "continuity reviewer notes",
            "cost/latency/retry count",
            "identity/product/audio/lip-sync QA evidence when applicable",
        ],
    }


def _qa_evidence_plan() -> dict[str, Any]:
    """Return the proof checklist required before promoting routes as top-tier."""
    dimensions = [
        {
            "id": "reference_identity_adherence",
            "applies_to": ["human_creator", "character", "product_spokesperson", "drama", "short_film"],
            "current_status": "partial_deterministic_probe",
            "source_modules": [
                "visual_reference_probe",
                "semantic_quality_evaluator",
                "benchmark_evidence_validator",
            ],
            "evidence_required": [
                "visual_reference_report",
                "reference_identity_notes",
                "sampled_qa_frames",
                "reviewer_notes",
            ],
            "promotion_rule": "No identity-heavy route is promoted until visual similarity and human reviewer notes pass on real paid outputs.",
        },
        {
            "id": "product_and_brand_fidelity",
            "applies_to": ["beauty", "food_recipe", "fashion", "ecommerce_catalog", "app_saas", "tech", "automotive"],
            "current_status": "benchmark_required",
            "source_modules": [
                "reference_asset_quality_gate",
                "semantic_quality_evaluator",
                "benchmark_evidence_validator",
            ],
            "evidence_required": [
                "product_closeup_frames",
                "brand_text_or_logo_ocr_report",
                "material_texture_notes",
                "reviewer_notes",
            ],
            "promotion_rule": "Premium product claims need close-up fidelity, no hallucinated logo/text, and two accepted paid examples per route.",
        },
        {
            "id": "ocr_text_artifact_control",
            "applies_to": ["captions", "packaging", "ui_demo", "ads", "education", "app_saas"],
            "current_status": "needs_model_backed_qa",
            "source_modules": [
                "text_artifact_report",
                "caption_burn_in",
                "benchmark_evidence_validator",
            ],
            "evidence_required": [
                "sampled_frame_ocr",
                "caption_alignment_report",
                "forbidden_hallucinated_text_notes",
            ],
            "promotion_rule": "Routes with visible text stay evidence-gated until OCR checks show readable intended text and no harmful hallucinated overlays.",
        },
        {
            "id": "audio_and_loudness",
            "applies_to": ["all_routes_with_music_sfx_or_voice"],
            "current_status": "deterministic_report_ready_model_qa_needed",
            "source_modules": [
                "audio_design_plan",
                "audio_validation_report",
                "post_process_candidate",
            ],
            "evidence_required": [
                "loudness_report",
                "silence_clip_report",
                "music_sfx_sync_notes",
                "reviewer_notes",
            ],
            "promotion_rule": "Audio lanes need loudness/silence metrics plus reviewer approval before being treated as production-default.",
        },
        {
            "id": "dialogue_lipsync",
            "applies_to": ["dialogue", "vn", "jp", "kr", "short_film", "episode"],
            "current_status": "benchmark_gated",
            "source_modules": [
                "dialogue_route_policy",
                "post_process_candidate",
                "benchmark_evidence_validator",
            ],
            "evidence_required": [
                "dialogue_output_url",
                "lip_sync_reviewer_notes",
                "phoneme_or_alignment_report",
                "speaker_consistency_notes",
            ],
            "promotion_rule": "Vietnamese and multi-speaker dialogue cannot auto-promote until lip-sync and speaker consistency pass real benchmarks.",
        },
        {
            "id": "cross_shot_continuity",
            "applies_to": ["micro_film", "short_film", "episode", "multi_scene_ads", "story_drama"],
            "current_status": "architecture_ready_paid_proof_needed",
            "source_modules": [
                "storyboard_contract",
                "dynamic_keyframe_memory",
                "cross_shot_diagnostic",
            ],
            "evidence_required": [
                "scene_handoff_frames",
                "accepted_keyframes",
                "cross_shot_continuity_report",
                "reviewer_notes",
            ],
            "promotion_rule": "Long-form and story routes need continuity evidence across scene boundaries before any top-tier claim.",
        },
        {
            "id": "long_form_graph_execution",
            "applies_to": ["duration_over_180s", "short_film", "episode"],
            "current_status": "implemented_architecture_benchmark_gated",
            "source_modules": [
                "production_graph",
                "graph_leases",
                "job_production_report",
            ],
            "evidence_required": [
                "production_graph_json",
                "execution_logs",
                "retry_count",
                "assembly_report",
                "paid_output_url",
            ],
            "promotion_rule": "5-30m jobs must prove graph execution, retries, assembly, and continuity before becoming default production promises.",
        },
        {
            "id": "cost_latency_retry",
            "applies_to": ["all_routes"],
            "current_status": "manifest_estimated_paid_measurement_needed",
            "source_modules": [
                "paid_benchmark_manifest",
                "benchmark_runbook",
                "benchmark_evidence_pack",
            ],
            "evidence_required": [
                "cost_usd",
                "latency_s",
                "retry_count",
                "accepted_minute_cost",
                "route_promotion_decision",
            ],
            "promotion_rule": "Routes need measured accepted-minute cost and retry data, not only estimated vendor pricing.",
        },
    ]
    return {
        "dimension_count": len(dimensions),
        "model_backed_required_before_top_tier": True,
        "currently_top_tier_blocked_by": [
            "real_paid_atlascloud_outputs",
            "model_backed_identity_product_lipsync_qa",
            "long_form_graph_benchmarks",
            "measured_cost_latency_retry_data",
        ],
        "dimensions": dimensions,
        "rule": (
            "Autonomous planning can stay one-click, but route promotion must be evidence-based: "
            "paid output, deterministic metrics, model-backed QA, and reviewer notes."
        ),
    }


def _scenario_row(scenario: dict[str, Any]) -> dict[str, Any]:
    decision = build_autonomous_production_decision(
        user_idea=str(scenario["idea"]),
        target_market=str(scenario["target_market"]),
        target_platform=str(scenario["target_platform"]),
        duration_hint_s=int(scenario["duration_s"]),
        reference_counts=dict(scenario["refs"]),
        niche_hint=str(scenario["niche_hint"]),
        speaker_count=int(scenario["speakers"]),
    )
    d = decision.get("decision") or {}
    route = d.get("primary_model_route") or {}
    dialogue = d.get("dialogue_route_policy") or {}
    score = decision.get("route_quality_scorecard") or {}
    refs = decision.get("reference_sufficiency") or {}
    safety = decision.get("responsible_content_gate") or {}
    return {
        "id": scenario["id"],
        "label": scenario["label"],
        "niche": d.get("niche"),
        "runtime_class": d.get("runtime_class"),
        "target_market": d.get("target_market"),
        "duration_s": d.get("target_duration_s"),
        "primary_visual_model": route.get("primary_visual_model"),
        "continuity_model": route.get("continuity_model"),
        "dialogue_required": bool(d.get("dialogue_required")),
        "dialogue_candidate": dialogue.get("dialogue_candidate"),
        "post_process_candidate": dialogue.get("post_process_candidate"),
        "graph_required": bool(d.get("graph_required")),
        "auto_route_allowed": bool(score.get("auto_route_allowed")),
        "manual_review_required": bool(
            safety.get("manual_review_required")
            or d.get("responsible_review_required")
            or dialogue.get("requires_benchmark_before_auto_route")
        ),
        "reference_status": refs.get("status"),
        "top_tier_claim_allowed": bool(score.get("top_tier_claim_allowed")),
        "operator_read": _scenario_operator_read(
            graph_required=bool(d.get("graph_required")),
            auto_route_allowed=bool(score.get("auto_route_allowed")),
            manual_review_required=bool(
                safety.get("manual_review_required")
                or d.get("responsible_review_required")
                or dialogue.get("requires_benchmark_before_auto_route")
            ),
        ),
    }


def _scenario_operator_read(
    *,
    graph_required: bool,
    auto_route_allowed: bool,
    manual_review_required: bool,
) -> str:
    if graph_required:
        return "long-form graph route; benchmark evidence required before default production claim"
    if manual_review_required:
        return "can plan/render with review gate; do not auto-publish or claim top-tier"
    if auto_route_allowed:
        return "short-form autonomous route is eligible when preflight passes"
    return "preview/benchmark route; improve refs or review before production"


__all__ = ["build_autonomous_workflow_niche_guide"]
