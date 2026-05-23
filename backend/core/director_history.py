"""Director V3 history store — SQLite snapshot of completed render jobs.

Mỗi khi `video_worker.render_plan()` hoặc `render_single_shot()` finishes
(done / failed), `record_job()` lưu snapshot vào `data/director_history.db`
để Project History UI list lại sau khi server restart.

Schema:
    director_jobs(
        job_id      PRIMARY KEY,
        plan_id,
        mode,                     # approved | plan_and_render | refine
        status,                   # done | failed | cancelled
        output_url,
        title,                    # bible.title (for list display)
        duration_s,
        cost_estimate_usd,
        plan_blob,                # full DirectorPlan JSON (for fork)
        chain_blob,               # render chain meta (last_frames per shot)
        created_at,
        finished_at,
    )

Pattern same as core/jobs_store.py and core/assets_store.py — WAL mode,
threading-safe via module lock.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger


_DB_PATH = Path(__file__).parent.parent / "data" / "director_history.db"
_LOCK = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS director_jobs (
    job_id            TEXT PRIMARY KEY,
    plan_id           TEXT,
    mode              TEXT,
    status            TEXT NOT NULL,
    output_url        TEXT,
    title             TEXT,
    duration_s        INTEGER,
    cost_estimate_usd REAL,
    plan_blob         TEXT,
    chain_blob        TEXT,
    created_at        TEXT NOT NULL,
    finished_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_director_jobs_finished ON director_jobs(finished_at DESC);
CREATE INDEX IF NOT EXISTS idx_director_jobs_status   ON director_jobs(status);
"""


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


def record_job(
    *,
    job_id: str,
    plan_id: Optional[str],
    mode: str,
    status: str,
    output_url: Optional[str],
    title: Optional[str],
    duration_s: Optional[int],
    cost_estimate_usd: Optional[float],
    plan: Optional[dict] = None,
    chain: Optional[list] = None,
    created_at: Optional[str] = None,
) -> None:
    """Upsert a job snapshot. Idempotent — safe to call repeatedly."""
    now = datetime.now(timezone.utc).isoformat()
    plan_blob = json.dumps(plan, ensure_ascii=False, default=str) if plan else None
    chain_blob = json.dumps(chain, ensure_ascii=False, default=str) if chain else None
    with _LOCK:
        with _conn() as c:
            c.execute(
                """
                INSERT INTO director_jobs (
                    job_id, plan_id, mode, status, output_url, title,
                    duration_s, cost_estimate_usd, plan_blob, chain_blob,
                    created_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    plan_id = excluded.plan_id,
                    mode = excluded.mode,
                    status = excluded.status,
                    output_url = excluded.output_url,
                    title = excluded.title,
                    duration_s = excluded.duration_s,
                    cost_estimate_usd = excluded.cost_estimate_usd,
                    plan_blob = COALESCE(excluded.plan_blob, director_jobs.plan_blob),
                    chain_blob = COALESCE(excluded.chain_blob, director_jobs.chain_blob),
                    finished_at = excluded.finished_at
                """,
                (
                    job_id, plan_id, mode, status, output_url, title,
                    duration_s, cost_estimate_usd, plan_blob, chain_blob,
                    created_at or now, now,
                ),
            )
    logger.info(f"[director_history] recorded {job_id} status={status}")


def list_jobs(
    limit: int = 50,
    status_filter: Optional[str] = None,
) -> list[dict]:
    q = "SELECT * FROM director_jobs WHERE 1=1"
    params: list[Any] = []
    if status_filter:
        q += " AND status = ?"
        params.append(status_filter)
    q += " ORDER BY finished_at DESC, created_at DESC LIMIT ?"
    params.append(limit)
    with _LOCK:
        with _conn() as c:
            rows = c.execute(q, params).fetchall()
    return [_row_to_dict(r, include_plan=False) for r in rows]


def get_job(job_id: str, include_plan: bool = True) -> Optional[dict]:
    with _LOCK:
        with _conn() as c:
            row = c.execute(
                "SELECT * FROM director_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
    return _row_to_dict(row, include_plan=include_plan) if row else None


def delete_job(job_id: str) -> bool:
    with _LOCK:
        with _conn() as c:
            cur = c.execute("DELETE FROM director_jobs WHERE job_id = ?", (job_id,))
            return cur.rowcount > 0


def _row_to_dict(row: sqlite3.Row, include_plan: bool) -> dict:
    out = {
        "job_id": row["job_id"],
        "plan_id": row["plan_id"],
        "mode": row["mode"],
        "status": row["status"],
        "output_url": row["output_url"],
        "title": row["title"],
        "duration_s": row["duration_s"],
        "cost_estimate_usd": row["cost_estimate_usd"],
        "created_at": row["created_at"],
        "finished_at": row["finished_at"],
    }
    if include_plan:
        out["plan"] = json.loads(row["plan_blob"]) if row["plan_blob"] else None
        out["chain"] = json.loads(row["chain_blob"]) if row["chain_blob"] else None
    return out
