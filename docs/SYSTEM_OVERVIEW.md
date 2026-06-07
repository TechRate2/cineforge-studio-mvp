# CineForge Studio System Overview

## Purpose

CineForge Studio is an autonomous video production system. It takes a user idea, optional reference assets, target duration, platform, and market, then produces a video through planning, prompt compilation, dry-run, approval, render, quality review, repair, assembly, delivery, and benchmark evidence.

## Main flow

1. User brief and references.
2. Creative reasoning and treatment selection.
3. Reference policy and Reference Intelligence.
4. Storyboard or segment plan.
5. Seedance Prompt OS.
6. Dry-run report.
7. ApprovalLock.
8. RenderExecutor safety gates.
9. Vendor render.
10. Post-render QA.
11. Repair when allowed.
12. Final assembly for long-form.
13. Final file and delivery QA.
14. Benchmark evidence.
15. Studio UI review.

## Core backend files

- `backend/agent/creative_treatment_search.py`
- `backend/agent/reference_intelligence.py`
- `backend/workers/render_dry_run.py`
- `backend/pipeline/render_execution.py`
- `backend/seedance/prompt_compiler.py`
- `backend/identity/post_render_consistency.py`
- `backend/workers/segment_repair_policy.py`
- `backend/workers/longform_render_executor.py`
- `backend/workers/final_delivery_qa.py`
- `backend/workers/final_assembly.py`
- `backend/benchmark/evidence_store.py`
- `backend/benchmark/runner.py`

## Core frontend files

- `app/studio/page.tsx`
- `components/studio/RenderReviewPanel.tsx`

## Safety gates

The product should preserve these gates:

- ApprovalLock before paid work.
- Seedance preflight before vendor work.
- Reference Intelligence blockers in dry-run and review.
- Consistency review when required.
- Cost gate when configured.
- Post-render QA after rendering.
- Final file and delivery QA before completion.

## Next priorities

1. Run full validation.
2. Gate paid render on dry-run hard failures.
3. Add short-form repair loop with budget guard.
4. Add Reference Intelligence UI panel.
5. Add benchmark batch runner by niche.
6. Add multimodal Reference Intelligence V2.
7. Add Asset Library and Production Bible.
8. Add commercial readiness tools.
