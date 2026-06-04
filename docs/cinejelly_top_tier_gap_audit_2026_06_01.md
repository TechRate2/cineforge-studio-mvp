# CineJelly Top-Tier Autonomous Video Agent Gap Audit

Date: 2026-06-01

This audit answers the product question directly: whether CineForge Studio,
as upgraded toward CineJelly Autonomous Agent, is already comparable to the
best autonomous AI video / short-drama systems, and what still has to be built
or proven.

## Verdict

CineJelly is now a strong autonomous short-form foundation, but it is not yet
proven top-tier at the level of the best production systems. The architecture
is pointed in the right direction: one-click UI, niche/market playbooks,
multimodal reference intake, production decision preview, screenplay planning,
shot graph primitives, model routing, deterministic QA, retry planning, and
artifact persistence.

The missing proof is not another UI control. The missing proof is real
production evidence: paid AtlasCloud renders across the benchmark matrix,
human/QA ratings, long-form graph execution under failures, model-backed
identity/product/lip-sync checks, and a full asset library for reusable
characters, products, locations, style, and voice.

Practical status:

- 15-60s UGC/product/social videos: strongest current fit.
- 60-180s micro films: structurally supported, needs more real output QA.
- 5-10m short films: planning, graph primitives, scene memory, and an explicit
  long-form execution gate exist; default production should stay
  benchmark-gated until paid graph runs prove it.
- 10-30m episodes: architecture direction is correct, but not production-proven.

## Direct Product Answer

If the question is "is CineJelly already at the level of the best China-style
autonomous short-drama apps?", the honest answer is:

- Architecturally, yes, it is moving in the right shape: one idea in, references
  in, autonomous producer/director/screenwriter/storyboard/editor roles, model
  routing hidden from users, long-form decomposition, asset memory, QA, retry,
  and final distribution packaging.
- Evidence-wise, not yet. A top app claim requires real AtlasCloud output clips,
  cost/latency data, human review, and model-backed QA across many niches and
  durations.
- Product-wise, the next step is not to add manual controls. The next step is
  to make the autonomous system more inspectable, benchmarked, and self-correcting.

The current product should be positioned as an autonomous production agent in
validation, strongest for short-form commercial/social content. It should not be
marketed yet as a fully proven 30-minute film factory until long-form graph
benchmarks pass.

## Operator Summary

Current source-backed answer:

- Strongest fit today: 15-60s autonomous UGC, product, beauty, food, fashion,
  app/SaaS, tech, lifestyle, and sensory social videos with clear references.
- Usable with extra QA: 60-180s micro-films, real estate, travel, restaurant,
  education, music, automotive, fitness, and short narrative formats.
- Benchmark-gated: 5-10 minute short films. These must use screenplay, scene
  graph, 4-15s Seedance units, handoff frames, QA, retry, and final assembly.
- Research-gated: 10-30 minute episodes, heavy multi-character drama, factual
  documentary/news, and safety-sensitive claims.
- Market selector: keep `Auto` as default. Optional VN/US/JP/KR/Global should
  influence script, proof style, props, voice/dialogue, captions, and safety
  tone, not expose manual model settings.
- Ideal user input: a short idea plus references. Product/UGC should include
  product or creator images; location niches should include environment/video
  motion refs; long-form/drama should include character/location/style pins;
  visible Vietnamese dialogue should include a clean voice/audio sample and
  stay benchmark/review-gated before top-tier claims.

The API version of this answer is exposed as
`operator_summary` in `GET /api/v1/director/autonomous/production-audit`.

## Current Runtime Verification

Local verification on 2026-06-01 confirms the source is running as an
autonomous-first system, not just a static design document:

- Frontend `/studio`: `200`.
- Backend `/health`: `200`.
- Backend compile: `python -m compileall -q backend` passed.
- Frontend typecheck: `node .\scripts\typecheck.mjs` passed.
- Autonomous backend smoke suite: `python backend\scripts\test_agent.py` passed
  with 90 tests.
- Autonomous UI guard: `node .\scripts\check-autonomous-ui.mjs` passed,
  proving `/studio` does not import the legacy manual Video Agent surface
  (`PromptCardV2`, `ReferenceZones`, manual settings, Enhance flow, manual
  DirectorPlan flow, or manual shot/audio/master-board state).
- Autonomous Next API proxy endpoints now use `http://127.0.0.1:8001` as the
  dev fallback and were smoke checked through `/api/v1/director/autonomous/*`;
  capability matrix, research, Atlas model matrix, paid benchmark manifest,
  niche launch matrix, playbook catalog, review rubric, and top-tier gate all
  returned `200`.
- `/studio` production decision UX is now autonomous-first: the main surface
  shows a compact agent decision and production intelligence summary, while
  Seedance formula, reference allocation, segment inspector, route scorecard,
  cinematic grammar, workflow, and QA gates live behind an expandable
  `Open production inspector` section.
- Vietnamese spoken-language detection was tightened so briefs such as
  "noi tieng Viet", "giong noi", "thuyet minh", "loi dan", and "doc thoai"
  trigger the dialogue route instead of being treated as silent visual clips.
- Vietnamese diacritic briefs are now covered by regression test; a prompt like
  "thi truong Viet Nam" plus "noi tieng Viet tu nhien" routes to `vn`,
  `Vietnamese`, and `dialogue_required=true`.
- Competitive research map now tracks 21 patterns, including CANVAS-style
  continuity dimensions, StoryBlender-style continuity memory graphs,
  Camera Artist-style cinematography agents, Codeywood-style producer gates,
  VibeFrame-style agent-readable reports, and recent Seedance structured
  shot-list creator reports.

The 5-minute Vietnamese short-film probe:

`Tao video 5 phut phim ngan ve co gai ban banh mi o Sai Gon phat hien bi mat
gia dinh, cinematic, co thoai tieng Viet.`

resolved to:

- niche: `drama`
- market: `vn`
- runtime: `short_film`
- target duration: `300s`
- graph required: `true`
- dialogue required: `true`
- dialogue candidate: `atlascloud/multitalk`
- script asset SOP enabled: `true`
- missing top-tier anchors:
  `character_visual_anchor`, `product_or_prop_visual_anchor`,
  `location_visual_anchor`, `motion_or_camera_reference`,
  `consented_voice_or_tts_audio`

This is the correct behavior for a serious autonomous agent: it does not
pretend a 5-minute narrative is production-ready from one text prompt. It
classifies the job as drama/short-film, requires a graph route, detects
Vietnamese dialogue, and asks for or auto-generates the assets that top
short-drama workflows need before premium render.

## 2026 China/Seedance Workflow Patterns To Match

The strongest current Seedance/China-style workflows converge on the same
production doctrine:

- Script-to-asset-to-keyframe-to-video, not prompt-to-video.
- Every segment has an explicit omni prompt with ordered `@image`, `@video`,
  and `@audio` bindings.
- Image references anchor character/product/style; video references transfer
  camera, motion, pacing, or edit rhythm; audio references guide rhythm, SFX,
  voice, or dialogue timing.
- Long videos are built from 4-15s units with screenplay/scene memory and
  previous-frame or first/last-frame handoffs.
- Character/product/location assets must become reusable production memory,
  not one-off uploads.
- A clean user UI can stay one-click, but the admin/debug layer must expose
  generated segment prompts, reference roles, graph nodes, QA scores, retries,
  cost, latency, and benchmark evidence.

Recent source alignment:

- `autonomous_competitive_research.py` now includes AtlasCloud `/docs`,
  `/docs/models/video`, predictions, uploadMedia, plus creator workflow reports
  from X around assigning explicit jobs to every image/video/audio reference.
- `autonomous_competitive_research.py` now includes LocalMiniDrama, Moyin
  Creator, MapleShaw Seedance prompt skill, and ComfyUI Seedance 2.0 docs.
- `seedance_prompt_compiler.py`, `seedance_reference_allocation.py`, and
  `scene_generation_agent.py` already implement explicit reference roles and
  Seedance-friendly prompt contracts.
- `autonomous_production_decision.py` now exposes a vendor-free
  `seedance_segment_inspector` so `/studio` can preview the first 4-15s
  Seedance units, each with action, camera, sound, continuity anchor,
  reference jobs, model route, and QA checks before paid render.
- `autonomous_production_decision.py` also exposes an
  `autonomous_input_upgrade_plan` that translates reference sufficiency,
  niche recipe, route quality, and segment preview into user-facing guidance:
  renderable now, top-tier ready or not, missing minimum refs, missing
  best-quality refs, and priority actions.
- `storyboard_board.py`, `scene_memory_pack.py`, and
  `continuity_handoff_policy.py` cover board anchors and previous-frame
  handoff logic, but these must still be A/B benchmarked with paid outputs.
- The `/studio` UI now includes a read-only expandable production inspector
  for prompt/reference/segment/model-route intelligence while keeping the
  primary user flow one-click. The next UI/admin improvement is richer
  benchmark evidence review and Asset Library organization, not manual
  model/settings controls.

Creator reports from X reinforce the same engineering rule: the product should
not expose model knobs to users, but the agent must internally assign a job to
each asset. A good Seedance segment prompt should contain:

`asset role -> time beat -> action -> camera -> sound -> constraints`

For CineJelly this maps to:

- image refs: character, product, location, style, first/last frame
- video refs: motion, camera movement, blocking, transition rhythm
- audio refs: voice tone, ambience, beat, SFX, dialogue timing
- text: story logic, timeline, action, camera, dialogue, constraints

The current source already carries those roles through
`seedance_reference_allocation.py` and `seedance_prompt_compiler.py`; the
remaining proof is real paid output evidence and visual/audio QA, not more
manual UI.

## Current Workflow, Step By Step

1. `/studio` receives one idea, optional runtime, optional market, and optional
   image/video/audio references.
2. The frontend uploads media and calls `POST /api/v1/director/autonomous`.
3. `autonomous_production_decision.py` performs a vendor-free preview:
   niche, target market, runtime class, dialogue need, model route, graph need,
   benchmark status, reference sufficiency, script asset SOP, and responsible
   content gate.
4. `AutonomousDirector` runs planner, market playbook, niche playbook,
   reference role tagging, storyboard, director, and editor skills.
5. Long-form inputs trigger screenplay/scene planning: acts, scene blueprints,
   dramatic questions, visual hooks, handoffs, and Seedance render-unit
   estimates.
6. A `DirectorPlan` and Production Bible are created with characters, products,
   style, audio, setting, constraints, reference jobs, shot list, caption, and
   hashtags.
7. `autonomous_preflight_gate.py` checks responsible content, long-form graph
   readiness, screenplay structure, story quality, niche fit, cross-shot
   coherence, reference sufficiency, script asset SOP, Seedance shot limits,
   and model constraints.
8. The worker routes internally across Seedance 2.0 Fast Reference, premium
   Reference, I2V/T2V, Wan fallback, and benchmark-locked dialogue candidates.
9. Each model call should stay inside the 4-15s Seedance unit doctrine; longer
   videos become many graph/shot units with handoff frames and scene memory.
10. Rendered clips are downloaded, probed, optionally retried, assembled,
    captioned, uploaded, and shown in `JobResultModal` with production audit
    metadata.

## Niche Fit Today

Strongest now, assuming clear references:

- UGC review
- beauty
- food
- ecommerce catalog
- fashion
- ASMR
- app/SaaS
- tech
- lifestyle

Usable but should be benchmarked before premium claims:

- drama / short film
- education
- real estate
- restaurant/hospitality
- travel
- automotive
- fitness
- gaming
- music video
- anime/comic

