"""Phase 0 smoke tests for typed pipeline contracts."""
from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_phase0_pipeline_contracts_import() -> None:
    """Contracts should be importable before later implementation phases."""
    from pipeline.contracts import InputContract, StoryboardScene

    request = InputContract(user_idea="Create a cinematic product video")
    scene = StoryboardScene(index=0, beat="hook", action="product rotates")

    assert request.input_id.startswith("input_")
    assert scene.index == 0
