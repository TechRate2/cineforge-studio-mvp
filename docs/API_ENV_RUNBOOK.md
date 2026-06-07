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
- `R2_PUBLIC_BASE_URL`
- `R2_CDN_BASE_URL`
- `R2_FINAL_VIDEO_ACCESS_MODE`
- `R2_PRESIGNED_URL_EXPIRES_S`

### Database

If a deployment path uses persistent jobs, users, workspaces, billing, or evidence storage, configure the database.

Expected configuration examples:

- `DATABASE_URL`

### Local media tools

Final assembly and file checks require:

- `ffmpeg`
- `ffprobe`

## Required validation

```bash
python -m pytest backend\tests -q
python backend\scripts\run_backend_tests.py
node .\scripts\typecheck.mjs
node .\scripts\check-autonomous-ui.mjs
```

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

## Failure handling

- Missing vendor key should fail before paid render.
- Missing storage config should fail delivery checks.
- Missing ffmpeg or ffprobe should fail final assembly or final video QA.
- Invalid reference URLs should appear in Reference Intelligence blockers.
- QA failures should result in review, repair, or fail-closed behavior.

## Documentation update rule

When provider names, API keys, storage modes, or runtime dependencies change, update this file and the smoke test matrix in the same pull request.
