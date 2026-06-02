# CineJelly Autonomous Video Agent Audit

Date: 2026-06-01

2026-06-01 correction: current Seedance/Atlas-compatible generation windows are
treated as 4-15s per model call. Anything above 15s must be decomposed into
shots and scene/chunk groups, then assembled. Scene groups can still be 30-60s
for production planning, progress, QA, and resume, but they are not sent as one
Seedance request.

## Verdict

CineJelly is now a strong autonomous-first video agent foundation, but it is
not yet equal to the best production-grade China/agentic video systems for
5-30 minute long-form output. The current stack is already competitive for
short-form and UGC/product workflows because it combines:

- autonomous-only `/studio` UI
- Seedance 2.0 quad-modal reference intake
- planner/storyboard/director/editor skills
- target market playbooks
- 23 niche playbooks and benchmark prompts
- long-form runtime/screenplay/scene planning
- producer cost strategy
- reference manifest, asset memory, QA metadata, and safe shot retry
- queryable autonomous capability/readiness matrix for all supported niches

The missing production-grade layer is a durable render graph executor with
resumable chunks, approved asset pinning, real visual/audio QA, benchmarked
model routing, and user-visible production inspection.

## Current Workflow

1. `/studio` accepts one idea, optional runtime, optional market, and up to 12
   mixed references:
   - 9 images
   - 3 videos
   - 3 audio refs
2. Frontend calls `POST /api/v1/director/autonomous`.
3. `AutonomousDirector` runs:
   - Planner: niche, hook, mood, duration, aspect.
   - Market playbook: localization, claim style, dialogue/caption tone.
   - Niche playbook: hook grammar, shot grammar, camera/audio/QA rules.
   - Asset memory retrieval: prior reusable assets are suggested as metadata.
   - RoleTagger: labels image/video/audio refs for identity, product, style,
     motion, rhythm, environment.
   - Runtime planner: short, sequence, micro-film, short-film, episode.
   - Screenplay/scene planner for >180s jobs.
   - Storyboard: panels/beats.
   - Director: renderable shot specs.
   - Editor: caption, hashtags, transition notes.
4. `DirectorPlan` is built with a Production Bible:
   - characters/products/style/audio/setting/constraints
   - reference assets
   - niche and market metadata
   - runtime structure
   - production graph artifact
5. API saves a production artifact snapshot for inspection/replay.
6. API persists the production graph into SQLite as graph/node/edge rows and
   exposes it through `GET /api/v1/director/jobs/{job_id}/production-graph`.
7. Background render worker:
   - auto-picks Seedance 2.0 / Seedance Fast / Wan fallback
   - chooses <=15s single-call multi-shot or per-shot reference chaining
   - passes image/video/audio refs to Seedance-capable routes
   - updates persisted graph node status for shots, QA, retry attempts, and
     final assembly
   - downloads rendered clips
   - probes media and samples QA frames
   - runs semantic QA when available
   - builds retry plan and executes safe per-shot retries
   - assembles final MP4 and returns result to JobResultModal
8. Asset memory stores useful image references for later runs.
9. Capability status can be queried from
   `GET /api/v1/director/autonomous/capabilities`.

## Seedance 2.0 Best-Practice Fit

Current implementation is aligned with the strongest public Seedance 2.0
patterns:

- explicit reference binding with `@image_N`, `@video_N`, `@audio_N`
- image refs for identity/product/style
- video refs for camera/motion rhythm
- audio refs for beat/SFX/dialogue style
- 4-15s generation chunks
- long videos decomposed into shots/scenes/chunks instead of one long prompt

References:

- https://www.seedvideo.net/docs/seedance-2-parameters
- https://seedance2.app/docs
- https://www.atlascloud.ai/docs/openapi-index
- https://www.atlascloud.ai/docs/more-models/atlascloud/mmaudio-v2/generateVideo
- https://www.atlascloud.ai/docs/more-models/bytedance/lipsync-audio-to-video/generateVideo
- https://www.atlascloud.ai/docs/more-models/bytedance/avatar-omni-human/generateVideo
- https://www.atlascloud.ai/docs/more-models/atlascloud/instant-character/generateImage
- https://www.atlascloud.ai/models/atlascloud/infinitetalk

