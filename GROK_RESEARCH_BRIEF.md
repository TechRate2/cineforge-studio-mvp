# 🔍 Research brief — gửi Grok để tìm tài liệu/repo/thread thực chiến cho 6 model AI video

> **Mục đích**: Tìm prompt patterns + pipeline + thread/repo thực chiến từ user thật cho mỗi model. CineForge Studio sẽ học từ đây để cải thiện prompt engineering + workflow ứng biến mọi niche.

> **Cách dùng**: Copy toàn bộ file này paste vào Grok (hoặc Claude/ChatGPT) → yêu cầu nó research + trả về list link theo format ở cuối.

---

## 🎯 BỐI CẢNH DỰ ÁN

Tôi đang build **CineForge Studio** — AI video agent tự động cho thị trường Việt Nam (TikTok/Reel/Short, UGC ads, drama, lip-sync VN). Stack:

- **Frontend**: Next.js 14 + Tailwind (Lumeflow/Topview-inspired UI)
- **Backend**: FastAPI Python
- **GPU**: AtlasCloud (Vidu/Wan/Seedance), GenMax TTS Việt (12 giọng), Cloudflare R2

Pipeline 5 layer:
```
User brief → Director Agent V4 (1 LLM call gen DirectorPlan: Continuity Bible + 8-15 shot)
           → Master Storyboard Board (1 image Seedream v4.5 ultra-wide 12-panel)
           → Human-in-the-Loop review (3 tab: Bible / Shots / Eval)
           → Scene Gen Agent (per-shot LLM build model-ready prompt)
           → Video Worker (Reference Chaining loop)
           → AssembleWorker (FFmpeg concat + audio timeline + caption + grade)
           → R2 upload
```

---

## 🎬 6 MODEL ĐANG TÍCH HỢP (verified AtlasCloud doc 2026-05-20)

### 1. **Vidu Q3** — `vidu/q3/reference-to-video` · $0.042/s
- **Use case**: UGC budget, multi-entity scene, aesthetic lifestyle
- **Max refs**: 4 ảnh (`images` plural, array)
- **Duration**: 3-16s
- **Resolution**: 540p/720p/1080p (default 720p)
- **Aspect**: 16:9 / 9:16 / 1:1 / 3:4 / 4:3
- **Audio**: native (generate_audio)
- **Quirk**: NO `@image_N` tag support — binds by **array order**, FIRST image = primary subject
- **Chain**: KHÔNG có i2v variant native → V4 fallback: stay in family, append last_frame as extra entry trong array images

### 2. **Vidu Q3-Mix** — `vidu/q3-mix/reference-to-video` · $0.106/s
- **Use case**: Premium ad, multi-subject scene, 1080p detail
- **Max refs**: 4 ảnh
- **Duration**: 1-16s
- **Resolution**: 720p / 1080p (NO 540p)
- **Audio**: native
- **Quirk**: HIỂU `@image_1 as <role>` tags (khác Vidu Q3 thường)
- **Best for**: Multi-character scene cần bind từng subject explicit

### 3. **Wan 2.7** — `alibaba/wan-2.7/image-to-video` · $0.10/s
- **Use case**: Lip-sync VN, talking head presenter, dialogue
- **Max refs**: 1 portrait + 1 audio URL
- **Duration**: **5s HOẶC 10s discrete only** (NO 6/7/8/9)
- **Resolution**: 480p / 720p / 1080p
- **Audio**: **driven** — nhận audio URL (mp3), Wan tự lip-sync khớp môi
- **Quirk**: Field `ratio` (NOT `aspect_ratio`), field `image` (singular), `audio` field cho driven mode
- **Chain**: i2v native, last_frame qua field `last_image`

### 4. **Seedance 1.5 Pro** — `bytedance/seedance-v1.5-pro/image-to-video` · $0.047/s
- **Use case**: Budget B-roll, product showcase từ 1 ảnh anchor
- **Max refs**: 1 ảnh (i2v only)
- **Duration**: 4-12s
- **Resolution**: 480p / 720p only
- **Audio**: native
- **Quirk**: Dùng `aspect_ratio` (khác 2.0 dùng `ratio`), poll qua `/model/result` (khác `/model/prediction`)
- **Variants**: t2v + i2v + i2v-fast ($0.018/s — rẻ nhất pipeline)

