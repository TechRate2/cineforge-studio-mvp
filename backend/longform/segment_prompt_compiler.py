"""Compile Phase 9A long-form segments into Seedance execution plans."""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from longform.contracts import LongFormExecutionPlan, SegmentPlan
from pipeline.contracts import AnalyzedInput, AssetRef, CreativePlan, SeedanceExecutionPlan, SeedanceShotPlan, canonical_hash
from workers.cost_control import CostControlService


class SegmentPromptCompiler:
    """Compile each long-form segment as a normal one-shot Seedance plan."""

    def __init__(self, *, cost_control: CostControlService | None = None) -> None:
        self.cost_control = cost_control or CostControlService()

    def compile(
        self,
        *,
        longform_plan: LongFormExecutionPlan,
        creative_plan: CreativePlan,
        analyzed_input: AnalyzedInput,
    ) -> LongFormExecutionPlan:
        """Attach per-segment SeedanceExecutionPlan objects and a master plan."""
        reference_assets = _metadata_asset_refs(analyzed_input)
        compiled_segments: list[SegmentPlan] = []
        for segment in longform_plan.segments:
            segment_execution_plan = self.compile_segment(
                longform_plan=longform_plan,
                creative_plan=creative_plan,
                analyzed_input=analyzed_input,
                segment=segment,
                reference_assets=reference_assets,
            )
            compiled_segments.append(segment.model_copy(update={
                "seedance_execution_plan": segment_execution_plan,
                "status": "compiled",
            }))
        master_plan = self.build_master_execution_plan(
            longform_plan=longform_plan.model_copy(update={"segments": compiled_segments}),
            creative_plan=creative_plan,
            reference_assets=reference_assets,
        )
        return longform_plan.model_copy(update={
            "segments": compiled_segments,
            "master_execution_plan": master_plan,
            "status": "compiled",
            "rules_applied": list(dict.fromkeys(longform_plan.rules_applied + [
                "phase9a.segment_prompt_compiler.per_segment_seedance_plan",
                "phase9a.segment_prompt_compiler.master_approval_plan",
            ])),
            "metadata": {
                **longform_plan.metadata,
                "master_execution_plan_id": master_plan.execution_plan_id,
                "segment_graph_hash": longform_plan.segment_graph_hash,
                "continuity_bible_hash": longform_plan.continuity_bible.continuity_hash,
            },
        })

    def compile_segment(
        self,
        *,
        longform_plan: LongFormExecutionPlan,
        creative_plan: CreativePlan,
        analyzed_input: AnalyzedInput,
        segment: SegmentPlan,
        reference_assets: list[AssetRef],
    ) -> SeedanceExecutionPlan:
        """Compile one segment into a one-shot SeedanceExecutionPlan."""
        shot = SeedanceShotPlan(
            shot_id=f"{segment.segment_id}_shot_0",
            index=0,
            duration_s=segment.duration_s,
            compiled_prompt=_segment_prompt(
                creative_plan=creative_plan,
                analyzed_input=analyzed_input,
                longform_plan=longform_plan,
                segment=segment,
            ),
            negative_prompt="no subtitles, no logo, no watermark, no identity drift, no style reset",
            model=str(creative_plan.metadata.get("model") or "seedance_2_0"),
            aspect_ratio=creative_plan.aspect_ratio,
            resolution=str(creative_plan.metadata.get("resolution") or "1080p"),
            references=reference_assets,
            rules_applied=[
                "phase9a.segment_prompt.entry_exit_state",
                "phase9a.segment_prompt.identity_bible_snapshot",
                "phase9a.segment_prompt.last_frame_handoff",
            ],
            metadata={
                "longform_plan_id": longform_plan.longform_plan_id,
                "segment_id": segment.segment_id,
                "segment_index": segment.index,
                "entry_state": segment.entry_state,
                "exit_state": segment.exit_state,
                "last_frame_anchor": segment.last_frame_anchor,
                "identity_bible_snapshot": segment.identity_bible_snapshot,
                "handoff_requirements": segment.handoff_requirements,
                "continuity_bible_hash": longform_plan.continuity_bible.continuity_hash,
                "segment_graph_hash": longform_plan.segment_graph_hash,
                "needs_identity_consistency": bool(creative_plan.consistency_plan.get("character_lock")),
                "needs_product_consistency": bool(creative_plan.consistency_plan.get("product_lock")),
                "needs_style_consistency": True,
                "consistency_score": creative_plan.consistency_plan.get("consistency_score"),
                "consistency_policy_action": creative_plan.consistency_plan.get("consistency_policy_action"),
                "consistency_policy_reasons": list(creative_plan.consistency_plan.get("consistency_policy_reasons") or []),
                "consistency_risk_flags": list(creative_plan.consistency_plan.get("consistency_risk_flags") or []),
            },
        )
        execution_plan = SeedanceExecutionPlan(
            storyboard_id=longform_plan.source_storyboard_id,
            model=shot.model,
            aspect_ratio=shot.aspect_ratio,
            resolution=shot.resolution,
            duration_s=segment.duration_s,
            compiled_prompt=shot.compiled_prompt,
            shots=[shot],
            reference_assets=reference_assets,
            rules_applied=[
                "phase9a.segment_execution_plan.one_seedance_clip_per_segment",
                *shot.rules_applied,
            ],
            metadata={
                "phase": "9a",
                "render_path": "long_form_segmented",
                "longform_plan_id": longform_plan.longform_plan_id,
                "segment_id": segment.segment_id,
                "segment_index": segment.index,
                "segment_graph_hash": longform_plan.segment_graph_hash,
                "continuity_bible_hash": longform_plan.continuity_bible.continuity_hash,
                "approved_idea": analyzed_input.normalized_idea,
                "long_form_readiness": creative_plan.metadata.get("long_form_readiness") or {},
                "consistency_policy_action": creative_plan.consistency_plan.get("consistency_policy_action"),
                "consistency_policy_reasons": list(creative_plan.consistency_plan.get("consistency_policy_reasons") or []),
            },
        )
        return execution_plan.model_copy(update={
            "cost_estimate": self.cost_control.estimate_plan_cost(execution_plan),
        })

    def build_master_execution_plan(
        self,
        *,
        longform_plan: LongFormExecutionPlan,
        creative_plan: CreativePlan,
        reference_assets: list[AssetRef],
    ) -> SeedanceExecutionPlan:
        """Create the single approval target for the whole long-form graph."""
        shots = [
            segment.seedance_execution_plan.shots[0]
            for segment in longform_plan.segments
            if segment.seedance_execution_plan and segment.seedance_execution_plan.shots
        ]
        master = SeedanceExecutionPlan(
            model=shots[0].model if shots else str(creative_plan.metadata.get("model") or "seedance_2_0"),
            aspect_ratio=creative_plan.aspect_ratio,
            resolution=str(creative_plan.metadata.get("resolution") or "1080p"),
            duration_s=longform_plan.total_duration_s,
            compiled_prompt="\n\n".join(shot.compiled_prompt for shot in shots),
            shots=shots,
            reference_assets=reference_assets,
            rules_applied=[
                "phase9a.master_execution_plan.single_approval_lock",
                "phase9a.master_execution_plan.segment_graph_hash",
                "phase9a.master_execution_plan.continuity_bible_hash",
            ],
            metadata={
                "phase": "9a",
                "render_path": "long_form_segmented",
                "longform_plan_id": longform_plan.longform_plan_id,
                "segment_ids": [segment.segment_id for segment in longform_plan.segments],
                "segment_graph_hash": longform_plan.segment_graph_hash,
                "continuity_bible_hash": longform_plan.continuity_bible.continuity_hash,
                "continuity_pressure": longform_plan.continuity_bible.continuity_pressure,
                "identity_bible_snapshot": longform_plan.continuity_bible.source_identity_bible_snapshot,
                "segment_handoff_requirements": longform_plan.metadata.get("segment_handoff_requirements") or [],
                "consistency_policy_action": creative_plan.consistency_plan.get("consistency_policy_action"),
                "consistency_policy_reasons": list(creative_plan.consistency_plan.get("consistency_policy_reasons") or []),
                "long_form_readiness": creative_plan.metadata.get("long_form_readiness") or {},
            },
        )
        return master.model_copy(update={
            "cost_estimate": self.cost_control.estimate_plan_cost(master),
        })