## External Patterns To Borrow

Latest additional research pass, 2026-05-31:

- AtlasCloud Seedance 2.0 routes expose `generateVideo` async jobs for
  `bytedance/seedance-2.0/image-to-video`,
  `bytedance/seedance-2.0/reference-to-video`, and Fast variants. Practical
  provider docs highlight 9 image refs, 3 video refs, 3 audio refs, mixed
  multimodal prompting, native audio/lip-sync, and per-request short clip
  limits. CineJelly's 12-reference UI and reference-role tagging match this.
- AtlasCloud also lists supporting video models worth routing selectively:
  `bytedance/lipsync/audio-to-video`, `bytedance/avatar-omni-human`, Vidu,
  Kling, Wan, and video-effects endpoints. Do not expose these as user choices;
  add them behind a benchmarked model router.
- AtlasCloud InfiniteTalk is now a priority benchmark candidate for dialogue
  and education/product-spokesperson scenes. It accepts portrait/reference
  video plus WAV/MP3 audio, advertises up to 10-minute talking-head output,
  multilingual phoneme-level lip sync, identity preservation, two-person
  conversation mode, and low per-run/per-second pricing. CineJelly should not
  replace Seedance with it; it should route only dialogue-heavy long scenes or
  localized Vietnamese presenter inserts to InfiniteTalk after benchmark clips
  prove stability.
- Public Seedance creator guidance repeats one practical rule: every uploaded
  asset must be assigned a job. Image refs should lock identity/product/style,
  video refs should transfer camera/motion/rhythm, audio refs should guide beat,
  ambience, voice tone, and SFX. Prompts should be timeline-based, physical,
  and shot-specific.
- Implemented in source: `backend/agent/seedance_prompt_compiler.py` now
  normalizes every Seedance 2.0 per-shot render prompt into reference jobs,
  timeline, shot direction, camera/sound, director intent, and constraints.
- Implemented in source: autonomous RoleTagger video/audio roles are persisted
  into `ContinuityBible.storytelling_meta.quad_modal_reference_roles`; the
  reference manifest now uses those roles so `@video_N` and `@audio_N` keep
  their intended jobs such as motion style, shot pacing, beat reference, SFX,
  or lip-sync source.
- Long-form research converges on the same architecture: global story/asset
  bible, storyboard/keyframe or sketch control, per-shot synthesis, evaluator
  agents, and selective regeneration instead of full rerenders.

Sources:

- https://www.atlascloud.ai/models/bytedance/seedance-2.0/image-to-video
- https://www.atlascloud.ai/zh/models/bytedance/seedance-2.0/reference-to-video
- https://www.atlascloud.ai/docs/openapi-index
- https://x.com/chatcutapp/status/2041763561333264865
- https://arxiv.org/abs/2605.23508
- https://arxiv.org/abs/2605.30090

Codeywood:

- modular skills
- reference library
- quality gates
- character/location references across many shots

Source: https://codeywood.com/

Research patterns:

- CANVAS: continuity-aware visual agentic storyboarding with character,
  background, and location-aware planning.
- CoAgent: plan-synthesize-verify loop with global context memory and selective
  regeneration.
- InfinityStory: world consistency and character-aware shot transitions.
- DrawVideo: storyboard/keyframe-guided long-video generation.
- MAViS: script writing, shot designing, character modeling, keyframe
  generation, video animation, audio generation, and evaluator agents.

Sources:

- https://arxiv.org/abs/2604.13452
- https://arxiv.org/abs/2512.22536
- https://arxiv.org/abs/2603.03646
- https://arxiv.org/abs/2605.23508
- https://aclanthology.org/2026.eacl-long.101.pdf

China/open-source production systems:

- Jellyfish: script input, storyboard preparation, consistency management,
  generation workspace, task tracking, reusable characters/scenes/props.
  Source: https://github.com/Forget-C/Jellyfish
- LumenX Studio: novel/script to short-comic-drama pipeline with asset
  extraction, style setting, asset generation, storyboard construction,
  storyboard images, and video synthesis. Source:
  https://github.com/alibaba/lumenx
