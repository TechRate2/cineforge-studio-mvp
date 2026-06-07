"""Policy-driven repair hints for rendered Seedance segments.

The worker already has vendor-level retries. This module provides the production
repair layer above that: it turns deterministic QA failures into concrete prompt
and metadata changes for the next render attempt. It does not mock vendor output
or fabricate scores; it only uses real render/QA reports produced by the current
pipeline.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pipeline.contracts import SeedanceExecutionPlan, SeedanceShotPlan
from workers.render_qa_service import SegmentQAReport
from workers.segment_renderer import SegmentRenderResult


class SegmentRepairPlan(BaseModel):
    """One concrete repair instruction for a failed/warned segment."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "cineforge.segment_repair_plan.v1"
    should_retry: bool = False
    reason: str = ""
    severity: str = "none"
    prompt_addendum: str = ""
    negative_prompt_addendum: str = ""
    rules_applied: list[str] = Field(default_factory=list)
    repair_tags: list[str] = Field(default_factory=list)
    source_warnings: list[str] = Field(default_factory=list)
    source_errors: list[str] = Field(default_factory=list)


def build_segment_repair_plan(
    *,
    shot: SeedanceShotPlan,
    result: SegmentRenderResult,
    qa_report: SegmentQAReport,
    attempt_index: int,
    max_attempts: int,
    previous_last_frame_url: str | None = None,
) -> SegmentRepairPlan:
    """Return the safest next repair for a rendered segment.

    The plan is conservative by design. It never changes references or model
    routing silently; it only strengthens the approved prompt, negative prompt,
    and metadata evidence for the next attempt.
    """
    if attempt_index >= max(0, max_attempts - 1):
        return SegmentRepairPlan(
            should_retry=False,
            reason="repair_budget_exhausted",
            severity="none",
            source_warnings=list(qa_report.warnings),
            source_errors=list(qa_report.errors),
            rules_applied=["segment_repair.budget_guard"],
        )

    warnings = _normalize_tokens([*qa_report.warnings, *qa_report.consistency_warnings])
    errors = _normalize_tokens(qa_report.errors)
    visual = qa_report.visual_consistency
    visual_flags = _normalize_tokens(getattr(visual, "quality_flags", []) if visual is not None else [])
    visual_retries = _normalize_tokens(getattr(visual, "retry_recommendations", []) if visual is not None else [])
    visual_action = str(getattr(visual, "action", "") if visual is not None else "").strip()
    all_tokens = _normalize_tokens([*warnings, *errors, *visual_flags, *visual_retries, visual_action, result.error_code or ""])

    if result.status != "completed" or result.error_code:
        return _vendor_or_transport_repair(
            errors=errors,
            warnings=warnings,
            result=result,
            previous_last_frame_url=previous_last_frame_url,
        )

    if visual_action == "block" or any("below_threshold" in token for token in all_tokens):
        severity = "high"
    elif qa_report.status == "fail" or visual_action == "requires_review":
        severity = "medium"
    elif qa_report.status == "warn" or visual_action == "warn":
        severity = "low"
    else:
        return SegmentRepairPlan(
            should_retry=False,
            reason="qa_passed_no_repair_needed",
            severity="none",
            source_warnings=list(qa_report.warnings),
            source_errors=list(qa_report.errors),
            rules_applied=["segment_repair.noop_when_passed"],
        )

    repair_tags: list[str] = []
    addenda: list[str] = []
    negatives: list[str] = []

    if _matches(all_tokens, "face", "identity", "character", "rendered_character_face_not_detected"):
        repair_tags.append("identity_repair")
        addenda.extend([
            "Keep the same character identity from the approved references and identity bible; do not change face, hair, age, skin tone, outfit, or body proportions.",
            "Use a clearer medium close-up or stable three-quarter framing so the face remains visible for identity QA.",
            "Reduce rapid pans, whip motion, heavy blur, and extreme occlusion around the face.",
        ])
        negatives.extend(["no face morphing", "no new random face", "no outfit drift", "no heavy face blur"])

    if _matches(all_tokens, "product", "logo", "label", "brand", "ocr"):
        repair_tags.append("product_repair")
        addenda.extend([
            "Make the hero product visibly larger in frame, cleanly lit, and unobstructed for at least one continuous beat.",
            "Preserve exact packaging geometry, colors, logo placement, and label layout from the approved product/brand reference.",
            "Use a cleaner background and slower product motion; avoid rotations that hide the label.",
        ])
        negatives.extend(["no product redesign", "no logo drift", "no unreadable fake label", "no tiny product"])

    if _matches(all_tokens, "style", "temporal", "lighting", "color", "flicker", "palette"):
        repair_tags.append("style_repair")
        addenda.extend([
            "Preserve the same color grade, light direction, contrast, lens feel, and material texture throughout the entire segment.",
            "Avoid random scene resets, exposure flicker, and sudden art-style changes between beats.",
        ])
        negatives.extend(["no lighting flicker", "no style reset", "no random color grade shift"])

    if _matches(all_tokens, "emotion", "performance", "micro", "expression"):
        repair_tags.append("emotion_repair")
        addenda.extend([
            "Carry the exact emotional state from entry to exit; show it through restrained facial expression, breathing, and body posture.",
            "Do not overact or jump to the next scene's emotional payoff early.",
        ])
        negatives.extend(["no exaggerated robotic acting", "no emotion reset"])

    if _matches(all_tokens, "handoff", "last_frame", "first_frame", "continuity") or previous_last_frame_url:
        repair_tags.append("handoff_repair")
        addenda.extend([
            "Start by matching the previous segment's final frame state: same subject placement, outfit, product/location layout, lighting, and camera distance.",
            "End with a stable final frame that can be reused as the next segment's continuity anchor.",
        ])
        negatives.extend(["no abrupt cutaway at final frame", "no new location without setup"])

    if _matches(all_tokens, "duration", "missing_duration", "decodable", "frame", "probe"):
        repair_tags.append("technical_visibility_repair")
        addenda.extend([
            "Keep the action physically simple and readable for the selected duration; one primary action only.",
            "Hold the key subject visibly long enough for post-render QA sampling.",
        ])
        negatives.extend(["no overloaded montage", "no frozen or black frames"])

    if not addenda:
        repair_tags.append("generic_visual_repair")
        addenda.extend([
            "Simplify the segment to one clear, physically filmable action that matches the approved prompt and references.",
            "Keep subject, product, camera, lighting, and style stable; do not introduce unplanned characters, props, logos, or locations.",
        ])
        negatives.extend(["no prompt mismatch", "no visual drift", "no watermark"])

    reason = _first_nonempty([
        *_normalize_tokens(errors),
        *_normalize_tokens(warnings),
        *_normalize_tokens(visual_flags),
        visual_action,
        "qa_repair_required",
    ])
    return SegmentRepairPlan(
        should_retry=True,
        reason=reason,
        severity=severity,
        prompt_addendum="\n".join(_dedupe(addenda))[:1600],
        negative_prompt_addendum=", ".join(_dedupe(negatives))[:500],
        repair_tags=_dedupe(repair_tags),
        source_warnings=list(qa_report.warnings),
        source_errors=list(qa_report.errors),
        rules_applied=[
            "segment_repair.qa_to_prompt_policy",
            "segment_repair.preserve_approval_lock_scope",
            "segment_repair.no_reference_or_model_swap_without_user_approval",
        ],
    )


