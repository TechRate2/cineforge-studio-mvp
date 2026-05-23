"""Idempotency-Key middleware — chống double-submit duplicate jobs.

Pattern (Stripe-style):
    Client gửi header `Idempotency-Key: <uuid>` với POST /api/v1/jobs/ugc.
    Server cache (key → response) trong 24h.
    Request thứ 2 cùng key → return cached response, KHÔNG tạo job mới.

Storage: SQLite file-based (cùng pattern jobs_store), persist qua restart.
"""

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger


_DB_PATH = Path(__file__).parent.parent / "data" / "idempotency.db"
_LOCK = threading.Lock()
_TTL_HOURS = 24  # cache 24h, sau đó cho phép request mới

_SCHEMA = """
CREATE TABLE IF NOT EXISTS idempotency (
    key TEXT PRIMARY KEY,
    body_hash TEXT NOT NULL,
    response_json TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_idem_expires ON idempotency(expires_at);
"""


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=10.0)
    c.execute("PRAGMA journal_mode=WAL")
    c.row_factory = sqlite3.Row
    return c


def _ensure_schema():
    with _LOCK:
        c = _conn()
        try:
            c.executescript(_SCHEMA)
            # Cleanup expired
            c.execute("DELETE FROM idempotency WHERE expires_at < ?",
                      (datetime.now(timezone.utc).isoformat(),))
            c.commit()
        finally:
            c.close()


_ensure_schema()


def hash_body(body: Any) -> str:
    """SHA256 hash của request body (dict/json) — match check để chống abuse."""
    if isinstance(body, dict):
        body_str = json.dumps(body, sort_keys=True, ensure_ascii=False)
    else:
        body_str = str(body)
    return hashlib.sha256(body_str.encode("utf-8")).hexdigest()


def lookup(key: str, body_hash: str) -> Optional[dict]:
    """Lookup cached response.

    Returns:
        None — chưa có cache (request đầu tiên)
        dict {response_json, status_code, body_match: bool} — cache hit
    """
    if not key:
        return None

    _ensure_schema()
    c = _conn()
    try:
        row = c.execute(
            "SELECT body_hash, response_json, status_code, expires_at "
            "FROM idempotency WHERE key = ?",
            (key,),
        ).fetchone()
        if not row:
            return None

        # Check expired
        if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
            return None

        return {
            "response_json": json.loads(row["response_json"]),
            "status_code": row["status_code"],
            "body_match": row["body_hash"] == body_hash,
        }
    finally:
        c.close()


def store(key: str, body_hash: str, response: Any, status_code: int = 201) -> None:
    """Store response cho key. TTL 24h."""
    if not key:
        return

    _ensure_schema()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=_TTL_HOURS)

    with _LOCK:
        c = _conn()
        try:
            c.execute(
                """
                INSERT OR REPLACE INTO idempotency
                    (key, body_hash, response_json, status_code, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    body_hash,
                    json.dumps(response, ensure_ascii=False, default=str),
                    status_code,
                    now.isoformat(),
                    expires.isoformat(),
                ),
            )
            c.commit()
            logger.info(f"[Idempotency] stored key={key[:16]}... expires_in=24h")
        finally:
            c.close()
