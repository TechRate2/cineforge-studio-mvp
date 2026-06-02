"""Typed pipeline contracts for CineForge Studio."""

from pipeline.approval_lock import ApprovalLock, ApprovalLockVerification
from pipeline.contracts import (
    AnalyzedInput,
    AssetRef,
    CreativePlan,
    InputContract,
    ReferenceRole,
    RenderAssemblyPlan,
    SeedanceExecutionPlan,
    SeedanceShotPlan,
    StoryboardContract,
    StoryboardScene,
    canonical_hash,
)
from pipeline.creative_planning import CreativePlanner
from pipeline.input_analysis import InputAnalyzer
from pipeline.render_execution import RenderExecutionResult, RenderExecutor
from pipeline.storyboard_generation import StoryboardGenerator
from pipeline.trace import PipelineTrace, PipelineTraceEntry

__all__ = [
    "ApprovalLock",
    "ApprovalLockVerification",
    "AnalyzedInput",
    "AssetRef",
    "CreativePlan",
    "CreativePlanner",
    "InputContract",
    "InputAnalyzer",
    "PipelineTrace",
    "PipelineTraceEntry",
    "ReferenceRole",
    "RenderAssemblyPlan",
    "RenderExecutionResult",
    "RenderExecutor",
    "SeedanceExecutionPlan",
    "SeedanceShotPlan",
    "StoryboardContract",
    "StoryboardGenerator",
    "StoryboardScene",
    "canonical_hash",
]
