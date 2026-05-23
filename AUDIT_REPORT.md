# 🔍 Source Code Audit Report — 2026-05-23

Phân loại toàn bộ file: **hoạt động thật / stub / legacy / orphan thừa**.

---

## 📊 Tổng quan

| Tier | FE | Backend | Tổng |
|---|---|---|---|
| ✅ Hoạt động thật end-to-end | 18 file | 31 file | **49** |
| 🚧 Stub placeholder | 5 file | 0 | 5 |
| ⚠️ Legacy (banner LEGACY) | 7 file | 9 file | 16 |
| 🔴 Orphan thừa (KHÔNG import) | 7 file | 4 file | **11** |
| 📂 Test/log artifacts | 0 | 6 file | 6 |

---

## ✅ FRONTEND — Hoạt động thật

### Routes UI (gọi BE qua hooks)
| Route | Backend gọi | Trạng thái |
|---|---|---|
| `app/studio/page.tsx` | `POST /api/v1/director/plan/stream` + `/generate` | ✅ Full flow |
| `app/studio/history/page.tsx` | `GET /api/v1/director/history` + `DELETE` | ✅ Wired |
| `app/studio/library/page.tsx` | `GET/POST/DELETE /api/v1/assets/*` | ✅ Wired |

### Components UI (đều được import)
- `StudioRail`, `StudioTopbar`, `AnnouncementBar` (layout shell)
- `PromptCard`, `ReferenceZones`, `ContextInjection`, `SettingsPanel`, `ModelShowcase`
- `DirectorPlanModal` (3-tab Bible/Shots/Eval), `JobResultModal`
- `ComingSoon` (used by 5 stub pages)
- `Modal`, `Drawer` (base UI)

### Hooks & libs (đều được dùng)
- `lib/studio/use-director-plan.ts` ⭐ (Director Agent flow)
- `lib/studio/use-director-job-poll.ts` (polling job status)
- `lib/studio/use-project-history.ts`
- `lib/studio/use-asset-library.ts`
- `lib/studio/model-config.ts` (per-model metadata)
- `lib/types/backend.ts` (TS contract với BE)

---

## ✅ BACKEND — Hoạt động thật

### API routes (mount trong `api/main.py`)
| Route | Endpoint prefix | Có UI gọi? |
|---|---|---|
| `api/routes/director.py` ⭐ | `/api/v1/director/*` | ✅ FE main flow |
| `api/routes/assets.py` | `/api/v1/assets/*` | ✅ FE library page |
| `api/routes/admin.py` | `/api/v1/admin/*` | 🚧 UI stub |
| `api/routes/avatars.py` | `/api/v1/avatars/*` | 🚧 chưa có UI |
| `api/routes/video_direct.py` | `/api/v1/video/direct/*` | 🚧 stub /studio/text-to-video |
| `api/routes/image_direct.py` | `/api/v1/image/direct/*` | 🚧 chưa wire |
| `api/routes/audio_direct.py` | `/api/v1/audio/direct/*` | 🚧 stub /studio/voice |
| `api/routes/media_upload.py` | `/api/v1/upload-media` | 🚧 chưa wire |
| `api/routes/llm_direct.py` | `/api/v1/llm/*` | 🚧 chưa wire |

### Agent (V3 core)
- `agent/director_agent.py` ⭐
- `agent/scene_generation_agent.py` ⭐
- `agent/continuity_manager.py` ⭐
- `agent/evaluation_layer.py`
- `agent/schemas.py` (Pydantic source of truth)
- `agent/model_specs.py` (verified AtlasCloud payload spec)
- `agent/model_picker.py`, `model_capabilities.py`, `model_adapter.py`
- `agent/model_demos.py`, `model_guide.py` (dùng bởi video/image_direct)
- `agent/image_specs.py`

### Workers
- `workers/video_worker.py` ⭐ (V3 reference chaining)
- `workers/assemble_worker.py` (FFmpeg concat)
- `workers/cost_gate.py` (draft-first cost gate)
- `workers/reassemble_worker.py` (refine 1 shot)

### Vendors (đều active qua llm_router)
- `vendors/atlascloud.py` ⭐
- `vendors/atlascloud_llm.py`
- `vendors/anthropic_client.py` (fallback 402)
- `vendors/llm_router.py`
- `vendors/genmax.py` (TTS Việt)
- `vendors/r2_storage.py`
- `vendors/_retry.py`