- Pixelle-Video: automated short video engine with copywriting, AI images/video,
  voiceover, background music, final composition, digital human and action
  transfer modules. Source: https://github.com/AIDC-AI/Pixelle-Video
- Huobao Drama: one-sentence-to-short-drama platform with Mastra agents and
  script-to-storyboard skill flow. Source:
  https://github.com/chatfire-AI/huobao-drama
- VibeFrame: agent-friendly project loop using deterministic files,
  storyboard/design docs, dry runs, cost gates, generated assets, render, and
  machine-readable review reports. Source:
  https://github.com/vericontext/vibeframe

What CineJelly should borrow from those systems:

- Treat assets as durable project objects, not only temporary uploads.
- Track every scene/shot/render/QA/retry as a task node with recoverable state.
- Let the agent generate script, scene list, shot list, prompts, captions,
  audio, and QA reports as inspectable artifacts.
- For long-form, make user-facing output a project/episode timeline, not a
  single opaque job.

2026-06-01 priority sources and how to apply them:

- AtlasCloud docs: keep the backend on async `generateVideo` + prediction
  polling + uploadMedia flow. Use Atlas as a model router backend, not as UI
  clutter. Source: https://www.atlascloud.ai/docs
- Seedance 2.0 parameter/manual docs: enforce 4-15s generation calls, max 9
  images, 3 videos, 3 audios, and explicit `@image/@video/@audio` role binding.
  Source: https://www.seedvideo.net/docs/seedance-2-parameters
- AtlasCloud InfiniteTalk: benchmark for long multilingual talking-head and
  product-spokesperson scenes before automatic routing. Source:
  https://www.atlascloud.ai/es/infinitetalk
- AtlasCloud MultiTalk: benchmark as lower-cost multi-person dialogue insert
  lane, not as a replacement for cinematic Seedance coverage. Source:
  https://www.atlascloud.ai/models/atlascloud/multitalk
- AtlasCloud MMAudio v2: post-render ambience/SFX pass after visual QA. Source:
  https://www.atlascloud.ai/models/atlascloud/mmaudio-v2
- Bytedance LipSync: repair generated dialogue clips from existing video+audio
  when phoneme alignment is more important than new cinematography. Source:
  https://www.atlascloud.ai/ko/models/bytedance/lipsync/audio-to-video
- AtlasCloud video-upscaler: final polish only, never a substitute for fixing
  bad source shots. Source:
  https://www.atlascloud.ai/docs/more-models/atlascloud/video-upscaler/generateVideo
- Implemented dialogue routing contract:
  `backend/agent/dialogue_route_policy.py` keeps Seedance as the cinematic
  coverage model, routes 5-10s visible-face dialogue to the current Wan
  fallback, benchmark-gates long single-speaker dialogue through InfiniteTalk,
  benchmark-gates two-speaker dialogue through MultiTalk, and treats LipSync as
  a repair lane rather than a primary scene generator.
- Implemented production decision preview:
  `POST /api/v1/director/autonomous/production-decision` returns a vendor-free
  explanation of niche, runtime class, graph requirement, Seedance route,
  dialogue lane, workflow steps, market/niche playbooks, QA gates, and
  benchmark requirement before `/autonomous` starts paid work.
- Implemented deterministic production-decision smoke coverage:
  `npm run backend:test` validates representative routing gates plus all 23
  canonical niche benchmark cases without calling LLMs or AtlasCloud.
- Implemented benchmark promotion policy:
  `backend/agent/benchmark_promotion_policy.py` keeps experimental
  dialogue/audio/upscale/character model routes locked until there are at
  least two real, approved, QA-passing vendor outputs for the relevant route.
- ViMax: borrow the Director + Screenwriter + Producer + Video Generator split
  for long-form jobs. Source: https://github.com/HKUDS/AI-Creator
- DirectorBench: benchmark long-form outputs with script, visual, audio,
  cross-modal, and stability dimensions instead of one generic score. Source:
  https://arxiv.org/abs/2605.30090

