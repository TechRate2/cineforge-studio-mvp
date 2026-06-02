from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from agent.model_specs import (
    build_payload,
    get_user_model_cost_rate,
    resolve_video_model_variant,
)
from agent.continuity_manager import normalize_per_shot_durations_for_model
from agent.multi_shot_prompt_builder import pick_strategy
from agent.scene_generation_agent import generate_scene
from agent.schemas import (
    AudioDesign,
    Constraints,
    ContinuityBible,
    CostEstimate,
    DirectorPlan,
    EvaluationReport,
    ReferenceAsset,
    Setting,
    Shot,
    ShotAudio,
    ShotContinuity,
    ShotVisual,
    VisualStyle,
)
from api.main import app
from api.routes.video_direct import DirectVideoRequest
from api.routes.director import PlanRequest, _JOBS_STORE
from api.schemas import ProductInput, VideoSettings


client = TestClient(app)


def test_product_intelligence_blocks_private_urls_without_vendor_calls():
    res = client.post(
        "/api/v1/director/autonomous/product-intelligence",
        json={"url": "http://localhost:3000/product", "user_idea": "Make a product ad"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "error"
    assert data["error"]["code"] == "private_host"
    assert data["vendor_calls_performed"] is False
    assert data["paid_video_vendor_calls_allowed"] is False


def test_deep_preflight_deterministic_mode_keeps_video_vendor_locked():
    payload = {
        "user_idea": "5-minute founder story for a Vietnamese cafe, emotional but premium",
        "target_market": "vn",
        "target_platform": "youtube",
        "duration_hint_s": 300,
        "reference_counts": {"images": 1, "videos": 0, "audios": 0},
        "reference_image_urls": ["https://cdn.example.com/cafe.jpg"],
        "reference_manifest": {
            "schema_version": "cinejelly.ui_reference_manifest.v1",
            "confirmed": True,
            "items": [
                {
                    "tag": "@image_1",
                    "kind": "image",
                    "role": "environment",
                    "role_confirmed": True,
                    "url": "https://cdn.example.com/cafe.jpg",
                    "prompt_binding": "@image_1 = environment.",
                }
            ],
        },
        "allow_live_llm": False,
        "allow_vision_llm": False,
    }
    res = client.post("/api/v1/director/autonomous/deep-preflight", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "deterministic_companion"
    assert data["vendor_calls_performed"] is False
    assert data["paid_video_vendor_calls_allowed"] is False
    assert data["route_source_of_truth"]["source"] == "model_route_strategy.summary"
    assert data["reference_brain"]["items"][0]["role"] == "environment"
    assert data["reference_brain"]["items"][0]["status"] == "confirmed"


def test_production_decision_primary_model_matches_route_strategy():
    payload = {
        "user_idea": "5-minute founder story for a Vietnamese cafe, emotional but premium",
        "target_market": "vn",
        "target_platform": "youtube",
        "duration_hint_s": 300,
        "reference_counts": {"images": 1, "videos": 0, "audios": 0},
        "reference_image_urls": ["https://cdn.example.com/cafe.jpg"],
        "reference_manifest": {
            "schema_version": "cinejelly.ui_reference_manifest.v1",
            "confirmed": True,
            "items": [
                {
                    "tag": "@image_1",
                    "kind": "image",
                    "role": "environment",
                    "role_confirmed": True,
                    "url": "https://cdn.example.com/cafe.jpg",
                    "prompt_binding": "@image_1 = environment.",
                }
            ],
        },
    }
    res = client.post("/api/v1/director/autonomous/production-decision", json=payload)
    assert res.status_code == 200
    data = res.json()
    primary = data["decision"]["primary_model_route"]["primary_visual_model"]
    strategy_primary = data["model_route_strategy"]["summary"]["primary_visual_model"]
    prompt_primary = data["prompt_execution_contract_v3"]["model_plan"]["primary_visual_model"]
    assert primary == strategy_primary == prompt_primary
    assert data["decision"]["primary_model_route"]["route_source_of_truth"] == "model_route_strategy.summary"


def test_seedance_payload_keeps_quad_modal_refs_and_ignores_legacy_direct_fields():
    payload = build_payload(
        model_key="seedance_2_0_ref",
        prompt="A product hero shot with smooth push-in.",
        images=["https://cdn.example.com/product.png"],
        reference_videos=[
            "https://cdn.example.com/motion-1.mp4",
            "https://cdn.example.com/motion-2.mp4",
            "https://cdn.example.com/motion-3.mp4",
            "https://cdn.example.com/motion-4.mp4",
        ],
        reference_audios=[
            "https://cdn.example.com/beat-1.wav",
            "https://cdn.example.com/beat-2.wav",
            "https://cdn.example.com/beat-3.wav",
            "https://cdn.example.com/beat-4.wav",
        ],
        duration_s=5,
        return_last_frame=True,
        movement_amplitude="auto",
        camera_fixed=True,
    )

    assert payload["reference_videos"] == [
        "https://cdn.example.com/motion-1.mp4",
        "https://cdn.example.com/motion-2.mp4",
        "https://cdn.example.com/motion-3.mp4",
    ]
    assert payload["reference_audios"] == [
        "https://cdn.example.com/beat-1.wav",
        "https://cdn.example.com/beat-2.wav",
        "https://cdn.example.com/beat-3.wav",
    ]
    assert payload["return_last_frame"] is True
    assert "camera_fixed" not in payload
    assert "movement_amplitude" not in payload


def test_direct_video_request_accepts_seedance_quad_refs_and_rejects_overflow():
    req = DirectVideoRequest(
        model_key="seedance_2_0_ref",
        prompt="Reference-bound cinematic shot.",
        images=["https://cdn.example.com/ref.png"],
        reference_videos=[
            "https://cdn.example.com/v1.mp4",
            "https://cdn.example.com/v2.mp4",
            "https://cdn.example.com/v3.mp4",
        ],
        reference_audios=[
            "https://cdn.example.com/a1.wav",
            "https://cdn.example.com/a2.wav",
            "https://cdn.example.com/a3.wav",
        ],
    )

    assert len(req.reference_videos or []) == 3
    assert len(req.reference_audios or []) == 3

    with pytest.raises(ValidationError):
        DirectVideoRequest(
            model_key="seedance_2_0_ref",
            prompt="Too many refs.",
            images=["https://cdn.example.com/ref.png"],
            reference_videos=[
                "https://cdn.example.com/v1.mp4",
                "https://cdn.example.com/v2.mp4",
                "https://cdn.example.com/v3.mp4",
                "https://cdn.example.com/v4.mp4",
            ],
        )


def test_director_plan_request_accepts_three_video_and_audio_refs():
    req = PlanRequest(
        product_input=ProductInput(text_description="A premium skincare launch."),
        reference_images=["https://cdn.example.com/product.png"],
        reference_videos=[
            "https://cdn.example.com/camera.mp4",
            "https://cdn.example.com/pacing.mp4",
            "https://cdn.example.com/motion.mp4",
        ],
        reference_audios=[
            "https://cdn.example.com/beat.wav",
            "https://cdn.example.com/voice.wav",
            "https://cdn.example.com/sfx.wav",
        ],
        settings=VideoSettings(),
    )

    assert len(req.reference_videos) == 3
    assert len(req.reference_audios) == 3


def test_user_model_cost_rates_are_read_from_model_specs():
    assert get_user_model_cost_rate("seedance_2_0") == 0.096
    assert get_user_model_cost_rate("seedance_2_0_fast") == 0.076
    assert get_user_model_cost_rate("auto") == 0.076
    assert get_user_model_cost_rate("wan_2_7") == 0.10


def _minimal_bible(reference_assets: list[ReferenceAsset] | None = None) -> ContinuityBible:
    return ContinuityBible(
        title="Seedance route test",
        logline="A focused product shot.",
        intent="product_demo",
        duration_s=5,
        characters=[],
        products=[],
        reference_assets=reference_assets or [],
        visual_style=VisualStyle(
            cinematography="cinematic handheld",
            color_grading="warm natural",
            lighting_design="soft window light",
            camera_language="clean product close-ups",
        ),
        audio_design=AudioDesign(mood="premium", music_genre="light beat"),
        setting=Setting(location="studio table", time_of_day="afternoon", atmosphere="warm"),
        constraints=Constraints(must_avoid=["extra text"]),
    )


def _minimal_shot(reference_indices: list[int] | None = None) -> Shot:
    return Shot(
        shot_id="S1",
        index=0,
        start_s=0,
        end_s=5,
        duration_s=5,
        purpose="hero",
        emotion_beat="curiosity",
        visual=ShotVisual(
            subject="premium skincare bottle on a table",
            action="the bottle rotates slowly as light catches the label",
            camera_shot="CU",
            camera_movement="slow push-in",
            background="warm studio table",
        ),
        audio=ShotAudio(sfx=["soft whoosh"], music_cue="light beat"),
        continuity=ShotContinuity(
            reference_indices=reference_indices or [],
            style_anchor="warm premium tabletop",
        ),
    )


def test_seedance_no_reference_scene_routes_to_t2v_payload():
    scene_job = generate_scene(
        bible=_minimal_bible(),
        shot=_minimal_shot(),
        model_key="seedance_2_0_ref",
        reference_images=[],
        llm_mode=False,
    )

    assert scene_job.render_mode == "t2v"
    assert scene_job.model_key == "seedance_2_0_t2v"
    payload = build_payload(**scene_job.to_atlas_kwargs())
    assert payload["model"] == "bytedance/seedance-2.0/text-to-video"
    assert "reference_images" not in payload


def test_seedance_video_only_reference_scene_stays_ref_route():
    scene_job = generate_scene(
        bible=_minimal_bible(),
        shot=_minimal_shot(),
        model_key="seedance_2_0_fast_ref",
        reference_images=[],
        reference_videos=["https://cdn.example.com/camera-motion.mp4"],
        llm_mode=False,
    )

    assert scene_job.render_mode == "ref_to_video"
    assert scene_job.model_key == "seedance_2_0_fast_ref"
    payload = build_payload(**scene_job.to_atlas_kwargs())
    assert payload["model"] == "bytedance/seedance-2.0-fast/reference-to-video"
    assert payload["reference_videos"] == ["https://cdn.example.com/camera-motion.mp4"]
    assert "reference_images" not in payload


def test_seedance_variant_resolver_maps_aliases_and_concrete_keys():
    assert resolve_video_model_variant("seedance_2_0", "ref") == "seedance_2_0_ref"
    assert resolve_video_model_variant("seedance_2_0_ref", "t2v") == "seedance_2_0_t2v"
    assert resolve_video_model_variant("seedance_2_0_fast_i2v", "ref") == "seedance_2_0_fast_ref"


def test_direct_preview_accepts_user_alias_and_routes_by_inputs():
    text_only = client.post(
        "/api/v1/video/direct/preview-payload",
        json={
            "model_key": "seedance_2_0_fast",
            "prompt": "A cinematic rainy coffee cup push-in.",
            "duration_s": 4,
            "resolution": "480p",
            "aspect_ratio": "9:16",
            "generate_audio": False,
        },
    )
    assert text_only.status_code == 200, text_only.text
    assert text_only.json()["model_key"] == "seedance_2_0_fast_t2v"
    assert text_only.json()["payload"]["model"] == "bytedance/seedance-2.0-fast/text-to-video"

    image_only = client.post(
        "/api/v1/video/direct/preview-payload",
        json={
            "model_key": "seedance_2_0_fast",
            "prompt": "Animate this frame with a slow push-in.",
            "image": "https://cdn.example.com/frame.png",
            "duration_s": 4,
            "resolution": "480p",
        },
    )
    assert image_only.status_code == 200, image_only.text
    assert image_only.json()["model_key"] == "seedance_2_0_fast_i2v"
    assert image_only.json()["payload"]["image"] == "https://cdn.example.com/frame.png"


def test_autonomous_llm_brain_policy_endpoint_is_non_paid_and_low_cost_default():
    response = client.post(
        "/api/v1/director/autonomous/llm-brain-policy",
        json={
            "user_idea": "TikTok VN beauty serum launch with product image reference.",
            "target_market": "vn",
            "target_platform": "tiktok",
            "duration_hint_s": 30,
            "reference_counts": {"images": 1},
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["vendor_calls_performed"] is False
    assert data["paid_video_vendor_calls_allowed"] is False
    assert data["routes"]["insight_extraction"]["model"] == "deepseek-ai/deepseek-v4-flash"
    assert data["routes"]["creative_generation"]["pro_selected"] is False
    assert data["routes"]["vision_reference_scan"]["model"] == "qwen/qwen3-vl-30b-a3b-instruct"


def test_autonomous_creative_brief_contract_endpoint_parses_duration_without_paid_calls():
    response = client.post(
        "/api/v1/director/autonomous/creative-brief-contract",
        json={
            "user_idea": "Hay lam video 45s quang cao serum cho TikTok VN, can hook cuon.",
            "target_market": "vn",
            "target_platform": "tiktok",
            "reference_counts": {"images": 1},
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["vendor_calls_performed"] is False
    assert data["paid_video_vendor_calls_allowed"] is False
    assert data["parsed"]["duration"]["requested_s"] == 45
    assert data["parsed"]["output_intent"] == "sell_product"


def test_autonomous_creative_producer_v2_endpoint_returns_script_graph_without_paid_calls():
    response = client.post(
        "/api/v1/director/autonomous/creative-producer-v2",
        json={
            "user_idea": "Hay lam video 45s quang cao serum cho TikTok VN, co anh san pham.",
            "target_market": "vn",
            "target_platform": "tiktok",
            "reference_counts": {"images": 1},
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["vendor_calls_performed"] is False
    assert data["paid_video_vendor_calls_allowed"] is False
    assert data["selected_angle"]["angle_id"] == "proof_first_transformation"
    assert len(data["script_beats"]) >= 4
    assert data["shot_graph"]["node_count"] >= len(data["script_beats"])


def test_autonomous_prompt_execution_contract_endpoint_returns_compiled_shots_without_paid_calls():
    response = client.post(
        "/api/v1/director/autonomous/prompt-execution-contract",
        json={
            "user_idea": "Hay lam video 45s quang cao serum cho TikTok VN, co anh san pham.",
            "target_market": "vn",
            "target_platform": "tiktok",
            "reference_counts": {"images": 1},
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["schema_version"] == "cinejelly.prompt_execution_contract.v3"
    assert data["vendor_calls_performed"] is False
    assert data["paid_video_vendor_calls_allowed"] is False
    assert data["compiled_shots"]
    assert data["readiness"]["compiled_shot_count"] == len(data["compiled_shots"])
    assert "[ACTION]" in data["compiled_shots"][0]["prompt"]


def test_autonomous_viral_creative_brain_endpoint_returns_hooks_without_paid_calls():
    response = client.post(
        "/api/v1/director/autonomous/viral-creative-brain",
        json={
            "user_idea": "Hay lam video 45s quang cao serum cho TikTok VN, co anh san pham.",
            "target_market": "vn",
            "target_platform": "tiktok",
            "reference_counts": {"images": 1},
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["schema_version"] == "cinejelly.viral_creative_brain.v1"
    assert data["vendor_calls_performed"] is False
    assert data["paid_video_vendor_calls_allowed"] is False
    assert data["selected_viral_pattern"]["pattern_id"] == "proof_first_scroll_stop"
    assert len(data["hook_variants"]) >= 4
    assert data["platform_package"]["cta"]


def test_autonomous_output_qa_retry_brain_endpoint_returns_retry_contract_without_paid_calls():
    response = client.post(
        "/api/v1/director/autonomous/output-qa-retry-brain",
        json={
            "user_idea": "Hay lam video 45s quang cao serum cho TikTok VN, co anh san pham.",
            "target_market": "vn",
            "target_platform": "tiktok",
            "reference_counts": {"images": 1},
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["schema_version"] == "cinejelly.output_qa_retry_brain.v1"
    assert data["vendor_calls_performed"] is False
    assert data["paid_video_vendor_calls_allowed"] is False
    assert data["per_shot_qa"]
    assert data["readiness"]["retry_recipe_count"] == len(data["per_shot_qa"])
    assert data["retry_policy"]["paid_retry_vendor_calls_allowed"] is False


def test_direct_video_preview_payload_accepts_video_ref_only_seedance_fast():
    video_ref_only = client.post(
        "/api/v1/video/direct/preview-payload",
        json={
            "model_key": "seedance_2_0_fast",
            "prompt": "Match the camera motion from the video reference.",
            "reference_videos": ["https://cdn.example.com/motion.mp4"],
            "duration_s": 4,
            "resolution": "480p",
            "aspect_ratio": "9:16",
        },
    )
    assert video_ref_only.status_code == 200, video_ref_only.text
    assert video_ref_only.json()["model_key"] == "seedance_2_0_fast_ref"
    assert video_ref_only.json()["payload"]["reference_videos"] == [
        "https://cdn.example.com/motion.mp4"
    ]


def test_pick_strategy_accepts_concrete_seedance_keys():
    assert pick_strategy(
        user_model="seedance_2_0_fast_ref",
        total_duration_s=10,
        num_shots=3,
        has_cross_location_cut=False,
    ) == "single_call_multi_shot"


def test_per_shot_duration_normalization_clamps_seedance_vendor_units():
    short = _minimal_shot()
    short.duration_s = 2
    short.end_s = 2

    long = _minimal_shot()
    long.shot_id = "S2"
    long.index = 1
    long.start_s = 2
    long.end_s = 22
    long.duration_s = 20

    plan = DirectorPlan(
        plan_id="plan_duration_fit",
        created_at="2026-06-01T00:00:00Z",
        continuity_bible=_minimal_bible(),
        shot_list=[short, long],
        storyboard_grid=[],
        evaluation=EvaluationReport(
            consistency_score=8,
            viral_potential_score=8,
            cinematic_score=8,
            pacing_score=8,
            brand_safety_score=9,
            overall_score=8,
        ),
        cost_estimate=CostEstimate(),
    )

    warnings = normalize_per_shot_durations_for_model(plan, "seedance_2_0_fast_ref")

    assert len(warnings) == 2
    assert [shot.duration_s for shot in plan.shot_list] == [4, 15]
    assert [(shot.start_s, shot.end_s) for shot in plan.shot_list] == [(0.0, 4.0), (4.0, 19.0)]
    assert plan.continuity_bible.duration_s == 19


def test_director_job_feedback_is_persisted_and_returned_without_paid_render():
    job_id = "test_phase3b_feedback_job"
    feedback_path = BACKEND_ROOT / "data" / "render_feedback" / f"{job_id}.json"
    feedback_path.unlink(missing_ok=True)
    _JOBS_STORE[job_id] = {
        "status": "done",
        "progress": 100,
        "mode": "autonomous",
        "model_key": "seedance_2_0_fast_t2v",
        "output_url": "https://cdn.example.com/test-feedback.mp4",
    }

    try:
        posted = client.post(
            f"/api/v1/director/jobs/{job_id}/feedback",
            json={
                "rating": "needs_work",
                "issue_tags": ["weak_hook", "prompt_mismatch"],
                "notes": "Hook is too generic for this niche.",
                "reviewer": "pytest",
            },
        )
        assert posted.status_code == 200, posted.text
        body = posted.json()
        assert body["summary"]["feedback_count"] == 1
        assert body["summary"]["has_blocking_issue"] is True
        assert body["summary"]["recommended_next_action"] == "revise_brief_or_route_before_rerender"

        fetched = client.get(f"/api/v1/director/jobs/{job_id}/feedback")
        assert fetched.status_code == 200, fetched.text
        evidence = fetched.json()
        assert evidence["schema_version"] == "cinejelly.render_feedback_evidence.v1"
        assert evidence["entries"][0]["model_key"] == "seedance_2_0_fast_t2v"

        job = client.get(f"/api/v1/director/jobs/{job_id}")
        assert job.status_code == 200, job.text
        assert job.json()["feedback_summary"]["feedback_count"] == 1
    finally:
        _JOBS_STORE.pop(job_id, None)
        feedback_path.unlink(missing_ok=True)


def test_phase4_completion_audit_endpoint_is_non_paid_and_locked():
    res = client.get("/api/v1/director/autonomous/phase4-completion-audit")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["schema_version"] == "cinejelly.phase4_non_paid_completion_audit.v1"
    assert data["verdict"]["non_paid_phase4_complete"] is True
    assert data["verdict"]["top_tier_claim_allowed"] is False
    assert data["vendor_call_policy"]["vendor_calls_allowed_by_this_audit"] is False
    checks = {item["key"]: item["status"] for item in data["checks"]}
    assert checks["vendor_spend_guard"] == "passed"
    assert checks["paid_output_proof"] == "locked"
