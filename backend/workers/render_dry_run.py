"""Dry-run reporting for paid Seedance render execution.

Dry-run is the required preview layer before paid render. It exposes the exact
payload shape, prompts, references, reference intelligence, cost estimate, and
knowledge provenance that would be used by AtlasCloud/Seedance without
submitting a vendor request.
"""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent.reference_intelligence import ReferenceIntelligenceService
from pipeline.approval_lock import ApprovalLock, ApprovalLockVerification
from pipeline.contracts import AssetRef, SeedanceExecutionPlan, SeedanceShotPlan

logger = logging.getLogger(__name__)


class ShotDryRunPayload(BaseModel):
    """One shot payload preview for AtlasCloud/Seedance."""

    model_config = ConfigDict(extra="forbid")

    shot_id: str
    index: int
    payload: dict[str, Any]
    prompt: str
    references: list[dict[str, Any]] = Field(default_factory=list)
    knowledge_rule_ids: list[str] = Field(default_factory=list)
    curated_example_ids: list[str] = Field(default_factory=list)


class RenderDryRunReport(BaseModel):
    """Complete dry-run report shown before any paid render is submitted."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "cineforge.render_dry_run_report.v1"
    execution_plan_id: str
    approval_lock_id: str
    approval_valid: bool
    approval_verification: ApprovalLockVerification | None = None
    model: str
    duration_s: int
    aspect_ratio: str
    resolution: str
    cost_estimate: dict[str, Any] = Field(default_factory=dict)
    shot_payloads: list[ShotDryRunPayload] = Field(default_factory=list)
    references: list[dict[str, Any]] = Field(default_factory=list)
    reference_intelligence: dict[str, Any] = Field(default_factory=dict)
    knowledge_rule_ids: list[str] = Field(default_factory=list)
    curated_example_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    hard_failures: list[str] = Field(default_factory=list)


class RenderDryRunService:
    """Generate deterministic reports for render approval review."""

    def __init__(self, *, reference_intelligence: ReferenceIntelligenceService | None = None) -> None:
        self.reference_intelligence = reference_intelligence or ReferenceIntelligenceService()

    def generate_dry_run_report(
        self,
        execution_plan: SeedanceExecutionPlan,
        approval_lock: ApprovalLock,
        approval_verification: ApprovalLockVerification | None = None,
    ) -> RenderDryRunReport:
        """Return a full dry-run report for the supplied execution plan."""
        verification = approval_verification or ApprovalLockVerification(valid=True)
        shots = execution_plan.shots or [_plan_as_single_shot(execution_plan)]
        references = _all_references(execution_plan)
        reference_report = self.reference_intelligence.analyze(
            assets=references,
            needs_character_lock=_needs_character_lock(execution_plan),
            needs_product_lock=_needs_product_lock(execution_plan),
        )
        logger.info(
            "render_dry_run_report_started",
            extra={
                "execution_plan_id": execution_plan.execution_plan_id,
                "approval_lock_id": approval_lock.lock_id,
                "shot_count": len(shots),
                "approval_valid": verification.valid,
                "reference_intelligence_status": reference_report.status,
            },
        )
        shot_payloads = [
            ShotDryRunPayload(
                shot_id=shot.shot_id,
                index=shot.index,
                payload=build_seedance_payload(
                    execution_plan=execution_plan,
                    shot=shot,
                    previous_last_frame_url=None,
                ),
                prompt=shot.compiled_prompt,
                references=[_asset_payload(asset) for asset in shot.references],
                knowledge_rule_ids=_dedupe(execution_plan.rules_applied + shot.rules_applied),
                curated_example_ids=_dedupe(execution_plan.examples_used + shot.examples_used),
            )
            for shot in shots
        ]
        report = RenderDryRunReport(
            execution_plan_id=execution_plan.execution_plan_id,
            approval_lock_id=approval_lock.lock_id,
            approval_valid=verification.valid,
            approval_verification=verification,
            model=execution_plan.model,
            duration_s=execution_plan.duration_s,
            aspect_ratio=execution_plan.aspect_ratio,
            resolution=execution_plan.resolution,
            cost_estimate=dict(execution_plan.cost_estimate),
            shot_payloads=shot_payloads,
            references=[_asset_payload(asset) for asset in references],
            reference_intelligence=reference_report.model_dump(mode="json"),
            knowledge_rule_ids=_dedupe(
                execution_plan.rules_applied
                + [rule for shot in shots for rule in shot.rules_applied]
                + list(execution_plan.metadata.get("knowledge_rule_ids") or [])
                + reference_report.rules_applied
            ),
            curated_example_ids=_dedupe(
                execution_plan.examples_used
                + [example for shot in shots for example in shot.examples_used]
                + list(execution_plan.metadata.get("curated_example_ids") or [])
            ),
            warnings=_dedupe(
                list(execution_plan.linter_warnings)
                + _consistency_policy_warnings(execution_plan)
                + reference_report.warnings
            ),
            hard_failures=_dedupe(reference_report.blockers),
        )
        logger.info(
            "render_dry_run_report_completed",
            extra={
                "execution_plan_id": execution_plan.execution_plan_id,
                "approval_lock_id": approval_lock.lock_id,
                "shot_payload_count": len(report.shot_payloads),
                "warning_count": len(report.warnings),
                "hard_failure_count": len(report.hard_failures),
                "knowledge_rule_count": len(report.knowledge_rule_ids),
                "curated_example_count": len(report.curated_example_ids),
            },
        )
        return report


def build_seedance_payload(
    *,
    execution_plan: SeedanceExecutionPlan,
    shot: SeedanceShotPlan,
    previous_last_frame_url: str | None = None,
) -> dict[str, Any]:
    """Build the AtlasCloud/Seedance video payload for one shot."""
    image_refs = [asset.url for asset in shot.references if asset.kind == "image" and asset.url]
    video_refs = [asset.url for asset in shot.references if asset.kind == "video" and asset.url]
    audio_refs = [asset.url for asset in shot.references if asset.kind == "audio" and asset.url]
    payload: dict[str, Any] = {
        "model_key": shot.model if shot.model != "auto" else execution_plan.model,
        "prompt": shot.compiled_prompt,
        "duration_s": shot.duration_s,
        "resolution": shot.resolution or execution_plan.resolution,
        "aspect_ratio": shot.aspect_ratio or execution_plan.aspect_ratio,
        "negative_prompt": shot.negative_prompt or None,
        "images": image_refs or None,
        "reference_videos": video_refs or None,
        "reference_audios": audio_refs or None,
        "return_last_frame": True,
    }
    if previous_last_frame_url:
        payload["image"] = previous_last_frame_url
        payload["images"] = [previous_last_frame_url]
    return {key: value for key, value in payload.items() if value not in (None, [], "")}


def _consistency_policy_warnings(execution_plan: SeedanceExecutionPlan) -> list[str]:
    action = str(execution_plan.metadata.get("consistency_policy_action") or "").strip()
    reasons = [str(item) for item in execution_plan.metadata.get("consistency_policy_reasons") or []]
    policy = execution_plan.metadata.get("consistency_policy") or {}
    if isinstance(policy, dict):
        action = action or str(policy.get("action") or "").strip()
        reasons.extend(str(item) for item in policy.get("reason_ids") or [])
    if action in {"requires_review", "block"}:
        return [f"consistency_policy.{action}: " + ", ".join(_dedupe(reasons))]
    return []


def _needs_character_lock(execution_plan: SeedanceExecutionPlan) -> bool:
    if bool(execution_plan.metadata.get("needs_identity_consistency")):
        return True
    consistency_plan = execution_plan.metadata.get("consistency_plan")
    if isinstance(consistency_plan, dict) and bool(consistency_plan.get("character_lock")):
        return True
    return any(bool(shot.metadata.get("needs_identity_consistency")) for shot in execution_plan.shots)


def _needs_product_lock(execution_plan: SeedanceExecutionPlan) -> bool:
    if bool(execution_plan.metadata.get("needs_product_consistency")):
        return True
    consistency_plan = execution_plan.metadata.get("consistency_plan")
    if isinstance(consistency_plan, dict) and bool(consistency_plan.get("product_lock")):
        return True
    return any(bool(shot.metadata.get("needs_product_consistency")) for shot in execution_plan.shots)


def _plan_as_single_shot(execution_plan: SeedanceExecutionPlan) -> SeedanceShotPlan:
    return SeedanceShotPlan(
        shot_id=f"{execution_plan.execution_plan_id}_shot_0",
        index=0,
        duration_s=execution_plan.duration_s,
        compiled_prompt=execution_plan.compiled_prompt,
        model=execution_plan.model,
        aspect_ratio=execution_plan.aspect_ratio,
        resolution=execution_plan.resolution,
        references=execution_plan.reference_assets,
        rules_applied=execution_plan.rules_applied,
        examples_used=execution_plan.examples_used,
        linter_warnings=execution_plan.linter_warnings,
    )


def _all_references(execution_plan: SeedanceExecutionPlan) -> list[AssetRef]:
    refs = list(execution_plan.reference_assets)
    for shot in execution_plan.shots:
        refs.extend(shot.references)
    seen: set[str] = set()
    out: list[AssetRef] = []
    for asset in refs:
        key = asset.asset_id or asset.url or str(asset.tag or "")
        if key in seen:
            continue
        seen.add(key)
        out.append(asset)
    return out


def _asset_payload(asset: AssetRef) -> dict[str, Any]:
    return {
        "asset_id": asset.asset_id,
        "kind": asset.kind,
        "url": asset.url,
        "tag": asset.tag,
        "role": asset.role.value,
        "name": asset.name,
    }


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value).strip()))


__all__ = [
    "RenderDryRunReport",
    "RenderDryRunService",
    "ShotDryRunPayload",
    "build_seedance_payload",
]
