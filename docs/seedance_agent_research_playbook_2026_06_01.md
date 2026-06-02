# Seedance Agent Research Playbook - 2026-06-01

This playbook converts current Seedance documentation, papers, public API
examples, and creator workflow observations into an operating spec for the
CineForge/CineJelly video agent. It is intentionally implementation-oriented:
the agent must turn vague user intent and media uploads into a production plan,
not just a prompt.

## Source Map

Primary sources used:

- BytePlus ModelArk Seedance 1.0 Pro: https://docs.byteplus.com/en/docs/modelark/1587798
- BytePlus ModelArk Seedance 1.0 Lite / prompt guide snippets: https://docs.byteplus.com/en/docs/modelark/1587797
- BytePlus ModelArk video generation API, including Seedance 2.0 capability notes: https://docs.byteplus.com/en/docs/ModelArk/1520757
- BytePlus Dreamina Seedance 2.0 prompt guide: https://docs.byteplus.com/en/docs/ModelArk/2222480
- BytePlus ModelArk pricing: https://docs.byteplus.com/en/docs/ModelArk/1099320
- Seedance 1.0 technical report: https://arxiv.org/abs/2506.09113
- Seedance 1.5 Pro technical report: https://arxiv.org/abs/2512.13507
- Seedance 2.0 model card: https://arxiv.org/abs/2604.14148
- fal.ai Seedance 2.0 API repo: https://github.com/fal-ai/seedance-2.0-api
- amrrs Seedance 2.0 API examples repo: https://github.com/amrrs/seedance-2.0-api
- Runware Seedance 2.0 examples: https://runware.ai/docs/models/bytedance-seedance-2-0/examples
- Awesome Seedance prompt examples: https://github.com/makesupday/Awesome-Seedance-2.0-Prompt-and-Examples
- TikTok creative best practices: https://ads.us.tiktok.com/help/article/creative-best-practices
- TikTok Web Auction Best Practices PDF: https://ads.tiktok.com/business/library/TikTok_Web_Auction_Best_Practices_2024.pdf
- YouTube Shorts editing tips: https://support.google.com/youtube/answer/13380879
- Axios report on Seedance 2.0 IP disputes: https://www.axios.com/2026/02/13/disney-bytedance-seedance

Use official docs and API pages as source of truth for capabilities, limits, and
pricing. Use community prompt examples only as weak evidence for prompt shape,
never as proof of model guarantees.

## Non-Negotiable Model Facts

- Seedance 1.0 Pro supports text input, image input, and video output. BytePlus
  lists 480p, 720p, 1080p, 24 fps, mp4, and 2-12s duration. It has strong
  multi-shot narrative behavior, first/last-frame I2V, instruction following,
  physical motion, and style response.
- Seedance 1.0 Pro Fast inherits Seedance 1.0 Pro strengths with lower cost and
  faster generation, but should be treated as iteration / preview route unless a
  benchmark proves it matches Pro for the current niche.
- Seedance 1.0 Lite is speed-oriented. It supports T2V and I2V, camera movement,
  first/last-frame transition behavior, and is useful for low-cost drafts, but
  is not the premium consistency route.
- Seedance 1.5 Pro is the audio-video bridge. The paper describes native
  audio-visual generation, multilingual/dialect lip-sync, cinematic camera
  control, and stronger narrative coherence. Use when native audio/lip-sync is
  required and Seedance 2.0 is unavailable or face/input policy blocks 2.0.
- Seedance 2.0 supports text, image, audio, and video references. The model card
  states 4-15s direct generation, 480p/720p native output, up to 9 images, 3
  videos, and 3 audio clips as references, plus a Fast variant.
- BytePlus Seedance 2.0 API notes add that reference-based generation needs at
  least one image or video input; audio alone is not enough. It supports
  generation, editing, extension, first-frame I2V, first/last-frame I2V, and
  T2V. The same docs warn that direct upload of reference images/videos
  containing real human faces is not supported unless using supported trusted,
  digital-character, or authorized asset workflows.
- fal.ai exposes Seedance 2.0 standard and fast routes for T2V, I2V, and R2V.
  Its API docs list T2V duration as auto or 4-15 seconds, aspect ratios including
  21:9, 16:9, 4:3, 1:1, 3:4, 9:16, and synchronized audio generation.

## Route Decision

Default routes:

- User provides only text and wants ideation: use T2V for concept exploration,
  but generate an internal visual bible first. If identity or product accuracy
  matters, create image anchors before final render.
