"""Assets store — reusable Character / Product / Storyboard references.

File-based SQLite (data/assets.db) so users can save a ref once and reuse it
across multiple Director plans. Pattern mirrors `core/jobs_store.py`:
  - One small SQLite table, WAL mode, threading-safe via module lock.
  - `payload` column stores a JSON blob so the schema stays stable while the
    front-end can attach arbitrary metadata (face_signature, outfit, tags, …).

Asset types:
  - `character`  — name + image_url + face_signature + outfit
  - `product`    — name + image_url + packaging_description + hero_features[]
  - `storyboard` — name + image_url + prompt (reusable composition reference)

The image is stored either as an external URL (e.g. after /upload to AtlasCloud
or R2) OR as a `data:image/...;base64,...` URL for offline drafts. Front-end
typically converts via `/api/v1/upload` first to keep DB row small.
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


_DB_PATH = Path(__file__).parent.parent / "data" / "assets.db"
_LOCK = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    id            TEXT PRIMARY KEY,
    type          TEXT NOT NULL CHECK (type IN ('character', 'product', 'storyboard')),
    name          TEXT NOT NULL,
    image_url     TEXT NOT NULL,
    payload       TEXT NOT NULL DEFAULT '{}',
    tags          TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    last_used_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_assets_type      ON assets(type);
CREATE INDEX IF NOT EXISTS idx_assets_updated   ON assets(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_assets_last_used ON assets(last_used_at DESC);
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


# ============================================================
# CRUD
# ============================================================
def create_asset(
    *,
    type: str,
    name: str,
    image_url: str,
    payload: Optional[dict] = None,
    tags: str = "",
) -> dict:
    if type not in ("character", "product", "storyboard"):
        raise ValueError(f"invalid asset type: {type}")
    now = datetime.now(timezone.utc).isoformat()
    asset_id = f"asset_{uuid.uuid4().hex[:12]}"
    payload_str = json.dumps(payload or {}, ensure_ascii=False)
    with _LOCK:
        with _conn() as c:
            c.execute(
                """
                INSERT INTO assets (id, type, name, image_url, payload, tags, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (asset_id, type, name, image_url, payload_str, tags, now, now),
            )
    logger.info(f"[assets_store] created {asset_id} type={type} name='{name}'")
    return _get_by_id(asset_id)


def list_assets(
    type_filter: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    q = "SELECT * FROM assets WHERE 1=1"
    params: list[Any] = []
    if type_filter:
        q += " AND type = ?"
        params.append(type_filter)
    if search:
        q += " AND (name LIKE ? OR tags LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    q += " ORDER BY COALESCE(last_used_at, updated_at) DESC LIMIT ?"
    params.append(limit)
    with _LOCK:
        with _conn() as c:
            rows = c.execute(q, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_asset(asset_id: str) -> Optional[dict]:
    return _get_by_id(asset_id)


def update_asset(
    asset_id: str,
    *,
    name: Optional[str] = None,
    image_url: Optional[str] = None,
    payload: Optional[dict] = None,
    tags: Optional[str] = None,
) -> Optional[dict]:
    existing = _get_by_id(asset_id)
    if not existing:
        return None
    now = datetime.now(timezone.utc).isoformat()
    new_name = name if name is not None else existing["name"]
    new_url = image_url if image_url is not None else existing["image_url"]
    new_payload = json.dumps(
        payload if payload is not None else existing["payload"], ensure_ascii=False,
    )
    new_tags = tags if tags is not None else existing["tags"]
    with _LOCK:
        with _conn() as c:
            c.execute(
                """
                UPDATE assets
                   SET name = ?, image_url = ?, payload = ?, tags = ?, updated_at = ?
                 WHERE id = ?
                """,
                (new_name, new_url, new_payload, new_tags, now, asset_id),
            )
    return _get_by_id(asset_id)


def touch_used(asset_id: str) -> None:
    """Bump `last_used_at` so the library surfaces recently used items first."""
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        with _conn() as c:
            c.execute("UPDATE assets SET last_used_at = ? WHERE id = ?", (now, asset_id))


def delete_asset(asset_id: str) -> bool:
    with _LOCK:
        with _conn() as c:
            cur = c.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
            return cur.rowcount > 0


# ============================================================
# Internals
# ============================================================
def _get_by_id(asset_id: str) -> Optional[dict]:
    with _LOCK:
        with _conn() as c:
            row = c.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
    return _row_to_dict(row) if row else None


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "type": row["type"],
        "name": row["name"],
        "image_url": row["image_url"],
        "payload": json.loads(row["payload"] or "{}"),
        "tags": row["tags"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_used_at": row["last_used_at"],
    }
