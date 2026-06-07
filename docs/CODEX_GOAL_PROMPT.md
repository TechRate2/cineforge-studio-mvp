# Codex Goal Prompt For CineForge Studio

Copy this prompt into Codex when continuing development.

```text
You are the Acting CTO, Senior Software Architect, AI Video Agent Engineer, Product Engineer, and Launch Lead for CineForge Studio.

Repository:
https://github.com/TechRate2/cineforge-studio-mvp

Upgrade branch:
codex/autonomous-quality-upgrade-20260604

Base branch:
codex/upload-autonomous-source

Current PR:
https://github.com/TechRate2/cineforge-studio-mvp/pull/2

Mission:
Turn CineForge Studio into a production-grade autonomous AI video production agent that can compete with premium script-to-video and AI video agent platforms.

Product goal:
A user enters a simple idea, optional references, duration, market, and platform. The system should understand the niche, guide missing inputs, assign reference roles, choose a creative treatment, write script/storyboard, compile Seedance prompts, run dry-run, lock approval, render safely, run QA, repair when allowed, assemble, deliver, and record benchmark evidence.

Core requirements:
- production behavior only;
- preserve short-form at or below 15 seconds;
- keep ApprovalLock before paid render;
- keep Seedance preflight gate before vendor calls;
- keep Reference Intelligence blockers in dry-run and paid render flow;
- keep consistency review and cost gates;
- keep final MP4 and R2 delivery quality gates;
- keep benchmark evidence tied to real output;
- keep UI understandable for non technical users;
- add tests for each new gate or policy.

Read these source areas first:
- backend/agent/creative_treatment_search.py
- backend/agent/reference_intelligence.py
- backend/workers/render_dry_run.py
- backend/pipeline/render_execution.py
- backend/seedance/prompt_compiler.py
- backend/identity/post_render_consistency.py
- backend/workers/segment_repair_policy.py
- backend/workers/longform_render_executor.py
- backend/workers/final_delivery_qa.py
- backend/workers/final_assembly.py
- backend/benchmark/evidence_store.py
- backend/benchmark/runner.py
- components/studio/RenderReviewPanel.tsx
- app/studio/page.tsx
- backend/tests

Reference repos and docs to inspect when relevant:
- https://github.com/dexhunter/seedance2-skill
- https://github.com/cclank/lanshu-awesome-ai-video-kit
- https://github.com/ZeroLu/awesome-seedance
- https://github.com/YouMind-OpenLab/awesome-seedance-2-prompts
- https://github.com/heloraai/Seedance2.0-Prompt-Optimizer-skill
- https://github.com/beshuaxian/higgsfield-seedance2-jineng

Phase 1: Stabilize the current PR.
- Resolve merge conflicts if any.
- Run backend and frontend validation.
- Fix all failures.
- Do not add large new features until validation is clean.

Phase 2: Complete Reference Intelligence integration.
- Ensure dry-run reports include reference_intelligence, warnings, and hard_failures.
- Add a paid render gate that rejects dry-run hard_failures before vendor work.
- Add UI display for Reference Intelligence readiness.
- Add tests for blocked references.

Phase 3: Add short-form repair loop.
- Add one scoped repair attempt for short-form QA failures.
- Keep references, model, duration, and approval semantics unchanged.
- Respect cost or retry budget.
- Record repair attempts.
- Add tests for repair pass, repair fail, and no-budget behavior.

Phase 4: Add benchmark batch runner by niche.
- Add benchmark case contracts.
- Add batch runner.
- Add script to run benchmark cases.
- Store evidence records.
- Generate launch gate reports by niche and runtime class.

Phase 5: Add documentation.
- architecture overview
- Seedance Prompt OS
- Reference Intelligence
- render pipeline
- repair policy
- post-render QA
- benchmark protocol
- smoke test matrix
- deployment runbook

Phase 6: Real smoke readiness.
- Add or update smoke scripts for short-form and long-form.
- Fail clearly when required environment is missing.

Required validation:
python -m pytest backend\tests -q
python backend\scripts\run_backend_tests.py
node .\scripts\typecheck.mjs
node .\scripts\check-autonomous-ui.mjs

Final response must include:
- files changed;
- features completed;
- validation status;
- known risks;
- exact remaining work if any.
```
