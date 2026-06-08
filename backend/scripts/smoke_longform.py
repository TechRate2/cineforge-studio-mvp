"""Safe long-form smoke test for CineForge Studio.

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

from longform.longform_planner import LongFormPlanner
from longform.segment_prompt_compiler import SegmentPromptCompiler
from pipeline.approval_lock import ApprovalLock
from pipeline.contracts import AssetRef, InputContract, ReferenceRole
from pipeline.creative_planning import CreativePlanner
from pipeline.input_analysis import InputAnalyzer
from workers.final_assembly import FinalVideoAssemblyService
from workers.longform_render_executor import LongFormRenderExecutor

from smoke_common import (
    missing_delivery_env,
    missing_env_payload,
    missing_media_tools,
    missing_vendor_env,
    print_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a safe long-form CineForge smoke.")
    parser.add_argument("--paid", action="store_true", help="Call paid video vendor and assemble final delivery.")
    parser.add_argument("--duration-s", type=int, default=30)
    parser.add_argument("--approve-consistency-review", action="store_true")
    parser.add_argument("--max-auto-repair-attempts", type=int, default=1)
    args = parser.parse_args()

    if args.paid:
        missing_env = [*missing_vendor_env(), *missing_delivery_env()]
        missing_tools = missing_media_tools()
        if missing_env or missing_tools:
            payload = missing_env_payload(
                missing=missing_env,
                message="Paid long-form smoke requires vendor/storage env and local media tools. No render job was queued.",
            )
            payload["missing_tools"] = missing_tools
            print_json(payload)
            return 2

    idea, longform_plan, approval_lock = _build_longform_plan_and_lock(
        duration_s=args.duration_s,
        paid=args.paid,
        approve_consistency_review=args.approve_consistency_review,
    )
    executor = LongFormRenderExecutor(max_auto_repair_attempts=args.max_auto_repair_attempts)
    if not args.paid:
        result = executor.dry_run(longform_plan=longform_plan, approval_lock=approval_lock, idea=idea)
        print_json({
            "status": result.status,
            "mode": "dry_run",
            "longform_plan_id": result.longform_plan_id,
            "approval_valid": result.approval_verification.valid,
            "dry_run_hard_failures": result.dry_run_report.hard_failures,
            "segment_count": len(longform_plan.segments),
            "message": result.message,
            "vendor_calls_performed": False,
        })
        return 0 if result.status == "dry_run" else 1

    result = executor.execute(
        longform_plan=longform_plan,
        approval_lock=approval_lock,
        idea=idea,
        dry_run_approved=True,
    )
    assembly_payload: dict[str, Any] | None = None
    if result.status == "completed":
        assembly = FinalVideoAssemblyService().assemble(
            job_id=f"smoke_longform_{longform_plan.longform_plan_id}",
            longform_plan_id=longform_plan.longform_plan_id,
            render_result=result,
            editor_preview={
                "distribution_package": {
                    "title_en": "CineForge long-form smoke",
                    "caption_en": "Automated paid long-form smoke delivery.",
                    "hashtags_en": ["#CineForge", "#AIvideo"],
                }
            },
        )
        assembly_payload = {
            "status": assembly.status,
            "final_video_url": assembly.final_video_url,
            "storage_key": assembly.storage_key,
            "final_video_qa": assembly.final_video_qa.model_dump(mode="json") if assembly.final_video_qa else None,
            "final_delivery_qa": assembly.final_delivery_qa.model_dump(mode="json") if assembly.final_delivery_qa else None,
            "error": assembly.error,
        }
    print_json({
        "status": result.status,
        "mode": "paid",
        "longform_plan_id": result.longform_plan_id,
        "approval_valid": result.approval_verification.valid,
        "repair_attempts_by_segment": result.repair_attempts_by_segment,
        "qa_statuses": [report.status for report in result.qa_reports],
        "message": result.message,
        "assembly": assembly_payload,
        "vendor_calls_performed": bool(result.rendered_segments),
    })
    return 0 if result.status == "completed" and assembly_payload and assembly_payload["status"] == "completed" else 1


def _build_longform_plan_and_lock(*, duration_s: int, paid: bool, approve_consistency_review: bool):
    idea = f"Create a {duration_s}s beauty serum product film with macro hook, proof sequence, and payoff."
    assets = [
        AssetRef(
            asset_id="smoke_longform_serum_hero",
            kind="image",
            url="https://cdn.test/smoke/serum-hero.png",
            tag="@Image1",
            role=ReferenceRole.PRODUCT_HERO,
            role_locked=True,
            role_confidence=0.95,
            notes="serum bottle product packaging hero reference",
        ),
        AssetRef(
            asset_id="smoke_longform_serum_detail",
            kind="image",
            url="https://cdn.test/smoke/serum-detail.png",
            tag="@Image2",
            role=ReferenceRole.PRODUCT_DETAIL,
            role_locked=True,
            role_confidence=0.9,
            notes="serum bottle label detail reference",
        ),
    ]
    analyzed = InputAnalyzer().analyze(InputContract(user_idea=idea, duration_hint_s=duration_s, assets=assets))
    creative_plan = CreativePlanner().plan(analyzed)
    longform_plan = LongFormPlanner().plan(creative_plan=creative_plan, analyzed_input=analyzed)
    longform_plan = SegmentPromptCompiler().compile(
        longform_plan=longform_plan,
        creative_plan=creative_plan,
        analyzed_input=analyzed,
    )
    master_plan = longform_plan.master_execution_plan
    if master_plan is None:
        raise RuntimeError("longform_plan_missing_master_execution_plan")
    action = str(master_plan.metadata.get("consistency_policy_action") or "")
    metadata: dict[str, Any] = {
        "approved_idea": analyzed.normalized_idea,
        "longform_plan_id": longform_plan.longform_plan_id,
        "longform_dry_run_approved": paid,
        "segment_graph_hash": longform_plan.segment_graph_hash,
        "continuity_bible_hash": longform_plan.continuity_bible.continuity_hash,
    }
    if approve_consistency_review and action == "requires_review":
        metadata.update({
            "consistency_review_approved": True,
            "consistency_review_approved_policy_action": "requires_review",
        })
    approval_lock = ApprovalLock.from_execution_plan(
        idea=analyzed.normalized_idea,
        execution_plan=master_plan,
        reference_assets=master_plan.reference_assets,
        cost_estimate=master_plan.cost_estimate,
        approved_by="smoke_longform",
        approval_source="longform_dry_run_preview",
        metadata=metadata,
    )
    return analyzed.normalized_idea, longform_plan, approval_lock


if __name__ == "__main__":
    raise SystemExit(main())