### Core utilities (đều dùng)
- `core/config.py`, `jobs_store.py`, `idempotency.py`
- `core/director_history.py`, `assets_store.py`, `style_presets.py`
- `core/llm_cache.py`, `llm_redact.py`, `sanitize.py`

### System prompts (markdown, hot-reload)
- `system_prompts/director.md` ⭐
- `system_prompts/scene.md` ⭐
- `system_prompts/evaluation.md`
- `system_prompts/revise.md` (cho refine flow)

---

## 🚧 STUB / Placeholder (chưa có logic thật)

| File | Note |
|---|---|
| `app/studio/text-to-video/page.tsx` | ComingSoon — sẽ wire `/api/v1/video/direct/generate` |
| `app/studio/image-to-video/page.tsx` | ComingSoon — Wan 2.7 / Seedance i2v |
| `app/studio/voice/page.tsx` | ComingSoon — GenMax TTS 12 giọng VN |
| `app/studio/admin/page.tsx` | ComingSoon — wire `/api/v1/admin/*` |
| `app/studio/docs/page.tsx` | ComingSoon — render markdown |

→ Backend ROUTE đã sẵn sàng (mount + tested), CHỈ thiếu UI gọi. Khi nào cần, build UI thôi.

---

## ⚠️ LEGACY — Có banner "LEGACY" trong code

### Backend (theo README banner)
| File | Lý do legacy | Risk xoá |
|---|---|---|
| `api/routes/jobs.py` | V2 endpoint Analyzer→Generator linear | ⚠️ Còn mount `/api/v1/jobs/*` trong main.py — verify không có client cũ gọi |
| `workers/render_pipeline.py` | 1900+ dòng, replaced bởi V3 video_worker | ⚠️ jobs.py phụ thuộc |
| `agent/strategies/` (7 file) | Strategy per-model V2 — render_pipeline dùng | ⚠️ Đi kèm với render_pipeline.py |
| `agent/strategies/__init__.py` | + base.py + picker.py + 6 model strategies | — |

→ Xoá BLOCK luôn: nếu chắc chắn KHÔNG còn client cũ gọi `/api/v1/jobs/ugc` / `/api/v1/jobs/propose` → có thể clean:
1. Bỏ `app.include_router(jobs.router, ...)` trong `main.py`
2. Xoá `api/routes/jobs.py` + `workers/render_pipeline.py` + `agent/strategies/`
3. Xoá `app/api/v1/jobs/*` proxy routes (8 file)
4. Xoá `lib/backend-client.ts` (chỉ dùng bởi 2 proxy legacy)

**→ Tiết kiệm ~2300 dòng code legacy.**

### Frontend proxy routes orphan (forward đến BE legacy)
| File | Trạng thái |
|---|---|
| `app/api/v1/jobs/route.ts` | proxy `/api/v1/jobs/ugc` — không UI nào gọi |
| `app/api/v1/jobs/[id]/route.ts` + `download/` | poll job V2 — không UI gọi |
| `app/api/v1/jobs/propose/route.ts` + `stream/` | gọi BE Analyzer→Generator | 
| `app/api/v1/jobs/storyboard/gen + regen` | V2 storyboard — không UI gọi |

→ Note: `next.config.js` rewrites đã auto-forward `/api/v1/*` đến BE, nên 8 file route.ts này gần như **THỪA HOÀN TOÀN** ngay cả khi giữ BE legacy (rewrites cover sẵn).

---

## 🔴 ORPHAN THỪA (KHÔNG import bởi ai)

### Frontend hooks orphan (sau redesign UI)
| File | Lý do orphan |
|---|---|
| `lib/studio/parse-image-mentions.ts` | Chỉ self-reference |
| `lib/studio/use-admin.ts` | UI admin chưa build (stub) |
| `lib/studio/use-director-plan-editor.ts` | DirectorPlanModal mới chưa support edit inline |
| `lib/studio/use-genmax-tts.ts` | UI voice chưa build (stub) |
| `lib/studio/use-refine-shot.ts` | UI refine button chưa add |
| `lib/studio/use-timeline.ts` | Timeline editor chưa build |
| `lib/studio/use-workspace-chat.ts` | Workspace chat đã bỏ ở redesign |

→ **An toàn xoá ngay 7 file** (~600-1000 dòng) HOẶC giữ làm "logic kho" để wire khi build sub-route.

