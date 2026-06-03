"""Continuity bible builder for Phase 9A long-form MVP."""
from __future__ import annotations

from typing import Any

from longform.contracts import ContinuityBible, SegmentPlan
from pipeline.contracts import AnalyzedInput, CreativePlan


class ContinuityBibleBuilder:
    """Build the continuity contract shared by all long-form segments."""

    def build(
        self,
        *,
        creative_plan: CreativePlan,
        analyzed_input: AnalyzedInput,
    ) -> ContinuityBible:
        """Create a continuity bible from Phase 6A/7A metadata."""
        readiness = creative_plan.metadata.get("long_form_readiness") or {}
        identity_snapshot = readiness.get("identity_bible_snapshot") or {}
        consistency_plan = creative_plan.consistency_plan or {}
        style_rules = _style_rules(creative_plan, consistency_plan)
        emotion_arc = _emotion_arc(creative_plan)
        return ContinuityBible(
            source_identity_bible_snapshot=dict(identity_snapshot),
            continuity_pressure=str(readiness.get("continuity_pressure") or "medium"),
            character_tracks={
                "required": bool(consistency_plan.get("character_lock")),
                "anchor_asset_ids": list(identity_snapshot.get("character_anchor_asset_ids") or []),
                "stable_traits": list(identity_snapshot.get("stable_character_traits") or []),
            },
            product_tracks={
                "required": bool(consistency_plan.get("product_lock")),
                "anchor_asset_ids": list(identity_snapshot.get("product_anchor_asset_ids") or []),
                "rules": list(identity_snapshot.get("product_rules") or []),
            },
            style_rules=style_rules,
            emotion_arc=emotion_arc,
            forbidden_drift=_forbidden_drift(consistency_plan),
            rules_applied=[
                "phase9a.continuity_bible.identity_snapshot",
                "phase9a.continuity_bible.segment_handoff_requirements",
                "phase9a.continuity_bible.forbidden_drift",
            ],
            warnings=_warnings(readiness=readiness, analyzed_input=analyzed_input),
            metadata={
                "analysis_id": analyzed_input.analysis_id,
                "creative_plan_id": creative_plan.creative_plan_id,
                "requested_duration_s": readiness.get("requested_duration_s") or creative_plan.duration_s,
                "segment_handoff_requirements": list(readiness.get("segment_handoff_requirements") or []),
                "pre_render_consistency_score": readiness.get("pre_render_consistency_score"),
            },
        )

    def attach_segment_snapshots(
        self,
        *,
        continuity_bible: ContinuityBible,
        segments: list[SegmentPlan],
    ) -> ContinuityBible:
        """Return a bible copy with segment-level continuity snapshots."""
        snapshots = {
            segment.segment_id: {
                "index": segment.index,
                "entry_state": segment.entry_state,
                "exit_state": segment.exit_state,
                "last_frame_anchor": segment.last_frame_anchor,
            }
            for segment in segments
        }
        return continuity_bible.model_copy(update={"segment_snapshots": snapshots})


def _style_rules(creative_plan: CreativePlan, consistency_plan: dict[str, Any]) -> list[str]:
    rules = [
        creative_plan.style_direction,
        "preserve one camera language across segments",
        "preserve lighting and color palette continuity",
        *list(consistency_plan.get("lock_notes") or []),
    ]
    return _dedupe(rules)


def _emotion_arc(creative_plan: CreativePlan) -> list[str]:
    arc = list(creative_plan.narrative_arc or [])
    if not arc:
        arc = [creative_plan.hook_pattern or creative_plan.objective]
    return _dedupe(arc)


def _forbidden_drift(consistency_plan: dict[str, Any]) -> list[str]:
    drift = ["no identity drift", "no style drift", "no continuity reset between segments"]
    if consistency_plan.get("character_lock"):
        drift.append("no face, hair, outfit, or silhouette changes")
    if consistency_plan.get("product_lock"):
        drift.append("no product geometry, label, logo, or package color changes")
    return _dedupe(drift)


def _warnings(*, readiness: dict[str, Any], analyzed_input: AnalyzedInput) -> list[str]:
    warnings: list[str] = []
    if not readiness.get("identity_bible_snapshot"):
        warnings.append("missing_identity_bible_snapshot")
    if int(analyzed_input.duration_s or 0) > 60:
        warnings.append("phase9a_duration_above_mvp_cap")
    return warnings


def _dedupe(values: list[Any]) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


__all__ = ["ContinuityBibleBuilder"]