Review-locked or safety-sensitive:

- finance education
- medical/wellness
- kids/family
- documentary/news/current events
- celebrity likeness, known IP, voice cloning, public figures

The agent should keep `Auto` target market as default and offer VN/US/SEA/JP/KR
/Global as optional guidance. Market should affect story culture, dialogue,
caption language, proof style, claim tone, props, and safety policy; it should
not reintroduce manual model settings.

## 5-Minute And 30-Minute Production Design

For a 5-minute request, the agent should not call Seedance once. The correct
workflow is:

1. Infer market, niche, audience, platform, and runtime class.
2. Write a logline, treatment, promise, conflict, and payoff.
3. Split into 3 acts and roughly 5 scenes.
4. Give each scene a purpose, dramatic question, visual hook, continuity anchor,
   turning point, and handoff image.
5. Split each 60s scene into about five 12s Seedance units.
6. Bind references per unit: character/product/style image refs, prior scene
   final frame, optional video motion ref, optional audio rhythm/SFX ref.
7. Render only 4-15s units.
8. QA each unit for identity, product, motion, prompt adherence, audio, and
   transition continuity.
9. Retry only failed units.
10. Assemble scenes, captions, hashtags, cover frame, and final MP4.

For a 30-minute request, the same idea must scale into an episode graph:

- 5-8 acts or chapters.
- 25-40 scenes.
- 120-180 Seedance units.
- Persistent character/product/location/style/voice bible.
- Graph executor required, not optional.
- Crash-safe render nodes, chunk-level resume, and cost ceiling.
- Human or model-backed checkpoints after every act.

Without this graph discipline, long video will drift: characters change, product
geometry shifts, transitions break, and the story becomes a sequence of attractive
but disconnected clips.

## Niche Readiness For Launch

Recommended launch order:

| Tier | Niches | Why |
| --- | --- | --- |
| Sell first | UGC review, beauty, food, ecommerce, fashion, app/SaaS, tech, lifestyle | Strong visual proof, short shots, easy reference anchoring, low narrative complexity. |
| Sell after benchmark | real estate, travel, restaurant/hospitality, automotive, fitness, education, music video | Viable, but needs better continuity, camera rhythm, and audio QA. |
| Gate behind review | drama/short film, documentary, finance, medical wellness, kids/family | Higher story, safety, claim, dialogue, and identity risks. |
| R&D only for now | 10-30m episodes, heavy multi-character drama, news/current events | Requires proven graph executor, asset library, and stricter legal/safety review. |

The strongest near-term market wedge is not "make every video". It is:

- one-click Vietnamese/global UGC and product ads;
- one-click beauty/food/ecommerce/fashion videos with strong references;
- short brand mini-films up to 60-180 seconds;
- benchmark-gated 5-minute short films.

## Current Source-Backed Workflow

1. Intake: `/studio` accepts one idea, optional runtime, optional market, and
   image/video/audio references. The UI remains autonomous-only.
2. Production decision preview: `POST /director/autonomous/production-decision`
   predicts niche, runtime class, market playbook, model route, dialogue route,
   Seedance caps, route quality scorecard, workflow steps, and QA gates before
   a paid render.
3. Planner: infers niche, hook, mood, target duration, aspect, and audio needs.
4. Market playbook: localizes language, dialogue style, proof style, caption
   tone, and cultural cues for Auto/VN/US/SEA/JP/KR/Global.
5. Reference manifest: image/video/audio refs receive production jobs. Images
   anchor identity/product/style, videos anchor motion/camera, audio anchors
   rhythm/SFX/dialogue.
6. Niche/runtime director: converts the selected niche and requested duration
   into a directing contract: story shape, opening move, scene architecture,
  Seedance unit count, editorial rhythm, reference contract, market
  localization, QA focus, and risk register. This keeps a 5 minute drama, a
  30s product proof, and a 15 minute episode from using the same generic flow.
7. Niche production recipe: the system now turns each niche/runtime into a
   concrete recipe for opening move, story engine, framing language, edit
   shape, sound shape, reference priority, duration scaling, Seedance prompt
   blocks, QA checks, and common failure modes.
8. Treatment and screenplay: the system builds production treatment, scene
   structure, screenplay beats, and long-form runtime structure.
9. Cinematic grammar: the source now builds a per-niche/runtime filming
   contract with story archetype, shot palette, transition logic, editor
   pacing, sound strategy, prompt directives, anti-patterns, and QA questions.
   This gives each niche a concrete film language instead of only keywords.
10. Director plan: creates a Production Bible, shot list, reference policy, and
   production graph metadata.
   Long-form screenplay scene lint rejects scenes that lack purpose, conflict,
   turning point, continuity anchor, or a handoff image.
11. Long-form execution gate: for micro-film/short-film/episode routes, the
   source now checks whether the production graph, scene memory pack, scene
   bridges, last-frame handoffs, graph executor flag, and benchmark evidence
   are ready. It returns `default_route_allowed`, `graph_executor_ready`,
   blockers, and required actions before any long-form route is treated as a
   default production path.
12. Prompt compiler: converts each shot into Seedance-ready reference jobs,
   timeline, environment, visual style, subject/action, camera/sound, shot
   contract, director intent, and constraints. The contract explicitly locks
   reference roles, one filmable action, continuity handoff, identity/product
   geometry, no unrequested scene jumps, and market/niche safety constraints.
   Pre-render Seedance shot lint rejects overlong, vague, or overloaded shots
   before paid render.
   Production decision now also exposes a segment inspector preview, showing
   the first planned Seedance units with duration, action, camera, references,
   continuity anchor, model route, and QA checks before vendor spend.
   It also exposes an autonomous input upgrade plan, so the UI can tell the
   user which references or approved pins would improve the result without
   reintroducing manual model/settings controls.
