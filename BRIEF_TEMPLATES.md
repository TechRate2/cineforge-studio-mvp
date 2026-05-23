# 📝 Brief Templates — Copy-Paste Library

> Verified templates từ creator pro (Dan Kieft course, Ben Bauchau character consistency, GitHub dexhunter/seedance2-skill MIT). Copy 1 trong 3 template dưới đây vào ô brief CineForge để có plan tốt nhất.

---

## Template 1 — Minimal Brief (15s ad / product showcase)

Source: Dan Kieft "Stop wasting Credits! Master Seedance 2.0" YouTube May 2026, timestamp 2:30-3:38.

```
GOAL: 15s product ad, [niche], [tone — cinematic / UGC raw / drama]
CHARACTER: [age range], [outfit], [vibe]
PRODUCT: [name + 1-line USP]
ENVIRONMENT: [location + time of day]
HOOK STYLE: [outcome_showcase / pov_confession / pattern_interrupt]
AUDIO: [silent_native / dialogue_vo / asmr_macro]
CTA: [user adds in post]
```

### Ví dụ điền (son lì matte 89k)
```
GOAL: 15s product ad, beauty Gen Z VN, cinematic UGC
CHARACTER: late 20s VN woman, cream knit cardigan, confident
PRODUCT: son lì matte 89k — dưỡng ẩm 8h, vegan
ENVIRONMENT: bàn make-up cửa sổ chiều, golden hour 4PM
HOOK STYLE: pov_confession
AUDIO: dialogue_vo
CTA: user adds in post (CapCut)
```

---

## Template 2 — Character Bible (multi-shot consistency)

Source: Ben Bauchau character consistency workflow (@BenBauchau X threads 2026) + GitHub `dexhunter/seedance2-skill` SKILL.md.

```yaml
character:
  id: char_main
  name: [pronounceable name]
  age_apparent: [late 20s / mid 30s]
  ethnicity: [Vietnamese / mixed Asian / generic]
  face_signature: |
    [1-2 sentences max 30 words]
    Example: "shoulder-length straight black hair with subtle layers,
    warm fair skin, calm intelligent eyes, soft confident demeanor"
  outfit_invariant: |
    [Single outfit description — DO NOT change across shots]
    Example: "cream knit cardigan over white silk camisole, gold thin necklace"
  posture: confident / relaxed / nervous / energetic
  voice_persona: [GenMax preset: mai / ngan / tran / duc_huy / ninh_don / quan]

# CRITICAL: reuse face_signature + outfit_invariant VERBATIM in every shot's
# STATIC section. Seedance / Vidu pixel-lock identical phrases.
```

### Reference image requirements (Higgsfield + Replicate consensus)
- 4 angles per character: front-facing close-up, full-body, 3/4 profile, gesture
- Resolution ≥ 1024×1024
- Lighting in reference = lighting in output (pick anchor with desired mood)
- Background: neutral or matching environment
- Generation tools: Flux Pro Ultra > Imagen 4 > Midjourney v7 (for AI-gen anchors)

---

## Template 3 — Shot List MD (4-5 shot timed)

Source: Higgsfield 8-scene workflow + Dan Kieft timeline prompting + awesome-seedance-2-prompts.

```markdown
## Shot List · [Title]

Total: 15s · Aspect: 9:16 · Model: Seedance 2.0

### S1 · HOOK (0-2s)
- Purpose: hook
- Camera: MCU handheld
- Action: [character action, NO product]
- Dialogue: "[Vietnamese 5-10 words, optional]"
- Refs: @image_1 (character)

### S2 · PAIN (2-6s)
- Purpose: pain
- Camera: WS push-in
- Action: [character with the problem]
- Refs: @image_1

### S3 · REVEAL (6-10s)
- Purpose: reveal
- Camera: ECU pull-out
- Action: [product enters frame as the answer]
- Refs: @image_2 (product)

### S4 · PROOF (10-15s)
- Purpose: proof
- Camera: MCU static
- Action: [character confidently using product]
- Refs: @image_1 + @image_2
- Caption: "[neutral descriptive — NO sales imperative]"
```

→ Paste shot list này khi anh muốn override Director Agent's plan. Send as user_brief với `force_shot_list=true`.

---

## Template 4 — Storyboard Image Prompt (GPT Image 2 / Seedream / Nano Banana)

