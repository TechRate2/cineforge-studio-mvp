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

For the locked source map, role-stage graph, evidence policy, and duration
claim rules, see `docs/CINEJELLY_SOURCE_MAP.md`.

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
- `components/studio/ChatBriefComposer.tsx`
- `components/studio/SmartReferenceTray.tsx`
- `components/studio/AgentPlanPreview.tsx`
- `components/studio/RenderTimeline.tsx`

## Chat-first Studio

The primary Studio UI is organized around a conversational creation flow:

1. `ChatBriefComposer` captures the user idea and conversation context.
2. `SmartReferenceTray` handles uploads, role confirmation, and Reference
   Intelligence readiness when dry-run data exists.
3. `AgentPlanPreview` summarizes the agent's objective, niche, concept, script,
   storyboard, voice/audio direction, prompt strategy, cost, and warnings.
4. `RenderTimeline` maps available backend state to dry-run, ApprovalLock,
   render, QA, repair, final assembly, delivery, and benchmark evidence.

Unavailable backend fields must remain pending or unknown in UI. The UI must not
invent QA scores, delivery URLs, repair counts, or benchmark results.
After a render starts, `JobResultModal` polls the job endpoint and reports the
latest job payload back to `/studio`; `RenderTimeline` consumes that real job
payload for QA, repair, assembly, output URL, and evidence-pack status.

## Safety gates

The product should preserve these gates:

- ApprovalLock before paid work.
- Seedance preflight before vendor work.
- Reference Intelligence blockers in dry-run and review.
- Dry-run hard failures reject paid short-form render before vendor work.
- Consistency review when required.
- Cost gate when configured.
- Post-render QA after rendering.
- Short-form and long-form repair budget guards.
- Final file and delivery QA before completion.

## Render and repair policy

Short-form renders run through `RenderExecutor`. A completed render that fails
QA may be repaired once by default using `SegmentRepairPlan`, then rendered
again with strengthened prompt/negative prompt metadata. Vendor/render failures
remain `render_failed` and do not enter prompt repair loops. Repair attempts are
recorded in `repair_attempts_by_shot`.

Long-form renders run through `LongFormRenderExecutor`, segment by segment, with
segment-level repair attempts recorded in `repair_attempts_by_segment`.

## Benchmark protocol

Benchmark case definitions live in `backend/benchmark/cases.py`. Batch runs use
`backend/benchmark/batch_runner.py` and can be launched with:

```bash
python backend\scripts\run_benchmark_cases.py
```

The default benchmark mode is dry-run only. Paid benchmark mode requires
explicit `--paid` and real vendor/storage env. Launch-gate pass requires
complete evidence fields and must not be inferred from dry-run records.

## Smoke scripts

Safe default smoke scripts:

```bash
python backend\scripts\smoke_shortform.py
python backend\scripts\smoke_longform.py --duration-s 30
```

Paid smoke scripts require explicit `--paid`. Missing env returns
`status: "missing_env"` and performs no vendor call.

## Next priorities

1. Run full validation and real smoke with production keys.
2. Populate Reference Intelligence V2 with real analyzer adapters.
3. Add Asset Library and Production Bible.
4. Promote Long-form Graph Executor V2 only after paid graph benchmarks.
5. Add commercial readiness tools.

## Future design notes

Reference Intelligence V2 has an evidence contract for image, video, audio,
OCR/logo, product, face, and style signals. Until a signal is actually computed
or imported through `AssetRef.evidence`, the system must list it as unavailable.

Asset Library / Production Bible should store characters, products, brands,
locations, voices, style packs, and consent metadata. Long-form Graph Executor
V2 should add resumable graph execution, segment cache, failed-node retry,
scene memory, handoff visual QA, and final timeline QA. Commercial readiness
should add credits, billing, usage ledger, cost caps, admin dashboards, support
evidence bundles, and privacy/consent logs.
