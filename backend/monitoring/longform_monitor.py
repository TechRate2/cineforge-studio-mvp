"""File-backed monitoring and alerting for long-form render jobs.

This module is intentionally dependency-light and production-safe. It records
runtime events as append-only JSONL plus a compact per-job state document so the
service can surface alerts even before a database/metrics backend is introduced.
"""
from __future__ import annotations

import json
import re
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field


LongFormAlertSeverity = Literal["info", "warning", "critical"]
LongFormJobStatus = Literal["pending", "rendering", "assembling", "completed", "failed"]

_ROOT = Path(__file__).parent.parent / "data" / "monitoring" / "longform"
_STATE_DIR = _ROOT / "jobs"
_EVENTS_PATH = _ROOT / "events.jsonl"
_ALERTS_PATH = _ROOT / "alerts.jsonl"
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,180}$")


class LongFormMetricEvent(BaseModel):
    """One structured monitoring event emitted by the long-form runtime."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: f"lf_evt_{uuid.uuid4().hex[:12]}")
    job_id: str
    event_type: str
    status: str | None = None
    segment_id: str | None = None
    model: str | None = None
    cost_estimate_usd: float | None = None
    consistency_score: float | None = None
    duration_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LongFormAlert(BaseModel):
    """An operational alert derived from long-form job metrics."""

    model_config = ConfigDict(extra="forbid")

    alert_id: str = Field(default_factory=lambda: f"lf_alert_{uuid.uuid4().hex[:12]}")
    job_id: str | None = None
    alert_type: str
    severity: LongFormAlertSeverity
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def record_job_started(
    *,
    job_id: str,
    segment_count: int,
    model: str,
    cost_estimate: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create or update monitoring state for a long-form job start."""
    state = _load_or_new_state(job_id)
    now = _now_iso()
    state.update(
        status="rendering",
        started_at=state.get("started_at") or now,
        updated_at=now,
        segment_count=max(0, int(segment_count)),
        model=str(model or ""),
        cost_estimate=cost_estimate or {},
        metadata={**(state.get("metadata") or {}), **(metadata or {})},
    )
    _write_state(job_id, state)
    event = LongFormMetricEvent(
        job_id=job_id,
        event_type="job_started",
        status="rendering",
        model=state.get("model") or None,
        cost_estimate_usd=_cost_usd(cost_estimate or {}),
        metadata={"segment_count": segment_count, **(metadata or {})},
    )
    _append_jsonl(_EVENTS_PATH, event.model_dump(mode="json"))
    return state


def record_segment_event(*, job_id: str, event: dict[str, Any]) -> dict[str, Any]:
    """Record a segment progress event and update per-segment timing."""
    state = _load_or_new_state(job_id)
    now = _now_iso()
    segment_id = str(event.get("segment_id") or "").strip()
    event_name = str(event.get("event") or "segment_event").strip()
    segments = dict(state.get("segments") or {})
    segment_state = dict(segments.get(segment_id) or {}) if segment_id else {}
    if segment_id:
        segment_state.setdefault("segment_id", segment_id)
        segment_state["index"] = event.get("segment_index")
        segment_state["updated_at"] = now
        if event_name == "segment_started":
            segment_state["started_at"] = now
            segment_state["status"] = "rendering"
        elif event_name == "segment_completed":
            segment_state["completed_at"] = now
            segment_state["status"] = "completed"
            segment_state["duration_ms"] = _elapsed_ms(segment_state.get("started_at"), now)
        elif event_name in {"segment_failed", "segment_repair"}:
            segment_state["status"] = "failed" if event_name == "segment_failed" else "repairing"
            segment_state["errors"] = event.get("errors") or event.get("qa_errors") or []
        segments[segment_id] = segment_state
    state["segments"] = segments
    state["updated_at"] = now
    if event_name == "segment_completed":
        state["completed_segments"] = len([s for s in segments.values() if s.get("status") == "completed"])
    _write_state(job_id, state)
    metric = LongFormMetricEvent(
        job_id=job_id,
        event_type=event_name,
        status=str(segment_state.get("status") or state.get("status") or ""),
        segment_id=segment_id or None,
        duration_ms=segment_state.get("duration_ms"),
        metadata={k: v for k, v in event.items() if k not in {"video_url", "last_frame_url"}},
    )
    _append_jsonl(_EVENTS_PATH, metric.model_dump(mode="json"))
    return state