13. Model router: routes internally. The user does not choose models. Seedance
   2.0 Fast Reference is the default visual route, Seedance 2.0 Reference is
   premium for high-fidelity hero shots, i2v is used for continuity anchors,
   and dialogue candidates remain benchmark-gated.
14. Render worker: submits AtlasCloud async jobs, polls results, renders per
    shot/chunk, and preserves metadata.
15. QA/retry: probes duration/audio/frame/reference/semantic checks and builds
    retry plans for failed scopes.
16. Assembly/editor: concatenates clips, produces final MP4, caption, hashtags,
    production artifact, and job result UI.

## Current Inspectable Contracts

The source now exposes the audit as API contracts, so product claims can be
checked against code instead of relying on README text.

- `GET /api/v1/director/autonomous/workflow`: source-of-truth pipeline stages,
  agent roles, runtime strategy, model routing, and known production gaps.
- `GET /api/v1/director/autonomous/readiness`: current verdict, benchmark
  coverage, best use cases, and next build order.
- `GET /api/v1/director/autonomous/capabilities`: supported niches, readiness
  buckets, model scorecard, benchmark contract, and next required upgrades.
- `GET /api/v1/director/autonomous/capability-matrix`: runtime-by-niche
  matrix with best niches, QA-required niches, review-required niches,
  reference contracts, long-form policy, and Seedance 2.0 best practices.
- `GET /api/v1/director/autonomous/niche-launch-matrix`: operational launch
  matrix that separates sell-first niches, benchmark-next niches, and
  review-locked niches with default duration envelopes and proof gates.
- `GET /api/v1/director/autonomous/atlas-model-matrix`: internal AtlasCloud
  model integration matrix. It keeps the UI autonomous-only while documenting
  active Seedance/Wan routes, benchmark-locked dialogue/audio/challenger
  models, Vietnamese dialogue priorities, cheap experiment candidates, and
  promotion gates.
- `GET /api/v1/director/autonomous/niche-playbook-catalog`: all-niche
  production catalog covering script pattern, reference contract, duration
  scaling, Seedance prompt contract, QA focus, and launch posture for every
  supported niche.
- `GET /api/v1/director/autonomous/top-tier-completion-gate`: strict parity
  gate that lists each requirement for claiming top-app quality, the current
  evidence, blockers, and the next proof order. This gate intentionally returns
  `top_app_parity_proven=false` until paid AtlasCloud evidence, model-backed QA,
  dialogue benchmarks, and long-form graph runs are stored and promoted.
- `GET /api/v1/director/autonomous/paid-benchmark-manifest`: concrete paid-run
  manifest for the next AtlasCloud batch, including two outputs per route,
  render payload blueprints, benchmark row creation payloads, post-render patch
  payloads, reviewer questions, and promotion targets.
  It now also includes `operator_runbook_phases`: preflight, paid render,
  QA/review, and promotion-or-rollback. This keeps route promotion tied to
  real evidence instead of attractive one-off outputs.
- `npm run benchmark:runbook`: CLI dry-run for the paid benchmark manifest. It
  reads the live API, prints the first benchmark runs, estimated spend, planned
  row creation path, render payload blueprint, post-render patch path, and
  required evidence keys. It is intentionally a runbook; it does not call paid
  AtlasCloud renders by itself.
- `npm run operator:report`: CLI Markdown report generated from live API. It
  summarizes the current top-app comparison, workflow stages, duration policy,
  niche fit, Seedance/model policy, long-form rule, paid benchmark batch,
  live niche audit, research position, next upgrades, completion gate, and
  evidence endpoints.
- `npm run decision:preview`: CLI dry-run for one arbitrary idea. Set
  `CINEJELLY_IDEA`, `CINEJELLY_DURATION`, `CINEJELLY_MARKET`,
  `CINEJELLY_NICHE`, and reference-count env vars to inspect the inferred
  niche, runtime, market, model route, dialogue lane, reference sufficiency,
  Seedance units, director strategy, input-upgrade advice, and safety gate
  before spending on a real render.
- `npm run niche:audit`: CLI dry-run that scans the full niche playbook catalog
  through live `production-decision` calls for 30s and 5m routes. It prints the
  inferred runtime, visual route, graph requirement, dialogue requirement,
  reference status, auto-route state, review state, and blocker state for each
  niche without calling AtlasCloud.
- `GET /api/v1/director/autonomous/niche-audit`: API form of the same all-niche
  routing audit. It returns summary counts plus `short_30s` and `long_5m` rows
  for admin/UI/report surfaces without vendor calls.
- `GET /api/v1/director/autonomous/benchmark-review-rubric`: weighted human or
  model-backed review rubric that explains how `qa_score` should be produced
  before a benchmark row can be approved and promoted.
- `POST/PATCH /api/v1/director/autonomous/benchmarks/results`: accepts optional
  `review_scores` and `review_hard_failures`; backend computes weighted
  `qa_score`, attaches the exact rubric/score evidence, and keeps failed
  dimensions or hard failures from promoting a route.
- `GET /api/v1/director/autonomous/production-audit`: compact executive audit:
  whether top-tier is proven, how one autonomous run works, strongest niches,
  long-form doctrine, external patterns to keep matching, and evidence gates.
- `GET /api/v1/director/autonomous/operator-brief`: compact operator answer
  composed from the production audit. It gives the current level, one-run
  workflow, strongest niches, duration policy, market policy, model policy, and
  evidence endpoints without asking the UI to parse the full audit payload.
  It also includes `top_app_comparison`, `production_workflow_steps`,
  `niche_fit_table`, `next_upgrade_order`, and `research_position` so an
  operator can answer whether CineJelly is at China/top-app parity without
  overclaiming before paid benchmark evidence exists.
- `POST /api/v1/director/autonomous/production-decision`: per-idea preview of
  niche, market, runtime, model route, dialogue route, reference sufficiency,
  niche execution rubric, niche/runtime director contract, niche production
  recipe, cinematic grammar, Seedance segment inspector, autonomous input
  upgrade plan, route quality scorecard, long-form execution gate, QA gates,
  scene preview, and graph requirement.