def _segment_prompt(
    *,
    creative_plan: CreativePlan,
    analyzed_input: AnalyzedInput,
    longform_plan: LongFormExecutionPlan,
    segment: SegmentPlan,
) -> str:
    identity = segment.identity_bible_snapshot
    return "\n".join([
        f"Long-form segment {segment.index + 1}/{len(longform_plan.segments)}.",
        f"Subject/setup: {creative_plan.objective or analyzed_input.normalized_idea}",
        f"Segment objective: {segment.objective}",
        f"Entry state: {_compact_state(segment.entry_state)}",
        f"Action: progress this segment clearly toward the exit state without resolving future segments early.",
        f"Exit state: {_compact_state(segment.exit_state)}",
        f"Camera/style: {creative_plan.style_direction}",
        f"Audio intent: {creative_plan.audio_direction}",
        f"Timing: Duration: {segment.duration_s}s",
        f"Continuity pressure: {longform_plan.continuity_bible.continuity_pressure}",
        f"Identity bible snapshot: {_compact_state(identity)}",
        "Last-frame handoff: return a stable last frame for the next segment; preserve character, product, style, and emotion continuity.",
        "Constraints: " + "; ".join(creative_plan.constraints[:8]),
    ])


def _compact_state(value: dict[str, Any]) -> str:
    parts = []
    for key, item in value.items():
        if item in (None, "", [], {}):
            continue
        parts.append(f"{key}={item}")
    return ", ".join(parts) if parts else "none"


def _metadata_asset_refs(analyzed_input: AnalyzedInput) -> list[AssetRef]:
    assets: list[AssetRef] = []
    for item in analyzed_input.metadata.get("assets") or []:
        if isinstance(item, AssetRef):
            assets.append(item)
        elif isinstance(item, dict):
            try:
                assets.append(AssetRef.model_validate(item))
            except ValidationError:
                continue
    return assets


__all__ = ["SegmentPromptCompiler"]