def record_consistency_score(
    *,
    job_id: str,
    segment_id: str,
    score: float | None,
    action: str | None = None,
    warnings: list[str] | None = None,
) -> LongFormAlert | None:
    """Record post-render consistency score and return an alert when needed."""
    state = _load_or_new_state(job_id)
    scores = list(state.get("consistency_scores") or [])
    entry = {
        "segment_id": segment_id,
        "score": score,
        "action": action,
        "warnings": warnings or [],
        "created_at": _now_iso(),
    }
    scores.append(entry)
    state["consistency_scores"] = scores[-50:]
    state["updated_at"] = _now_iso()
    _write_state(job_id, state)
    _append_jsonl(
        _EVENTS_PATH,
        LongFormMetricEvent(
            job_id=job_id,
            event_type="consistency_score",
            segment_id=segment_id,
            consistency_score=score,
            metadata={"action": action, "warnings": warnings or []},
        ).model_dump(mode="json"),
    )
    if score is not None and float(score) < 60.0:
        return _emit_alert(
            job_id=job_id,
            alert_type="low_consistency_score",
            severity="warning" if float(score) >= 45.0 else "critical",
            message=f"Post-render consistency score is low for {segment_id}.",
            metadata=entry,
        )
    return None


def record_upload_result(*, job_id: str, success: bool, storage_key: str | None = None, error: str | None = None) -> LongFormAlert | None:
    """Track final R2/S3 upload outcome and alert on repeated failure."""
    state = _load_or_new_state(job_id)
    failures = int(state.get("upload_failures") or 0)
    if success:
        state["upload_failures"] = 0
        state["last_upload_status"] = "completed"
    else:
        failures += 1
        state["upload_failures"] = failures
        state["last_upload_status"] = "failed"
    state["updated_at"] = _now_iso()
    _write_state(job_id, state)
    _append_jsonl(
        _EVENTS_PATH,
        LongFormMetricEvent(
            job_id=job_id,
            event_type="r2_upload_completed" if success else "r2_upload_failed",
            status=state.get("status"),
            metadata={"storage_key": storage_key, "error": _safe_text(error)},
        ).model_dump(mode="json"),
    )
    if not success and failures >= 1:
        return _emit_alert(
            job_id=job_id,
            alert_type="r2_upload_failure",
            severity="critical",
            message="Long-form final video upload failed.",
            metadata={"storage_key": storage_key, "error": _safe_text(error), "consecutive_failures": failures},
        )
    return None


def record_job_finished(*, job_id: str, status: LongFormJobStatus, error: str | None = None) -> list[LongFormAlert]:
    """Finalize job status and emit terminal alerts when failed."""
    state = _load_or_new_state(job_id)
    now = _now_iso()
    state["status"] = status
    state["updated_at"] = now
    state["completed_at"] = now if status in {"completed", "failed"} else state.get("completed_at")
    state["duration_ms"] = _elapsed_ms(state.get("started_at"), now)
    state["error"] = _safe_text(error)
    _write_state(job_id, state)
    _append_jsonl(
        _EVENTS_PATH,
        LongFormMetricEvent(
            job_id=job_id,
            event_type="job_finished",
            status=status,
            duration_ms=state.get("duration_ms"),
            metadata={"error": _safe_text(error)},
        ).model_dump(mode="json"),
    )
    alerts: list[LongFormAlert] = []
    if status == "failed":
        alert = _emit_alert(
            job_id=job_id,
            alert_type="job_failed",
            severity="warning",
            message="Long-form job failed.",
            metadata={"error": _safe_text(error), "duration_ms": state.get("duration_ms")},
        )
        alerts.append(alert)
    alerts.extend(evaluate_global_alerts())
    return alerts


