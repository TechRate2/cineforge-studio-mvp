# Storytelling Research — CineForge Director/Scene Agent Redesign

Source-synthesized from 7 references (ViMax, ArcReel, drama-director-skill, awesome-seedance-2-prompts, MindStudio $200 film, CrePal product-ad, AtlasCloud Seedance drama). Target: TikTok/Reel 15-60s, niche-agnostic.

---

## A. HOOK PATTERNS (first 1-3s)

- **Pattern Interrupt** — visual anomaly, unexpected scale/motion (CrePal: "must communicate intent instantly without sound").
- **Direct Question** — "Tired of messy cables?" / "Why do creators keep this on their desk?" (CrePal problem-solution).
- **Bold Statement / Status Reveal** — "Your product photos can sell harder." (CrePal feature-led).
- **Lifestyle Cold-Open** — character mid-action, no setup ("already mid-stride", MindStudio action-anchoring).
- **POV Confession** — first-person handheld, micro close-up of hand/face reaction (drama-director hero shot).
- **Social Proof Drop** — "X creators use this" (CrePal social-proof).
- **Visual Anomaly / Pattern Break** — extreme wide aerial → hard cut to close-up (Seedance double-contrast cut).
- **Before/After Tease** — show "after" state first, withhold cause (universal ad pattern).
- **Offer-led** — "Launch week 20% off" (CrePal offer-led; only when promo real).
- **Reaction Shot Cold-Open** — silhouette/profile micro-tremor (MindStudio: avoid full-face).

## B. DRAMATIC STRUCTURE (15-60s arc)

Synthesized 3-act compressed (drama-director 9-beat × 3×3 grid + CrePal 3-part rhythm + AtlasCloud setup/rising/turn/resolution×2):

- **0-2s HOOK** — pattern interrupt, no logo, no product close-up.
- **2-6s SETUP / PAIN** — establish character + problem context; one environment, one character preferred.
- **6-12s TENSION / ESCALATION** — stakes rise; "rising action panels 4-6"; intercut close-ups.
- **12-20s SOLUTION REVEAL** — product appears as answer to problem, not as subject.
- **20-30s PROOF / DEMO** — feature shown via action, not text overlay.
- **Final 2-3s CTA** — explicit verb ("Shop now / Try today / Link in bio"). CrePal: "weak CTA wastes the creative".

15s variant: collapse SETUP+TENSION into 3-5s, SOLUTION 5-9s, PROOF 9-12s, CTA 12-15s.

## C. LEAD-IN PRODUCT (no-ad feel)

- **Problem-First, Product Later** — show pain 0-3s, product appears at 3-6s as the resolution (CrePal core).
- **Camera Move, Not Product Move** — "slow push-in, soft studio lighting, floating feature callouts" — product stays static, camera does work (CrePal motion-prompt strategy).
- **Casual Placement** — product is in frame ambient (desk, hand) before becoming subject; never open with product close-up.
- **Before/After Split** — split-frame or hard cut showing transformation; product is the hinge.
- **Three-Variant Spawning** — generate "premium / lifestyle / offer-led" angles per product (CrePal).
- **Result-First Hook** — show outcome, reveal product caused it (reverse causality).

## D. CHARACTER / CONSISTENCY (Seedance 2.0)

- **Visual DNA Lock** — establish character via reference image; describe minimally in motion prompt; Seedance treats reference as visual DNA (drama-director).
- **Reference Chaining** — feed best generated shot as reference for next shots featuring same character (MindStudio).
- **9-Panel Anchor** — generate 9-panel comic on one canvas → ensures same outfit/hair/face since all panels share pixels (AtlasCloud).
- **Face-Anchor Phrase** — "same character across all panels, same outfit, same hairstyle" (AtlasCloud explicit).
- **Functional Descriptors** — "photorealistic digital character / figure" beats age indicators (drama-director compliance trick).
- **Avoid Full-Face Overuse** — design around silhouette, profile, hand close-ups, object inserts (MindStudio: full-face is still hard).
- **Character Lock-In Session** — burn 10-15 generations to find character look BEFORE narrative shots (MindStudio).
- **Outfit Invariant Rule** — specify once in Static Description; never change mid-sequence unless plot.
- **Clue/Prop Tracking** — mark key props as "线索" / "anchor object" — track across cuts for continuity (ArcReel).

## E. SHOT-BY-SHOT TIMING (sweet spots)

