# 🎬 CineForge Storytelling Pipeline — V4

> Niche-agnostic dramatic structure cho mọi video AI 15s – 60s, tổng hợp từ 7 nguồn industry (ViMax, ArcReel, drama-director-skill, awesome-seedance-2-prompts, MindStudio film, CrePal product ads, AtlasCloud Seedance drama workflow).

---

## 1. Best practices summary (8 sections — đã embed vào prompt)

### A · Hook patterns (10 named)
`pattern_interrupt` · `direct_question` · `bold_statement` · `lifestyle_cold_open` · `pov_confession` · `social_proof_drop` · `visual_anomaly` · `before_after_tease` · `reaction_shot` · `offer_led`

→ Director Agent picks EXACTLY ONE pattern per plan. No mixing. Bake into shot 1.

### B · Dramatic structure (fixed beat sheet, slot-filled)
```
HOOK    (0-2s)         pattern interrupt, NO product, NO logo
PAIN    (2-6s)         problem viewer recognizes, character introduced
TENSION (escalation)   stakes rise — only when duration ≥ 30s
REVEAL  (≥40% runtime) product appears as the answer
PROOF   (demo)         feature via action, not text overlay
CTA     (final 2-3s)   explicit imperative verb
```

### C · Lead-in product (no-ad feel)
- Problem-first, product later
- Camera moves, not product moves
- Casual ambient placement before subject reveal
- Three-variant spawning (premium / lifestyle / offer-led)
- Result-first hook (show outcome, reveal cause)

### D · Character consistency (Seedance 2.0)
- Visual DNA lock via `face_signature` 1-2 concrete sentences
- Reference chaining (last_frame → next shot i2v input)
- 9-panel anchor / face-anchor phrase reused verbatim
- Functional descriptors only (NO age numbers)
- Design around full-face overuse — silhouette / profile / hand close-up

### E · Shot-by-shot timing (sweet spot)
- Hook: 1-2s · Setup: 2×2s · Tension: 3-4×1.5s · Reveal: 2-3s · Proof: 2×2s · CTA: 2-3s
- 15s → 8-10 shots · 30s → 12-18 · 60s → 20-30
- Complex motion only on wide/medium · Double-contrast cut each transition

### F · Seedance 2.0 three-section template
```
[STYLE & MOOD]    palette, film stock, lighting
[DYNAMIC]         0:00-0:02 ECU push-in ... 0:02-0:04 Hard cut to MS handheld ...
[STATIC]          face anchor phrase verbatim, outfit invariant, location lock, negatives
```

### G · Niche-agnostic strategy (slot pattern)
Fill from brief, no per-niche template:
```
problem_statement  · character_archetype  · product_role  · payoff_emotion  · cta_verb
```

### H · Pitfalls (avoided in prompt)
Don't open with product close-up · Don't skip style bible · Don't mix incompatible perspectives in one cut · Don't over-describe (>2000 chars) · Don't write "camera sweeps comic page" · Don't regenerate individual shots (drift) · Don't put complex motion in close-ups · Don't use age indicators · Don't forget audio · Don't skip CTA verb.

---

## 2. Where each best practice lives in code

| Best practice | File | Mechanism |
|---|---|---|
| 10 hook patterns enum | `backend/agent/storytelling.py` | `HOOK_PATTERNS` dict + `hook_patterns_block()` |
| Beat sheet 15s/30s/60s | `backend/agent/storytelling.py` | `beat_sheet_for(duration_s)` + `beat_sheet_block()` |
| Hard rules (negative constraints) | `backend/agent/storytelling.py` | `hard_rules_block()` |
| Niche slot pattern | `backend/agent/storytelling.py` | `NICHE_SLOT_KEYS` + `niche_slot_block()` |
| 3-section Seedance schema | `backend/system_prompts/scene.md` | §2 template |
| Drama-beat awareness per shot | `backend/system_prompts/scene.md` + `scene_generation_agent.py` | §1 + `beat_intent` payload field |
| Auto-validators (product timing, double-contrast, hook presence) | `backend/agent/storytelling.py` | `validate_plan(plan_dict)` |
| Storytelling context injection | `backend/agent/director_agent.py` | `_build_director_input` adds `storytelling_context` block |
| Post-LLM soft validation | `backend/agent/director_agent.py` | After `sanitize_plan` → calls `validate_plan` → emits `storytelling_check` SSE event |

---

## 3. End-to-end Pipeline (CineForge V4)

