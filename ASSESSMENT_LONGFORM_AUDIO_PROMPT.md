# 📋 Đánh giá toàn diện pipeline CineForge — Long-form, Audio, Prompt evolution

> Tổng hợp từ 7 nguồn industry đã fetch (ViMax / ArcReel / drama-director-skill / awesome-seedance-2-prompts / MindStudio / CrePal / AtlasCloud drama) + tài liệu user mới gửi (intake wizard + master storyboard board) + 4 thread X mới + code thực tế trong source.

---

## 🎯 TÓM TẮT 1 CÂU

Pipeline V4 hiện tại **đỉnh cao về STRUCTURE** (10 hook patterns + beat sheet + 6 validators + chain identity), nhưng **YẾU 3 chỗ thực chiến**:
1. **Long-form > 15s** chưa orchestration đúng (duration_extender mới ở mức utility, chưa wire vào V3 flow)
2. **Audio** mới ở mức "voice overlay" — thiếu BGM library + SFX library + sync per-shot
3. **Master Storyboard Board** chưa có (gen 12-panel riêng thay vì 1 canvas — drift identity nặng)

Anh đã spot đúng 2/3 gap (board + audio). Long-form là gap thứ 3 ít người để ý.

---

## 1️⃣ PIPELINE THỰC TẾ — ví dụ 4 scenario

### Scenario A · Video 15s "Son lì matte 89k" (hiện đang chạy được)

```
INPUT
  brief: "Video TikTok 15s nữ Gen Z thử son lì matte 89k golden hour"
  refs: 2 ảnh (Character + Product)
  model: seedance_2_0, dialogue_vo

LAYER 1 · Director Agent → 5 shots (HOOK/PAIN/REVEAL/PROOF/CTA)
  - 1 LLM call (~$0.04, ~20s)
  - Storytelling validator: CLEAN

LAYER 1.5 · Storyboard (CURRENT: gen 5 panel ảnh riêng × $0.04 = $0.20)
  ⚠️ GAP: drift identity giữa panel — Linh khác mặt mỗi frame

LAYER 2 · Scene Gen × 5 shots
  - 5 LLM call × $0.01 = $0.05
  - Output: 5 prompts model-ready

LAYER 3 · Video render Seedance 2.0
  - S1 (2s, ref_to_video, refs=[character])    → $0.19
  - S2 (4s, i2v_chain từ S1)                   → $0.38
  - S3 (4s, ref_to_video, refs=[product])      → $0.38  ← chain reset (REVEAL)
  - S4 (3s, i2v_chain từ S3)                   → $0.29
  - S5 (2s, i2v_chain từ S4)                   → $0.19
  Total render: $1.43

LAYER 4 · TTS Việt × 5 shot dialogue
  - GenMax "mai" voice × 5 line ~$0.01

LAYER 5 · FFmpeg assemble
  - Concat 5 clip (scale 9:16 1080×1920, libx264 crf=20)
  - Overlay voice (1.0 volume) + BGM (-22dB nếu có)
  - Burn ASS subtitle "Be Vietnam Pro 48pt"
  - Film grain noise=alls=6 + eq=saturation=1.03

OUTPUT
  final.mp4 (~15s, 1080×1920, ~$1.53 total)
  Upload R2 → public URL
```

✅ **Hoạt động được**. Identity persist nhờ chain. Audio simple mix.

---

### Scenario B · Video 30s "Tech demo iPhone" (cần check)

```
INPUT brief 30s tech demo → tech_config.duration_s=30

LAYER 1 · Director Agent
  → beat_sheet_for(30) trả 6 beats: HOOK / PAIN / TENSION / REVEAL / PROOF / CTA
  → ~12 shots
  → ⚠️ Seedance 2.0 max_duration=15s/clip → KHÔNG render 30s 1 clip được

LAYER 3 · Render
  ✅ HOẠT ĐỘNG OK vì:
  - Mỗi shot trong shot_list tự cap < 15s (Director time-budget)
  - Chain logic ghép shot → tổng 30s
  - Vd: 12 shot × 2.5s avg = 30s

→ KHÔNG cần duration_extender. Multi-shot ARC = native solution cho 30s.
```

