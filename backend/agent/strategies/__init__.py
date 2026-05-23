"""WorkflowStrategy — Model-aware dispatch per AtlasCloud video model.

Pattern: Strategy + Smart Picker.
Director Agent V3 dispatches different prompt format / ref count / preprocessing
per video model — Seedance 2.0 multi-shot time-coded, Vidu Q3 inline-named refs,
Wan 2.7 lipsync (no prompt — audio+portrait only).

Inspired by:
    - Topview AI (Seedance-native architecture)
    - Higgsfield (MCSLA per-model serialization)
    - Pollo AI (declarative model picker)
    - Industry research 2026-05 (see CLAUDE.md)
"""

from agent.strategies.base import (
    Script,
    Scene,
    Character,
    VideoJob,
    WorkflowStrategy,
)
from agent.strategies.seedance_2 import SeedanceV2Strategy
from agent.strategies.seedance_2_fast import SeedanceV2FastStrategy
from agent.strategies.vidu_q3 import ViduQ3Strategy
from agent.strategies.vidu_q3_mix import ViduQ3MixStrategy
from agent.strategies.wan_27_lipsync import Wan27LipsyncStrategy
from agent.strategies.seedance_15_pro import Seedance15ProStrategy


# Registry — singleton list of all available strategies, indexed by user_model key.
# Order matters for smart picker default tie-break (higher = preferred when scores equal).
ALL_STRATEGIES: list[WorkflowStrategy] = [
    SeedanceV2Strategy(),
    ViduQ3Strategy(),
    ViduQ3MixStrategy(),
    Wan27LipsyncStrategy(),
    Seedance15ProStrategy(),
    SeedanceV2FastStrategy(),
]


def get_strategy_for_model(user_model: str) -> WorkflowStrategy:
    """Lookup strategy by user_model key (vd 'seedance_2_0', 'vidu_q3', 'wan_2_7').

    Raises:
        ValueError nếu không tìm strategy match.
    """
    for s in ALL_STRATEGIES:
        if s.user_model == user_model:
            return s
    raise ValueError(
        f"No strategy for user_model='{user_model}'. "
        f"Available: {[s.user_model for s in ALL_STRATEGIES]}"
    )


__all__ = [
    "Script",
    "Scene",
    "Character",
    "VideoJob",
    "WorkflowStrategy",
    "SeedanceV2Strategy",
    "SeedanceV2FastStrategy",
    "ViduQ3Strategy",
    "ViduQ3MixStrategy",
    "Wan27LipsyncStrategy",
    "Seedance15ProStrategy",
    "ALL_STRATEGIES",
    "get_strategy_for_model",
]
