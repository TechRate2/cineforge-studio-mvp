"""LLM response cache — SQLite WAL (file-based, persistent qua restart).

Mục đích: skip LLM call trùng lặp → tiết kiệm 30-60% cost + 100% latency.

Key = sha256(model + messages JSON normalized + max_tokens + temperature)
Value = response content (text) + token usage + cached_at timestamp
TTL = 7 ngày mặc định (cho cùng prompt + ảnh)

Cache HIT scenarios:
    1. User submit cùng product + cùng ref ảnh 2 lần → 100% hit
    2. Anh test dev cùng input nhiều lần → 100% hit (zero cost)
    3. Cùng skill_pack + same niche với khác product → partial hit ở
       VisualPlanner system prompt (system prompt = stable)

Cache MISS scenarios:
    - temperature > 0.5 (creative output, không nên cache)
    - User upload ảnh khác → image data URL khác → key khác

Bypass cache:
    - Set env LLM_CACHE_DISABLED=1
    - Hoặc temperature >= 0.7 (creative tasks)
"""

import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from loguru import logger


_CACHE_DIR = Path(__file__).parent.parent / "data"
_CACHE_DIR.mkdir(exist_ok=True)
_DB_PATH = _CACHE_DIR / "llm_cache.db"
_TTL_DAYS = 7

# Bypass khi temperature cao (creative) — Director temp=0.8, Hook Writer temp=0.7+...
# CHỈ cache khi temperature ≤ 0.5 (analytical tasks consistent)
_CACHE_TEMPERATURE_MAX = 0.5

_lock = threading.RLock()
_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> Optional[sqlite3.Connection]:
    """Lazy init connection — WAL mode cho concurrent safe."""
    global _conn
    if os.getenv("LLM_CACHE_DISABLED") == "1":
        return None
    with _lock:
        if _conn is None:
            try:
                _conn = sqlite3.connect(
                    str(_DB_PATH),
                    check_same_thread=False,
                    timeout=5.0,
                )
                _conn.execute("PRAGMA journal_mode=WAL;")
                _conn.execute("PRAGMA synchronous=NORMAL;")
                _conn.execute("""
                    CREATE TABLE IF NOT EXISTS llm_cache (
                        cache_key TEXT PRIMARY KEY,
                        model TEXT NOT NULL,
                        response_text TEXT NOT NULL,
                        prompt_tokens INTEGER DEFAULT 0,
                        completion_tokens INTEGER DEFAULT 0,
                        cached_at TEXT NOT NULL,
                        hit_count INTEGER DEFAULT 0
                    )
                """)
                _conn.execute("CREATE INDEX IF NOT EXISTS idx_cached_at ON llm_cache(cached_at)")
                _conn.commit()
                logger.info(f"[LLMCache] initialized at {_DB_PATH}")
            except Exception as e:
                logger.warning(f"[LLMCache] init fail: {e} — cache disabled")
                _conn = None
        return _conn


def _make_key(model: str, messages: list, max_tokens: int, temperature: float) -> str:
    """Build deterministic cache key — sort_keys để serialize stable."""
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": round(temperature, 2),
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def lookup(model: str, messages: list, max_tokens: int, temperature: float) -> Optional[dict]:
    """Trả cached response nếu có + chưa expired. Hit → bump hit_count.

    Returns:
        dict {"text": str, "prompt_tokens": int, "completion_tokens": int, "cached": True}
        hoặc None khi miss.
    """
    if temperature > _CACHE_TEMPERATURE_MAX:
        return None
    conn = _get_conn()
    if not conn:
        return None
    key = _make_key(model, messages, max_tokens, temperature)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=_TTL_DAYS)).isoformat()
    try:
        with _lock:
            row = conn.execute(
                "SELECT response_text, prompt_tokens, completion_tokens, cached_at FROM llm_cache "
                "WHERE cache_key = ? AND cached_at > ?",
                (key, cutoff),
            ).fetchone()
            if not row:
                return None
            # Hit — bump count
            conn.execute(
                "UPDATE llm_cache SET hit_count = hit_count + 1 WHERE cache_key = ?",
                (key,),
            )
            conn.commit()
        logger.info(
            f"[LLMCache] HIT {model} (cached {row[3][:19]}) — save ~{row[1] + row[2]} tokens"
        )
        return {
            "text": row[0],
            "prompt_tokens": row[1],
            "completion_tokens": row[2],
            "cached": True,
        }
    except Exception as e:
        logger.warning(f"[LLMCache] lookup fail: {e}")
        return None


def store(
    model: str,
    messages: list,
    max_tokens: int,
    temperature: float,
    response_text: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """Store response cho future hit. Skip nếu temperature > cache max."""
    if temperature > _CACHE_TEMPERATURE_MAX:
        return
    conn = _get_conn()
    if not conn:
        return
    key = _make_key(model, messages, max_tokens, temperature)
    try:
        with _lock:
            conn.execute(
                "INSERT OR REPLACE INTO llm_cache "
                "(cache_key, model, response_text, prompt_tokens, completion_tokens, cached_at, hit_count) "
                "VALUES (?, ?, ?, ?, ?, ?, 0)",
                (key, model, response_text, prompt_tokens, completion_tokens, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"[LLMCache] store fail: {e}")


def cleanup_expired() -> int:
    """Xoá entries > TTL_DAYS. Trả số rows deleted. Có thể chạy daily cron."""
    conn = _get_conn()
    if not conn:
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=_TTL_DAYS)).isoformat()
    try:
        with _lock:
            cur = conn.execute("DELETE FROM llm_cache WHERE cached_at < ?", (cutoff,))
            conn.commit()
            return cur.rowcount
    except Exception as e:
        logger.warning(f"[LLMCache] cleanup fail: {e}")
        return 0


def stats() -> dict:
    """Trả thống kê — total rows, hit_total, oldest, newest."""
    conn = _get_conn()
    if not conn:
        return {"enabled": False}
    try:
        with _lock:
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(hit_count), 0), MIN(cached_at), MAX(cached_at) "
                "FROM llm_cache"
            ).fetchone()
            return {
                "enabled": True,
                "total_entries": row[0],
                "total_hits": row[1],
                "oldest": row[2],
                "newest": row[3],
                "db_path": str(_DB_PATH),
            }
    except Exception as e:
        return {"enabled": True, "error": str(e)}
