# CineForge Studio Codex Agent Brief

## Mission

CineForge Studio is an autonomous AI video production system built around Seedance rendering. The product should help a non technical user turn a simple idea and optional references into a planned, rendered, reviewed, repaired, assembled, delivered, and benchmarked video.

The system should behave like a production team in software form:

- Producer
- Creative Director
- Script Writer
- Storyboard Artist
- Seedance Prompt Engineer
- Render Supervisor
- Quality Inspector
- Repair Agent
- Editor
- Delivery Assistant
- Benchmark Analyst

## Current Source Context

Main repository:

- https://github.com/TechRate2/cineforge-studio-mvp

Current upgrade branch:

- `codex/autonomous-quality-upgrade-20260604`

Base branch:

- `codex/upload-autonomous-source`

Current upgrade PR:

- https://github.com/TechRate2/cineforge-studio-mvp/pull/2

The current PR already adds or improves:

- creative treatment search
- Seedance Prompt OS
- paid render preflight gate
- Reference Intelligence V1
- dry-run Reference Intelligence reporting
- post-render visual consistency policy
- long-form segment continuity prompt compiler
- long-form segment repair
- final MP4 quality check
- R2 delivery quality check
- benchmark evidence store
- benchmark render runner
- RenderReviewPanel review UX
- tests for the above policies and gates

## Operating Principles

1. Build production behavior, not demonstration behavior.
2. Preserve the short-form path at or below 15 seconds.
3. Keep paid render gates strict: ApprovalLock, Seedance preflight, Reference Intelligence, consistency review, and cost gate.
4. Keep prompts structured and reference jobs explicit.
5. Keep QA conservative when evidence is weak or missing.
6. Keep repair scoped: strengthen prompt or metadata inside budget while preserving approved references and model route.
7. Keep delivery fail-closed when final file or storage delivery metadata is invalid.
8. Keep benchmark claims tied to real evidence records.
9. Keep UI understandable to non technical users.
10. Keep code typed, testable, and maintainable.

## Required Validation Before Merge

Run:

```bash
python -m pytest backend\tests -q
python backend\scripts\run_backend_tests.py
node .\scripts\typecheck.mjs
node .\scripts\check-autonomous-ui.mjs
```

## Required Real Smoke Before Launch

A launch candidate should pass:

1. Short-form text-only 8s.
2. Short-form product reference 8 to 12s.
3. Short-form creator plus product UGC 12 to 15s.
4. Long-form 30s dry-run.
5. Long-form 30s paid render.
6. Final assembly and R2 delivery.
7. Quality failure leads to repair or review behavior.
8. Delivery failure fails closed.
9. Benchmark evidence record is created.

## Definition of Done

A change is complete only when:

- implementation uses real project contracts and real pipeline data;
- tests are added or updated;
- short-form is not regressed;
- paid render gates remain intact;
- UI states are explainable;
- validation commands pass in a real checkout;
- PR notes state validation status and remaining risks clearly.