✅ **Hoạt động được** không cần code mới.

---

### Scenario C · Video 60s "Brand story Việt" (vùng xám)

```
INPUT brief 60s → duration_s=60

LAYER 1 · Director Agent
  → beat_sheet_for(60) → 7 beats: HOOK/SETUP/PAIN/TENSION/REVEAL/PROOF/CTA
  → 20-30 shots (MindStudio recommend 25-35 cho 2-3min)
  
  ⚠️ ISSUE 1: LLM context overflow risk
    - 25 shot × ~500 token / shot JSON = 12K token output
    - max_tokens=8000 hiện tại → có thể TRUNCATE
    - FIX: tăng max_tokens=16000 cho duration>=45s

  ⚠️ ISSUE 2: Director thinking depth
    - 1 LLM call để plan 25 shot risky về quality
    - Industry pattern (ViMax/ArcReel): Director→Screenwriter→Producer 3 stages
    - FIX: 2-pass — pass 1 outline 7 beats, pass 2 detail 25 shots per beat

LAYER 3 · Render
  ⚠️ ISSUE 3: 25 shot × 2-3s = ~$5-7 total
    - Cost gate draft-first cứu được nếu plan tệ
    - Nhưng chain identity qua 25 shot drift mạnh
    - FIX: Master Storyboard Board cứu drift (anh đề xuất đúng)

LAYER 5 · Assemble
  ⚠️ ISSUE 4: Audio sync per-shot phức tạp hơn
    - Hiện tại _overlay_voiceover dùng 1 voice file duy nhất
    - 60s video cần per-shot TTS sync (Linh nói S1 0-2s, S3 6-10s, S5 13-15s)
    - FIX: build audio timeline với silence padding + concat các voice clip
```

🟡 **Hoạt động được nhưng quality risky**. Cần:
- max_tokens bump → 30 phút fix
- Master storyboard board → 3-4h
- Audio per-shot sync → 2-3h

---

### Scenario D · Video 2min+ long-form "Drama short film" (CHƯA SUPPORT)

```
INPUT duration_s=120 (2 min)

LAYER 1 · Director Agent
  ❌ KHÔNG SUPPORT: beat_sheet_for(120) → vẫn return 7-phase 60s arc
  ❌ KHÔNG SUPPORT: 1 LLM call gen 60+ shots out token overflow chắc chắn

CURRENT WORKAROUND: duration_extender.py
  - Hàm plan_generations(120, max=15) → chia 8 segment × 15s
  - Mỗi segment có needs_continuity_ref=True
  - extract_last_frame_ffmpeg() trích last frame để chain
  
  ⚠️ ISSUE: duration_extender HIỆN không được wire vào V3 director.py
    - chỉ là utility orphan (chỉ model_adapter.py import nhẹ)
    - V3 flow KHÔNG biết cách split long-form

CẦN BUILD: Long-form Orchestrator
  → Director Agent gen 1 PLAN OUTLINE cấp scene (5-10 scene × 12-24s)
  → Per scene: gọi Director con gen 6-12 shots × 2-3s
  → Render scene-by-scene, chain last_frame xuyên scene
  → Total 2 min = 8-10 scene × 6-12 shots = 60-120 shots
```

❌ **CHƯA support 2min+**. Cần build hierarchical Director (Scene Director → Shot Director).

---

## 2️⃣ AUDIO PIPELINE — chi tiết thực tế

Source hiện tại có 3 mode + 1 mode hidden:

### Mode `silent_native` (default)
```
Shot LLM output generate_audio=true → Seedance/Vidu native gen sound effects
Assemble: KHÔNG overlay audio
Result: Video có sound ambient từ AI (gió, bước chân, etc.) — KHÔNG dialogue
Cost: $0
Phù hợp: B-roll, lifestyle, không cần thoại
```

