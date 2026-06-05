"""Compile Phase 9A long-form segments into Seedance execution plans."""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from longform.contracts import LongFormExecutionPlan, SegmentPlan
from pipeline.contracts import AnalyzedInput, AssetRef, CreativePlan, SeedanceExecutionPlan, SeedanceShotPlan
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
                "phase10.longform_prompt.seedance_formula_blocks",
                "phase10.longform_prompt.continuity_handoff_contract",
                "phase10.longform_prompt.post_render_qa_contract",
            ])),
            "metadata": {
                **longform_plan.metadata,
                "master_execution_plan_id": master_plan.execution_plan_id,
                "segment_graph_hash": longform_plan.segment_graph_hash,
                "continuity_bible_hash": longform_plan.continuity_bible.continuity_hash,
                "segment_prompt_method": "seedance_formula_blocks_with_entry_exit_handoff",
                "post_render_qa_required": True,
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
        selected_strategy = _selected_strategy(creative_plan)
        qa_contract = _post_render_qa_probe_contract(
            creative_plan=creative_plan,
            segment=segment,
            treatment_id=str(selected_strategy.get("strategy_id") or selected_strategy.get("treatment_id") or ""),
        )
        shot = SeedanceShotPlan(
            shot_id=f"{segment.segment_id}_shot_0",
            index=0,
            duration_s=segment.duration_s,
            compiled_prompt=_segment_prompt(
                creative_plan=creative_plan,
                analyzed_input=analyzed_input,
                longform_plan=longform_plan,
                segment=segment,
                reference_assets=reference_assets,
            ),
            negative_prompt=(
                "no subtitles, no watermark, no random new faces, no identity drift, "
                "no outfit drift, no product drift, no style reset, no fake unreadable text, "
                "no extra logos not present in confirmed references"
            ),
            model=str(creative_plan.metadata.get("model") or "seedance_2_0"),
            aspect_ratio=creative_plan.aspect_ratio,
            resolution=str(creative_plan.metadata.get("resolution") or "1080p"),
            references=reference_assets,
            rules_applied=[
                "phase9a.segment_prompt.entry_exit_state",
                "phase9a.segment_prompt.identity_bible_snapshot",
                "phase9a.segment_prompt.last_frame_handoff",
                "phase10.segment_prompt.seedance_formula_blocks",
                "phase10.segment_prompt.single_action_unit",
                "phase10.segment_prompt.qa_probe_contract",
            ],
            metadata={
                "longform_plan_id": longform_plan.longform_plan_id,
                "segment_id": segment.segment_id,
                "segment_index": segment.index,
                "segment_position": _segment_position(segment.index, len(longform_plan.segments)),
                "entry_state": segment.entry_state,
                "exit_state": segment.exit_state,
                "last_frame_anchor": segment.last_frame_anchor,
                "identity_bible_snapshot": segment.identity_bible_snapshot,
                "handoff_requirements": segment.handoff_requirements,
                "continuity_bible_hash": longform_plan.continuity_bible.continuity_hash,
                "segment_graph_hash": longform_plan.segment_graph_hash,
                "creative_strategy_id": selected_strategy.get("strategy_id") or selected_strategy.get("treatment_id"),
                "creative_strategy_label": selected_strategy.get("label"),
                "needs_identity_consistency": bool(creative_plan.consistency_plan.get("character_lock")),
                "needs_product_consistency": bool(creative_plan.consistency_plan.get("product_lock")),
                "needs_style_consistency": True,
                "needs_emotion_consistency": bool(_is_emotional_longform(creative_plan=creative_plan, treatment_id=qa_contract["treatment_id"])),
                "consistency_score": creative_plan.consistency_plan.get("consistency_score"),
                "consistency_policy_action": creative_plan.consistency_plan.get("consistency_policy_action"),
                "consistency_policy_reasons": list(creative_plan.consistency_plan.get("consistency_policy_reasons") or []),
                "consistency_risk_flags": list(creative_plan.consistency_plan.get("consistency_risk_flags") or []),
                "post_render_qa_probe_contract": qa_contract,
                "longform_handoff_policy": {
                    "previous_segment_id": f"segment_{segment.index:02d}" if segment.index > 0 else None,
                    "next_segment_id": f"segment_{segment.index + 2:02d}" if segment.index + 1 < len(longform_plan.segments) else None,
                    "first_frame_rule": _first_frame_rule(segment),
                    "last_frame_rule": _last_frame_rule(segment, len(longform_plan.segments)),
                },
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
                "segment_position": _segment_position(segment.index, len(longform_plan.segments)),
                "segment_graph_hash": longform_plan.segment_graph_hash,
                "continuity_bible_hash": longform_plan.continuity_bible.continuity_hash,
                "approved_idea": analyzed_input.normalized_idea,
                "long_form_readiness": creative_plan.metadata.get("long_form_readiness") or {},
                "continuity_pressure": longform_plan.continuity_bible.continuity_pressure,
                "post_render_qa_probe_contract": qa_contract,
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
                "phase10.master_execution_plan.post_render_qa_rollup",
                "phase10.master_execution_plan.handoff_frame_contract",
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
                "post_render_qa_probe_contract": _post_render_qa_probe_contract(
                    creative_plan=creative_plan,
                    segment=None,
                    treatment_id=str((_selected_strategy(creative_plan).get("strategy_id") or "")),
                ),
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
    reference_assets: list[AssetRef],
) -> str:
    """Build a production Seedance prompt for one long-form segment."""
    identity = segment.identity_bible_snapshot
    segment_count = len(longform_plan.segments)
    selected_strategy = _selected_strategy(creative_plan)
    constraints = _dedupe_strings([
        *_listify(creative_plan.constraints),
        "one continuous Seedance unit, not a trailer montage",
        "do not reset character, outfit, product, location, lighting, color grade, or emotional state",
        "no subtitles or watermark; keep any product label readable only when it exists in references",
        "finish on a stable handoff frame with subject/product/location clearly visible",
    ])
    blocks = [
        f"LONG-FORM SEEDANCE SEGMENT {segment.index + 1}/{segment_count} — {segment.duration_s}s.",
        f"Series objective: {_safe_text(creative_plan.objective or analyzed_input.normalized_idea, 360)}",
        f"Director treatment: {_safe_text(selected_strategy.get('label') or selected_strategy.get('strategy_id') or 'autonomous continuity route', 160)}",
        f"Segment position: {_segment_position(segment.index, segment_count)}.",
        "",
        "Reference jobs:",
        _reference_job_block(reference_assets=reference_assets, segment=segment),
        "",
        "Timeline beat:",
        f"- Entry state at frame 0: {_compact_state(segment.entry_state)}",
        f"- Segment objective: {_safe_text(segment.objective, 360)}",
        "- Action: progress this objective clearly, with one readable cause-and-effect action; do not resolve future segments early.",
        f"- Exit state by final second: {_compact_state(segment.exit_state)}",
        "",
        "Camera and composition:",
        f"- Style direction: {_safe_text(creative_plan.style_direction, 260)}",
        f"- Continuity camera rule: {_continuity_camera_rule(segment=segment, segment_count=segment_count)}",
        "- Keep framing stable enough for post-render identity/product probes to see the subject.",
        "",
        "Lighting, color, texture:",
        f"- Continuity pressure: {longform_plan.continuity_bible.continuity_pressure}",
        "- Preserve the same light direction, grade, material texture, and environment geography from the continuity bible.",
        "",
        "Sound and performance:",
        f"- Audio intent: {_safe_text(creative_plan.audio_direction, 220)}",
        "- If dialogue or VO is implied, make performance natural and timed to visible emotion; do not invent unsupported lip-sync identities.",
        "",
        "Continuity handoff:",
        _continuity_bridge_block(segment=segment, segment_count=segment_count),
        "",
        f"Identity bible snapshot: {_compact_state(identity)}",
        "Constraints:",
        "; ".join(constraints[:10]),
    ]
    return "\n".join(block for block in blocks if block is not None)


def _reference_job_block(*, reference_assets: list[AssetRef], segment: SegmentPlan) -> str:
    if not reference_assets:
        return "- No confirmed visual reference asset is attached; rely on identity bible and keep design simple for manual review."
    lines = []
    for index, asset in enumerate(reference_assets[:9], start=1):
        role = _asset_value(asset, "role") or _asset_value(asset, "kind") or "reference"
        name = _asset_value(asset, "name") or _asset_value(asset, "asset_id") or f"ref_{index}"
        lines.append(f"- @{index}: {role} — preserve {name} when visible; never swap its job.")
    if segment.index > 0:
        lines.append("- Previous segment last-frame anchor is the first-frame continuity source; match it before moving the scene forward.")
    return "\n".join(lines)


def _continuity_bridge_block(*, segment: SegmentPlan, segment_count: int) -> str:
    first_rule = _first_frame_rule(segment)
    last_rule = _last_frame_rule(segment, segment_count)
    requirements = "; ".join(_dedupe_strings(_listify(segment.handoff_requirements))[:8])
    return "\n".join([
        f"- First-frame rule: {first_rule}",
        f"- Last-frame rule: {last_rule}",
        f"- Handoff requirements: {requirements or 'preserve character, product, style, emotion and scene state'}",
    ])


def _first_frame_rule(segment: SegmentPlan) -> str:
    if segment.index == 0:
        return "establish the opening state clearly and capture a reusable final frame for segment 2"
    return "start by matching previous segment final frame: same subject pose family, outfit, product placement, location layout, and lighting"


def _last_frame_rule(segment: SegmentPlan, segment_count: int) -> str:
    if segment.index + 1 >= segment_count:
        return "hold a clean final payoff frame for assembly; no abrupt style shift or random new subject"
    return "hold a stable, readable bridge frame in the final second for the next segment to inherit"


def _continuity_camera_rule(*, segment: SegmentPlan, segment_count: int) -> str:
    if segment.index == 0:
        return "start with a clear establishing frame, then move into the segment action"
    if segment.index + 1 >= segment_count:
        return "keep camera motivated and settle into a final hero/payoff frame"
    return "begin close enough to inherit previous frame, then use one motivated movement toward the exit state"


def _post_render_qa_probe_contract(
    *,
    creative_plan: CreativePlan,
    segment: SegmentPlan | None,
    treatment_id: str,
) -> dict[str, Any]:
    required = ["style_similarity"]
    if creative_plan.consistency_plan.get("character_lock") or treatment_id in {"short_drama_arc", "documentary_testimonial"}:
        required.append("face_similarity")
        required.append("emotion_similarity")
    if creative_plan.consistency_plan.get("product_lock") or treatment_id in {"proof_first_ugc", "cinematic_premium"}:
        required.append("product_visibility")
        required.append("logo_label_similarity")
    if segment is not None and segment.index > 0:
        required.append("handoff_frame_stability")
    return {
        "schema_version": "cineforge.post_render_qa_probe_contract.v1",
        "treatment_id": treatment_id or "unknown",
        "required_signals": _dedupe_strings(required),
        "minimum_signal_confidence": 0.35,
        "strict_low_confidence_threshold": 0.18,
        "missing_required_signal_action": "requires_review",
        "block_on": ["face_similarity_below_block_threshold", "product_visibility_below_block_threshold"],
        "retry_recommendation_required": True,
    }


def _selected_strategy(creative_plan: CreativePlan) -> dict[str, Any]:
    strategy = creative_plan.metadata.get("creative_strategy")
    if isinstance(strategy, dict):
        selected = strategy.get("selected_strategy")
        if isinstance(selected, dict):
            return dict(selected)
    treatment = creative_plan.metadata.get("selected_creative_treatment")
    if isinstance(treatment, dict):
        return dict(treatment)
    return {}


def _is_emotional_longform(*, creative_plan: CreativePlan, treatment_id: str) -> bool:
    text = " ".join([
        treatment_id,
        str(creative_plan.target_niche),
        str(creative_plan.objective),
        " ".join(_listify(creative_plan.narrative_arc)),
    ]).lower()
    return any(token in text for token in ("drama", "story", "film", "emotion", "testimonial", "documentary"))


def _segment_position(index: int, count: int) -> str:
    if index == 0:
        return "opening"
    if index + 1 >= count:
        return "finale"
    return "middle_bridge"


def _compact_state(value: dict[str, Any]) -> str:
    parts = []
    for key, item in value.items():
        if item in (None, "", [], {}):
            continue
        parts.append(f"{key}={_safe_text(item, 160)}")
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


def _asset_value(asset: AssetRef, field_name: str) -> str:
    value = getattr(asset, field_name, None)
    if value is None and hasattr(asset, "model_dump"):
        value = asset.model_dump(mode="json").get(field_name)
    return str(value or "").strip()


def _listify(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)] if str(value).strip() else []


def _dedupe_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _safe_text(value: Any, cap: int) -> str:
    text = str(value or "").replace("\n", " ").strip()
    return text[:cap] if len(text) > cap else text


__all__ = ["SegmentPromptCompiler"]
