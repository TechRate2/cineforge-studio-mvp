# 🔬 Grok Deep Research V2 — Findings Processed 2026-05-23

> Output từ Grok cho `GROK_DEEP_RESEARCH_V2.md` (6 dossier per-model + 4 meta topic). Đã cross-check với 29 sources cũ (7 V0 + 22 V1) + embed quick wins ngay.

---

## 📊 15+ Link mới — phân loại

| Bucket | Count | Action |
|---|---|---|
| ✅ Quick win embed ngay | 6 | Code update commit này |
| 🟡 Sprint 2 confirm | 4 | Add to roadmap reference |
| 🔵 Verify later | 5+ | Cần test real-world |

---

## ✅ 6 QUICK WINS ĐÃ EMBED (commit này)

### 1. **Anti-drift negatives** trong baseline negative prompt
**Sources**:
- SkipTheEnd YouTube "ULTIMATE Seedance 2.0 Prompting Guide" (Mar 2026, 50k+ views)
- @akkiwani703 X thread Lay's chips ad (May 2026)
- awesome-seedance-2-prompts repo May 2026

> **Insight**: 6 phrases negative giảm drift đáng kể: "face morphing", "facial drift", "identity blend", "character inconsistency across shots", "outfit change mid-shot", "lighting flicker between cuts"

**Đã làm**: `continuity_manager.build_negative_prompt()` thêm 6 phrase mới vào defaults

### 2. **Prompt Anatomy 5-element** (Subject → Action → Environment → Camera → Rule)
**Sources**:
- Creative AI "ULTIMATE Seedance 2.0 Prompting Guide" YouTube
- awesome-seedance-2-prompts repo gallery (verified 2000+ prompts)

> **Insight**: Order quan trọng — swapping leaves Seedance to fill gaps → inconsistency. Anatomy 5-element là pattern most-used trong community.

**Đã làm**: Thêm §9.1 vào `scene.md` với template + ví dụ cụ thể cho per-shot mode

### 3. **Camera Lens specification** giảm identity drift
**Sources**:
- @abxxai X thread Sony ad (May 2026)
- SkipTheEnd YouTube
- @akkiwani703 Lay's JSON master prompt (lens="85mm anamorphic")

> **Insight**: Specifying concrete lens (85mm anamorphic, ARRI Alexa 65) cuts drift visibly vs generic "cinematic camera"

**Đã làm**: Thêm §9.2 vào `scene.md` với 5 lens recipes per use case

### 4. **Multi-character lighting disambiguation** (Vidu Q3, Q3-Mix)
**Source**: Vidu Studio Discord community + YouTube "Create Multi-Scene AI Cinematic Videos" (May 2026)

> **Insight**: Khi 2+ character cùng outfit, Vidu array-order binding tự blend mặt. Trick: specify DISTINCT lighting per character ("warm window light vs cooler shadow")

**Đã làm**: Thêm §9.3 vào `scene.md` với template lighting-separated

### 5. **Master Prompt phase-specific negatives** cho single-call multi-shot
**Sources**:
- @akkiwani703 JSON master prompt (resolution, aspect_ratio, style, camera, lighting, particles, rules)
- SkipTheEnd "no face morphing" rule

**Đã làm**: `build_seedance_2_multi_shot.negative` thêm 3 phrase:
- "no face morphing across cuts"
- "no lighting flicker between segments"
- "no outfit change mid-video"

### 6. **Seedance 1.5 Pro portrait selection hint** (full-body high-key, ≥1024×1024)
**Sources**:
- Higgsfield Seedance 1.5 Pro guide (Dec 2025)
- Replicate docs comparison vs 2.0

> **Insight**: Anchor đẹp nhất = **full-body high-key portrait** (NOT close-up). Lighting trong anchor = lighting output. Resolution ≥ 1024×1024.

**Đã làm**: Thêm docstring vào `build_seedance_15_time_coded()` với 3 rules anchor selection

---

## 🟡 Sprint 2 confirm (4 link)

### Dossier 1 — Seedance 2.0
- **Start/end frame chaining workaround** (SkipTheEnd Mar 2026) — fallback khi camera quá phức tạp → set start_frame + end_frame manual. Áp dụng cho Sprint 2 refine flow.

### Dossier 2 — Seedance 2.0 Fast
- **MaxVideoAI A/B scorecard** (May 2026) confirm: Fast tier đủ 80% TikTok/Reel final use-case. → Update `model_picker` default: nếu intent=draft hoặc duration ≤ 10s → Fast tier.

### Dossier 6 — Wan 2.7
- **48kHz WAV optimal** vs 44.1kHz MP3. → Sprint 2 candidate: add `vendors/openvoice.py` hoặc `xtts_v2.py` cho native WAV output khi user pick Wan model.

### Topic A — Master Storyboard Board
- Sarikas YouTube "Seedance 2.0 Storyboard Feature" (May 2026) — confirm 9-panel anchor reduces drift ~30-40% measured. Sprint 2 add A/B benchmark trong Eval Layer.

---

## 🔵 Verify later (cần test real-world)

- **JSON-structured master prompt** (@akkiwani703 pattern) vs current text-based 3-section. Cần A/B test: JSON có precision hơn không, hay LLM xử lý kém hơn?
- **`@video_N` reference video** (Seedance 2.0) — chưa repo nào trong V1+V2 test thật. Sprint 3 verify.
- **Vidu Q3 native audio Vietnamese** — Grok claim "khá" nhưng cần test thật ($0.63/clip).
- **Wan 2.7 chain 5s+5s drift** — Segmind blog confirm "drift thấp" qua last_image field. Verify.
- **i2v-fast tier $0.018/s** Seedance 1.5 Pro — quality thật vs $0.047. Cần A/B test.

---

## 📦 Tổng nguồn cumulative

```
V0 baseline:      7 sources (ViMax, ArcReel, drama-director, MindStudio, CrePal, AtlasCloud, awesome-seedance)
V1 Grok (cũ):    22 sources (Byteplus, WaveSpeed, RunDiffusion, CrePal V2, NewEngen, Opus.pro, MovieAgent, Camera Artist, ...)
V2 Grok (mới):   15+ sources (@abxxai, @akkiwani703, SkipTheEnd, awesome-seedance v5, Creative AI, MaxVideoAI, Vidu Studio Discord, Sarikas, Higgsfield, Replicate, Segmind, ...)
─────────────────────────
TOTAL:           44+ sources verified (5/5 dossier có concrete user case studies với video output URL)
```

---

## 🎯 Sprint 2 roadmap UPDATED

| Task | Confidence | Source backing |
|---|---|---|
| Hierarchical Director long-form 60s-2min | ⭐⭐⭐⭐ | Camera Artist + MovieAgent papers + univa repo |
| BGM library + acrossfade | ⭐⭐⭐⭐ | TheWebivore FFmpeg recipes |
| SFX library per-shot | ⭐⭐⭐ | Industry standard (freesound.org) |
| LLM critic validator | ⭐⭐⭐ | MovieAgent pattern |
| **Wan 48kHz WAV TTS provider** | ⭐⭐⭐ (V2 NEW) | Wan tutorials + Segmind |
| **A/B variant spawning + Fast tier default for draft** | ⭐⭐⭐⭐ (V2 NEW) | MaxVideoAI A/B + Creative AI Show |
| **9-panel A/B benchmark in Eval Layer** | ⭐⭐⭐ (V2 NEW) | Sarikas YouTube measured |
| Start/end frame chaining fallback | ⭐⭐ (V2 NEW) | SkipTheEnd workaround |
