"""Phase 0 smoke tests for ApprovalLock."""
from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_phase0_approval_lock_detects_matching_plan() -> None:
    """A lock should verify when the approved payload is unchanged."""
    from pipeline.approval_lock import ApprovalLock
    from pipeline.contracts import AssetRef, ReferenceRole, SeedanceExecutionPlan

    asset = AssetRef(
        kind="image",
        url="https://cdn.example.com/product.png",
        tag="@image_1",
        role=ReferenceRole.PRODUCT_HERO,
    )
    plan = SeedanceExecutionPlan(
        model="seedance_2_0",
        duration_s=8,
        compiled_prompt="A clean product hero shot.",
        reference_assets=[asset],
        cost_estimate={"total_usd": 0.25},
    )
    lock = ApprovalLock.from_execution_plan(
        idea="Create a product hero video",
        execution_plan=plan,
        reference_assets=[asset],
        cost_estimate={"total_usd": 0.25},
        approved_by="test",
    )

    result = lock.verify_against(
        idea="Create a product hero video",
        execution_plan=plan,
        reference_assets=[asset],
        cost_estimate={"total_usd": 0.25},
    )

    assert result.valid is True
    assert result.mismatched_fields == []
