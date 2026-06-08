"""Vendor clients should ignore placeholder secrets."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_atlascloud_llm_ignores_placeholder_coding_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from vendors import atlascloud_llm

    monkeypatch.setattr(atlascloud_llm.settings, "atlascloud_llm_api_key", "your-api-key", raising=False)
    monkeypatch.setattr(atlascloud_llm.settings, "atlascloud_api_key", "pay-as-you-go-real-key", raising=False)
    monkeypatch.setattr(atlascloud_llm.settings, "atlascloud_llm_base_url", "https://llm.example/v1", raising=False)

    client = atlascloud_llm.AtlasCloudLLMClient()
    try:
        assert client.coding_plan_key == ""
        assert client.pay_as_you_go_key == "pay-as-you-go-real-key"
        assert client.api_key == "pay-as-you-go-real-key"
    finally:
        client.close()


def test_atlascloud_llm_rejects_placeholder_only_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    from vendors import atlascloud_llm

    monkeypatch.setattr(atlascloud_llm.settings, "atlascloud_llm_api_key", "replace_me", raising=False)
    monkeypatch.setattr(atlascloud_llm.settings, "atlascloud_api_key", "xxxxxxxxxxxx", raising=False)
    monkeypatch.setattr(atlascloud_llm.settings, "atlascloud_llm_base_url", "https://llm.example/v1", raising=False)

    with pytest.raises(RuntimeError, match="AtlasCloud LLM requires"):
        atlascloud_llm.AtlasCloudLLMClient()
