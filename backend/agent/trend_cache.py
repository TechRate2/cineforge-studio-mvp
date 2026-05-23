"""Trend Cache — SQLite-backed VN TikTok trend store.

Lightweight data layer extracted from the V2 trend_watcher persona.
- `fetch_relevant_trends(niche, age, ...)` is consumed by Director Agent V3 as
  optional context (Director system prompt accepts `trends_context`).
- `insert_scanned_trend()` + `log_scan()` are used by `workers/trend_scanner.py`
  cron job.

Bootstrap seeds + WAL mode preserved from V2 (proven stable).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from loguru import logger


DB_PATH = Path(__file__).parent.parent / "data" / "trend_cache.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trend_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    format_type TEXT,
    target_niches TEXT,
    audience_age_min INTEGER,
    audience_age_max INTEGER,
    trending_score INTEGER DEFAULT 5,
    source TEXT,
    discovered_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP,
    raw_example TEXT
);
CREATE INDEX IF NOT EXISTS idx_trends_score ON trends(trending_score DESC);
CREATE INDEX IF NOT EXISTS idx_trends_expires ON trends(expires_at);

CREATE TABLE IF NOT EXISTS scan_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    scanned_at TIMESTAMP NOT NULL,
    items_found INTEGER DEFAULT 0,
    status TEXT
);
"""

SEED_TRENDS = [
    {
        "trend_id": "seed_pov_thanh_can",
        "title": "POV thành viên thân cận",
        "description": "POV format: 'POV: [người thân] tự nhiên hỏi/làm gì đó về vẻ ngoài của bạn'",
        "format_type": "POV",
        "target_niches": "beauty,fashion,lifestyle",
        "audience_age_min": 18, "audience_age_max": 35,
        "trending_score": 9, "source": "seed",
        "raw_example": "POV: bạn trai tự nhiên hỏi 'em đánh son gì mà bóng thế'",
    },
    {
        "trend_id": "seed_before_after_n_days",
        "title": "Before/After N ngày",
        "description": "Visual proof: Ngày 1 vs ngày N (N = 7/14/21/30/60)",
        "format_type": "before_after",
        "target_niches": "beauty,supplement,fitness",
        "audience_age_min": 22, "audience_age_max": 45,
        "trending_score": 10, "source": "seed",
        "raw_example": "Ngày 1 vs ngày 30, mình không tin vào mắt mình",
    },
    {
        "trend_id": "seed_tested_n_kept_one",
        "title": "Tested N - giữ 1",
        "description": "Authority + curiosity: 'Mình đã thử N sản phẩm, đây là cái duy nhất giữ'",
        "format_type": "curiosity_gap",
        "target_niches": "beauty,tech,fashion,food",
        "audience_age_min": 22, "audience_age_max": 40,
        "trending_score": 9, "source": "seed",
        "raw_example": "Mình đã thử 12 thỏi son 800k+, đây là thỏi duy nhất giữ",
    },
    {
        "trend_id": "seed_rant_industry",
        "title": "Rant về ngành",
        "description": "Controversial: 'Mình nói thật, ngành X đang scam bằng Y'",
        "format_type": "controversial",
        "target_niches": "beauty,supplement,tech,fashion",
        "audience_age_min": 20, "audience_age_max": 40,
        "trending_score": 9, "source": "seed",
        "raw_example": "Mình nói thật, ngành mỹ phẩm VN đang scam bằng 'whitening'",
    },
    {
        "trend_id": "seed_stop_action",
        "title": "Stop X — đây là Y",
        "description": "Hot take: 'Stop [hành động phổ biến], đây là [alternative]'",
        "format_type": "controversial",
        "target_niches": "beauty,tech,fashion,lifestyle",
        "audience_age_min": 18, "audience_age_max": 35,
        "trending_score": 8, "source": "seed",
        "raw_example": "Stop mua serum 1 triệu, đây là loại 89k đang viral",
    },
    {
        "trend_id": "seed_chi_em_test",
        "title": "Mấy chị em ơi",
        "description": "Community appeal: 'Mấy chị em ơi mình [test/try] cái này và...'",
        "format_type": "relatable",
        "target_niches": "beauty,mom_baby,fashion,food",
        "audience_age_min": 22, "audience_age_max": 40,
        "trending_score": 7, "source": "seed",
        "raw_example": "Mấy chị em ơi mình thử mặt nạ giấy này và da căng bóng luôn",
    },
]


def _ensure_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA_SQL)
        if conn.execute("SELECT COUNT(*) FROM trends").fetchone()[0] == 0:
            logger.info("[trend_cache] seeding default trends")
            for t in SEED_TRENDS:
                _insert(conn, t)
            conn.commit()
    finally:
        conn.close()


def _insert(conn: sqlite3.Connection, t: dict) -> None:
    expires = t.get("expires_at") or (datetime.now() + timedelta(days=30)).isoformat()
    conn.execute(
        """
        INSERT OR REPLACE INTO trends
            (trend_id, title, description, format_type, target_niches,
             audience_age_min, audience_age_max, trending_score, source,
             discovered_at, expires_at, raw_example)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            t["trend_id"], t["title"], t.get("description", ""),
            t.get("format_type", "general"), t.get("target_niches", ""),
            t.get("audience_age_min", 18), t.get("audience_age_max", 50),
            t.get("trending_score", 5), t.get("source", "manual"),
            datetime.now().isoformat(), expires, t.get("raw_example", ""),
        ),
    )


def fetch_relevant_trends(
    niche: Optional[str] = None,
    audience_age: Optional[tuple[int, int]] = None,
    limit: int = 5,
    min_score: int = 6,
) -> list[dict]:
    _ensure_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        q = (
            "SELECT * FROM trends "
            "WHERE trending_score >= ? "
            "AND (expires_at IS NULL OR expires_at > ?) "
        )
        p: list = [min_score, datetime.now().isoformat()]
        if niche:
            root = str(niche).split(".")[0].split("_")[0].lower()
            q += "AND LOWER(target_niches) LIKE ? "
            p.append(f"%{root}%")
        if audience_age:
            a_min, a_max = audience_age
            q += "AND audience_age_min <= ? AND audience_age_max >= ? "
            p.extend([a_max, a_min])
        q += "ORDER BY trending_score DESC LIMIT ?"
        p.append(limit)
        rows = conn.execute(q, p).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def insert_scanned_trend(trend: dict) -> None:
    _ensure_db()
    conn = sqlite3.connect(str(DB_PATH))
    try:
        _insert(conn, trend)
        conn.commit()
    finally:
        conn.close()


def log_scan(source: str, items_found: int, status: str = "ok") -> None:
    _ensure_db()
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute(
            "INSERT INTO scan_log (source, scanned_at, items_found, status) VALUES (?, ?, ?, ?)",
            (source, datetime.now().isoformat(), items_found, status),
        )
        conn.commit()
    finally:
        conn.close()
