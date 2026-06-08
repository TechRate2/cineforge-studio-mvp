"""Deterministic backend smoke tests for CineJelly Autonomous Agent.

These tests do not call LLMs or AtlasCloud. They protect the routing contracts
that make the one-click agent behave like a producer/director instead of a
generic prompt sender.
"""
from __future__ import annotations

import sys
import asyncio
import hashlib
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.autonomous_production_decision import build_autonomous_production_decision
from agent.autonomous_director import (
    _apply_planner_decision_guard,
    _apply_creative_treatment_to_planner,
    _build_director_plan,
)
from agent.autonomous_benchmark_suite import build_autonomous_benchmark_contract
from agent.autonomous_benchmark_planner import build_autonomous_benchmark_plan
from agent.autonomous_capability_matrix import build_autonomous_capability_matrix
from agent.autonomous_competitive_research import build_autonomous_competitive_research
from agent.autonomous_niche_launch_matrix import build_autonomous_niche_launch_matrix
from agent.autonomous_niche_audit import build_autonomous_niche_audit
from agent.autonomous_market_audit import build_autonomous_market_audit
from agent.autonomous_niche_playbook_catalog import build_autonomous_niche_playbook_catalog
from agent.autonomous_operator_brief import build_autonomous_operator_brief
from agent.autonomous_paid_benchmark_manifest import build_autonomous_paid_benchmark_manifest
from agent.autonomous_production_audit import build_autonomous_production_audit
from agent.autonomous_preflight_gate import build_autonomous_preflight_report
from agent.autonomous_top_tier_completion_gate import build_autonomous_top_tier_completion_gate
from agent.autonomous_workflow_niche_guide import build_autonomous_workflow_niche_guide
from agent.atlas_model_integration_matrix import build_atlas_model_integration_matrix
from agent.cinematic_grammar_contract import build_cinematic_grammar_contract
from agent.phase3_prompt_route_audit import build_phase3_prompt_route_audit
from agent.phase4_non_paid_completion_audit import build_phase4_non_paid_completion_audit
from agent.prompt_execution_contract_v3 import build_prompt_execution_contract_v3
from agent.viral_creative_brain import build_viral_creative_brain
from agent.output_qa_retry_brain import build_output_qa_retry_brain
from agent.benchmark_promotion_policy import build_benchmark_promotion_policy
from agent.benchmark_evidence_validator import REQUIRED_EVIDENCE_KEYS, validate_benchmark_result_evidence
from agent.benchmark_evidence_pack_builder import build_benchmark_result_draft_from_artifact
from core.config import settings
from core.production_artifacts import load_report
from vendors.llm_router import llm
from agent.autonomous_benchmark_runner import run_autonomous_benchmark_batch
from agent.benchmark_review_rubric import build_benchmark_review_rubric, score_benchmark_review
from agent.conversational_preflight import build_conversational_preflight
from agent.continuity_handoff_policy import (
    apply_continuity_handoffs,
    build_continuity_handoff_policy,
)
from agent.creative_brief_contract import build_creative_brief_contract
from agent.creative_producer_v2 import build_creative_producer_v2
from agent.creative_treatment_search import build_creative_treatment_search
from agent.cross_shot_diagnostic import diagnose_cross_shot_coherence
from agent.dialogue_route_policy import build_dialogue_route_policy
from agent.distribution_package import build_distribution_package
from agent.dynamic_keyframe_memory import build_dynamic_keyframe_memory_contract
from agent.long_form_execution_gate import build_long_form_execution_gate
from agent.llm_brain_policy import build_llm_brain_policy
from agent.producer_story_critic import critique_producer_story
from agent.production_graph import build_production_graph
from agent.responsible_content_gate import build_responsible_content_gate
from agent.asset_memory import select_approved_asset_pins_for_render
from agent.niche_runtime_director import build_niche_runtime_director_contract
from agent.niche_production_recipe import build_niche_production_recipe
from agent.schemas import (
    AudioDesign,
    Constraints,
    ContinuityBible,
    CostEstimate,
    DirectorPlan,
    EvaluationReport,
    Setting,
    Shot,
    ShotAudio,
    ShotContinuity,
    ShotVisual,
    VisualStyle,
)
from agent.screenplay_scene_linter import lint_screenplay_scene_structure
from agent.seedance_prompt_compiler import compile_seedance_scene_prompt
from agent.seedance_shot_linter import lint_seedance_plan
from agent.seedance_reference_allocation import build_seedance_reference_allocation
from agent.multi_shot_prompt_builder import build_seedance_2_multi_shot
from core import assets_store, autonomous_asset_pins, autonomous_benchmark_store
from skills.niche_benchmarks import list_benchmark_cases
from skills.planner import PlannerOutput
from skills.storyboard import StoryboardOutput, StoryboardPanel
from skills.director import DirectorOutput, DirectorShotSpec
from skills.role_tagger import RoleTaggerOutput, TaggedReference
from api.routes.director import (
    AutonomousGenerateRequest,
    _apply_benchmark_review_scores,
    _approved_plan_meta_from_request,
    autonomous_generate,
)


_REVIEW_REQUIRED = {"documentary", "finance_education", "kids_family", "medical_wellness"}
_PREMIUM_VISUAL_NICHES = {"beauty", "fashion", "food", "ecommerce_catalog"}


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _decision(**kwargs):
    return build_autonomous_production_decision(**kwargs)


def _reference_counts(strategy: list[str]) -> dict[str, int]:
    counts = {"images": 0, "videos": 0, "audios": 0}
    for item in strategy:
        text = item.lower()
        if "video" in text:
            counts["videos"] += 1
        elif any(token in text for token in ("audio", "voice", "music", "beat", "ambience")):
            counts["audios"] += 1
        else:
            counts["images"] += 1
    return counts


def _minimal_plan(shots: list[Shot], *, duration_s: int | None = None, runtime_structure: dict | None = None) -> DirectorPlan:
    resolved_duration = int(duration_s if duration_s is not None else sum(int(s.duration_s) for s in shots))
    return DirectorPlan(
        plan_id="test_plan",
        created_at="2026-06-01T00:00:00Z",
        continuity_bible=ContinuityBible(
            title="Test plan",
            logline="A creator tests a product with a clear visual proof.",
            intent="ugc_review",
            duration_s=resolved_duration,
            characters=[],
            products=[],
            visual_style=VisualStyle(
                cinematography="handheld UGC",
                color_grading="warm natural",
                lighting_design="soft window light",
                camera_language="macro close-ups and handheld POV",
            ),
            audio_design=AudioDesign(
                mood="authentic",
                music_genre="light creator beat",
                sfx_emphasis=["tap", "click"],
            ),
            setting=Setting(location="Saigon cafe", time_of_day="afternoon", atmosphere="warm"),
            constraints=Constraints(must_avoid=["fake claims"]),
            storytelling_meta={
                "niche": "ugc_review",
                "runtime_structure": runtime_structure or {},
                "market_playbook": {
                    "target_market": "vn",
                    "hook_style": "direct visual proof",
                    "caption_language": "Vietnamese first",
                },
                "niche_playbook": {
                    "niche": "ugc_review",
                    "beat_flow": ["result hook", "why viewer cares", "test in hand", "proof result", "soft recommendation"],
                },
                "production_treatment": {
                    "story_engine": "result first",
                    "camera_language": "handheld",
                    "editing_rhythm": "fast proof beats",
                    "reference_policy": "use product ref for hero shots",
                    "seedance_execution": "4-15s per shot",
                    "qa_risks": ["product drift"],
                },
            },
        ),
        shot_list=shots,
        evaluation=EvaluationReport(
            consistency_score=8,
            viral_potential_score=8,
            cinematic_score=8,
            pacing_score=8,
            brand_safety_score=8,
            overall_score=8,
        ),
        cost_estimate=CostEstimate(total_cost_usd=0.01),
    )


def _valid_long_form_runtime_structure() -> dict:
    scenes = [
        {
            "scene_id": "SC01",
            "index": 0,
            "act": 1,
            "duration_s": 60,
            "purpose": "cold_open_result_hook",
            "dramatic_question": "What surprising test result makes the viewer care about the product promise?",
            "visual_hook": "Creator reveals the result before explaining the test",
            "continuity_anchor": "Establish same creator, product bottle, cafe table, and warm handheld style",
            "handoff_to_next": "End on an unresolved product flaw that makes the next test necessary",
        },
        {
            "scene_id": "SC02",
            "index": 1,
            "act": 2,
            "duration_s": 120,
            "purpose": "escalation_test_in_hand",
            "dramatic_question": "Does the in-hand test prove the claim under realistic conditions?",
            "visual_hook": "Macro close-up of the product texture changing under real use",
            "continuity_anchor": "Carry forward same creator/product/location and previous closing frame",
            "handoff_to_next": "End with a visible result that sets up the final verdict",
        },
        {
            "scene_id": "SC03",
            "index": 2,
            "act": 3,
            "duration_s": 120,
            "purpose": "final_payoff_soft_recommendation",
            "dramatic_question": "What final visual proof resolves the product promise honestly?",
            "visual_hook": "Before-after result shown through a natural creator reaction",
            "continuity_anchor": "Carry forward creator face, product geometry, cafe light, and tone",
            "handoff_to_next": "End with a memorable final image and emotional payoff",
        },
    ]
    scripts = [
        {
            "scene_id": scene["scene_id"],
            "act": scene["act"],
            "duration_s": scene["duration_s"],
            "premise": f"{scene['purpose']}: {scene['dramatic_question']}",
            "conflict": "The visual test must overcome viewer skepticism with a real proof beat.",
            "turning_point": "A visible result changes what the viewer believes and motivates the next scene.",
            "opening_image": scene["visual_hook"],
            "closing_image": scene["handoff_to_next"],
            "dialogue_or_vo_intent": "One short natural Vietnamese creator line supports the visual proof.",
            "reference_priorities": ["creator image", "product image", "previous scene final frame"],
            "qa_focus": ["identity continuity", "product geometry", "scene purpose visible"],
        }
        for scene in scenes
    ]
    return {
        "runtime_class": "short_film",
        "target_duration_s": 300,
        "scene_count": 3,
        "scene_blueprints": scenes,
        "screenplay_plan": {
            "logline": "A creator turns a surprising product test into a believable visual proof arc.",
            "act_beats": [{"act": 1}, {"act": 2}, {"act": 3}],
            "scene_scripts": scripts,
            "continuity_contract": [
                "Every scene carries forward the same creator/product/location unless explicitly changed.",
                "Every scene ends with a handoff image that motivates the next scene.",
            ],
            "editor_promise": "The final cut should feel like one continuous product short film with proof and payoff.",
        },
    }


def _valid_scene_memory_pack(shots: list[Shot]) -> dict:
    return {
        "schema_version": "cinejelly.scene_memory_pack.v1",
        "runtime_class": "short_film",
        "target_duration_s": 300,
        "scene_count": 3,
        "shot_count": len(shots),
        "scene_memory": [
            {
                "scene_id": "SC01",
                "index": 0,
                "act": 1,
                "duration_s": 60,
                "purpose": "cold_open_result_hook",
                "opening_image_intent": "creator reveals the final proof first",
                "closing_image_intent": "unresolved flaw sets up the next test",
                "continuity_anchor": "same creator, product, cafe table, warm handheld style",
                "handoff_to_next": "visible unresolved flaw",
                "shot_ids": ["S1", "S2"],
                "first_shot_id": "S1",
                "last_shot_id": "S2",
            },
            {
                "scene_id": "SC02",
                "index": 1,
                "act": 2,
                "duration_s": 120,
                "purpose": "escalation_test_in_hand",
                "opening_image_intent": "macro texture test continues from the previous frame",
                "closing_image_intent": "visible result sets up final verdict",
                "continuity_anchor": "same creator/product/location plus previous final frame",
                "handoff_to_next": "result close-up",
                "shot_ids": ["S3", "S4"],
                "first_shot_id": "S3",
                "last_shot_id": "S4",
            },
            {
                "scene_id": "SC03",
                "index": 2,
                "act": 3,
                "duration_s": 120,
                "purpose": "final_payoff_soft_recommendation",
                "opening_image_intent": "final verdict starts from the prior result image",
                "closing_image_intent": "memorable proof and emotional payoff",
                "continuity_anchor": "same creator/product/light/tone",
                "handoff_to_next": "final proof image",
                "shot_ids": ["S5", "S6"],
                "first_shot_id": "S5",
                "last_shot_id": "S6",
            },
        ],
        "shot_scene_map": [
            {
                "shot_id": shot.shot_id,
                "scene_id": "SC01" if i < 2 else "SC02" if i < 4 else "SC03",
                "scene_index": 0 if i < 2 else 1 if i < 4 else 2,
                "previous_shot_id": shot.continuity.previous_shot_id,
            }
            for i, shot in enumerate(shots)
        ],
        "bridge_policy": {
            "runtime_requires_scene_bridges": True,
            "bridge_count": 2,
            "bridges": [
                {
                    "from_scene_id": "SC01",
                    "to_scene_id": "SC02",
                    "source_last_shot_id": "S2",
                    "target_first_shot_id": "S3",
                    "preferred_bridge": "previous final frame becomes the first close-up of the next test",
                },
                {
                    "from_scene_id": "SC02",
                    "to_scene_id": "SC03",
                    "source_last_shot_id": "S4",
                    "target_first_shot_id": "S5",
                    "preferred_bridge": "result close-up carries into the final verdict",
                },
            ],
        },
    }


def _shot(
    *,
    shot_id: str = "S1",
    index: int = 0,
    start_s: int = 0,
    duration_s: int = 8,
    purpose: str = "hook",
    character_ids: list[str] | None = None,
    product_ids: list[str] | None = None,
    reference_indices: list[int] | None = None,
    previous_shot_id: str | None = None,
    subject: str = "Vietnamese creator holding a matte black perfume bottle",
    action: str = "sprays perfume onto a paper strip and reacts to the first scent",
    camera_shot: str = "CU macro",
    camera_movement: str = "slow handheld push-in",
    background: str = "small Saigon cafe table",
) -> Shot:
    return Shot(
        shot_id=shot_id,
        index=index,
        start_s=start_s,
        end_s=start_s + duration_s,
        duration_s=duration_s,
        purpose=purpose,
        emotion_beat="curiosity",
        visual=ShotVisual(
            subject=subject,
            action=action,
            camera_shot=camera_shot,
            camera_movement=camera_movement,
            background=background,
        ),
        audio=ShotAudio(sfx=["spray", "paper rustle"], music_cue="soft creator beat"),
        continuity=ShotContinuity(
            character_ids=character_ids or [],
            product_ids=product_ids or [],
            reference_indices=reference_indices or [],
            previous_shot_id=previous_shot_id,
            style_anchor="warm handheld cafe UGC",
        ),
    )


def test_beauty_premium_seedance() -> None:
    data = _decision(
        user_idea="A Vietnamese beauty creator tests a premium lipstick in a Saigon cafe with macro texture.",
        target_market="vn",
        duration_hint_s=30,
        reference_counts={"images": 2, "videos": 0, "audios": 1},
    )
    decision = data["decision"]
    _assert(decision["niche"] == "beauty", f"expected beauty, got {decision['niche']}")
    _assert(decision["runtime_class"] == "short", f"expected short, got {decision['runtime_class']}")
    _assert(
        decision["primary_model_route"]["primary_visual_model"] == "seedance_2_0_ref",
        "beauty/product hero should use premium Seedance reference route",
    )
    _assert(decision["dialogue_required"] is False, "audio texture ref must not force dialogue lane")
    _assert(decision["graph_required"] is False, "30s beauty short should not require graph")


def test_vietnamese_beauty_review_routes_to_beauty_not_generic_ugc() -> None:
    data = _decision(
        user_idea="Một creator Việt review son môi cao cấp trong quán cafe Sài Gòn, quay cận texture và có voiceover ngắn.",
        target_market="vn",
        target_platform="tiktok",
        duration_hint_s=300,
        reference_counts={"images": 2, "videos": 0, "audios": 1},
    )
    decision = data["decision"]
    _assert(decision["niche"] == "beauty", f"expected Vietnamese beauty niche, got {decision['niche']}")
    _assert(decision["runtime_class"] == "short_film", "300s Vietnamese beauty review should still use short_film runtime")
    _assert(decision["primary_model_route"]["primary_visual_model"] == "seedance_2_0_ref", "beauty hero/product shots should use premium reference route")
    _assert(decision["dialogue_required"] is True, "voiceover Vietnamese beauty review should use dialogue lane")
    _assert(decision["graph_required"] is True, "5 minute Vietnamese beauty review should require graph execution")


def test_vietnamese_market_keywords_route_specific_niches() -> None:
    cases = [
        ("Tour căn hộ có ban công, phòng ngủ và ánh sáng tự nhiên cho khách mua nhà.", "real_estate"),
        ("Giải thích cách lập quỹ dự phòng và tiết kiệm tiền bằng ví dụ hóa đơn tháng.", "finance_education"),
        ("Video du lịch Đà Nẵng 3 ngày với biển, lịch trình ăn uống và góc quay flycam.", "travel"),
        ("Một huấn luyện viên hướng dẫn tư thế squat đúng trong phòng tập gym.", "fitness"),
        ("Tao video 5 phut ve mot founder Viet Nam ra mat app AI giup shop online tang doanh thu, co kich tinh, demo san pham.", "app_saas"),
        ("Creator review app AI quan ly don hang cho shop online, co dashboard va ket qua tang doanh thu.", "app_saas"),
        ("Mot shop thoi trang ra mat bo vay moi bang video lookbook.", "fashion"),
        ("Chu quan pho gioi thieu mon moi va khong gian nha hang am cung.", "restaurant_hospitality"),
    ]
    for idea, expected_niche in cases:
        data = _decision(
            user_idea=idea,
            target_market="vn",
            duration_hint_s=60,
            reference_counts={"images": 1, "videos": 0, "audios": 0},
        )
        got = data["decision"]["niche"]
        _assert(got == expected_niche, f"expected {expected_niche} for Vietnamese idea, got {got}")


def test_niche_resolution_exposes_scores_and_hits_for_mixed_briefs() -> None:
    data = _decision(
        user_idea="Creator review app AI quan ly don hang cho shop online, co dashboard va ket qua tang doanh thu.",
        target_market="vn",
        duration_hint_s=60,
        reference_counts={"images": 2, "videos": 1, "audios": 1},
    )
    resolution = data["input_summary"]["niche_resolution"]
    _assert(resolution["selected_niche"] == "app_saas", f"expected app_saas resolution, got {resolution}")
    _assert(resolution["source"] == "keyword_score", "niche resolution should explain keyword score source")
    _assert(resolution["confidence"] >= 0.82, "specific app/SaaS mixed brief should have useful confidence")
    top = resolution["scores"][0]
    _assert(top["niche"] == "app_saas", f"top niche score should be app_saas: {top}")
    _assert("shop online" in top["specific_hits"], "specific hits should expose shop online signal")
    _assert("dashboard" in top["specific_hits"], "specific hits should expose dashboard signal")


def test_ambiguous_niche_resolution_blocks_autoroute_until_review() -> None:
    data = _decision(
        user_idea="Lam video viral cho thuong hieu moi, that cuon hut va chuyen nghiep.",
        target_market="vn",
        duration_hint_s=30,
        reference_counts={"images": 0, "videos": 0, "audios": 0},
    )
    decision = data["decision"]
    resolution = data["input_summary"]["niche_resolution"]
    scorecard = data["route_quality_scorecard"]
    _assert(resolution["confidence"] < 0.75, f"vague brief should have low niche confidence: {resolution}")
    _assert(decision["niche_resolution_review_required"] is True, "ambiguous niche should require review")
    _assert("niche_resolution_ambiguous" in scorecard["blocking_reasons"], "scorecard should block ambiguous niche")
    _assert(scorecard["auto_route_allowed"] is False, "ambiguous niche should not auto-route without review")
    _assert(
        any("niche resolution" in gate for gate in data["qa_gates"]),
        "QA gates should expose niche clarification requirement",
    )
    _assert(resolution["clarifying_questions"], "ambiguous niche should return clarifying questions")
    _assert("primary niche" in resolution["suggested_brief_signals"], "ambiguous niche should return suggested brief signals")
    _assert(
        "First 3s" in resolution["suggested_brief_template"],
        "ambiguous niche should return a fillable brief template",
    )


def test_autonomous_generate_rejects_ambiguous_niche_before_chain() -> None:
    async def _run() -> None:
        try:
            await autonomous_generate(
                AutonomousGenerateRequest(
                    user_idea="Lam video viral cho thuong hieu moi, that cuon hut va chuyen nghiep.",
                    target_market="vn",
                    target_platform="tiktok",
                    duration_hint_s=30,
                    user_model="auto",
                    resolution="720p",
                ),
                idempotency_key=None,
            )
        except Exception as e:
            status_code = getattr(e, "status_code", None)
            detail = getattr(e, "detail", {})
            _assert(status_code == 422, f"ambiguous autonomous render should return 422, got {status_code}")
            _assert(
                isinstance(detail, dict) and detail.get("code") == "niche_resolution_requires_clarification",
                f"unexpected ambiguous render detail: {detail}",
            )
            return
        raise AssertionError("ambiguous autonomous render should be rejected before chain")

    asyncio.run(_run())


def test_autonomous_generate_request_accepts_approved_plan_metadata() -> None:
    render_source = "User idea:\nClear beauty serum review.\n\nApproved render plan:\nScript beats included."
    source_hash = hashlib.sha256(render_source.encode("utf-8")).hexdigest()
    request = AutonomousGenerateRequest(
        user_idea=render_source,
        target_market="vn",
        target_platform="tiktok",
        duration_hint_s=30,
        user_model="auto",
        resolution="720p",
        approved_plan_id="plan_1234567890abcdef",
        approved_plan_source_hash=source_hash,
        approved_plan_source_length=len(render_source),
    )
    payload = request.model_dump()
    _assert(payload["approved_plan_id"] == "plan_1234567890abcdef", "approved plan id should be accepted")
    _assert(payload["approved_plan_source_hash"] == source_hash, "approved plan hash should be accepted")
    _assert(payload["approved_plan_source_length"] == len(render_source), "approved plan source length should be accepted")
    meta = _approved_plan_meta_from_request(request)
    _assert(meta["included_in_render_source"] is True, "matching approved plan hash should be render-included")


def test_autonomous_generate_rejects_stale_approved_plan_metadata() -> None:
    request = AutonomousGenerateRequest(
        user_idea="User idea:\nEdited after approval.",
        target_market="vn",
        target_platform="tiktok",
        duration_hint_s=30,
        user_model="auto",
        resolution="720p",
        approved_plan_id="plan_stale",
        approved_plan_source_hash="0" * 64,
        approved_plan_source_length=12,
    )
    try:
        _approved_plan_meta_from_request(request)
    except Exception as e:
        _assert(getattr(e, "status_code", None) == 422, "stale approved plan metadata should return 422")
        detail = getattr(e, "detail", {})
        _assert(
            isinstance(detail, dict) and detail.get("code") == "approved_plan_source_hash_mismatch",
            f"unexpected stale plan detail: {detail}",
        )
        return
    raise AssertionError("stale approved plan metadata should be rejected")


def test_clear_niche_resolution_does_not_ask_for_clarification() -> None:
    data = _decision(
        user_idea="Creator review app AI quan ly don hang cho shop online, co dashboard va ket qua tang doanh thu.",
        target_market="vn",
        duration_hint_s=60,
        reference_counts={"images": 2, "videos": 1, "audios": 1},
    )
    resolution = data["input_summary"]["niche_resolution"]
    _assert(resolution["selected_niche"] == "app_saas", "clear app brief should resolve to app_saas")
    _assert(resolution["confidence"] >= 0.9, "clear app brief should be high confidence")
    _assert(resolution["clarifying_questions"] == [], "clear niche should not ask clarifying questions")
    _assert(resolution["suggested_brief_signals"] == [], "clear niche should not suggest missing brief signals")
    _assert(resolution["suggested_brief_template"] == "", "clear niche should not show a brief template")


def test_auto_market_infers_vietnamese_language_and_playbook() -> None:
    data = _decision(
        user_idea="Một creator Việt review son môi cao cấp trong quán cafe Sài Gòn, quay cận texture và có voiceover ngắn.",
        target_market="auto",
        target_platform="tiktok",
        duration_hint_s=300,
        reference_counts={"images": 2, "videos": 0, "audios": 1},
    )
    decision = data["decision"]
    _assert(decision["target_market"] == "vn", f"auto market should infer vn, got {decision['target_market']}")
    _assert(data["input_summary"]["requested_target_market"] == "auto", "requested market should remain auditable")
    _assert(data["market_playbook"]["primary_language"] == "Vietnamese", "VN auto inference should use Vietnamese playbook")
    _assert(
        decision["dialogue_route_policy"]["target_language"] == "Vietnamese",
        "auto VN dialogue should speak Vietnamese",
    )


def test_vietnamese_spoken_language_tokens_enable_dialogue_lane() -> None:
    data = _decision(
        user_idea=(
            "Video review m\u00e1y xay c\u1ea7m tay, "
            "n\u00f3i ti\u1ebfng Vi\u1ec7t t\u1ef1 nhi\u00ean."
        ),
        target_market="auto",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 1, "videos": 0, "audios": 1},
    )
    decision = data["decision"]
    _assert(decision["target_market"] == "vn", f"spoken Vietnamese brief should infer VN, got {decision['target_market']}")
    _assert(decision["dialogue_required"] is True, "noi tieng Viet / natural speech should enable dialogue lane")
    _assert(
        decision["dialogue_route_policy"]["target_language"] == "Vietnamese",
        "spoken Vietnamese dialogue route should target Vietnamese",
    )


def test_vietnamese_diacritic_market_brief_routes_to_vn_dialogue() -> None:
    data = _decision(
        user_idea=(
            "T\u1ea1o video 60 gi\u00e2y review son d\u01b0\u1ee1ng cho th\u1ecb tr\u01b0\u1eddng "
            "Vi\u1ec7t Nam, c\u00f3 ng\u01b0\u1eddi n\u00f3i ti\u1ebfng Vi\u1ec7t t\u1ef1 nhi\u00ean, "
            "hook m\u1ea1nh 3 gi\u00e2y \u0111\u1ea7u v\u00e0 caption viral."
        ),
        target_market="auto",
        target_platform="tiktok",
        duration_hint_s=60,
        reference_counts={"images": 1, "videos": 0, "audios": 1},
    )
    decision = data["decision"]
    _assert(decision["target_market"] == "vn", f"diacritic Vietnamese brief should infer VN, got {decision['target_market']}")
    _assert(decision["dialogue_required"] is True, "Vietnamese natural speech with diacritics should enable dialogue lane")
    _assert(data["market_playbook"]["primary_language"] == "Vietnamese", "VN market should use Vietnamese playbook")