- `scripts/check-autonomous-ui.mjs`: regression guard for the one-click UI. It
  fails if `/studio` reintroduces the old manual Video Agent card, manual
  reference zones, model/settings panel, Enhance action, manual DirectorPlan
  flow, or manual shot/audio/master-board state.

Current smoke status from the source-backed audit:

- `top_tier_production_grade`: false.
- `current_level`: strong autonomous short-form foundation.
- `best_niches_now`: 9.
- `workflow_in_one_run`: 8 steps.
- `what_the_agent_does_today`: 10 agent stages.
- `evidence_blocking_top_tier_claim.required_evidence`: now includes real
  output URL, Seedance prompt formula, per-shot prompts, reference manifest,
  production graph snapshot, scene memory, continuity handoffs, segment
  inspector, visual/semantic/text QA reports, cost/latency, accepted minute
  cost, benchmark review score, QA frames, audio/identity notes, reviewer
  notes, and retry count.

## Seedance 2.0 Contract To Preserve

The current source follows the important Seedance 2.0 constraints:

- Generation units are 4-15 seconds, not one long prompt.
- Up to 9 image references.
- Up to 3 video references.
- Up to 3 audio references.
- Up to 12 mixed reference files total.
- Text/image/video/audio can be combined for omni-reference workflows.
- Per-shot prompts should stay sectioned: reference jobs, timeline,
  environment, visual style, shot direction, camera/sound, shot contract,
  director intent, and constraints.
- Paid benchmark evidence must store the exact Seedance prompt formula that
  produced the accepted output; otherwise the route cannot be reproduced or
  promoted safely.
- Each reference must have one assigned job. Do not let identity, product,
  camera, and audio roles blend together.
- Each shot prompt must state one physically filmable action and preserve
  identity, product geometry, wardrobe, lighting, and color grade.
- Long-form videos must be decomposed into shots, scenes, chunks, QA, retry,
  and assembly.

This means the right long-form design is not "ask Seedance for a 5 minute
video". The correct design is:

logline -> treatment -> screenplay -> scene bible -> shot graph -> 4-15s
Seedance calls -> QA/retry -> assembly -> audio/caption/final polish.

## Best Current Niches

High readiness:

- UGC review
- beauty
- food
- ecommerce catalog
- fashion
- ASMR
- app/SaaS demo
- tech/product demo
- lifestyle

These work well because they benefit from short, visual, proof-driven shots and
strong references. They do not require complex dialogue or long narrative arcs.

Medium readiness:

- drama / short film
- education / explainer
- automotive
- fitness
- gaming
- music video
- anime/comic
- real estate
- restaurant/hospitality
- travel

These are viable, but need stronger continuity QA, asset pins, and real
benchmark clips before top-tier claims.

Review required:

- documentary / current events
- finance education
- medical wellness
- kids/family

These should keep autonomous planning, but require safety/claims review and
stronger evidence handling.

## Top-Tier Pattern Comparison

ByteDance / Moyin short-drama agent pattern:

- What it proves: the best China-style short-drama systems are not only video
  generators; they are end-to-end production crews that infer plot, characters,
  shots, camera, voice, music, editing, and delivery from sparse input.
- CineJelly status: autonomous planner/storyboard/director/editor, niche
  playbooks, production treatment, production decision preview, and graph
  primitives already follow this direction.
- Required upgrade: add real AtlasCloud benchmark outputs, stronger character
  bible enforcement, and model-backed story/visual/audio critics before
  claiming "top app" quality.

Jellyfish pattern:

- What it proves: short-drama quality depends on asset management and reusable
  production objects, not only prompts.
- CineJelly status: asset pins exist, `/studio` can approve image refs as
  memory, filter active/paused/archived pins, pause/archive/activate pins, and
  edit role/priority plus series/campaign key for active pins before reusing
  them across jobs.
- Required upgrade: character/product/location/style/voice libraries with
  market/niche metadata editing, batch cleanup, and richer reuse across jobs.

MovieAgent pattern:

- What it proves: long-form needs script + character bank + multi-agent scene
  planning before generation.
- CineJelly status: screenplay and scene planning exist; long-form execution is
  graph-gated.
- Required upgrade: make screenplay/scene/chunk graph the default path after
  paid long-form benchmarks pass.

CANVAS / long-horizon storyboarding pattern:

- What it proves: long videos need an explicit continuity-aware storyboard and
  scene graph before any clip generation, otherwise identity, location, and
  story causality drift.
- CineJelly status: scene blueprints, screenplay plan, continuity anchors,
  production graph persistence, scene lint, and `scene_memory_pack` exist.
- Remaining: use visual embedding checks after render and benchmark scene-bridge
  failure rates on paid 5-10 minute jobs.

DrawVideo / agentic evaluation pattern:

- What it proves: autonomous video systems improve when generation and
  evaluation are separated into repeated plan-generate-critic-retry loops.
- CineJelly status: deterministic preflight, Seedance shot lint, screenplay
  scene lint, strong QA gate, semantic QA, retry planner, and graph retry
  primitives exist.
- Required upgrade: add model-backed critics for story coherence, face/product
  identity, lip-sync, and multilingual text artifacts.

DirectorBench / CameraBench pattern:

- What it proves: "cinematic" quality can be evaluated through director-like
  dimensions: shot size, camera motion, subject action, temporal coherence, and
  instruction following.
- CineJelly status: prompt compiler and linter already require concrete
  subject/action/setting/camera/audio fields.
- Required upgrade: add a benchmark rubric that scores camera language and
  edit rhythm per niche, not only whether a clip exists.

Co-Director / GenAD-Bench pattern:

- What it proves: strong agentic video systems explore multiple creative
  directions, then use multimodal self-refinement to reduce identity drift,
  brand/product drift, and weak audience fit.
- CineJelly status: niche/market playbooks, producer story critic, and
  `creative_treatment_search` now compare multiple deterministic director
  treatments before paid render. The selected treatment is injected into planner
  notes, Production Bible constraints, production treatment metadata, shot
  dynamic descriptions, production preview, and job inspector; alternates are
  preserved for future regeneration flows.
- Required upgrade: make the next generation model-backed: score generated
  thumbnails/frames for asset fidelity, demographic fit, marketing appeal, and
  visual quality after the first benchmark renders.

MSVBench / multi-shot evaluation pattern:

- What it proves: multi-shot videos need hierarchical scripts, story assets,
  and cross-shot metrics; single-shot quality is not enough.
- CineJelly status: scene blueprints, screenplay planning, production graph
  artifacts, and `cross_shot_diagnostic` exist. The preflight gate now scores
  transition continuity, subject/product persistence, edit rhythm, and narrative
  progression across the assembled shot list.
- Required upgrade: calibrate these deterministic cross-shot metrics with real
  rendered clips and model/human review, especially for long-form transition
  quality.

ComfyUI / workflow-graph pattern:

- What it proves: production reliability improves when every expensive step is
  a resumable node with inputs, outputs, status, retry policy, and artifacts.
- CineJelly status: production graph store and executor primitives exist; long
  jobs can run behind `CINEJELLY_ENABLE_GRAPH_LONG_FORM=1`.
- Required upgrade: promote graph execution to default only after crash/retry
  tests with real paid renders.

MCP / AtlasCloud skills pattern:

- What it proves: production agents should have tool access to model docs,
  model invocation, benchmarks, artifact inspection, and deployment workflows
  instead of relying on static prompt knowledge.
- CineJelly status: routes and docs can expose readiness/benchmark/workflow
  state, but the local agent does not yet use AtlasCloud MCP/CLI directly.
- Required upgrade: add an internal benchmark/admin workflow that can run Atlas
  test jobs, attach evidence, and update promotion gates.

ViMax / AI-Creator pattern:

- What it proves: director, screenwriter, producer, and generator should be
  separate roles with explicit handoff artifacts.
- CineJelly status: modular skills and role contracts exist.
- Required upgrade: persist and expose every artifact for inspection and
  selective regeneration.

Codeywood pattern:

- What it proves: sparse input becomes episodic content through skills, quality
  gates, and reference-based consistency.
- CineJelly status: similar skill structure exists; producer/story critic,
  screenplay lint, reference sufficiency, and preflight gates are implemented.
- Required upgrade: benchmark a stronger writers-room pass for 3-30m jobs and
  keep the best screenplay arc before paid render.

CANVAS / StoryBlender / Camera Artist pattern:

- What it proves: top long-form systems need explicit character, background,
  prop, location, and camera-language continuity dimensions, plus a memory
  graph that decouples global assets from per-shot variables.
- CineJelly status: scene memory pack, continuity handoff policy, cross-shot
  diagnostic, cinematic grammar contract, and benchmark review rubric exist.
- Required upgrade: store per-dimension continuity evidence in paid benchmark
  rows and block route promotion if any continuity dimension is below bar.

VibeFrame pattern:

- What it proves: agentic video workflows are easier to resume and debug when
  storyboard, design, graph, QA, and build reports are persisted as artifacts.
- CineJelly status: production artifacts, graph store, and benchmark evidence
  pack builder exist; `production_artifacts` now also writes a concise
  `cinejelly.agent_readable_production_report.v1` beside each snapshot and the
  backend exposes `/api/v1/director/jobs/{job_id}/production-report`. The
  JobResultModal also surfaces a Production Report panel with report/evidence
  links when a job artifact exists.
- Required upgrade: attach production report links to benchmark rows so
  reviewers can inspect the exact storyboard/design/graph/QA context during
  route promotion.
- Current benchmark evidence pack builder now includes
  `agent_readable_production_report` supporting evidence with links to the
  production report, raw artifact, and benchmark evidence pack for the job.

Seedance-specific creator pattern:

- What it proves: prompt structure must bind references explicitly and each
  shot must have subject, one physical action, setting, camera, light, motion,
  and audio cue.
- CineJelly status: screenplay scene lint, prompt compiler, playbooks,
  `seedance_reference_allocation`, and deterministic Seedance shot lint now
  enforce this direction before paid render. The production preview exposes how
  image/video/audio references map to character, product, style, camera motion,
  pacing, beat, SFX, dialogue, and long-form handoff jobs.
- Required upgrade: extend linting into model-backed story/visual critique after
  first benchmark renders.

Recent creator workflow pattern:

- Public Seedance creator discussions in May 2026 are converging on the same
  rule: stop using blob prompts; use structured shot lists, stable subject
  definitions, explicit reference tags, camera/lens/SFX per shot, and last-frame
  chaining for longer work.
- CineJelly status: this is already mostly encoded in prompt compiler, scene
  preview, reference policy, and continuity handoff logic.
- Required upgrade: make the generated shot list and reference tags easy to
  inspect and selectively regenerate from the JobResultModal/admin inspector.

## Recommended Model Routing

Keep Seedance 2.0 as the visual director:

- `seedance_2_0_fast_ref`: default route for most jobs with refs.
- `seedance_2_0_ref`: premium route for beauty, fashion, food, product hero,
  high-fidelity cinematic shots.
- `seedance_2_0_fast_i2v` / `seedance_2_0_i2v`: continuity route from previous
  last frame or keyframe.
- `seedance_2_0_fast_t2v`: only for no-reference drafts or abstract b-roll.
- `wan_2_7_i2v`: narrow fallback for short driven-audio dialogue.

Benchmark-gated candidates:

- InfiniteTalk: long single-speaker presenter/dialogue.
- MultiTalk: multi-person dialogue.
- MMAudio: post-render ambience/SFX.
- ByteDance LipSync: post-render lip-sync repair.
- OmniHuman/avatar route: portrait dialogue.
- Instant Character: reusable character sheet generation.
- Video upscaler: final polish only after QA.
- Wan 2.2 Turbo: cheap 5s image-to-video iteration and motion tests, not the
  primary cinematic route.
- Veo 3.1 Lite/Fast: benchmark for cinematic polish and brand ads when
  reference count is low.
- Kling 3.0/O3: benchmark for multilingual lip-sync, custom subject workflows,
  and high-consistency skits when cost is acceptable.

Do not auto-route these candidates until at least 2 real approved outputs per
model/niche/runtime route pass QA score >= 8.0 with real output URLs.

Recommended cheap-but-safe route for Vietnamese/global dialogue:

- Keep Seedance as the visual coverage model for cinematic movement, product,
  setting, and non-speaking story beats.
- Use Wan 2.7 only as a narrow fallback for short audio-driven lip-sync inserts.
- Benchmark InfiniteTalk for long single-speaker Vietnamese presenter scenes.
- Benchmark MultiTalk for two-person short-drama dialogue where cost matters.
- Use ByteDance LipSync only as a repair/post-process lane, not as the primary
  story generator.
- Use MMAudio only after visual QA passes, so sound design does not hide bad
  visuals.

## Country / Market Setting

Keep the current optional target market selector. Do not force users to choose
too much.

Recommended design:

- Default: Auto.
- Optional: VN, US, SEA, JP, KR, Global.
- Separate voice/language only when the user cares about spoken output.

The market should influence:

- hook style
- caption language
- dialogue naturalness
- proof style
- setting/props/behavior
- pacing and CTA tone

It should not become a manual country-heavy form. The agent should infer most
of this from idea + references.

## Upgrade Roadmap

P0: Paid benchmark evidence

- Render the 23 canonical benchmark cases.
- Store output URL, model, cost, latency, QA frames, QA score, reviewer rating.
- Promote routes only through `benchmark_promotion_policy`.
- Add one benchmark row per route, not only per niche:
  - Seedance Fast Reference for default visual coverage.
  - Seedance Premium Reference for hero/product/fashion/beauty shots.
  - Seedance i2v continuity for previous-frame chaining.
  - InfiniteTalk for single-speaker Vietnamese presenter.
  - ByteDance LipSync repair for visible dialogue.
  - Wan 2.2 Turbo for cheap motion draft.
  - Veo 3.1 Lite/Fast for cinematic ad polish.
  - Kling 3.0/O3 for high-consistency multilingual subject workflows.
- Start with these paid benchmark batches:
  - VN UGC/product: `ugc_review`, `beauty`, `food`, `app_saas`.
  - Global cinematic: `drama`, `fashion`, `travel`, `real_estate`.
  - Dialogue: VN education presenter, two-speaker drama, product testimonial.
  - Safety/review: `finance_education`, `medical_wellness`, `documentary`.

P0: Long-form graph validation

- Run 5m and 10m jobs with `CINEJELLY_ENABLE_GRAPH_LONG_FORM=1`.
- Test crash/retry/resume at shot and chunk level.
- Promote graph executor to default only after paid evidence passes.

P1: Asset Library

- Implemented: `/studio` can approve refs as character/product/style pins.
- Implemented: filter active/paused/archived memory pins and pause/archive/
  activate them.
- Implemented: edit role and priority for active memory pins.
- Implemented: filter memory by series/campaign key and assign existing active
  pins to the current series.
- Implemented: autonomous render can safely auto-select approved active memory
  pins by niche, market, series, priority, and idea-token match while explicit
  user-selected pins keep priority.
- Implemented: `seedance_reference_allocation` previews how uploaded and pinned
  references will be used against Seedance 2.0 caps: 9 image refs, 3 video refs,
  3 audio refs, and 12 mixed refs.
- Remaining: support market/niche metadata editing, location/voice
  anchors, batch cleanup, and dedicated library views.
- Inject the strongest pins automatically into reference policy.

P1: Model-backed QA

- Add face/product embedding similarity.
- Add robust OCR/text artifact checks for multilingual outputs.
- Add lip-sync scoring for visible dialogue.
- Add audio loudness/silence/SFX timing thresholds.
- Implemented: deterministic producer story critic scoring:
  - hook clarity in first 3 seconds
  - scene causality
  - visual payoff
  - niche-specific proof
  - market/caption fit
- Implemented: deterministic cross-shot diagnostic scoring:
  - transition continuity between adjacent shared-subject shots
  - character/product persistence through reference bindings
  - edit rhythm and repeated camera-language risk
  - narrative progression from hook to payoff
- Remaining: add model-backed story/visual critique after benchmark renders.

P1: Prompt and screenplay lints

- Implemented: fail shots that contain more than one physical action.
- Implemented: fail overlong 15s+ Seedance shots.
- Implemented: warn/fail generic or missing subject/action/camera/setting/audio
  fields before render.
- Implemented: fail long-form scenes without purpose, conflict/stakes, turning
  point, continuity anchor, handoff image, or matching screenplay scene.
- Implemented: audit and auto-apply required previous-frame handoffs for
  adjacent shots that share character/product/reference anchors, and surface
  the policy in preflight/job result UI.
- Remaining: tune critic thresholds with paid benchmark reviewer scores.

P2: Admin production inspector

- Expose treatment, screenplay, scene graph, shot graph, prompts, refs, QA,
  retries, cost, latency, and model routes for each job.

P2: First/last-frame continuity builder

- Implemented: `scene_memory_pack` persists scene purpose, opening/closing image
  intent, reference priorities, Seedance unit policy, shot-to-scene mapping, and
  scene bridge policy inside production artifacts and production graph nodes.
