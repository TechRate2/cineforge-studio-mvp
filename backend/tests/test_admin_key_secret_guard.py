"""Admin/operator gates must ignore placeholder ADMIN_API_KEY values."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_direct_paid_guard_treats_placeholder_admin_key_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.routes import paid_guard

    monkeypatch.setattr(paid_guard.settings, "allow_direct_paid_generation", True, raising=False)
    monkeypatch.setattr(paid_guard.settings, "admin_api_key", "your-api-key", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        paid_guard.require_direct_paid_generation("your-api-key")

    exc = exc_info.value
    assert exc.status_code == 424
    assert exc.detail["code"] == "missing_env"
    assert exc.detail["missing_env"] == ["ADMIN_API_KEY"]
    assert exc.detail["vendor_calls_performed"] is False


def test_admin_mutation_guard_treats_placeholder_admin_key_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.routes import admin

    monkeypatch.setattr(admin.settings, "app_env", "production", raising=False)
    monkeypatch.setattr(admin.settings, "admin_api_key", "replace_me", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(admin.require_admin("replace_me"))

    assert exc_info.value.status_code == 403
    assert "ADMIN_API_KEY" in str(exc_info.value.detail)


def test_director_operator_guard_treats_placeholder_admin_key_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.routes import director

    monkeypatch.setattr(director.app_settings, "admin_api_key", "xxxxxxxxxxxx", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        director._require_mutation_admin("xxxxxxxxxxxx")

    assert exc_info.value.status_code == 403
    assert "ADMIN_API_KEY" in str(exc_info.value.detail)