def test_auto_market_infers_japanese_and_korean_scripts() -> None:
    jp = _decision(
        user_idea="東京の小さなカフェで新しい抹茶スイーツを紹介する短い動画。",
        target_market="auto",
        duration_hint_s=30,
        reference_counts={"images": 1},
    )
    kr = _decision(
        user_idea="서울의 뷰티 크리에이터가 새로운 쿠션 파운데이션을 테스트하는 영상.",
        target_market="auto",
        duration_hint_s=30,
        reference_counts={"images": 1},
    )
    _assert(jp["decision"]["target_market"] == "jp", f"expected jp, got {jp['decision']['target_market']}")
    _assert(kr["decision"]["target_market"] == "kr", f"expected kr, got {kr['decision']['target_market']}")


def test_responsible_content_gate_blocks_unverified_likeness_and_ip() -> None:
    gate = build_responsible_content_gate(
        user_idea="Create a fake endorsement ad where Taylor Swift says this investment app is safe, clone her voice.",
        target_market="us",
        has_dialogue=True,
        reference_counts={"audios": 1},
    )
    _assert(gate["status"] == "fail", "public figure voice clone endorsement should fail")
    _assert(gate["render_allowed"] is False, "high-risk likeness prompt should block render")
    _assert("unverified_voice_or_likeness_clone" in gate["hard_blockers"], "voice clone blocker missing")
    ip_gate = build_responsible_content_gate(
        user_idea="Make a product ad with Pikachu and Spider-Man using my brand.",
        target_market="global",
    )
    _assert(ip_gate["render_allowed"] is False, "known IP commercial prompt should block render")
    soft = build_responsible_content_gate(
        user_idea="Original cafe scene with cinematic energy inspired by Pixar warmth, no known characters.",
        target_market="global",
    )
    _assert(soft["status"] == "warn", "soft style reference should require review, not hard fail")


def test_production_decision_exposes_responsible_content_gate() -> None:
    data = _decision(
        user_idea="Create a fake endorsement ad where Taylor Swift says this investment app is safe, clone her voice.",
        target_market="us",
        duration_hint_s=30,
        reference_counts={"audios": 1},
    )
    gate = data["responsible_content_gate"]
    _assert(gate["render_allowed"] is False, "production decision should expose responsible render block")
    _assert(data["decision"]["render_blocked_by_responsible_gate"] is True, "decision should mark responsible block")
    _assert(data["decision"]["responsible_review_required"] is True, "decision should mark responsible review")


def test_planner_guard_aligns_llm_niche_with_deterministic_preview() -> None:
    decision = _decision(
        user_idea="Một creator Việt review son môi cao cấp trong quán cafe Sài Gòn.",
        target_market="auto",
        target_platform="tiktok",
        duration_hint_s=300,
        reference_counts={"images": 2, "audios": 1},
    )
    planner = PlannerOutput(
        niche="ugc_review",
        primary_emotion="curiosity",
        hook_pattern="action_reveal",
        hook_first_3s="macro lipstick texture swipe on a cafe table",
        mood="warm cafe",
        style_direction="Handheld close-up, soft daylight.",
        suggested_duration_s=30,
        suggested_aspect_ratio="9:16",
        suggested_audio_mode="dialogue_vo",
        director_notes="Creator-style proof.",
    )
    guarded = _apply_planner_decision_guard(planner, deterministic_decision=decision)
    out = guarded["planner"]
    meta = guarded["meta"]
    _assert(out.niche == "beauty", f"planner guard should correct niche to beauty, got {out.niche}")
    _assert(out.suggested_duration_s == 300, "planner guard should align duration with preview contract")
    _assert(meta["applied"] is True, "planner guard should report applied corrections")
    _assert("niche" in meta["corrections"], "planner guard should report niche correction")
    _assert(meta["target_market"] == "vn", "planner guard should carry inferred market")


def test_planner_guard_noops_when_planner_matches_preview() -> None:
    decision = _decision(
        user_idea="A Vietnamese beauty creator tests a premium lipstick in a Saigon cafe.",
        target_market="vn",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 2, "audios": 1},
    )
    planner = PlannerOutput(
        niche="beauty",
        primary_emotion="desire",
        hook_pattern="macro texture surprise",
        hook_first_3s="extreme close-up of lipstick texture",
        mood="polished warm",
        style_direction="Soft macro beauty lighting.",
        suggested_duration_s=30,
        suggested_aspect_ratio="9:16",
        suggested_audio_mode="asmr_macro",
        director_notes="Beauty proof.",
    )
    guarded = _apply_planner_decision_guard(planner, deterministic_decision=decision)
    _assert(guarded["planner"].niche == "beauty", "aligned planner should keep niche")
    _assert(guarded["meta"]["applied"] is False, "aligned planner should not report corrections")


def test_long_form_decision_exposes_scene_blueprint_preview() -> None:
    data = _decision(
        user_idea="Một creator Việt review son môi cao cấp trong quán cafe Sài Gòn, quay cận texture và có voiceover ngắn.",
        target_market="auto",
        target_platform="tiktok",
        duration_hint_s=300,
        reference_counts={"images": 2, "audios": 1},
    )
    preview = data["long_form_scene_preview"]
    scenes = preview["scene_blueprints"]
    _assert(preview["enabled"] is True, "5 minute job should expose long-form scene preview")
    _assert(preview["scene_count"] == data["runtime_structure"]["scene_count"], "scene count should match runtime structure")
    _assert(preview["estimated_seedance_units"] >= 20, "5 minute preview should estimate many Seedance render units")
    _assert(len(scenes) == 5, f"300s short film should expose five scenes, got {len(scenes)}")
    _assert(scenes[0]["scene_id"] == "SC01", "first scene should have stable scene id")
    _assert(scenes[0]["seedance_render_plan"]["target_unit_duration_s"] <= 15, "scene units must honor Seedance 15s cap")
    _assert(scenes[0]["seedance_render_plan"]["target_unit_duration_s"] >= 4, "scene units must honor Seedance 4s floor")
    _assert(scenes[0]["seedance_render_plan"]["estimated_units"] == 5, "60s scene should estimate five ~12s units")
    _assert(
        scenes[1]["seedance_render_plan"]["continuity_mode"] == "previous_scene_final_frame_plus_anchor_refs",
        "later scenes should carry previous scene final frame",
    )
    _assert(scenes[0]["visual_hook"], "scene preview should expose visual hook")
    _assert(scenes[0]["conflict"], "scene preview should expose screenplay conflict")
    _assert(scenes[-1]["handoff_to_next"].startswith("End with a memorable"), "final scene should close with payoff")
    _assert(preview["continuity_contract"], "scene preview should expose continuity contract")


def test_production_decision_ranks_creative_treatments_before_render() -> None:
    data = _decision(
        user_idea="A premium beauty creator tests a luxury lipstick with macro texture and cinematic cafe lighting.",
        target_market="global",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 2, "videos": 1, "audios": 1},
    )
    search = data["creative_treatment_search"]
    candidates = search["candidates"]
    _assert(search["selected_treatment_id"] == "cinematic_premium", f"premium beauty should select cinematic route, got {search['selected_treatment_id']}")
    _assert(len(candidates) >= 4, "creative search should compare multiple director treatments")
    _assert(candidates[0]["score"] >= candidates[-1]["score"], "creative treatments should be ranked")
    _assert(candidates[0]["director_intent"], "selected treatment should expose director intent")
    _assert(candidates[0]["reference_policy"], "selected treatment should expose reference policy")


def test_production_decision_exposes_hero_shot_candidate_policy() -> None:
    data = _decision(
        user_idea="A premium serum TikTok ad with macro texture hook, product close-up, skin result proof, and final payoff.",
        target_market="vn",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 3, "videos": 1, "audios": 1},
        niche_hint="beauty",
    )
    policy = data["hero_shot_candidate_policy"]
    _assert(policy["schema_version"] == "cinejelly.hero_shot_candidate_policy.v1", "hero-shot candidate policy schema missing")
    _assert(policy["enabled"] is True, "strong short-form beauty route should allow candidate selection")
    _assert(policy["mode"] == "auto_candidate_selection", "beauty short should auto-select hero-shot candidates")
    _assert(policy["max_candidates_per_marked_beat"] >= 2, "premium product route should plan multiple candidates")
    beat_ids = {beat["id"] for beat in policy["candidate_beats"]}
    _assert("opening_hook" in beat_ids, "candidate policy should mark opening hook")
    _assert("product_or_hero_closeup" in beat_ids, "candidate policy should mark product/hero close-up")
    _assert("turn_or_payoff" in beat_ids, "candidate policy should mark payoff beat")
    _assert(policy["estimated_extra_seedance_units"] >= 2, "candidate policy should expose extra Seedance unit estimate")
    _assert("reference identity/product fidelity" in policy["selection_criteria"], "candidate policy should include fidelity selection criterion")


def test_long_form_hero_shot_candidates_stay_benchmark_gated() -> None:
    data = _decision(
        user_idea="Phim ngắn 5 phút có thoại tiếng Việt về bí mật gia đình, nhân vật chính, twist cuối và cảm xúc mạnh.",
        target_market="vn",
        target_platform="youtube_long",
        duration_hint_s=300,
        reference_counts={"images": 4, "videos": 1, "audios": 1, "pinned_assets": 1},
        niche_hint="drama",
        speaker_count=2,
    )
    policy = data["hero_shot_candidate_policy"]
    _assert(policy["enabled"] is False, "long-form candidate selection should stay benchmark gated")
    _assert(policy["mode"] == "benchmark_graph_keyframes", "5m drama should use benchmark graph keyframe policy")
    beat_ids = {beat["id"] for beat in policy["candidate_beats"]}
    _assert("character_reveal" in beat_ids, "long-form drama should mark character reveal")
    _assert("turn_or_payoff" in beat_ids, "long-form drama should mark twist/payoff")
    _assert("dialogue_closeup" in beat_ids, "dialogue drama should mark dialogue close-up")
    _assert("long_form" in policy["budget_policy"], "policy should expose long-form budget guidance")


def test_long_form_error_recycling_policy_maps_failures_to_memory() -> None:
    data = _decision(
        user_idea="Phim ngắn 5 phút có thoại tiếng Việt về bí mật gia đình, nhân vật chính, twist cuối và cảm xúc mạnh.",
        target_market="vn",
        target_platform="youtube_long",
        duration_hint_s=300,
        reference_counts={"images": 4, "videos": 1, "audios": 1, "pinned_assets": 1},
        niche_hint="drama",
        speaker_count=2,
    )
    policy = data["long_form_error_recycling_policy"]
    _assert(policy["schema_version"] == "cinejelly.long_form_error_recycling_policy.v1", "error recycling schema missing")
    _assert(policy["enabled"] is True, "5m drama should enable error recycling policy")
    _assert(policy["mode"] == "graph_required", "5m drama should require graph error recycling")
    _assert(policy["graph_required"] is True, "5m drama should mark graph required")
    _assert(policy["memory_update_plan"], "error recycling should expose memory update plan")
    first_update = policy["memory_update_plan"][0]
    _assert("accepted_keyframe_url" in first_update["positive_memory_on_pass"], "positive memory should keep accepted keyframes")
    negative_codes = {
        item["failure_code"]
        for item in policy["negative_memory_templates"]
    }
    _assert("identity_drift" in negative_codes, "negative memory should include identity drift")
    _assert("speaker_or_phoneme_mismatch" in negative_codes, "dialogue long-form should include phoneme mismatch memory")
    _assert("negative_prompt_constraints" in policy["graph_node_patch_contract"]["on_failure"], "failure patch should store negative constraints")
    _assert("paid graph benchmarks" in policy["promotion_rule"], "promotion should stay paid-benchmark gated")


def test_long_form_story_prefers_short_drama_treatment() -> None:
    data = _decision(
        user_idea="A five minute short film story with a twist about a creator rebuilding trust after a product failure.",
        target_market="global",
        target_platform="youtube_long",
        duration_hint_s=300,
        reference_counts={"images": 2, "videos": 0, "audios": 1},
        niche_hint="drama",
    )
    search = data["creative_treatment_search"]
    _assert(search["selected_treatment_id"] == "short_drama_arc", f"long-form story should select drama arc, got {search['selected_treatment_id']}")
    selected = search["candidates"][0]
    _assert("long_form_structure_fit" in selected["reasons"], "long-form winner should explain structure fit")
    _assert("Seedance units" in selected["duration_strategy"], "duration strategy should mention unit decomposition")


def test_creative_treatment_search_flags_missing_visual_refs_for_long_form() -> None:
    runtime = {
        "runtime_class": "short_film",
        "target_duration_s": 300,
    }
    search = build_creative_treatment_search(
        user_idea="A documentary style explainer with voiceover about a local founder.",
        niche="documentary",
        target_market="vn",
        target_platform="youtube_long",
        runtime_payload=runtime,
        reference_counts={"images": 0, "videos": 0, "audios": 1, "pinned_assets": 0},
        niche_playbook={"hook_moves": ["cold-open consequence"]},
        market_playbook={"hook_style": "trust-first local proof"},
        has_dialogue=True,
    )
    risks = [risk for item in search["candidates"] for risk in item.get("risks", [])]
    _assert("no_visual_anchor_refs" in risks, "long-form without image refs should surface visual anchor risk")
    _assert(search["selected_treatment_id"] == "documentary_testimonial", "documentary should prefer testimonial treatment")


def test_production_decision_exposes_seedance_reference_allocation() -> None:
    data = _decision(
        user_idea="A premium beauty creator tests a luxury lipstick with macro texture and cinematic cafe lighting.",
        target_market="global",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 3, "videos": 1, "audios": 1},
    )
    allocation = data["seedance_reference_allocation"]
    _assert(allocation["fits_seedance_caps"] is True, "3/1/1 refs should fit Seedance caps")
    roles = [item["role"] for item in allocation["image_role_plan"]]
    _assert(roles[0] == "style_reference", f"cinematic beauty should prioritize style ref, got {roles}")
    _assert("product_hero" in roles, "beauty/product allocation should include product hero")
    _assert(allocation["video_role_plan"][0]["role"] == "camera_motion", "cinematic treatment should use video as camera motion")
    _assert(allocation["per_shot_policy"], "allocation should expose per-shot usage policy")


def test_production_decision_exposes_seedance_segment_inspector() -> None:
    data = _decision(
        user_idea="Creator review app AI quan ly don hang cho shop online, mo dau bang dashboard tang doanh thu.",
        target_market="vn",
        target_platform="tiktok",
        duration_hint_s=45,
        reference_counts={"images": 2, "videos": 1, "audios": 1},
    )
    inspector = data["seedance_segment_inspector"]
    _assert(inspector["schema_version"] == "cinejelly.seedance_segment_inspector.v1", "segment inspector schema missing")
    _assert(inspector["preview_segment_count"] >= 1, "segment inspector should expose preview segments")
    first = inspector["segments"][0]
    _assert(4 <= first["target_duration_s"] <= 15, "segment duration must fit Seedance unit contract")
    _assert(first["prompt_blocks"]["reference_jobs"], "segment should expose explicit reference jobs")
    _assert("one physical action" in first["prompt_blocks"]["constraints"], "segment should expose shot constraints")
    _assert(first["model_route"].startswith("seedance_2_0"), "segment should expose internal Seedance route")


def test_production_decision_exposes_seedance_prompt_formula() -> None:
    data = _decision(
        user_idea="Tao video 5 phut phim ngan ve co gai ban banh mi o Sai Gon phat hien bi mat gia dinh, co thoai tieng Viet.",
        target_market="vn",
        target_platform="tiktok",
        duration_hint_s=300,
        reference_counts={"images": 1, "videos": 1, "audios": 1},
        niche_hint="drama",
        speaker_count=2,
    )
    formula = data["seedance_prompt_formula"]
    _assert(formula["schema_version"] == "cinejelly.seedance_prompt_formula.v1", "prompt formula schema missing")
    _assert(formula["niche"] == "drama", "formula should follow resolved niche")
    _assert(formula["runtime_class"] == "short_film", "formula should follow runtime class")
    _assert("reference_jobs" in formula["formula"], "formula should start from explicit reference jobs")
    _assert("timeline" in formula["formula"], "formula should expose timing contract")
    _assert("camera" in formula["formula"], "formula should expose camera contract")
    _assert("sound" in formula["formula"], "formula should expose sound contract")
    required = formula["reference_job_policy"]["required_reference_jobs"]
    _assert("character_identity_reference" in required, "drama should require character identity reference")
    _assert("location_or_motion_reference" in required, "long drama should require location/motion reference")
    _assert("voice_or_dialogue_audio_reference" in required, "dialogue should require voice/audio reference")
    skeleton = " ".join(formula["unit_prompt_skeleton"])
    _assert("[REFERENCE JOBS]" in skeleton and "[SHOT CONTRACT]" in skeleton, "formula should provide prompt skeleton")


def test_production_decision_exposes_prompt_template_bank_policy() -> None:
    data = _decision(
        user_idea="A premium food creator films a crispy banh mi with macro crunch, steam, sauce pull, and final taste payoff.",
        target_market="vn",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 3, "videos": 1, "audios": 1},
        niche_hint="food",
    )
    policy = data["prompt_template_bank_policy"]
    _assert(policy["schema_version"] == "cinejelly.prompt_template_bank_policy.v1", "prompt template bank schema missing")
    _assert(policy["status"] == "baseline_template_needs_benchmark", "unproven route should keep baseline template benchmark-gated")
    key = policy["template_key"]
    _assert(key["niche"] == "food", "template key should include niche")
    _assert(key["model_key"] in {"seedance_2_0_ref", "seedance_2_0_fast_ref"}, "template key should include Seedance route")
    _assert(len(key["fingerprint"]) == 16, "template fingerprint should be stable and compact")
    _assert("reference_jobs" in policy["source_formula"]["formula_order"], "template should retain formula order")
    _assert(len(policy["template_slots"]) >= 6, "template should expose slots")
    learning = policy["benchmark_learning_plan"]
    _assert(learning["variant_count"] == 3, "template bank should compare variants")
    _assert("accepted-minute cost" in learning["compare_on"], "template learning should compare accepted-minute cost")
    _assert("compiled_prompt_text" in policy["evidence_to_store"], "template evidence should store compiled prompt text")
    _assert(policy["selection_policy"]["current_route_promoted"] is False, "template should not be promoted without evidence")


def test_production_decision_exposes_autonomous_input_upgrade_plan() -> None:
    data = _decision(
        user_idea="Phim ngan 5 phut ve founder Viet ke cau chuyen ung dung AI cho shop online, co voiceover.",
        target_market="vn",
        target_platform="youtube_long",
        duration_hint_s=300,
        reference_counts={"images": 0, "videos": 0, "audios": 0},
        niche_hint="app_saas",
    )
    plan = data["autonomous_input_upgrade_plan"]
    _assert(plan["schema_version"] == "cinejelly.autonomous_input_upgrade_plan.v1", "input upgrade schema missing")
    _assert(plan["renderable_now"] is True, "thin app long-form input should still be renderable unless caps fail")
    _assert(plan["top_tier_ready"] is False, "thin app long-form input must not be top-tier ready")
    _assert(plan["priority_actions"], "input upgrade plan should expose next actions")
    _assert(plan["missing_to_best"]["images"] > 0, "long-form plan should ask for stronger image refs")
    _assert("Renderable now" in plan["user_message"], "plan should provide user-facing guidance")


def test_production_decision_exposes_asset_bible_completion_policy() -> None:
    data = _decision(
        user_idea="Phim ngan 5 phut ve co gai ban banh mi o Sai Gon phat hien bi mat gia dinh, co thoai tieng Viet.",
        target_market="vn",
        target_platform="youtube_long",
        duration_hint_s=300,
        reference_counts={"images": 0, "videos": 0, "audios": 0},
        niche_hint="drama",
        speaker_count=2,
    )
    policy = data["asset_bible_completion_policy"]
    _assert(policy["schema_version"] == "cinejelly.asset_bible_completion_policy.v1", "asset bible policy schema missing")
    _assert(policy["status"] == "long_form_asset_bible_incomplete", "thin 5m drama should have incomplete asset bible")
    _assert("characters" in policy["required_groups"], "long-form drama should require character group")
    _assert("locations" in policy["required_groups"], "long-form drama should require location group")
    _assert("voice_or_dialogue" in policy["required_groups"], "dialogue drama should require voice/dialogue group")
    groups = {row["group"]: row for row in policy["group_status"]}
    _assert(groups["characters"]["status"] == "missing_anchor", "thin drama should miss character visual anchor")
    _assert(groups["locations"]["status"] == "missing_anchor", "thin drama should miss location visual anchor")
    _assert(groups["voice_or_dialogue"]["status"] == "missing_anchor", "thin drama should miss voice anchor")
    _assert(policy["auto_pin_plan"]["generate_missing_anchor_candidates"] is True, "missing anchors should generate pin candidates")
    _assert(policy["render_policy"]["top_tier_claim_allowed"] is False, "asset bible cannot allow top-tier claim without evidence")


def test_conversational_preflight_drafts_plan_before_render() -> None:
    data = build_conversational_preflight(
        user_idea="Video 30s review serum duong da cho TikTok Viet Nam, hook manh, canh dung san pham that.",
        target_market="auto",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 2, "videos": 1, "audios": 0},
    )
    _assert(data["schema_version"] == "cinejelly.conversational_preflight.v1", "conversation preflight schema missing")
    _assert(data["status"] == "ready_for_approval", "clear short brief should wait for approval")
    _assert(data["approval_required"] is True, "preflight should require user approval before render")
    _assert(data["render_ready"] is False, "preflight should not be render-ready before approval")
    _assert(data["creative_plan"]["logline"], "preflight should draft a logline")
    _assert(len(data["script_outline"]) >= 3, "preflight should draft script beats")
    _assert(len(data["storyboard"]) >= 3, "preflight should draft storyboard frames")
    _assert(data["distribution_preview"]["caption_draft"], "preflight should draft a publishing caption")
    _assert(data["distribution_preview"]["hook_first_3s"], "preflight should expose a hook preview")
    _assert(data["distribution_preview"]["hashtags"], "preflight should expose hashtags before render")
    checklist = data["approval_checklist"]
    checklist_keys = {item["key"] for item in checklist}
    _assert("creative_intent" in checklist_keys, "preflight should expose creative intent approval check")
    _assert("script_blueprint" in checklist_keys, "preflight should expose script approval check")
    _assert("storyboard" in checklist_keys, "preflight should expose storyboard approval check")
    _assert("publishing" in checklist_keys, "preflight should expose publishing approval check")
    approved = build_conversational_preflight(
        user_idea=data["approved_brief"],
        target_market="auto",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 2, "videos": 1, "audios": 0},
        approved=True,
    )
    _assert(approved["status"] == "approved_for_render", "approved preflight should unlock render state")
    _assert(approved["render_ready"] is True, "approved clear preflight should be render-ready")


def test_conversational_preflight_infers_vietnamese_market_and_duration_from_chat_brief() -> None:
    data = build_conversational_preflight(
        user_idea=(
            "T\u1ea1o video TikTok 12s cho serum l\u00e0m \u0111\u1eb9p t\u1ea1i Vi\u1ec7t Nam, "
            "m\u1edf \u0111\u1ea7u b\u1eb1ng b\u1eb1ng ch\u1ee9ng hi\u1ec7u qu\u1ea3, phong c\u00e1ch creator "
            "cao c\u1ea5p, c\u00f3 c\u1ea3nh c\u1eadn s\u1ea3n ph\u1ea9m v\u00e0 k\u1ebft th\u00fac b\u1eb1ng CTA nh\u1eb9."
        ),
        target_market="auto",
        target_platform="tiktok",
        duration_hint_s=None,
        reference_counts={"images": 0, "videos": 0, "audios": 0},
    )
    decision = data["production_decision"]["decision"]
    _assert(data["summary"]["market"] == "vn", f"chat preflight should infer VN, got {data['summary']['market']}")
    _assert(data["summary"]["target_duration_s"] == 12, "chat preflight should parse the 12s runtime from the idea")
    _assert(decision["target_market"] == "vn", "production decision should carry inferred VN market")
    _assert(decision["target_duration_s"] == 12, "production decision should carry parsed 12s runtime")
    _assert(data["production_decision"]["market_playbook"]["primary_language"] == "Vietnamese", "VN plan should use Vietnamese market playbook")
    _assert(data["planning_trace"]["vendor_calls_performed"] is False, "chat preflight must remain vendor-free")


def test_conversational_preflight_asks_when_brief_is_too_thin() -> None:
    data = build_conversational_preflight(
        user_idea="make video viral",
        target_market="auto",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 0, "videos": 0, "audios": 0},
    )
    _assert(data["status"] == "needs_user_input", "thin brief should ask a blocking question")
    _assert(data["render_ready"] is False, "thin brief must not unlock render")
    _assert(data["blocking_questions"], "thin brief should explain what is missing")
    _assert(data["suggested_replies"], "thin brief should provide quick replies for the chat UI")
    _assert(data["blocking_questions"][0]["suggested_replies"], "blocking question should carry reply suggestions")


