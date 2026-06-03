"""Linear segment graph builder for Phase 9A long-form MVP."""
from __future__ import annotations

from longform.contracts import ContinuityBible, SegmentHandoff, SegmentPlan
from pipeline.contracts import canonical_hash


class SegmentGraphBuilder:
    """Create and validate a linear segment graph with explicit handoffs."""

    def build_linear_graph(
        self,
        *,
        segments: list[SegmentPlan],
        continuity_bible: ContinuityBible,
    ) -> list[SegmentHandoff]:
        """Return one handoff record per segment in linear render order."""
        if not segments:
            raise ValueError("long-form segment graph requires at least one segment")
        handoffs: list[SegmentHandoff] = []
        for index, segment in enumerate(segments):
            previous = segments[index - 1] if index > 0 else None
            handoffs.append(SegmentHandoff(
                previous_segment_id=previous.segment_id if previous else None,
                next_segment_id=segment.segment_id,
                character_state={
                    "carry_from_previous": bool(previous),
                    "tracks": continuity_bible.character_tracks,
                },
                prop_state={
                    "carry_from_previous": bool(previous),
                    "tracks": continuity_bible.product_tracks,
                },
                emotion_state={
                    "entry": segment.entry_state.get("emotion"),
                    "exit": segment.exit_state.get("emotion"),
                    "arc": continuity_bible.emotion_arc,
                },
                scene_state={
                    "entry": segment.entry_state.get("scene"),
                    "exit": segment.exit_state.get("scene"),
                    "continuity_pressure": continuity_bible.continuity_pressure,
                },
                continuity_notes=[
                    "linear_graph_no_branching",
                    "use previous last_frame_url as next segment visual anchor" if previous else "capture first segment last frame",
                    *segment.handoff_requirements,
                ],
                rules_applied=[
                    "phase9a.segment_graph.linear_only",
                    "phase9a.segment_graph.last_frame_handoff",
                ],
            ))
        return handoffs

    def validate_linear_graph(
        self,
        *,
        segments: list[SegmentPlan],
        graph: list[SegmentHandoff],
    ) -> list[str]:
        """Return validation warnings for graph/segment mismatches."""
        warnings: list[str] = []
        if len(graph) != len(segments):
            warnings.append("segment_graph_length_mismatch")
        segment_ids = [segment.segment_id for segment in segments]
        next_ids = [edge.next_segment_id for edge in graph]
        if next_ids != segment_ids[: len(next_ids)]:
            warnings.append("segment_graph_order_mismatch")
        for index, edge in enumerate(graph):
            expected_previous = segment_ids[index - 1] if index > 0 else None
            if edge.previous_segment_id != expected_previous:
                warnings.append(f"segment_graph_previous_mismatch:{edge.next_segment_id}")
        return list(dict.fromkeys(warnings))

    def graph_hash(self, graph: list[SegmentHandoff]) -> str:
        """Return a stable hash of the segment graph."""
        return canonical_hash(graph)


__all__ = ["SegmentGraphBuilder"]