Source: Sarikas YouTube "Storyboard Feature Nobody's Talking About" May 2026 + AtlasCloud 9-Panel Anchor.

```
A premium director's storyboard sheet on dark teal #0d2335 background,
ultra-wide cinemascope landscape format (16:9 ratio).

HEADER (top bar):
- Title bold white sans-serif: "[VIDEO TITLE UPPERCASE]"
- Metadata small: "BOARD 1/1 · 15s · 9:16 · [GENRE]"
- Concept line cyan: "[1-line logline]"

PANELS GRID (4×3 = 12 cells, fill [N], blank others dark navy):
[For each shot: Panel number top-left cyan, title top-middle, timestamp top-right mono,
 16:9 image full-bleed showing the action, footer black bar with 4 micro-fields
 (CAMERA/MOVEMENT, ACTION, DIALOGUE/SFX, TRANSITION)]

CHARACTER LOCK (verbatim across all panels):
[Paste character.face_signature + outfit_invariant from Character Bible template]

VISUAL STYLE LOCK:
- Cinematography: [from Bible visual_style]
- Color grading: [warm filmic / teal-orange / pastel / noir]
- Lighting: [golden hour / studio key+fill / window soft / chiaroscuro]
- Film texture: [35mm grain / 16mm grain / digital clean]

FOOTER STRIP (4 sections):
1. CAMERA & LENS STYLE: [lens illustration + "85mm anamorphic"]
2. COLOR & LIGHT: 4 color swatches matching grade
3. SOUND DESIGN & MUSIC: wave icon + "[music_genre], [mood]"
4. NOTES: [italic 1-line director note]

HARD CONSTRAINTS:
- SAME character pixel-locked across ALL panels
- Photorealistic cinematic stills, NO illustration/cartoon
- Panel borders thin cyan #4DD8E0, 2px stroke
- Sans-serif headings, mono digits for timestamps
```

→ Đây chính là prompt CineForge gen Master Board. Anh có thể test gen riêng trên Seedream v4.5 / Nano Banana Pro / Flux Pro Ultra để A/B.

---

## 🎯 Anti-pattern catalog — KHÔNG nên viết

Để tránh fail Director Agent + Validators:

❌ **CTA imperatives** (validator block):
- "Mua ngay link bio", "Đặt ngay", "Shop now", "Click here", "Swipe up"

❌ **Age numbers** (Seedance trigger conservative filter):
- "28-year-old woman" → dùng "late 20s"
- "13-year-old boy" → dùng "teenage" hoặc "young"

❌ **Product mở video** (validator block):
- Shot 1 visual.subject = "lipstick close-up" → reject

❌ **CTA shot purpose** (validator block):
- shot.purpose = "cta" → reject

❌ **Vague camera** (Grok V2 + V3):
- "cinematic camera" → quá rộng, drift dễ
- ✅ Dùng "85mm anamorphic" / "ARRI Alexa 65 IMAX" / "macro 100mm"

❌ **Too many adjectives** (Grok V3 Dan Kieft):
- >25 adjective trong 1 prompt → AI fill gap, inconsistency

❌ **Multi-character cùng outfit không lighting-distinct** (Vidu):
- 2 cô gái cùng cardigan trắng cùng cùng góc → blend face shot 2

---

## 📚 Source license

- `dexhunter/seedance2-skill` MIT → free copy
- `songguoxs/seedance-prompt-skill` MIT → free copy
- Dan Kieft course timestamp 2:30-3:38 → public YouTube reference
- Ben Bauchau character workflow → free public X share
- Sarikas Storyboard YouTube → public reference

→ Toàn bộ template trên CC / MIT / public — anh paste vào CineForge UI freely.

---

## 🚀 Sử dụng trong CineForge

1. **Template 1 (Minimal Brief)**: paste vào ô textarea ở `/studio` → Director Agent expand thành DirectorPlan
2. **Template 2 (Character Bible)**: copy phần `character.face_signature` paste vào Reference notes khi upload ảnh nhân vật
3. **Template 3 (Shot List)**: dùng khi anh muốn override Director — tạo plan thủ công paste vào brief với prefix "FORCE_SHOT_LIST:\n"
4. **Template 4 (Storyboard)**: đây là internal prompt CineForge auto-build cho Master Board. Anh có thể paste vào Midjourney/Flux để A/B test riêng.