```
┌─────────────────────────────────────────────────────────────────────┐
│ USER INPUT (Studio UI — /studio)                                    │
│   • brief text (any niche, any duration)                            │
│   • reference_images[] (Character / Product / Storyboard zones)     │
│   • reference_role_hints[] (from zone tagging, skips vision LLM)    │
│   • settings (model, duration_s, aspect, resolution, audio_mode)    │
│   • context_injection (pain_points, USPs, forbidden_to_say, mood)   │
└─────────────────────┬───────────────────────────────────────────────┘
                      │ POST /api/v1/director/plan/stream
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│ LAYER 1 · Director Agent V4 (director_agent.py)                     │
│ ┌───────────────────────────────────────────────────────────────┐   │
│ │ A. Sanitize inputs (prompt injection + PII strip)             │   │
│ │ B. Ref classification: user-tag hints > vision LLM scan       │   │
│ │ C. Build input bundle:                                        │   │
│ │     - product_input, reference_*, brief, context              │   │
│ │     - tech_config + model_capability_notes                    │   │
│ │     - 🆕 storytelling_context {                                │   │
│ │           hook_patterns:  ← 10-pattern enum                   │   │
│ │           beat_sheet:     ← phase budget for duration_s       │   │
│ │           hard_rules:     ← negative constraints              │   │
│ │           niche_slots:    ← 5-slot fill pattern               │   │
│ │       }                                                       │   │
│ │ D. Director LLM call → DeepSeek-V4-Pro / Claude Sonnet 4.6    │   │
│ │     System: system_prompts/director.md (with storytelling §)  │   │
│ │     User:   JSON input bundle above                           │   │
│ │     Output: DirectorPlan JSON (Bible + ShotList + Storyboard) │   │
│ │ E. Parse + repair + reindex shots                             │   │
│ │ F. continuity_manager: validate_plan + auto_chain + sanitize  │   │
│ │ G. 🆕 storytelling.validate_plan() — soft, log issues:        │   │
│ │     • PRODUCT_OPENS (block - product as shot 1 subject)       │   │
│ │     • PRODUCT_TOO_EARLY (warn - <30% runtime)                 │   │
│ │     • DOUBLE_CONTRAST_VIOLATION (warn)                        │   │
│ │     • MISSING_HOOK (block - no shot purpose=hook)             │   │
│ │     • WEAK_FACE_ANCHOR (warn)                                 │   │
│ │     • DURATION_MISMATCH (warn ±2s)                            │   │
│ │     → emit SSE event `storytelling_check` to FE               │   │
│ │ H. Evaluation Layer self-score (5 dim + overall)              │   │
│ │ I. Cost estimate (LLM + storyboard + render + audio)          │   │
│ └───────────────────────────────────────────────────────────────┘   │
└─────────────────────┬───────────────────────────────────────────────┘
                      │ SSE complete → DirectorPlan
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ✋ HUMAN-IN-THE-LOOP (DirectorPlanModal UI)                          │
│   User reviews 3 tabs: Bible / Shot List / Evaluation               │
│   Sees storytelling issues if any (red_flags + suggestions)         │
│   Edits if needed (TODO: revise endpoint), then APPROVE             │
└─────────────────────┬───────────────────────────────────────────────┘
                      │ POST /api/v1/director/generate
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│ LAYER 2 · Scene Generation Agent V4 (per shot)                      │
│ ┌───────────────────────────────────────────────────────────────┐   │
│ │ Called lazily from video_worker.render_loop per shot          │   │
│ │ Per-shot payload to scene.md LLM:                             │   │
│ │     - bible (with storytelling_meta)                          │   │
│ │     - shot (with purpose + dynamic_description)               │   │
│ │     - model_key + model_format_hint                           │   │
│ │     - last_frame_url (chain anchor from prior shot)           │   │
│ │     - reference_images[], reference_videos[]                  │   │
│ │     - 🆕 beat_intent ← derived from shot.purpose              │   │
│ │ LLM output: SceneRenderJob                                    │   │
│ │     - prompt (3-section Seedance OR model-specific format)    │   │
│ │     - negative_prompt (must_avoid + phase-specific)           │   │
│ │     - reference_image_indices                                 │   │
│ │     - render_mode (ref_to_video / i2v_chain / t2v)            │   │
│ │     - chain_input_url                                         │   │
│ │     - model_params (duration, resolution, aspect, audio)      │   │
│ └───────────────────────────────────────────────────────────────┘   │
└─────────────────────┬───────────────────────────────────────────────┘
                      │ atlas_client.generate_video(**job.to_atlas_kwargs())
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│ LAYER 3 · Video Worker (video_worker.py)                            │
│ ┌───────────────────────────────────────────────────────────────┐   │
│ │ for shot in plan.shot_list (sequential, identity-chained):    │   │
│ │   • shot 0 OR previous_shot_id=null → ref_to_video            │   │
│ │   • shot N with chain + last_frame_url → swap i2v variant     │   │
│ │   • vendors.atlascloud.generate_video()                       │   │
│ │   • download clip + capture next last_frame_url               │   │
│ │ Optional cost_gate(draft_first) — render shot[0] at Fast tier,│   │
│ │ score via Eval. Abort if < threshold before spending Standard │   │
│ │ tier credits.                                                 │   │
│ │ AssembleWorker: FFmpeg concat → TTS overlay → SFX → caption.ass│  │
│ │ Color consistency pass (Bible visual_style → eq/curves)       │   │
│ │ Upload final MP4 to Cloudflare R2 (fallback file://)          │   │
│ └───────────────────────────────────────────────────────────────┘   │
└─────────────────────┬───────────────────────────────────────────────┘
                      │ output_url (MP4)
                      ▼
                ┌──────────────┐
                │ JobResultModal│  ← user xem MP4, download, share
                └──────────────┘
```

