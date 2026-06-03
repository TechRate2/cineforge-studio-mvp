"""Long-form segmented planner for Phase 9A MVP."""
from __future__ import annotations

import math
from typing import Any

from longform.continuity_bible import ContinuityBibleBuilder
from longform.contracts import ActPlan, LongFormExecutionPlan, SegmentPlan, SequencePlan
from longform.segment_graph import SegmentGraphBuilder
from pipeline.contracts import AnalyzedInput, CreativePlan


class LongFormPlanner:
    """Plan a 30-60s video as a linear graph of 10-12s Seedance segments."""

    def __init__(
        self,
        *,
        continuity_bible_builder: ContinuityBibleBuilder | None = None,
        segment_graph_builder: SegmentGraphBuilder | None = None,
    ) -> None:
        self.continuity_bible_builder = continuity_bible_builder or ContinuityBibleBuilder()
        self.segment_graph_builder = segment_graph_builder or SegmentGraphBuilder()

    def plan(
        self,
        *,
        creative_plan: CreativePlan,
        analyzed_input: AnalyzedInput,
    ) -> LongFormExecutionPlan:
        """Build a long-form execution plan without compiling render prompts."""
        total_duration_s = _longform_duration_s(creative_plan=creative_plan, analyzed_input=analyzed_input)
        durations = _allocate_segment_durations(total_duration_s)
        continuity_bible = self.continuity_bible_builder.build(
            creative_plan=creative_plan,
            analyzed_input=analyzed_input,
        )
        identity_snapshot = dict(continuity_bible.source_identity_bible_snapshot)
        handoff_requirements = _handoff_requirements(creative_plan)
        segments = _build_segments(
            durations=durations,
            creative_plan=creative_plan,
            continuity_pressure=continuity_bible.continuity_pressure,
            identity_snapshot=identity_snapshot,
            handoff_requirements=handoff_requirements,
        )
        continuity_bible = self.continuity_bible_builder.attach_segment_snapshots(
            continuity_bible=continuity_bible,
            segments=segments,
        )
        graph = self.segment_graph_builder.build_linear_graph(
            segments=segments,
            continuity_bible=continuity_bible,
        )
        graph_warnings = self.segment_graph_builder.validate_linear_graph(segments=segments, graph=graph)
        sequence = SequencePlan(
            index=0,
            objective=creative_plan.objective,
            segment_ids=[segment.segment_id for segment in segments],
            start_s=0,
            duration_s=total_duration_s,
        )
        act = ActPlan(
            index=0,
            objective=creative_plan.objective,
            sequence_ids=[sequence.sequence_id],
            start_s=0,
            duration_s=total_duration_s,
        )
        return LongFormExecutionPlan(
            source_creative_plan_id=creative_plan.creative_plan_id,
            total_duration_s=total_duration_s,
            acts=[act],
            sequences=[sequence],
            segments=segments,
            segment_graph=graph,
            continuity_bible=continuity_bible,
            rules_applied=[
                "phase9a.longform_planner.segmented_orchestration",
                "phase9a.longform_planner.segment_duration_10_12s",
                "phase9a.longform_planner.linear_graph_only",
            ],
            warnings=graph_warnings,
            metadata={
                "analysis_id": analyzed_input.analysis_id,
                "render_path": "long_form_segmented",
                "segment_count": len(segments),
                "segment_duration_s": durations,
                "continuity_pressure": continuity_bible.continuity_pressure,
                "identity_bible_snapshot": identity_snapshot,
                "segment_handoff_requirements": handoff_requirements,
                "phase9a_mvp": True,
            },
        )


def _longform_duration_s(*, creative_plan: CreativePlan, analyzed_input: AnalyzedInput) -> int:
    readiness = creative_plan.metadata.get("long_form_readiness") or {}
    duration_s = int(readiness.get("requested_duration_s") or analyzed_input.duration_s or creative_plan.duration_s)
    if not 30 <= duration_s <= 60:
        raise ValueError("Phase 9A MVP supports long-form durations from 30 to 60 seconds.")
    return duration_s


def _allocate_segment_durations(total_duration_s: int) -> list[int]:
    segment_count = max(3, math.ceil(total_duration_s / 12))
    if segment_count > 5:
        raise ValueError("Phase 9A MVP supports at most 5 long-form segments.")
    base = total_duration_s // segment_count
    remainder = total_duration_s % segment_count
    durations = [base + (1 if index < remainder else 0) for index in range(segment_count)]
    if any(duration < 10 or duration > 12 for duration in durations):
        raise ValueError("Phase 9A segment allocation must stay between 10 and 12 seconds.")
    return durations


def _build_segments(
    *,
    durations: list[int],
    creative_plan: CreativePlan,
    continuity_pressure: str,
    identity_snapshot: dict[str, Any],
    handoff_requirements: list[str],
) -> list[SegmentPlan]:
    segments: list[SegmentPlan] = []
    cursor = 0
    arc = list(creative_plan.narrative_arc or [creative_plan.hook_pattern or creative_plan.objective])
    for index, duration_s in enumerate(durations):
        objective = arc[min(index, len(arc) - 1)] if arc else creative_plan.objective
        entry_state = _entry_state(index=index, creative_plan=creative_plan, objective=objective)
        exit_state = _exit_state(index=index, segment_count=len(durations), objective=objective)
        segment_id = f"segment_{index + 1:02d}"
        segments.append(SegmentPlan(
            segment_id=segment_id,
            index=index,
            start_s=cursor,
            duration_s=duration_s,
            objective=objective,
            entry_state=entry_state,
            exit_state=exit_state,
            last_frame_anchor={
                "required": True,
                "source": "previous_segment_last_frame" if index > 0 else "capture_for_next_segment",
                "previous_segment_id": f"segment_{index:02d}" if index > 0 else None,
                "url": None,
            },
            identity_bible_snapshot=identity_snapshot,
            handoff_requirements=handoff_requirements,
            metadata={
                "continuity_pressure": continuity_pressure,
                "longform_segment_index": index,
                "longform_segment_count": len(durations),
            },
        ))
        cursor += duration_s
    return segments


def _entry_state(*, index: int, creative_plan: CreativePlan, objective: str) -> dict[str, Any]:
    return {
        "scene": "opening_state" if index == 0 else "continue_from_previous_exit",
        "emotion": _emotion_for(index=index, creative_plan=creative_plan),
        "objective": objective,
    }


def _exit_state(*, index: int, segment_count: int, objective: str) -> dict[str, Any]:
    return {
        "scene": "final_payoff_state" if index == segment_count - 1 else "handoff_ready_state",
        "emotion": "resolved" if index == segment_count - 1 else "in_progress",
        "objective": objective,
    }


def _emotion_for(*, index: int, creative_plan: CreativePlan) -> str:
    if index == 0:
        return "setup"
    if index >= max(1, creative_plan.shot_count - 1):
        return "payoff"
    return "escalation"


def _handoff_requirements(creative_plan: CreativePlan) -> list[str]:
    readiness = creative_plan.metadata.get("long_form_readiness") or {}
    requirements = list(readiness.get("segment_handoff_requirements") or [])
    requirements.extend([
        "preserve identity_bible_snapshot",
        "carry previous last_frame_anchor into next segment",
        "preserve character, product, emotion, and scene state",
    ])
    return list(dict.fromkeys(str(item) for item in requirements if str(item).strip()))


__all__ = ["LongFormPlanner"]
