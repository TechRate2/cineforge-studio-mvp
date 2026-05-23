# 🔬 Deep Research Brief V2 — Operational Pipeline per Model (FROM REAL USERS)

> **Khác V1**: V1 tìm general best practices. V2 tìm **CASE STUDY THỰC TẾ** — user đã làm ra video tốt + share full workflow + post-mortem. Mỗi model = 1 dossier riêng. Ưu tiên thread có **screenshot kết quả thật + prompt copy-pastable**.

> **Mục đích**: CineForge Studio đang xử lý 6 model (Seedance 2.0 / 2.0 Fast / 1.5 Pro / Vidu Q3 / Q3-Mix / Wan 2.7). Pipeline V4.5 hiện tại dispatch per-model strategy nhưng cần verify với cộng đồng thực chiến xem có pattern hay hơn không.

---

## 📋 CONTEXT GỬI CHO GROK

Tôi đang vận hành 1 AI video agent gen video TikTok/Reel/Drama short tiếng Việt cho thị trường VN. Stack: Next.js + FastAPI + AtlasCloud GPU. 6 model đang tích hợp. Tôi cần Grok tìm tài liệu **THỰC CHIẾN** từ user đã ra video chất lượng cao (KHÔNG phải marketing fluff).

### Yêu cầu chất lượng nguồn

✅ **OK**: 
- Twitter/X thread có video output embed + caption "Made with X model in Y minutes for $Z"
- YouTube creator tutorials có timestamp specific (00:23 prompt, 02:15 output)
- Reddit r/aivideo / r/MachineLearning post có comparison test
- Discord community shares (PromptLab, Seedance fan club, Vidu Studio)
- Medium articles từ creator thật, không phải vendor blog
- GitHub gist với prompt examples + linked video output
- Substack newsletter từ AI creators (Bilawal Sidhu, Heather Cooper, Iancu, Ben Bauchau, Pierrick Chevallier)

❌ **SKIP**:
- Marketing landing page từ vendor (Vidu/ByteDance/Alibaba PR)
- Listicle "10 AI video tools you must try" generic
- AI-generated content farm articles
- Affiliate review sites
- Tutorial chỉ show button click không có prompt

---

## 🎬 6 DOSSIER MODEL — TÌM CHI TIẾT TỪNG CÁI

### DOSSIER 1: Seedance 2.0 (ByteDance — multi-shot inline)

**Tôi đã biết** (đã embed):
- Endpoint: `bytedance/seedance-2.0/reference-to-video`
- Max: 9 image refs + 3 video refs, duration 4-15s, native audio
- Format: 3-section prompt `[STYLE & MOOD]/[DYNAMIC]/[STATIC]` + multi-shot inline `[Shot N | Xs | camera]`
- Spec từ Byteplus official docs Apr 2026

**Tôi cần Grok tìm**:
1. **5+ Twitter/X thread** từ creator dùng Seedance 2.0 ra video viral (>100k views). Yêu cầu:
   - Full prompt copy-pastable
   - Video output URL
   - Tổng thời gian gen + retry count
   - Notes về quirk họ phát hiện (failure modes)
2. **3+ YouTube tutorial** chi tiết Seedance 2.0 prompt formula (>10k views):
   - Camera language nào hoạt động tốt nhất (dolly-in vs push-in vs handheld)
   - @video_N reference video — ai đã test thật, kết quả gì
   - Multi-shot inline limit thực tế (bao nhiêu shot tối ưu trước khi drift)
3. **Failure modes** từ user post-mortem:
   - Khi nào identity drift xảy ra dù dùng `same character verbatim`?
   - Prompt nào trigger refusal/filtering (NSFW false positive)?
   - Sweet spot duration cho từng aspect ratio (9:16 vs 16:9)?
4. **Character consistency hack** — 9-panel anchor có thực sự work không, hay paper claim?
5. **Audio sync issue** — native audio generation có khớp với dialogue prompt không?

### DOSSIER 2: Seedance 2.0 Fast — same model nhưng faster tier

**Tôi đã biết**:
- $0.076/s vs $0.096/s — rẻ 20%
- Same multi-shot inline support
- Suitable cho draft + cost gate

