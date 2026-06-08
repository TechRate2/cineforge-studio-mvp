from __future__ import annotations

import pytest

from vendors import r2_storage


def _patch_missing_r2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(r2_storage.settings, "r2_account_id", "")
    monkeypatch.setattr(r2_storage.settings, "r2_access_key_id", "")
    monkeypatch.setattr(r2_storage.settings, "r2_secret_access_key", "")
    monkeypatch.setattr(r2_storage.settings, "r2_bucket_name", "ugc-vietnam-output")


def test_r2_config_rejects_placeholder_secret_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(r2_storage.settings, "r2_account_id", "xxxxxxxx")
    monkeypatch.setattr(r2_storage.settings, "r2_access_key_id", "your_api_key")
    monkeypatch.setattr(r2_storage.settings, "r2_secret_access_key", "<secret>")
    monkeypatch.setattr(r2_storage.settings, "r2_bucket_name", "ugc-vietnam-output")

    assert r2_storage.is_configured() is False


@pytest.mark.asyncio
async def test_upload_with_fallback_refuses_local_file_url_by_default(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_missing_r2(monkeypatch)
    monkeypatch.setattr(r2_storage.settings, "app_env", "development")
    monkeypatch.setattr(r2_storage.settings, "allow_r2_local_fallback", False)
    local_file = tmp_path / "final.mp4"
    local_file.write_bytes(b"fake-test-bytes")

    with pytest.raises(RuntimeError, match="R2 not configured"):
        await r2_storage.upload_with_fallback(local_file, "video/test/final.mp4")


@pytest.mark.asyncio
async def test_upload_with_fallback_local_file_url_requires_explicit_dev_opt_in(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_missing_r2(monkeypatch)
    monkeypatch.setattr(r2_storage.settings, "app_env", "development")
    monkeypatch.setattr(r2_storage.settings, "allow_r2_local_fallback", True)
    local_file = tmp_path / "final.mp4"
    local_file.write_bytes(b"local-dev-only")

    result = await r2_storage.upload_with_fallback(local_file, "video/test/final.mp4")

    assert result.startswith("file://")
