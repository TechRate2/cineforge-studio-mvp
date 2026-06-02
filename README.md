# CineForge Studio MVP

CineForge Studio is being upgraded into **CineJelly Autonomous Agent**: an
autonomous video studio where the user gives one idea plus optional
image/video/audio references, then the system plans, routes, renders, reviews,
and packages a complete short or story-driven video.

Current product direction: **Autonomous Director only**. The `/studio` UI no
longer exposes the old manual Video Agent V2 controls.

## Current Status

CineJelly is a strong autonomous short-form foundation, especially for
15-60 second UGC, product, social, travel, food, education, music, and mini
drama experiments. It is not yet evidence-proven as a top-tier 5-30 minute
production system until paid AtlasCloud benchmark renders, human/model QA, and
promotion gates pass.

The honest operating rule:

- 15-60s: production-ready autonomous route.
- 60-180s: supported with stronger continuity and QA.
- 5-10m: benchmark-gated graph execution, not blind one-shot generation.
- 10-30m: research-gated episode pipeline until real benchmark evidence exists.

## Main Workflow

1. User opens `/studio`.
2. User enters one idea, optional target duration, optional market/language, and
   optional references.
3. Frontend calls `POST /api/v1/director/autonomous/production-decision` for a
   vendor-free preview of niche, market, story route, model strategy, reference
   sufficiency, Seedance segment plan, and missing inputs.
4. If the brief is ambiguous, the UI blocks paid render and asks for the minimum
   clarifying input.
5. User clicks **Generate Full Video (Autonomous)**.
6. Backend calls `POST /api/v1/director/autonomous`.
7. `AutonomousDirector` builds strategy, story, references, screenplay, scene
   blueprints, model route, render plan, QA gates, and distribution package.
8. Background worker renders AtlasCloud video segments, handles continuity, then
   assembles the final artifact.
9. `/studio` polls the job and shows the result in `JobResultModal`.

## Run Locally

```bash
# Frontend
npm install
npm run dev:frontend
```

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn api.main:app --host 127.0.0.1 --port 8002 --reload
```

Open `http://localhost:3000/studio`.

The Next.js app rewrites `/api/v1/*` to the FastAPI backend.

## Environment

Copy `.env.example` to `.env.local`, then fill the vendor keys needed for your
run:

```bash
ANTHROPIC_API_KEY=
ATLASCLOUD_API_KEY=
ATLASCLOUD_LLM_API_KEY=
GENMAX_API_KEY=
ELEVENLABS_API_KEY=
R2_*
DATABASE_URL=
```

Backend reads `.env.local` from the repo root and can be overridden by
`backend/.env`.

## Autonomous Inspection Endpoints

Use these before claiming the system is production-grade for a new niche or long
duration:

- `GET /api/v1/director/autonomous/workflow`
- `GET /api/v1/director/autonomous/readiness`
- `GET /api/v1/director/autonomous/recommendations`
- `GET /api/v1/director/autonomous/production-audit`
- `POST /api/v1/director/autonomous/production-decision`
- `GET /api/v1/director/autonomous/niche-launch-matrix`
- `GET /api/v1/director/autonomous/niche-playbook-catalog`
- `GET /api/v1/director/autonomous/atlas-model-matrix`
- `GET /api/v1/director/autonomous/top-tier-completion-gate`
- `GET /api/v1/director/autonomous/paid-benchmark-manifest`
- `GET /api/v1/director/autonomous/benchmark-review-rubric`
- `POST/PATCH /api/v1/director/autonomous/benchmarks/results`

## Important Source Files

- Frontend: `app/studio/page.tsx`
- Result modal: `components/studio/JobResultModal.tsx`
- Job polling types: `lib/studio/use-director-job-poll.ts`
- Autonomous route: `backend/api/routes/director.py`
- Main autonomous chain: `backend/agent/autonomous_director.py`
- Production decision: `backend/agent/autonomous_production_decision.py`
- Workflow contract: `backend/agent/autonomous_workflow_contract.py`
- Production audit: `backend/agent/autonomous_production_audit.py`
- Paid benchmark manifest: `backend/agent/autonomous_paid_benchmark_manifest.py`
- Competitive research map: `backend/agent/autonomous_competitive_research.py`
- Model scorecard: `backend/agent/model_scorecard.py`
- Atlas model matrix: `backend/agent/atlas_model_integration_matrix.py`

## Documentation

- `docs/cinejelly_top_tier_gap_audit_2026_06_01.md`: current source-backed gap
  audit, operator summary, workflow, China/Seedance references, and benchmark
  plan.
- `docs/cinejelly_autonomous_agent_blueprint.md`: long-form architecture and
  autonomous roadmap.
- `docs/autonomous_video_agent_audit_2026_05_31.md`: earlier audit and
  implementation history.

External references tracked in the audit include AtlasCloud docs, Seedance 2.0
docs, Jellyfish, LocalMiniDrama, Moyin Creator, MovieAgent, DrawVideo,
ComfyUI Seedance 2.0 notes, ViMax, and Seedance prompt-skill patterns.

## Verification

```bash
python -m compileall -q backend
python backend\scripts\run_backend_tests.py
node .\scripts\typecheck.mjs
node .\scripts\check-autonomous-ui.mjs
```

Smoke check:

```bash
Invoke-WebRequest http://127.0.0.1:8002/health
Invoke-WebRequest http://localhost:3000/studio
```

## License

Private - owner: taithutv7@gmail.com