**Tôi cần Grok tìm**:
1. **Quality comparison** Seedance 2.0 vs Fast — A/B test thật từ creator:
   - Cùng prompt, 2 model → output có khác biệt rõ không?
   - Khi nào Fast tier đủ tốt (use case nào)?
2. **Cost-quality sweet spot** — bao nhiêu % user dùng Fast cho final, bao nhiêu % chỉ draft?
3. **Failure modes riêng** của Fast tier (faster = compromise gì?)

### DOSSIER 3: Seedance 1.5 Pro (i2v budget tier)

**Tôi đã biết**:
- $0.047/s · max 12s · 1 image ref only
- Time-coded prompt format `[0-3s] ... [3-7s] ...`
- Variants: i2v + t2v + i2v-fast ($0.018/s rẻ nhất)

**Tôi cần Grok tìm**:
1. **Single-image anchor strategy** — chọn ảnh thế nào để Seedance 1.5 Pro gen tốt nhất?
   - Portrait vs full-body vs product close-up
   - DPI/resolution sweet spot
   - Lighting trong ảnh anchor ảnh hưởng output ra sao
2. **Time-coded prompt examples** từ thực chiến — bao nhiêu time segment tối ưu?
3. **Compare vs Seedance 2.0** — khi nào 1.5 Pro CỦA TỐT HƠN 2.0?
4. **i2v-fast tier $0.018/s** — quality thật so với chuẩn?

### DOSSIER 4: Vidu Q3 (multi-entity, array-order binding)

**Tôi đã biết**:
- $0.042/s · 4 refs · max 16s · NO `@image_N` tags
- Bind by ARRAY ORDER — first image = primary subject
- Native audio

**Tôi cần Grok tìm**:
1. **Multi-entity workflow** — gen scene 2-4 nhân vật cùng frame:
   - User thực tế ordering array thế nào để bind đúng?
   - Có trick gì khi 2 nhân vật mặc đồ giống nhau?
2. **Chain identity cross-shot** — last_frame anchor pattern (Vidu không có i2v native):
   - Append last_frame vào array có giữ identity không?
   - Cost của trick này (cần test)
3. **Vidu Q3 vs Seedance 2.0** trong multi-character scene — ai win?
4. **Native audio quality** — TTS native của Vidu có support tiếng Việt không, hay phải overlay post?

### DOSSIER 5: Vidu Q3-Mix (premium variant, hiểu `@image_N`)

**Tôi đã biết**:
- $0.106/s · 4 refs · 720p/1080p · UNDERSTAND `@image_N` tags
- Best for: multi-subject scene cần bind từng role explicit

**Tôi cần Grok tìm**:
1. **`@image_N` tagging best practices** — syntax chính xác Vidu accept (so với Seedance 2.0)
2. **Premium tier ROI** — khi nào $0.106/s đáng vs $0.042 Q3 thường?
3. **1080p output thực tế** — fidelity so với 720p upscale có khác biệt rõ?

### DOSSIER 6: Wan 2.7 (Alibaba — lip-sync driven)

**Tôi đã biết**:
- $0.10/s · 5/10s discrete duration · 1 portrait ref + 1 audio URL
- Audio driven mode: feed mp3 → lip-sync khớp môi
- i2v native, last_image field for chain

**Tôi cần Grok tìm**:
1. **Vietnamese lip-sync quality** — user VN đã test Wan 2.7 với tiếng Việt chưa?
   - Vowel/tone accuracy
   - Audio format requirement (mp3 vs wav, 44.1kHz vs 48kHz)
   - TTS provider nào sync tốt nhất với Wan (ElevenLabs vs GenMax vs OpenVoice)
2. **Portrait quality** — kiểu ảnh nào lip-sync work best?
   - Front-facing vs 3/4 view
   - Lighting (high-key vs soft)
   - Mouth visibility / facial hair issue
3. **Chain 5s+5s = 10s video** — hay vẫn drift giữa 2 segment?
4. **Wan 2.7 vs Pika / RunwayML / D-ID / HeyGen** cho talking head — comparison cụ thể

---

## 🎯 META TOPICS — CROSS-MODEL

