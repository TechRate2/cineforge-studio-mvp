"""Shared helpers for safe local smoke scripts."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.config import settings  # noqa: E402
from core.env_guard import missing_secret_names  # noqa: E402
from core.media_tools import missing_media_tools as _missing_media_tools  # noqa: E402


def missing_vendor_env() -> list[str]:
    """Return missing env names for paid video vendor calls."""
    return missing_secret_names([
        ("ATLASCLOUD_API_KEY", settings.atlascloud_api_key),
    ])


def missing_delivery_env() -> list[str]:
    """Return missing env names for final storage delivery."""
    return missing_secret_names([
        ("R2_ACCOUNT_ID", settings.r2_account_id),
        ("R2_ACCESS_KEY_ID", settings.r2_access_key_id),
        ("R2_SECRET_ACCESS_KEY", settings.r2_secret_access_key),
        ("R2_BUCKET_NAME", settings.r2_bucket_name),
    ])


def missing_media_tools() -> list[str]:
    """Return missing local media tools needed for assembly QA."""
    return _missing_media_tools()


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def missing_env_payload(*, missing: list[str], message: str) -> dict[str, Any]:
    return {
        "status": "missing_env",
        "message": message,
        "missing_env": missing,
        "vendor_calls_performed": False,
    }