- User provides one strong image: use I2V first-frame route for short motion or
  first/last-frame route when the user needs a controlled ending.
- User provides multiple images/videos/audios or wants exact style, motion,
  audio, product, or character control: use Seedance 2.0 R2V/reference route.
- User wants talking-head, dialogue-heavy, language-specific lip-sync: prefer a
  native/driven lip-sync route proven by benchmark. Seedance 1.5 Pro is relevant
  for audio-video generation; Wan/other driven lip-sync lanes can remain fallback
  where your benchmark shows better mouth accuracy.
- User wants quick iterations, many variants, or low budget: use Fast/Lite for
  draft candidates, then promote winning structure to Pro/2.0 standard.
- User wants 15s-30m: never rely on one model call. Build script, bible, scene
  plan, and render graph; render 4-15s shots or 30-60s chunks and assemble.

Escalation rules:

- If subject consistency is critical, require visual anchors before paid render:
  character/product/environment/style image references, previous approved frames,
  or storyboard board.
- If user uploads real human faces for Seedance 2.0 BytePlus route, verify the
  provider policy path before sending. Use authorized asset, digital character,
  or trusted generated asset workflow where available.
- If prompt asks for copyrighted characters, actors, celebrity likeness, or a
  "make it like [specific protected franchise/character]" workflow, rewrite to
  original archetypes and style-neutral descriptions. Seedance 2.0 has already
  drawn major IP disputes; the agent should not make infringement its viral
  strategy.

## Agent Workflow For Non-Expert Users

The user should be able to say: "make a viral video from this product/photo and
my idea." The agent must then run a production interview silently or with minimal
questions.

1. Interpret intent.
   - Extract niche, platform, duration, target market, audience, goal, CTA,
     emotional tone, mandatory facts, forbidden claims, and user-provided media.
   - If missing, infer safely from media and ask at most one blocking question
     only when legal, medical, finance, product claim, or identity permission is
     ambiguous.

2. Build an asset bible.
   - Character card: face, hair, outfit, age range, body language, voice, accent,
     exact lines not to drift.
   - Product card: geometry, package, label, color, material, allowed claims.
   - Location card: geography, time of day, lighting, background landmarks.
   - Style card: color grade, camera language, texture, pacing, caption style.
   - Audio card: music mood, SFX, dialogue, voiceover, subtitle plan.

3. Research or infer the creative angle.
   - For ads: generate 5-10 angles, rank by proof strength and hook clarity.
   - For story/film: generate logline, conflict, stakes, reversal, final image.
   - For education: convert topic into one contradiction, one proof/example, one
     takeaway.
   - For product: force visible proof; do not depend on narration alone.

4. Select route and references.
   - Assign every uploaded/generated asset exactly one primary job: identity,
     product, environment, style, camera motion, shot pacing, beat, SFX, dialogue.
   - Do not let one reference simultaneously control identity, camera, product,
     and audio. This is the main cause of drift.

5. Generate screenplay and shot plan.
   - Each shot must have: purpose, duration, subject, one physical action,
     environment, camera shot, camera movement, lighting, audio cue, continuity
     anchor, and retry criteria.
   - Long form must have acts, scenes, chunk boundaries, continuity handoffs,
     and approved final frames.

6. Compile Seedance prompts.
   - Use structured blocks, not blob paragraphs:
     reference jobs -> timeline -> environment -> style -> action -> camera and
     sound -> shot contract -> constraints.
   - Keep one filmable action per 4-15s unit.
   - Mention exact reference mapping: "Use Image 1 for character identity",
     "match camera motion from Video 1", "use Audio 1 for pacing/SFX", etc.
   - Add constraints: no extra characters, no text/logos unless requested, keep
     product geometry, keep wardrobe, keep color grade, no scene jump.

7. Render, QA, and repair.
   - Score each shot on identity, product accuracy, motion physics, camera
     adherence, scene continuity, audio sync, text/caption quality, and platform
     hook.
   - Retry only failed shots or chunks. Do not regenerate the whole film unless
     the bible or script is wrong.
   - Store winning prompt, references, seed, model route, cost, latency, and QA
     notes as benchmark evidence.

8. Assemble and package.
   - Normalize aspect ratio, captions, safe zones, loudness, cuts, transitions,
     and final duration.
   - Produce platform variants: TikTok/Reels/Shorts 9:16, YouTube 16:9 trailer,
     thumbnail/keyframe, title/caption/hashtags/CTA.