- **Hook shot**: 1-2s (single hard cut).
- **Setup shots**: 2 shots × 2s each.
- **Tension shots**: 3-4 shots × 1.5-2s each (faster pacing escalates).
- **Reveal shot**: 2-3s (slower to land).
- **Proof shots**: 2 shots × 2s.
- **CTA frame**: 2-3s static or push-in.
- **Total shot count 15s**: 8-10 shots. **30s**: 12-18 shots. **60s**: 20-30 shots (MindStudio: 25-35 for 2-3min).
- **Reserve complex motion for wide/medium**; close-ups stay simple (MindStudio).
- **Double-contrast cuts** — change BOTH shot size AND camera mode each cut (AtlasCloud).

## F. SEEDANCE 2.0 PROMPT TEMPLATE (multi-shot)

Three-section structure (drama-director + AtlasCloud):

```
[STYLE & MOOD]
Photorealistic cinematic realism, Netflix production quality, IMAX-grade detail.
[Palette]: cold blues + warm amber highlights. Shallow DoF, anamorphic flare.

[DYNAMIC DESCRIPTION] — shot sequence with hard cuts + timing
0:00-0:02 Extreme wide aerial drone, [subject + action].
0:02-0:04 Hard cut to medium handheld close-up, [micro-expression].
0:04-0:08 Hard cut to wide stabilized tracking, [escalation].
0:08-0:12 Extreme close-up insert locked-off, [product reveal].
0:12-0:15 Static push-in on [CTA frame].

[STATIC DESCRIPTION] — invariants
Same character across all shots, same outfit, same hairstyle.
Location: [single environment]. Lighting rig locked.
No text overlay, no watermark, no lens distortion, no sudden shake.
```

Formula compressed: **[Subject] + [Action] + [Camera Technique] + [Lighting] + [Style/Quality]** (awesome-seedance).

## G. NICHE-AGNOSTIC STRATEGIES

One framework for beauty / tech / food / fashion / B2B — drive via slot variables, not niche templates:

- **Emotional beats** are universal (pause → tension → release → climax → CTA).
- **Lighting transitions** (warm→cool, bright→dark) signal phase change in ANY niche.
- **Scale reference** — tiny subject vs massive environment hooks in tech, food, fashion equally.
- **Particle effects** (dust, water, steam, light rays) = universal mood multipliers.
- **Caption rhythm** (Hook → Benefit → CTA) maps 1:1 onto visual rhythm regardless of vertical.
- **Output-review checklist > category checklist** (CrePal): accuracy maintained, claims grounded, motion serves clarity, captions work muted.
- **Slot pattern for Director Agent**: `{problem_statement, character_archetype, product_role, payoff_emotion, cta_verb}` — fill from niche, structure stays.

## H. PITFALLS

- **Don't open with product close-up** — looks like ad, instant skip (CrePal).
- **Don't skip style bible** — 30min upfront saves hours of regen (MindStudio).
- **Don't mix incompatible perspectives in one cut** — POV + overhead drone breaks (awesome-seedance).
- **Don't over-describe** — 2000+ char prompts confuse Seedance; prioritize visual hierarchy.
- **Don't write motion prompt as "camera sweeps comic page"** — describe scene action (AtlasCloud).
- **Don't regenerate individual shots** — character drift; stick to locked reference (AtlasCloud).
- **Don't ignore shooting ratio** — budget 3-5 generations per usable clip (MindStudio).
- **Don't put complex motion in close-ups** — wide/medium only (MindStudio).
- **Don't use age indicators** — triggers conservative filtering; use functional descriptors.
- **Don't trust dialogue-heavy concepts** — visual metaphor > talking heads (MindStudio).
- **Don't forget audio** — "mediocre visuals + great audio feels professional".
- **Don't skip the CTA verb** — vague brand appeals = wasted creative.

---

## TOP 3 ACTIONABLE INSIGHTS — Inject into LLM Director Agent prompt

1. **Force the 3-section Seedance schema per scene** (Style&Mood / Dynamic with `0:00-0:02` timestamps / Static invariants). LLM outputs JSON with these three fields per shot + a `face_anchor_phrase` reused verbatim across all shots. This locks character DNA + camera grammar simultaneously, the single highest-ROI pattern from 5/7 sources.

2. **Embed a niche-agnostic beat sheet as the structural skeleton, fill slots from niche brief**: `HOOK(0-2s, pattern_interrupt) → PAIN(2-6s) → ESCALATION(6-12s) → REVEAL(12-20s, product as solution) → PROOF(20-30s) → CTA(final 2-3s, explicit verb)`. Director Agent does NOT choose structure; it only chooses HOOK_PATTERN from enum A and fills slots. Eliminates niche-specific templates entirely.

3. **Enforce "product never opens, product is the answer"** as hard rule + auto-validator: shot 1 must not contain product as subject; product first appears at REVEAL phase (>= 40% into runtime). Pair with "double-contrast cut" rule (each cut must change shot size AND camera mode) — both checkable from shot list JSON before render, saves 3-5x credits via shooting-ratio compression.