def test_conversational_preflight_keeps_revision_notes_in_approved_brief() -> None:
    data = build_conversational_preflight(
        user_idea="Video 30s review serum duong da cho TikTok Viet Nam, hook manh, canh dung san pham that.",
        target_market="vn",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 2, "videos": 1, "audios": 0},
        revision_notes="Make the hook more emotional and make the final product proof clearer.",
        approved=True,
    )
    _assert(data["status"] == "approved_for_render", "clear revised plan should approve")
    _assert("Revision focus:" in data["approved_brief"], "approved brief should preserve revision notes for render")
    _assert("Approved render plan:" in data["approved_brief"], "approved brief should include the locked render plan")
    _assert("\n\nApproved render plan:" in data["approved_brief"], "approved brief should preserve section breaks")
    _assert("Scene map:" in data["approved_brief"], "approved brief should include compact scene map")
    _assert("Publishing preview:" in data["approved_brief"], "approved brief should lock the approved publishing preview")
    _assert("Caption:" in data["approved_brief"], "approved brief should include approved caption draft")
    _assert("Hashtags:" in data["approved_brief"], "approved brief should include approved hashtags")
    _assert("Script beats:" in data["approved_brief"], "approved brief should include script beats")
    _assert("Storyboard frames:" in data["approved_brief"], "approved brief should include storyboard frames")
    _assert("Render checks:" in data["approved_brief"], "approved brief should include locked pre-render checks")
    _assert("Creative intent:" in data["approved_brief"], "approved brief should include creative intent check")
    _assert("Execution route:" in data["approved_brief"], "approved brief should include execution route check")
    _assert(len(data["approved_brief"]) <= 2000, "approved brief must fit autonomous render request limit")
    _assert(data["approved_plan"]["id"].startswith("plan_"), "approved plan should expose a stable plan id")
    _assert(data["approved_plan"]["source_length"] == len(data["approved_brief"]), "approved plan length should match render source")
    _assert(data["approved_plan"]["included_in_render_source"] is True, "approved plan should mark render source inclusion")
    _assert(data["creative_plan"]["revision_directive"], "creative plan should expose revision directive")


def test_conversational_preflight_uses_structured_chat_history() -> None:
    data = build_conversational_preflight(
        user_idea="Create a product video.",
        target_market="vn",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 1, "videos": 0, "audios": 0},
        conversation_messages=[
            {"role": "user", "text": "The product is a cooling sunscreen for commuters in Ho Chi Minh City."},
            {"role": "assistant", "text": "I will build a short proof-driven plan."},
            {"role": "user", "text": "Make the hook about heat, sweat, and a visible skin finish payoff."},
        ],
    )
    context = data["conversation_context"]
    _assert(context["user_turn_count"] == 2, "chat context should count user turns")
    _assert(context["assistant_turn_count"] == 1, "chat context should preserve assistant turns")
    _assert("visible skin finish" in data["approved_brief"], "approved brief should include useful user chat context")
    _assert("visible skin finish" in context["latest_user_turn"], "latest user turn should be exposed")


def test_conversational_preflight_keeps_revision_chat_out_of_base_idea() -> None:
    data = build_conversational_preflight(
        user_idea="Video 30s review serum duong da cho TikTok Viet Nam, hook manh, canh dung san pham that.",
        target_market="vn",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 2, "videos": 1, "audios": 0},
        revision_notes="Make the hook more emotional and add a clearer final product proof.",
        approved=True,
        conversation_messages=[
            {
                "role": "user",
                "text": "Video 30s review serum duong da cho TikTok Viet Nam, hook manh, canh dung san pham that.",
                "intent": "idea",
            },
            {"role": "assistant", "text": "I drafted a short plan: Proof-first UGC."},
            {
                "role": "user",
                "text": "Make the hook more emotional and add a clearer final product proof.",
                "intent": "revision",
            },
        ],
    )
    base_section = data["approved_brief"].split("\n\n", 1)[0]
    _assert("Make the hook more emotional" not in base_section, "revision chat should not pollute the base user idea")
    _assert("Revision focus:" in data["approved_brief"], "revision chat should still be represented as revision focus")
    _assert(data["conversation_context"]["latest_user_turn"].startswith("Make the hook"), "chat context should preserve latest revision turn")


def test_conversational_preflight_accepts_chat_answers_for_long_form_story_spine() -> None:
    data = build_conversational_preflight(
        user_idea="Make a 5 minute video.",
        target_market="vn",
        target_platform="youtube_long",
        duration_hint_s=300,
        reference_counts={"images": 2, "videos": 1, "audios": 1},
        approved=True,
        conversation_messages=[
            {
                "role": "assistant",
                "text": "For long-form I need the main character, conflict, and transformation.",
            },
            {
                "role": "user",
                "text": (
                    "Treat this as an app SaaS launch film, not fictional drama. Main character is a "
                    "Vietnamese founder whose shop is failing; conflict is proving an AI ordering app "
                    "can save one chaotic launch day; transformation is from panic to a confident "
                    "revenue reveal."
                ),
            },
        ],
    )
    question_ids = {item["id"] for item in data["blocking_questions"]}
    _assert(data["status"] == "needs_user_input", "long-form should stay blocked until graph execution is ready")
    _assert(data["render_ready"] is False, "long-form graph blocker must not unlock render")
    _assert("long_form_story_missing" not in question_ids, "chat answer should resolve the long-form story blocker")
    _assert("long_form_execution_blocked" in question_ids, "long-form should expose graph execution blocker")
    _assert(data["summary"]["niche"] == "app_saas", "explicit chat answer should resolve app SaaS niche")
    _assert("Vietnamese founder" in data["approved_brief"], "approved brief should carry the chat story spine")
    _assert(data["approved_plan"]["included_in_render_source"] is False, "blocked long-form plan should not be locked into render source")


def test_conversational_preflight_blocks_long_form_missing_references() -> None:
    data = build_conversational_preflight(
        user_idea=(
            "Make a 5 minute short drama about a Vietnamese founder whose cafe is failing, "
            "conflict is proving one AI app can save launch day, ending is revenue reveal."
        ),
        target_market="vn",
        target_platform="youtube_long",
        duration_hint_s=300,
        reference_counts={"images": 0, "videos": 0, "audios": 0},
        approved=True,
    )
    question_ids = {item["id"] for item in data["blocking_questions"]}
    _assert(data["status"] == "needs_user_input", "long-form without refs should ask before approval")
    _assert(data["render_ready"] is False, "long-form without refs must not unlock render")
    _assert("reference_minimum_missing" in question_ids, "missing long-form refs should be a blocking question")
    _assert(data["suggested_replies"], "missing long-form refs should provide quick replies")


def test_conversational_preflight_unlocks_long_form_when_graph_flag_and_refs_ready() -> None:
    old = os.environ.get("CINEJELLY_ENABLE_GRAPH_LONG_FORM")
    os.environ["CINEJELLY_ENABLE_GRAPH_LONG_FORM"] = "1"
    try:
        data = build_conversational_preflight(
            user_idea=(
                "Make a 5 minute short drama about a Vietnamese founder whose cafe is failing, "
                "conflict is proving one AI app can save launch day, ending is revenue reveal."
            ),
            target_market="vn",
            target_platform="youtube_long",
            duration_hint_s=300,
            reference_counts={"images": 2, "videos": 1, "audios": 0},
            approved=True,
        )
    finally:
        if old is None:
            os.environ.pop("CINEJELLY_ENABLE_GRAPH_LONG_FORM", None)
        else:
            os.environ["CINEJELLY_ENABLE_GRAPH_LONG_FORM"] = old

    checks = {item["key"]: item for item in data["approval_checklist"]}
    _assert(data["status"] == "approved_for_render", "graph-enabled long-form with refs should unlock approval")
    _assert(data["render_ready"] is True, "graph-enabled long-form should be render-ready after approval")
    _assert(checks["execution_route"]["status"] == "ready", "graph-enabled long-form route should be ready")
    _assert("Long-form production route is ready" in checks["execution_route"]["detail"], "execution detail should explain long-form route")


def test_conversational_preflight_user_surface_hides_internal_execution_terms() -> None:
    data = build_conversational_preflight(
        user_idea=(
            "Make a 5 minute short drama about a Vietnamese founder whose cafe is failing, "
            "conflict is proving one AI app can save launch day, ending is revenue reveal."
        ),
        target_market="vn",
        target_platform="youtube_long",
        duration_hint_s=300,
        reference_counts={"images": 0, "videos": 0, "audios": 0},
    )
    visible_text = " ".join([
        str(data.get("assistant_message") or ""),
        " ".join(str(item.get("question") or "") + " " + str(item.get("why") or "") for item in data["blocking_questions"]),
        " ".join(str(reply) for reply in data["suggested_replies"]),
        " ".join(str(item.get("label") or "") + " " + str(item.get("detail") or "") for item in data["approval_checklist"]),
    ]).lower()
    for internal in ("graph executor", "production_graph", "production graph", "scene_memory_pack", "cinejelly_enable_graph_long_form"):
        _assert(internal not in visible_text, f"user-facing preflight should hide internal term: {internal}")


def test_conversational_preflight_suggests_long_form_story_reply_templates() -> None:
    data = build_conversational_preflight(
        user_idea="Make a 5 minute video about a launch.",
        target_market="vn",
        target_platform="youtube_long",
        duration_hint_s=300,
        reference_counts={"images": 1, "videos": 0, "audios": 0},
    )
    _assert(data["status"] == "needs_user_input", "thin long-form brief should ask for story spine")
    replies = " ".join(data["suggested_replies"])
    _assert("Main character" in replies and "conflict" in replies, "long-form quick replies should ask for story spine")


def test_production_decision_exposes_niche_execution_rubric() -> None:
    data = _decision(
        user_idea="A premium food creator films a crispy banh mi with macro crunch, steam, sauce pull, and final taste payoff.",
        target_market="vn",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 2, "videos": 1, "audios": 1},
    )
    rubric = data["niche_execution_rubric"]
    _assert(rubric["niche"] == data["decision"]["niche"], "rubric should follow resolved production niche")
    _assert(rubric["required_hook_moves"], "rubric should expose niche hook moves")
    _assert(rubric["required_beat_flow"], "rubric should expose niche beat flow")
    _assert(rubric["camera_grammar"], "rubric should expose niche camera grammar")
    _assert(rubric["quality_bar"], "rubric should expose niche quality bar")


def test_production_decision_exposes_niche_runtime_director_contract() -> None:
    data = _decision(
        user_idea="A five minute Vietnamese short drama about a founder proving a product promise through a cafe test and final twist.",
        target_market="vn",
        target_platform="youtube_long",
        duration_hint_s=300,
        reference_counts={"images": 2, "videos": 1, "audios": 1},
        niche_hint="drama",
    )
    contract = data["niche_runtime_director"]
    _assert(contract["schema_version"] == "cinejelly.niche_runtime_director.v1", "runtime director contract schema should be exposed")
    _assert(contract["runtime_class"] == "short_film", "5 minute job should be a short_film contract")
    _assert(contract["director_mode"] == "screenplay_scene_graph_director", "short film should use screenplay scene graph mode")
    _assert(contract["seedance_unit_doctrine"]["estimated_units"] >= 20, "5 minute film should decompose into many Seedance units")
    _assert(contract["seedance_unit_doctrine"]["single_call_allowed"] is False, "long form must not use one Seedance call")
    _assert(contract["scene_architecture"]["long_form_method"] == "screenplay_scene_graph_chunks_shots_qa_assembly", "long-form method should be explicit")


def test_production_decision_exposes_niche_production_recipe() -> None:
    data = _decision(
        user_idea="A Vietnamese beauty creator proves a lipstick stays clean through a cafe drink test.",
        target_market="vn",
        duration_hint_s=30,
        reference_counts={"images": 2, "videos": 1, "audios": 1},
    )
    recipe = data["niche_production_recipe"]
    _assert(recipe["schema_version"] == "cinejelly.niche_production_recipe.v1", "recipe schema missing")
    _assert(recipe["niche"] == "beauty", "recipe should follow resolved niche")
    _assert("product geometry" in recipe["seedance_prompt_recipe"]["must_include"], "beauty/product recipe should lock product geometry")
    _assert(recipe["reference_recipe"]["best_quality_refs"]["images"] >= 3, "premium product recipe should ask for multiple image refs")


def test_niche_production_recipe_scales_long_form_to_graph_units() -> None:
    runtime = _valid_long_form_runtime_structure()
    recipe = build_niche_production_recipe(
        niche="drama",
        runtime_payload=runtime,
        target_market="vn",
        target_platform="youtube_long",
        niche_playbook={
            "hook_moves": ["emotion close-up"],
            "camera": ["ECU eyes/hands", "OTS confrontation"],
            "audio": "low tension bed",
        },
        reference_counts={"images": 2, "videos": 1, "audios": 1},
        has_dialogue=True,
    )
    duration = recipe["duration_recipe"]
    prompt = recipe["seedance_prompt_recipe"]
    _assert(duration["estimated_seedance_units"] >= 25, "5 minute recipe should split into many Seedance units")
    _assert(duration["rule"].startswith("screenplay -> scenes"), "long-form recipe should require graph decomposition")
    _assert("handoff image" in prompt["must_include"], "long-form prompt recipe should require handoff images")


def test_production_decision_exposes_route_quality_scorecard() -> None:
    data = _decision(
        user_idea="A premium beauty creator tests a lipstick with macro texture and final mirror reveal.",
        target_market="vn",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 3, "videos": 1, "audios": 1},
    )
    scorecard = data["route_quality_scorecard"]
    _assert(scorecard["schema_version"] == "cinejelly.route_quality_scorecard.v1", "route scorecard should be exposed")
    _assert(scorecard["route_key"]["niche"] == data["decision"]["niche"], "route scorecard should follow resolved niche")
    _assert(scorecard["auto_route_allowed"] is True, "high-readiness short-form should allow autonomous route")
    _assert(scorecard["top_tier_claim_allowed"] is False, "route must not claim top-tier without promoted real evidence")
    _assert("route_not_promoted_by_benchmark_policy" in scorecard["blocking_reasons"], "missing real evidence should block premium claim")
    _assert(scorecard["next_benchmark_batch"], "scorecard should prescribe benchmark batch")


def test_production_decision_exposes_cinematic_grammar_contract() -> None:
    data = _decision(
        user_idea="A street food vendor makes crispy banh mi with crunch, steam, sauce pull, and a first bite payoff.",
        target_market="vn",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 2, "videos": 1, "audios": 1},
    )
    grammar = data["cinematic_grammar"]
    _assert(grammar["schema_version"] == "cinejelly.cinematic_grammar.v1", "cinematic grammar schema should be exposed")
    _assert(grammar["story_archetype"]["name"] == "texture_ritual_payoff", "food should use sensory story archetype")
    roles = [item["role"] for item in grammar["shot_palette"]]
    _assert("sensory_hook" in roles and "payoff_close" in roles, "food grammar should expose sensory shot roles")
    _assert(grammar["prompt_directives"], "grammar should expose prompt directives")
    _assert(any("tactile" in item for item in grammar["transition_logic"]), "sensory transition logic should be tactile")


def test_cinematic_grammar_contract_long_form_adds_scene_bridge() -> None:
    grammar = build_cinematic_grammar_contract(
        niche="drama",
        runtime_payload={"runtime_class": "short_film", "target_duration_s": 300},
        target_market="vn",
        creative_treatment={"treatment_id": "short_drama_arc"},
    )
    roles = [item["role"] for item in grammar["shot_palette"]]
    _assert(grammar["story_archetype"]["name"] == "conflict_reveal_aftertaste", "drama should use narrative archetype")
    _assert("scene_bridge" in roles, "long-form cinematic grammar must include scene bridge shot role")
    _assert(any("handoff" in item for item in grammar["transition_logic"]), "long-form transitions should require handoff image")
    _assert(any("scene" in question.lower() for question in grammar["qa_questions"]), "long-form QA should ask scene-level questions")


def test_niche_runtime_director_flags_long_form_without_visual_anchor() -> None:
    runtime = {
        "runtime_class": "episode",
        "target_duration_s": 900,
        "scene_count": 10,
        "chunk_count": 15,
        "act_count": 5,
        "target_scene_duration_s": 75,
        "target_chunk_duration_s": 60,
    }
    contract = build_niche_runtime_director_contract(
        niche="drama",
        runtime_payload=runtime,
        target_market="vn",
        target_platform="youtube_long",
        has_dialogue=True,
        reference_counts={"images": 0, "videos": 0, "audios": 0},
    )
    _assert(contract["director_mode"] == "episode_showrunner_graph_director", "episode should use showrunner graph mode")
    _assert("visual_anchor" in contract["reference_contract"]["missing_for_best_quality"], "long drama should require visual anchors")
    _assert("voice_or_dialogue_audio_reference" in contract["reference_contract"]["missing_for_best_quality"], "dialogue episode should require audio reference")
    _assert("long_form_without_visual_anchor" in contract["risk_register"], "risk register should flag missing anchors")
    _assert(any("lip-sync" in item for item in contract["qa_focus"]), "dialogue QA should include lip-sync")


def test_seedance_reference_allocation_warns_long_form_without_visual_anchor() -> None:
    allocation = build_seedance_reference_allocation(
        niche="drama",
        runtime_payload={"runtime_class": "short_film", "target_duration_s": 300},
        reference_counts={"images": 0, "videos": 1, "audios": 1, "pinned_assets": 0},
        has_dialogue=True,
        creative_treatment={"treatment_id": "short_drama_arc"},
    )
    _assert("long_form_without_visual_identity_anchor" in allocation["warnings"], "long-form should warn without image/pinned anchor")
    _assert(allocation["long_form_handoff_policy"]["enabled"] is True, "long-form handoff policy should be enabled")
    shot_types = [item["shot_type"] for item in allocation["per_shot_policy"]]
    _assert("scene_handoff" in shot_types, "long-form allocation should include scene handoff policy")
    _assert("dialogue_insert" in shot_types, "dialogue allocation should include dialogue insert policy")
    sufficiency = allocation["reference_sufficiency"]
    _assert(sufficiency["status"] == "warn", "missing long-form visual anchor should warn")
    _assert(sufficiency["top_tier_ready"] is False, "thin references must not be top-tier ready")
    _assert("visual_anchor_missing" in sufficiency["missing_for_top_tier"], "sufficiency should explain visual anchor gap")


def test_creative_treatment_is_injected_into_director_plan() -> None:
    search = _decision(
        user_idea="A premium beauty creator tests a luxury lipstick with macro texture and cinematic cafe lighting.",
        target_market="global",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 2, "videos": 1, "audios": 1},
    )["creative_treatment_search"]
    selected_id = search["selected_treatment_id"]
    planner = PlannerOutput(
        niche="beauty",
        primary_emotion="desire",
        hook_pattern="macro texture surprise",
        hook_first_3s="macro lipstick texture glides across skin",
        mood="premium warm cafe",
        style_direction="Soft cinematic beauty lighting.",
        suggested_duration_s=30,
        suggested_aspect_ratio="9:16",
        suggested_audio_mode="asmr_macro",
        director_notes="Beauty proof with product texture.",
    )
    planner = _apply_creative_treatment_to_planner(
        planner,
        selected_creative_treatment=search["candidates"][0],
    )
    storyboard = StoryboardOutput(
        panels=[
            StoryboardPanel(
                index=0,
                duration_s=8,
                purpose="hook",
                visual_description="Vietnamese beauty creator holds the lipstick near a cafe window. She swipes the texture on her wrist.",
                suggested_camera="ECU push-in",
                suggested_lighting="soft warm window light",
                emotion_beat="curiosity",
                chunk_id=0,
            ),
            StoryboardPanel(
                index=1,
                duration_s=8,
                purpose="proof",
                visual_description="Macro product texture catches the light. The creator reacts naturally.",
                suggested_camera="CU handheld",
                suggested_lighting="soft warm window light",
                emotion_beat="desire",
                chunk_id=0,
            ),
        ],
        total_duration_s=16,
        n_chunks=1,
        chunk_duration_s=[16],
    )
    director = DirectorOutput(
        shots=[
            DirectorShotSpec(
                shot_id="S1",
                index=0,
                duration_s=8,
                purpose="hook",
                subject="Vietnamese beauty creator with lipstick",
                action="swipes lipstick texture on wrist",
                camera_shot="ECU",
                camera_movement="push-in",
                lighting_override="soft warm window light",
                emotion_beat="curiosity",
            ),
            DirectorShotSpec(
                shot_id="S2",
                index=1,
                duration_s=8,
                purpose="proof",
                subject="macro lipstick texture",
                action="catches light as creator reacts",
                camera_shot="CU",
                camera_movement="handheld",
                lighting_override="soft warm window light",
                emotion_beat="desire",
                previous_shot_id="S1",
            ),
        ],
        total_duration_s=16,
        render_strategy="per_shot_chain",
        user_model="seedance_2_0",
        n_chunks=1,
        chunk_shot_ids=[["S1", "S2"]],
        reasoning="test",
    )
    role_out = RoleTaggerOutput(
        tagged=[
            TaggedReference(
                modality="image",
                index=0,
                url="https://example.com/creator.png",
                role="character_anchor",
                tag="@image_1 as primary character",
                confidence=0.9,
            ),
            TaggedReference(
                modality="image",
                index=1,
                url="https://example.com/lipstick.png",
                role="product_hero",
                tag="@image_2 as product",
                confidence=0.9,
            ),
        ],
        prompt_tag_suffix="Use references: @image_1 as primary character, @image_2 as product.",
    )
    plan = _build_director_plan(
        req=type("Req", (), {
            "user_idea": "A premium beauty creator tests a luxury lipstick with macro texture and cinematic cafe lighting.",
            "reference_image_urls": ["https://example.com/creator.png", "https://example.com/lipstick.png"],
            "reference_video_urls": ["https://example.com/motion.mp4"],
            "reference_audio_urls": ["https://example.com/beat.wav"],
            "pinned_asset_ids": [],
            "pinned_assets": [],
            "target_platform": "tiktok",
            "target_market": "global",
        })(),
        planner=planner,
        storyboard=storyboard,
        director=director,
        role_tagger=role_out,
        runtime_structure={"runtime_class": "short", "target_duration_s": 30},
        target_market="global",
        creative_treatment_search=search,
    )
    meta = plan.continuity_bible.storytelling_meta or {}
    selected = meta["selected_creative_treatment"]
    _assert(selected["treatment_id"] == selected_id, "DirectorPlan should persist selected creative treatment")
    _assert("creative_treatment_search" in meta, "DirectorPlan should persist creative treatment search")
    _assert("seedance_reference_allocation" in meta, "DirectorPlan should persist Seedance reference allocation")
    _assert(meta["seedance_reference_allocation"]["fits_seedance_caps"] is True, "DirectorPlan allocation should fit caps")
    _assert(meta["scene_memory_pack"]["scene_count"] == 1, "DirectorPlan should persist a scene memory pack")
    _assert(meta["dynamic_keyframe_memory"]["schema_version"] == "cinejelly.dynamic_keyframe_memory.v1", "DirectorPlan should persist dynamic keyframe memory contract")
    _assert(
        meta["production_graph"]["nodes"][1]["payload"]["scene_memory"]["scene_id"] == "SC01",
        "production graph scene nodes should carry scene memory",
    )
    must_have = " ".join(plan.continuity_bible.constraints.must_have)
    _assert("Creative treatment" in must_have, "creative treatment should become a production constraint")
    _assert("selected treatment" in plan.shot_list[0].dynamic_description, "shot prompt description should include treatment directive")


def test_short_decision_disables_scene_blueprint_preview() -> None:
    data = _decision(
        user_idea="A beauty creator tests a premium lipstick texture.",
        target_market="global",
        duration_hint_s=30,
        reference_counts={"images": 1},
    )
    preview = data["long_form_scene_preview"]
    _assert(preview["enabled"] is False, "30s short should not expose long-form scene preview")
    _assert(preview["scene_blueprints"] == [], "short scene preview should be empty")


def test_phase1_brain_policy_uses_flash_and_qwen_without_pro_by_default() -> None:
    data = _decision(
        user_idea="TikTok VN beauty serum launch with a proof-first hook.",
        target_market="vn",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 2, "videos": 0, "audios": 0},
    )
    policy = data["llm_brain_policy"]
    routes = policy["routes"]
    _assert(policy["vendor_calls_performed"] is False, "brain policy must be vendor-free")
    _assert(policy["paid_video_vendor_calls_allowed"] is False, "brain policy must not allow paid video calls")
    _assert(routes["insight_extraction"]["model"] == "deepseek-ai/deepseek-v4-flash", "analyzer should default to Flash")
    _assert(routes["creative_generation"]["model"] == "deepseek-ai/deepseek-v4-flash", "generator should stay Flash by default")
    _assert(routes["vision_reference_scan"]["model"] == "qwen/qwen3-vl-30b-a3b-instruct", "image refs should route to Qwen3-VL")
    _assert(routes["creative_generation"]["pro_selected"] is False, "Pro must not be selected without approval")


def test_phase1_complex_brief_gates_pro_until_explicit_approval() -> None:
    data = _decision(
        user_idea=(
            "A 5 minute Vietnamese short drama with two characters, family secret, dialogue, "
            "street food stall location, emotional twist, and cinematic ending."
        ),
        target_market="vn",
        target_platform="youtube_long",
        duration_hint_s=300,
        reference_counts={"images": 4, "videos": 1, "audios": 2},
        speaker_count=2,
    )
    policy = data["llm_brain_policy"]
    route = policy["routes"]["creative_generation"]
    _assert(policy["complexity"]["band"] in {"complex", "critical"}, "long drama should be complex or critical")
    _assert(route["pro_candidate"] is True, "complex route should expose Pro as candidate")
    _assert(route["pro_selected"] is False, "Pro must stay locked by default")
    _assert(route["upgrade_candidate"] == "deepseek-ai/deepseek-v4-pro", "Pro candidate should be explicit")
    _assert(policy["route_summary"]["primary_text_model"] == "deepseek-ai/deepseek-v4-flash", "locked route should still use Flash")


def test_phase1_complex_brief_selects_pro_only_when_explicitly_allowed() -> None:
    policy = build_llm_brain_policy(
        user_idea=(
            "A 5 minute Vietnamese short drama with two speakers, secret reveal, dialogue, "
            "multi-scene continuity and cinematic story arc."
        ),
        target_market="vn",
        target_platform="youtube_long",
        duration_s=300,
        runtime_class="short_film",
        reference_counts={"images": 4, "videos": 1, "audios": 2},
        niche="drama",
        has_dialogue=True,
        speaker_count=2,
        graph_required=True,
        allow_expensive_reasoning=True,
    )
    route = policy["routes"]["creative_generation"]
    _assert(route["model"] == "deepseek-ai/deepseek-v4-pro", "explicit approval should allow Pro for complex route")
    _assert(route["pro_selected"] is True, "Pro selected flag should reflect explicit approval")