- Save each shot's last frame as the next shot's optional i2v continuity anchor.
- Use selected keyframes for character wardrobe, product angle, and location
  layout reuse.
- Add automated checks that a next shot has a matching continuity handoff when
  the scene contains the same character/product/location.

P2: Distribution intelligence

- Implemented: per-platform package generation for TikTok/Reels/Shorts/
  YouTube long/Xiaohongshu/Bilibili with caption limits, hashtag ranges,
  title hint, cover-frame cue, CTA style, posting hint, and platform checks.
- Remaining: calibrate package rules with real account analytics and add
  platform-specific thumbnail/cover generation.

P2: Multi-treatment creative search

- Implemented: generate 5 deterministic director treatments before render:
  - proof-first UGC
  - cinematic premium
  - documentary/testimonial
  - fast social hook
  - short-drama arc
- Implemented: score each treatment before render using niche fit, runtime fit,
  platform fit, market fit, dialogue risk, and reference sufficiency.
- Implemented: selected treatment is injected into the real autonomous render
  chain, including planner notes, Production Bible constraints, production
  treatment, shot dynamic descriptions, production decision preview, and
  JobResultModal.
- Remaining: add model-backed frame/thumbnail scoring and a regenerate flow
  that lets users reuse alternate treatments without exposing manual settings.

## Source Evidence

- `backend/agent/autonomous_workflow_contract.py`
- `backend/agent/autonomous_production_decision.py`
- `backend/agent/autonomous_niche_launch_matrix.py`
- `backend/agent/autonomous_niche_playbook_catalog.py`
- `backend/agent/autonomous_paid_benchmark_manifest.py`
- `backend/agent/autonomous_top_tier_completion_gate.py`
- `backend/agent/atlas_model_integration_matrix.py`
- `backend/agent/benchmark_review_rubric.py`
- `backend/agent/model_scorecard.py`
- `backend/agent/benchmark_promotion_policy.py`
- `backend/agent/screenplay_scene_linter.py`
- `backend/agent/seedance_shot_linter.py`
- `backend/skills/niche_playbooks.py`
- `backend/skills/niche_readiness.py`
- `backend/workers/video_worker.py`
- `app/studio/page.tsx`

## External References

- AtlasCloud docs:
  https://www.atlascloud.ai/docs
- AtlasCloud MCP/CLI/skills page:
  https://www.atlascloud.ai/docs/en/openapi-index
- AtlasCloud Seedance 2.0 Fast Reference-to-Video:
  https://www.atlascloud.ai/models/bytedance/seedance-2.0-fast/reference-to-video
- AtlasCloud model catalog:
  https://www.atlascloud.ai/models/list
- AtlasCloud video generation docs:
  https://www.atlascloud.ai/docs/models/video
- AtlasCloud predictions docs:
  https://www.atlascloud.ai/docs/predictions
- AtlasCloud upload files docs:
  https://www.atlascloud.ai/docs/upload-files
- AtlasCloud InfiniteTalk:
  https://www.atlascloud.ai/models/atlascloud/infinitetalk
- AtlasCloud ByteDance LipSync A2V:
  https://www.atlascloud.ai/ko/models/bytedance/lipsync/audio-to-video
- AtlasCloud Wan 2.2 Turbo I2V:
  https://www.atlascloud.ai/models/atlascloud/wan-2.2-turbo/image-to-video
- AtlasCloud Kling 3.0 overview:
  https://www.atlascloud.ai/blog/ai-updates/Kling-3-0-Live-on-Atlas-Cloud-The-All-in-One-AI-Video-Generator-with-Smart-Storyboarding-Native-Lip-Sync
- AtlasCloud Veo 3.1 guide:
  https://www.atlascloud.ai/blog/guides/veo-3-1-api-guide
- AtlasCloud MultiTalk:
  https://www.atlascloud.ai/models/atlascloud/multitalk
- AtlasCloud MMAudio v2:
  https://www.atlascloud.ai/models/atlascloud/mmaudio-v2
- ByteDance Seedance 2.0:
  https://seed.bytedance.com/en/seedance2_0
- Seedance 2.0 docs:
  https://seedance2.app/docs
- Seedance parameters:
  https://www.seedvideo.net/docs/seedance-2-parameters
- Jellyfish:
  https://github.com/Forget-C/Jellyfish
- MovieAgent:
  https://github.com/showlab/MovieAgent
- CineAGI:
  https://arxiv.org/abs/2604.23579
- Co-Director:
  https://co-director-agent.github.io/
- DirectorBench:
  https://arxiv.org/abs/2605.30090
- MSVBench:
  https://arxiv.org/abs/2602.23969
- ViMax / AI-Creator:
  https://github.com/HKUDS/ViMax
- LocalMiniDrama:
  https://github.com/xuanyustudio/LocalMiniDrama
- Moyin Creator:
  https://github.com/MemeCalculate/moyin-creator
- MapleShaw Seedance 2.0 prompt skill:
  https://github.com/MapleShaw/seedance2.0-prompt-skill/blob/main/SKILL.md
- ComfyUI Seedance 2.0 docs:
  https://docs.comfy.org/zh/tutorials/partner-nodes/bytedance/seedance-2-0
- ByteDance Moyin / AI short-drama agent coverage:
  https://pandaily.com/byte-dance-launches-ai-short-drama-agent-powered-by-seedance-2-0
- Codeywood:
  https://codeywood.com/
- InfiniteTalk:
  https://arxiv.org/abs/2508.14033
- MultiTalk:
  https://github.com/MeiGen-AI/MultiTalk
- ChatCut Seedance 2.0 prompt guide on X:
  https://x.com/chatcutapp/status/2041763561333264865
- OpenArt/Seedance creator report on X:
  https://x.com/azed_ai/status/2040460544495526397
- CapCut Video Studio/Seedance agent workflow report on X:
  https://x.com/masahirochaen/status/2037147512046252168