## Niche Readiness

High readiness:

- UGC review
- beauty
- food
- tech/product demo
- ASMR
- ecommerce catalog
- lifestyle/fashion
- app/SaaS demo

Medium readiness:

- drama/short film
- education/explainer
- documentary/founder story
- real estate
- restaurant/hospitality
- travel
- gaming
- automotive
- fitness
- music video
- anime/comic

Needs additional approval/safety workflow:

- finance education
- medical/wellness
- kids/family
- legal/regulatory content
- news/current-events documentary

## Required Upgrades

P0:

- Graph executor: the graph is now persisted into SQLite, the linear worker
  updates node status, and trusted graph executor handlers can render shots,
  run strong QA, and assemble final output. `/director/autonomous` can route
  long-form jobs through `graph_executor_long_form` when
  `CINEJELLY_ENABLE_GRAPH_LONG_FORM=1`; default-on production still requires
  paid benchmark validation.
- Implemented partial foundation: `production_graph_store.build_resume_plan()`
  now diagnoses failed/running/pending graph nodes, blocked shot dependencies,
  next resumable shot action, and assembly readiness. The production graph API
  returns this as `resume_plan`; the remaining work is a queue runner that
  executes this plan automatically.
- Implemented execution batch planner:
  `production_graph_store.build_execution_batch()` converts persisted graph
  state into dependency-safe worker tasks (`render_shot`, `retry_shot`,
  `run_qa`, `assemble_final`) and returns it from the production graph API as
  `execution_batch`. This is still not a full queue executor, but it is the
  missing contract a future executor can consume without re-planning the film.
- Implemented graph task leasing:
  `production_graph_store.claim_execution_batch()` marks ready graph tasks as
  `leased` with worker id, lease id, action, and TTL metadata so multiple
  workers do not claim the same shot/QA/assembly task. The API exposes this at
  `POST /api/v1/director/jobs/{job_id}/production-graph/claim`. The remaining
  work is a background executor that consumes leases and calls the per-shot
  render/QA/assembly handlers.
- Implemented lease expiry/release:
  `production_graph_store.release_expired_leases()` restores expired leased
  nodes to their previous executable status, and the API exposes this at
  `POST /api/v1/director/jobs/{job_id}/production-graph/leases/expire`. This
  prevents dead workers from locking long-form shots forever.
- Implemented flagged long-form graph execution: autonomous jobs with persisted
  production graphs can run through the graph executor loop behind
  `CINEJELLY_ENABLE_GRAPH_LONG_FORM=1`. The per-shot graph render path keeps
  local fallback files until assembly, so R2-disabled development runs do not
  lose intermediate clips before final concat.
- Implemented UI visibility: `JobResultModal` now fetches the production graph
  for autonomous jobs and shows a compact Production Inspector with runtime
  class, shot/chunk counts, done/running/pending/failed counts, next resumable
  shot, dependency blockers, and assembly readiness.
- Implemented model routing visibility: `backend/agent/model_scorecard.py`
  defines active Seedance/Wan routing tiers, use-cases, avoid-cases, cost,
  quad-modal support, and future Atlas candidates that require benchmarks. The
  autonomous capabilities endpoint now exposes this as `model_scorecard`.
- Implemented benchmark contract: `backend/agent/autonomous_benchmark_suite.py`
  turns all 23 canonical niche cases into a vendor-free production benchmark
  plan with runtime class, required references, recommended model route,
  pass/fail gates, evidence requirements, and candidate-model tests for
  InfiniteTalk, MMAudio, LipSync, Avatar OmniHuman, and Instant Character. This
  is exposed through `GET /api/v1/director/autonomous/benchmarks` and embedded
  in the capabilities endpoint as `benchmark_contract`.
- Implemented workflow contract: `backend/agent/autonomous_workflow_contract.py`
  exposes the autonomous source-of-truth pipeline as structured data through
  `GET /api/v1/director/autonomous/workflow`: one-click input contract,
  producer/director/editor/QA stages, artifacts, quality gates, runtime
  strategy, model routing, niche fit, and remaining production gaps.