def test_phase1_pro_env_override_does_not_change_default_generator(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_model_generator", "deepseek-ai/deepseek-v4-pro")
    monkeypatch.setattr(settings, "llm_allow_pro_for_complex_brief", False)
    policy = build_llm_brain_policy(
        user_idea="Simple TikTok product demo.",
        target_market="vn",
        target_platform="tiktok",
        duration_s=30,
        reference_counts={"images": 0},
        niche="ugc_review",
    )
    _assert(
        policy["route_summary"]["primary_text_model"] == "deepseek-ai/deepseek-v4-flash",
        "policy must not let generator env override silently select Pro",
    )
    provider, model = llm._resolve_model("generator")
    _assert(provider == "atlascloud", "generator route should remain AtlasCloud")
    _assert(model == "deepseek-ai/deepseek-v4-flash", "router default generator must stay Flash")


def test_phase1_creative_brief_contract_parses_prompt_duration_and_goal() -> None:
    contract = build_creative_brief_contract(
        user_idea="Hay lam video 45s quang cao serum cho TikTok VN, can hook cuon va anh san pham.",
        target_market="vn",
        target_platform="tiktok",
        reference_counts={"images": 1},
    )
    parsed = contract["parsed"]
    _assert(contract["vendor_calls_performed"] is False, "creative brief contract must be vendor-free")
    _assert(parsed["duration"]["requested_s"] == 45, "45s prompt duration should be parsed")
    _assert(parsed["output_intent"] == "sell_product", "serum ad should resolve to sell_product intent")
    _assert(parsed["reference_expectation"]["has_visual_anchor"] is True, "image refs should mark visual anchor")
    _assert(contract["readiness"]["completeness_score"] >= 70, "concrete prompt should be mostly complete")


def test_phase1_creative_brief_contract_parses_30p_as_long_form_cap() -> None:
    contract = build_creative_brief_contract(
        user_idea="Lam cho toi video 30p dang short film ve founder quan cafe co twist cam xuc.",
        target_market="vn",
        target_platform="youtube_long",
        reference_counts={"images": 2, "audios": 1},
    )
    _assert(contract["parsed"]["duration"]["requested_s"] == 1800, "30p should parse as 1800 seconds")
    _assert(contract["quality_target"]["tier"] == "long_form_story", "30p route should be long-form story tier")
    _assert(contract["parsed"]["output_intent"] in {"entertain", "brand_story"}, "story/founder prompt should resolve to a story intent")


def test_phase1_production_decision_uses_prompt_duration_when_ui_auto() -> None:
    data = _decision(
        user_idea="Hay lam video 45s quang cao serum cho TikTok VN, hook proof-first.",
        target_market="vn",
        target_platform="tiktok",
        duration_hint_s=None,
        reference_counts={"images": 1},
    )
    _assert(data["input_summary"]["parsed_duration_hint_s"] == 45, "decision should expose parsed prompt duration")
    _assert(data["decision"]["target_duration_s"] == 45, "decision should use parsed duration when UI duration is auto")
    _assert(data["creative_brief_contract"]["parsed"]["duration"]["requested_s"] == 45, "decision should include creative brief contract")


def test_phase1_production_decision_uses_prompt_platform_over_default() -> None:
    data = _decision(
        user_idea="Create a 2 minute YouTube founder story for a cafe with a premium documentary feel.",
        target_market="global",
        target_platform="tiktok",
        duration_hint_s=None,
        reference_counts={"images": 2},
    )
    _assert(
        data["creative_brief_contract"]["parsed"]["target_platform"] == "youtube_long",
        "contract should parse explicit YouTube platform",
    )
    _assert(
        data["input_summary"]["target_platform"] == "youtube_long",
        "production decision should honor prompt platform over default tiktok",
    )
    _assert(
        data["decision"]["target_platform"] == "youtube_long",
        "decision summary should expose effective prompt platform",
    )


def test_phase1_creative_brief_contract_flags_missing_subject() -> None:
    contract = build_creative_brief_contract(
        user_idea="Hay lam video that viral.",
        target_market="auto",
        target_platform="tiktok",
        reference_counts={},
    )
    missing_keys = {item["key"] for item in contract["missing_fields"]}
    _assert("subject" in missing_keys, "vague brief should ask for subject")
    _assert(contract["blocking_questions"], "vague brief should generate a blocking question")


def test_phase2_creative_producer_v2_builds_product_script_and_shot_graph() -> None:
    data = _decision(
        user_idea="Hay lam video 45s quang cao serum cho TikTok VN, hook proof-first, co anh san pham.",
        target_market="vn",
        target_platform="tiktok",
        reference_counts={"images": 1},
    )
    producer = data["creative_producer_v2"]
    _assert(producer["vendor_calls_performed"] is False, "producer v2 must be vendor-free")
    _assert(
        producer["selected_angle"]["angle_id"] == "proof_first_transformation",
        "serum proof ad should select proof-first transformation",
    )
    _assert(len(producer["script_beats"]) >= 4, "producer should build a multi-beat script")
    _assert(producer["shot_graph"]["node_count"] >= len(producer["script_beats"]), "shot graph should cover all script beats")
    _assert(producer["prompt_compiler_handoff"]["shot_count"] == producer["shot_graph"]["node_count"], "handoff should match graph")


def test_phase2_creative_producer_v2_keeps_short_shots_above_render_minimum() -> None:
    data = _decision(
        user_idea="Make a 15s TikTok product proof ad for a serum with a clear CTA.",
        target_market="global",
        target_platform="tiktok",
        duration_hint_s=15,
        reference_counts={"images": 1},
    )
    producer = data["creative_producer_v2"]
    policy = producer["shot_graph"]["render_unit_policy"]
    min_unit_s = policy["min_unit_s"]
    durations = [node["duration_s"] for node in producer["shot_graph"]["nodes"]]
    _assert(policy["min_unit_s"] == 4, "producer policy should state the Seedance render minimum")
    _assert(len(producer["script_beats"]) <= 15 // min_unit_s, "short producer should compress beats to fit render minimum")
    _assert(all(duration >= min_unit_s for duration in durations), "every shot node should respect render minimum")


def test_phase2_creative_producer_v2_selects_drama_reversal_for_long_story() -> None:
    data = _decision(
        user_idea=(
            "Create a 5 minute YouTube short drama about a founder hiding a family secret, "
            "with dialogue, emotional twist and cinematic ending."
        ),
        target_market="global",
        target_platform="tiktok",
        reference_counts={"images": 3, "audios": 1},
        speaker_count=2,
    )
    producer = data["creative_producer_v2"]
    _assert(
        data["decision"]["target_platform"] == "youtube_long",
        "prompt platform should drive producer route",
    )
    _assert(
        producer["selected_angle"]["angle_id"] == "short_drama_reversal",
        "long drama should select short-drama reversal",
    )
    _assert(producer["shot_graph"]["node_count"] >= 10, "5m story should become many shot graph nodes")
    _assert("scene_continuity" in producer["qa_contract"]["checks"], "long story producer QA should include scene continuity")


def test_phase2_preflight_uses_producer_v2_for_script_and_storyboard() -> None:
    preflight = build_conversational_preflight(
        user_idea="Hay lam video 45s quang cao serum cho TikTok VN, hook proof-first.",
        target_market="vn",
        target_platform="tiktok",
        reference_counts={"images": 1},
    )
    _assert("creative_producer_v2" in preflight, "preflight should expose producer v2")
    _assert(preflight["summary"]["producer_angle"], "preflight summary should expose producer angle")
    _assert(len(preflight["script_outline"]) >= 4, "preflight script should use producer beats")
    _assert(preflight["storyboard"][0]["id"].startswith("S"), "storyboard should use producer shot graph nodes")


def test_phase3_prompt_execution_contract_compiles_every_producer_shot() -> None:
    data = _decision(
        user_idea="Hay lam video 45s quang cao serum cho TikTok VN, hook proof-first, co anh san pham.",
        target_market="vn",
        target_platform="tiktok",
        reference_counts={"images": 2, "videos": 1},
    )
    contract = data["prompt_execution_contract_v3"]
    producer = data["creative_producer_v2"]
    rebuilt = build_prompt_execution_contract_v3(
        user_idea=data["long_form_scene_preview"].get("logline") or "serum proof ad",
        creative_brief_contract=data["creative_brief_contract"],
        creative_producer_v2=producer,
        decision=data["decision"],
        seedance_prompt_formula=data["seedance_prompt_formula"],
        seedance_reference_allocation=data["seedance_reference_allocation"],
        model_route_strategy=data["model_route_strategy"],
        llm_brain_policy=data["llm_brain_policy"],
    )
    _assert(contract["schema_version"] == "cinejelly.prompt_execution_contract.v3", "phase3 prompt contract schema missing")
    _assert(contract["vendor_calls_performed"] is False, "phase3 prompt contract must be vendor-free")
    _assert(contract["paid_video_vendor_calls_allowed"] is False, "phase3 prompt contract must not unlock paid render")
    _assert(len(contract["compiled_shots"]) == producer["shot_graph"]["node_count"], "phase3 should compile every shot graph node")
    _assert(rebuilt["readiness"]["compiled_shot_count"] == contract["readiness"]["compiled_shot_count"], "direct phase3 builder should be deterministic")
    first_prompt = contract["compiled_shots"][0]["prompt"]
    _assert("[REFERENCE JOBS]" in first_prompt and "[ACTION]" in first_prompt and "[CAMERA]" in first_prompt, "compiled prompt should include required Seedance blocks")
    _assert(all(4 <= shot["duration_s"] <= 15 for shot in contract["compiled_shots"]), "compiled shot durations should stay in Seedance unit range")


def test_phase3_prompt_execution_contract_routes_no_reference_jobs_to_text_to_video() -> None:
    data = _decision(
        user_idea="Make a 30s cinematic surreal travel dream through a neon city.",
        target_market="global",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 0, "videos": 0, "audios": 0},
    )
    contract = data["prompt_execution_contract_v3"]
    modes = {shot["render_mode"] for shot in contract["compiled_shots"]}
    _assert(modes == {"text_to_video"}, "no-reference prompt contract should route to text-to-video")
    _assert(all(not shot["reference_slots"] for shot in contract["compiled_shots"]), "text-to-video shots should not require reference slots")


def test_phase3_prompt_execution_contract_binds_image_references_to_slots() -> None:
    data = _decision(
        user_idea="Make a 30s premium beauty product proof ad for a serum with exact packaging.",
        target_market="global",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 2, "videos": 0, "audios": 0},
    )
    contract = data["prompt_execution_contract_v3"]
    ref_shots = [shot for shot in contract["compiled_shots"] if shot["render_mode"] != "text_to_video"]
    _assert(ref_shots, "image-reference job should create non-T2V prompt shots")
    _assert(any(shot["reference_slots"] for shot in ref_shots), "image-reference prompt shots should bind reference slots")
    _assert(any("reference_identity_or_product_match" in shot["qa_checks"] for shot in ref_shots), "reference QA should be enforced")


def test_phase3_product_image_reference_prioritizes_product_hero_slot() -> None:
    data = _decision(
        user_idea="Make a 30s product proof ad for a serum with exact packaging and CTA.",
        target_market="global",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 1},
    )
    first_image_role = data["seedance_reference_allocation"]["image_role_plan"][0]["role"]
    first_slot_role = data["prompt_execution_contract_v3"]["compiled_shots"][0]["reference_slots"][0]["role"]
    _assert(first_image_role == "product_hero", "single product image should be allocated as product hero")
    _assert(first_slot_role == "product_hero", "compiled product prompt should bind first slot as product hero")


def test_phase3_preflight_exposes_prompt_execution_contract_summary() -> None:
    preflight = build_conversational_preflight(
        user_idea="Hay lam video 45s quang cao serum cho TikTok VN, co anh san pham.",
        target_market="vn",
        target_platform="tiktok",
        reference_counts={"images": 1},
    )
    _assert("prompt_execution_contract_v3" in preflight, "preflight should expose phase3 prompt contract")
    _assert(preflight["summary"]["compiled_shot_count"] == len(preflight["prompt_execution_contract_v3"]["compiled_shots"]), "preflight summary should match compiled shots")
    _assert(preflight["summary"]["prompt_primary_visual_model"], "preflight summary should expose phase3 primary visual model")


def test_phase4a_viral_creative_brain_selects_product_proof_pattern() -> None:
    data = _decision(
        user_idea="Hay lam video 45s quang cao serum cho TikTok VN, hook proof-first, co anh san pham.",
        target_market="vn",
        target_platform="tiktok",
        reference_counts={"images": 1},
    )
    brain = data["viral_creative_brain"]
    rebuilt = build_viral_creative_brain(
        user_idea="Hay lam video 45s quang cao serum cho TikTok VN, hook proof-first, co anh san pham.",
        creative_brief_contract=data["creative_brief_contract"],
        creative_producer_v2=data["creative_producer_v2"],
        prompt_execution_contract_v3=data["prompt_execution_contract_v3"],
        decision=data["decision"],
        creative_treatment_search=data["creative_treatment_search"],
        niche_playbook=data["niche_playbook"],
        market_playbook=data["market_playbook"],
    )
    _assert(brain["schema_version"] == "cinejelly.viral_creative_brain.v1", "viral brain schema missing")
    _assert(brain["vendor_calls_performed"] is False, "viral brain must be vendor-free")
    _assert(brain["paid_video_vendor_calls_allowed"] is False, "viral brain must not unlock paid render")
    _assert(brain["selected_viral_pattern"]["pattern_id"] == "proof_first_scroll_stop", "serum proof ad should select proof-first viral pattern")
    _assert(len(brain["hook_variants"]) >= 4, "viral brain should generate multiple hook variants")
    _assert(brain["readiness"]["creative_score"] >= 80, "complete product proof brief should be high-scoring")
    _assert(rebuilt["selected_viral_pattern"]["pattern_id"] == brain["selected_viral_pattern"]["pattern_id"], "viral brain should be deterministic")


def test_phase4a_viral_creative_brain_selects_long_drama_reversal() -> None:
    data = _decision(
        user_idea=(
            "Create a 5 minute YouTube short drama about a Vietnamese founder hiding a family secret, "
            "with dialogue, emotional twist and cinematic ending."
        ),
        target_market="vn",
        target_platform="tiktok",
        reference_counts={"images": 3, "videos": 1, "audios": 1},
        speaker_count=2,
    )
    brain = data["viral_creative_brain"]
    _assert(
        brain["selected_viral_pattern"]["pattern_id"] == "short_drama_reversal_loop",
        "long drama should select short-drama viral reversal",
    )
    _assert("long_form_needs_scene_level_payoff_tracking" in {risk["risk"] for risk in brain["risk_guards"]}, "long drama should warn about scene payoff tracking")
    _assert(brain["retention_plan"]["long_form_rule"].startswith("close every scene"), "long-form viral plan should use scene cliffhangers")


def test_phase4a_preflight_exposes_viral_brain_and_distribution_preview() -> None:
    preflight = build_conversational_preflight(
        user_idea="Hay lam video 45s quang cao serum cho TikTok VN, co anh san pham.",
        target_market="vn",
        target_platform="tiktok",
        reference_counts={"images": 1},
    )
    _assert("viral_creative_brain" in preflight, "preflight should expose viral brain")
    _assert(preflight["summary"]["viral_pattern"], "preflight summary should expose viral pattern")
    _assert(preflight["summary"]["viral_creative_score"] >= 80, "preflight should expose strong viral creative score")
    _assert(preflight["distribution_preview"]["viral_pattern"], "distribution preview should use viral package")
    _assert(preflight["distribution_preview"]["cta"], "distribution preview should expose viral CTA")


def test_phase4b_output_qa_retry_brain_builds_product_retry_contract() -> None:
    data = _decision(
        user_idea="Hay lam video 45s quang cao serum cho TikTok VN, hook proof-first, co anh san pham.",
        target_market="vn",
        target_platform="tiktok",
        reference_counts={"images": 1},
    )
    brain = data["output_qa_retry_brain"]
    rebuilt = build_output_qa_retry_brain(
        user_idea="Hay lam video 45s quang cao serum cho TikTok VN, hook proof-first, co anh san pham.",
        creative_brief_contract=data["creative_brief_contract"],
        creative_producer_v2=data["creative_producer_v2"],
        prompt_execution_contract_v3=data["prompt_execution_contract_v3"],
        viral_creative_brain=data["viral_creative_brain"],
        decision=data["decision"],
    )
    _assert(brain["schema_version"] == "cinejelly.output_qa_retry_brain.v1", "output QA retry schema missing")
    _assert(brain["vendor_calls_performed"] is False, "output QA retry brain must be vendor-free")
    _assert(brain["paid_video_vendor_calls_allowed"] is False, "output QA retry brain must not unlock paid retry")
    _assert(len(brain["per_shot_qa"]) == len(data["prompt_execution_contract_v3"]["compiled_shots"]), "QA nodes should match compiled shots")
    issue_tags = {item["issue_tag"] for item in brain["issue_taxonomy"]}
    _assert("product_identity_drift" in issue_tags, "product ad QA should include product identity drift")
    retry_tags = {item["retry_recipe"]["primary_issue_tag"] for item in brain["per_shot_qa"]}
    _assert("product_identity_drift" in retry_tags, "product ad should prepare product retry recipes")
    _assert(rebuilt["readiness"]["qa_node_count"] == brain["readiness"]["qa_node_count"], "output QA retry brain should be deterministic")


def test_phase4b_output_qa_retry_brain_requires_long_form_continuity_review() -> None:
    data = _decision(
        user_idea=(
            "Create a 5 minute YouTube short drama about a Vietnamese founder hiding a family secret, "
            "with dialogue, emotional twist and cinematic ending."
        ),
        target_market="vn",
        target_platform="tiktok",
        reference_counts={"images": 3, "videos": 1, "audios": 1},
        speaker_count=2,
    )
    brain = data["output_qa_retry_brain"]
    issue_tags = {item["issue_tag"] for item in brain["issue_taxonomy"]}
    sequence_checks = set(brain["sequence_qa"]["checks"])
    retry_tags = {item["retry_recipe"]["primary_issue_tag"] for item in brain["per_shot_qa"]}
    _assert("continuity_break" in issue_tags, "long-form QA should include continuity break taxonomy")
    _assert("scene_payoff_break" in issue_tags, "long-form QA should include scene payoff taxonomy")
    _assert("cross_shot_continuity" in sequence_checks, "long-form sequence QA should include cross-shot continuity")
    _assert("continuity_break" in retry_tags, "long-form continuity shots should prepare continuity retry recipes")


def test_phase4b_preflight_exposes_output_qa_retry_summary() -> None:
    preflight = build_conversational_preflight(
        user_idea="Hay lam video 45s quang cao serum cho TikTok VN, co anh san pham.",
        target_market="vn",
        target_platform="tiktok",
        reference_counts={"images": 1},
    )
    _assert("output_qa_retry_brain" in preflight, "preflight should expose output QA retry brain")
    _assert(preflight["summary"]["qa_node_count"] == len(preflight["output_qa_retry_brain"]["per_shot_qa"]), "preflight QA summary should match nodes")
    _assert(preflight["summary"]["qa_confidence_score"] >= 80, "complete product brief should have strong QA confidence")
    _assert(preflight["summary"]["retry_recipe_count"] == preflight["summary"]["qa_node_count"], "every shot should get a retry recipe")


def test_long_vn_presenter_uses_graph_and_infinitetalk_candidate() -> None:
    data = _decision(
        user_idea="A Vietnamese founder explains an AI inbox app in a 5 minute presenter video.",
        target_market="vn",
        target_platform="youtube_long",
        duration_hint_s=300,
        reference_counts={"images": 2, "videos": 0, "audios": 1},
    )
    decision = data["decision"]
    _assert(decision["runtime_class"] == "short_film", "300s should be short_film runtime")
    _assert(decision["graph_required"] is True, "5 minute jobs must require graph execution")
    _assert(decision["dialogue_required"] is True, "explains/presenter should require dialogue lane")
    _assert(
        decision["dialogue_route_policy"]["dialogue_candidate"] == "atlascloud/infinitetalk",
        "long single-speaker presenter should benchmark InfiniteTalk",
    )
    strategy = data["model_route_strategy"]
    candidates = {item["model_key"]: item for item in strategy["benchmark_locked_candidates"]}
    _assert("atlascloud/infinitetalk" in candidates, "model route strategy should expose InfiniteTalk candidate")
    _assert(candidates["atlascloud/infinitetalk"]["status"] == "benchmark_locked", "InfiniteTalk must stay locked")
    _assert(strategy["seedance_execution"]["estimated_units"] >= 20, "5m Seedance strategy should estimate many units")
    _assert(
        decision["benchmark_required_before_top_tier_claim"] is True,
        "long-form/dialogue candidate must stay benchmark-gated",
    )
    sufficiency = data["reference_sufficiency"]
    _assert(sufficiency["status"] == "warn", "VN dialogue route should require review before top-tier claims")
    _assert("localized_dialogue_review" in sufficiency["missing_for_top_tier"], "VN dialogue should require benchmark review")


def test_two_speaker_drama_uses_multitalk_candidate() -> None:
    policy = build_dialogue_route_policy(
        niche="drama",
        target_market="global",
        duration_s=120,
        has_dialogue=True,
        reference_audio_count=2,
        speaker_count=2,
    ).model_dump()
    _assert(policy["route_type"] == "multi_speaker_dialogue_candidate", "two speakers should use multi-speaker route")
    _assert(policy["dialogue_candidate"] == "atlascloud/multitalk", "two-speaker dialogue should benchmark MultiTalk")
    _assert(policy["requires_benchmark_before_auto_route"] is True, "MultiTalk must be benchmark-gated")


def test_model_route_strategy_locks_emerging_visual_challengers() -> None:
    no_ref = _decision(
        user_idea="A surreal cinematic travel dream through an impossible city at sunrise.",
        target_market="global",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 0, "videos": 0, "audios": 0},
    )
    strategy = no_ref["model_route_strategy"]
    candidates = {item["model_key"]: item for item in strategy["benchmark_locked_candidates"]}
    _assert(strategy["summary"]["primary_visual_model"] == "seedance_2_0_fast_t2v", "no-ref drafts should use Seedance fast t2v")
    _assert("atlascloud_catalog:veo_3_1_lite" in candidates, "no-ref concepts should expose Veo Lite benchmark candidate")
    _assert(any("no-reference" in lock for lock in strategy["route_locks"]), "no-ref route should warn about consistency claims")

    premium = _decision(
        user_idea="A premium restaurant hospitality film with dish macro, venue ambience, and cinematic service.",
        target_market="vn",
        target_platform="tiktok",
        duration_hint_s=30,
        reference_counts={"images": 2, "videos": 1, "audios": 1},
    )
    premium_candidates = {item["model_key"]: item for item in premium["model_route_strategy"]["benchmark_locked_candidates"]}
    _assert(premium["model_route_strategy"]["summary"]["primary_visual_model"] == "seedance_2_0_ref", "premium hospitality should use full Seedance ref")
    _assert("atlascloud_catalog:vidu_q3_reference_to_video" in premium_candidates, "premium visual niches should expose Vidu Q3 challenger benchmark")


def test_finance_keeps_review_gate() -> None:
    data = _decision(
        user_idea="Explain why emergency funds matter before investing using jars and monthly bills.",
        target_market="us",
        duration_hint_s=60,
        reference_counts={"images": 1, "videos": 0, "audios": 0},
        niche_hint="finance_education",
    )
    decision = data["decision"]
    _assert(decision["niche"] == "finance_education", "finance hint should resolve to finance_education")
    _assert(decision["readiness"] == "review_required", "finance education requires review")
    _assert(
        any("safety review" in gate for gate in data["qa_gates"]),
        "finance decision must include safety review QA gate",
    )
    _assert(decision["benchmark_required_before_top_tier_claim"] is True, "review niches must require benchmark")


def test_food_uses_sensory_seedance_route() -> None:
    data = _decision(
        user_idea="A street food vendor makes crispy banh mi from bread crackle to sauce pour.",
        target_market="vn",
        duration_hint_s=30,
        reference_counts={"images": 1, "videos": 0, "audios": 1},
    )
    decision = data["decision"]
    _assert(decision["niche"] == "food", f"expected food, got {decision['niche']}")
    _assert(
        decision["primary_model_route"]["primary_visual_model"] == "seedance_2_0_ref",
        "food sensory/product shots should use premium Seedance route",
    )
    _assert("sensory hook" in data["niche_playbook"]["beat_flow"], "food playbook should expose sensory beat flow")


def test_long_narrative_context_beats_object_keyword_for_drama() -> None:
    data = _decision(
        user_idea=(
            "Tao video 5 phut phim ngan ve co gai ban banh mi o Sai Gon "
            "phat hien bi mat gia dinh, cam xuc manh, cinematic, co thoai tieng Viet."
        ),
        target_market="vn",
        duration_hint_s=300,
        reference_counts={"images": 0, "videos": 0, "audios": 0},
        speaker_count=2,
    )
    decision = data["decision"]
    resolution = data["input_summary"]["niche_resolution"]
    sop = data["script_asset_sop"]
    _assert(decision["niche"] == "drama", f"narrative short film should resolve to drama, got {decision['niche']}")
    _assert(decision["graph_required"] is True, "5 minute drama must route through long-form graph policy")
    _assert(decision["dialogue_required"] is True, "explicit Vietnamese dialogue should enable dialogue lane")
    _assert(sop["enabled"] is True, "long-form narrative should expose script asset SOP")
    _assert(sop["asset_groups"]["characters"], "script asset SOP should propose character anchors")
    _assert(sop["asset_groups"]["locations"], "script asset SOP should propose location anchors")
    _assert("character_visual_anchor" in sop["missing_before_top_tier"], "thin drama input should request character visual anchor")
    _assert("consented_voice_or_tts_audio" in sop["missing_before_top_tier"], "dialogue drama should request voice/audio anchor")
    _assert(
        any(step["name"] == "script asset SOP" for step in data["workflow_steps"]),
        "workflow should expose script/entity asset SOP stage",
    )
    _assert(
        any("narrative_short_film_signal" in row.get("specific_hits", []) for row in resolution["scores"]),
        "niche evidence should explain narrative override",
    )


def test_english_short_drama_context_beats_street_food_keyword() -> None:
    data = _decision(
        user_idea=(
            "A 5 minute Vietnamese short drama about two sisters rebuilding their "
            "street food stall after a storm, emotional but hopeful, consistent "
            "characters and location."
        ),
        target_market="vn",
        target_platform="youtube_long",
        duration_hint_s=300,
        reference_counts={"images": 6, "videos": 2, "audios": 2},
        speaker_count=2,
    )
    decision = data["decision"]
    resolution = data["input_summary"]["niche_resolution"]
    _assert(decision["niche"] == "drama", f"explicit English short drama should resolve to drama, got {decision['niche']}")
    _assert(decision["graph_required"] is True, "5 minute English drama should require long-form graph")
    _assert(decision["dialogue_required"] is True, "two-speaker long drama should enable dialogue lane")
    _assert(
        any("narrative_short_film_signal" in row.get("specific_hits", []) for row in resolution["scores"]),
        "English short drama override should expose narrative signal",
    )