def evaluate_stuck_jobs(*, timeout_minutes: int = 45) -> list[LongFormAlert]:
    """Alert on jobs that have not updated within the timeout window."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(1, timeout_minutes))
    alerts: list[LongFormAlert] = []
    for state in _iter_states():
        if state.get("status") not in {"pending", "rendering", "assembling"}:
            continue
        updated = _parse_dt(state.get("updated_at") or state.get("started_at"))
        if updated and updated < cutoff:
            alerts.append(_emit_alert(
                job_id=str(state.get("job_id") or ""),
                alert_type="job_stuck_timeout",
                severity="critical",
                message="Long-form job appears stuck beyond the monitoring timeout.",
                metadata={"status": state.get("status"), "updated_at": state.get("updated_at")},
            ))
    return alerts


def evaluate_global_alerts() -> list[LongFormAlert]:
    """Evaluate aggregate error-rate and repeated consistency alerts."""
    states = list(_iter_states())[-50:]
    if not states:
        return []
    alerts: list[LongFormAlert] = []
    terminal = [s for s in states if s.get("status") in {"completed", "failed"}]
    if len(terminal) >= 5:
        failed = [s for s in terminal if s.get("status") == "failed"]
        error_rate = len(failed) / max(1, len(terminal))
        if error_rate >= 0.4:
            alerts.append(_emit_alert(
                job_id=None,
                alert_type="high_longform_error_rate",
                severity="critical",
                message="Long-form job error rate is unusually high.",
                metadata={"error_rate": round(error_rate, 4), "sample_size": len(terminal)},
            ))
    low_scores = [
        score
        for state in states
        for score in (state.get("consistency_scores") or [])
        if isinstance(score, dict) and score.get("score") is not None and float(score.get("score")) < 60
    ]
    if len(low_scores) >= 3:
        alerts.append(_emit_alert(
            job_id=None,
            alert_type="repeated_low_consistency_score",
            severity="warning",
            message="Multiple recent long-form segments have low post-render consistency scores.",
            metadata={"count": len(low_scores)},
        ))
    return alerts


def monitoring_summary(*, limit: int = 100) -> dict[str, Any]:
    """Return an operations summary for recent long-form jobs and alerts."""
    states = list(_iter_states())[-max(1, int(limit)):]
    status_counts = Counter(str(state.get("status") or "unknown") for state in states)
    terminal = [state for state in states if state.get("status") in {"completed", "failed"}]
    failed = [state for state in terminal if state.get("status") == "failed"]
    durations = [int(state.get("duration_ms") or 0) for state in terminal if int(state.get("duration_ms") or 0) > 0]
    costs = [_cost_usd(state.get("cost_estimate") or {}) for state in states]
    models = Counter(str(state.get("model") or "unknown") for state in states)
    return {
        "schema_version": "cineforge.longform_monitoring_summary.v1",
        "job_count": len(states),
        "status_counts": dict(status_counts),
        "error_rate": round(len(failed) / max(1, len(terminal)), 4) if terminal else 0.0,
        "avg_duration_ms": int(sum(durations) / len(durations)) if durations else 0,
        "avg_estimated_cost_usd": round(sum(costs) / max(1, len([c for c in costs if c > 0])), 4) if any(costs) else 0.0,
        "model_counts": dict(models),
        "recent_alerts": list_alerts(limit=20),
        "generated_at": _now_iso(),
    }


def list_alerts(*, limit: int = 50) -> list[dict[str, Any]]:
    if not _ALERTS_PATH.exists():
        return []
    lines = _ALERTS_PATH.read_text(encoding="utf-8").splitlines()
    alerts: list[dict[str, Any]] = []
    for line in lines[-max(1, int(limit)):]:
        try:
            alerts.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return alerts


def load_job_state(job_id: str) -> dict[str, Any] | None:
    clean = _validate_job_id(job_id)
    path = _state_path(clean)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_or_new_state(job_id: str) -> dict[str, Any]:
    clean = _validate_job_id(job_id)
    existing = load_job_state(clean)
    if existing:
        return existing
    now = _now_iso()
    return {
        "schema_version": "cineforge.longform_monitoring_job.v1",
        "job_id": clean,
        "status": "pending",
        "started_at": now,
        "updated_at": now,
        "segment_count": 0,
        "completed_segments": 0,
        "segments": {},
        "consistency_scores": [],
        "upload_failures": 0,
        "cost_estimate": {},
        "metadata": {},
    }


def _write_state(job_id: str, state: dict[str, Any]) -> None:
    clean = _validate_job_id(job_id)
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = _state_path(clean)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _iter_states() -> list[dict[str, Any]]:
    if not _STATE_DIR.exists():
        return []
    states: list[dict[str, Any]] = []
    for path in sorted(_STATE_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime):
        try:
            states.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            logger.warning("[longform_monitor] failed to load state", extra={"path": str(path)})
    return states


def _emit_alert(
    *,
    job_id: str | None,
    alert_type: str,
    severity: LongFormAlertSeverity,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> LongFormAlert:
    alert = LongFormAlert(
        job_id=job_id,
        alert_type=alert_type,
        severity=severity,
        message=message,
        metadata=metadata or {},
    )
    _append_jsonl(_ALERTS_PATH, alert.model_dump(mode="json"))
    logger.warning(
        "longform_monitor_alert",
        extra={
            "alert_type": alert_type,
            "severity": severity,
            "job_id": job_id,
            "metadata": metadata or {},
        },
    )
    return alert


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def _state_path(job_id: str) -> Path:
    return _STATE_DIR / f"{_validate_job_id(job_id)}.json"


def _validate_job_id(job_id: str) -> str:
    value = str(job_id or "").strip()
    if not _JOB_ID_RE.match(value):
        raise ValueError("invalid long-form monitoring job_id")
    return value


def _cost_usd(cost: dict[str, Any]) -> float:
    for key in ("total_cost_usd", "render_cost_usd", "estimated_cost_usd"):
        value = cost.get(key)
        try:
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _elapsed_ms(start: Any, end: Any) -> int | None:
    start_dt = _parse_dt(start)
    end_dt = _parse_dt(end)
    if not start_dt or not end_dt:
        return None
    return max(0, int((end_dt - start_dt).total_seconds() * 1000))


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _safe_text(value: Any) -> str:
    return str(value or "").replace("\n", " ").replace("\r", " ")[:500]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "LongFormAlert",
    "LongFormMetricEvent",
    "evaluate_global_alerts",
    "evaluate_stuck_jobs",
    "list_alerts",
    "load_job_state",
    "monitoring_summary",
    "record_consistency_score",
    "record_job_finished",
    "record_job_started",
    "record_segment_event",
    "record_upload_result",
]
