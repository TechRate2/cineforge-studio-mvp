# 🎥 Grok V3 — Tìm MANUAL WORKFLOW từng model (creator pro làm thủ công)

> **Khác V1/V2**: V1 best-practices chung. V2 case studies có video output. **V3 = step-by-step MANUAL workflow** từ creator chuyên nghiệp đã ra video thực chiến — để tôi reverse-engineer thành pipeline automated chuẩn.

> **Mục đích**: Hiểu cách 1 creator pro **THỦ CÔNG** dùng từng model từ A-Z, từ prep input (ảnh ref, prompt) → gen → retry → post-prod → final. Từ đó cải tiến pipeline automated CineForge đúng cách họ làm.

---

## 📋 CONTEXT GỬI GROK

Tôi đang vận hành AI video agent gen video TikTok/Reel/Drama VN. Stack: Next.js + FastAPI + AtlasCloud + GenMax TTS. Pipeline automated nhưng cần verify đúng cách dân pro làm thủ công.

Tôi cần Grok tìm **manual workflow documentation** — nghĩa là creator đã viết/quay lại CÁCH HỌ LÀM CỤ THỂ với từng model, không phải tutorial nhanh.

### Loại nguồn ưu tiên TÌM

✅ **TOP TIER nguồn cần**:
- Long-form YouTube "How I made X with [model]" (15+ phút, full screen recording)
- Twitter/X thread dài (10+ tweet) "From brief to final — my workflow"
- Medium/Substack "Behind the scenes: making my viral [model] video"
- Reddit r/aivideo step-by-step post với screenshots mỗi step
- Discord pinned message "Production guide" của community
- Notion / Google Doc workflow share publicly
- GitHub README workflow templates với examples

✅ **Specific creators worth searching** (nếu họ đã share workflow):
- Bilawal Sidhu (@bilawalsidhu) — AI cinematic creator
- Heather Cooper (@HBCoop_) — Seedance early adopter
- Iancu (@Iancu_ai) — GPT Image + Seedance workflow
- Ben Bauchau (@BenBauchau) — Character consistency expert
- Pierrick Chevallier (@PierrickChev) — French AI filmmaker
- Cristóbal Valenzuela (@c_valenzuelab) — Runway founder, ad workflow
- Curious Refuge — AI filmmaking course content
- Karen X. Cheng (@karenxcheng) — viral AI content
- Brett Cooper (@brettcooper24) — Hollywood-grade AI
- Lyndoc (Discord/YouTube) — Vidu workflow

❌ **SKIP**:
- Tutorial dưới 5 phút (không đủ detail)
- Compilation reel without explanation
- Vendor marketing
- Affiliate content "earn $1000/day with AI"

---

## 🎬 6 DOSSIER MANUAL WORKFLOW per model

### DOSSIER 1: **Seedance 2.0 manual workflow** — making a 15s ad/short

Yêu cầu Grok tìm 5-10 nguồn trả lời cụ thể:

#### Phase 1: Pre-production (TRƯỚC khi gen)
1. **Brief writing** — họ viết brief thế nào? Có template gì?
2. **Reference gathering** — họ thu thập bao nhiêu ảnh ref? Từ đâu (Pinterest, Midjourney gen riêng, photo shoot thật)?
3. **Reference quality requirements** — DPI, lighting, angle... cụ thể
4. **Storyboard sketching** — họ vẽ tay, dùng Procreate, hoặc gen GPT Image 2 / Midjourney trước? Bao nhiêu panels?

#### Phase 2: Prompt engineering (CÁCH viết prompt)
1. **Structure prompt thực tế** họ dùng — copy verbatim
2. **Iteration count** — bao nhiêu lần sửa prompt trước khi gen?
3. **A/B test prompts** — họ test 2-3 variant không?
4. **Specific words/phrases** họ phát hiện hoạt động tốt (camera verbs, lighting terms, style words)
5. **Words/phrases họ TRÁNH** (trigger filter, gây drift)