def test_reference_count_aliases_are_backward_compatible() -> None:
    data = _decision(
        user_idea="A creator reviews a new camera with a reference image, demo video, and room audio.",
        target_market="global",
        duration_hint_s=60,
        reference_counts={"image": 1, "video": 1, "audio": 1, "pinned": 1},
    )
    counts = data["input_summary"]["reference_counts"]
    _assert(counts["images"] == 1, "singular image alias should normalize to images")
    _assert(counts["videos"] == 1, "singular video alias should normalize to videos")
    _assert(counts["audios"] == 1, "singular audio alias should normalize to audios")
    _assert(counts["pinned_assets"] == 1, "pinned alias should normalize to pinned_assets")
    _assert(
        data["decision"]["primary_model_route"]["primary_visual_model"] != "seedance_2_0_fast_t2v",
        "non-zero reference aliases should route away from pure text-to-video",
    )


def test_seedance_shot_linter_passes_renderable_shot() -> None:
    plan = _minimal_plan([_shot()])
    lint = lint_seedance_plan(bible=plan.continuity_bible, shots=plan.shot_list)
    _assert(lint["status"] == "pass", f"expected lint pass, got {lint['status']} {lint['top_issues']}")
    _assert(lint["failed_shot_count"] == 0, "renderable shot should have no failures")


def test_seedance_shot_linter_fails_overloaded_long_shot() -> None:
    plan = _minimal_plan([
        _shot(
            duration_s=18,
            subject="person",
            action="opens the box then walks to the mirror then applies the product then shows the result",
            camera_shot="cinematic",
            camera_movement="beautiful movement",
            background="",
        )
    ])
    lint = lint_seedance_plan(bible=plan.continuity_bible, shots=plan.shot_list)
    _assert(lint["status"] == "fail", f"expected lint fail, got {lint['status']}")
    report = lint["shot_reports"][0]
    _assert("seedance_duration" in report["hard_failures"], "long Seedance unit should fail duration lint")
    _assert("one_physical_action" in report["hard_failures"], "overloaded action should fail one-action lint")


def test_seedance_prompt_compiler_emits_structured_reference_contract() -> None:
    plan = _minimal_plan([_shot(reference_indices=[0], previous_shot_id="S0")])
    prompt = compile_seedance_scene_prompt(
        bible=plan.continuity_bible,
        shot=plan.shot_list[0],
        base_prompt="Show the creator proving the product result with a tight hook.",
        reference_manifest={
            "images": [{"tag": "@image_1", "label": "creator and product identity anchor"}],
            "videos": [{"tag": "@video_1", "role": "handheld push-in camera reference"}],
            "audios": [{"tag": "@audio_1", "role": "soft creator beat reference"}],
        },
        render_mode="ref_to_video",
        model_key="seedance_2_0_fast_ref",
    )
    for section in [
        "[REFERENCE JOBS]",
        "[TIMELINE]",
        "[ENVIRONMENT]",
        "[VISUAL STYLE]",
        "[SHOT DIRECTION]",
        "[CAMERA AND SOUND]",
        "[SHOT CONTRACT]",
        "[DIRECTOR INTENT]",
        "[CONSTRAINTS]",
    ]:
        _assert(section in prompt, f"compiled Seedance prompt should include {section}")
    _assert("Use each reference only for its assigned job" in prompt, "reference jobs must keep roles separate")
    _assert("one physically filmable action" in prompt, "prompt must keep shots renderable")
    _assert("Preserve identity, product geometry" in prompt, "prompt must anchor continuity")
    _assert("Continue from previous shot S0" in prompt, "prompt must expose shot-to-shot continuity")


def test_seedance_prompt_compiler_includes_formula_contract_when_present() -> None:
    plan = _minimal_plan([_shot(reference_indices=[0])])
    plan.continuity_bible.storytelling_meta = {
        **(plan.continuity_bible.storytelling_meta or {}),
        "seedance_prompt_formula": {
            "schema_version": "cinejelly.seedance_prompt_formula.v1",
            "formula": ["reference_jobs", "timeline", "story_intent", "action", "camera", "sound", "shot_contract"],
            "niche_template": {
                "story_intent": "prove one visible product promise through a tactile action",
                "action": "show one concrete product interaction",
                "camera": "macro/detail/hero framing that preserves geometry",
            },
        },
    }
    prompt = compile_seedance_scene_prompt(
        bible=plan.continuity_bible,
        shot=plan.shot_list[0],
        base_prompt="Show a product proof beat.",
        reference_manifest={"images": [{"tag": "@image_1", "label": "product identity anchor"}]},
        render_mode="ref_to_video",
        model_key="seedance_2_0_ref",
    )
    _assert("[PROMPT FORMULA]" in prompt, "Seedance prompt should include formula contract")
    _assert("reference jobs -> timeline" in prompt, "formula order should be visible")
    _assert("Niche action rule" in prompt, "niche action rule should guide the render prompt")


def test_seedance_single_call_prompt_includes_formula_contract_when_present() -> None:
    shots = [
        _shot(shot_id="S1", index=0, start_s=0, duration_s=6, reference_indices=[0]),
        _shot(shot_id="S2", index=1, start_s=6, duration_s=6, reference_indices=[0], previous_shot_id="S1"),
    ]
    plan = _minimal_plan(shots, duration_s=12)
    plan.continuity_bible.storytelling_meta = {
        **(plan.continuity_bible.storytelling_meta or {}),
        "seedance_prompt_formula": {
            "schema_version": "cinejelly.seedance_prompt_formula.v1",
            "formula": ["reference_jobs", "timeline", "action", "camera", "sound", "constraints"],
            "niche_template": {
                "story_intent": "make one short product story readable",
                "action": "show one concrete visible proof per unit",
                "camera": "controlled macro and hero shots",
            },
        },
    }
    spec = build_seedance_2_multi_shot(
        bible=plan.continuity_bible,
        shots=shots,
        reference_images=["https://cdn.example.com/ref.jpg"],
        reference_videos=[],
        reference_audios=[],
        model_key="seedance_2_0_fast_ref",
        resolution="720p",
    )
    _assert("[PROMPT FORMULA]" in spec.prompt, "single-call prompt should include formula contract")
    _assert("reference jobs -> timeline" in spec.prompt, "single-call formula order should be visible")


def test_per_shot_render_quality_probe_uses_current_scene_job() -> None:
    source = (Path(__file__).resolve().parents[1] / "workers" / "video_worker.py").read_text(encoding="utf-8")
    stage_1 = source.index("# Stage 1")
    stage_3 = source.index("# Stage 3", stage_1)
    per_shot_loop = "".join(source[stage_1:stage_3].split())
    _assert(
        "reference_image_urls=scene_job.reference_image_urls" not in per_shot_loop,
        "per-shot render loop must not reference scene_job before it exists",
    )
    _assert(
        "reference_image_urls=job.reference_image_urls" in per_shot_loop,
        "per-shot render loop should probe reference similarity from the current generated scene job",
    )


def test_seedance_prompt_compiler_preserves_non_seedance_prompt() -> None:
    plan = _minimal_plan([_shot()])
    base_prompt = "A plain prompt for a non-Seedance fallback model."
    prompt = compile_seedance_scene_prompt(
        bible=plan.continuity_bible,
        shot=plan.shot_list[0],
        base_prompt=base_prompt,
        model_key="wan_2_7_i2v",
    )
    _assert(prompt == base_prompt, "non-Seedance routes must preserve legacy prompt behavior")


def test_autonomous_preflight_includes_seedance_lint() -> None:
    bad_plan = _minimal_plan([
        _shot(
            duration_s=18,
            action="opens the box then walks to the mirror then applies the product then shows the result",
        )
    ])
    report = build_autonomous_preflight_report(
        plan=bad_plan,
        resolved_model="seedance_2_0_fast_ref",
        target_market="vn",
        target_platform="tiktok",
        reference_counts={"images": 1, "videos": 0, "audios": 0},
    )
    _assert(report["status"] == "fail", "preflight should fail when Seedance shot lint fails")
    _assert("seedance_shot_lint" in report["hard_failures"], "preflight hard failures should include shot lint")
    _assert(report["seedance_shot_lint"]["failed_shot_count"] == 1, "preflight should expose lint aggregate")


def test_autonomous_preflight_blocks_responsible_content() -> None:
    plan = _minimal_plan([_shot()])
    plan.continuity_bible.storytelling_meta = {
        **(plan.continuity_bible.storytelling_meta or {}),
        "user_idea": "Make a fake endorsement where Elon Musk recommends this finance app and clone his voice.",
    }
    report = build_autonomous_preflight_report(
        plan=plan,
        resolved_model="seedance_2_0_fast_ref",
        target_market="us",
        target_platform="tiktok",
        reference_counts={"images": 1, "videos": 0, "audios": 1},
    )
    _assert(report["responsible_content_gate"]["render_allowed"] is False, "preflight should expose responsible gate block")
    _assert("responsible_content_gate" in report["hard_failures"], "responsible gate should hard-fail high-risk render")


def test_autonomous_preflight_includes_niche_execution_rubric() -> None:
    plan = _minimal_plan([
        _shot(shot_id="S1", index=0, start_s=0, purpose="result hook"),
        _shot(
            shot_id="S2",
            index=1,
            start_s=8,
            purpose="test in hand",
            previous_shot_id="S1",
            action="demonstrates the product close to camera with clear tactile proof",
        ),
        _shot(
            shot_id="S3",
            index=2,
            start_s=16,
            purpose="proof result",
            previous_shot_id="S2",
            action="shows the final visible result and gives a soft recommendation",
            camera_shot="MS",
        ),
    ])
    report = build_autonomous_preflight_report(
        plan=plan,
        resolved_model="seedance_2_0_fast_ref",
        target_market="vn",
        target_platform="tiktok",
        reference_counts={"images": 1, "videos": 1, "audios": 1},
    )
    rubric = report["niche_execution_rubric"]
    _assert(rubric["status"] in {"pass", "warn"}, f"niche rubric should not hard fail a coherent UGC plan: {rubric}")
    _assert(rubric["score"] >= 70, "coherent plan should get a useful niche execution score")
    _assert("niche_execution_rubric" not in report["hard_failures"], "coherent niche fit should not block render")


def test_screenplay_scene_linter_passes_valid_long_form_structure() -> None:
    lint = lint_screenplay_scene_structure(
        duration_s=300,
        runtime_structure=_valid_long_form_runtime_structure(),
    )
    _assert(lint["status"] == "pass", f"expected screenplay lint pass, got {lint['status']} {lint['top_issues']}")
    _assert(lint["failed_scene_count"] == 0, "valid long-form scenes should have no failures")


def test_screenplay_scene_linter_fails_missing_scene_continuity() -> None:
    runtime = _valid_long_form_runtime_structure()
    runtime["scene_blueprints"][1]["continuity_anchor"] = ""
    runtime["screenplay_plan"]["scene_scripts"][1]["conflict"] = ""
    runtime["screenplay_plan"]["scene_scripts"][1]["turning_point"] = "setup"
    lint = lint_screenplay_scene_structure(duration_s=300, runtime_structure=runtime)
    _assert(lint["status"] == "fail", f"expected screenplay lint fail, got {lint['status']}")
    failed = [r for r in lint["scene_reports"] if r["status"] == "fail"]
    _assert(failed and failed[0]["scene_id"] == "SC02", "SC02 should fail scene lint")
    _assert("missing_continuity_anchor" in failed[0]["issues"], "missing continuity anchor should fail")
    _assert("missing_conflict" in failed[0]["issues"], "missing conflict should fail")


def test_autonomous_preflight_includes_screenplay_scene_lint() -> None:
    runtime = _valid_long_form_runtime_structure()
    runtime["scene_blueprints"][0]["handoff_to_next"] = ""
    plan = _minimal_plan([_shot()], duration_s=300, runtime_structure=runtime)
    report = build_autonomous_preflight_report(
        plan=plan,
        resolved_model="seedance_2_0_fast_ref",
        target_market="vn",
        target_platform="tiktok",
        reference_counts={"images": 1, "videos": 0, "audios": 0},
    )
    _assert("screenplay_scene_lint" in report["hard_failures"], "preflight should include screenplay lint failure")
    _assert(report["screenplay_scene_lint"]["failed_scene_count"] == 1, "preflight should expose failed scene count")


def test_continuity_handoff_policy_applies_required_chains() -> None:
    shots = [
        _shot(shot_id="S1", index=0, start_s=0, purpose="hook", character_ids=["char_main"], product_ids=["prod_main"]),
        _shot(shot_id="S2", index=1, start_s=8, purpose="demo", character_ids=["char_main"], product_ids=["prod_main"]),
        _shot(shot_id="S3", index=2, start_s=16, purpose="transition", character_ids=["char_main"], product_ids=["prod_main"]),
        _shot(shot_id="S4", index=3, start_s=24, purpose="proof", character_ids=["char_main"], product_ids=["prod_main"]),
    ]
    before = build_continuity_handoff_policy(shots, duration_s=300, runtime_class="short_film")
    _assert(before["missing_required_handoffs"] == 1, "S2 should require a missing handoff before apply")
    after = apply_continuity_handoffs(shots, duration_s=300, runtime_class="short_film")
    _assert(shots[1].continuity.previous_shot_id == "S1", "S2 should chain from S1")
    _assert(shots[2].continuity.previous_shot_id is None, "transition shot should remain an intentional cut")
    _assert(after["missing_required_handoffs"] == 0, "apply should resolve required handoffs")
    _assert(after["intentional_cuts"] >= 1, "policy should expose intentional cuts")


def test_autonomous_preflight_fails_missing_long_form_handoff() -> None:
    runtime = _valid_long_form_runtime_structure()
    shots = [
        _shot(shot_id="S1", index=0, start_s=0, purpose="hook", character_ids=["char_main"], product_ids=["prod_main"]),
        _shot(shot_id="S2", index=1, start_s=8, purpose="demo", character_ids=["char_main"], product_ids=["prod_main"]),
        _shot(shot_id="S3", index=2, start_s=16, purpose="proof", character_ids=["char_main"], product_ids=["prod_main"], previous_shot_id="S2"),
    ]
    plan = _minimal_plan(shots, duration_s=300, runtime_structure=runtime)
    report = build_autonomous_preflight_report(
        plan=plan,
        resolved_model="seedance_2_0_fast_ref",
        target_market="vn",
        target_platform="tiktok",
        reference_counts={"images": 1, "videos": 0, "audios": 0},
    )
    _assert("continuity_handoff_policy" in report["hard_failures"], "missing long-form handoff should be a hard preflight failure")
    _assert(report["continuity_handoff_policy"]["missing_required_handoffs"] == 1, "preflight should expose missing handoff count")


def test_production_decision_exposes_long_form_execution_gate() -> None:
    data = _decision(
        user_idea="A 5 minute Vietnamese short film about a founder revealing a product mistake and earning trust.",
        target_market="vn",
        duration_hint_s=300,
        reference_counts={"images": 1, "videos": 1, "audios": 0},
    )
    gate = data["long_form_execution_gate"]
    _assert(gate["enabled"] is True, "5 minute jobs should expose the long-form execution gate")
    _assert(gate["render_route"] == "graph_executor_required", "long-form preview should require graph execution")
    _assert(gate["default_route_allowed"] is False, "planning preview should not claim default long-form readiness")
    _assert(
        "persist executable production_graph with shot and QA nodes" in gate["required_before_default"],
        "gate should explain graph requirement before default route",
    )


def test_long_form_execution_gate_passes_executable_graph_contract() -> None:
    runtime = _valid_long_form_runtime_structure()
    shots = [
        _shot(shot_id="S1", index=0, start_s=0, purpose="hook", character_ids=["char_main"], product_ids=["prod_main"]),
        _shot(shot_id="S2", index=1, start_s=8, purpose="proof setup", character_ids=["char_main"], product_ids=["prod_main"], previous_shot_id="S1"),
        _shot(shot_id="S3", index=2, start_s=16, purpose="test escalation", character_ids=["char_main"], product_ids=["prod_main"], previous_shot_id="S2"),
        _shot(shot_id="S4", index=3, start_s=24, purpose="visible result", character_ids=["char_main"], product_ids=["prod_main"], previous_shot_id="S3"),
        _shot(shot_id="S5", index=4, start_s=32, purpose="verdict setup", character_ids=["char_main"], product_ids=["prod_main"], previous_shot_id="S4"),
        _shot(shot_id="S6", index=5, start_s=40, purpose="final payoff", character_ids=["char_main"], product_ids=["prod_main"], previous_shot_id="S5"),
    ]
    memory = _valid_scene_memory_pack(shots)
    graph = build_production_graph(
        plan_id="test_plan",
        duration_s=300,
        runtime_structure=runtime,
        shots=shots,
        scene_memory_pack=memory,
    ).model_dump()
    gate = build_long_form_execution_gate(
        duration_s=300,
        runtime_payload=runtime,
        production_graph=graph,
        scene_memory_pack=memory,
        shots=shots,
        graph_executor_enabled=True,
        route_quality_scorecard={
            "top_tier_claim_allowed": False,
            "requires_human_review": False,
        },
    )
    _assert(gate["status"] == "warn", f"benchmark warning is allowed, got {gate['status']}: {gate}")
    _assert(gate["graph_executor_ready"] is True, "complete graph contract should be executor-ready")
    _assert(gate["default_route_allowed"] is True, "enabled graph executor and complete contract should allow default route")
    _assert(gate["execution_contract"]["graph_qa_count"] == len(shots), "every shot should have a QA node")


def test_production_graph_shot_nodes_carry_prompt_formula_and_reference_contract() -> None:
    runtime = _valid_long_form_runtime_structure()
    shots = [
        _shot(shot_id="S1", index=0, start_s=0, purpose="hook", reference_indices=[0]),
        _shot(shot_id="S2", index=1, start_s=8, purpose="proof", previous_shot_id="S1", reference_indices=[0, 1]),
    ]
    memory = _valid_scene_memory_pack(shots)
    prompt_formula = {
        "schema_version": "cinejelly.seedance_prompt_formula.v1",
        "source_pattern": "asset job -> timeline -> action -> camera -> sound -> constraints",
        "formula": ["reference_jobs", "timeline", "action", "camera", "sound", "constraints"],
        "reference_job_policy": {
            "required_reference_jobs": ["character_identity_reference", "location_or_motion_reference"],
            "slot_priority": ["character image", "motion video", "style image"],
            "assignment_rule": "each reference gets one job",
        },
        "niche_template": {
            "story_intent": "advance one visible story beat",
            "action": "show one physical action",
            "camera": "controlled continuity framing",
        },
    }
    graph = build_production_graph(
        plan_id="plan_formula",
        duration_s=300,
        runtime_structure=runtime,
        shots=shots,
        scene_memory_pack=memory,
        prompt_formula=prompt_formula,
        reference_contract=prompt_formula,
    ).model_dump()
    shot_node = next(node for node in graph["nodes"] if node["id"] == "shot_S2")
    payload = shot_node["payload"]
    _assert(payload["prompt_formula"]["schema_version"] == "cinejelly.seedance_prompt_formula.v1", "shot node should carry formula")
    _assert("reference_jobs" in payload["prompt_formula"]["formula"], "formula order should be retained")
    _assert("character_identity_reference" in payload["reference_contract"]["required_reference_jobs"], "reference jobs should be retained")
    _assert(payload["reference_contract"]["reference_indices"] == [0, 1], "shot reference indices should be retained")
    _assert(payload["render_contract"]["unit_duration_s"] == [4, 15], "shot node should retain Seedance unit contract")


def test_dynamic_keyframe_memory_contract_maps_scene_handoffs() -> None:
    shots = [
        _shot(shot_id=f"S{i + 1}", index=i, start_s=i * 10, previous_shot_id=(f"S{i}" if i else None))
        for i in range(6)
    ]
    runtime = _valid_long_form_runtime_structure()
    memory = _valid_scene_memory_pack(shots)
    graph = build_production_graph(
        plan_id="plan_memory",
        duration_s=300,
        runtime_structure=runtime,
        shots=shots,
        scene_memory_pack=memory,
    ).model_dump()
    contract = build_dynamic_keyframe_memory_contract(
        scene_memory_pack=memory,
        production_graph=graph,
        accepted_outputs=[
            {
                "shot_id": "S2",
                "video_url": "https://cdn.example.com/s2.mp4",
                "last_frame_url": "https://cdn.example.com/s2-last.jpg",
                "qa_score": 8.6,
            }
        ],
    )
    _assert(contract["schema_version"] == "cinejelly.dynamic_keyframe_memory.v1", "dynamic memory schema missing")
    _assert(contract["status"] == "partially_populated", "accepted outputs should populate memory")
    _assert(len(contract["memory_bank"]["planned_anchors"]) == 3, "one planned anchor per scene expected")
    _assert(len(contract["memory_bank"]["bridge_anchors"]) == 2, "scene bridge anchors should mirror scene memory bridges")
    rendered = contract["memory_bank"]["rendered_anchors"][0]
    _assert(rendered["scene_id"] == "SC01", "rendered anchor should inherit scene id from shot map")
    _assert(rendered["last_frame_url"].endswith("s2-last.jpg"), "rendered anchor should preserve last frame URL")
    _assert(contract["promotion_gate"]["top_tier_claim_allowed"] is False, "memory contract alone must not allow top-tier claim")


def test_autonomous_preflight_includes_long_form_execution_gate() -> None:
    runtime = _valid_long_form_runtime_structure()
    shots = [
        _shot(shot_id="S1", index=0, start_s=0, purpose="hook"),
        _shot(shot_id="S2", index=1, start_s=8, purpose="proof", previous_shot_id="S1"),
    ]
    plan = _minimal_plan(shots, duration_s=300, runtime_structure=runtime)
    report = build_autonomous_preflight_report(
        plan=plan,
        resolved_model="seedance_2_0_fast_ref",
        target_market="vn",
        target_platform="tiktok",
        reference_counts={"images": 1, "videos": 0, "audios": 0},
    )
    _assert(
        "long_form_execution_gate" in report["hard_failures"],
        "preflight should hard-fail long-form plans without graph/scene memory",
    )
    _assert(report["long_form_execution_gate"]["enabled"] is True, "preflight should expose long-form gate payload")
    _assert("production_graph" in report["long_form_execution_gate"]["blockers"], "missing graph should be a blocker")


def test_autonomous_preflight_includes_script_asset_sop_for_long_form() -> None:
    runtime = _valid_long_form_runtime_structure()
    shots = [
        _shot(
            shot_id="S1",
            index=0,
            start_s=0,
            purpose="hook",
            character_ids=["char_main"],
            product_ids=["prod_main"],
            action="a young woman opens a banh mi cart in Saigon",
        ),
        _shot(
            shot_id="S2",
            index=1,
            start_s=8,
            purpose="family secret reveal",
            character_ids=["char_main"],
            product_ids=["prod_main"],
            previous_shot_id="S1",
            action="she discovers a hidden family note",
        ),
    ]
    shots[0].audio.dialogue_vn = "Con se khong bo cuoc dau."
    plan = _minimal_plan(shots, duration_s=300, runtime_structure=runtime)
    plan.continuity_bible.storytelling_meta = {
        **(plan.continuity_bible.storytelling_meta or {}),
        "user_idea": (
            "Tao video 5 phut phim ngan ve co gai ban banh mi o Sai Gon "
            "phat hien bi mat gia dinh, cinematic, co thoai tieng Viet."
        ),
        "niche": "drama",
        "niche_playbook": {"niche": "drama"},
    }
    report = build_autonomous_preflight_report(
        plan=plan,
        resolved_model="seedance_2_0_fast_ref",
        target_market="vn",
        target_platform="tiktok",
        reference_counts={"images": 0, "videos": 0, "audios": 0},
    )
    _assert(report["script_asset_sop"]["enabled"] is True, "preflight should expose script asset SOP")
    _assert("script_asset_sop" in report["warnings"], "missing long-form anchors should warn before render")
    missing = report["script_asset_sop"]["missing_before_top_tier"]
    _assert("character_visual_anchor" in missing, "SOP should require character visual anchor")
    _assert("location_visual_anchor" in missing, "SOP should require location visual anchor")
    _assert("consented_voice_or_tts_audio" in missing, "dialogue plan should require voice/audio anchor")


def test_cross_shot_diagnostic_passes_coherent_sequence() -> None:
    shots = [
        _shot(
            shot_id="S1",
            index=0,
            start_s=0,
            purpose="hook",
            character_ids=["char_main"],
            product_ids=["prod_main"],
            reference_indices=[0, 1],
            action="shows the final visible result before explaining the test",
            camera_shot="ECU",
            camera_movement="push-in",
        ),
        _shot(
            shot_id="S2",
            index=1,
            start_s=8,
            purpose="demo",
            character_ids=["char_main"],
            product_ids=["prod_main"],
            reference_indices=[0, 1],
            previous_shot_id="S1",
            action="tests the product in hand with a close macro demonstration",
            camera_shot="CU",
            camera_movement="handheld",
        ),
        _shot(
            shot_id="S3",
            index=2,
            start_s=16,
            purpose="payoff",
            character_ids=["char_main"],
            product_ids=["prod_main"],
            reference_indices=[0, 1],
            previous_shot_id="S2",
            action="reveals the before after proof and gives a soft verdict",
            camera_shot="MS",
            camera_movement="static",
        ),
    ]
    plan = _minimal_plan(shots, duration_s=24)
    diagnostic = diagnose_cross_shot_coherence(plan=plan)
    _assert(diagnostic["status"] in {"pass", "warn"}, f"coherent short sequence should not fail: {diagnostic}")
    _assert(diagnostic["score"] >= 78, "coherent sequence should score at least 78")


def test_cross_shot_diagnostic_fails_flat_long_form_without_handoffs() -> None:
    runtime = _valid_long_form_runtime_structure()
    shots = [
        _shot(
            shot_id=f"S{i + 1}",
            index=i,
            start_s=i * 8,
            purpose="setup",
            character_ids=["char_main"],
            product_ids=["prod_main"],
            reference_indices=[0],
            action="keeps doing generic stuff",
            camera_shot="MS",
            camera_movement="static",
            previous_shot_id=None,
        )
        for i in range(6)
    ]
    plan = _minimal_plan(shots, duration_s=300, runtime_structure=runtime)
    diagnostic = diagnose_cross_shot_coherence(plan=plan)
    _assert(diagnostic["status"] == "fail", f"flat long-form without handoffs should fail: {diagnostic}")
    issues = " ".join(diagnostic["top_issues"])
    _assert("missing_adjacent_handoff" in issues, "diagnostic should flag missing adjacent handoffs")
    _assert("repeated_camera_language_run" in issues, "diagnostic should flag repeated camera language")
    _assert("final_shot_not_payoff" in issues, "diagnostic should flag missing payoff")