## Prompt Contract

Recommended unit prompt shape:

```text
[REFERENCE JOBS]
Image 1: character identity anchor, preserve exact face/hair/outfit.
Image 2: product geometry anchor, preserve package shape/label/color.
Video 1: camera movement reference, match push-in/orbit tempo.
Audio 1: SFX or dialogue pacing reference.

[TIMELINE]
0-2s: hook action.
2-7s: proof/demo action.
7-10s: reveal/turn/payoff.

[ENVIRONMENT]
Location, time of day, lighting, background landmarks, atmosphere.

[STYLE]
Color grade, texture, genre, realism level, edit rhythm.

[SHOT DIRECTION]
Subject: one concrete subject.
Action: one visible physical action.
Camera: shot size + angle + lens feel + movement + continuity purpose.
Sound: dialogue/SFX/ambience/music cue.

[SHOT CONTRACT]
One physically filmable action. Preserve identity/product/location/style.
No unrequested text, logos, extra characters, scene jumps, or claim changes.
```

For text-to-video:

- Use T2V when exploration is acceptable or there is no fixed identity.
- Add explicit subject, action, setting, camera, lighting, style, audio, aspect,
  and duration.
- Avoid asking T2V to preserve a character across many independent generations
  without anchors.

For image-to-video:

- Treat the source image as a hard first frame or first/last-frame contract, not
  loose inspiration.
- Prompt motion and camera only where possible; the image already defines many
  static details.
- If the output must end in a specific state, use first/last-frame I2V.

For reference-to-video:

- Name each reference by slot and job in the prompt.
- Use images for identity/product/style/environment, videos for camera/motion/
  VFX/transition, and audio for beat/SFX/dialogue pacing.
- Keep reference count within route caps and avoid overloading the prompt with
  more than the shot actually needs.

For video editing/extension:

- Use timestamp/spatial instructions: "At 2s, upper-right table area, add..."
- For removal/modification, state what remains unchanged.
- For extension, say forward/backward and describe the before/after content.
- For track completion, use at most the supported video inputs and explicitly
  describe transition logic between clips.

## Shot Planning By Duration

15-30s short:

- 3-6 shots.
- 0-3s pattern interrupt or promise.
- 3-12s proof, conflict, or demonstration.
- 12-24s escalation/reveal/payoff.
- Final seconds: CTA, loop, or memorable final image.

31-60s sequence:

- 6-12 shots across 2 scenes.
- Use one location/time jump at most.
- Use last-frame handoff if the same character/product continues.

1-3m micro film:

- 3 acts: hook/setup, escalation, payoff.
- 3-6 scenes, each with one scene question.
- Render 4-15s shots; QA per scene.

3-10m short film:

- 3 acts with 5-10 scenes.
- Keep each scene anchored by a master keyframe or previous final frame.
- Dialogue should be short and cuttable; do not ask one Seedance shot to carry a
  long monologue.

10-30m episode:

- 5-act structure: cold open, setup, rising action, crisis, resolution.
- Chunk into 30-60s render groups and maintain a scene memory pack.
- Use recurring visual motifs, consistent voice profiles, and locked character
  wardrobe/location rules.
- Every scene needs a handoff image, QA report, and retry scope.

## Niche Recipes

Product/ecommerce:

- Strong route: image/product anchor + I2V/R2V.
- Prompt proof: unbox, use, texture, before/after, 360 orbit, macro detail.
- Avoid hallucinated claims, changed packaging, unreadable labels, fake logos.

Beauty/fashion:

- Use character + product + style references.
- Focus on tactile close-ups, face/hair/skin continuity, fabric movement,
  mirror/reflection shots, soft lighting.
- Never imply medical results unless claims are provided and reviewed.

Food/restaurant/ASMR:

- Use SFX and macro texture. Steam, crunch, pour, tear, melt, stir are strong
  physical verbs.
- Keep one sensory action per shot.

UGC/testimonial:

- Do not over-polish. TikTok guidance favors native 9:16, sound, visible people,
  DIY/UGC aesthetics, hooks early, CTA, and creative iteration.
- Generate several hook variants before render.

Education/finance/medical wellness:

- Visualize one concept, contradiction, or example per shot.
- Add claim-safety review. Avoid diagnosis, guaranteed returns/results, or
  unverified factual claims.

Drama/short film:

- Need character bible, scene question, emotional turn, blocking, eyeline,
  wardrobe, and final-frame handoff.
- Use close-ups selectively; repeated extreme close-ups are drift-prone.

Travel/real estate:

- Need spatial orientation: establishing -> path -> feature -> detail.
- Use stable landmarks and screen direction. Avoid impossible location jumps
  inside one shot.

Music video:

- Beat reference matters. Map movement to audio sections.
- Use repeated motifs and color palette to create continuity across cuts.

## Viral Packaging Rules

Use platform guidance as constraints, not superstition:

- TikTok official guidance: native 9:16, at least 720p, sound/music, UI safe
  zone, people when useful, hook in first 6s, content proposition in first 3s,
  captions/text overlays, transitions/graphics, CTA, and creative refresh.
- TikTok auction guide: at least 3-5 unique creatives per ad group; video should
  be vertical/full-screen, include audio, be above 720p, longer than 5s, and
  ideally 21-34s for the referenced ad guide.
- YouTube Shorts guidance: audio, text, voiceover, and timed text help viewers
  follow story/context through fast edits.

Agent behavior:

- Always output at least 3 hook alternatives for short-form jobs.
- Always generate a caption/subtitle plan if the video includes talking,
  education, news, or fast story beats.
- Always generate at least one loop ending option for shorts.
- For paid/performance content, create multiple materially different variants,
  not tiny prompt edits.

## QA Gates

Hard fails before render:

- Shot duration >15s for a single Seedance unit.
- Missing subject, action, camera, or setting.
- More than one unrelated action chain in a shot.
- References exceed provider caps.
- Same reference assigned conflicting jobs.
- Real-person face reference sent into a route that disallows it.
- Protected IP/celebrity likeness request without authorization.
- High-risk factual claim without source/review.

Hard fails after render:

- Character/product identity changed materially.
- Product label/package/geometry is wrong.
- Face/mouth/audio sync fails for dialogue route.
- Motion violates the intended action or physics.
- New unrequested character, logo, text, or location appears.
- Scene handoff breaks pose, eyeline, lighting, wardrobe, or screen direction.

Repair policy:

- Bad motion: rewrite action with one stronger physical verb and degree adverb.
- Bad camera: replace vague camera words with shot size, angle, lens feel, and
  one movement.
- Bad identity: strengthen identity anchor, reuse same wording, use previous
  approved frame, reduce close-up pressure.
- Bad product: use product image as first/primary reference, simplify action,
  favor macro/locked camera.
- Bad long-form continuity: retry only the failed shot with previous final frame
  as hard anchor.

## Implementation Hooks In This Repo

Existing modules already align with this playbook:

- `backend/agent/long_form_orchestrator.py`: classifies 15s-30m runtime and
  enforces scene/chunk based rendering.
- `backend/agent/seedance_reference_allocation.py`: assigns image/video/audio
  reference jobs and caps.
- `backend/agent/seedance_prompt_formula.py`: emits the prompt formula contract.
- `backend/agent/seedance_prompt_compiler.py`: compiles structured Seedance
  prompts from bible and shot.
- `backend/agent/seedance_shot_linter.py`: catches duration, vague subject,
  overloaded action, camera, setting, audio, and continuity issues.
- `backend/agent/scene_generation_agent.py`: converts shots to render jobs and
  injects Seedance reference tags/manifest.

Recommended next implementation upgrades:

- Add provider-policy awareness for Seedance 2.0 real-human face references:
  `trusted_generated`, `digital_character`, `authorized_person`, `blocked`.
- Persist source-backed route facts in a machine-readable model card so model
  guide data does not drift from official docs.
- Add a "viral package" artifact to each director job: hook variants, caption
  plan, platform aspect/safe-zone plan, CTA, and test matrix.
- Add benchmark fields for `reference_job_conflict`, `caption_readability`,
  `hook_strength`, `scene_handoff_integrity`, and `ip_likeness_risk`.
- Add a prompt-length guard for Seedance 2.0 under 1000 words on BytePlus, with
  compression by removing static details that references already carry.

## Bottom Line

Seedance is strongest when treated as a high-end shot generator inside a
director/editor pipeline. The agent should not be a prompt box. It should be a
producer, strategist, screenwriter, continuity supervisor, prompt compiler,
render QA reviewer, and platform packaging system. The winning operating model
is: lock references, write a bible, split filmable shots, render 4-15s units,
QA/retry locally, assemble globally, and learn from benchmark evidence.
