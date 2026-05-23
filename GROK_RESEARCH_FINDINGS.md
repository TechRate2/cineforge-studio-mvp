# 📚 Grok Research Findings — Processed 2026-05-23

> Output từ Grok cho 15 buckets trong `GROK_RESEARCH_BRIEF.md`. Đã cross-check với 7 nguồn cũ + code hiện tại. Phân loại theo actionability.

---

## 📊 Tổng quan 22 link mới

| Category | Count | Action |
|---|---|---|
| ✅ Quick win — adopted ngay | 4 | Code update Sprint 1+ |
| 🟡 Sprint 2 confirm | 5 | Tăng confidence cho Hierarchical Director |
| 🟢 Add to docs / reference | 8 | Cập nhật source map |
| 🔵 Verify / explore later | 5 | Sprint 3 polish |

---

## ✅ QUICK WINS — adopted ngay (4)

### 1. Outcome Showcase hook (TikTok VN 2026 winning pattern)
**Sources**: NewEngen Jan 2026 trends + Opus.pro 5 hook types 2026 analysis (34k clips analyzed)

> **Insight**: Cho VN Gen Z 2026, "Product/Outcome Showcase" + reverse-causality là hook convert NHẤT — show end-state hero shot 1-2s đầu rồi cut về journey.

**Đã làm**:
- Thêm `outcome_showcase` hook pattern (#11) vào `storytelling.py` HOOK_PATTERNS
- Example brief: *"Bowl phở Hà Nội hoàn hảo 1.5s steam rising → cut về tay làm bún sống"*
- Director Agent giờ có 11 hook patterns để pick (thêm 1 từ 10 cũ)

### 2. Character Block reusable verbatim (CrePal pattern)
**Source**: https://crepal.ai/blog/aivideo/blog-seedance-2-0-character-consistency/ (Feb 2026)

> **Insight**: Reuse 1 verbatim character block xuyên mọi shot's STATIC section → Seedance treat identical phrases như hard pixel-level lock. Consistency 65% → 92% qua 12 shots.

**Đã làm**:
- Thêm §3.1 "Character Block reusable" trong `scene.md` với template + warning "do NOT paraphrase"

### 3. FFmpeg crossfade recipes audio_timeline (TheWebivore)
**Source**: thewebivore.com/using-ffmpeg-to-cut-trim-songs-together-with-crossfade

> **Insight**: `atrim + acrossfade` recipe chính xác cho dialogue + silence + BGM. Per-shot sync chuẩn.

**Status**: `audio_timeline.py` đã có `adelay` cho voice/SFX. Sprint 2 thêm `acrossfade` cho BGM transitions giữa scene boundaries (60s+).

### 4. Wan 2.7 audio 44.1kHz cleaner = better lip-sync
**Source**: atlascloud.ai/blog/ai-updates/wan-2-7-video-model-is-live

> **Insight**: Wan 2.7 chấp nhận WAV/MP3 2-30s, càng clean càng tốt vocal signature.

**Status**: GenMax TTS Việt mặc định 44.1kHz mp3 → ✅ chuẩn. Comment trong `vendors/genmax.py` đã verify.

---

## 🟡 SPRINT 2 CONFIRM — Hierarchical Director architecture (5)

### 5. **Camera Artist** paper (arXiv 2604.09195)
3 agents Director (outline→scene) + Cinematography Shot + Video Gen. Confirm Sprint 2 architecture.

### 6. **MovieAgent** (ShowLab github + paper)
Hierarchical CoT Director + Scene Plan + Shot Plan cho long-form. Có **LLM-based validator agent** — vượt storytelling.validate_plan code-level hiện tại.

> **Action Sprint 2**: Build `agent/outline_director.py` (scene-level) → call hiện tại `director_agent.py` per scene (shot-level). Identity chain xuyên scene qua master_board_url + last_frame.

### 7. **AI-Flow Storyboard to Cinematic Video**
3x3 / 2x2 storyboard → per-shot prompt workflow. Match design Master Board → per-shot ref hiện tại.

### 8. **Sarikas YouTube Storyboard Seedance 2.0**
GPT Image 2 generated 9-panel → feed làm global style anchor cho Seedance. Confirm hướng đi `master_board_url` của Task #7.

### 9. **MovieAgent validator agent**
LLM-based critic kiểm plan trước render. Hơn validate_plan hiện tại (rule-based 6 rules). Sprint 3 có thể thêm "LLM critic" pass.

---

## 🟢 ADD TO DOCS / REFERENCE (8)

Đáng track nhưng chưa cần code:

10. **Byteplus official Dreamina Seedance 2.0 prompt guide** (Apr 23 2026) — Official docs xác nhận multi-shot inline + `@image_N`/`@video_N` syntax đã embed trong scene.md.
11. **WaveSpeed Seedance 2.0 template** (Feb 9 2026) — 5-part template Subject+Action+Camera+Style+Negative, đã match awesome-seedance-2-prompts.
12. **WaveSpeed Vidu Q3 ref-to-video** — Confirm bind by array order (Q3 thường) vs `@image_N` (Q3 Mix).
13. **ShengShu Vidu Q3 press release** — Confirm 4-7 refs, multi-entity binding rules.
14. **Awesome Seedance updated May 2026** — Repo cũ tôi đã đọc, đã update thêm 2000+ prompts.
15. **Medium "Reference Pack + Rules" article** — Workflow 3 stills + 1 motion clip + 1 style anchor cho character lock-in. Có thể tích hợp vào Sprint 2 nếu user upload đa modal.
16. **RunDiffusion Seedance 2.0 guide** — `@filename` references (đã match @image_N pattern).
17. **NewEngen TikTok trends Jan 2026** — Vietnamese audio "Ngây Thơ Duet" + opposing perspectives. Cultural insight cho Director Agent context injection.

---

## 🔵 VERIFY / EXPLORE LATER — Sprint 3 polish (5)

18. **AtlasCloud "Best AI Video Models 2026"** — Tiered routing + draft-first $0.022/s. Áp dụng cho Cost Gate enhancement.
19. **Opus.pro 5 hook types** — Confirm 1/5 (Product/Outcome Showcase) đã add. Còn 4 type khác có thể đã match existing hooks → cross-check khi có time.
20. **Camera Artist paper** — Confirmed Sprint 2 direction.
21. **MovieAgent open-source pipeline** — Reference architecture nếu cần rewrite hierarchical.
22. **YouTube "Seedance 2.0 + GPT Image 2 Storyboard"** — Reverse Topview/Lumeflow UI insights, áp dụng UI polish Sprint 3.

---

## 🆕 ĐÃ EMBED VÀO CODE (commit hiện tại)

```diff
+ backend/agent/storytelling.py   HOOK_PATTERNS["outcome_showcase"]  (Opus.pro 2026)
+ backend/system_prompts/scene.md §3.1 Character Block reusable        (CrePal Feb 2026)
```

Director Agent giờ có **11 hook patterns**. Scene Gen giờ instruct LLM dùng verbatim Character Block trong STATIC section.

---

## 🗺️ ROADMAP UPDATE — Sprint 2 confirmed

**Trước Grok research** (Sprint 2 plan):
- Hierarchical Director cho 60-120s
- BGM/SFX library
- Wan lip-sync polish

**Sau Grok research** (Sprint 2 enhanced):
- Hierarchical Director with **MovieAgent-style CoT** (proven 2026 paper)
- BGM library + **acrossfade FFmpeg recipes** (TheWebivore)
- Wan TTS **44.1kHz preference** (verified)
- **LLM critic validator** trước render (MovieAgent pattern, Sprint 3)
- **Reference Pack workflow** (3 stills + motion + style anchor) cho character lock-in session

**Sprint 3 add**:
- Tiered cost routing draft-first $0.022/s (AtlasCloud guide 2026)
- Cross-check 4 hook patterns còn lại từ Opus.pro 5-list
- Multi-modal reference pack UI

---

## 📦 Tổng nguồn đã học sau Grok = **7 cũ + 22 mới = 29 sources**

```
7 cũ (Sprint 0):
  ViMax · ArcReel · drama-director-skill · awesome-seedance-2-prompts
  MindStudio $200 film · CrePal · AtlasCloud Seedance drama

22 mới (Grok 2026-05-23):
  Bucket 1: Byteplus / WaveSpeed / RunDiffusion (Seedance cookbook)
  Bucket 2: Medium / CrePal (character consistency)
  Bucket 3: PRNewswire / WaveSpeed (Vidu multi-entity)
  Bucket 4: Segmind / AtlasCloud (Wan lip-sync)
  Bucket 5: Camera Artist arXiv / MovieAgent OpenReview (hierarchical)
  Bucket 6: StackOverflow (last_frame FFmpeg)
  Bucket 7: Sarikas YouTube / AI-Flow (storyboard)
  Bucket 8: NewEngen / Opus.pro (TikTok VN hooks)
  Bucket 9: AtlasCloud cost guide
  Bucket 10: TheWebivore FFmpeg
  Bucket 11: 4C framework YouTube
  Bucket 12: MovieAgent ShowLab (validators)
  Bucket 13: Segmind Wan TTS
  Bucket 14: Reverse Topview/Lumeflow YouTube
  Bucket 15: MovieAgent + awesome-seedance updates
```
