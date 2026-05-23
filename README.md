# CineForge Studio MVP

Standalone fork of the `ai-studio-hub` repo containing **only the AI Video Studio**
pipeline (Director Agent V3) — backend + frontend. Stripped of marketing pages,
admin panel, pricing, login, model docs. Those will be re-added later by the owner.

Source extracted on 2026-05-23 from commit `4011272` of `TechRate2/ugc-vietnam-studio`.

## What's included

### Backend (`backend/`)
Full FastAPI app implementing the 3-layer Director V3 pipeline:

- **Layer 1 — Director Agent** (`backend/agent/director_agent.py`)
  generates Continuity Bible + Shot List + Storyboard from a user brief via LLM.
- **Layer 2 — Scene Generation Agent** (`backend/agent/scene_generation_agent.py`)
  turns each Shot into a model-ready prompt with `@image_N` / `@video_N` tags,
  Reference Chaining, role-aware refs, cinematic vocabulary.
- **Layer 3 — Video Worker** (`backend/workers/video_worker.py`)
  chain-renders shots through AtlasCloud (Seedance 2.0 / Vidu Q3 / Wan 2.7),
  carries `last_frame_url` between shots, assembles MP4 with ffmpeg + audio,
  uploads to R2.

Includes 43+ bug fixes from 5 Sprints (security, race, lifecycle, validation,
info leak, cost/billing, UX/observability, spec correctness, protocol).

### Frontend (`app/` + `components/`)
- `/studio` — original CineForge V3 input + DirectorPlanModal review flow
- `/studio-v5` — LumeFlow-inspired visual redesign (same V3 logic)
- All `components/studio/*` (DirectorPlanTab, TimelineEditor, RefineDrawer,
  AudioStudioDrawer, WorkspaceChat, ProjectHistoryDrawer, AssetLibrary,
  ReferenceZones, AdvancedPanel, ContextInjection, GenerateFormats,
  VideoAgentCard, JobResultModal)
- All hooks in `lib/studio/*` (use-director-plan, use-director-plan-editor,
  use-refine-shot, use-asset-library, use-project-history, use-workspace-chat,
  use-timeline, use-admin, use-genmax-tts)

### NOT included (deferred to owner)
- `/pricing`, `/login`, `/docs`, `/admin`, `/models/[slug]`, `/`-landing
- `components/Header`, `Sidebar`, `Footer`, `PromoBanner` (marketing chrome)
- `app/api/v1/{chat,avatars,templates}` (legacy non-studio APIs)
- Legacy `lib/models`, `lib/image/*`

## Setup

```bash
# Frontend
npm install

# Backend (Python 3.12)
cd backend
python -m venv venv
venv\Scripts\activate     # Windows
# OR: source venv/bin/activate  # Mac/Linux
pip install -r requirements.txt
```

## Env

```bash
cp .env.example .env.local
# Fill in: ANTHROPIC_API_KEY, ATLASCLOUD_API_KEY, ATLASCLOUD_LLM_API_KEY,
# GENMAX_API_KEY, ELEVENLABS_API_KEY, R2_*, DATABASE_URL (optional)
```

Backend reads `.env.local` from root + `backend/.env` override.

## Run

```bash
# Backend (port 8001)
cd backend
python -m uvicorn api.main:app --port 8001 --reload

# Frontend (port 3000) — separate terminal
npm run dev:frontend
```

Visit `http://localhost:3000` → auto-redirect to `/studio`.

## Architecture

```
Browser
   ↓
Next.js (port 3000)
   ↓ /api/v1/* rewrite (next.config.js)
FastAPI (port 8001)
   ├── /director/plan/stream  → Layer 1 LLM → ContinuityBible + ShotList
   ├── /director/generate     → Layer 2 + Layer 3 worker chain
   ├── /director/jobs/{id}    → job polling
   ├── /jobs/storyboard       → image gen for storyboard
   ├── /audio/direct          → TTS via GenMax
   ├── /image/direct          → image gen (Seedream/Flux)
   └── /video/direct          → video gen direct (bypass director)
```

Vendors: AtlasCloud (video + LLM), GenMax (TTS VN), ElevenLabs (SFX), R2 (storage).

## License

Private — owner: taithutv7@gmail.com