#### Phase 3: Generation settings
1. **Atlas/Higgsfield/WaveSpeed/Replicate** — họ chạy ở platform nào? Lý do?
2. **Tier** Standard vs Fast — pick khi nào?
3. **Resolution** — 720p/1080p/1440p? Trade-off
4. **Duration sweet spot** — họ pick 5/10/15s? Tại sao
5. **Reference upload order** — quan trọng không? Đầu/cuối?
6. **Seed** — fix seed hay random?

#### Phase 4: Trial-error iteration
1. **Average retries** per final shot — 2 lần, 5 lần, 10 lần?
2. **Cost per usable clip** thực tế (3-5x base cost?)
3. **Failure modes** specific — face morph, NSFW trigger, action wrong, camera drift...
4. **Recovery strategy** — họ làm gì khi gen fail? Sửa prompt? Đổi ref? Đổi model?

#### Phase 5: Post-production (SAU khi có MP4)
1. **Upscaling** — Topaz Video AI? CapCut AI? Khi nào dùng?
2. **Color grading** — DaVinci Resolve? Premiere? Preset nào?
3. **Audio mixing** — Audition? CapCut? Music library nào?
4. **Caption burning** — manual hay tool tự động?
5. **Final export settings** — bitrate, codec, container

#### Phase 6: Distribution
1. **Platform optimization** — TikTok 9:16 vs Reel 9:16 — khác biệt
2. **Posting strategy** — peak hours VN, hashtags
3. **Performance tracking** — họ measure thế nào (views, CTR, engagement)

---

### DOSSIER 2-6: **Seedance 2.0 Fast / Seedance 1.5 Pro / Vidu Q3 / Vidu Q3-Mix / Wan 2.7**

Yêu cầu **6 phase tương tự** cho mỗi model, focus điểm đặc thù:

| Model | Điểm đặc thù cần dig | Question đặc thù |
|---|---|---|
| **Seedance 2.0 Fast** | Khi nào pick Fast vs Standard? | A/B 10 use case → 80% nào dùng Fast OK? |
| **Seedance 1.5 Pro** | Single anchor i2v quality | Họ chọn ảnh anchor thế nào? Crop ratio? Lighting? |
| **Vidu Q3** | Array-order binding | Trick gì để bind đúng character khi 2-3 nhân vật cùng đồ? |
| **Vidu Q3-Mix** | `@image_N` syntax thật | Có khác `@image_1 as primary` vs `@image1 character`? |
| **Wan 2.7** | Lip-sync VN thực tế | TTS provider tốt nhất sync khớp môi? Voice trẻ vs già? Speed normal vs slow? |

---

## 🎯 META TOPICS — Manual workflow cross-model

### Topic E: Pre-production thủ công chuẩn

Bộ tool dân pro dùng:
1. **Reference gen tool** — Midjourney v7 vs Flux Pro Ultra vs Imagen 4 — họ pick nào cho character anchor?
2. **Mood board tool** — Milanote, Eagle, Pinterest sections?
3. **Brief template** — copy paste structure (Hooks library, character bible template)
4. **Image enhancement** — Topaz Photo AI, Magnific upscaler — workflow cụ thể

### Topic F: Render farm management

1. **Multi-platform strategy** — họ dùng 1 platform hay xoay vòng (Higgsfield + WaveSpeed + Replicate + Atlas)?
2. **Cost tracking** — sheet/Notion tracking spend per project
3. **Parallel jobs** — gen 3-5 variant cùng lúc rồi pick best?
4. **Failed gen recycle** — họ giữ và remix gen lỗi không?

### Topic G: Post-production toolchain thực tế

1. **Stack chuẩn industry** AI creator pro:
   - Upscale: Topaz Video AI 6.0+ vs Magnific Video?
   - Frame interpolation: Topaz Apollo? Flowframes? RIFE-NCNN?
   - Color: DaVinci Resolve Studio preset chuyên cho AI video?
   - Stabilization: Topaz Vlog stabilizer? After Effects Warp?
   - Compositing: After Effects layered? Premiere Pro?
2. **Time spent post-prod vs gen** — ratio?
3. **Manual fix common AI artifacts** — extra fingers / face morph / text overlay glitch — họ xử lý thế nào?

### Topic H: Distribution + analytics

