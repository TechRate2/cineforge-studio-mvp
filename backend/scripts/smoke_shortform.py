"""Safe short-form smoke test for CineForge Studio.

Default mode is dry-run only and performs no paid vendor call.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from pipeline.approval_lock import ApprovalLock
from pipeline.contracts import AssetRef, InputContract, ReferenceRole
from pipeline.creative_planning import CreativePlanner
from pipeline.input_analysis import InputAnalyzer
from pipeline.render_execution import RenderExecutor
from pipeline.storyboard_generation import StoryboardGenerator
from seedance.prompt_compiler import SeedancePromptCompiler

from smoke_common import missing_env_payload, missing_vendor_env, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a safe short-form CineForge smoke.")
    parser.add_argument("--paid", action="store_true", help="Call the paid video vendor. Requires real env.")
    parser.add_argument("--max-auto-repair-attempts", type=int, default=1)
    args = parser.parse_args()

    if args.paid:
        missing = missing_vendor_env()
        if missing:
            print_json(missing_env_payload(
                missing=missing,
                message="Paid short-form smoke requires ATLASCLOUD_API_KEY. No render job was queued.",
            ))
            return 2

    idea, execution_plan, approval_lock = _build_shortform_plan_and_lock()
    executor = RenderExecutor(max_auto_repair_attempts=args.max_auto_repair_attempts)
    result = executor.execute(
        execution_plan=execution_plan,
        approval_lock=approval_lock,
        idea=idea,
        dry_run_only=not args.paid,
    )
    payload: dict[str, Any] = {
        "status": result.status,
        "mode": "paid" if args.paid else "dry_run",
        "execution_plan_id": result.execution_plan_id,
        "approval_valid": result.approval_verification.valid,
        "dry_run_hard_failures": result.dry_run_report.hard_failures,
        "dry_run_warnings": result.dry_run_report.warnings,
        "repair_attempts_by_shot": result.repair_attempts_by_shot,
        "qa_statuses": [report.status for report in result.qa_reports],
        "output_urls": [segment.video_url for segment in result.rendered_segments if segment.video_url],
        "message": result.message,
        "vendor_calls_performed": bool(args.paid and result.rendered_segments),
    }
    print_json(payload)
    if not args.paid:
        return 0 if result.status == "dry_run" else 1
    return 0 if result.status == "completed" and not any(report.status == "fail" for report in result.qa_reports) else 1


def _build_shortform_plan_and_lock():
    idea = "Create a 12s premium skincare serum product video with macro texture hook, product hero reveal, and clean payoff."
    product_ref = AssetRef(
        asset_id="smoke_serum_product",
        kind="image",
        url="https://cdn.test/smoke/serum-product.png",
        tag="@Image1",
        role=ReferenceRole.PRODUCT_HERO,
        role_locked=True,
        role_confidence=0.95,
        notes="serum bottle product packaging hero reference for smoke planning",
    )
    analyzed = InputAnalyzer().analyze(InputContract(
        user_idea=idea,
        duration_hint_s=12,
        assets=[product_ref],
    ))
    creative_plan = CreativePlanner().plan(analyzed)
    storyboard = StoryboardGenerator().generate(creative_plan, analyzed)
    execution_plan = SeedancePromptCompiler().compile(creative_plan, storyboard, analyzed)
    approval_lock = ApprovalLock.from_execution_plan(
        idea=analyzed.normalized_idea,
        execution_plan=execution_plan,
        approved_by="smoke_shortform",
        approval_source="dry_run_preview",
        metadata={"approved_idea": analyzed.normalized_idea},
    )
    return analyzed.normalized_idea, execution_plan, approval_lock


if __name__ == "__main__":
    raise SystemExit(main())