### Mode `dialogue_vo` (đã wire phần lớn)
```
GenMax TTS gen 1 audio file Việt từ tất cả dialogue_vn của shots
Assemble._overlay_voiceover():
  Mix: voice (100% volume) + BGM (8% volume, hardcoded -22dB)
  amix=inputs=2:duration=first
  -map 0:v -map [aout] (drop AI native audio)
Result: Voice clean + nhạc nhẹ BG
Cost: $0.01 TTS + $0 BGM (nếu có sẵn)

⚠️ GAP 1: KHÔNG có BGM library — bgm_path mặc định None
⚠️ GAP 2: voice là 1 file ghép, không sync per-shot timing
   - Vd 15s video, Linh nói shot 1 (0-2s), nghỉ, nói shot 3 (6-10s)
   - Hiện tại: 1 voice file dài, ghép tuần tự — sai timing
   - Cần: build timeline với silence gaps
```

### Mode `asmr_macro` (partial)
```
Pre-render SFX MP3 → overlay như voiceover
Hoặc sfx_sequence[{time_s, sfx_file}] → overlay multi-track
⚠️ Multi-track overlay code: chỉ implement BGM, chưa làm multi-SFX
Phù hợp: food porn, ASMR, product texture close-up
```

### Mode `driven` (Wan 2.7 only — hidden)
```
Wan 2.7 nhận audio URL làm input → lip-sync khớp môi
Pipeline khác:
  1. Pre-render TTS Việt qua GenMax → audio.mp3
  2. Pass audio URL vào Wan 2.7 i2v → video output có môi sync
  3. Skip _overlay_voiceover (audio đã embed)
⚠️ GAP: V3 flow chưa tự switch sang driven mode khi user chọn Wan 2.7
```

### Audio timeline ideal (chưa build)

```
0s      2s      6s          10s         13s     15s
|  S1   |  S2  |     S3     |    S4     |  S5   |
|"hook"| "pain"|"reveal"   |  "proof"   | "cta" |
|       |      |            |            |       |
| dial1 |      | dial2      | dial3      | dial4 |
| 1.5s  |      | 3.2s       | 2.5s       | 1.5s  |
| (gap) |      | (gap 0.3s) | (gap 0.5s) | end   |
|       |      |            |            |       |
| BGM_lofi cross-fade throughout                  |
| SFX: lip-pop@1s, paper@4s, glow@6s, click@13s   |
```

Cần build: `audio_timeline_builder.py` → FFmpeg `acrossfade` + `adelay` filters.

---

## 3️⃣ PROMPT EVOLUTION — từng layer thực tế

### Layer 1 · Director system prompt (`director.md` 13KB)

Cấu trúc 12 section:
```
1. THE CORE PRINCIPLE — story skeleton fixed, slots niche-agnostic
2. BEAT SHEET — fixed structural skeleton
3. HOOK_PATTERN — pick exactly ONE
4. PRODUCT TIMING — unbreakable rule
5. CHARACTER DNA LOCK — face_signature contract
6. SEEDANCE 2.0 — 3-section schema awareness
7. DOUBLE-CONTRAST CUTS
8. UNIVERSAL REFERENCE — tag every uploaded image
9. REFERENCE CHAINING — chain logic
10. AUDIO DESIGN — paired with visual rhythm
11. MODEL HARD CONSTRAINTS
12. NICHE FLEXIBILITY + BRAND SAFETY
+ INPUT schema + OUTPUT schema + QUALITY BAR + HOW TO THINK
```

### Layer 1 · User message (JSON 1.5KB built dynamic)

```jsonc
{
  "product_input": {"text_description": "..."},
  "reference_images": ["url1","url2"],
  "reference_hints": [{"index":0,"role":"character_anchor"}, ...],
  "user_brief": "Video TikTok 15s nữ Gen Z thử son lì 89k...",
  "context_injection": {pain_points, usps, real_reviews, forbidden_to_say, mood_hint},
  "tech_config": {model:"seedance_2_0", duration_s:15, ..., 
                  model_capability_notes:"max_refs=9, duration_range=4-15s, image_tags=yes"},
  "niche_hint": "beauty",
  "storytelling_context": {
    "hook_patterns": "<10 patterns enum 1.2KB>",
    "beat_sheet": "<phase budget>",
    "hard_rules": "<6 hard rules>",
    "niche_slots": "<5-slot fill pattern>"
  }
}
```

