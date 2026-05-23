# 🎯 Grok V4 — Targeted Follow-up cho 4 gaps cụ thể

> **Context**: Grok V3 trả về CỰC TỐT cho Seedance 2.0 (Dan Kieft 25min YouTube với timestamps + Higgsfield 8-scene workflow + AtlasCloud Digital Set + Dreamina docs + RunDiffusion). Đã embed 5 quick wins.
>
> **Gap còn lại** — Dossier 2-6 (Seedance Fast / 1.5 Pro / Vidu Q3 / Q3-Mix / Wan 2.7) chỉ có 1-2 link sơ sài, KHÔNG có phase-by-phase với verbatim prompt + timestamps. Cần V4 đào sâu 4 mục cụ thể.

---

## 🔍 Gap #1: **Wan 2.7 Vietnamese lip-sync THỰC CHIẾN**

Cần Grok tìm:
- **Creator VN nào đã test Wan 2.7 với tiếng Việt thật** — Twitter/X VN, Facebook AI VN group, YouTube VN
- Verbatim audio file format họ dùng: 44.1kHz mp3 vs 48kHz wav, mono vs stereo
- TTS provider thắng nhất: GenMax / ElevenLabs v3 / Vbee / OpenVoice / XTTS-v2 — A/B với Wan
- Vowel/tone accuracy report — bao nhiêu % câu sync ngon, lỗi nhất ở dấu thanh nào (sắc, huyền, ngã)?
- Portrait quality: front-facing vs 3/4, lighting cứng vs mềm, mouth visibility (râu/khẩu trang fail?)
- **Speed setting** — TTS speed 1.0 vs 0.9 vs 1.1 — cái nào Wan sync tốt hơn
- Chain 5s+5s = 10s via last_image field — drift rate thực tế (có người nào share screenshot vs có không?)

Volume target: **5-8 link** real VN creator hoặc Asian-language tester
Format: cùng V3 structure (Phase 1-6) + audio specs cụ thể

---

## 🔍 Gap #2: **Vidu Q3 / Q3-Mix workflow phase-by-phase**

Cần Grok tìm:
- **Long-form YouTube 15+ phút** với Vidu Q3-Mix manual workflow (V3 chỉ có AtlasCloud case study generic)
- Specific creators: **Lyndoc** Discord/YouTube, **PromeAI** team, creators dùng ShengShu Vidu Studio
- Verbatim prompt example với `@image_1 as primary character` syntax — chính xác Vidu accept format nào (test `@image1` vs `@image_1` vs `<image1>`)
- Array order test: upload [A, B, C] vs [B, A, C] vs [A, C, B] — kết quả khác biệt thế nào trong multi-character scene
- Multi-entity scene workflow — bao nhiêu max nhân vật cùng frame trước khi blend? Trick keep distinct (lighting + position + outfit color)?
- Cost per usable: $0.042/s × 16s = $0.67 base. Sau retries thật bao nhiêu?
- Failure modes top 3 cho Vidu Q3
- 1080p output vs 720p upscale — fidelity test thật

Volume target: **5-7 link** Vidu-focused
Format: Phase 1-6 đầy đủ

---

## 🔍 Gap #3: **Failure mode catalog per-model (cho 5 model còn lại)**

V3 chỉ có Dossier 1 đầy đủ "Top 3 failure modes". Các dossier khác missing. Cần Grok tìm cho mỗi model:

### Seedance 2.0 Fast — failure modes (so với Standard)
- Tier downgrade compromise gì cụ thể?
- Texture loss khi nào dễ thấy nhất (close-up vs wide)?
- Khi nào KHÔNG dùng được Fast (must Standard)?

### Seedance 1.5 Pro — failure modes
- Single anchor i2v khi nào fail (background change quá nhiều, action quá phức tạp)?
- Time-coded prompt limit thực tế bao nhiêu segment trước khi loose?

### Vidu Q3 (non-Mix) — failure modes
- Array-order khi nào bind sai?
- Multi-character thì khi nào blend face?
- Native audio Vietnamese — có support thật không hay phải overlay?

### Vidu Q3-Mix — failure modes
- `@image_N` tag khi nào fail (typo? case sensitivity?)
- 1080p tier — bottleneck quality nào (compression artifact?)

### Wan 2.7 — failure modes
- Audio-driven khi nào lip-sync fail (audio nhiễu, dialect mạnh, tốc độ quá nhanh)?
- 5s/10s discrete — workaround khi cần 7s hoặc 12s?
- Facial hair / khẩu trang / kính — model có handle được không?

Volume target: **3-5 link per model** post-mortem honest, có screenshot/video showing failure
Format: list 5 failure modes + recovery strategy + cost của mỗi recovery

---

## 🔍 Gap #4: **Brief template + Claude MD skill file copy-pastable**

V3 mention Higgsfield Claude skill file (Dropbox link) nhưng KHÔNG paste full content.

Cần Grok:
- **Fetch + paste full content** của `Seedance-2-Skill.md` từ Dropbox link
- **Brief template structure** Dan Kieft dùng (timestamp 2:30-3:38 video) — viết verbatim cho người dùng VN copy
- **Character bible template** — Ben Bauchau character consistency expert có template gì không (Twitter/Substack)
- **Shot list template** cho 15s ad — 4 shot vs 5 shot vs 6 shot — template MD/JSON
- **Storyboard prompt template** cho GPT Image 2 / Nano Banana Pro — verbatim
- Best Claude/GPT system prompt cho "expand brief → DirectorPlan JSON" — có ai share công khai không

Volume target: **3-5 actual template files** anh có thể copy-paste vào CineForge
Format: full file content + license note (CC / public / paid)

---

## 📤 FORMAT OUTPUT GROK PHẢI TRẢ VỀ (V4)

```markdown
## Gap [#N]: [Tên gap]

### Source 1: [URL clickable]
- Type / Author / Date / Quality signal
- **What I'm extracting**: [1 dòng tóm tắt cụ thể]
- **Verbatim content** (copy-paste ready):
   ```
   [actual prompt / template / failure log / audio spec]
   ```
- **Timestamp / location in source**: [URL#t=120 hoặc tweet #5 trong thread]
- **CineForge action item**: [code path tôi sẽ update]
```

---

## 🚫 Anti-fluff (cùng V3)

Skip:
- Marketing fluff
- Generic "AI video tips"
- Older than Jan 2025 unless foundational
- Workflow KHÔNG có verbatim content (chỉ summary)

---

## 📊 Volume target V4

- Gap #1 (Wan VN): 5-8 link
- Gap #2 (Vidu): 5-7 link
- Gap #3 (Failure modes 5 model): 3-5 link × 5 model = 15-25 link
- Gap #4 (Templates): 3-5 actual file content

Total: **28-45 link/template verified**

---

## ⚙️ Sau khi có V4 output

Anh paste về tôi. Tôi sẽ:
1. **Wan VN insights** → update `vendors/genmax.py` audio format hint + UI cảnh báo khi user pick Wan + dialect mạnh
2. **Vidu workflow** → enhance `scene.md §9.3` multi-character disambiguation với verbatim examples
3. **Failure mode catalog** → expand `storytelling.validate_plan` thêm rules per-model + scene.md anti-pattern table
4. **Brief template** → tạo `BRIEF_TEMPLATES.md` + add UI suggestion chips trong PromptCardV2 với template starters

→ Goal: pipeline CineForge có **failure mode catalog đầy đủ 6 model** + **template library copy-paste** + **Wan VN lip-sync optimized** + **Vidu multi-character trick verified**.
