"""Style Preset Library — reusable bible-style bundles.

User lưu 1 lần combo (visual_style + audio_design + setting + constraints)
rồi apply vào plan mới mà không phải prompt lại từng lần. Director Agent
khi nhận `style_preset_id` trong tech_config sẽ pin các field này vào
Continuity Bible output.

Pattern: SQLite WAL, threading-safe, JSON blob for nested fields.

Schema:
    style_presets(
        id            TEXT PRIMARY KEY,         -- preset_xxxx
        name          TEXT NOT NULL,            -- "Cinematic 35mm warm",
        description   TEXT,                     -- 1-2 sentence summary
        visual_style  TEXT NOT NULL,            -- JSON dict
        audio_design  TEXT NOT NULL,
        setting       TEXT NOT NULL,
        constraints   TEXT NOT NULL,
        tags          TEXT NOT NULL DEFAULT '',
        is_builtin    INTEGER NOT NULL DEFAULT 0,
        created_at    TEXT NOT NULL,
        updated_at    TEXT NOT NULL,
        last_used_at  TEXT
    )
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


_DB_PATH = Path(__file__).parent.parent / "data" / "style_presets.db"
_LOCK = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS style_presets (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    visual_style  TEXT NOT NULL DEFAULT '{}',
    audio_design  TEXT NOT NULL DEFAULT '{}',
    setting       TEXT NOT NULL DEFAULT '{}',
    constraints   TEXT NOT NULL DEFAULT '{}',
    tags          TEXT NOT NULL DEFAULT '',
    is_builtin    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    last_used_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_presets_used      ON style_presets(last_used_at DESC);
CREATE INDEX IF NOT EXISTS idx_presets_builtin   ON style_presets(is_builtin DESC, updated_at DESC);
"""


# Default built-in presets seeded on first init — gives users a starting library.
_BUILTIN_PRESETS = [
    {
        "id": "preset_builtin_cinematic_warm",
        "name": "Cinematic 35mm — Warm filmic",
        "description": "Warm filmic grade, soft window light, shallow DOF — luxurious UGC / brand story.",
        "visual_style": {
            "cinematography": "cinematic 35mm anamorphic, shallow DOF",
            "color_grading": "warm filmic, slight teal shadows",
            "lighting_design": "golden hour soft window, key+fill ratio 3:1",
            "camera_language": "slow dolly-in, rack focus reveals",
            "film_grain": "light 35mm grain",
            "aspect_ratio": "9:16",
        },
        "audio_design": {
            "mood": "warm, intimate",
            "tempo": "mid",
            "music_genre": "lo-fi acoustic",
            "sfx_emphasis": ["fabric rustle", "soft ambient"],
            "dialogue_style": "conversational",
        },
        "setting": {
            "location": "indoor cafe / bedroom / studio",
            "time_of_day": "late afternoon",
            "atmosphere": "cosy",
        },
        "constraints": {
            "must_have": ["soft natural light"],
            "must_avoid": ["harsh studio strobe", "neon"],
            "brand_safety": [],
        },
        "tags": "cinematic, warm, premium, UGC",
    },
    {
        "id": "preset_builtin_genz_viral",
        "name": "Gen-Z Viral TikTok",
        "description": "Handheld iPhone UGC, fast cuts, punchy text overlays — for viral short hooks.",
        "visual_style": {
            "cinematography": "handheld iPhone UGC, vertical 9:16",
            "color_grading": "vivid saturated, slight cool blue",
            "lighting_design": "natural bright daylight, no harsh shadow",
            "camera_language": "whip pan, quick cuts, punch zoom",
            "film_grain": "clean digital",
            "aspect_ratio": "9:16",
        },
        "audio_design": {
            "mood": "energetic",
            "tempo": "fast",
            "music_genre": "trending TikTok pop",
            "sfx_emphasis": ["whoosh", "pop"],
            "dialogue_style": "conversational",
        },
        "setting": {
            "location": "any",
            "time_of_day": "daytime",
            "atmosphere": "high-energy",
        },
        "constraints": {
            "must_have": ["strong 2s hook"],
            "must_avoid": ["slow paced opening"],
            "brand_safety": [],
        },
        "tags": "viral, TikTok, gen-z, UGC, fast",
    },
    {
        "id": "preset_builtin_pastel_airy",
        "name": "Pastel Airy Beauty",
        "description": "Soft pastel pinks/creams, airy backlit — beauty / skincare aesthetic.",
        "visual_style": {
            "cinematography": "macro close-up, soft focus",
            "color_grading": "pastel airy, lifted blacks",
            "lighting_design": "backlit window haze, soft bounce fill",
            "camera_language": "static + slow push-in, rack focus on product",
            "film_grain": "clean digital with subtle bloom",
            "aspect_ratio": "9:16",
        },
        "audio_design": {
            "mood": "calm, dreamy",
            "tempo": "slow",
            "music_genre": "ambient pads",
            "sfx_emphasis": ["bottle clink", "liquid pour"],
            "dialogue_style": "silent",
        },
        "setting": {
            "location": "vanity table / bathroom",
            "time_of_day": "morning",
            "atmosphere": "fresh, clean",
        },
        "constraints": {
            "must_have": ["product visibility", "soft natural light"],
            "must_avoid": ["dark moody shadows"],
            "brand_safety": ["no medical claims"],
        },
        "tags": "beauty, skincare, pastel, aesthetic, silent",
    },
]


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
            # Seed built-in nếu lần đầu
            count = c.execute("SELECT COUNT(*) FROM style_presets WHERE is_builtin=1").fetchone()[0]
            if count == 0:
                now = datetime.now(timezone.utc).isoformat()
                for p in _BUILTIN_PRESETS:
                    c.execute(
                        """
                        INSERT OR REPLACE INTO style_presets
                            (id, name, description, visual_style, audio_design, setting,
                             constraints, tags, is_builtin, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                        """,
                        (
                            p["id"], p["name"], p["description"],
                            json.dumps(p["visual_style"], ensure_ascii=False),
                            json.dumps(p["audio_design"], ensure_ascii=False),
                            json.dumps(p["setting"], ensure_ascii=False),
                            json.dumps(p["constraints"], ensure_ascii=False),
                            p["tags"], now, now,
                        ),
                    )
                logger.info(f"[style_presets] seeded {len(_BUILTIN_PRESETS)} built-in presets")


