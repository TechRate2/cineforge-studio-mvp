from __future__ import annotations

import asyncio
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_conversational_preflight_api_infers_vietnamese_market_and_duration() -> None:
    from api.routes import director

    async def run_case() -> None:
        request = director.ConversationalPreflightRequest(
            user_idea=(
                "T\u1ea1o video TikTok 12s cho serum l\u00e0m \u0111\u1eb9p t\u1ea1i Vi\u1ec7t Nam, "
                "m\u1edf \u0111\u1ea7u b\u1eb1ng b\u1eb1ng ch\u1ee9ng hi\u1ec7u qu\u1ea3, phong c\u00e1ch creator "
                "cao c\u1ea5p, c\u00f3 c\u1ea3nh c\u1eadn s\u1ea3n ph\u1ea9m v\u00e0 k\u1ebft th\u00fac b\u1eb1ng CTA nh\u1eb9."
            ),
            target_market="auto",
            target_platform="tiktok",
            duration_hint_s=None,
            reference_counts={"images": 0, "videos": 0, "audios": 0},
        )

        data = await director.autonomous_conversational_preflight(request)
        decision = data["production_decision"]["decision"]

        assert data["summary"]["market"] == "vn"
        assert data["summary"]["target_duration_s"] == 12
        assert decision["target_market"] == "vn"
        assert decision["target_duration_s"] == 12
        assert data["production_decision"]["market_playbook"]["primary_language"] == "Vietnamese"
        assert "T\u00f4i \u0111\u00e3 d\u1ef1ng k\u1ebf ho\u1ea1ch" in data["assistant_message"]
        assert "ph\u00ea duy\u1ec7t \u0111\u1ec3 render" in data["assistant_message"]
        assert "I drafted" not in data["assistant_message"]
        assert data["planning_trace"]["vendor_calls_performed"] is False
        assert data["planning_trace"]["paid_video_vendor_calls_allowed"] is False

    asyncio.run(run_case())
