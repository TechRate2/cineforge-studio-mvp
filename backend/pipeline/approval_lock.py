"""Approval lock for protecting paid render execution.

ApprovalLock is created only after the user approves the Storyboard or Prompt
Preview. Phase 0 defines the contract and verification mechanics; Phase 3 will
enforce this lock before any paid Seedance render call.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from pipeline.contracts import AssetRef, SeedanceExecutionPlan, canonical_hash, utc_now


HASH_FIELDS = (
    "idea_hash",
    "reference_urls_hash",
    "asset_roles_hash",
    "model_hash",
    "aspect_ratio_hash",
    "resolution_hash",
    "duration_hash",
    "compiled_prompt_hash",
    "execution_plan_hash",
    "cost_estimate_hash",
)


class ApprovalLockVerification(BaseModel):
    """Result returned by ApprovalLock.verify_against."""

    model_config = ConfigDict(extra="forbid")

    valid: bool
    mismatched_fields: list[str] = Field(default_factory=list)
    expected_hashes: dict[str, str] = Field(default_factory=dict)
    actual_hashes: dict[str, str] = Field(default_factory=dict)


class ApprovalLock(BaseModel):
    """Immutable approval snapshot for a compiled Seedance execution plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "cineforge.approval_lock.v1"
    lock_id: str = Field(default_factory=lambda: f"approval_{uuid4().hex[:12]}")
    idea_hash: str
    reference_urls_hash: str
    asset_roles_hash: str
    model_hash: str
    aspect_ratio_hash: str
    resolution_hash: str
    duration_hash: str
    compiled_prompt_hash: str
    execution_plan_hash: str
    cost_estimate_hash: str
    model: str = "auto"
    aspect_ratio: str = "9:16"
    resolution: str = "1080p"
    duration_s: int = Field(..., ge=1)
    user_approval_timestamp: datetime = Field(default_factory=utc_now)
    approved_by: str = "unknown"
    approval_source: str = Field(
        "prompt_preview",
        description="Expected values include storyboard, prompt_preview, dry_run_preview.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_execution_plan(
        cls,
        *,
        idea: str,
        execution_plan: SeedanceExecutionPlan | Mapping[str, Any],
        reference_assets: Sequence[AssetRef | Mapping[str, Any]] | None = None,
        cost_estimate: Mapping[str, Any] | None = None,
        approved_by: str = "unknown",
        approval_source: str = "prompt_preview",
        user_approval_timestamp: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ApprovalLock":
        """Create a lock from the exact plan the user approved."""
        plan_data = _as_mapping(execution_plan)
        assets = list(
            reference_assets
            if reference_assets is not None
            else _extract_reference_assets(plan_data)
        )
        model = str(plan_data.get("model") or "auto")
        aspect_ratio = str(plan_data.get("aspect_ratio") or "9:16")
        resolution = str(plan_data.get("resolution") or "1080p")
        duration_s = int(plan_data.get("duration_s") or _sum_shot_durations(plan_data) or 1)
        compiled_prompt = _compiled_prompt(plan_data)
        effective_cost = dict(
            cost_estimate
            if cost_estimate is not None
            else plan_data.get("cost_estimate") or {}
        )

        return cls(
            idea_hash=canonical_hash((idea or "").strip()),
            reference_urls_hash=canonical_hash(_reference_urls(assets)),
            asset_roles_hash=canonical_hash(_asset_roles(assets)),
            model_hash=canonical_hash(model),
            aspect_ratio_hash=canonical_hash(aspect_ratio),
            resolution_hash=canonical_hash(resolution),
            duration_hash=canonical_hash(duration_s),
            compiled_prompt_hash=canonical_hash(compiled_prompt),
            execution_plan_hash=canonical_hash(plan_data),
            cost_estimate_hash=canonical_hash(effective_cost),
            model=model,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            duration_s=duration_s,
            user_approval_timestamp=user_approval_timestamp or utc_now(),
            approved_by=approved_by,
            approval_source=approval_source,
            metadata=metadata or {},
        )

    def verify_against(
        self,
        *,
        idea: str,
        execution_plan: SeedanceExecutionPlan | Mapping[str, Any],
        reference_assets: Sequence[AssetRef | Mapping[str, Any]] | None = None,
        cost_estimate: Mapping[str, Any] | None = None,
    ) -> ApprovalLockVerification:
        """Verify that the current render candidate matches this approval."""
        candidate = self.from_execution_plan(
            idea=idea,
            execution_plan=execution_plan,
            reference_assets=reference_assets,
            cost_estimate=cost_estimate,
            approved_by=self.approved_by,
            approval_source=self.approval_source,
            metadata=self.metadata,
        )
        expected = {field: str(getattr(self, field)) for field in HASH_FIELDS}
        actual = {field: str(getattr(candidate, field)) for field in HASH_FIELDS}
        mismatches = [
            field
            for field in HASH_FIELDS
            if expected[field] != actual[field]
        ]
        return ApprovalLockVerification(
            valid=not mismatches,
            mismatched_fields=mismatches,
            expected_hashes=expected,
            actual_hashes=actual,
        )


def _as_mapping(value: SeedanceExecutionPlan | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    return dict(value)


def _extract_reference_assets(plan_data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    assets = list(plan_data.get("reference_assets") or [])
    for shot in plan_data.get("shots") or []:
        if isinstance(shot, Mapping):
            assets.extend(shot.get("references") or [])
    return assets


def _reference_urls(assets: Sequence[AssetRef | Mapping[str, Any]]) -> list[str]:
    urls: list[str] = []
    for asset in assets:
        data = _asset_mapping(asset)
        url = str(data.get("url") or "").strip()
        if url:
            urls.append(url)
    return sorted(dict.fromkeys(urls))


def _asset_roles(assets: Sequence[AssetRef | Mapping[str, Any]]) -> list[dict[str, str]]:
    roles: list[dict[str, str]] = []
    for asset in assets:
        data = _asset_mapping(asset)
        key = str(data.get("asset_id") or data.get("tag") or data.get("url") or "").strip()
        if not key:
            continue
        roles.append({
            "key": key,
            "kind": str(data.get("kind") or ""),
            "role": str(data.get("role") or ""),
            "tag": str(data.get("tag") or ""),
        })
    return sorted(roles, key=lambda row: (row["key"], row["kind"], row["role"], row["tag"]))


def _asset_mapping(asset: AssetRef | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(asset, BaseModel):
        return asset.model_dump(mode="json", exclude_none=True)
    return dict(asset)


def _compiled_prompt(plan_data: Mapping[str, Any]) -> str:
    plan_prompt = str(plan_data.get("compiled_prompt") or "").strip()
    shot_prompts = [
        str(shot.get("compiled_prompt") or "").strip()
        for shot in plan_data.get("shots") or []
        if isinstance(shot, Mapping) and str(shot.get("compiled_prompt") or "").strip()
    ]
    return "\n\n".join([part for part in [plan_prompt, *shot_prompts] if part])


def _sum_shot_durations(plan_data: Mapping[str, Any]) -> int:
    total = 0
    for shot in plan_data.get("shots") or []:
        if isinstance(shot, Mapping):
            total += int(shot.get("duration_s") or 0)
    return total


__all__ = ["ApprovalLock", "ApprovalLockVerification"]