1. **TikTok / Reel / Short upload spec** chính xác 2026
2. **Caption template VN winning** — emoji ratio, hashtag count, hook word
3. **Performance analytics** — họ track metric nào? Tool gì?

---

## 📤 FORMAT OUTPUT GROK PHẢI TRẢ VỀ

```markdown
## DOSSIER [N]: [Model name] — MANUAL WORKFLOW

### Source 1: [URL]
- **Type**: YouTube long-form / X thread / Medium / Reddit / Discord
- **Author**: [handle] (followers, niche)
- **Date**: YYYY-MM-DD
- **Quality**: views/likes/comments
- **Length**: total minutes (YouTube) OR tweet count

### PHASE 1 — Pre-production
- Brief writing: [họ viết thế nào, có template không?]
- References: [bao nhiêu ảnh, từ đâu, gen tool nào?]
- Storyboard: [tool, panel count, gen process]

### PHASE 2 — Prompt engineering
- **Full prompt structure** (copy-paste):
   ```
   [verbatim prompt họ dùng]
   ```
- Iteration count: [N lần sửa]
- Words that worked: [list]
- Words that failed: [list]

### PHASE 3 — Generation settings
- Platform: [Atlas / Higgsfield / WaveSpeed / Replicate]
- Tier: [Fast / Standard / Pro]
- Resolution: [720p/1080p/1440p]
- Duration: [Xs] · sweet spot reason: ...
- Refs order: [primary first vs last vs middle]
- Seed: [fixed / random]

### PHASE 4 — Trial-error
- Average retries: [N attempts to get usable clip]
- Cost per usable clip: $X (after retries)
- Top 3 failure modes: ...
- Recovery strategy: ...

### PHASE 5 — Post-production
- Upscale tool: [Topaz Video AI / Magnific / none]
- Color grade: [DaVinci / Premiere / preset name]
- Audio: [Audition / CapCut / source library]
- Caption: [manual / auto]
- Export: [bitrate, codec]

### PHASE 6 — Distribution
- Platform: [TikTok / Reel / Short / YouTube]
- Spec compliance: [aspect, length, file size limits]
- Posting time: [peak hours their data]
- Performance achieved: [views, CTR if shared]

### KEY INSIGHTS FOR CINEFORGE
1. ...
2. ...
3. ...

### TIMELINE EXAMPLE
"Made 15s lipstick ad in 47 minutes total":
- 0:00-08:00 Brief + ref gathering
- 08:00-15:00 Prompt iteration (3 versions)
- 15:00-25:00 Gen + retry (4 attempts, kept 2nd)
- 25:00-35:00 Upscale Topaz + color DaVinci
- 35:00-40:00 Audio mix + caption
- 40:00-47:00 Export + upload TikTok
```

---

## 🚫 ANTI-FLUFF FILTER

Skip nếu:
- Không có actual phase-by-phase breakdown
- Không có time spent per phase
- Không có actual tool name (Topaz / DaVinci / specific)
- Không có cost number
- Không có failure example
- "Easy AI video in 1 click" content farm
- AI-generated meta tutorial

---

## 📊 VOLUME TARGET

- Mỗi dossier: **3-7 high-quality manual workflow** sources
- Meta topics: **3-5 sources mỗi topic**
- Total expected: **30-50 verified manual workflow guides**

Ưu tiên 2025-2026 publication. Older paper foundational OK nếu vẫn relevant.

---

## ⚙️ SAU KHI CÓ OUTPUT

Anh paste output Grok về cho tôi. Tôi sẽ:
1. **Reverse-engineer manual workflow** từng model thành automated pipeline
2. **Identify pre-prod step** CineForge nên hỗ trợ trong UI (vd: brief template, ref quality check, storyboard preview)
3. **Identify post-prod step** CineForge nên integrate (vd: auto Topaz upscale, DaVinci color preset, CapCut caption export)
4. **Trial-error pattern** → update model_picker + retry logic (avg retries / cost gate threshold)
5. **Failure mode catalog** → expand validator + scene.md anti-patterns
6. Commit updates với reference từng source

Goal: pipeline CineForge = **automation of consensus manual workflow** từ 30-50 pro creator real.
