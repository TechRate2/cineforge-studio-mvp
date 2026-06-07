# Validation And Launch Checklist

## Required validation commands

Run these commands before merging production changes:

```bash
python -m pytest backend\tests -q
python backend\scripts\run_backend_tests.py
node .\scripts\typecheck.mjs
node .\scripts\check-autonomous-ui.mjs
```

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

## Merge rule

Do not merge a launch candidate until validation passes and the remaining risks are written in the pull request summary.
