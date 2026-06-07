# Reference Intelligence

## Purpose

Reference Intelligence helps CineForge Studio understand whether uploaded assets are ready for rendering. It supports dry-run review, reference blockers, and future multimodal asset analysis.

## Current version

Reference Intelligence V1 is metadata-based. It uses only supplied asset fields such as kind, URL, tag, role, role confidence, role locked state, name, notes, and metadata.

V1 does not claim pixel or audio understanding. Pixel, OCR, logo, face, product, video-motion, and audio analysis belong to a future V2 analyzer.

## Main contract

Important source file:

- `backend/agent/reference_intelligence.py`

Main models:

- `ReferenceAssetInsight`
- `ReferenceIntelligenceReport`
- `ReferenceIntelligenceService`

Report fields include:

- status: ready, needs_review, blocked;
- asset_count;
- image_count;
- video_count;
- audio_count;
- insights;
- required_roles;
- missing_required_roles;
- warnings;
- blockers;
- reference_sufficiency;
- rules_applied.

## Readiness behavior

An asset can be:

- ready: role is locked, URL exists, and no important warning is present;
- needs_review: role is unknown, role is not locked, or confidence is low;
- blocked: media URL is missing or a policy error exists.

A project can be:

- ready: all assets and required roles are usable;
- needs_review: references require user confirmation or non-critical warnings exist;
- blocked: at least one blocker exists.

## Dry-run integration

Reference Intelligence is surfaced through `RenderDryRunReport`:

- `reference_intelligence`
- `warnings`
- `hard_failures`

Important source file:

- `backend/workers/render_dry_run.py`

Existing UI can read dry-run `hard_failures` as blockers.

## Future UI integration

Create a Reference Intelligence panel showing:

- project readiness;
- image, video, and audio counts;
- missing required roles;
- each asset readiness;
- role;
- confidence;
- best use;
- role locked status;
- warnings;
- blockers.

## V2 roadmap

Reference Intelligence V2 should add real analyzers:

- image analyzer for face, product, logo, label, style, and asset quality;
- video analyzer for duration, camera motion, pacing, blur, and handoff frames;
- audio analyzer for voice, music, sound effects, loudness, and duration;
- OCR or logo checks when available;
- quality score based on computed evidence.

Computed evidence must be real and traceable. If a signal is not computed, report it as unavailable.

## Tests

Current and future tests should cover:

- missing product role;
- media asset without URL;
- locked product reference ready;
- dry-run report surfaces blocked reference;
- paid render rejects dry-run hard failures;
- UI displays blockers clearly.