def test_autonomous_preflight_includes_cross_shot_diagnostic() -> None:
    runtime = _valid_long_form_runtime_structure()
    shots = [
        _shot(
            shot_id=f"S{i + 1}",
            index=i,
            start_s=i * 8,
            purpose="setup",
            character_ids=["char_main"],
            product_ids=["prod_main"],
            reference_indices=[0],
            action="keeps doing generic stuff",
            camera_shot="MS",
            camera_movement="static",
        )
        for i in range(6)
    ]
    plan = _minimal_plan(shots, duration_s=300, runtime_structure=runtime)
    report = build_autonomous_preflight_report(
        plan=plan,
        resolved_model="seedance_2_0_fast_ref",
        target_market="vn",
        target_platform="tiktok",
        reference_counts={"images": 1, "videos": 0, "audios": 0},
    )
    _assert("cross_shot_diagnostic" in report["hard_failures"], "preflight should hard-fail bad long-form cross-shot flow")
    _assert(report["cross_shot_diagnostic"]["status"] == "fail", "preflight should expose cross-shot diagnostic")


def test_producer_story_critic_passes_proof_driven_ugc_plan() -> None:
    shots = [
        _shot(shot_id="S1", index=0, start_s=0, purpose="hook", product_ids=["prod_main"], action="shows the final visible result before explaining the test"),
        _shot(shot_id="S2", index=1, start_s=8, purpose="demo", product_ids=["prod_main"], action="tests the product in hand with a close macro demonstration"),
        _shot(shot_id="S3", index=2, start_s=16, purpose="proof", product_ids=["prod_main"], action="reveals the before after proof and gives a soft verdict"),
    ]
    plan = _minimal_plan(shots, duration_s=24)
    critic = critique_producer_story(plan=plan, target_market="vn", target_platform="tiktok")
    _assert(critic["status"] in {"pass", "warn"}, f"proof-driven plan should not fail story critic: {critic}")
    _assert(critic["score"] >= 78, "proof-driven plan should score at least 78")


def test_producer_story_critic_fails_vague_no_payoff_plan() -> None:
    shots = [
        _shot(shot_id="S1", index=0, start_s=0, purpose="setup", action="does something nice"),
        _shot(shot_id="S2", index=1, start_s=8, purpose="setup", action="keeps doing generic stuff"),
        _shot(shot_id="S3", index=2, start_s=16, purpose="setup", action="ends"),
    ]
    plan = _minimal_plan(shots, duration_s=24)
    critic = critique_producer_story(plan=plan, target_market="", target_platform="unknown")
    _assert(critic["status"] == "fail", f"vague no-payoff plan should fail story critic: {critic}")
    _assert("first_shot_lacks_explicit_hook" in critic["top_issues"], "critic should flag missing hook")
    _assert("final_shot_lacks_payoff_or_takeaway" in critic["top_issues"], "critic should flag missing payoff")


def test_distribution_package_localizes_tiktok_vn() -> None:
    pkg = build_distribution_package(
        target_platform="tiktok",
        target_market="vn",
        niche="ugc_review",
        duration_s=30,
        caption_vn="Kết quả này hơi bất ngờ. Test thật mới biết.",
        caption_en="This result was surprising. Real test first.",
        hashtags_vn=["xuhuong", "review", "tiktokshop", "lamdep", "fyp", "testthat"],
        hashtags_en=["review", "viral", "producttest"],
        market_playbook={"posting_hint": "TikTok VN 19:00-22:00", "claim_style": "visible proof"},
    )
    _assert(pkg["target_platform"] == "tiktok", "platform should normalize to tiktok")
    _assert(pkg["target_market"] == "vn", "market should stay VN")
    _assert(pkg["caption_primary"].startswith("Kết quả"), "VN market should use Vietnamese primary caption")
    _assert("product/result" in pkg["cover_frame_cue"], "UGC cover should emphasize product/result")
    _assert(pkg["checks"][0]["status"] == "pass", "caption length should pass")


def test_distribution_package_youtube_long_uses_long_form_packaging() -> None:
    pkg = build_distribution_package(
        target_platform="youtube_long",
        target_market="global",
        niche="education",
        duration_s=600,
        caption_vn="Một bài giải thích ngắn.",
        caption_en="A practical explanation with a clear visual takeaway.",
        hashtags_vn=["giaithich", "hoctap"],
        hashtags_en=["education", "explainer", "aitools", "tutorial"],
        market_playbook={"claim_style": "safe educational framing"},
    )
    _assert(pkg["target_platform"] == "youtube_long", "long platform should stay youtube_long")
    _assert(pkg["runtime_bucket"] == "short_film", "600s should package as short_film")
    _assert("chapters" in pkg["description_hint"].lower(), "long-form description should include chapters")
    _assert("thumbnail" in " ".join(pkg["platform_notes"]).lower(), "long-form package should mention thumbnail")


def test_autonomous_asset_pin_status_lifecycle() -> None:
    asset = assets_store.create_asset(
        type="character",
        name="Test autonomous creator anchor",
        image_url="https://example.com/test-creator.png",
        payload={"source": "backend_smoke_test"},
        tags="autonomous,test",
    )
    pin = autonomous_asset_pins.create_pin(
        asset_id=asset["id"],
        role="character_anchor",
        target_market="vn",
        niche="ugc_review",
        series_key="smoke_series",
        priority=88,
        status="active",
        notes="backend smoke test",
    )
    try:
        active = autonomous_asset_pins.list_pins(status="active", target_market="vn", niche="ugc_review", limit=10)
        _assert(any(row["id"] == pin["id"] for row in active), "new active pin should appear in active filtered list")
        series_filtered = autonomous_asset_pins.list_pins(status="active", series_key="smoke_series", limit=10)
        _assert(any(row["id"] == pin["id"] for row in series_filtered), "pin should appear in series filtered list")
        paused = autonomous_asset_pins.update_pin(pin["id"], status="paused", notes="paused by smoke test")
        _assert(paused and paused["status"] == "paused", "pin should update to paused")
        active_after_pause = autonomous_asset_pins.list_pins(status="active", target_market="vn", niche="ugc_review", limit=10)
        _assert(not any(row["id"] == pin["id"] for row in active_after_pause), "paused pin should leave active list")
        restored = autonomous_asset_pins.update_pin(
            pin["id"],
            status="active",
            role="style_reference",
            priority=42,
            series_key="smoke_series_v2",
        )
        _assert(restored and restored["status"] == "active", "pin should reactivate")
        _assert(restored["role"] == "style_reference", "pin role should update")
        _assert(restored["priority"] == 42, "pin priority should update")
        _assert(restored["series_key"] == "smoke_series_v2", "pin series should update")
    finally:
        autonomous_asset_pins.delete_pin(pin["id"])
        assets_store.delete_asset(asset["id"])


def test_auto_select_approved_asset_pins_prefers_series_and_priority() -> None:
    character = assets_store.create_asset(
        type="character",
        name="Series creator anchor",
        image_url="https://example.com/series-creator.png",
        payload={"source": "backend_smoke_test"},
        tags="autonomous,ugc_review,vn,creator",
    )
    product = assets_store.create_asset(
        type="product",
        name="Generic product anchor",
        image_url="https://example.com/generic-product.png",
        payload={"source": "backend_smoke_test"},
        tags="autonomous,ugc_review,vn,product",
    )
    series_pin = autonomous_asset_pins.create_pin(
        asset_id=character["id"],
        role="character_anchor",
        target_market="vn",
        niche="ugc_review",
        series_key="launch_series",
        priority=70,
        status="active",
    )
    product_pin = autonomous_asset_pins.create_pin(
        asset_id=product["id"],
        role="product_hero",
        target_market="vn",
        niche="ugc_review",
        priority=95,
        status="active",
    )
    try:
        selected = select_approved_asset_pins_for_render(
            user_idea="Vietnamese creator reviews the product in a launch series",
            niche="ugc_review",
            target_market="vn",
            series_key="launch_series",
            explicit_pin_ids=[],
            limit=2,
        )
        ids = selected["auto_selected_pin_ids"]
        _assert(series_pin["id"] in ids, "series pin should be auto-selected")
        _assert(product_pin["id"] in ids, "high-priority product pin should be auto-selected")
        first = selected["selected"][0]
        _assert(first["pin_id"] == series_pin["id"], "series match should outrank generic priority")
    finally:
        autonomous_asset_pins.delete_pin(series_pin["id"])
        autonomous_asset_pins.delete_pin(product_pin["id"])
        assets_store.delete_asset(character["id"])
        assets_store.delete_asset(product["id"])


def test_all_canonical_niche_benchmarks_have_valid_production_decisions() -> None:
    cases = list_benchmark_cases()
    _assert(len(cases) >= 23, f"expected at least 23 benchmark cases, got {len(cases)}")
    seen: set[str] = set()
    for case in cases:
        niche = case["niche"]
        seen.add(niche)
        data = _decision(
            user_idea=case["idea"],
            target_market=case.get("target_market") or "auto",
            duration_hint_s=case.get("duration_hint_s"),
            reference_counts=_reference_counts(case.get("reference_strategy") or []),
            niche_hint=niche,
        )
        decision = data["decision"]
        duration = int(case.get("duration_hint_s") or 30)
        seedance = decision["seedance_contract"]

        _assert(decision["niche"] == niche, f"{niche}: decision changed niche to {decision['niche']}")
        _assert(data["benchmark_reference"]["case_id"] == f"bench_{niche}", f"{niche}: benchmark reference mismatch")
        _assert(seedance["single_call_max_s"] == 15, f"{niche}: Seedance single-call cap must stay 15s")
        _assert(seedance["shot_duration_s"] == "4-15", f"{niche}: Seedance shot duration contract changed")
        _assert(all(seedance["input_refs_fit"].values()), f"{niche}: canonical refs exceed Seedance caps")
        _assert(bool(decision["graph_required"]) == (duration > 180), f"{niche}: graph requirement mismatch")
        _assert(len(data["workflow_steps"]) >= 9, f"{niche}: workflow must expose producer-to-editor steps")
        _assert(data["qa_gates"], f"{niche}: QA gates missing")

        if niche in _REVIEW_REQUIRED:
            _assert(decision["readiness"] == "review_required", f"{niche}: must remain review_required")
            _assert(
                any("safety review" in gate for gate in data["qa_gates"]),
                f"{niche}: safety QA gate missing",
            )
            _assert(
                decision["benchmark_required_before_top_tier_claim"] is True,
                f"{niche}: review niche must be benchmark-gated",
            )

        if niche in _PREMIUM_VISUAL_NICHES:
            _assert(
                decision["primary_model_route"]["primary_visual_model"] == "seedance_2_0_ref",
                f"{niche}: premium visual niche should route to Seedance 2.0 Reference",
            )

    _assert(len(seen) == len(cases), "benchmark cases should be unique by niche")


def test_benchmark_promotion_policy_locks_without_real_evidence() -> None:
    policy = build_benchmark_promotion_policy(results=[])
    _assert(policy["summary"]["promoted_route_count"] == 0, "no evidence must promote zero routes")
    candidates = {m["model_key"]: m for m in policy["candidate_models"]}
    infinitetalk = candidates["atlascloud/infinitetalk"]
    _assert(infinitetalk["eligible_for_auto_routing"] is False, "InfiniteTalk must stay locked without evidence")
    _assert("needs_2_approved_outputs_has_0" in infinitetalk["missing_reasons"], "missing count reason expected")
    _assert(candidates["atlascloud/framepack"]["eligible_for_auto_routing"] is False, "FramePack must stay locked without evidence")
    _assert(candidates["bytedance/seedream-v4/sequential"]["eligible_for_auto_routing"] is False, "Seedream reference-pack route must stay locked without evidence")


def test_benchmark_contract_tracks_current_atlas_candidate_routes() -> None:
    contract = build_autonomous_benchmark_contract()
    _assert(
        contract["global_pass_policy"]["required_evidence_keys"] == REQUIRED_EVIDENCE_KEYS,
        "benchmark contract should reuse canonical evidence validator keys",
    )
    _assert(
        "production_graph_snapshot" in contract["global_pass_policy"]["required_evidence_keys"],
        "benchmark contract should require graph evidence for top-tier claims",
    )
    candidates = {
        item["model"]: item
        for item in contract["model_candidate_tests"]
    }
    expected = {
        "atlascloud/infinitetalk",
        "atlascloud/multitalk",
        "atlascloud/mmaudio-v2",
        "bytedance/lipsync/audio-to-video",
        "atlascloud/wan-2.2-turbo/image-to-video",
        "atlascloud/framepack",
        "bytedance/seedream-v4/sequential",
        "atlascloud_catalog:veo_3_1_lite",
        "atlascloud_catalog:vidu_q3_reference_to_video",
    }
    missing = sorted(expected - set(candidates))
    _assert(not missing, f"benchmark contract missing current Atlas candidates: {missing}")
    _assert(
        "Seedance 2.0 Reference-to-Video for quad-modal cinematic/product shots"
        in candidates["atlascloud_catalog:vidu_q3_reference_to_video"]["must_not_replace"],
        "Vidu challenger must not replace Seedance without route evidence",
    )
    _assert(
        "cheap fixed-5s motion probe" in candidates["atlascloud/wan-2.2-turbo/image-to-video"]["route_policy_after_pass"],
        "Wan 2.2 Turbo policy should stay limited to cheap motion probes",
    )


def test_benchmark_plan_prioritizes_long_form_and_launch_evidence() -> None:
    plan = build_autonomous_benchmark_plan(limit=8, focus="launch", results=[])
    selected = plan["selected_runs"]
    _assert(selected, "benchmark plan should select runs")
    case_ids = {item.get("case_id") for item in selected if item.get("kind") == "canonical_case"}
    _assert("bench_drama" in case_ids, "launch plan should include long-form drama proof")
    _assert(
        any("long_form_graph_proof" in item.get("why_now", []) for item in selected),
        "plan should explain long-form graph proof priority",
    )
    _assert(
        all((item.get("run_request") or {}).get("mode") == "dry_run" for item in selected),
        "benchmark plan run requests should default to dry_run",
    )
    _assert(plan["summary"]["stored_results_considered"] == 0, "test plan should use injected empty evidence")


def test_benchmark_plan_prioritizes_locked_model_candidates() -> None:
    plan = build_autonomous_benchmark_plan(limit=6, focus="model_candidates", results=[])
    models = [item.get("model_key") for item in plan["selected_runs"]]
    _assert("atlascloud/infinitetalk" in models, "model candidate plan should include InfiniteTalk")
    _assert("atlascloud/multitalk" in models, "model candidate plan should include MultiTalk")
    _assert("bytedance/lipsync/audio-to-video" in models, "model candidate plan should include LipSync")
    first = plan["selected_runs"][0]
    _assert(first["priority"] in {"P0", "P1"}, "top model candidate should be high priority")
    _assert(first["promotion_status"]["eligible_for_auto_routing"] is False, "candidates must stay locked without evidence")


def test_benchmark_promotion_policy_promotes_only_real_approved_outputs() -> None:
    evidence_pack = {
        "per_shot_prompts": [{"shot_id": "S1", "prompt": "presenter explains one idea"}],
        "seedance_prompt_formula": {
            "schema_version": "cinejelly.seedance_prompt_formula.v1",
            "formula": ["reference_jobs", "timeline", "action", "camera", "sound", "constraints"],
        },
        "reference_manifest": [{"tag": "@image_1", "role": "portrait"}],
        "model_route_per_shot": [{"shot_id": "S1", "model_key": "atlascloud/infinitetalk"}],
        "production_graph_snapshot": {"graph_id": "graph_education", "node_count": 1, "done_count": 1},
        "scene_memory_pack": {"scene_count": 1, "identity_anchors": ["creator face"]},
        "continuity_handoff_report": {"status": "pass", "required_handoff_count": 0},
        "seedance_segment_inspector": {"schema_version": "cinejelly.seedance_segment_inspector.v1", "all_segments_valid": True},
        "qa_frames": ["https://cdn.example.com/qa-frame-1.jpg"],
        "visual_reference_similarity_report": {"status": "pass", "average_best_similarity": 0.84},
        "semantic_quality_report": {"status": "pass", "score": 8.7},
        "text_artifact_report": "not_applicable_no_text_overlay",
        "audio_report": {"loudness_lufs": -16.0, "sync_status": "pass"},
        "identity_product_notes": "face identity stable across sampled frames",
        "benchmark_review_score": {"schema_version": "cinejelly.benchmark_review_score.v1", "promotion_ready": True, "weighted_score": 8.6},
        "accepted_minute_cost": {"cost_per_finished_minute_usd": 3.75, "includes_retries": True},
        "reviewer_notes": "approved without structural edits",
        "retry_count": 0,
    }
    base = {
        "case_id": "bench_education",
        "niche": "education",
        "target_market": "vn",
        "runtime_class": "short_film",
        "model_key": "atlascloud/infinitetalk",
        "status": "passed",
        "reviewer_decision": "approved",
        "qa_score": 8.4,
        "cost_usd": 1.25,
        "latency_s": 140.0,
    }
    locked = build_benchmark_promotion_policy(results=[
        {**base, "id": "stub_1", "output_url": "stub://benchmark/education", "evidence": evidence_pack},
        {**base, "id": "real_1", "output_url": "https://cdn.example.com/education-1.mp4"},
    ])
    _assert(locked["summary"]["promoted_route_count"] == 0, "stub output must not count toward promotion")
    _assert("missing_required_evidence_pack" in locked["locked_routes"][0]["missing_reasons"], "real output without evidence pack must stay locked")

    promoted = build_benchmark_promotion_policy(results=[
        {**base, "id": "real_1", "output_url": "https://cdn.example.com/education-1.mp4", "evidence": evidence_pack},
        {**base, "id": "real_2", "output_url": "https://cdn.example.com/education-2.mp4", "qa_score": 8.9, "evidence": evidence_pack},
    ])
    _assert(promoted["summary"]["promoted_route_count"] == 1, "two real approved outputs should promote one route")
    route = promoted["promoted_routes"][0]
    _assert(route["model_key"] == "atlascloud/infinitetalk", "promoted route model mismatch")
    _assert(route["niche"] == "education", "promoted route niche mismatch")
    candidate = next(m for m in promoted["candidate_models"] if m["model_key"] == "atlascloud/infinitetalk")
    _assert(candidate["eligible_for_auto_routing"] is True, "candidate model should become auto-routable after evidence")


def test_benchmark_evidence_validator_reports_precise_missing_fields() -> None:
    row = {
        "case_id": "bench_education",
        "niche": "education",
        "target_market": "vn",
        "runtime_class": "short_film",
        "model_key": "atlascloud/infinitetalk",
        "status": "passed",
        "reviewer_decision": "approved",
        "qa_score": 8.6,
        "output_url": "https://cdn.example.com/education.mp4",
        "evidence": {
            "per_shot_prompts": [{"shot_id": "S1", "prompt": "presenter explains"}],
        },
    }
    validation = validate_benchmark_result_evidence(row)
    _assert(validation["promotion_ready"] is False, "missing cost/latency/evidence should block promotion")
    _assert("missing_cost_usd" in validation["missing_reasons"], "validator should require cost")
    _assert("missing_latency_s" in validation["missing_reasons"], "validator should require latency")
    _assert("seedance_prompt_formula" in validation["missing_evidence_keys"], "validator should require prompt formula evidence")
    _assert("reference_manifest" in validation["missing_evidence_keys"], "validator should report missing evidence keys")


def test_benchmark_runner_adds_non_promotional_evidence_template() -> None:
    batch = run_autonomous_benchmark_batch(
        niches=["beauty"],
        mode="dry_run",
        limit=1,
    )
    row = batch["created"][0]
    try:
        evidence = row["evidence"]
        template = evidence["promotion_evidence_template"]
        _assert(template["schema_version"] == "cinejelly.benchmark_evidence_template.v1", "template schema missing")
        _assert("per_shot_prompts" in template["required_evidence_keys"], "template should list required evidence keys")
        _assert("seedance_prompt_formula" in template["required_evidence_keys"], "template should require prompt formula keys")
        _assert("per_shot_prompts" not in evidence, "template must not fill real evidence keys")
        validation = validate_benchmark_result_evidence(row)
        _assert(validation["promotion_ready"] is False, "dry-run template must not count as promotion evidence")
    finally:
        autonomous_benchmark_store.delete_result(row["id"])


def test_artifact_evidence_pack_autofills_only_proven_fields() -> None:
    artifact = {
        "job_id": "job_smoke",
        "plan_id": "plan_smoke",
        "request_meta": {
            "target_market": "vn",
            "resolved_model": "bytedance/seedance-2.0-fast/reference-to-video",
            "reference_image_urls": ["https://cdn.example.com/creator.png"],
            "reference_audio_urls": ["https://cdn.example.com/voice.mp3"],
        },
        "production_decision": {
            "decision": {
                "niche": "beauty",
                "target_market": "vn",
                "runtime_class": "short",
                "primary_model_route": {"primary_visual_model": "seedance_2_0_ref"},
            },
            "seedance_prompt_formula": {
                "schema_version": "cinejelly.seedance_prompt_formula.v1",
                "formula": ["reference_jobs", "timeline", "action", "camera", "sound", "constraints"],
                "niche_template": {
                    "story_intent": "prove one beauty product result visibly",
                    "action": "show one tactile lipstick interaction",
                    "camera": "macro/detail/hero framing",
                },
            },
        },
        "shot_list": [
            {
                "shot_id": "S1",
                "purpose": "hook",
                "duration_s": 8,
                "dynamic_description": "Macro lipstick texture reveal on a Saigon cafe table.",
                "visual": {
                    "subject": "Vietnamese creator with lipstick",
                    "action": "swipes lipstick and reacts",
                    "camera_shot": "macro close-up",
                    "camera_movement": "slow push-in",
                    "background": "warm cafe table",
                },
                "audio": {"caption_on_screen": "Test thật mới biết"},
                "continuity": {"reference_indices": [0]},
            }
        ],
    }
    job_record = {
        "job_id": "job_smoke",
        "status": "done",
        "output_url": "https://cdn.example.com/final.mp4",
        "render_quality": [
            {
                "status": "pass",
                "score": 8.3,
                "criteria": {
                    "shot_id": "S1",
                    "frame_samples": {
                        "frames": [
                            {
                                "url": "https://cdn.example.com/qa/job_smoke/S1/frame.jpg",
                                "timestamp_s": 2.0,
                                "persist_status": "ok",
                            }
                        ]
                    },
                    "media_probe": {
                        "status": "pass",
                        "duration_s": 8.0,
                        "audio_stream_count": 1,
                    },
                    "visual_reference_probe": {
                        "status": "pass",
                        "average_best_similarity": 0.82,
                    },
                },
            }
        ],
        "retry_plan": {"summary": {"retry_count": 0}},
        "dynamic_keyframe_memory": {
            "schema_version": "cinejelly.dynamic_keyframe_memory.v1",
            "status": "partially_populated",
            "scene_count": 1,
            "shot_count": 1,
            "memory_bank": {
                "rendered_anchors": [
                    {
                        "shot_id": "S1",
                        "scene_id": "SC01",
                        "video_url": "https://cdn.example.com/s1.mp4",
                        "last_frame_url": "https://cdn.example.com/s1-last.jpg",
                    }
                ],
                "bridge_anchors": [],
            },
            "promotion_gate": {"top_tier_claim_allowed": False},
        },
    }
    draft = build_benchmark_result_draft_from_artifact(artifact, job_record=job_record)
    evidence = draft["evidence"]
    _assert(evidence["per_shot_prompts"][0]["shot_id"] == "S1", "artifact pack should include shot prompt evidence")
    _assert(evidence["seedance_prompt_formula"]["schema_version"] == "cinejelly.seedance_prompt_formula.v1", "artifact pack should include prompt formula")
    _assert(evidence["reference_manifest"]["images"][0]["tag"] == "@image_1", "artifact pack should include reference manifest")
    _assert(evidence["model_route_per_shot"][0]["model_key"], "artifact pack should include model route")
    _assert(evidence["dynamic_keyframe_memory"]["rendered_anchor_count"] == 1, "artifact pack should include dynamic memory evidence")
    _assert(evidence["qa_frames"][0]["url"].endswith("frame.jpg"), "artifact pack should include persisted QA frames")
    _assert(
        evidence["agent_readable_production_report"]["production_report_url"].endswith("/job_smoke/production-report"),
        "artifact pack should link agent-readable production report",
    )
    _assert(evidence["retry_count"] == 0, "artifact pack should include retry count")
    _assert("reviewer_notes" not in evidence, "artifact pack must not invent reviewer approval")
    _assert(
        draft["evidence_pack"]["production_report"]["benchmark_evidence_pack_url"].endswith("/job_smoke/benchmark-evidence-pack"),
        "evidence pack should expose benchmark evidence pack URL",
    )

    row = {
        **draft,
        "status": "passed",
        "reviewer_decision": "approved",
        "qa_score": 8.6,
        "cost_usd": 0.42,
        "latency_s": 72.0,
    }
    validation = validate_benchmark_result_evidence(row)
    _assert(validation["promotion_ready"] is False, "missing real reviewer notes must block promotion")
    _assert("reviewer_notes" in validation["missing_evidence_keys"], "validator should still require reviewer notes")


