# Validation And Launch Checklist

## Required validation commands

Run these commands before merging production changes:

```bash
python -m pytest backend\tests -q
python backend\scripts\run_backend_tests.py
node .\scripts\typecheck.mjs
node .\scripts\check-autonomous-ui.mjs
```

For chat-first Studio changes, also confirm that `/studio` renders the
Vietnamese-first labels, Reference Intelligence blockers, Agent plan preview,
and RenderTimeline without static or fabricated production data. After render
polling returns a real job payload, RenderTimeline should reflect real QA,
repair, assembly, delivery URL, and benchmark evidence-pack status when present.
If `next build` is run while a local Next dev server is already serving
`localhost:3000`, restart the dev server before browser/API verification so the
served `.next` runtime is not stale.
When `/studio` looks unstyled or visually broken on localhost, run:

```bash
node .\scripts\check-studio-runtime-css.mjs
```

This guard catches the common failure mode where `/studio` returns HTTP 200 but
the referenced Next CSS asset is stale, empty, or 404.

## Required runtime components

A real deployment needs:

- Python dependencies installed;
- Node dependencies installed;
- video rendering API keys;
- storage configuration for final files;
- database configuration where the app requires it;
- ffmpeg;
- ffprobe.

## Smoke checks

A launch candidate should complete these checks with real configuration:

1. Short-form text-only render.
2. Short-form product-reference render.
3. Creator plus product UGC render.
4. Long-form dry-run.
5. Long-form paid render.
6. Final assembly and storage delivery.
7. Quality review path.
8. Delivery failure closed state.
9. Benchmark evidence record.

Safe dry-run smoke commands:

```bash
python backend\scripts\smoke_shortform.py
python backend\scripts\smoke_longform.py --duration-s 30
python backend\scripts\run_benchmark_cases.py --case-id bench_food_restaurant_12s
```

Paid smoke commands require real keys and explicit opt-in:

```bash
python backend\scripts\smoke_shortform.py --paid
python backend\scripts\smoke_longform.py --paid --duration-s 30 --approve-consistency-review
python backend\scripts\run_benchmark_cases.py --paid --case-id bench_food_restaurant_12s
```

## Launch evidence

Store evidence for each launch niche:

- input brief;
- reference summary;
- creative treatment;
- model route;
- output URL;
- cost;
- latency;
- QA result;
- human review score;
- repair count;
- failure reason when present.

Launch-gate pass requires complete usable evidence records with output URL,
cost, latency, QA score, and human score. Dry-run evidence is useful for
pipeline readiness but must not be used to claim production benchmark success.
Benchmark rows may use metadata-only development stubs only for local graph/API
smoke; those rows must not contain output URLs, cost, latency, QA scores, or
delivery evidence. A row cannot be marked `passed` unless backend validation
reports the evidence pack as promotion-ready.
Benchmark evidence records reject non-HTTP(S) `output_url` values. Local paths,
`file://`, `stub://`, and loopback URLs such as `localhost` or `127.0.0.1`
are not launch evidence and must stay out of usable benchmark rows. The
benchmark store enforces this even for direct script/agent writes, not only API
requests.

The main Studio UI may summarize benchmark status only when real evidence exists.
Raw benchmark rows and operator diagnostics stay in admin/operator surfaces.

## Repair and QA checks

- Short-form repair may retry a completed render that failed QA inside the
  configured repair budget.
- A render attempt is only "completed" when the segment has a deliverable
  non-loopback HTTP(S) video URL. Missing, local, loopback, or stub segment URLs
  are render failures (`missing_deliverable_video_url`) and must not enter the
  prompt repair loop.
- Final delivery QA and Studio output previews follow the same URL rule:
  `file://`, local paths, `stub://`, `localhost`, and `127.0.0.1` are not
  public delivery evidence.
- Repair history must be recorded per shot or segment.
- Repair must not change approved references, model route, duration, aspect
  ratio, or cost gate semantics.
- Missing critical QA signals are not a pass.
- Final assembly must fail closed when MP4 QA or delivery QA fails.

## Merge rule

Do not merge a launch candidate until validation passes and the remaining risks are written in the pull request summary.
