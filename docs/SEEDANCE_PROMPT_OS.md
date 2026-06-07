# Seedance Prompt OS

## Purpose

Seedance Prompt OS is the prompt discipline used by CineForge Studio. It turns creative plans and storyboard scenes into structured Seedance-ready render plans.

## Core contract

Every render unit should include:

- subject;
- action;
- scene or environment;
- lighting and color;
- camera;
- timing;
- audio or style;
- quality details;
- constraints;
- reference jobs;
- negative prompt.

## Reference jobs

References should not be attached without purpose. Each reference should have a role and a job.

Examples:

- product hero: preserve packaging, geometry, label, logo, color, and hero visibility;
- character anchor: preserve identity, face, hair, age, outfit, body proportions, and continuity;
- style reference: guide color grade, lens feel, art direction, and mood;
- camera motion: guide camera path and movement style;
- audio voice: guide narration or dialogue route;
- audio BGM: guide music bed, mood, and tempo.

## Negative prompt strategy

Negative prompt should reduce common generation issues:

- watermark;
- subtitles when not requested;
- text overlays when not requested;
- malformed hands or faces;
- random new characters;
- abrupt unmotivated scene jumps;
- unreadable labels;
- identity drift;
- outfit drift;
- product redesign;
- logo drift;
- packaging geometry changes.

## Preflight

Prompt OS should create shot-level and plan-level preflight summaries.

Preflight should surface:

- hard failures;
- warnings;
- prompt linter issues;
- reference policy issues;
- reference sufficiency;
- shot reports.

RenderExecutor should reject hard failures before paid vendor work.

## Important files

- `backend/seedance/prompt_compiler.py`
- `backend/seedance/prompt_formula.py`
- `backend/seedance/prompt_linter.py`
- `backend/seedance/reference_policy.py`
- `backend/pipeline/render_execution.py`
- `backend/tests/test_seedance_prompt_compiler_prompt_os.py`

## Testing checklist

- One-shot short-form keeps available references.
- Prompt contains `Reference Jobs:` when references exist.
- Negative prompt includes product and identity guardrails when required.
- Shot metadata includes `seedance_preflight`.
- Plan metadata includes `reference_sufficiency`.
- Preflight hard failures reject before vendor work.