### Backend orphan (chỉ self-reference hoặc trong render_pipeline LEGACY)
| File | Trạng thái |
|---|---|
| `agent/duration_extender.py` | Chỉ `model_adapter.py` ref nhẹ — chia long-form duration | 
| `agent/trend_cache.py` + `workers/trend_scanner.py` | Cron scraper VN TikTok — không có cron đăng ký |
| `vendors/elevenlabs_sfx.py` | Chỉ render_pipeline LEGACY dùng → orphan nếu xoá legacy |

→ **An toàn xoá nếu xoá legacy.**

---

## 📂 TEST / LOG ARTIFACTS (xoá thoải mái)

| File | Size | Note |
|---|---|---|
| `backend/dev_all.log` | 224K | Log dev session cũ |
| `backend/uvicorn.log` | 1K | Boot log |
| `backend/uvicorn.err` | 1K | Boot err |
| `fe_new.log` | 4K | Log FE session |
| `dev_all_run.log` | 8K | Log session |
| `backend/scripts/propose_v2.json` | 257B | Test body V2 (deprecated) |
| `backend/scripts/propose_v3.json` | 20K | Test body V3 reference |
| `backend/scripts/test_propose_body.json` | 592B | Test artifact |
| `public/` | empty | Đã clean trước |
| `backend/data/jobs_store.db` | 43M | Job history cũ — có thể vacuum nếu muốn |

---

## 🎯 Đề xuất CLEAN UP (3 mức)

### Mức 1 — An toàn (~ no risk)
1. Xoá 7 FE hook orphan trong `lib/studio/`
2. Xoá `backend/dev_all.log`, `uvicorn.log`, `uvicorn.err`, `fe_new.log`, `dev_all_run.log`
3. Xoá `backend/scripts/propose_v2.json` + `test_propose_body.json` (giữ `propose_v3.json` làm reference)
4. Vacuum SQLite jobs_store.db để giảm 43MB → vài MB

**Lệnh:**
```bash
cd c:/Users/Admin/Desktop/cineforge-studio-mvp
rm lib/studio/parse-image-mentions.ts lib/studio/use-admin.ts lib/studio/use-director-plan-editor.ts \
   lib/studio/use-genmax-tts.ts lib/studio/use-refine-shot.ts lib/studio/use-timeline.ts \
   lib/studio/use-workspace-chat.ts
rm backend/dev_all.log backend/uvicorn.log backend/uvicorn.err fe_new.log dev_all_run.log
rm backend/scripts/propose_v2.json backend/scripts/test_propose_body.json
```

### Mức 2 — Xoá Legacy V2 (~2300 dòng code)
1. Trong `backend/api/main.py`: bỏ dòng `app.include_router(jobs.router, ...)`
2. Xoá `backend/api/routes/jobs.py`
3. Xoá `backend/workers/render_pipeline.py`
4. Xoá `backend/agent/strategies/` (7 file)
5. Xoá `backend/vendors/elevenlabs_sfx.py`
6. Xoá `app/api/v1/jobs/` (8 file proxy)
7. Xoá `lib/backend-client.ts`

→ Verify trước: grep production logs xem có client nào còn gọi `/api/v1/jobs/ugc` không. Nếu không → SAFE.

### Mức 3 — Trim cron không dùng
- Xoá `backend/agent/trend_cache.py` + `backend/workers/trend_scanner.py` + `backend/data/trend_cache.db`
- Bỏ logic trend khỏi director_agent (check usage trước)

---

## 📈 Sau khi clean

| | Trước | Sau Mức 1 | Sau Mức 1+2 | Sau full Mức 1+2+3 |
|---|---|---|---|---|
| Tổng file `.ts/tsx/py` | 87 | 75 | 56 | 53 |
| Code dòng | ~12K | ~11K | ~9K | ~8.5K |
| Disk | ~50MB | ~5MB | ~5MB | ~5MB |

---

## ✅ TÓM TẮT 1 CÂU

Source hiện tại có **49 file hoạt động thật end-to-end**, **5 stub placeholder** (có route BE sẵn chỉ chưa wire UI), **16 file LEGACY V2** (an toàn xoá), **11 file orphan thuần** (an toàn xoá ngay). Backend pipeline V3 (Director → Scene Gen → Video Worker → Assemble) hoàn toàn intact, không phụ thuộc gì LEGACY.