_init()


# ============================================================
# CRUD
# ============================================================
def list_presets(search: Optional[str] = None, limit: int = 100) -> list[dict]:
    q = "SELECT * FROM style_presets WHERE 1=1"
    params: list[Any] = []
    if search:
        q += " AND (name LIKE ? OR tags LIKE ? OR description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    # Built-ins first, then most-used user presets
    q += " ORDER BY is_builtin DESC, COALESCE(last_used_at, updated_at) DESC LIMIT ?"
    params.append(limit)
    with _LOCK:
        with _conn() as c:
            rows = c.execute(q, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_preset(preset_id: str) -> Optional[dict]:
    with _LOCK:
        with _conn() as c:
            row = c.execute("SELECT * FROM style_presets WHERE id=?", (preset_id,)).fetchone()
    return _row_to_dict(row) if row else None


def create_preset(
    *,
    name: str,
    description: str = "",
    visual_style: dict,
    audio_design: dict,
    setting: dict,
    constraints: dict,
    tags: str = "",
) -> dict:
    preset_id = f"preset_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        with _conn() as c:
            c.execute(
                """
                INSERT INTO style_presets
                    (id, name, description, visual_style, audio_design, setting,
                     constraints, tags, is_builtin, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    preset_id, name, description,
                    json.dumps(visual_style, ensure_ascii=False),
                    json.dumps(audio_design, ensure_ascii=False),
                    json.dumps(setting, ensure_ascii=False),
                    json.dumps(constraints, ensure_ascii=False),
                    tags, now, now,
                ),
            )
    logger.info(f"[style_presets] created {preset_id} '{name}'")
    return get_preset(preset_id)  # type: ignore[return-value]


def update_preset(preset_id: str, **fields: Any) -> Optional[dict]:
    existing = get_preset(preset_id)
    if not existing or existing.get("is_builtin"):
        return None  # Cannot edit built-ins
    allowed = {"name", "description", "visual_style", "audio_design", "setting", "constraints", "tags"}
    updates: dict[str, Any] = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return existing
    now = datetime.now(timezone.utc).isoformat()
    json_keys = {"visual_style", "audio_design", "setting", "constraints"}
    set_parts: list[str] = []
    params: list[Any] = []
    for k, v in updates.items():
        set_parts.append(f"{k}=?")
        params.append(json.dumps(v, ensure_ascii=False) if k in json_keys else v)
    set_parts.append("updated_at=?")
    params.extend([now, preset_id])
    with _LOCK:
        with _conn() as c:
            c.execute(f"UPDATE style_presets SET {', '.join(set_parts)} WHERE id=?", params)
    return get_preset(preset_id)


def touch_used(preset_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        with _conn() as c:
            c.execute("UPDATE style_presets SET last_used_at=? WHERE id=?", (now, preset_id))


def delete_preset(preset_id: str) -> bool:
    with _LOCK:
        with _conn() as c:
            row = c.execute("SELECT is_builtin FROM style_presets WHERE id=?", (preset_id,)).fetchone()
            if not row:
                return False
            if row["is_builtin"]:
                # Refuse to delete built-ins
                return False
            cur = c.execute("DELETE FROM style_presets WHERE id=?", (preset_id,))
            return cur.rowcount > 0


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "visual_style": json.loads(row["visual_style"] or "{}"),
        "audio_design": json.loads(row["audio_design"] or "{}"),
        "setting": json.loads(row["setting"] or "{}"),
        "constraints": json.loads(row["constraints"] or "{}"),
        "tags": row["tags"] or "",
        "is_builtin": bool(row["is_builtin"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_used_at": row["last_used_at"],
    }