### Topic A: Master Storyboard Board / 9-panel Anchor — DEEP DIVE
Tôi đã implement Seedream v4.5 gen 1 ảnh ultra-wide 12 panel. Cần tìm:
1. User real đã test 9-panel có giảm drift bao nhiêu % cụ thể?
2. Cách prompt cho image model gen board layout chuyên nghiệp (font, palette swatch, panel borders)
3. Image model nào tốt nhất cho board: Seedream v4.5 vs GPT Image 2 vs Nano Banana Pro vs Flux Pro Ultra
4. Board làm reference cho video — pass 1 ảnh ultra-wide vs split thành N ảnh riêng, kết quả khác nhau ra sao?

### Topic B: Hierarchical Director for long-form (>15s)
Plan Sprint 2. Cần tìm:
1. Open-source repo có Director Agent xử lý 60s-3min video — workflow cụ thể
2. Camera Artist paper / MovieAgent / Univa — ai đã clone implement và share kết quả
3. Cross-segment chain identity — last_frame của segment 1 làm input segment 2 — drift rate thực tế
4. Cost optimization cho 2min drama: total bao nhiêu? render budget cho user indie $50-100?

### Topic C: TikTok VN Gen Z 2026 Patterns
Niche specific cho VN market. Cần tìm:
1. KOL VN đã dùng AI gen video viral nào? (case study: HiHi, Linh Ngọc Đàm, Quang Linh Vlogs)
2. Hook 1-3s nào convert best cho audience VN (Gen Z 18-25)
3. Dialogue tiếng Việt — câu nói viral 2026 (audio trend "Ngây Thơ", "Em Xinh"...)
4. Caption tiếng Việt + emoji pattern winning algorithm TikTok VN
5. Local product placement — son lì, mỹ phẩm VN, food street — example brief winning

### Topic D: Audio Pipeline thực chiến
1. GenMax TTS Việt 12 voice — user đã pick voice nào cho niche nào (beauty / tech / food / drama)?
2. BGM library mood-tagged — open-source catalog nào tốt cho video AI gen?
3. SFX library — Boom Library / Splice / freesound.org — workflow integrate vào FFmpeg
4. Cross-fade BGM giữa scene boundary — recipe FFmpeg cụ thể
5. Audio sync issue: TTS dài hơn shot duration → giải pháp speed-up vs split dialogue

---

## 📤 FORMAT OUTPUT GROK PHẢI TRẢ VỀ

```markdown
## DOSSIER [N]: [Tên model]

### Link 1: [URL]
- **Type**: X thread / YouTube / Reddit / Discord / Medium / GitHub gist
- **Author**: [@handle real name] (followers/subscribers nếu visible)
- **Date**: YYYY-MM-DD
- **Quality signal**: views/likes/replies/forks
- **What they made**: [1 dòng — "15s lipstick ad", "60s drama short", etc.]
- **Output URL**: [video link nếu có]
- **Cost they paid**: $X for Y seconds
- **Time to ship**: total minutes from brief to final
- **Full prompt** (copy-paste ready):
   ```
   [STYLE & MOOD]
   ...full prompt verbatim...
   ```
- **Workflow steps** (numbered):
   1. ...
   2. ...
- **Failure modes they hit** (post-mortem honest):
   - ...
- **Key insight CineForge nên adopt**: [1-2 câu cụ thể]
- **Verify status**: ✅ verified output (link clickable) / ⚠️ claim only no proof
```

### Anti-fluff filter
Skip link nếu:
- Không có actual prompt text
- Không có video output để xem
- Vendor marketing content (Vidu/ByteDance/Alibaba PR)
- AI-generated SEO farm
- "Top 10 tools" listicle generic
- Older than Jan 2025 trừ khi paper nền tảng

### Volume target
Mỗi dossier: **5-10 link chất lượng cao** (thà ít mà chất). Cross-model meta topics: 3-5 link mỗi topic.

Total expected: **40-70 link verified**

---

## ⚙️ SAU KHI CÓ OUTPUT

Anh paste output Grok về cho tôi → tôi sẽ:
1. Cross-check với 29 sources cũ (7 V1 + 22 V2)
2. Identify gap thật sự — pattern HAY mà chưa có trong code
3. Update prompts (director.md / scene.md / multi_shot_prompt_builder.py)
4. Update model_picker logic nếu có insight chọn model tốt hơn
5. Commit từng update với references rõ source

→ Goal: **pipeline cuối cùng = consensus của community thực chiến**, không phải tôi tự suy luận.