def apply_segment_repair(
    *,
    execution_plan: SeedanceExecutionPlan,
    shot: SeedanceShotPlan,
    repair_plan: SegmentRepairPlan,
    repair_attempt: int,
) -> tuple[SeedanceExecutionPlan, SeedanceShotPlan]:
    """Return repaired copies of the execution plan and shot.

    The ApprovalLock remains valid because this function is used only inside the
    already-approved render job after a failed output, and the repair is stored
    in render metadata/history. It does not mutate references, cost cap, or model
    choice.
    """
    if not repair_plan.should_retry:
        return execution_plan, shot
    prompt = _append_section(
        shot.compiled_prompt,
        "AUTO-REPAIR INSTRUCTIONS",
        repair_plan.prompt_addendum,
    )
    negative_prompt = _append_negative(shot.negative_prompt, repair_plan.negative_prompt_addendum)
    metadata = {
        **shot.metadata,
        "auto_repair": {
            "schema_version": repair_plan.schema_version,
            "attempt": repair_attempt,
            "reason": repair_plan.reason,
            "severity": repair_plan.severity,
            "repair_tags": repair_plan.repair_tags,
            "source_warnings": repair_plan.source_warnings,
            "source_errors": repair_plan.source_errors,
        },
    }
    repaired_shot = shot.model_copy(update={
        "compiled_prompt": prompt,
        "negative_prompt": negative_prompt,
        "metadata": metadata,
        "rules_applied": _dedupe([*shot.rules_applied, *repair_plan.rules_applied]),
        "linter_warnings": _dedupe([*shot.linter_warnings, f"auto_repair:{repair_plan.reason}"]),
    })
    repaired_shots = [
        repaired_shot if item.shot_id == shot.shot_id else item
        for item in execution_plan.shots
    ]
    repaired_plan = execution_plan.model_copy(update={
        "shots": repaired_shots,
        "compiled_prompt": _append_section(
            execution_plan.compiled_prompt,
            f"AUTO-REPAIR FOR {shot.shot_id}",
            repair_plan.prompt_addendum,
        ),
        "metadata": {
            **execution_plan.metadata,
            "auto_repair_last": {
                "shot_id": shot.shot_id,
                "attempt": repair_attempt,
                "reason": repair_plan.reason,
                "repair_tags": repair_plan.repair_tags,
            },
        },
        "rules_applied": _dedupe([*execution_plan.rules_applied, *repair_plan.rules_applied]),
    })
    return repaired_plan, repaired_shot


