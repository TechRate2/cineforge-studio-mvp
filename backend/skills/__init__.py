"""CineJelly Skills — modular per-domain skill files.

Pattern (Skill OS inspired): mỗi file = 1 class + Pydantic input/output schemas
+ 1 `async def run()` method. Skills standalone (no cross-skill imports), được
chain qua `agent/autonomous_director.py` orchestrator.

Active skills (V6.1 — Autonomous Director big update):
  - planner       : niche analysis + viral hook 3-second
  - storyboard    : 6-9 panel layout (short) hoặc multi-chunk (long-form)
  - director      : shot count + duration + camera + long-form chain decision
  - role_tagger   : quad-modal @image_N / @video_N / @audio_N role binding
  - editor        : transition cues + viral caption + hashtags VN/EN

Mỗi skill có thể chạy độc lập (unit test) hoặc qua orchestrator (production).
Pattern intentionally KHÔNG dùng abstract base class — over-abstraction cho 5 skills.
"""

from .planner import AutoPlanner, PlannerInput, PlannerOutput
from .storyboard import AutoStoryboard, StoryboardInput, StoryboardOutput, StoryboardPanel
from .director import AutoDirector, DirectorInput, DirectorOutput
from .role_tagger import RoleTagger, RoleTaggerInput, RoleTaggerOutput, TaggedReference
from .editor import AutoEditor, EditorInput, EditorOutput
from .niche_playbooks import get_niche_playbook, list_niche_keys
from .market_playbooks import get_market_playbook
from .niche_benchmarks import (
    list_benchmark_cases,
    get_benchmark_case,
    validate_benchmark_coverage,
)
from .niche_readiness import build_niche_readiness_matrix

__all__ = [
    "AutoPlanner", "PlannerInput", "PlannerOutput",
    "AutoStoryboard", "StoryboardInput", "StoryboardOutput", "StoryboardPanel",
    "AutoDirector", "DirectorInput", "DirectorOutput",
    "RoleTagger", "RoleTaggerInput", "RoleTaggerOutput", "TaggedReference",
    "AutoEditor", "EditorInput", "EditorOutput",
    "get_niche_playbook", "list_niche_keys", "get_market_playbook",
    "list_benchmark_cases", "get_benchmark_case", "validate_benchmark_coverage",
    "build_niche_readiness_matrix",
]
