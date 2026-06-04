"""Phase 13 commercial features and long-form monitoring tests."""
from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_longform_monitoring_records_job_metrics_and_alerts(tmp_path, monkeypatch) -> None:
    """Monitoring should persist job state, segment timing, score alerts, and summary."""
    from monitoring import longform_monitor

    root = tmp_path / "monitor"
    monkeypatch.setattr(longform_monitor, "_ROOT", root)
    monkeypatch.setattr(longform_monitor, "_STATE_DIR", root / "jobs")
    monkeypatch.setattr(longform_monitor, "_EVENTS_PATH", root / "events.jsonl")
    monkeypatch.setattr(longform_monitor, "_ALERTS_PATH", root / "alerts.jsonl")

    longform_monitor.record_job_started(
        job_id="job_monitor_1",
        segment_count=3,
        model="seedance_2_0",
        cost_estimate={"total_cost_usd": 1.25},
    )
    longform_monitor.record_segment_event(
        job_id="job_monitor_1",
        event={"event": "segment_started", "segment_id": "segment_01", "segment_index": 0},
    )
    longform_monitor.record_segment_event(
        job_id="job_monitor_1",
        event={"event": "segment_completed", "segment_id": "segment_01", "segment_index": 0},
    )
    alert = longform_monitor.record_consistency_score(
        job_id="job_monitor_1",
        segment_id="segment_01",
        score=42.0,
        action="block",
        warnings=["product_visibility_below_threshold"],
    )
    longform_monitor.record_upload_result(job_id="job_monitor_1", success=True, storage_key="longform/job_monitor_1/final.mp4")
    longform_monitor.record_job_finished(job_id="job_monitor_1", status="completed")

    state = longform_monitor.load_job_state("job_monitor_1")
    summary = longform_monitor.monitoring_summary()

    assert alert is not None
    assert state is not None
    assert state["status"] == "completed"
    assert state["completed_segments"] == 1
    assert state["segments"]["segment_01"]["status"] == "completed"
    assert summary["job_count"] == 1
    assert summary["status_counts"]["completed"] == 1
    assert any(item["alert_type"] == "low_consistency_score" for item in summary["recent_alerts"])


def test_commercial_store_brand_template_credit_and_analytics(tmp_path, monkeypatch) -> None:
    """Brand kits, templates, usage ledger, and analytics should persist to disk."""
    from commercial import commercial_store

    root = tmp_path / "commercial"
    monkeypatch.setattr(commercial_store, "_ROOT", root)
    monkeypatch.setattr(commercial_store, "_BRANDS_DIR", root / "brand_kits")
    monkeypatch.setattr(commercial_store, "_TEMPLATES_DIR", root / "templates")
    monkeypatch.setattr(commercial_store, "_USAGE_DIR", root / "usage")
    monkeypatch.setattr(commercial_store, "_LEDGER_PATH", root / "usage_ledger.jsonl")

    kit = commercial_store.upsert_brand_kit(
        owner_user_id="user_commercial",
        name="CineForge Labs",
        primary_colors=["#00D4FF", "#101820"],
        fonts=["Inter"],
        voice="precise and premium",
        style_guide="clean cinematic SaaS visuals",
    )
    templates = commercial_store.list_templates()
    usage = commercial_store.charge_credits(
        user_id="user_commercial",
        job_id="job_commercial",
        credits=25,
        estimated_cost_usd=0.25,
        model="seedance_2_0",
        segment_count=3,
        render_path="long_form_segmented",
        metadata={"brand_id": kit.brand_id, "template_id": templates[0].template_id},
    )
    balance = commercial_store.credit_balance("user_commercial")
    analytics = commercial_store.analytics_summary(user_id="user_commercial", brand_id=kit.brand_id)

    assert commercial_store.load_brand_kit(kit.brand_id) is not None
    assert any(template.template_id == "ugc_ad" for template in templates)
    assert usage.credits_delta == -25
    assert balance["credits_balance"] == 975
    assert analytics["render_count"] == 1
    assert analytics["credits_spent"] == 25


def test_autonomous_dry_run_applies_brand_kit_and_template(monkeypatch, tmp_path) -> None:
    """Commercial context should modify the actual compiled prompt path."""
    from api.routes import director
    from commercial import commercial_store

    root = tmp_path / "commercial"
    monkeypatch.setattr(commercial_store, "_ROOT", root)
    monkeypatch.setattr(commercial_store, "_BRANDS_DIR", root / "brand_kits")
    monkeypatch.setattr(commercial_store, "_TEMPLATES_DIR", root / "templates")
    monkeypatch.setattr(commercial_store, "_USAGE_DIR", root / "usage")
    monkeypatch.setattr(commercial_store, "_LEDGER_PATH", root / "usage_ledger.jsonl")

    kit = commercial_store.upsert_brand_kit(
        owner_user_id="user_brand_prompt",
        name="Northstar Beauty",
        primary_colors=["#F4D35E"],
        fonts=["Inter"],
        voice="warm expert",
        style_guide="luxury macro skincare lighting",
        negative_constraints=["no off-brand colors"],
    )
    spawned: list[Any] = []
    monkeypatch.setattr(director, "_spawn", lambda coro: spawned.append(coro))

    async def run_case() -> None:
        director._JOBS_STORE.clear()
        idea = "Create a 12s premium beauty serum product ad with proof and payoff."
        source_hash = hashlib.sha256(idea.encode("utf-8")).hexdigest()
        request = director.AutonomousGenerateRequest(
            user_idea=idea,
            target_market="vn",
            target_platform="tiktok",
            duration_hint_s=12,
            user_model="auto",
            resolution="720p",
            dry_run_only=True,
            user_id="user_brand_prompt",
            brand_kit_id=kit.brand_id,
            template_id="beauty_proof",
            approved_plan_id="approved_brand_plan",
            approved_plan_source_hash=source_hash,
            approved_plan_source_length=len(idea),
        )
        response = await director.autonomous_generate(request, idempotency_key=None)
        for coro in spawned:
            coro.close()
        job = director._JOBS_STORE[response["job_id"]]
        execution_plan = job["seedance_execution_plan"]
        prompt = execution_plan["shots"][0]["compiled_prompt"]

        assert "Northstar Beauty" in prompt
        assert "luxury macro skincare lighting" in prompt
        assert execution_plan["metadata"]["brand_kit_id"] == kit.brand_id
        assert execution_plan["metadata"]["template_id"] == "beauty_proof"
        assert any(entry["stage"] == "commercial_context" for entry in response["pipeline_trace"]["entries"])

    asyncio.run(run_case())
