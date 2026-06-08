"""Admin credits endpoint must not fabricate vendor wallet balances."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_admin_credits_reports_readiness_without_fake_balances(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.routes import admin

    monkeypatch.setattr(admin.settings, "atlascloud_api_key", "your-api-key", raising=False)
    monkeypatch.setattr(admin.settings, "atlascloud_base_url", "https://atlas.example", raising=False)
    monkeypatch.setattr(admin.settings, "atlascloud_llm_api_key", "sk-real-llm-key", raising=False)
    monkeypatch.setattr(admin.settings, "atlascloud_llm_base_url", "https://atlas-llm.example", raising=False)
    monkeypatch.setattr(admin.settings, "genmax_api_key", "", raising=False)
    monkeypatch.setattr(admin.settings, "genmax_base_url", "https://genmax.example", raising=False)
    monkeypatch.setattr(admin.settings, "anthropic_api_key", "", raising=False)
    monkeypatch.setattr(admin.settings, "r2_account_id", "", raising=False)
    monkeypatch.setattr(admin.settings, "r2_access_key_id", "replace_me", raising=False)
    monkeypatch.setattr(admin.settings, "r2_secret_access_key", "", raising=False)
    monkeypatch.setattr(admin.settings, "r2_bucket_name", "", raising=False)
    monkeypatch.setattr(admin.settings, "r2_public_url", "", raising=False)

    payload = asyncio.run(admin.get_credits())

    assert payload["schema_version"] == "cineforge.admin_credits.v1"
    assert "atlascloud" not in payload
    assert "r2" not in payload

    providers = payload["providers"]
    assert providers["atlascloud"]["status"] == "missing_env"
    assert providers["atlascloud"]["missing_env"] == ["ATLASCLOUD_API_KEY"]
    assert providers["atlascloud"]["balance"] is None
    assert providers["atlascloud"]["balance_status"] == "unavailable"
    assert "balance_usd" not in providers["atlascloud"]
    assert "balance_credits" not in providers["genmax"]

    assert providers["atlascloud_llm"]["status"] == "configured"
    assert providers["atlascloud_llm"]["key_masked"].startswith("sk-r")
    assert providers["genmax"]["status"] == "missing_env"
    assert providers["anthropic"]["status"] == "missing_env"

    r2 = payload["storage"]["r2"]
    assert r2["status"] == "missing_env"
    assert set(r2["missing_env"]) == {
        "R2_ACCOUNT_ID",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_BUCKET_NAME",
    }