### 5. **Seedance 2.0** ⭐ — `bytedance/seedance-2.0/reference-to-video` · $0.096/s
- **Use case**: Cinematic multi-shot, premium ad, narrative storytelling
- **Max refs**: **9 ảnh** + **3 video refs**
- **Duration**: 4-15s
- **Resolution**: 480p / 720p / 720p-SR / 1080p / 1080p-SR / 1440p-SR
- **Audio**: native
- **Quirk**: HIỂU `@image_N` tags + `@video_N` tags (camera/motion/pacing) · Multi-shot inline notation `[Shot 1 | 2s | dolly | @image_1 as primary character]` · `return_last_frame=true` support cho chaining
- **Chain**: SWAP sang `seedance_2_0_i2v` variant + pass last_frame as image
- **Format prompt 3-section**: `[STYLE & MOOD]` + `[DYNAMIC DESCRIPTION]` (timestamped) + `[STATIC DESCRIPTION]`

### 6. **Seedance 2.0 Fast** — `bytedance/seedance-2.0-fast/reference-to-video` · $0.076/s
- Cùng feature 2.0 nhưng nhanh + rẻ 20%
- Dùng cho daily UGC mid-tier + cost gate draft-first

---

## 📐 PROMPT TEMPLATE HIỆN TẠI

### Layer 1 — Director Agent (1 LLM call output JSON DirectorPlan)
System prompt: `system_prompts/director.md` (13KB, 12 section)
Key constraints:
- 10 hook patterns enum (pattern_interrupt / direct_question / pov_confession / ...)
- Beat sheet duration-aware (15s: HOOK→PAIN→REVEAL→PROOF→CTA · 60s: + SETUP+TENSION)
- Hard rules: product NEVER opens shot 1, product first appears ≥30% runtime, double-contrast cut mỗi transition
- 5-slot niche-agnostic fill: problem_statement / character_archetype / product_role / payoff_emotion / cta_verb

### Layer 2 — Scene Generation Agent (per-shot LLM)
System prompt: `system_prompts/scene.md` (10KB)
Model-aware format hints:
- `seedance_2_0_ref` / `_fast_ref` → `multi_shot_inline` (3-section)
- `seedance_2_0_i2v` / `_fast_i2v` / `wan_2_7_i2v` → `i2v_motion` (motion verbs only)
- `seedance_v15_pro_i2v` → `time_coded` `[0-3s] ... [3-5s] ...`
- `vidu_q3_ref` → `single_descriptive`
- `vidu_q3_mix_ref` → `multi_ref_tagged` với `@image_N`

### Reference Chaining (identity persist)
```
Shot N có previous_shot_id + last_frame_url:
  Seedance 2.0: SWAP ref → i2v variant, pass last_frame as image
  Vidu Q3: STAY in family, append last_frame vào array images[]
  Wan 2.7: native i2v + last_image field
```

---

## 📚 7 NGUỒN ĐÃ HỌC ROI

Đã đọc + embed best practices vào code:

1. **ViMax** (github.com/HKUDS/ViMax) — Multi-agent Director+Screenwriter+Producer pattern
2. **ArcReel** (github.com/ArcReel/ArcReel) — Story→Storyboard→Video, anchor object tracking
3. **drama-director-skill** (github.com/kianaliang-dev/drama-director-skill) — 3-section Seedance prompt template, functional descriptors no-age
4. **awesome-seedance-2-prompts** (github.com/YouMind-OpenLab) — `@image_N` role tags, formula Subject+Action+Camera+Lighting+Style
5. **MindStudio AI short film $200** (mindstudio.ai/blog/ai-short-film-under-200-production-workflow) — Reference chaining, 25-35 shots/2-3min, character lock-in session
6. **CrePal product video ads** (crepal.ai/blog/agent/how-to-turn-product-photos-into-ai-video-ads) — "Problem-first, product later", camera moves not product moves
7. **AtlasCloud Seedance drama workflow** (atlascloud.ai/blog/guides/ultimate-drama-workflow-gpt-image-2-seedance-2-0) — 9-Panel Anchor pattern, double-contrast cuts, face-anchor phrase verbatim

---

## 🔎 NHIỆM VỤ CỦA GROK — TÌM TÀI LIỆU MỚI/SÂU HƠN

Tìm thêm các loại tài liệu/repo/thread sau **CHƯA có trong 7 nguồn trên**, đặc biệt 2026:

### 🗂️ 15 BUCKETS CẦN TÌM (mỗi bucket 3-7 link)

1. **Seedance 2.0 prompt cookbook** — repo / blog hướng dẫn cấu trúc prompt thực chiến cho ByteDance Seedance 2.0 (`reference-to-video`). Đặc biệt: pattern `[Shot N | Xs | <camera>]` multi-shot inline, `@image_N as <role>` tags, `@video_N` references.