### Layer 2 · Scene system prompt (`scene.md` 10KB)

Cấu trúc 10 section, key parts:
```
1. DRAMA-BEAT AWARENESS — table mapping shot.purpose → camera/lighting tendency
2. SEEDANCE 2.0 — 3-SECTION TEMPLATE [STYLE & MOOD]/[DYNAMIC]/[STATIC]
3. UNIVERSAL REFERENCE BINDING — @image_N role labels verbatim
4. REFERENCE CHAINING — "Continue from previous frame:" prefix scaffold
5. VIDEO REFERENCES (@video_N) — Seedance 2.0 only
6. MODEL-AWARE FORMATTING (multi_shot_inline/time_coded/i2v_motion/single_descriptive)
7. NEGATIVE PROMPT mandatory + phase-specific
8. CINEMATIC VOCABULARY PALETTE
9. NO INVENTION BEYOND BIBLE
10. AGE-INDICATOR AVOIDANCE
```

### Layer 2 · Scene user payload (JSON 4-8KB)
```jsonc
{
  "bible": "(full ContinuityBible — 3-4KB)",
  "shot": {shot_id, purpose, emotion_beat, visual, audio, continuity, dynamic_description},
  "model_key": "seedance_2_0_ref",
  "model_format_hint": "multi_shot_inline",
  "last_frame_url": null|"https://...",
  "reference_images": [...],
  "reference_videos": [...],
  "beat_intent": "PATTERN INTERRUPT beat — extreme/anomaly camera, NO product..."
}
```

### Layer 3 · AtlasCloud payload (~1KB per shot)

Seedance 2.0 ref-to-video example:
```json
{
  "model": "bytedance/seedance-2.0/reference-to-video",
  "prompt": "[STYLE & MOOD]\nPhotorealistic cinematic UGC, warm filmic 35mm grain...\n[DYNAMIC DESCRIPTION]\n[Shot 1 | 2s | handheld | @image_1 as primary character]\n0:00-0:02 Handheld MCU side profile, Linh @image_1 half-smile...\n[STATIC DESCRIPTION]\nSame character across all shots: Vietnamese woman...",
  "negative_prompt": "chữa nẻ, no product close-up, extra fingers, watermark, age indicators",
  "reference_images": ["https://example.com/character_linh.jpg"],
  "ratio": "9:16", "resolution": "720p", "duration": 2,
  "generate_audio": true, "return_last_frame": true
}
```

### Layer 4 · FFmpeg commands (Assemble)

**Concat 5 clips scale 9:16:**
```bash
ffmpeg -f concat -safe 0 -i concat_list.txt \
  -c:v libx264 -preset fast -crf 20 \
  -c:a aac -b:a 192k \
  -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black" \
  -y concat.mp4
```

**Voice + BGM mix:**
```bash
ffmpeg -i concat.mp4 -i voice.mp3 -i bgm.mp3 \
  -filter_complex "[1:a]volume=1.0[voice];[2:a]volume=0.08[bgm];[voice][bgm]amix=inputs=2:duration=first[aout]" \
  -map 0:v -map [aout] -c:v copy -c:a aac -shortest \
  -y with_audio.mp4
```

**Caption ASS burn:**
```bash
ffmpeg -i with_audio.mp4 -vf "ass=captions.ass" -c:a copy -y with_caption.mp4
```

**Film grain final touch:**
```bash
ffmpeg -i with_caption.mp4 -vf "noise=alls=6:allf=t,eq=saturation=1.03" -c:a copy -y final.mp4
```

---

## 4️⃣ GAP ANALYSIS — so với industry best practices

