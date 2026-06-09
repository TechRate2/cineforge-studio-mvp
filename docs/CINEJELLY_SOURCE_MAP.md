# CineJelly Source Map

This document locks the current autonomous director architecture so future work
extends the production-safe path instead of reintroducing ad hoc render flows.

## Canonical Path

The canonical paid render path is:

1. `/studio` chat-first brief and reference upload.
2. `POST /api/v1/director/autonomous/production-decision` for vendor-free planning preview.
3. `POST /api/v1/director/autonomous` for dry-run or paid render.
4. `SeedanceExecutionPlan` plus `ApprovalLock`.
5. `RenderExecutor` or `LongFormRenderExecutor`.
6. segment render, deterministic QA, optional repair, assembly, R2 delivery QA.
7. benchmark evidence pack and feedback integrity review.

Legacy `DirectorPlan` remains compatibility surface only. New production work
must attach evidence to the Seedance execution path.

## Production Roles

The production graph uses typed role-stage nodes as audit metadata:

- Intake Producer: input contract, duration policy, market/platform intent.
- Research Strategist: niche playbook, competitive patterns, treatment choice.
- Screenwriter: screenplay, acts, scene scripts, dialogue policy.
- Asset Librarian: reference manifest, asset bible, user-confirmed roles.
- Storyboard Director: scene blueprints, shot list, visual beats.
- Prompt Compiler: Seedance prompt formula, reference jobs, negative prompt.
- Render Producer: cost gate, approval lock, render execution plan.
- Continuity Supervisor: scene memory, last-frame handoff, downstream invalidation.
- Critic QA: deterministic QA, model-backed QA contract, repair policy.
- Editor Delivery: assembly, delivery URL, final delivery QA.
- Benchmark Analyst: evidence pack, promotion readiness, feedback integrity.

Role nodes are not paid render tasks. Executable graph units remain shot, QA,
and assembly nodes so the queue runner stays dependency-safe.

## Evidence Policy

Evidence beats claims. A claim is not launch-ready unless the backend has real:

- rendered output URL;
- clean final delivery QA;
- reference manifest;
- QA checkpoint report;
- render cost and latency;
- human or model review notes;
- feedback integrity that is promotion-safe.

Missing evidence must remain `pending` or `needs_review`. It must never be
displayed as pass, benchmark-ready, or top-tier proof.

## Reference Policy

The Reference Manifest is the paid render source of truth. Every image, video,
and audio reference needs one clear job, must fit Seedance caps, and must be
confirmed by the user before paid render. Reference Intelligence V2 may report
detected, user-confirmed, and unavailable signals, but analyzer output never
replaces user role confirmation.

## Duration Policy

- 15-60 seconds: current strongest production range.
- 60+ seconds: requires segmented graph evidence and stronger QA.
- 5-10 minutes: benchmark-gated until paid graph runs pass.
- 10-30 minutes: research-gated until graph execution, asset bible, dialogue,
  continuity, QA, cost, and benchmark evidence are proven.

## Guard Rails

Paid work must fail closed when approval lock, confirmed reference manifest,
cost gate, R2/delivery configuration, dry-run hard failures, or deliverable URL
validation is missing. Direct vendor generation remains an admin/safety-gated
route, not the normal Studio path.