- Implemented readiness report: `backend/agent/autonomous_readiness_report.py`
  composes capabilities, workflow, and benchmark contracts into a source-backed
  verdict exposed at `GET /api/v1/director/autonomous/readiness`. It answers
  whether the project is top-tier production grade today, which niches are
  strongest, and which build steps must happen next.
- Implemented benchmark result store: `backend/core/autonomous_benchmark_store.py`
  persists benchmark evidence rows in SQLite with case/model/niche, output URL,
  cost, latency, QA score, reviewer decision, and arbitrary evidence metadata.
  APIs under `GET/POST/PATCH /api/v1/director/autonomous/benchmarks/results`
  let future paid benchmark runs attach real AtlasCloud outputs to the
  benchmark contract.
- Implemented approved asset pins: `backend/core/autonomous_asset_pins.py`
  persists explicit continuity anchors for character, product, location, style,
  or voice by niche, market, series, priority, and status. APIs under
  `/api/v1/assets/autonomous-pins` let the app approve/tune/delete pins. Asset
  memory suggestions now return approved pins separately as `pinned`, while
  `POST /api/v1/director/autonomous` accepts `pinned_asset_ids` and injects
  active pin images into the Seedance reference pool within the 9-image cap.
  `/studio` now exposes pin selection, active/paused/archived filtering, role
  and priority tuning, and series/campaign filtering/assignment for continuity.
- Resume after restart for 5-30 minute jobs.
- Real visual/audio QA that evaluates sampled frames, identity, product,
  captions, audio loudness/silence/sync.
- Graph-aware retries: rerender failed shot/chunk and downstream chained shots
  only when required.
- Graph executor QA is now aligned with the linear worker QA stack: when a
  graph `run_qa` task executes through trusted paid handlers, it runs ffprobe,
  frame sampling, optional OCR text-artifact probing, visual reference
  similarity baseline, semantic frame QA, and `strong_quality_gate` before
  marking the QA node passed/warn/failed.

P1:

- Approved asset pinning UI: expand the current `/studio` memory controls into
  a full library for character, product, location, voice, and style anchors.
- Model benchmark harness per niche/market/cost before adding new Atlas models.
- Internal model router candidates:
  - `atlascloud/mmaudio-v2` for ambience/SFX pass
- `atlascloud/infinitetalk` for long multilingual talking-head/dialogue clips
- `atlascloud/multitalk` for lower-cost multi-person dialogue tests
- `bytedance/lipsync/audio-to-video` for existing video + TTS lip sync
  - `bytedance/avatar-omni-human` for portrait talking-head clips
  - `atlascloud/instant-character` for character anchors
  - Wan 2.5 fast / Veo / Kling only after benchmark evidence

P2:

- Optional production inspector panel on `/studio`: script, scene list, shot
  list, refs, cost, QA, retry/deferred reasons.
- Per-niche metrics: cost, QA failures, retry rate, user rating, caption CTR.
- More benchmark cases: 3-5 per niche instead of one canonical case.

P3:

- Shot/keyframe control layer for long-form: generate or request a first-frame
  keyframe per shot before video render, then use Seedance image-to-video or
  reference-to-video. This follows DrawVideo-style long-form control and gives
  better continuity than prompt-only video generation.
- Niche model scorecards: run the same benchmark against Seedance 2.0 Fast,
  Seedance 2.0 Reference, Wan, Vidu/Kling where available, and any Atlas
  dialogue/lip-sync/audio models. Store cost, latency, retry rate, identity
  score, audio sync score, and final user rating before enabling automatic
  routing.
- Creator prompt compiler: normalize every shot into the proven Seedance
  formula: asset job assignment, timeline, subject, physical action, camera,
  sound, constraints, and avoid-list. First version is implemented for
  per-shot Seedance renders; next step is adding benchmark scores for the
  compiler against raw LLM prompts.

## Product Principle

Keep UI one-click by default. Country/market selection should stay optional:
`Auto` should be default, but `VN`, `US`, `SEA`, `JP`, `KR`, and `Global`
should guide script, dialogue, proof style, captions, cultural pacing, and
voice selection when the user knows the target audience.