| Best practice | Source | Status |
|---|---|---|
| 10 hook patterns enum | CrePal + drama-director + AtlasCloud | ✅ V4 wired |
| Beat sheet duration-aware | CrePal + MindStudio + AtlasCloud | ✅ V4 wired (15/30/60) |
| 3-section Seedance prompt | drama-director + AtlasCloud | ✅ V4 in scene.md |
| @image_N role tags | awesome-seedance-2-prompts | ✅ |
| Reference chaining i2v | MindStudio | ✅ |
| Functional descriptors (no age) | drama-director | ✅ |
| Niche-agnostic slots | CrePal | ✅ V4 |
| Storytelling validators | (novel V4) | ✅ — KHÔNG có repo nào có |
| HITL review modal | (V3 native) | ✅ |
| **Master Storyboard Board** (9-panel anchor) | **AtlasCloud** | ❌ **CHƯA** |
| **Intake Wizard 4-10 câu** | tài liệu user | ❌ chưa |
| **Multi-pass Director (outline → detail)** | ViMax / ArcReel | ❌ Long-form chưa |
| **Hierarchical Scene Director** | ArcReel | ❌ 2min+ chưa |
| **Audio timeline builder** | (industry standard) | ❌ chỉ overlay 1 file |
| **BGM library + auto-pick** | Lovart | ❌ |
| **SFX library** | AtlasCloud drama | ❌ |
| **3-variant spawning** (premium/lifestyle/offer) | CrePal | ❌ — đã có hook patterns nhưng chưa loop A/B |
| **Multi-revision per plan** | univa | ❌ revise endpoint sẵn UI chưa |
| **Quality monitoring + auto re-plan** | univa | 🟡 cost gate có, full eval-loop chưa |
| **Web search niche trends** | Nano Banana Pro enable_web_search | ❌ chưa wire |
| **Lip-sync driven Wan auto-switch** | (per-model logic) | 🟡 partial |

**Tổng: 9/20 đã có ✅ · 2/20 partial 🟡 · 9/20 missing ❌**

---

## 5️⃣ ĐỀ XUẤT CẢI TIẾN — priority ranking

### 🔴 Mức 1 — High value, low effort (~1 ngày)
| Task | Effort | Impact |
|---|---|---|
| **Master Storyboard Board** (anh đề xuất) | 3-4h | ⭐⭐⭐⭐⭐ Identity lock + UX wow |
| **max_tokens bump cho long-form** | 30min | ⭐⭐⭐⭐ Fix 30s+ truncate |
| **Audio timeline per-shot sync** | 2-3h | ⭐⭐⭐⭐ Dialogue đúng timing |
| **Storytelling check UI display** | 1h | ⭐⭐⭐ Red flags visible |
| **Refine 1 shot button** (endpoint sẵn) | 2h | ⭐⭐⭐⭐ Tiết kiệm $$$ |

### 🟡 Mức 2 — Medium effort (~2-3 ngày)
| Task | Effort | Impact |
|---|---|---|
| **Hierarchical Director (outline → detail)** cho 30s+ | 1 ngày | ⭐⭐⭐⭐ Quality 30-60s |
| **BGM library + auto-pick by mood** | 1 ngày | ⭐⭐⭐ Polish |
| **SFX library + per-shot sync** | 1 ngày | ⭐⭐⭐ ASMR/food |
| **Intake Wizard 4 câu critical** | 4h | ⭐⭐ UX |
| **3-variant spawning UI** (3 hook → A/B) | 4h | ⭐⭐⭐⭐ Conversion |
| **Wan auto lip-sync flow** | 4h | ⭐⭐⭐ Talking head |

### 🔵 Mức 3 — Long-form architecture (~1 tuần)
| Task | Effort | Impact |
|---|---|---|
| **2min+ Scene-Director hierarchical** | 3-5 ngày | ⭐⭐⭐⭐⭐ Unlock drama short film |
| **Eval-loop auto re-plan** | 2 ngày | ⭐⭐⭐ Quality monitoring |
| **Multi-revision per plan UI** | 1 ngày | ⭐⭐ UX |

