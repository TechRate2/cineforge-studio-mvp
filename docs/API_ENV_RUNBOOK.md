# API And Environment Runbook

This runbook lists the runtime components needed for CineForge Studio to operate with real renders and delivery.

## Required runtime groups

### Video rendering provider

The render worker must have a configured video rendering provider. Current source paths reference AtlasCloud and Seedance-oriented execution plans. Keep provider request and response handling in real pipeline modules only.

Expected configuration examples:

- `ATLASCLOUD_API_KEY`
- `ATLASCLOUD_LLM_API_KEY`

### LLM or planning provider

Planning and advanced creative reasoning may use a language model provider when enabled by the backend configuration.

Expected configuration examples:

- `ANTHROPIC_API_KEY`

### Image or video model fallback provider

Some deployments may use additional model providers for supporting workflows.

Expected configuration examples:

- `GENMAX_API_KEY`

### Voice or audio provider

Audio, narration, or voice workflows may use a voice provider when enabled.

Expected configuration examples:

- `ELEVENLABS_API_KEY`

### Object storage and delivery

Final videos and artifacts should be delivered through object storage. Current source supports R2-style delivery metadata and presigned or public URLs.

Expected configuration examples:

- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET_NAME`
- `R2_PUBLIC_URL`
- `R2_FINAL_VIDEO_ACCESS_MODE`
- `R2_PRESIGNED_URL_EXPIRES_S`
- `ALLOW_R2_LOCAL_FALLBACK=false`

`ALLOW_R2_LOCAL_FALLBACK` is off by default. Keep it off for production and
paid smoke. When R2 is missing or upload fails, render delivery must fail
closed instead of returning a local `file://` URL. The local fallback exists
only for explicit development-only smoke work with `APP_ENV=development`.

### Database

If a deployment path uses persistent jobs, users, workspaces, billing, or evidence storage, configure the database.

Expected configuration examples:

- `DATABASE_URL`

### Local media tools

Final assembly and file checks require:

- `ffmpeg`
- `ffprobe`
- `opencv-python-headless` for deterministic post-render CV probes in the Python environment

If the binaries are not on `PATH`, set explicit portable binary paths:

- `FFMPEG_BIN=C:\tools\ffmpeg\bin\ffmpeg.exe`
- `FFPROBE_BIN=C:\tools\ffmpeg\bin\ffprobe.exe`

Smoke scripts and the final assembly/QA workers use the same resolver. A bad
configured path fails closed and is reported as a missing tool; the code does
not substitute a fake assembly path.

## Required validation

```bash
python -m pytest backend\tests -q
python backend\scripts\run_backend_tests.py
node .\scripts\typecheck.mjs
node .\scripts\check-autonomous-ui.mjs
```

## Safe smoke scripts

These scripts are safe by default and run dry-runs only:

```bash
python backend\scripts\smoke_shortform.py
python backend\scripts\smoke_longform.py --duration-s 30
python backend\scripts\run_benchmark_cases.py --case-id bench_food_restaurant_12s
```

Paid smoke requires explicit opt-in:

```bash
python backend\scripts\smoke_shortform.py --paid
python backend\scripts\smoke_longform.py --paid --duration-s 30 --approve-consistency-review
python backend\scripts\run_benchmark_cases.py --paid --case-id bench_food_restaurant_12s
```

When required keys or tools are missing, scripts return `status: "missing_env"`,
list `missing_env`, perform no vendor calls, and include
`vendor_calls_performed: false`.

## Required smoke sequence

1. Start backend with real environment variables.
2. Start frontend.
3. Run short-form dry-run.
4. Run short-form paid render.
5. Run long-form dry-run.
6. Run long-form paid render.
7. Verify final assembly.
8. Verify storage delivery URL.
9. Verify QA report is present.
10. Verify benchmark evidence can be written.

## Benchmark evidence safety

- `dry_run` benchmark cases compile real plans and write non-promotional
  evidence templates only.
- Development metadata stubs are metadata-only. They must not write `stub://`
  output URLs, local file URLs, cost, latency, QA score, or delivery evidence.
- `POST/PATCH /api/v1/director/autonomous/benchmarks/results` may mark a row
  `passed` only when backend evidence validation is promotion-ready.
- Paid benchmark success requires real HTTP(S) output URL, cost, latency,
  QA/review score, reviewer approval, retry/repair count, and the required
  evidence pack. Loopback URLs such as `localhost` or `127.0.0.1` are not
  accepted as benchmark output evidence.

## Failure handling

- Missing vendor key should fail before paid render with `code: "missing_env"` and a `missing_env` list. Placeholder values such as `...`, `your_api_key`, or `<key>` count as missing; the backend must not queue a render job or make a vendor call.
- Placeholder values made only of `x` characters, such as the examples in `.env.example`, also count as missing.
- Direct media endpoints (`/video/direct/generate`, `/image/direct/generate`,
  `/audio/direct/generate`, and `/upload-media`) must also return
  `code: "missing_env"` with `vendor_calls_performed: false` before creating a
  local job or touching a vendor client.
- Direct image/video/audio poll responses, storyboard master-board generation,
  final-video endpoints, and Studio delivery UI must only surface deliverable
  non-loopback `http`/`https` output URLs. Vendor responses that report
  `completed` but provide `file://`, `stub://`, local paths, `localhost`,
  `127.0.0.1`, or no URL are treated as failed output delivery, not completed
  media.
- Seedance segment rendering follows the same rule in the core paid pipeline:
  `SegmentRenderer` and `RenderExecutor` require a deliverable HTTP(S)
  `video_url` before a segment can be marked completed. Completed vendor
  responses without such a URL return `missing_deliverable_video_url` and stay
  in `render_failed`, not QA repair or delivery.
- Missing storage config should fail delivery checks.
- Missing or placeholder R2 config must not produce fake storage URLs. Legacy
  upload helpers raise by default; local `file://` fallback requires explicit
  `ALLOW_R2_LOCAL_FALLBACK=true` and `APP_ENV=development`.
- Timeline reassemble input clips follow the same rule: `file://` clip URLs are
  refused unless `ALLOW_R2_LOCAL_FALLBACK=true` and `APP_ENV=development`.
- Long-form final assembly also refuses readable local segment paths unless the
  same development fallback opt-in is enabled.
- Missing ffmpeg or ffprobe should fail final assembly or final video QA.
- Invalid reference URLs should appear in Reference Intelligence blockers.
- QA failures should result in review, repair, or fail-closed behavior.

## Admin readiness endpoint

`GET /api/v1/admin/credits` reports provider and R2 readiness only. It must not
invent wallet balances, usage totals, QA scores, output URLs, or other vendor
state. If a vendor balance API is not wired, the response returns
`balance: null` with `balance_status: "unavailable"` and points operators to the
vendor dashboard.

## Documentation update rule

When provider names, API keys, storage modes, or runtime dependencies change, update this file and the smoke test matrix in the same pull request.