2. **Seedance 2.0 character consistency** — workflow giữ identity character nhất quán xuyên 8-15 shot (Heather Cooper @HBCoop_, Iancu_ai, Ben_Bauchau, Pierrick Chevallier nếu có).

3. **Vidu Q3 / Q3-Mix multi-entity** — pipeline gen nhiều character cùng frame, scene đông người, identity bind by array order (Vidu Q3 không hiểu @image_N — trick gì để bind?)

4. **Wan 2.7 lip-sync Vietnamese / Asian languages** — workflow pre-render TTS Việt rồi feed vào Wan i2v cho lip-sync khớp môi. Audio format requirements (mp3 vs wav), portrait quality tips.

5. **Hierarchical Director for long-form (60s-3min)** — pattern Outline Director (scene-level) → Shot Director (per-scene) để gen drama short film. ArcReel / univa / agentic-video-editor có gì?

6. **Reference Chaining + last_frame extraction** — best practices trích last frame mượt, gen i2v shot tiếp tránh drift identity. FFmpeg recipe + workflow real-world (MindStudio đề cập nhưng cần sâu hơn).

7. **Master Storyboard Board / 9-panel anchor** — gen 1 ảnh ultra-wide chứa 9-12 panel làm global style reference. Seedream v4.5 vs Nano Banana Pro vs Flux best practices. Image-to-video downstream tận dụng board làm anchor ra sao.

8. **TikTok VN viral patterns 2026** — hook 1-3s nào hoạt động cho audience Việt? Gen Z VN, KOL UGC. Câu thoại mở đầu tiếng Việt cuốn người xem.

9. **Cost optimization** — patterns giảm cost gen video (cost gate, draft-first tier, refine 1 shot vs full re-render, A/B variant spawning). Repos thực chiến.

10. **Audio timeline + BGM library** — workflow per-shot dialogue sync với silence padding + BGM cross-fade + SFX layered. FFmpeg recipes (`adelay`, `amix`, `acrossfade`). Open-source BGM/SFX catalog mood-tagged.

11. **Niche-agnostic prompt slot pattern** — pattern fill slot từ brief thay vì template hardcode per niche. CrePal đề cập nhưng cần sâu hơn — repo nào có "1 framework cho 10 niche".

12. **Storytelling validators code-level** — repo nào auto-check plan trước khi render (product timing, hook presence, double-contrast cut, duration sum)?

13. **Auto pre-render TTS workflow** — pipeline Whisper / OpenVoice / ElevenLabs / GenMax tự gen dialogue trước rồi feed vào video gen. Workflow VN.

14. **Industry agent SaaS reverse-engineer** — phân tích Topview Agent / Lumeflow / RunwayML Watch / Pika Labs / Lovart AI — họ build pipeline gì? Tab Storyboard / Refine / Variants UI pattern gì?

15. **Open-source FULL pipeline alternatives** — repo open-source agentic video studio đầy đủ (Director + Scene + Worker + Assembly). univa, agentic-video-editor, open-ai-ugc, ViMax — sâu hơn 7 nguồn cũ. Lib mới 2026.

### 📤 FORMAT OUTPUT GROK PHẢI TRẢ VỀ

Cho mỗi bucket, return:

```markdown
## Bucket {N}: {tên}

### Link 1: {URL}
- **Type**: GitHub repo / blog post / X thread / YouTube video / paper
- **Title**: {original title}
- **Author**: {handle/name}
- **Date**: {publish date if visible}
- **Summary 50 từ**: {tóm tắt nội dung — focus practical tips}
- **Áp dụng cho CineForge**: {Director Agent / Scene Gen / Specific model / Pipeline stage}
- **Key insight đáng học**: {1-2 câu — pattern mới hoặc kỹ thuật chưa có trong 7 nguồn cũ}

### Link 2: ...
```

Yêu cầu: **ưu tiên link publish 2025-2026**, ưu tiên repo/thread có người dùng thực chiến share screenshot kết quả thật. Skip link kiểu marketing/PR fluff. Mỗi bucket 3-7 link. **Đừng lặp lại 7 nguồn cũ đã liệt kê**.

---

## ✅ Sau khi có output Grok

Gửi lại file kết quả cho Claude → tôi sẽ:
1. Cross-check link nào đã embed trong code (skip duplicate)
2. Phát hiện gap mới cần bổ sung (vd: hierarchical director, BGM library)
3. Plan Sprint 2/3 dựa trên insights mới
4. Update prompt files (director.md / scene.md / storytelling.py) nếu có pattern hay hơn