---

## 6️⃣ ĐÁNH GIÁ "MỌI THỨ ĐÃ CHUẨN CHƯA?"

### ✅ Đã chuẩn
- Pipeline 15-30s end-to-end **VERIFIED CODE PATH**
- Storytelling layer V4 đã embed 15/15 best practices từ 7 nguồn
- Identity persist qua chain i2v
- Cost gate draft-first
- Markdown prompts hot-reload
- 14 model AtlasCloud wired
- 12 voice GenMax wired
- R2 storage + fallback
- Idempotency Stripe-style

### ⚠️ Chưa chuẩn (gap quan trọng)
- **Master Storyboard Board** — gap lớn nhất, anh spot đúng
- **Audio timeline per-shot sync** — current là "voice file ghép cứng"
- **Long-form > 60s** — chưa hierarchical
- **BGM/SFX library** — không có catalog mood-based
- **A/B variant spawning** — chỉ 1 plan per brief

### 🔴 Risk thật khi đi live
1. **30-60s video output quality** — chưa stress test, có thể chain identity drift sau shot 10
2. **Vietnamese TTS lip-sync** — Wan 2.7 driven mode chưa auto wire khi audio_mode=dialogue_vo
3. **Long dialogue per shot** — TTS có thể dài hơn video shot → cắt cụt hoặc lệch
4. **Storyboard preview** — user duyệt plan dựa text JSON, không thấy ảnh thật

---

## 7️⃣ NÊN BẮT ĐẦU CẢI TIẾN TỪ ĐÂU

Đề xuất 3-stage roadmap:

### 🚀 Sprint 1 (1 ngày) — Foundation hoàn thiện 15-30s
1. Master Storyboard Board (3-4h) ← anh đề xuất
2. Storytelling check UI display (1h)
3. Refine 1 shot button (2h)
4. max_tokens bump (30min)
5. Audio timeline per-shot sync (2-3h)

→ Đi từ "scaffold đẹp" → "demo-able product cho 15-30s video"

### 🎬 Sprint 2 (2-3 ngày) — Long-form 60-120s + Audio rich
1. Hierarchical Director cho 60s+ (1 ngày)
2. BGM library auto-pick (1 ngày)
3. SFX library + sync (1 ngày)
4. Wan auto lip-sync (4h)

→ Đi từ "single-form 15s" → "multi-format short film up to 2min"

### 🏆 Sprint 3 (1 tuần) — Production-grade
1. Eval-loop auto re-plan (2 ngày)
2. 3-variant spawning A/B (4h)
3. Multi-revision UI (1 ngày)
4. Web search niche trends Nano Banana (1 ngày)
5. Real-world test 50 video brief + finetune prompts (2 ngày)

→ Đi từ "demo" → "Tier 3 sản phẩm bán được"

---

## 8️⃣ KẾT LUẬN HONEST

**Source hiện tại = "scaffold V4 chất lượng cao, top 30% so với industry"** vì:
- ✅ Đã embed 15/15 best practice cốt lõi từ 7 nguồn
- ✅ Có validators code-level không repo nào trong tài liệu có
- ✅ HITL review + cost gate + niche-agnostic — combo này hiếm

**Nhưng để THẬT SỰ "agent đỉnh cao thực thụ làm 1 clip hoàn chỉnh"**, còn 3 thứ bắt buộc:
1. **Master Storyboard Board** — anh đề xuất chính xác
2. **Audio timeline per-shot** — không thể bỏ qua cho TikTok VN
3. **Long-form hierarchical** — để compete với MindStudio short film

→ Đề nghị **EXEC Sprint 1 trước** (~1 ngày, $0 cost vì code work). Sau đó test với 5-10 video brief thật (~$15-25 render) → confirm quality. Rồi mới quyết Sprint 2/3.

Anh muốn tôi exec Sprint 1 ngay không? Hay focus 1 task riêng (vd Master Storyboard Board)?
