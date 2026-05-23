# 🎬 Ví dụ thực tế end-to-end — CineForge V4

> Brief: *"Video TikTok 15s nữ Gen Z thử son lì matte 89k tại bàn make-up, golden hour, hook đầu phải mạnh"*
>
> Bài này trace TỪNG LAYER với JSON THẬT (chạy bằng `_design_refs/demo_pipeline.py`). Full output trong `_design_refs/demo_pipeline_output.txt`.

---

## 🗺️ Bản đồ pipeline

```
Studio UI → Director Agent V4 → HITL Review → Scene Gen V4 → AtlasCloud → Assemble → R2
            (1 LLM call,        (user duyệt   (N LLM call,    (N video    (FFmpeg     (storage)
             plan only)          trước render) 1/shot)         API call)   ghép)
```

Mỗi LLM call có:
- **System prompt** = file Markdown trong `backend/system_prompts/`
- **User message** = JSON input bundle
- **Output** = JSON strict theo schema

---

## 📥 STEP 0 · USER INPUT (từ Studio UI)

User mở `/studio`, điền 3 thứ:
1. **Brief** (textarea)
2. **Reference zones** (kéo thả ảnh — Character / Product / Storyboard)
3. **Settings** (model + duration + aspect + audio mode + context injection)

JSON gửi tới `/api/v1/director/plan/stream`:

```jsonc
{
  "product_input": {
    "text_description": "Son lì matte 89k, dưỡng ẩm 8h, không chì"
  },
  "reference_images": [
    "https://example.com/character_linh.jpg",
    "https://example.com/lipstick_product.jpg"
  ],
  "reference_role_hints": ["character_anchor", "product_hero"],
  "user_brief": "Video TikTok 15 giây cho nữ Gen Z thử son lì matte 89k tại bàn make-up. Cảm giác golden hour soft, confident, vibe UGC review thật. Hook đầu phải mạnh để giữ chân scroll.",
  "context_injection": {
    "pain_points": "Son hay bị khô môi sau 2-3h, dễ trôi khi ăn",
    "usps": "Dưỡng ẩm 8h liên tục, vegan, giá 89k cực hợp Gen Z VN",
    "real_reviews": "\"Mình lì cả buổi đi học không cần dặm lại\"",
    "forbidden_to_say": "Không nói chữa nẻ môi, không so sánh đối thủ",
    "mood_hint": "Chill confident, hơi flex một chút"
  },
  "tech_config": {
    "model": "seedance_2_0", "duration_s": 15,
    "aspect_ratio": "9:16", "resolution": "720p",
    "audio_mode": "dialogue_vo"
  },
  "niche_hint": "beauty"
}
```

