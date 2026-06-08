"""Production endpoint migration tests for /director/autonomous."""
from __future__ import annotations

import asyncio
import hashlib
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_autonomous_endpoint_queues_seedance_execution_plan_not_legacy_render(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production autonomous route must use ApprovalLock + RenderExecutor safe path."""
    from api.routes import director

    spawned: list[Any] = []

    def capture_spawn(coro: Any) -> None:
        spawned.append(coro)
        return None

    async def fail_legacy_render_plan(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("legacy render_plan must not be called by /director/autonomous")

    monkeypatch.setattr(director, "_spawn", capture_spawn)
    monkeypatch.setattr(director.video_worker, "render_plan", fail_legacy_render_plan)

    async def run_case() -> None:
        director._JOBS_STORE.clear()
        request = _approved_request(dry_run_only=True)
        response = await director.autonomous_generate(request, idempotency_key=None)

        assert response["execution_mode"] == "seedance_execution_plan"
        assert response["legacy_render_plan_used"] is False
        assert response["editor_preview"]["caption_en"]
        assert response["editor_preview"]["distribution_package"]["source"] == "seedance_execution_plan_pipeline"
        assert response["approval_verification"]["valid"] is True
        assert response["seedance_execution_plan"]["shot_count"] >= 1
        assert [entry["stage"] for entry in response["pipeline_trace"]["entries"]] == [
            "input_contract",
            "input_analysis",
            "identity_consistency",
            "creative_reasoning",
            "creative_planning",
            "storyboard_generation",
            "seedance_prompt_compile",
            "approval_lock",
        ]
        assert spawned, "endpoint should queue the safe Seedance execution coroutine"

        await spawned.pop(0)
        job = director._JOBS_STORE[response["job_id"]]
        assert job["status"] == "dry_run"
        assert job["execution_mode"] == "seedance_execution_plan"
        assert job["render_execution"]["approval_verification"]["valid"] is True
        assert job["render_execution"]["dry_run_report"]["approval_valid"] is True
        assert job["autonomous_meta"]["legacy_render_plan_used"] is False
        assert job["autonomous_meta"]["editor_preview"]["caption_en"]

    asyncio.run(run_case())


def test_autonomous_endpoint_enables_long_form_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Long-form dry-run should use the segmented production path, not legacy DirectorPlan."""
    from api.routes import director

    spawned: list[Any] = []
    monkeypatch.setattr(director, "_spawn", lambda coro: spawned.append(coro))

    async def run_case() -> None:
        director._JOBS_STORE.clear()
        request = director.AutonomousGenerateRequest(
            user_idea="Create a 30s premium beauty serum story with three proof beats and a final offer.",
            target_market="vn",
            target_platform="tiktok",
            duration_hint_s=30,
            user_model="auto",
            resolution="720p",
            dry_run_only=True,
        )
        response = await director.autonomous_generate(request, idempotency_key=None)

        assert response["execution_mode"] == "long_form_segmented"
        assert response["legacy_render_plan_used"] is False
        assert response["longform_plan"]["total_duration_s"] == 30
        assert len(response["longform_plan"]["segments"]) == 3
        assert response["render_dry_run_report"]["approval_valid"] is True
        assert response["seedance_execution_plan"]["duration_s"] == 30
        assert spawned == [], "long-form dry-run should not spawn a background worker"
        job = director._JOBS_STORE[response["job_id"]]
        assert job["status"] == "dry_run"
        assert job["execution_mode"] == "long_form_segmented"
        assert job["longform_render_execution"]["status"] == "dry_run"

    asyncio.run(run_case())


def test_autonomous_endpoint_paid_long_form_requires_approved_dry_run() -> None:
    """Paid long-form render should not start without an approved dry-run job id."""
    from api.routes import director

    async def run_case() -> None:
        user_idea = "Create a 30s premium beauty serum story with three proof beats and a final offer."
        request = director.AutonomousGenerateRequest(
            user_idea=user_idea,
            target_market="vn",
            target_platform="tiktok",
            duration_hint_s=30,
            user_model="auto",
            resolution="720p",
            dry_run_only=False,
            approved_plan_id="approved_longform_plan",
            approved_plan_source_hash=hashlib.sha256(user_idea.encode("utf-8")).hexdigest(),
            approved_plan_source_length=len(user_idea),
        )
        with pytest.raises(Exception) as exc_info:
            await director.autonomous_generate(request, idempotency_key=None)
        error = exc_info.value
        assert getattr(error, "status_code", None) == 422
        assert getattr(error, "detail", {}).get("code") == "long_form_dry_run_required"

    asyncio.run(run_case())


def test_autonomous_endpoint_rejects_missing_env_before_paid_render(monkeypatch: pytest.MonkeyPatch) -> None:
    """Paid render must report missing env instead of queueing a fake job."""
    from api.routes import director

    spawned: list[Any] = []
    monkeypatch.setattr(director, "_spawn", lambda coro: spawned.append(coro))
    monkeypatch.setattr(director.app_settings, "atlascloud_api_key", "...")

    async def run_case() -> None:
        director._JOBS_STORE.clear()
        request = _approved_request(dry_run_only=False)
        with pytest.raises(Exception) as exc_info:
            await director.autonomous_generate(request, idempotency_key=None)
        error = exc_info.value
        assert getattr(error, "status_code", None) == 503
        detail = getattr(error, "detail", {})
        assert detail.get("code") == "missing_env"
        assert detail.get("missing_env") == ["ATLASCLOUD_API_KEY"]
        assert detail.get("vendor_calls_performed") is False
        assert detail.get("paid_video_vendor_calls_allowed") is False
        assert spawned == []
        assert director._JOBS_STORE == {}

    asyncio.run(run_case())


def test_autonomous_endpoint_rejects_unsupported_duration_gap() -> None:
    """16-29s is intentionally rejected until a distinct mid-form strategy exists."""
    from api.routes import director

    async def run_case() -> None:
        request = director.AutonomousGenerateRequest(
            user_idea="Create a 20s premium beauty serum story with product proof and a final offer.",
            target_market="vn",
            target_platform="tiktok",
            duration_hint_s=20,
            user_model="auto",
            resolution="720p",
            dry_run_only=True,
        )
        with pytest.raises(Exception) as exc_info:
            await director.autonomous_generate(request, idempotency_key=None)
        error = exc_info.value
        assert getattr(error, "status_code", None) == 422
        assert getattr(error, "detail", {}).get("code") == "autonomous_duration_gap_not_supported"

    asyncio.run(run_case())


def test_autonomous_endpoint_rejects_duration_over_60s() -> None:
    """Phase 10 production endpoint should fail-safe beyond the 30-60s MVP window."""
    from api.routes import director

    async def run_case() -> None:
        request = director.AutonomousGenerateRequest(
            user_idea="Create a 75s premium beauty serum story with multiple proof beats and a final offer.",
            target_market="vn",
            target_platform="tiktok",
            duration_hint_s=75,
            user_model="auto",
            resolution="720p",
            dry_run_only=True,
        )
        with pytest.raises(Exception) as exc_info:
            await director.autonomous_generate(request, idempotency_key=None)
        error = exc_info.value
        assert getattr(error, "status_code", None) == 422
        assert getattr(error, "detail", {}).get("code") == "autonomous_duration_too_long"

    asyncio.run(run_case())


def test_autonomous_endpoint_paid_long_form_reuses_approved_dry_run_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Paid long-form render should reuse the exact dry-run bundle and segment approvals."""
    from api.routes import director

    spawned: list[Any] = []
    render_calls: list[dict[str, Any]] = []

    def capture_spawn(coro: Any) -> None:
        spawned.append(coro)

    async def capture_longform_render(**kwargs: Any) -> dict[str, Any]:
        render_calls.append(kwargs)
        return {"status": "captured"}

    monkeypatch.setattr(director, "_spawn", capture_spawn)
    monkeypatch.setattr(director.video_worker, "render_longform_execution_plan", capture_longform_render)
    monkeypatch.setattr(director.app_settings, "atlascloud_api_key", "test_atlas_key")

    async def run_case() -> None:
        director._JOBS_STORE.clear()
        user_idea = "Create a 30s premium beauty serum story with three proof beats and a final offer."
        user_id = f"test_paid_reuse_{uuid.uuid4().hex[:8]}"
        source_hash = hashlib.sha256(user_idea.encode("utf-8")).hexdigest()
        dry_run_request = director.AutonomousGenerateRequest(
            user_idea=user_idea,
            target_market="vn",
            target_platform="tiktok",
            duration_hint_s=30,
            user_model="auto",
            resolution="720p",
            dry_run_only=True,
            user_id=user_id,
            approved_plan_id="approved_longform_plan",
            approved_plan_source_hash=source_hash,
            approved_plan_source_length=len(user_idea),
        )
        dry_run_response = await director.autonomous_generate(dry_run_request, idempotency_key=None)
        for coro in spawned:
            coro.close()
        spawned.clear()
        segment_ids = [segment["segment_id"] for segment in dry_run_response["longform_plan"]["segments"]]

        paid_request = director.AutonomousGenerateRequest(
            user_idea=user_idea,
            target_market="vn",
            target_platform="tiktok",
            duration_hint_s=30,
            user_model="auto",
            resolution="720p",
            dry_run_only=False,
            user_id=user_id,
            approved_plan_id="approved_longform_plan",
            approved_plan_source_hash=source_hash,
            approved_plan_source_length=len(user_idea),
            approved_dry_run_job_id=dry_run_response["job_id"],
            approved_segment_ids=segment_ids,
            consistency_review_approved=True,
            consistency_review_decision="approved",
            consistency_review_reason="Reviewed product and style continuity risk; references are acceptable.",
            consistency_reviewed_segment_ids=segment_ids,
        )
        paid_response = await director.autonomous_generate(paid_request, idempotency_key=None)
        assert paid_response["execution_mode"] == "long_form_segmented"
        assert paid_response["job_id"] == dry_run_response["job_id"]
        assert spawned
        await spawned.pop(0)
        assert render_calls
        assert render_calls[0]["dry_run_approved"] is True
        assert render_calls[0]["longform_plan"].longform_plan_id == dry_run_response["job_id"]

    asyncio.run(run_case())


def test_autonomous_endpoint_rejects_incomplete_segment_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    """Paid long-form render must include every reviewed segment id from the dry-run bundle."""
    from api.routes import director

    spawned: list[Any] = []
    monkeypatch.setattr(director, "_spawn", lambda coro: spawned.append(coro))
    monkeypatch.setattr(director.app_settings, "atlascloud_api_key", "test_atlas_key")

    async def run_case() -> None:
        director._JOBS_STORE.clear()
        user_idea = "Create a 30s premium beauty serum story with three proof beats and a final offer."
        user_id = f"test_segment_review_{uuid.uuid4().hex[:8]}"
        source_hash = hashlib.sha256(user_idea.encode("utf-8")).hexdigest()
        dry_run_request = director.AutonomousGenerateRequest(
            user_idea=user_idea,
            target_market="vn",
            target_platform="tiktok",
            duration_hint_s=30,
            user_model="auto",
            resolution="720p",
            dry_run_only=True,
            user_id=user_id,
            approved_plan_id="approved_longform_plan",
            approved_plan_source_hash=source_hash,
            approved_plan_source_length=len(user_idea),
        )
        dry_run_response = await director.autonomous_generate(dry_run_request, idempotency_key=None)
        for coro in spawned:
            coro.close()
        spawned.clear()
        segment_ids = [segment["segment_id"] for segment in dry_run_response["longform_plan"]["segments"]]

        paid_request = director.AutonomousGenerateRequest(
            user_idea=user_idea,
            target_market="vn",
            target_platform="tiktok",
            duration_hint_s=30,
            user_model="auto",
            resolution="720p",
            dry_run_only=False,
            user_id=user_id,
            approved_plan_id="approved_longform_plan",
            approved_plan_source_hash=source_hash,
            approved_plan_source_length=len(user_idea),
            approved_dry_run_job_id=dry_run_response["job_id"],
            approved_segment_ids=segment_ids[:-1],
            consistency_review_approved=True,
            consistency_review_decision="approved",
            consistency_review_reason="Reviewed consistency risk before checking segment list.",
            consistency_reviewed_segment_ids=segment_ids[:-1],
        )
        with pytest.raises(Exception) as exc_info:
            await director.autonomous_generate(paid_request, idempotency_key=None)
        error = exc_info.value
        assert getattr(error, "status_code", None) == 422
        assert getattr(error, "detail", {}).get("code") == "long_form_segment_review_incomplete"

    asyncio.run(run_case())


def test_autonomous_endpoint_rejects_consistency_review_without_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """requires_review consistency approval must include a human reason."""
    from api.routes import director

    spawned: list[Any] = []
    monkeypatch.setattr(director, "_spawn", lambda coro: spawned.append(coro))
    monkeypatch.setattr(director.app_settings, "atlascloud_api_key", "test_atlas_key")

    async def run_case() -> None:
        director._JOBS_STORE.clear()
        user_idea = "Create a 30s premium beauty serum story with three proof beats and a final offer."
        user_id = f"test_review_reason_{uuid.uuid4().hex[:8]}"
        source_hash = hashlib.sha256(user_idea.encode("utf-8")).hexdigest()
        dry_run_request = director.AutonomousGenerateRequest(
            user_idea=user_idea,
            target_market="vn",
            target_platform="tiktok",
            duration_hint_s=30,
            user_model="auto",
            resolution="720p",
            dry_run_only=True,
            user_id=user_id,
            approved_plan_id="approved_longform_plan",
            approved_plan_source_hash=source_hash,
            approved_plan_source_length=len(user_idea),
        )
        dry_run_response = await director.autonomous_generate(dry_run_request, idempotency_key=None)
        for coro in spawned:
            coro.close()
        spawned.clear()
        segment_ids = [segment["segment_id"] for segment in dry_run_response["longform_plan"]["segments"]]

        paid_request = director.AutonomousGenerateRequest(
            user_idea=user_idea,
            target_market="vn",
            target_platform="tiktok",
            duration_hint_s=30,
            user_model="auto",
            resolution="720p",
            dry_run_only=False,
            user_id=user_id,
            approved_plan_id="approved_longform_plan",
            approved_plan_source_hash=source_hash,
            approved_plan_source_length=len(user_idea),
            approved_dry_run_job_id=dry_run_response["job_id"],
            approved_segment_ids=segment_ids,
            consistency_review_approved=True,
            consistency_review_decision="approved",
        )
        with pytest.raises(Exception) as exc_info:
            await director.autonomous_generate(paid_request, idempotency_key=None)
        error = exc_info.value
        assert getattr(error, "status_code", None) == 422
        assert getattr(error, "detail", {}).get("code") == "consistency_review_reason_required"

    asyncio.run(run_case())


def test_autonomous_endpoint_rejects_consistency_review_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rejected consistency review should block paid long-form render."""
    from api.routes import director

    spawned: list[Any] = []
    monkeypatch.setattr(director, "_spawn", lambda coro: spawned.append(coro))
    monkeypatch.setattr(director.app_settings, "atlascloud_api_key", "test_atlas_key")

    async def run_case() -> None:
        director._JOBS_STORE.clear()
        user_idea = "Create a 30s premium beauty serum story with three proof beats and a final offer."
        user_id = f"test_review_reject_{uuid.uuid4().hex[:8]}"
        source_hash = hashlib.sha256(user_idea.encode("utf-8")).hexdigest()
        dry_run_request = director.AutonomousGenerateRequest(
            user_idea=user_idea,
            target_market="vn",
            target_platform="tiktok",
            duration_hint_s=30,
            user_model="auto",
            resolution="720p",
            dry_run_only=True,
            user_id=user_id,
            approved_plan_id="approved_longform_plan",
            approved_plan_source_hash=source_hash,
            approved_plan_source_length=len(user_idea),
        )
        dry_run_response = await director.autonomous_generate(dry_run_request, idempotency_key=None)
        for coro in spawned:
            coro.close()
        spawned.clear()
        segment_ids = [segment["segment_id"] for segment in dry_run_response["longform_plan"]["segments"]]

        paid_request = director.AutonomousGenerateRequest(
            user_idea=user_idea,
            target_market="vn",
            target_platform="tiktok",
            duration_hint_s=30,
            user_model="auto",
            resolution="720p",
            dry_run_only=False,
            user_id=user_id,
            approved_plan_id="approved_longform_plan",
            approved_plan_source_hash=source_hash,
            approved_plan_source_length=len(user_idea),
            approved_dry_run_job_id=dry_run_response["job_id"],
            approved_segment_ids=segment_ids,
            consistency_review_approved=False,
            consistency_review_decision="rejected",
            consistency_review_reason="Product identity risk is too high for paid render.",
            consistency_reviewed_segment_ids=segment_ids,
        )
        with pytest.raises(Exception) as exc_info:
            await director.autonomous_generate(paid_request, idempotency_key=None)
        error = exc_info.value
        assert getattr(error, "status_code", None) == 422
        assert getattr(error, "detail", {}).get("code") == "consistency_review_rejected"

    asyncio.run(run_case())


def test_autonomous_endpoint_rejects_paid_render_without_approved_source() -> None:
    """Paid autonomous render must require approved render-source metadata."""
    from api.routes import director

    async def run_case() -> None:
        request = director.AutonomousGenerateRequest(
            user_idea="Create a 12s premium beauty serum product ad with macro texture, hero reveal, and payoff.",
            target_market="vn",
            target_platform="tiktok",
            duration_hint_s=12,
            user_model="auto",
            resolution="720p",
            dry_run_only=False,
        )
        with pytest.raises(Exception) as exc_info:
            await director.autonomous_generate(request, idempotency_key=None)
        error = exc_info.value
        assert getattr(error, "status_code", None) == 422
        assert getattr(error, "detail", {}).get("code") == "approval_lock_source_required"

    asyncio.run(run_case())


def test_autonomous_endpoint_rejects_wan_without_image_reference_before_chain() -> None:
    """Image-driven Wan route must not use placeholder or text-only fallback refs."""
    from api.routes import director

    async def run_case() -> None:
        director._JOBS_STORE.clear()
        request = director.AutonomousGenerateRequest(
            user_idea=(
                "Create a 10s TikTok UGC product review for sunscreen with a Vietnamese "
                "creator speaking to camera, clear lip-sync and product payoff."
            ),
            target_market="vn",
            target_platform="tiktok",
            duration_hint_s=10,
            user_model="wan_2_7",
            resolution="720p",
            dry_run_only=True,
            auto_select_asset_pins=False,
            reference_image_urls=[],
        )
        with pytest.raises(Exception) as exc_info:
            await director.autonomous_generate(request, idempotency_key=None)
        error = exc_info.value
        assert getattr(error, "status_code", None) == 422
        detail = getattr(error, "detail", {})
        assert detail.get("code") == "model_requires_image_reference"
        assert detail.get("vendor_calls_performed") is False
        assert detail.get("paid_video_vendor_calls_allowed") is False
        assert director._JOBS_STORE == {}

    asyncio.run(run_case())


def _approved_request(*, dry_run_only: bool) -> Any:
    from api.routes import director

    user_idea = (
        "Create a 12s premium beauty serum product ad with macro texture hook, "
        "hero product reveal, and polished payoff frame."
    )
    source_hash = hashlib.sha256(user_idea.encode("utf-8")).hexdigest()
    return director.AutonomousGenerateRequest(
        user_idea=user_idea,
        target_market="vn",
        target_platform="tiktok",
        duration_hint_s=12,
        user_model="auto",
        resolution="720p",
        approved_plan_id="plan_seedance_exec_test",
        approved_plan_source_hash=source_hash,
        approved_plan_source_length=len(user_idea),
        dry_run_only=dry_run_only,
    )
