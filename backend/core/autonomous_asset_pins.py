"""Approved autonomous asset pins.

Asset memory suggests reusable references automatically. Pins are the explicit
approval layer: a user or future admin UI can lock an asset as a character,
product, location, style, or voice anchor for a niche/market/series before
another autonomous run uses it.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from core import assets_store


_DB_PATH = Path(__file__).parent.parent / "data" / "autonomous_asset_pins.db"
_LOCK = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS autonomous_asset_pins (
    id             TEXT PRIMARY KEY,
    asset_id       TEXT NOT NULL,
    role           TEXT NOT NULL,
    target_market  TEXT NOT NULL DEFAULT 'auto',
    niche          TEXT NOT NULL DEFAULT 'any',
    series_key     TEXT NOT NULL DEFAULT '',
    priority       INTEGER NOT NULL DEFAULT 50,
    status         TEXT NOT NULL DEFAULT 'active',
    notes          TEXT NOT NULL DEFAULT '',
    metadata       TEXT NOT NULL DEFAULT '{}',
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_asset_pins_asset ON autonomous_asset_pins(asset_id);
CREATE INDEX IF NOT EXISTS idx_asset_pins_role ON autonomous_asset_pins(role);
CREATE INDEX IF NOT EXISTS idx_asset_pins_market ON autonomous_asset_pins(target_market);
CREATE INDEX IF NOT EXISTS idx_asset_pins_niche ON autonomous_asset_pins(niche);
CREATE INDEX IF NOT EXISTS idx_asset_pins_status ON autonomous_asset_pins(status);
CREATE INDEX IF NOT EXISTS idx_asset_pins_priority ON autonomous_asset_pins(priority DESC);
"""

_ALLOWED_STATUS = {"active", "paused", "archived"}


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


def create_pin(
    *,
    asset_id: str,
    role: str,
    target_market: str = "auto",
    niche: str = "any",
    series_key: str = "",
    priority: int = 50,
    status: str = "active",
    notes: str = "",
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Approve one reusable asset as an autonomous continuity anchor."""
    asset = assets_store.get_asset(asset_id)
    if not asset:
        raise ValueError(f"asset '{asset_id}' not found")
    normalized_status = _normalize_status(status)
    now = datetime.now(timezone.utc).isoformat()
    pin_id = f"pin_{uuid.uuid4().hex[:12]}"
    with _LOCK:
        with _conn() as c:
            c.execute(
                """
                INSERT INTO autonomous_asset_pins (
                    id, asset_id, role, target_market, niche, series_key,
                    priority, status, notes, metadata, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pin_id,
                    asset_id,
                    _clean(role, "reference_anchor"),
                    _clean(target_market, "auto"),
                    _clean(niche, "any"),
                    series_key.strip(),
                    max(0, min(int(priority or 50), 100)),
                    normalized_status,
                    notes[:1000],
                    json.dumps(metadata or {}, ensure_ascii=False, default=str),
                    now,
                    now,
                ),
            )
    return get_pin(pin_id) or {"id": pin_id}


def update_pin(
    pin_id: str,
    *,
    role: Optional[str] = None,
    target_market: Optional[str] = None,
    niche: Optional[str] = None,
    series_key: Optional[str] = None,
    priority: Optional[int] = None,
    status: Optional[str] = None,
    notes: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    existing = get_pin(pin_id)
    if not existing:
        return None
    now = datetime.now(timezone.utc).isoformat()
    next_metadata = existing.get("metadata") or {}
    if metadata is not None:
        next_metadata = {**next_metadata, **metadata}
    with _LOCK:
        with _conn() as c:
            c.execute(
                """
                UPDATE autonomous_asset_pins
                   SET role = ?,
                       target_market = ?,
                       niche = ?,
                       series_key = ?,
                       priority = ?,
                       status = ?,
                       notes = ?,
                       metadata = ?,
                       updated_at = ?
                 WHERE id = ?
                """,
                (
                    _clean(role if role is not None else existing["role"], "reference_anchor"),
                    _clean(target_market if target_market is not None else existing["target_market"], "auto"),
                    _clean(niche if niche is not None else existing["niche"], "any"),
                    (series_key if series_key is not None else existing["series_key"]).strip(),
                    max(0, min(int(priority if priority is not None else existing["priority"]), 100)),
                    _normalize_status(status if status is not None else existing["status"]),
                    (notes if notes is not None else existing["notes"])[:1000],
                    json.dumps(next_metadata, ensure_ascii=False, default=str),
                    now,
                    pin_id,
                ),
            )
    return get_pin(pin_id)


def get_pin(pin_id: str) -> Optional[dict[str, Any]]:
    with _LOCK:
        with _conn() as c:
            row = c.execute(
                "SELECT * FROM autonomous_asset_pins WHERE id = ?",
                (pin_id,),
            ).fetchone()
    return _row_to_dict(row) if row else None


def list_pins(
    *,
    status: Optional[str] = "active",
    target_market: Optional[str] = None,
    niche: Optional[str] = None,
    role: Optional[str] = None,
    series_key: Optional[str] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    q = "SELECT * FROM autonomous_asset_pins WHERE 1=1"
    params: list[Any] = []
    if status:
        q += " AND status = ?"
        params.append(_normalize_status(status))
    if role:
        q += " AND role = ?"
        params.append(role)
    if series_key:
        q += " AND series_key = ?"
        params.append(series_key)
    if target_market:
        q += " AND target_market IN ('auto', ?)"
        params.append(target_market)
    if niche:
        q += " AND niche IN ('any', ?)"
        params.append(niche)
    q += " ORDER BY priority DESC, updated_at DESC LIMIT ?"
    params.append(max(1, min(int(limit or 100), 500)))
    with _LOCK:
        with _conn() as c:
            rows = c.execute(q, params).fetchall()
    return [_row_to_dict(row) for row in rows]


def delete_pin(pin_id: str) -> bool:
    with _LOCK:
        with _conn() as c:
            cur = c.execute("DELETE FROM autonomous_asset_pins WHERE id = ?", (pin_id,))
            return cur.rowcount > 0


def stats() -> dict[str, Any]:
    with _LOCK:
        with _conn() as c:
            total = c.execute("SELECT COUNT(*) AS n FROM autonomous_asset_pins").fetchone()["n"]
            by_status = c.execute(
                "SELECT status, COUNT(*) AS n FROM autonomous_asset_pins GROUP BY status"
            ).fetchall()
    return {
        "schema_version": "cinejelly.asset_pin_stats.v1",
        "total_pins": int(total or 0),
        "status_counts": {row["status"]: int(row["n"]) for row in by_status},
    }


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    asset = assets_store.get_asset(row["asset_id"])
    return {
        "id": row["id"],
        "asset_id": row["asset_id"],
        "role": row["role"],
        "target_market": row["target_market"],
        "niche": row["niche"],
        "series_key": row["series_key"],
        "priority": row["priority"],
        "status": row["status"],
        "notes": row["notes"],
        "metadata": json.loads(row["metadata"] or "{}"),
        "asset": asset,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _normalize_status(status: str) -> str:
    s = (status or "active").strip().lower()
    if s not in _ALLOWED_STATUS:
        raise ValueError(f"invalid pin status: {status}")
    return s


def _clean(value: Optional[str], fallback: str) -> str:
    out = (value or fallback).strip().lower()
    return out or fallback


__all__ = [
    "create_pin",
    "update_pin",
    "get_pin",
    "list_pins",
    "delete_pin",
    "stats",
]