---

## 4. Tại sao thiết kế này "ứng biến mọi niche"

1. **Cấu trúc FIXED, nội dung NICHE-AGNOSTIC** — LLM không tự bịa structure, chỉ điền slot từ brief. Beauty/tech/food/B2B/drama đều dùng cùng beat sheet, chỉ khác `problem_statement` / `cta_verb`.

2. **Hook patterns enum** — LLM chọn 1 trong 10 pattern có sẵn (đã chứng minh viral). Không có cơ hội bịa hook tệ.

3. **Hard rules tự validate** — Product không mở đầu video, double-contrast cut, hook phải tồn tại. Tránh được những bug pattern phổ biến.

4. **3-section Seedance** — Khi target Seedance 2.0, prompt theo schema chuẩn industry, output ổn định identity.

5. **Beat-aware per shot** — Scene Gen biết shot này là HOOK hay REVEAL, adapt camera/light language phù hợp.

6. **System prompts là Markdown** — Sửa file `.md` = sửa AI (lru_cache reload). Không cần redeploy.

---

## 5. Migration notes — V3 → V4

### Đã thay đổi (backward-compatible)
- `system_prompts/director.md` rewrite — thêm storytelling layer
- `system_prompts/scene.md` rewrite — thêm drama-beat awareness
- `backend/agent/director_agent.py::_build_director_input` — inject `storytelling_context`
- `backend/agent/director_agent.py` — soft validation call sau parse
- `backend/agent/scene_generation_agent.py` — inject `beat_intent` field vào LLM payload

### Đã thêm mới
- `backend/agent/storytelling.py` (new module — 280 dòng, pure functions)
- `STORYTELLING_PIPELINE.md` (doc này)

### KHÔNG break
- `DirectorPlan` schema giữ nguyên (storytelling_meta + dynamic_description là optional fields)
- API endpoint signatures giữ nguyên
- All UI hooks / proxy routes wire bình thường
- Existing FE flow chạy không lỗi

### Optional schema extension (LLM tự fill khi có)
- `bible.storytelling_meta` (hook_pattern, beat_coverage, product_first_appearance_s, primary_emotion_arc)
- `shot.dynamic_description` (timestamped beat string cho Seedance multi-shot)

Nếu LLM cũ output không có 2 field này → vẫn parse OK vì Pydantic ignore extra fields trừ khi schema strict.

---

## 6. Test plan thực chiến

| Test | Brief | Expected behavior |
|---|---|---|
| **Niche shift** | "Video TikTok 15s nữ Gen Z thử son li matte" → "Video TikTok 15s tech demo iPhone 16 Pro" → "Video TikTok 15s phở Việt Nam ASMR" | Cả 3 đều output beat sheet HOOK→PAIN→REVEAL→PROOF→CTA, chỉ khác slot. KHÔNG có niche template hardcoded. |
| **Hook diversity** | Chạy 10 lần cùng brief | Director chọn ≥ 5 hook pattern khác nhau (pattern_interrupt, direct_question, pov_confession...). |
| **Product timing** | Brief "video review son" | shot 1 KHÔNG có product as subject. Product xuất hiện ≥ 30% runtime. Nếu LLM phá rule → log issue PRODUCT_OPENS. |
| **Duration adapt** | 15s vs 30s vs 60s | 15s → 5 beats compressed. 60s → 7 beats full arc. |
| **Model awareness** | Đổi model Seedance 2.0 → Vidu Q3 → Wan 2.7 | Director respect model_capability_notes: Wan duration discrete [5,10], Vidu max_refs=4. |

---

## 7. Future improvements (chưa làm)

- **Storyboard preview tab** trong DirectorPlanModal — show ảnh từ `/director/storyboard` endpoint
- **Revise plan** button trong PlanModal → call `/director/revise` với feedback text
- **Refine 1 shot** từ ShotList tab → call `/director/refine`
- **Cost gate UI** toggle — kích hoạt `draft_first` mode trong SettingsPanel
- **Storytelling check display** trong PlanModal — show story_issues từ SSE event
- **Hook pattern preview gallery** — UI cho user thấy 10 hook patterns + ví dụ
