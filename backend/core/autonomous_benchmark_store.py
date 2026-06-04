"""SQLite store for autonomous benchmark render results.

The benchmark contract defines what should be tested. This store records the
actual evidence from benchmark runs: model route, output URL, cost, latency,
QA scores, and reviewer decision. It is intentionally small so real AtlasCloud
benchmark jobs can start attaching evidence without changing the render worker.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger


_DB_PATH = Path(__file__).parent.parent / "data" / "autonomous_benchmarks.db"
_LOCK = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS autonomous_benchmark_results (
    id                TEXT PRIMARY KEY,
    case_id           TEXT NOT NULL,
    niche             TEXT NOT NULL,
    target_market     TEXT NOT NULL,
    runtime_class     TEXT NOT NULL,
    model_key         TEXT NOT NULL,
    status            TEXT NOT NULL,
    output_url        TEXT,
    cost_usd          REAL,
    latency_s         REAL,
    qa_score          REAL,
    reviewer_decision TEXT,
    evidence          TEXT NOT NULL DEFAULT '{}',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_benchmark_case ON autonomous_benchmark_results(case_id);
CREATE INDEX IF NOT EXISTS idx_benchmark_niche ON autonomous_benchmark_results(niche);
CREATE INDEX IF NOT EXISTS idx_benchmark_model ON autonomous_benchmark_results(model_key);
CREATE INDEX IF NOT EXISTS idx_benchmark_status ON autonomous_benchmark_results(status);
CREATE INDEX IF NOT EXISTS idx_benchmark_updated ON autonomous_benchmark_results(updated_at DESC);
"""

_ALLOWED_STATUSES = {"planned", "running", "passed", "failed", "needs_review"}
_ALLOWED_DECISIONS = {"approved", "rejected", "needs_review", "unknown", ""}


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=10.0)
    c.execute("PRAGMA journal_mode=WAL")
    c.row_factory = sqlite3.Row
    return c


def _init() -> None:
    with _LOCK:
        with _conn() as c:
            c.executescript(_SCHEMA)


_init()


def create_result(
    *,
    case_id: str,
    niche: str,
    target_market: str,
    runtime_class: str,
    model_key: str,
    status: str = "planned",
    output_url: Optional[str] = None,
    cost_usd: Optional[float] = None,
    latency_s: Optional[float] = None,
    qa_score: Optional[float] = None,
    reviewer_decision: Optional[str] = None,
    evidence: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create one benchmark result/evidence row."""
    normalized_status = _normalize_status(status)
    normalized_decision = _normalize_decision(reviewer_decision)
    now = datetime.now(timezone.utc).isoformat()
    result_id = f"benchrun_{uuid.uuid4().hex[:12]}"
    with _LOCK:
        with _conn() as c:
            c.execute(
                """
                INSERT INTO autonomous_benchmark_results (
                    id, case_id, niche, target_market, runtime_class, model_key,
                    status, output_url, cost_usd, latency_s, qa_score,
                    reviewer_decision, evidence, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result_id,
                    case_id,
                    niche,
                    target_market,
                    runtime_class,
                    model_key,
                    normalized_status,
                    output_url,
                    cost_usd,
                    latency_s,
                    qa_score,
                    normalized_decision,
                    json.dumps(evidence or {}, ensure_ascii=False, default=str),
                    now,
                    now,
                ),
            )
    logger.info(
        f"[autonomous_benchmark_store] created {result_id} case={case_id} model={model_key} status={normalized_status}"
    )
    return get_result(result_id) or {"id": result_id}