→ FE hook: [`lib/studio/use-director-plan.ts:203`](lib/studio/use-director-plan.ts#L203) (`createPlan`)
→ BE route: [`backend/api/routes/director.py:356`](backend/api/routes/director.py#L356) (`/plan/stream`)

---

## 🎯 STEP 1 · LAYER 1 — Director Agent V4

### 1a. Sanitize input
`backend/agent/director_agent.py:97-120` — strip PII (số điện thoại VN, email, CCCD) + neutralize prompt injection từ `context_injection`. Lý do: user-supplied text vào prompt LLM → security boundary.

### 1b. Reference classification
Vì user đã tag role trong UI (zone Character/Product), skip vision LLM (~$0.01 saved). Code: `director_agent.py:165-175`.

Output `ref_hints`:
```json
[
  {"index": 0, "role": "character_anchor", "notes": "user-tagged"},
  {"index": 1, "role": "product_hero", "notes": "user-tagged"}
]
```

### 1c. **⭐ Build input bundle với storytelling injection (V4)**
Code: `director_agent.py::_build_director_input` (line 551).

Đây là step **MỚI V4** — tôi bồi đắp 4 block "storytelling_context" vào bundle gửi LLM:

```jsonc
{
  "product_input": {...},
  "reference_images": [...],
  "reference_hints": [...],
  "user_brief": "...",
  "context_injection": {...},
  "tech_config": {
    "model": "seedance_2_0",
    "duration_s": 15,
    "model_capability_notes": "user_model=seedance_2_0; max_refs_per_shot=9; duration_range=4-15s; audio_mode=native; image_tags=yes; multi_shot_inline=yes"
  },
  "niche_hint": "beauty",

  // 🆕 V4 STORYTELLING LAYER injection
  "storytelling_context": {
    "hook_patterns": "HOOK_PATTERN enum (pick exactly ONE for shot 1):\n- pattern_interrupt: ...\n- direct_question: ...\n- bold_statement: ...\n- lifestyle_cold_open: ...\n- pov_confession: ...\n- social_proof_drop: ...\n- visual_anomaly: ...\n- before_after_tease: ...\n- reaction_shot: ...\n- offer_led: ...",
    "beat_sheet": "BEAT SHEET (duration=15s, fill but don't restructure):\n- HOOK [0-2s] — Pattern interrupt, no product, no logo\n- PAIN [2-5s] — Show problem viewer recognizes\n- REVEAL [5-9s] — Product appears as the resolution\n- PROOF [9-12.5s] — Feature demonstrated via action\n- CTA [12.5-15s] — Explicit verb (Shop / Try / Link)",
    "hard_rules": "HARD RULES (auto-validated):\n- Shot 1 MUST NOT contain product as subject\n- Product first appears at REVEAL phase (≥30% runtime)\n- Each cut changes AT LEAST one of {camera_shot, camera_movement}\n- Sum of durations matches target ±2s\n- Primary character MUST have non-empty face_signature\n- CTA shot must contain explicit imperative verb",
    "niche_slots": "NICHE-AGNOSTIC SLOTS:\n- problem_statement\n- character_archetype\n- product_role\n- payoff_emotion\n- cta_verb\n→ Same skeleton works for beauty/tech/food/fashion/B2B."
  }
}
```

**Nguồn tài liệu**: storytelling_context được build từ `backend/agent/storytelling.py` (mới, 280 dòng). Các hằng số:
- `HOOK_PATTERNS` (10 patterns) ← tổng hợp từ **CrePal** (problem-solution / feature-led / social-proof / offer-led) + **drama-director-skill** (POV confession) + **AtlasCloud Seedance** (visual anomaly / double-contrast)
- `beat_sheet_for(15s)` ← từ **CrePal** 3-part rhythm + **MindStudio** 8-10 shots / 15s + **AtlasCloud** setup/rising/turn/resolution
- `hard_rules` ← từ **CrePal** "don't open with product close-up" + **AtlasCloud** double-contrast cut
- `niche_slots` ← từ **CrePal** output-review checklist universal

### 1d. **LLM call**
Code: `director_agent.py:205-213`.

```python
raw = llm.complete(
    system_prompt=load("director"),     # backend/system_prompts/director.md (13KB)
    user_message=director_user,          # JSON bundle bên trên
    task="generator",                    # DeepSeek-V4-Pro hoặc Claude Sonnet 4.6
    max_tokens=8000,
    temperature=0.65,
)
```

`director.md` (13KB, 12 section) khoá LLM theo:
- Beat sheet phải đúng skeleton
- Hook pattern phải chọn 1 trong 10
- Product không được mở video
- Face DNA phải concrete

### 1e. **Output DirectorPlan (example realistic)**

LLM trả về JSON `DirectorPlan`. Tóm tắt structure (bible + 5 shots cho 15s):

**Continuity Bible**:
```jsonc
{
  "title": "Son lì 89k thử thách 8 tiếng",
  "logline": "Linh thử son lì matte cả ngày — review thật không filter",
  "characters": [{
    "id": "char_linh",
    "name": "Linh",
    "face_signature": "Vietnamese woman, late 20s, shoulder-length straight black hair with subtle layers, warm fair skin, calm intelligent eyes",
    "outfit": "Cream knit cardigan over white silk camisole"
  }],
  "products": [{
    "id": "prod_son",
    "name": "Son lì matte 89k",
    "hero_features": ["Lì 8h", "Dưỡng ẩm", "Vegan"],
    "color_palette": ["#3D1A1A", "#C9A961"]
  }],
  "visual_style": {
    "cinematography": "handheld UGC iPhone with cinematic grading",
    "color_grading": "warm filmic teal-and-orange",
    "lighting_design": "golden hour soft window light"
  },
  "storytelling_meta": {                          // 🆕 V4 field
    "hook_pattern": "pov_confession",             // ← LLM picked 1 of 10
    "beat_coverage": ["HOOK","PAIN","REVEAL","PROOF","CTA"],
    "product_first_appearance_s": 6.0,            // ≥ 30% of 15s ✅
    "primary_emotion_arc": "curiosity → recognition → relief → trust → action"
  }
}
```

**Shot list** (5 shot, time-budget 0→15s):

| # | Start | Dur | Purpose | Subject (visual) | Camera | Has product? |
|---|---|---|---|---|---|---|
| S1 | 0 | 2s | **hook** | Linh side profile half-smile | MCU handheld | ❌ NO product |
| S2 | 2 | 4s | **pain** | Linh ngán nhìn gương, lau son cũ | WS push-in | ❌ NO product |
| S3 | 6 | 4s | **reveal** | Son lì 89k trên bàn ánh nắng | ECU pull-out | ✅ Product enter @ 6s (40% runtime) |
| S4 | 10 | 3s | **proof** | Linh apply son, môi căng matte | MCU static | ✅ |
| S5 | 13 | 2s | **cta** | Son + tag giá 89k overlay | MS push-in | ✅ |

Mỗi shot có schema giàu:
```jsonc
{
  "shot_id": "S1", "purpose": "hook", "emotion_beat": "pov_confession",
  "duration_s": 2,
  "visual": {
    "subject": "Linh side profile half-smile, looking down",
    "action": "tay đưa lên môi như chuẩn bị nói gì",
    "camera_shot": "MCU", "camera_movement": "handheld",
    "composition": "rule-of-thirds",
    "background": "blurred warm window backlight"
  },
  "audio": {
    "dialogue_vn": "Ok mình thử cái này 8 tiếng nha...",
    "caption_on_screen": "8 tiếng cùng son lì 89k"
  },
  "continuity": {
    "character_ids": ["char_linh"],
    "product_ids": [],                  // ← shot 1 không có product
    "reference_indices": [0],            // → @image_1
    "previous_shot_id": null
  },
  "dynamic_description": "0:00-0:02 Handheld MCU side profile, Linh half-smile, warm rim light from window right, slight head turn"   // 🆕 V4 field — timestamped Seedance beat
}
```

### 1f. **🆕 V4 Storytelling validator**
Code: `director_agent.py:300-322` gọi `storytelling.validate_plan(plan_dict)`.

Chạy 6 rule kiểm:

| Rule | Plan này |
|---|---|
| `PRODUCT_OPENS` (shot 1 ko có product) | ✅ S1 không có product |
| `PRODUCT_TOO_EARLY` (product < 30% runtime) | ✅ S3 reveal @ 6s = 40% |
| `DOUBLE_CONTRAST_VIOLATION` | ✅ Mọi cut đổi camera_shot HOẶC movement |
| `MISSING_HOOK` (no purpose=hook) | ✅ S1.purpose = "hook" |
| `DURATION_MISMATCH` (sum != target ±2s) | ✅ 2+4+4+3+2 = 15 |
| `WEAK_FACE_ANCHOR` (face_signature empty) | ✅ 14 từ concrete |

**Result: CLEAN — 0 issue.** Plan pass tất cả validators.

Nếu LLM phá rule (vd cho son xuất hiện shot 1) → emit SSE event `storytelling_check` về FE → user thấy red flag trong PlanModal.

### 1g. Evaluation Layer self-score
Code: `agent/evaluation_layer.py` — gọi LLM với `system_prompts/evaluation.md` chấm 5 dim (consistency / viral / cinematic / pacing / brand_safety) → overall score.

### 1h. Cost estimate
- Director plan: $0.04
- Vision scan: skipped (user-tagged)
- Eval: $0.005
- Render: 15s × $0.096 = $1.44
- TTS: $0.01
- **Total: ~$1.49 / video**

---

## ✋ STEP 2 · HITL REVIEW (DirectorPlanModal)

SSE complete event → FE mở `DirectorPlanModal` 3 tab:
- **Bible**: characters + visual_style + audio_design + setting
- **Shot List**: 5 cards với dialogue + camera + chain indicators
- **Evaluation**: 5 score gradient + strengths + red_flags

User có thể:
- **Approve & Render** → gọi `/director/generate` (đốt ~$1.5)
- **Close** → discard plan (chỉ tốn $0.04 plan cost)

→ FE: [`components/studio/DirectorPlanModal.tsx`](components/studio/DirectorPlanModal.tsx)

---

## 🎨 STEP 3 · LAYER 2 — Scene Gen per shot

Khi user Approve, `video_worker.render_plan()` chạy. Cho TỪNG shot, gọi Scene Gen:

### 3a. Build payload cho S1

```jsonc
{
  "bible": "(full bible passed — omitted)",
  "shot": {
    "shot_id": "S1", "purpose": "hook", "emotion_beat": "pov_confession",
    "visual": {...}, "audio": {...},
    "continuity": {
      "reference_indices": [0],
      "previous_shot_id": null
    },
    "dynamic_description": "0:00-0:02 Handheld MCU side profile, Linh half-smile, warm rim light from window right, slight head turn"
  },
  "model_key": "seedance_2_0_ref",
  "model_format_hint": "multi_shot_inline",
  "last_frame_url": null,
  "reference_images": [...],
  "reference_videos": [],

  // 🆕 V4 — derive từ shot.purpose
  "beat_intent": "PATTERN INTERRUPT beat — extreme/anomaly camera, high contrast cut, NO product, max scroll-stop impact."
}
```

→ Code: `agent/scene_generation_agent.py:475-510` (`_BEAT_INTENT` mapping)

### 3b. LLM call với `scene.md`
Code: `scene_generation_agent.py:492-498`.

System prompt `scene.md` (10KB) khoá:
- 3-section template cho Seedance (STYLE/DYNAMIC/STATIC)
- Per-purpose camera tendency table (hook → ECU/anomaly, reveal → push-in/warm)
- Role-aware @image_N tags
- Reference chaining scaffold prefix khi i2v

### 3c. Output Scene LLM

```jsonc
{
  "prompt": "[STYLE & MOOD]\nPhotorealistic cinematic UGC, warm filmic 35mm grain, shallow depth of field, anamorphic subtle flare. Palette: warm amber + soft window backlight.\n\n[DYNAMIC DESCRIPTION]\n[Shot 1 | 2s | handheld | @image_1 as primary character (exact face, hair, outfit from reference)]\n0:00-0:02 Handheld MCU side profile, Linh @image_1 half-smile, tay đưa lên môi như sắp nói, warm rim light from window right, slight head turn toward camera. Character speaks: \"Ok mình thử cái này 8 tiếng nha...\"\n\n[STATIC DESCRIPTION]\nSame character across all shots: Vietnamese woman, late 20s, shoulder-length straight black hair with subtle layers, warm fair skin, calm intelligent eyes. Outfit: cream knit cardigan over white silk camisole. Location: bàn make-up cửa sổ chiều, golden hour 4PM, warm intimate atmosphere.",

  "negative_prompt": "chữa nẻ, so sánh đối thủ, no product close-up, no logo, no brand watermark in opening frame, extra fingers, warped face, low quality, watermark, text overlay duplication, lens distortion, sudden shake, age indicators",

  "reference_image_indices": [0],
  "render_mode": "ref_to_video",
  "chain_input_url": null,
  "model_params": {
    "duration_s": 2, "resolution": "720p", "aspect_ratio": "9:16",
    "generate_audio": true, "return_last_frame": true
  }
}
```

**Nguồn template 3-section**:
- `[STYLE & MOOD]` / `[DYNAMIC]` / `[STATIC]` ← format từ **drama-director-skill** + **AtlasCloud Seedance drama**
- `@image_N as <role>` ← từ **awesome-seedance-2-prompts** + verified AtlasCloud spec
- `Negative prompt` ← combination từ **MindStudio** ("no age indicators") + **CrePal** ("no product close-up in opener")

---

## 🎬 STEP 4 · LAYER 3 — AtlasCloud render + chain

### 4a. Atlas payload cho S1
Code: `backend/workers/video_worker.py` + `backend/vendors/atlascloud.py::generate_video()`.

```jsonc
{
  "model": "bytedance/seedance-v2.0/reference-to-video",
  "prompt": "(prompt từ Scene Gen)",
  "negative_prompt": "(negative từ Scene Gen)",
  "reference_images": ["https://example.com/character_linh.jpg"],
  "ratio": "9:16", "resolution": "720p",
  "duration": 2, "generate_audio": true,
  "return_last_frame": true, "seed": 0
}
```

### 4b. Atlas response
```jsonc
{
  "video_url": "https://r2.example.com/clip_S1.mp4",
  "last_frame_url": "https://r2.example.com/clip_S1_last_frame.jpg",
  "duration": 2.0
}
```

### 4c. **🔥 Chain để S2** — identity persist

S2 có `previous_shot_id="S1"` + S1 trả `last_frame_url` → Worker SWAP model key `seedance_2_0_ref` → `seedance_2_0_i2v` + pass `image=last_frame_url`:

```jsonc
{
  "render_mode": "i2v_chain",
  "chain_input_url": "https://r2.example.com/clip_S1_last_frame.jpg",
  "prompt_prefix": "Continue from previous frame: same character, same wardrobe, same lighting, same color grade. Now: ",
  "prompt_body": "WS push-in through doorway, Linh seated at make-up desk, wiping old lipstick off with tissue...",
  "model_key": "seedance_2_0_i2v"   // ← AUTO-SWAPPED
}
```

Identity (mặt + outfit + lighting) inherit gần 100% từ S1. → giải quyết bài toán "drift" classic của AI video.

**Nguồn**: pattern này từ **MindStudio reference chaining** + **AtlasCloud Seedance i2v doc**.

### 4d. Loop tiếp tục
- S3 (reveal, product enter): RESET chain (previous_shot_id=null), gọi `ref_to_video` với product ref
- S4 (proof): chain từ S3
- S5 (cta): chain từ S4

→ Code: `workers/video_worker.py` render loop chính ~150 dòng.

---

## 🎞️ STEP 5 · Assemble (FFmpeg)

Code: `workers/assemble_worker.py`.

1. **Concat 5 clip** với aspect-aware scale: `ffmpeg -i S1 -i S2 ... -filter_complex concat=n=5 ...`
2. **TTS overlay** (nếu `audio_mode=dialogue_vo`): gọi `vendors/genmax.py` gen audio Việt cho mỗi shot có `dialogue_vn`, mix lên timeline
3. **Caption.ass burn**: chuyển `caption_on_screen` thành subtitle ASS, burn vào video
4. **Color consistency pass**: dựa `bible.visual_style.color_grading` ("teal-and-orange") → áp filter `curves=preset=increase_contrast,eq=saturation=1.10:contrast=1.05`

Output: `final.mp4` local.

---

## ☁️ STEP 6 · Upload R2

Code: `vendors/r2_storage.py` (boto3 S3-compatible).

```python
upload_to_r2(
    local_path="/tmp/final.mp4",
    key=f"video/{job_id}/final.mp4",
)
# Returns: https://cdn.yourdomain.com/video/job_xxx/final.mp4
```

Nếu thiếu R2 env → fallback `file:///` local URL (dev mode).

---

## 📺 STEP 7 · FE polling + display

```
useDirectorJobPoll(jobId) — poll every 2.5s GET /director/jobs/{job_id}
  status: pending → planning → rendering → assembling → uploading → done
  progress: 0 → 20 → 50 → 80 → 95 → 100
  output_url: filled when done
  ↓
JobResultModal renders <video src={output_url} controls />
```

---

## 📚 Tài liệu / nguồn cảm hứng đã dùng

| Layer / Decision | Nguồn |
|---|---|
| **10 hook patterns** | CrePal (problem-solution, feature-led, social-proof, offer-led) · drama-director-skill (POV) · AtlasCloud (visual anomaly) |
| **Beat sheet 15s/30s/60s** | CrePal 3-part rhythm · MindStudio 8-10 shots / 15s · AtlasCloud setup/rising/turn/resolution |
| **3-section Seedance prompt** (STYLE / DYNAMIC / STATIC) | drama-director-skill + AtlasCloud Seedance drama workflow |
| **Hard rule "product never opens"** | CrePal core rule |
| **Double-contrast cut** | AtlasCloud explicit |
| **Face anchor phrase reuse** | AtlasCloud 9-panel anchor · MindStudio character lock-in |
| **Reference chaining (last_frame i2v)** | MindStudio reference chaining workflow |
| **Functional descriptors (no age numbers)** | drama-director-skill compliance trick |
| **@image_N role tags** | awesome-seedance-2-prompts + AtlasCloud spec |
| **Slot pattern niche-agnostic** | CrePal output-review checklist universal |
| **Multi-agent layered (Director / Scene / Worker)** | ViMax (Director+Screenwriter+Producer) · ArcReel (Story→Storyboard→Video) |
| **Cinematic vocabulary palette** | Industry film terminology synthesized cross-sources |
| **Cost gate draft-first** | MindStudio shooting-ratio (3-5 generations per usable clip) |
| **Continuity Bible concept** | Pre-existing V3 CineForge architecture |
| **UI design system** | Lumeflow.ai screenshot scrape (dark canvas + magenta-orange gradient + Albert Sans + glass cards) |

Research tổng hợp trong:
- [`_design_refs/STORYTELLING_RESEARCH.md`](_design_refs/STORYTELLING_RESEARCH.md) (V4 storytelling)
- [`_design_refs/lumeflow/`](_design_refs/lumeflow) (47 screenshot + DOM/CSS dump UI)

---

## 🎯 Lợi ích của thiết kế này

| Vấn đề thường gặp khi gen AI video | CineForge V4 giải quyết bằng |
|---|---|
| Video "trông như ads" → bị skip | Hard rule product never opens · Hook pattern enum · Lead-in problem-first |
| Identity character drift qua shot | Continuity Bible + face_signature + Reference Chaining (i2v swap) |
| Mỗi niche cần template riêng → dev hell | Niche-agnostic slot pattern · cùng beat sheet cho mọi niche |
| Đốt $1.5 cho plan tệ mới biết | HITL review modal + Storytelling validator catch pre-render |
| Identity drift khi gọi từng shot riêng | Chain `previous_shot_id` + auto-swap i2v variant |
| Prompt rối → output không reproducible | 3-section Seedance template + Negative prompt mandatory + length cap |
| Sửa prompt = redeploy | Markdown system prompts hot-reload qua `lru_cache` |
| Render thật fail = mất hết tiền | Cost Gate draft-first: render shot[0] tier Fast → eval → abort sớm |
| Khó debug LLM output | SSE event per stage + storytelling_check event surface red flags |

---

## ▶️ Tự chạy demo

```bash
cd backend
python ../_design_refs/demo_pipeline.py
```

Output đầy đủ ~300 dòng — tất cả JSON real chạy qua code thật (no LLM call, free). Lưu sẵn ở [`_design_refs/demo_pipeline_output.txt`](_design_refs/demo_pipeline_output.txt).

Muốn test với LLM thật → vào `http://localhost:3000/studio`, nhập brief, nhấn Generate Plan. Sẽ tốn ~$0.04 cho plan.
