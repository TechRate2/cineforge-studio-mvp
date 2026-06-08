from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_role_tagger_default_skips_vision_llm(monkeypatch) -> None:
    """Normal autonomous planning must stay metadata/position based."""
    from skills import role_tagger
    from skills.role_tagger import RoleTagger, RoleTaggerInput

    calls: list[dict[str, Any]] = []

    def fail_if_called(**kwargs: Any) -> str:
        calls.append(kwargs)
        raise AssertionError("vision LLM must be opt-in only")

    monkeypatch.setattr(role_tagger.llm, "complete_with_image", fail_if_called)

    result = asyncio.run(RoleTagger().run(RoleTaggerInput(
        image_urls=["https://cdn.example.com/ref-1.png", "https://cdn.example.com/ref-2.png"],
        niche="beauty",
        user_idea="Create a serum product ad.",
    )))

    assert calls == []
    assert [item.role for item in result.tagged] == ["character_anchor", "product_hero"]
    assert all(item.confidence == 0.5 for item in result.tagged)


def test_role_tagger_vision_llm_runs_only_when_explicitly_enabled(monkeypatch) -> None:
    """Explicit opt-in keeps the existing vision role suggestion lane available."""
    from skills import role_tagger
    from skills.role_tagger import RoleTagger, RoleTaggerInput

    calls: list[dict[str, Any]] = []

    def fake_vision(**kwargs: Any) -> str:
        calls.append(kwargs)
        return '{"roles": ["product_hero", "style_reference"]}'

    monkeypatch.setattr(role_tagger.llm, "complete_with_image", fake_vision)

    result = asyncio.run(RoleTagger().run(RoleTaggerInput(
        image_urls=["https://cdn.example.com/ref-1.png", "https://cdn.example.com/ref-2.png"],
        niche="beauty",
        user_idea="Create a serum product ad.",
        use_vision_llm=True,
    )))

    assert len(calls) == 1
    assert calls[0]["task"] == "vision"
    assert [item.role for item in result.tagged] == ["product_hero", "style_reference"]
    assert all(item.confidence == 0.8 for item in result.tagged)


def test_autonomous_request_defaults_skip_vision_role_tagging() -> None:
    """API and internal director defaults must preserve metadata-only Reference Intelligence V1."""
    from agent.autonomous_director import AutonomousRunRequest
    from api.routes.director import AutonomousGenerateRequest

    api_request = AutonomousGenerateRequest(user_idea="Create a premium serum product ad.")
    director_request = AutonomousRunRequest(user_idea="Create a premium serum product ad.")

    assert api_request.use_vision_llm_for_tagging is False
    assert director_request.use_vision_llm_for_tagging is False
