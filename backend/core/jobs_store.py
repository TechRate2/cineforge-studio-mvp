"""Jobs store — file-based persistence để fix BUG-H1.

In-memory dict mất hết khi restart backend. File-based SQLite (1 table)
giữ JOBS qua restart. Tương lai có thể migrate sang Postgres dễ dàng.

Schema giữ tối thiểu — JSON blob để flexible với thay đổi schema agent.
"""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from loguru import logger


_DB_PATH = Path(__file__).parent.parent / "data" / "jobs_store.db"
_LOCK = threading.Lock()  # cross-thread safety cho BackgroundTasks

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',
    progress INTEGER NOT NULL DEFAULT 0,
    current_step TEXT,
    output_url TEXT,
    thumbnail_url TEXT,
    duration_s INTEGER,
    cost_actual_usd REAL,
    error_message TEXT,
    atlas_prediction_id TEXT,
    full_blob TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_updated ON jobs(updated_at DESC);
"""


def _conn() -> sqlite3.Connection:
    """Get DB connection. WAL mode để concurrent read khi write."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=10.0)
    c.execute("PRAGMA journal_mode=WAL")
    c.row_factory = sqlite3.Row
    return c


def _ensure_schema():
    """Init schema (idempotent)."""
    with _LOCK:
        c = _conn()
        try:
            c.executescript(_SCHEMA)
            c.commit()
        finally:
            c.close()


_ensure_schema()


def create(job_id: UUID, initial: dict[str, Any]) -> None:
    """Create new job row. initial must have 'request' (CreateJobRequest dump)."""
    job_id_str = str(job_id)
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        c = _conn()
        try:
            c.execute(
                """
                INSERT OR REPLACE INTO jobs
                    (job_id, status, progress, full_blob, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id_str,
                    initial.get("status", "pending"),
                    initial.get("progress", 0),
                    json.dumps(initial, ensure_ascii=False, default=str),
                    now,
                    now,
                ),
            )
            c.commit()
        finally:
            c.close()


def get(job_id: Any) -> Optional[dict]:
    """Return job dict or None nếu không tồn tại.

    Accept UUID or str job_id.
    """
    job_id_str = str(job_id)
    c = _conn()
    try:
        row = c.execute(
            "SELECT * FROM jobs WHERE job_id = ?", (job_id_str,)
        ).fetchone()
        if not row:
            return None
        # Merge column fields with JSON blob (column fields win — they're authoritative)
        blob = json.loads(row["full_blob"]) if row["full_blob"] else {}
        merged = {**blob, **{k: row[k] for k in row.keys() if k != "full_blob"}}
        # Parse timestamps
        for k in ("created_at", "updated_at"):
            try:
                merged[k] = datetime.fromisoformat(merged[k])
            except (ValueError, TypeError):
                pass
        return merged
    finally:
        c.close()


def update(job_id: Any, **fields: Any) -> None:
    """Patch job fields. Auto bump updated_at."""
    job_id_str = str(job_id)
    now = datetime.now(timezone.utc).isoformat()
    # Whitelist column fields (others go vào blob)
    col_fields = {
        "status", "progress", "current_step", "output_url", "thumbnail_url",
        "duration_s", "cost_actual_usd", "error_message", "atlas_prediction_id",
    }

    with _LOCK:
        c = _conn()
        try:
            # Get current blob for merge
            row = c.execute("SELECT full_blob FROM jobs WHERE job_id = ?", (job_id_str,)).fetchone()
            if not row:
                logger.warning(f"[jobs_store] update missing job {job_id_str}")
                return

            blob = json.loads(row["full_blob"]) if row["full_blob"] else {}
            for k, v in fields.items():
                blob[k] = v  # always update blob

            # Build UPDATE statement for column fields
            col_updates = [(k, v) for k, v in fields.items() if k in col_fields]
            set_parts = ", ".join(f"{k} = ?" for k, _ in col_updates)
            set_parts += (", " if set_parts else "") + "full_blob = ?, updated_at = ?"
            params = [v for _, v in col_updates] + [json.dumps(blob, ensure_ascii=False, default=str), now, job_id_str]

            c.execute(f"UPDATE jobs SET {set_parts} WHERE job_id = ?", params)
            c.commit()
        finally:
            c.close()


def delete(job_id: Any) -> bool:
    """Delete job row. Return True nếu deleted."""
    job_id_str = str(job_id)
    with _LOCK:
        c = _conn()
        try:
            cursor = c.execute("DELETE FROM jobs WHERE job_id = ?", (job_id_str,))
            c.commit()
            return cursor.rowcount > 0
        finally:
            c.close()


def list_recent(limit: int = 50) -> list[dict]:
    """List recent jobs (debug/admin)."""
    c = _conn()
    try:
        rows = c.execute(
            "SELECT job_id, status, progress, current_step, updated_at FROM jobs "
            "ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()


class _DictLikeStore:
    """Compat shim cho code cũ dùng JOBS[id] = {...} pattern.

    Behaves như dict nhưng persist xuống SQLite. Old code không phải sửa.
    """

    def __getitem__(self, key):
        result = get(key)
        if result is None:
            raise KeyError(key)
        return result

    def __setitem__(self, key, value):
        if get(key) is None:
            create(key, value)
        else:
            update(key, **value)

    def __delitem__(self, key):
        if not delete(key):
            raise KeyError(key)

    def __contains__(self, key):
        return get(key) is not None

    def get(self, key, default=None):
        result = get(key)
        return result if result is not None else default

    def update(self, key, **fields):
        """Bypass dict.update — explicit method for partial update."""
        update(key, **fields)


# Singleton — drop-in replacement cho old `JOBS: dict[UUID, dict] = {}`
JOBS = _DictLikeStore()