def test_agent_readable_production_report_summarizes_artifact_for_resume() -> None:
    artifact = {
        "job_id": "job_report_smoke",
        "plan_id": "plan_report_smoke",
        "request_meta": {
            "reference_image_urls": ["https://cdn.example.com/creator.png"],
            "reference_video_urls": ["https://cdn.example.com/camera.mp4"],
            "reference_audio_urls": ["https://cdn.example.com/voice.mp3"],
            "autonomous_preflight": {
                "status": "pass",
                "render_allowed": True,
                "warnings": ["benchmark_required_before_top_tier"],
            },
        },
        "production_decision": {
            "decision": {
                "niche": "drama",
                "target_market": "vn",
                "runtime_class": "short_film",
                "target_duration_s": 300,
                "execution_mode": "graph_executor_long_form_when_flagged",
                "graph_required": True,
                "primary_model_route": {"primary_visual_model": "seedance_2_0_fast_ref"},
                "dialogue_route_policy": {"dialogue_candidate": "atlascloud/multitalk"},
                "benchmark_required_before_top_tier_claim": True,
            },
            "seedance_reference_allocation": {
                "image_role_plan": [{"tag": "@image_1", "role": "character_identity", "job": "lock face/outfit"}],
                "video_role_plan": [{"tag": "@video_1", "role": "camera_motion", "job": "guide handheld pacing"}],
                "audio_role_plan": [{"tag": "@audio_1", "role": "dialogue_voice", "job": "guide Vietnamese speech tone"}],
            },
            "seedance_segment_inspector": {
                "mode": "long_form_scene_units",
                "estimated_total_units": 25,
                "unit_contract": {"duration_s": [4, 15]},
            },
            "seedance_prompt_formula": {
                "schema_version": "cinejelly.seedance_prompt_formula.v1",
                "formula": ["reference_jobs", "timeline", "action", "camera", "sound", "constraints"],
            },
        },
        "runtime_structure": {"runtime_class": "short_film", "target_duration_s": 300, "scene_count": 5},
        "production_graph": {
            "graph_id": "graph_report_smoke",
            "summary": {"node_count": 42, "edge_count": 58, "scene_count": 5, "chunk_count": 5},
        },
        "producer_strategy": {"risk_level": "medium"},
        "shot_list": [
            {
                "shot_id": "S1",
                "purpose": "opening hook",
                "duration_s": 8,
                "visual": {
                    "subject": "young woman at banh mi cart",
                    "action": "discovers a hidden family photo",
                    "camera_shot": "medium handheld",
                },
                "audio": {"caption_on_screen": "Bi mat nam trong o banh mi nay"},
                "continuity": {"reference_indices": [0], "previous_shot_id": None},
            }
        ],
    }
    report = load_report(
        "job_report_smoke",
        job_record={
            "job_id": "job_report_smoke",
            "status": "done",
            "output_url": "https://cdn.example.com/final.mp4",
            "render_quality": [{"status": "pass"}],
            "retry_plan": {"summary": {"retry_count": 1}},
        },
    )
    _assert(report is None, "load_report should not invent a report without persisted artifact")

    from core import production_artifacts
    original_loader = production_artifacts.load_snapshot
    try:
        production_artifacts.load_snapshot = lambda job_id: artifact if job_id == "job_report_smoke" else None  # type: ignore[assignment]
        report = production_artifacts.load_report(
            "job_report_smoke",
            job_record={
                "job_id": "job_report_smoke",
                "status": "done",
                "output_url": "https://cdn.example.com/final.mp4",
                "render_quality": [{"status": "pass"}],
                "retry_plan": {"summary": {"retry_count": 1}},
            },
        )
    finally:
        production_artifacts.load_snapshot = original_loader  # type: ignore[assignment]

    _assert(report is not None, "artifact report should be buildable from a snapshot")
    _assert(report["schema_version"] == "cinejelly.agent_readable_production_report.v1", "report schema missing")
    _assert(report["storyboard_report"]["sample_shots"][0]["shot_id"] == "S1", "report should expose storyboard shots")
    _assert(report["design_report"]["reference_counts"]["images"] == 1, "report should summarize references")
    _assert(report["design_report"]["segment_preview"]["estimated_total_units"] == 25, "report should expose Seedance unit count")
    _assert(report["graph_report"]["node_count"] == 42, "report should expose graph node count")
    _assert(report["qa_report"]["retry_count"] == 1, "report should expose retry count")
    _assert(report["qa_report"]["output_url"] == "https://cdn.example.com/final.mp4", "report should preserve real HTTP output URL")
    _assert(report["qa_report"]["local_output_path"] == "", "report should not mark HTTP output as local path")
    _assert(report["benchmark_report"]["top_tier_claim_allowed"] is False, "report should keep benchmark claim gated")

    try:
        production_artifacts.load_snapshot = lambda job_id: artifact if job_id == "job_report_smoke" else None  # type: ignore[assignment]
        local_report = production_artifacts.load_report(
            "job_report_smoke",
            job_record={
                "job_id": "job_report_smoke",
                "status": "done",
                "output_url": "file:///tmp/local-final.mp4",
                "output_path": "C:/tmp/local-final.mp4",
            },
        )
    finally:
        production_artifacts.load_snapshot = original_loader  # type: ignore[assignment]

    _assert(local_report is not None, "local report should still be buildable")
    _assert(local_report["qa_report"]["output_url"] is None, "local file URL must not be reported as real output_url")
    _assert(local_report["qa_report"]["local_output_path"] == "C:/tmp/local-final.mp4", "local path should remain operator-only metadata")


def test_autonomous_capability_matrix_explains_niche_runtime_fit() -> None:
    matrix = build_autonomous_capability_matrix()
    _assert(matrix["verdict"]["top_tier_claim_allowed"] is False, "capability matrix must not claim top-tier without evidence")
    _assert("ugc_review" in matrix["best_today"], "UGC review should be a best-today niche")
    _assert("medical_wellness" in matrix["review_required"], "medical wellness should remain review-required")
    drama = next(row for row in matrix["niches"] if row["niche"] == "drama")
    _assert(drama["long_form_policy"]["graph_required_after_s"] is not None, "drama long-form should require graph routing")
    _assert(len(drama["runtime_routes"]) == 4, "capability matrix should probe short through episode runtimes")
    food = next(row for row in matrix["niches"] if row["niche"] == "food")
    refs = food["recommended_reference_contract"]["optimal"]
    _assert(refs["images"] >= 3 and refs["videos"] >= 1, "high-readiness sensory niches should recommend multimodal refs")
    _assert(
        "Seedance prompt formula used for the accepted route" in matrix["evidence_required_before_top_tier"],
        "capability matrix should require prompt formula evidence",
    )
    _assert(
        matrix["required_evidence_keys"] == REQUIRED_EVIDENCE_KEYS,
        "capability matrix should expose canonical evidence validator keys",
    )


def test_autonomous_production_audit_keeps_top_tier_claim_evidence_gated() -> None:
    audit = build_autonomous_production_audit()
    verdict = audit["executive_verdict"]
    _assert(verdict["top_tier_production_grade"] is False, "audit must not claim top-tier without real benchmark evidence")
    operator = audit["operator_summary"]
    _assert("not evidence-proven" in operator["plain_answer"], "operator summary should keep top-tier claim evidence-gated")
    _assert(operator["market_answer"]["default"] == "Auto should remain the default.", "operator summary should answer market default")
    _assert(
        any(item["duration"] == "5-10m" and item["status"] == "benchmark_gated" for item in operator["duration_policy"]),
        "operator summary should explain 5-10m benchmark gating",
    )
    _assert(operator["what_user_should_provide"], "operator summary should list user input guidance")
    _assert(audit["workflow_in_one_run"], "audit should explain the one-run workflow")
    _assert("ugc_review" in audit["best_niches_now"], "audit should expose current best niches")
    _assert("medical_wellness" in audit["review_required_niches"], "audit should expose review-required niches")
    long_form = audit["long_form_doctrine"]
    _assert("Never ask one video model" in long_form["rule"], "audit should preserve long-form decomposition rule")
    _assert("4-15s Seedance render units" in long_form["implementation"], "audit should require Seedance-sized render units")
    _assert(
        audit["input_upgrade_policy"]["schema"] == "cinejelly.autonomous_input_upgrade_plan.v1",
        "audit should expose autonomous input upgrade policy",
    )
    evidence = audit["evidence_blocking_top_tier_claim"]
    _assert(evidence["benchmark_results"] == 0, "local smoke store should have no approved real benchmark evidence")
    _assert("real AtlasCloud output URLs per canonical benchmark case" in evidence["required_evidence"], "audit should list concrete evidence gates")
    _assert("Seedance prompt formula used for the accepted route" in evidence["required_evidence"], "audit should require formula evidence")
    _assert(audit["competitive_research"]["implementation_score"]["score"] >= 60, "audit should expose competitive research score")
    _assert(
        len(audit["top_tier_maturity_ladder"]) >= 6,
        "audit should expose a top-tier maturity ladder",
    )
    _assert(
        audit["top_tier_maturity_ladder"][-1]["status"] == "research_gated",
        "30-minute episode tier should stay research gated",
    )
    _assert(audit["external_sources_reviewed"], "audit should expose reviewed external sources")
    _assert("beauty" in audit["niche_launch_matrix"]["tiers"]["sell_first"], "audit should expose sell-first launch niches")
    _assert(audit["niche_playbook_catalog"]["summary"]["niche_count"] >= 20, "audit should expose all-niche playbook summary")
    _assert(audit["top_tier_completion_gate"]["verdict"]["top_app_parity_proven"] is False, "audit should expose strict top-tier gate")
    _assert(audit["paid_benchmark_manifest"]["summary"]["paid_run_count"] >= 2, "audit should expose paid benchmark manifest summary")
    _assert(audit["benchmark_review_rubric"]["dimension_count"] >= 8, "audit should expose benchmark review rubric")


def test_autonomous_operator_brief_answers_workflow_niche_and_gap_questions() -> None:
    brief = build_autonomous_operator_brief()
    _assert(brief["schema_version"] == "cinejelly.autonomous_operator_brief.v1", "operator brief schema missing")
    _assert(brief["top_tier_proven"] is False, "operator brief must not claim top-tier without evidence")
    _assert("not evidence-proven" in brief["plain_answer"], "brief should keep top-tier status evidence-gated")
    _assert(
        brief["top_app_comparison"]["verdict"] == "architecture_shape_close_but_not_output_proven",
        "brief should compare against leading production apps without overclaiming",
    )
    _assert(
        "Seedance 2.0 quad-modal reference routing" in brief["top_app_comparison"]["matches_top_apps_on"],
        "brief should explain which top-app patterns are already matched",
    )
    _assert(len(brief["workflow"]) >= 8, "brief should expose the current autonomous workflow steps")
    _assert(brief["workflow_guide_summary"]["schema_version"] == "cinejelly.autonomous_workflow_niche_guide.v1", "brief should include workflow guide summary")
    _assert(brief["workflow_guide_summary"]["workflow_step_count"] >= 8, "brief guide summary should count workflow stages")
    _assert(brief["workflow_guide_summary"]["duration_strategy_count"] >= 4, "brief guide summary should count duration strategies")
    _assert(len(brief["production_workflow_steps"]) >= 8, "brief should expose source-backed stage details")
    _assert("ugc_review" in brief["best_niches_now"], "brief should expose best-current niches")
    _assert("medical_wellness" in brief["review_required_niches"], "brief should expose review-required niches")
    _assert("beauty" in brief["niche_fit_table"]["sell_first"], "brief should expose sell-first niche posture")
    _assert(brief["niche_audit_summary"]["niche_count"] >= 23, "brief should expose live all-niche audit summary")
    _assert(brief["niche_audit_summary"]["long_graph_required"] == brief["niche_audit_summary"]["niche_count"], "brief should preserve long-form graph policy")
    _assert(brief["niche_audit_summary"]["top_tier_claim_allowed"] is False, "brief should keep all-niche top-tier claim gated")
    _assert(brief["market_audit_summary"]["auto_default_recommended"] is True, "brief should expose live market audit default")
    _assert(brief["market_audit_summary"]["model_choice_hidden"] is True, "brief should keep market guidance separate from model picking")
    _assert(brief["market_audit_summary"]["top_tier_claim_allowed"] is False, "brief market audit should stay evidence gated")
    _assert(
        any(item["duration"] == "5-10m" and item["status"] == "benchmark_gated" for item in brief["duration_policy"]),
        "brief should explain long-form benchmark gating",
    )
    _assert(brief["market_policy"]["default"] == "Auto should remain the default.", "brief should answer market default")
    _assert(
        any("infinitetalk" in item.lower() for item in brief["model_policy"]["vn_dialogue_priority"]),
        "brief should preserve Vietnamese dialogue benchmark priority",
    )
    _assert(
        any(item.get("rule") == "seedance_unit_length" for item in brief["model_policy"]["source_backed_model_rules"]),
        "brief should expose source-backed Seedance unit policy",
    )
    _assert(
        any("CINEJELLY_ENABLE_GRAPH_LONG_FORM" in item for item in brief["next_upgrade_order"]),
        "brief should give the graph-mode benchmark step",
    )
    _assert(
        "/api/v1/director/jobs/{job_id}/production-report" in brief["evidence_endpoints"],
        "brief should point reviewers to production report evidence",
    )
    _assert(
        "/api/v1/director/autonomous/workflow-niche-guide" in brief["evidence_endpoints"],
        "brief should expose workflow niche guide endpoint",
    )


def test_autonomous_workflow_niche_guide_explains_current_state_without_overclaiming() -> None:
    guide = build_autonomous_workflow_niche_guide()
    _assert(guide["schema_version"] == "cinejelly.autonomous_workflow_niche_guide.v1", "workflow niche guide schema missing")
    _assert(guide["current_position"]["ui_mode"] == "autonomous_director_only", "guide should preserve autonomous-only UI contract")
    _assert(guide["current_position"]["top_tier_proven"] is False, "guide must not claim top-tier without evidence")
    _assert(len(guide["workflow_steps"]) >= 8, "guide should expose end-to-end workflow steps")
    _assert(len(guide["duration_strategy"]) >= 4, "guide should expose short through episode duration strategy")
    _assert("beauty" in guide["niche_fit"]["sell_first"], "guide should expose sell-first niches")
    _assert("medical_wellness" in guide["niche_fit"]["review_locked"], "guide should expose review-locked niches")
    cards = guide["niche_fit"]["cards"]
    _assert(len(cards) >= 20, "guide should expose niche cards for supported niches")
    _assert(cards[0]["launch_tier"] == "sell_first", "guide niche cards should prioritize sell-first niches")
    beauty_card = next(card for card in cards if card["niche"] == "beauty")
    _assert(beauty_card["primary_visual_model"] == "seedance_2_0_ref", "beauty card should show premium Seedance route")
    _assert("top-tier marketing claim" in beauty_card["benchmark_before"], "beauty card should keep premium claim benchmark-gated")
    medical_card = next(card for card in cards if card["niche"] == "medical_wellness")
    _assert(medical_card["launch_tier"] == "review_locked", "medical card should stay review locked")
    scenarios = {row["id"]: row for row in guide["scenario_route_examples"]}
    _assert(scenarios["vn_beauty_short"]["auto_route_allowed"] is True, "VN beauty short should be auto-route eligible")
    _assert(scenarios["vn_beauty_short"]["primary_visual_model"] == "seedance_2_0_ref", "VN beauty should use premium Seedance visual route")
    _assert(scenarios["global_saas_launch"]["niche"] == "app_saas", "SaaS scenario should route to app_saas")
    _assert(scenarios["vn_drama_5m"]["graph_required"] is True, "VN 5m drama should require graph")
    _assert(scenarios["vn_drama_5m"]["dialogue_required"] is True, "VN 5m drama should require dialogue lane")
    _assert(scenarios["vn_drama_5m"]["auto_route_allowed"] is False, "VN 5m drama should stay benchmark-gated")
    _assert(scenarios["medical_wellness_explainer"]["manual_review_required"] is True, "medical wellness scenario should require review")
    blueprints = {row["id"]: row for row in guide["long_form_blueprints"]}
    _assert(blueprints["three_minute_product_story"]["estimated_seedance_units"] >= 10, "3m blueprint should split into many Seedance units")
    five_min = blueprints["five_minute_short_film"]
    _assert(five_min["runtime_class"] == "short_film", "5m blueprint should be short_film")
    _assert(five_min["graph_required"] is True, "5m blueprint should require graph")
    _assert(five_min["dialogue_required"] is True, "5m VN drama blueprint should require dialogue lane")
    episode = blueprints["thirty_minute_episode"]
    _assert(episode["runtime_class"] == "episode", "30m blueprint should be episode runtime")
    _assert(episode["estimated_seedance_units"] >= 100, "30m blueprint should estimate many Seedance units")
    _assert(episode["top_tier_claim_allowed"] is False, "long-form blueprint must keep top-tier claim gated")
    _assert(guide["niche_fit"]["audit_summary"]["long_graph_required"] == guide["niche_fit"]["audit_summary"]["niche_count"], "guide should keep all 5m routes graph-required")
    _assert(guide["market_and_language"]["summary"]["auto_default_recommended"] is True, "guide should keep Auto as market default")
    _assert(guide["market_and_language"]["vietnam_status"]["auto_route_status"] == "benchmark_gated", "guide should keep VN dialogue benchmark-gated")
    rule_keys = {row["rule"] for row in guide["seedance_2_usage"]["core_rules"]}
    _assert("seedance_unit_length" in rule_keys, "guide should expose Seedance 4-15s unit rule")
    _assert("dialogue_is_insert_or_repair_lane" in rule_keys, "guide should expose dialogue/lipsync lane rule")
    _assert(guide["seedance_2_usage"]["model_picker_visible_to_user"] is False, "guide should keep model picker hidden")
    qa_plan = guide["qa_evidence_plan"]
    _assert(qa_plan["dimension_count"] >= 8, "guide should expose QA proof dimensions")
    _assert(qa_plan["model_backed_required_before_top_tier"] is True, "top-tier promotion should require model-backed QA")
    qa_dimensions = {row["id"]: row for row in qa_plan["dimensions"]}
    for dimension in [
        "reference_identity_adherence",
        "dialogue_lipsync",
        "cross_shot_continuity",
        "long_form_graph_execution",
        "cost_latency_retry",
    ]:
        _assert(dimension in qa_dimensions, f"guide should include {dimension} QA dimension")
    _assert("reviewer_notes" in qa_dimensions["reference_identity_adherence"]["evidence_required"], "identity QA should require reviewer notes")
    _assert("lip_sync_reviewer_notes" in qa_dimensions["dialogue_lipsync"]["evidence_required"], "dialogue QA should require lipsync reviewer notes")
    _assert("paid_output_url" in qa_dimensions["long_form_graph_execution"]["evidence_required"], "long-form QA should require paid output evidence")


def test_autonomous_competitive_research_maps_sources_to_source_gaps() -> None:
    research = build_autonomous_competitive_research()
    _assert(research["schema_version"] == "cinejelly.autonomous_competitive_research.v1", "research schema missing")
    source_names = {row["name"] for row in research["sources"]}
    _assert("AtlasCloud Seedance 2.0" in source_names, "research should include AtlasCloud Seedance source")
    _assert("Higgsfield cinematic logic layer" in source_names, "research should include Higgsfield cinematic logic layer")
    _assert("Higgsfield MCP creative studio" in source_names, "research should include Higgsfield chat-native MCP workflow")
    _assert("Higgsfield Supercomputer" in source_names, "research should include Higgsfield Supercomputer agent reference")
    _assert("Topview AI Video Agent V2" in source_names, "research should include Topview agent product reference")
    _assert("HeyGen rebuilt Video Agent" in source_names, "research should include HeyGen blueprint-first video agent reference")
    _assert("OpenMontage" in source_names, "research should include OpenMontage agentic video system")
    _assert("Montaj agent timeline editor" in source_names, "research should include agentic editor reference")
    _assert("Jellyfish AI Short Drama Studio" in source_names, "research should include Jellyfish source")
    _assert("NovelVids" in source_names, "research should include novel-to-short-drama production reference")
    _assert("LocalMiniDrama" in source_names, "research should include Chinese Seedance workflow source")
    _assert("Moyin Creator" in source_names, "research should include Seedance film pipeline source")
    _assert("Alibaba LumenX Studio" in source_names, "research should include Alibaba script-to-video SOP source")
    _assert("Huobao Drama" in source_names, "research should include one-sentence Chinese drama automation source")
    _assert("Toonflow" in source_names, "research should include practical Seedance short-drama production source")
    _assert("ViMax / AI-Creator" in source_names, "research should include ViMax multi-agent source")
    _assert("Awesome Seedance 2.0 Prompt and Examples" in source_names, "research should include Seedance prompt-bank source")
    _assert("Fal Seedance 2.0 Reference-to-Video Examples" in source_names, "research should include Seedance reference API examples")
    _assert("Codeywood" in source_names, "research should include Codeywood gate-based story workflow source")
    _assert("VibeFrame" in source_names, "research should include agent-readable storyboard/build-report workflow source")
    _assert("Seedance structured shot-list creator reports" in source_names, "research should include creator shot-list workflow evidence")
    _assert("StoryMem" in source_names, "research should include memory-based long-form source")
    _assert("CoAgent" in source_names, "research should include plan-synthesize-verify source")
    _assert("Co-Director" in source_names, "research should include global creative optimization source")
    _assert("DreamShot" in source_names, "research should include storyboard role-conditioning source")
    _assert("CANVAS" in source_names, "research should include continuity-aware narrative framework source")
    _assert("StoryBlender" in source_names, "research should include continuity memory graph source")
    _assert("Camera Artist" in source_names, "research should include cinematography-shot agent source")
    _assert("VideoGen-of-Thought" in source_names, "research should include script-keyframe-shot source")
    _assert("One Sentence, One Drama" in source_names, "research should include newest short-drama multi-agent source")
    _assert("MUSE" in source_names, "research should include closed-loop long-story orchestration source")
    _assert("AniMaker" in source_names, "research should include multi-candidate clip selection source")
    _assert("TTV Pipeline" in source_names, "research should include long-form segmentation/chaining pipeline source")
    _assert("Stable Video Infinity" in source_names, "research should include long-video anti-drift source")
    _assert("Creator short-drama asset workflow reports" in source_names, "research should include creator workflow evidence")
    pattern_keys = {row["key"] for row in research["patterns"]}
    _assert("saas_shell_hides_provider_security_noise" in pattern_keys, "research should map clean SaaS shell pattern")
    _assert("conversational_preflight_approval_gate" in pattern_keys, "research should map conversational approval gate")
    _assert("chat_native_tool_orchestration" in pattern_keys, "research should map chat-native tool orchestration")
    _assert("cinematic_logic_layer_before_generation" in pattern_keys, "research should map cinematic planning layer")
    _assert("screenplay_scene_graph_long_form" in pattern_keys, "research should map long-form graph pattern")
    _assert("omni_segment_reference_binding" in pattern_keys, "research should map Seedance omni segment binding")
    _assert("keyframe_grid_and_previous_frame_handoff" in pattern_keys, "research should map keyframe handoff pattern")
    _assert("dynamic_keyframe_memory_bank" in pattern_keys, "research should map dynamic memory bank pattern")
    _assert("script_keyframe_shot_smoothing_pipeline" in pattern_keys, "research should map script-keyframe-shot smoothing pattern")
    _assert("global_creative_direction_search" in pattern_keys, "research should map creative direction search pattern")
    _assert("writers_room_and_producer_gate" in pattern_keys, "research should map writers-room producer gate pattern")
    _assert("continuity_benchmark_dimensions" in pattern_keys, "research should map long-form continuity dimensions")
    _assert("agent_readable_artifact_reports" in pattern_keys, "research should map agent-readable artifact report pattern")
    _assert("agent_timeline_review_after_render" in pattern_keys, "research should map post-render agent timeline pattern")
    _assert("video_prior_storyboard_and_role_conditioning" in pattern_keys, "research should map video-prior storyboard pattern")
    _assert("novel_or_script_to_asset_sop" in pattern_keys, "research should map script-to-asset SOP pattern")
    _assert("multi_candidate_selection_for_hero_beats" in pattern_keys, "research should map multi-candidate hero beat selection")
    _assert("benchmark_winning_prompt_template_bank" in pattern_keys, "research should map benchmark-winning prompt bank")
    _assert("long_form_error_recycling" in pattern_keys, "research should map long-form error recycling")
    _assert("responsible_likeness_ip_gate" in pattern_keys, "research should map likeness/IP guard pattern")
    _assert("dialogue_as_separate_lane" in pattern_keys, "research should map dialogue lane pattern")
    upgrades = {row["upgrade"]: row for row in research["source_backed_upgrade_matrix"]}
    for upgrade in [
        "paid_seedance_benchmark_pack",
        "conversational_cinematic_preflight",
        "model_backed_reference_and_lipsync_qa",
        "agent_timeline_review_workspace",
        "accepted_render_memory_and_variant_chat",
        "full_asset_library_and_entity_extraction",
        "benchmark_winning_seedance_prompt_bank",
        "multi_candidate_hero_shot_selection",
        "long_form_error_recycling_and_keyframe_memory",
    ]:
        _assert(upgrade in upgrades, f"research should expose {upgrade} upgrade")
    _assert(upgrades["paid_seedance_benchmark_pack"]["priority"] == "P0", "paid benchmark pack should be P0")
    _assert(research["implementation_score"]["top_tier_claim_allowed"] is False, "research must not claim top-tier without evidence")


def test_autonomous_niche_launch_matrix_sets_sell_first_and_review_locked_tiers() -> None:
    matrix = build_autonomous_niche_launch_matrix()
    _assert(matrix["schema_version"] == "cinejelly.autonomous_niche_launch_matrix.v1", "niche launch schema missing")
    _assert(matrix["summary"]["top_tier_claim_allowed"] is False, "launch matrix must keep top-tier evidence gated")
    _assert("beauty" in matrix["tiers"]["sell_first"], "beauty should be sell-first")
    _assert("medical_wellness" in matrix["tiers"]["review_locked"], "medical wellness should be review-locked")
    beauty = next(row for row in matrix["rows"] if row["niche"] == "beauty")
    _assert(beauty["max_default_duration_s"] == 60, "sell-first niches should default to short-form launch duration")
    _assert("top-tier marketing claim" in beauty["benchmark_before"], "sell-first still needs benchmark before premium claims")
    medical = next(row for row in matrix["rows"] if row["niche"] == "medical_wellness")
    _assert(medical["max_default_duration_s"] == 0, "review-locked niches should not auto-render by default")
    _assert("claims safety" in medical["risk_controls"], "medical niche should carry claim safety controls")