def update_result(
    result_id: str,
    *,
    status: Optional[str] = None,
    output_url: Optional[str] = None,
    cost_usd: Optional[float] = None,
    latency_s: Optional[float] = None,
    qa_score: Optional[float] = None,
    reviewer_decision: Optional[str] = None,
    evidence: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    existing = get_result(result_id)
    if not existing:
        return None
    now = datetime.now(timezone.utc).isoformat()
    next_evidence = existing["evidence"]
    if evidence:
        next_evidence = {**next_evidence, **evidence}
    with _LOCK:
        with _conn() as c:
            c.execute(
                """
                UPDATE autonomous_benchmark_results
                   SET status = ?,
                       output_url = ?,
                       cost_usd = ?,
                       latency_s = ?,
                       qa_score = ?,
                       reviewer_decision = ?,
                       evidence = ?,
                       updated_at = ?
                 WHERE id = ?
                """,
                (
                    _normalize_status(status or existing["status"]),
                    output_url if output_url is not None else existing.get("output_url"),
                    cost_usd if cost_usd is not None else existing.get("cost_usd"),
                    latency_s if latency_s is not None else existing.get("latency_s"),
                    qa_score if qa_score is not None else existing.get("qa_score"),
                    _normalize_decision(
                        reviewer_decision if reviewer_decision is not None
                        else existing.get("reviewer_decision")
                    ),
                    json.dumps(next_evidence, ensure_ascii=False, default=str),
                    now,
                    result_id,
                ),
            )
    return get_result(result_id)


def get_result(result_id: str) -> Optional[dict[str, Any]]:
    with _LOCK:
        with _conn() as c:
            row = c.execute(
                "SELECT * FROM autonomous_benchmark_results WHERE id = ?",
                (result_id,),
            ).fetchone()
    return _row_to_dict(row) if row else None


def list_results(
    *,
    case_id: Optional[str] = None,
    niche: Optional[str] = None,
    model_key: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    q = "SELECT * FROM autonomous_benchmark_results WHERE 1=1"
    params: list[Any] = []
    if case_id:
        q += " AND case_id = ?"
        params.append(case_id)
    if niche:
        q += " AND niche = ?"
        params.append(niche)
    if model_key:
        q += " AND model_key = ?"
        params.append(model_key)
    if status:
        q += " AND status = ?"
        params.append(status)
    q += " ORDER BY updated_at DESC LIMIT ?"
    params.append(max(1, min(int(limit or 100), 500)))
    with _LOCK:
        with _conn() as c:
            rows = c.execute(q, params).fetchall()
    return [_row_to_dict(row) for row in rows]


def delete_result(result_id: str) -> bool:
    """Delete one benchmark result row."""
    with _LOCK:
        with _conn() as c:
            cur = c.execute(
                "DELETE FROM autonomous_benchmark_results WHERE id = ?",
                (result_id,),
            )
            return cur.rowcount > 0


def stats() -> dict[str, Any]:
    """Return compact readiness stats for API/report surfaces."""
    with _LOCK:
        with _conn() as c:
            total = c.execute("SELECT COUNT(*) AS n FROM autonomous_benchmark_results").fetchone()["n"]
            by_status = c.execute(
                "SELECT status, COUNT(*) AS n FROM autonomous_benchmark_results GROUP BY status"
            ).fetchall()
            by_niche = c.execute(
                """
                SELECT niche, COUNT(*) AS n,
                       SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) AS passed
                  FROM autonomous_benchmark_results
                 GROUP BY niche
                 ORDER BY n DESC, niche ASC
                """
            ).fetchall()
            by_model = c.execute(
                """
                SELECT model_key, COUNT(*) AS n,
                       SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) AS passed
                  FROM autonomous_benchmark_results
                 GROUP BY model_key
                 ORDER BY n DESC, model_key ASC
                """
            ).fetchall()
    return {
        "schema_version": "cinejelly.benchmark_result_stats.v1",
        "total_results": int(total or 0),
        "status_counts": {row["status"]: int(row["n"]) for row in by_status},
        "niche_counts": [
            {"niche": row["niche"], "total": int(row["n"]), "passed": int(row["passed"] or 0)}
            for row in by_niche
        ],
        "model_counts": [
            {"model_key": row["model_key"], "total": int(row["n"]), "passed": int(row["passed"] or 0)}
            for row in by_model
        ],
    }


def _normalize_status(status: str) -> str:
    s = (status or "planned").strip().lower()
    if s not in _ALLOWED_STATUSES:
        raise ValueError(f"invalid benchmark status: {status}")
    return s


def _normalize_decision(decision: Optional[str]) -> str:
    d = (decision or "unknown").strip().lower()
    if d not in _ALLOWED_DECISIONS:
        raise ValueError(f"invalid reviewer decision: {decision}")
    return d or "unknown"


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "case_id": row["case_id"],
        "niche": row["niche"],
        "target_market": row["target_market"],
        "runtime_class": row["runtime_class"],
        "model_key": row["model_key"],
        "status": row["status"],
        "output_url": row["output_url"],
        "cost_usd": row["cost_usd"],
        "latency_s": row["latency_s"],
        "qa_score": row["qa_score"],
        "reviewer_decision": row["reviewer_decision"],
        "evidence": json.loads(row["evidence"] or "{}"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


__all__ = [
    "create_result",
    "update_result",
    "get_result",
    "list_results",
    "delete_result",
    "stats",
]