def _vendor_or_transport_repair(
    *,
    errors: list[str],
    warnings: list[str],
    result: SegmentRenderResult,
    previous_last_frame_url: str | None,
) -> SegmentRepairPlan:
    code = str(result.error_code or "vendor_render_error")
    addenda = [
        "Re-render the same approved segment with simpler, physically filmable action and stable subject framing.",
        "Do not add new scenes, characters, products, or style changes while recovering from the failed render attempt.",
    ]
    if previous_last_frame_url:
        addenda.append("Preserve the previous last-frame continuity anchor when retrying this segment.")
    return SegmentRepairPlan(
        should_retry=code in {"vendor_rate_limited", "vendor_timeout", "vendor_render_error", "vendor_invalid_request"},
        reason=code,
        severity="medium",
        prompt_addendum="\n".join(addenda),
        negative_prompt_addendum="no overloaded action, no prompt conflict, no unsupported reference swap",
        repair_tags=["vendor_recovery"],
        source_warnings=warnings,
        source_errors=errors or [code],
        rules_applied=["segment_repair.vendor_recovery_policy"],
    )


def _append_section(base: str, title: str, text: str) -> str:
    body = str(text or "").strip()
    if not body:
        return base
    base_text = str(base or "").strip()
    section = f"{title}:\n{body}"
    if section in base_text:
        return base_text
    return f"{base_text}\n\n{section}".strip()


def _append_negative(base: str, extra: str) -> str:
    values = _dedupe([
        *[part.strip() for part in str(base or "").split(",") if part.strip()],
        *[part.strip() for part in str(extra or "").split(",") if part.strip()],
    ])
    return ", ".join(values)


def _matches(tokens: list[str], *needles: str) -> bool:
    haystack = " ".join(tokens).lower()
    return any(needle.lower() in haystack for needle in needles)


def _normalize_tokens(values: list[Any]) -> list[str]:
    return [str(item).strip() for item in values if str(item or "").strip()]


def _first_nonempty(values: list[str]) -> str:
    for value in values:
        if str(value).strip():
            return str(value).strip()[:160]
    return "qa_repair_required"


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


__all__ = [
    "SegmentRepairPlan",
    "apply_segment_repair",
    "build_segment_repair_plan",
]
