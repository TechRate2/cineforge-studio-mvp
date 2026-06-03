"""Production endpoint migration tests for /director/autonomous."""
from __future__ import annotations

import asyncio
import hashlib
import sys
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


def test_autonomous_endpoint_blocks_long_form_on_new_paid_path() -> None:
    """Long-form must not fall back to legacy DirectorPlan on the production route."""
    from api.routes import director

    async def run_case() -> None:
        request = director.AutonomousGenerateRequest(
            user_idea="Create a 30s premium beauty serum story with three proof beats and a final offer.",
            target_market="vn",
            target_platform="tiktok",
            duration_hint_s=30,
            user_model="auto",
            resolution="720p",
            dry_run_only=True,
        )
        with pytest.raises(Exception) as exc_info:
            await director.autonomous_generate(request, idempotency_key=None)
        error = exc_info.value
        assert getattr(error, "status_code", None) == 422
        detail = getattr(error, "detail", {})
        assert detail.get("code") == "long_form_seedance_pipeline_not_ready"
        assert detail.get("strategy") == "block_until_segmented_long_form_seedance_pipeline_is_approved"
        assert detail.get("max_single_execution_duration_s") == 15

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