def test_autonomous_niche_audit_covers_short_and_long_routes_without_top_tier_claims() -> None:
    audit = build_autonomous_niche_audit()
    _assert(audit["schema_version"] == "cinejelly.autonomous_niche_audit.v1", "niche audit schema missing")
    summary = audit["summary"]
    _assert(summary["niche_count"] >= 23, "niche audit should cover all canonical niches")
    _assert(summary["short_auto_allowed"] >= 15, "most short-form niches should be auto-routable with sufficient refs")
    _assert(summary["long_graph_required"] == summary["niche_count"], "all 5m routes should require graph execution")
    _assert(summary["long_auto_allowed"] == 0, "5m routes should stay benchmark-gated before default auto route")
    _assert(summary["top_tier_claim_allowed"] is False, "niche audit must not claim top-tier without evidence")
    short = {row["niche"]: row for row in audit["short_30s"]}
    long = {row["niche"]: row for row in audit["long_5m"]}
    _assert(short["beauty"]["primary_visual_model"] == "seedance_2_0_ref", "beauty short should use premium Seedance ref route")
    _assert(short["ugc_review"]["auto_route_allowed"] is True, "UGC review short should be auto-routable")
    _assert(short["medical_wellness"]["auto_route_allowed"] is False, "medical short should stay review/benchmark gated")
    _assert(long["drama"]["graph_required"] is True, "drama 5m should require graph")
    _assert(long["drama"]["dialogue_required"] is True, "drama 5m should mark dialogue lane")


def test_autonomous_market_audit_keeps_auto_default_and_dialogue_gated() -> None:
    audit = build_autonomous_market_audit()
    _assert(audit["schema_version"] == "cinejelly.autonomous_market_audit.v1", "market audit schema missing")
    summary = audit["summary"]
    _assert(summary["market_count"] >= 7, "market audit should cover canonical markets")
    _assert(summary["auto_default_recommended"] is True, "Auto should remain the default UX")
    _assert(summary["override_supported"] is True, "explicit market override should be supported")
    _assert(summary["model_choice_hidden"] is True, "model choice should stay hidden from the one-click UI")
    _assert(summary["long_graph_required_count"] == summary["market_count"], "all 5m market routes should require graph execution")
    _assert(summary["top_tier_claim_allowed"] is False, "market audit must not claim top-tier without evidence")
    _assert(summary["vn_dialogue_candidate"] in {"atlascloud/infinitetalk", "atlascloud/multitalk"}, "VN long dialogue should expose Atlas dialogue candidate")
    long = {row["requested_market"]: row for row in audit["long_5m"]}
    vn_long = long["vn"]
    _assert(vn_long["effective_market"] == "vn", "explicit VN market should remain VN")
    _assert(vn_long["primary_language"] == "Vietnamese", "VN route should use Vietnamese playbook")
    _assert(vn_long["dialogue_required"] is True, "VN 5m drama should require dialogue lane")
    _assert(vn_long["manual_review_required"] is True, "VN dialogue should stay benchmark/review gated")
    _assert(vn_long["post_process_candidate"] == "bytedance/lipsync/audio-to-video", "VN dialogue should expose lipsync repair lane")


def test_atlas_model_integration_matrix_keeps_new_models_benchmark_locked() -> None:
    matrix = build_atlas_model_integration_matrix()
    _assert(matrix["schema_version"] == "cinejelly.atlas_model_integration_matrix.v1", "atlas model matrix schema missing")
    _assert(matrix["recommendation"]["keep_ui_model_picker"] is False, "one-click UI should not expose model picker")
    _assert(matrix["recommendation"]["default_route"] == "seedance_2_0_fast_ref", "Seedance Fast Reference should remain default")
    rows = {row["model_key"]: row for row in matrix["rows"]}
    _assert(rows["seedance_2_0_fast_ref"]["status"] == "active", "default Seedance route should be active")
    _assert(rows["atlascloud/infinitetalk"]["status"] == "priority_benchmark_required", "InfiniteTalk should be benchmark gated")
    _assert(rows["atlascloud/infinitetalk"]["lane"] == "dialogue_or_lipsync", "InfiniteTalk should be dialogue lane")
    _assert(rows["kwaivgi/kling-lipsync/audio-to-video"]["lane"] == "dialogue_or_lipsync", "Kling lip-sync should be dialogue repair lane")
    _assert(rows["atlascloud/framepack"]["lane"] == "cheap_motion_or_dialogue_probe", "FramePack should stay a cheap motion probe")
    _assert(rows["bytedance/seedream-v4/sequential"]["lane"] == "asset_generation", "Seedream sequential should be asset generation")
    _assert("video duration 2-10s in Atlas docs" in rows["kwaivgi/kling-lipsync/audio-to-video"]["operational_limits"], "Kling lip-sync limits should be explicit")
    _assert("cost_policy" in matrix["recommendation"], "matrix should expose operator cost policy")
    rule_keys = {row["rule"] for row in matrix["source_backed_model_rules"]}
    _assert("seedance_unit_length" in rule_keys, "matrix should encode Atlas-backed Seedance unit length")
    _assert("dialogue_is_insert_or_repair_lane" in rule_keys, "matrix should encode Atlas-backed dialogue lane rule")
    _assert("accepted_minute_cost" in rule_keys, "matrix should encode accepted-minute cost rule")
    _assert("asset_generation" in matrix["lane_policy"], "matrix should expose asset lane policy")
    _assert("reviewer_decision" in matrix["promotion_gate"]["required_fields"], "promotion gate must require reviewer decision")
    _assert("reviewer_notes" in matrix["promotion_gate"]["required_evidence_keys"], "promotion gate must require reviewer notes")
    _assert("seedance_prompt_formula" in matrix["promotion_gate"]["required_evidence_keys"], "promotion gate must require prompt formula")
    _assert(
        matrix["promotion_gate"]["required_evidence_keys"] == REQUIRED_EVIDENCE_KEYS,
        "atlas model matrix should reuse the canonical evidence validator keys",
    )
    _assert(matrix["verdict"]["top_tier_claim_allowed"] is False, "new Atlas models must not create top-tier claim")


def test_autonomous_niche_playbook_catalog_scales_niches_to_long_form() -> None:
    catalog = build_autonomous_niche_playbook_catalog()
    _assert(catalog["schema_version"] == "cinejelly.autonomous_niche_playbook_catalog.v1", "playbook catalog schema missing")
    _assert(catalog["summary"]["niche_count"] >= 20, "playbook catalog should cover all supported niches")
    _assert(len(catalog["duration_templates"]) == 4, "catalog should explain short through episode duration templates")
    rows = {row["niche"]: row for row in catalog["rows"]}
    _assert("beauty" in rows and "drama" in rows, "catalog should include commercial and narrative niches")
    beauty_short = rows["beauty"]["duration_scaling"][0]
    _assert(beauty_short["runtime_class"] == "short", "beauty first duration example should be short")
    drama_episode = rows["drama"]["duration_scaling"][-1]
    _assert(drama_episode["runtime_class"] == "episode", "drama should expose episode scaling")
    _assert(drama_episode["single_call_allowed"] is False, "episode scaling must not allow one render call")
    _assert("scene_continuity_and_pacing_need_graph_qa" in drama_episode["risk_register"], "long drama should require graph QA")
    _assert("reference jobs" in rows["food"]["seedance_prompt_contract"]["structure"], "Seedance prompt contract should be structured")


def test_autonomous_top_tier_completion_gate_requires_real_evidence() -> None:
    gate = build_autonomous_top_tier_completion_gate()
    _assert(gate["schema_version"] == "cinejelly.autonomous_top_tier_completion_gate.v1", "top-tier gate schema missing")
    verdict = gate["verdict"]
    _assert(verdict["top_app_parity_proven"] is False, "top-tier parity must not be proven without evidence")
    _assert(verdict["partial_count"] >= 1, "gate should expose partial architecture work")
    reqs = {item["key"]: item for item in gate["requirements"]}
    _assert(reqs["autonomous_only_user_experience"]["status"] == "passed", "autonomous UI requirement should pass")
    _assert(reqs["all_niche_directing_system"]["status"] == "passed", "all-niche playbook requirement should pass")
    _assert(reqs["real_benchmark_evidence"]["status"] == "failed", "real evidence should fail locally without promoted outputs")
    _assert("no_promoted_routes" in reqs["real_benchmark_evidence"]["blockers"], "missing promoted route blocker should be explicit")
    _assert(
        "seedance_prompt_formula" in reqs["real_benchmark_evidence"]["evidence"]["required_fields"],
        "top-tier gate should require formula evidence",
    )
    _assert("Benchmark InfiniteTalk" in " ".join(gate["next_proof_order"]), "next proof order should include dialogue benchmark")


def test_autonomous_paid_benchmark_manifest_prepares_two_outputs_per_sell_first_route() -> None:
    manifest = build_autonomous_paid_benchmark_manifest(focus="sell_first", outputs_per_route=2, limit=9)
    _assert(manifest["schema_version"] == "cinejelly.autonomous_paid_benchmark_manifest.v1", "paid manifest schema missing")
    summary = manifest["summary"]
    _assert(summary["top_tier_claim_after_manifest"] is False, "manifest alone must not claim top-tier")
    _assert(summary["case_count"] >= 8, "sell-first manifest should cover launch niches")
    _assert(summary["paid_run_count"] == summary["case_count"] * 2, "manifest should require two outputs per route")
    _assert(summary["estimated_vendor_cost_usd"]["subtotal"] > 0, "manifest should estimate paid vendor cost")
    phases = {phase["phase"]: phase for phase in manifest["operator_runbook_phases"]}
    _assert("preflight" in phases and "paid_render" in phases, "manifest should include operator preflight/render phases")
    _assert("qa_review" in phases and "promotion_or_rollback" in phases, "manifest should include QA and rollback phases")
    _assert("exit_gate" in phases["qa_review"], "runbook QA phase should define an exit gate")
    first = manifest["runs"][0]
    _assert(first["estimated_vendor_cost_usd"]["estimated_total_usd"] > 0, "each paid run should estimate cost")
    _assert(first["estimated_vendor_cost_usd"]["estimated_seedance_units"] >= 1, "each paid run should estimate Seedance units")
    _assert(first["review_rubric"]["promotion_thresholds"]["minimum_weighted_score"] == 8.0, "paid runs should include review rubric")
    _assert(first["render_payload_blueprint"]["user_model"] == "auto", "paid manifest should keep UI/model route autonomous")
    _assert(first["benchmark_result_create_blueprint"]["status"] == "planned", "benchmark row should start as planned")
    patch = first["benchmark_result_patch_after_render"]
    _assert("output_url" in patch and "reviewer_decision" in patch, "patch payload should require output and review")
    evidence = patch["evidence"]
    _assert("per_shot_prompts" in evidence and "retry_count" in evidence, "patch evidence should include promotion keys")
    _assert(first["promotion_target"]["requires_two_approved_outputs"] is True, "promotion target should require two approved outputs")


def test_phase3_prompt_route_audit_covers_models_niches_and_paid_gate() -> None:
    audit = build_phase3_prompt_route_audit()
    _assert(audit["schema_version"] == "cinejelly.phase3_prompt_route_audit.v1", "phase3 audit schema missing")
    verdict = audit["verdict"]
    _assert(verdict["ready_for_controlled_paid_benchmark"] is True, "phase3 non-billable gate should pass")
    _assert(verdict["top_tier_claim_allowed"] is False, "phase3 audit must not allow top-tier claim without paid evidence")
    route_keys = {route["model_key"] for route in audit["model_route_contracts"]}
    for required in {
        "seedance_2_0_fast_t2v",
        "seedance_2_0_fast_i2v",
        "seedance_2_0_fast_ref",
        "seedance_2_0_ref",
        "wan_2_7_i2v",
    }:
        _assert(required in route_keys, f"missing model route contract {required}")
    situations = " ".join(item["situation"] for item in audit["situation_routing"])
    _assert("3-30 minute" in situations, "phase3 audit should cover long-form routing")
    _assert(audit["niche_prompt_matrix"]["niche_count"] >= 20, "phase3 audit should cover all canonical niches")
    blocks = audit["prompt_contract"]["required_block_order"]
    _assert("reference jobs" in blocks and "shot contract" in blocks, "phase3 prompt blocks should include reference jobs and shot contract")
    paid_gate = audit["paid_benchmark_gate"]
    _assert("minimum_next_manifest" in paid_gate and paid_gate["first_paid_runs"], "phase3 audit should include paid benchmark manifest preview")
    feedback_loop = audit["phase3b_feedback_loop"]
    _assert("POST /api/v1/director/jobs/{job_id}/feedback" == feedback_loop["endpoints"]["record_feedback"], "phase3B feedback endpoint contract missing")
    _assert("prompt_mismatch" in feedback_loop["issue_tags"], "phase3B feedback tags should include prompt mismatch")


def test_phase4_non_paid_completion_audit_closes_phase_without_vendor_calls() -> None:
    audit = build_phase4_non_paid_completion_audit()
    _assert(audit["schema_version"] == "cinejelly.phase4_non_paid_completion_audit.v1", "phase4 audit schema missing")
    verdict = audit["verdict"]
    _assert(verdict["non_paid_phase4_complete"] is True, "phase4 non-paid infrastructure should be complete")
    _assert(verdict["top_tier_claim_allowed"] is False, "phase4 must not allow top-tier claim without paid proof")
    _assert(verdict["paid_output_proof_complete"] is False, "phase4 no-paid audit must not claim paid output proof")
    policy = audit["vendor_call_policy"]
    _assert(policy["vendor_calls_allowed_by_this_audit"] is False, "phase4 audit must forbid vendor calls")
    _assert(policy["atlascloud_smoke_test_performed"] is False, "phase4 audit must not mark Atlas smoke as performed")
    checks = {item["key"]: item for item in audit["checks"]}
    for required in {
        "vendor_spend_guard",
        "benchmark_dry_run_manifest",
        "required_evidence_pack_contract",
        "post_render_feedback_loop",
        "long_form_graph_resume_contract",
        "non_paid_verification_suite",
        "top_tier_claim_gate",
    }:
        _assert(checks[required]["status"] == "passed", f"phase4 check should pass: {required}")
    _assert(checks["paid_output_proof"]["status"] == "locked", "paid proof should be locked, not passed")
    qa = audit["phase4b_post_render_qa"]
    _assert("qa_frames" in qa["required_evidence_keys"], "phase4 QA should require QA frames")
    _assert("strong_quality_gate.evaluate_strong_quality_gate" in qa["local_or_fail_soft_probes"], "phase4 QA should include strong quality gate")
    commands = audit["phase4d_e2e_verification"]["commands"]
    _assert("python -m pytest -q" in commands and "node .\\node_modules\\next\\dist\\bin\\next build" in commands, "phase4 verification commands missing")


def test_benchmark_review_rubric_scores_weighted_promotion_decision() -> None:
    rubric = build_benchmark_review_rubric(
        niche="drama",
        runtime_class="short_film",
        target_market="vn",
        has_dialogue=True,
    )
    _assert(rubric["schema_version"] == "cinejelly.benchmark_review_rubric.v1", "review rubric schema missing")
    keys = {dim["key"] for dim in rubric["dimensions"]}
    _assert("long_form_continuity" in keys, "short-film rubric should add long-form continuity dimension")
    _assert(rubric["promotion_thresholds"]["requires_reviewer_notes"] is True, "reviewer notes should be required")
    good_scores = {key: 8.6 for key in keys}
    scored = score_benchmark_review(rubric=rubric, dimension_scores=good_scores)
    _assert(scored["promotion_ready"] is True, f"good filled rubric should promote: {scored}")
    weak_scores = {key: 8.6 for key in keys}
    weak_scores["reference_adherence"] = 6.5
    weak = score_benchmark_review(rubric=rubric, dimension_scores=weak_scores)
    _assert(weak["promotion_ready"] is False, "below-bar reference adherence should block promotion")
    _assert("reference_adherence" in weak["below_bar_dimensions"], "weak dimension should be named")


def test_benchmark_result_payload_can_compute_qa_score_from_review_scores() -> None:
    payload = {
        "case_id": "bench_ugc_review",
        "niche": "ugc_review",
        "target_market": "vn",
        "runtime_class": "short",
        "model_key": "seedance_2_0_fast_ref",
        "status": "passed",
        "output_url": "https://cdn.example.com/ugc.mp4",
        "cost_usd": 2.28,
        "latency_s": 120.0,
        "review_scores": {
            "hook_and_retention": 8.8,
            "reference_adherence": 8.7,
            "camera_and_motion_quality": 8.4,
            "story_or_proof_clarity": 8.5,
            "market_and_platform_fit": 8.2,
            "audio_and_lipsync": 8.1,
            "technical_artifacts": 8.6,
            "cost_latency_and_retry_fit": 8.0,
        },
        "evidence": {
            "audio_report": "voice and foley acceptable",
            "reviewer_notes": "approved without structural edits",
        },
    }
    scored = _apply_benchmark_review_scores(payload)
    _assert("review_scores" not in scored, "raw review_scores should not be passed into benchmark store")
    _assert(scored["qa_score"] >= 8.0, "weighted review score should become qa_score")
    _assert(scored["reviewer_decision"] == "approved", "good rubric score should recommend approval")
    _assert(scored["evidence"]["benchmark_review_score"]["promotion_ready"] is True, "review score evidence should be promotion-ready")
    _assert(scored["evidence"]["benchmark_review_rubric"]["schema_version"] == "cinejelly.benchmark_review_rubric.v1", "rubric should be attached to evidence")
    blocked = _apply_benchmark_review_scores({
        **payload,
        "review_scores": {
            **payload["review_scores"],
            "reference_adherence": 6.0,
        },
        "review_hard_failures": ["identity drift in hero product close-up"],
    })
    _assert(blocked["qa_score"] < scored["qa_score"], "weak review dimension should lower qa_score")
    _assert(blocked["reviewer_decision"] == "needs_review", "hard failures should keep reviewer decision gated")
    _assert(blocked["evidence"]["benchmark_review_score"]["promotion_ready"] is False, "hard failures should block promotion")
    _assert("reference_adherence" in blocked["evidence"]["benchmark_review_score"]["below_bar_dimensions"], "blocked dimension should be retained")


def main() -> None:
    tests = [
        test_beauty_premium_seedance,
        test_vietnamese_beauty_review_routes_to_beauty_not_generic_ugc,
        test_vietnamese_market_keywords_route_specific_niches,
        test_niche_resolution_exposes_scores_and_hits_for_mixed_briefs,
        test_ambiguous_niche_resolution_blocks_autoroute_until_review,
        test_autonomous_generate_rejects_ambiguous_niche_before_chain,
        test_autonomous_generate_request_accepts_approved_plan_metadata,
        test_autonomous_generate_rejects_stale_approved_plan_metadata,
        test_clear_niche_resolution_does_not_ask_for_clarification,
        test_auto_market_infers_vietnamese_language_and_playbook,
        test_vietnamese_spoken_language_tokens_enable_dialogue_lane,
        test_vietnamese_diacritic_market_brief_routes_to_vn_dialogue,
        test_auto_market_infers_japanese_and_korean_scripts,
        test_responsible_content_gate_blocks_unverified_likeness_and_ip,
        test_production_decision_exposes_responsible_content_gate,
        test_planner_guard_aligns_llm_niche_with_deterministic_preview,
        test_planner_guard_noops_when_planner_matches_preview,
        test_long_form_decision_exposes_scene_blueprint_preview,
        test_production_decision_ranks_creative_treatments_before_render,
        test_production_decision_exposes_hero_shot_candidate_policy,
        test_long_form_hero_shot_candidates_stay_benchmark_gated,
        test_long_form_error_recycling_policy_maps_failures_to_memory,
        test_long_form_story_prefers_short_drama_treatment,
        test_creative_treatment_search_flags_missing_visual_refs_for_long_form,
        test_production_decision_exposes_seedance_reference_allocation,
        test_production_decision_exposes_seedance_segment_inspector,
        test_production_decision_exposes_seedance_prompt_formula,
        test_production_decision_exposes_prompt_template_bank_policy,
        test_phase3_prompt_execution_contract_compiles_every_producer_shot,
        test_phase3_prompt_execution_contract_routes_no_reference_jobs_to_text_to_video,
        test_phase3_prompt_execution_contract_binds_image_references_to_slots,
        test_phase3_product_image_reference_prioritizes_product_hero_slot,
        test_phase3_preflight_exposes_prompt_execution_contract_summary,
        test_phase4a_viral_creative_brain_selects_product_proof_pattern,
        test_phase4a_viral_creative_brain_selects_long_drama_reversal,
        test_phase4a_preflight_exposes_viral_brain_and_distribution_preview,
        test_phase4b_output_qa_retry_brain_builds_product_retry_contract,
        test_phase4b_output_qa_retry_brain_requires_long_form_continuity_review,
        test_phase4b_preflight_exposes_output_qa_retry_summary,
        test_production_decision_exposes_autonomous_input_upgrade_plan,
        test_production_decision_exposes_asset_bible_completion_policy,
        test_conversational_preflight_drafts_plan_before_render,
        test_conversational_preflight_infers_vietnamese_market_and_duration_from_chat_brief,
        test_conversational_preflight_asks_when_brief_is_too_thin,
        test_conversational_preflight_keeps_revision_notes_in_approved_brief,
        test_conversational_preflight_uses_structured_chat_history,
        test_conversational_preflight_keeps_revision_chat_out_of_base_idea,
        test_conversational_preflight_accepts_chat_answers_for_long_form_story_spine,
        test_conversational_preflight_blocks_long_form_missing_references,
        test_conversational_preflight_unlocks_long_form_when_graph_flag_and_refs_ready,
        test_conversational_preflight_user_surface_hides_internal_execution_terms,
        test_conversational_preflight_suggests_long_form_story_reply_templates,
        test_production_decision_exposes_niche_execution_rubric,
        test_production_decision_exposes_niche_runtime_director_contract,
        test_production_decision_exposes_niche_production_recipe,
        test_niche_production_recipe_scales_long_form_to_graph_units,
        test_production_decision_exposes_route_quality_scorecard,
        test_production_decision_exposes_cinematic_grammar_contract,
        test_cinematic_grammar_contract_long_form_adds_scene_bridge,
        test_niche_runtime_director_flags_long_form_without_visual_anchor,
        test_seedance_reference_allocation_warns_long_form_without_visual_anchor,
        test_creative_treatment_is_injected_into_director_plan,
        test_short_decision_disables_scene_blueprint_preview,
        test_long_vn_presenter_uses_graph_and_infinitetalk_candidate,
        test_two_speaker_drama_uses_multitalk_candidate,
        test_model_route_strategy_locks_emerging_visual_challengers,
        test_finance_keeps_review_gate,
        test_food_uses_sensory_seedance_route,
        test_long_narrative_context_beats_object_keyword_for_drama,
        test_english_short_drama_context_beats_street_food_keyword,
        test_reference_count_aliases_are_backward_compatible,
        test_seedance_shot_linter_passes_renderable_shot,
        test_seedance_shot_linter_fails_overloaded_long_shot,
        test_seedance_prompt_compiler_emits_structured_reference_contract,
        test_seedance_prompt_compiler_includes_formula_contract_when_present,
        test_seedance_single_call_prompt_includes_formula_contract_when_present,
        test_per_shot_render_quality_probe_uses_current_scene_job,
        test_seedance_prompt_compiler_preserves_non_seedance_prompt,
        test_autonomous_preflight_includes_seedance_lint,
        test_autonomous_preflight_blocks_responsible_content,
        test_autonomous_preflight_includes_niche_execution_rubric,
        test_screenplay_scene_linter_passes_valid_long_form_structure,
        test_screenplay_scene_linter_fails_missing_scene_continuity,
        test_autonomous_preflight_includes_screenplay_scene_lint,
        test_continuity_handoff_policy_applies_required_chains,
        test_autonomous_preflight_fails_missing_long_form_handoff,
        test_production_decision_exposes_long_form_execution_gate,
        test_long_form_execution_gate_passes_executable_graph_contract,
        test_production_graph_shot_nodes_carry_prompt_formula_and_reference_contract,
        test_dynamic_keyframe_memory_contract_maps_scene_handoffs,
        test_autonomous_preflight_includes_long_form_execution_gate,
        test_autonomous_preflight_includes_script_asset_sop_for_long_form,
        test_cross_shot_diagnostic_passes_coherent_sequence,
        test_cross_shot_diagnostic_fails_flat_long_form_without_handoffs,
        test_autonomous_preflight_includes_cross_shot_diagnostic,
        test_producer_story_critic_passes_proof_driven_ugc_plan,
        test_producer_story_critic_fails_vague_no_payoff_plan,
        test_distribution_package_localizes_tiktok_vn,
        test_distribution_package_youtube_long_uses_long_form_packaging,
        test_autonomous_asset_pin_status_lifecycle,
        test_auto_select_approved_asset_pins_prefers_series_and_priority,
        test_all_canonical_niche_benchmarks_have_valid_production_decisions,
        test_benchmark_promotion_policy_locks_without_real_evidence,
        test_benchmark_contract_tracks_current_atlas_candidate_routes,
        test_benchmark_plan_prioritizes_long_form_and_launch_evidence,
        test_benchmark_plan_prioritizes_locked_model_candidates,
        test_benchmark_promotion_policy_promotes_only_real_approved_outputs,
        test_benchmark_evidence_validator_reports_precise_missing_fields,
        test_benchmark_runner_adds_non_promotional_evidence_template,
        test_artifact_evidence_pack_autofills_only_proven_fields,
        test_agent_readable_production_report_summarizes_artifact_for_resume,
        test_autonomous_capability_matrix_explains_niche_runtime_fit,
        test_autonomous_production_audit_keeps_top_tier_claim_evidence_gated,
        test_autonomous_operator_brief_answers_workflow_niche_and_gap_questions,
        test_autonomous_workflow_niche_guide_explains_current_state_without_overclaiming,
        test_autonomous_competitive_research_maps_sources_to_source_gaps,
        test_autonomous_niche_launch_matrix_sets_sell_first_and_review_locked_tiers,
        test_autonomous_niche_audit_covers_short_and_long_routes_without_top_tier_claims,
        test_autonomous_market_audit_keeps_auto_default_and_dialogue_gated,
        test_atlas_model_integration_matrix_keeps_new_models_benchmark_locked,
        test_autonomous_niche_playbook_catalog_scales_niches_to_long_form,
        test_autonomous_top_tier_completion_gate_requires_real_evidence,
        test_autonomous_paid_benchmark_manifest_prepares_two_outputs_per_sell_first_route,
        test_phase3_prompt_route_audit_covers_models_niches_and_paid_gate,
        test_phase4_non_paid_completion_audit_closes_phase_without_vendor_calls,
        test_benchmark_review_rubric_scores_weighted_promotion_decision,
        test_benchmark_result_payload_can_compute_qa_score_from_review_scores,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"PASS {len(tests)} autonomous backend smoke tests")


if __name__ == "__main__":
    main()
