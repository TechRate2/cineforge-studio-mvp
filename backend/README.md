# CineForge AI V3 — Backend

FastAPI + Pydantic + AtlasCloud — Director Agent V3 (dynamic planning) thay thế hoàn toàn pipeline Analyzer→Generator linear cũ.

> Đây là backend cho [UGC Vietnam Studio](../README.md). Frontend Next.js gọi qua proxy `/api/v1/*`.

---

## 1. Triết lý thiết kế

- **Zero hardcoded templates.** Không còn 30 template skeleton. Director Agent tự sinh shot list 8-15 shots phù hợp brief + duration + niche bất kỳ.
- **Continuity Bible** là single source of truth. Mọi shot prompt downstream derive từ Bible → identity nhất quán video dài.
- **Universal Reference.** Mỗi ảnh user upload được Director tag role + binding shot_ids. Scene Gen Agent dùng `continuity_manager.references_for_shot()` để lấy đúng refs cho từng shot.
- **Reference Chaining.** Shot có `previous_shot_id` → render loop tự swap i2v + pass last frame trước = identity không drift.
- **Markdown system prompts**, không hardcode trong `.py`. Iterate prompt = sửa file `.md` → reload, không build lại.
- **Human-in-the-Loop**. Director plan KHÔNG tự render. User review tab Bible/Shot List/Eval → Approve mới fire `/generate`.

---

## 2. Kiến trúc 3 Layer

```
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 1 — Director Agent V3                                     │
│   agent/director_agent.py + system_prompts/director.md          │
│   1 LLM call (DeepSeek-V4-Pro / Claude Sonnet)                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ Continuity Bible:                                       │   │
│   │   title / logline / intent / duration                   │   │
│   │   characters[] (face_signature + outfit invariant)      │   │
│   │   products[] (packaging + hero_features)                │   │
│   │   visual_style {cinematography, grading, lighting...}   │   │
│   │   audio_design {mood, tempo, dialogue_style...}         │   │
│   │   setting {location, time_of_day, atmosphere}           │   │
│   │   constraints {must_have, must_avoid, brand_safety}     │   │
│   │   reference_assets[] {index, role, apply_to_shots[]}    │   │
│   │ Shot List 8-15 shots:                                   │   │
│   │   visual / audio / continuity / model_routing per shot  │   │
│   │ Storyboard Grid (prompts cho image gen)                 │   │
│   └─────────────────────────────────────────────────────────┘   │
│   + Vision pass nhẹ phân loại refs (optional)                   │
│   + agent/evaluation_layer.py self-critique scoring             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
          ✋  Human-in-the-Loop (DirectorPlanModal review/edit)
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 2 — Scene Generation Agent                                │
│   agent/scene_generation_agent.py + system_prompts/scene.md     │
│   Per shot: build SceneRenderJob {prompt, refs, render_mode}    │
│   Model-aware format hints:                                     │
│     - seedance_2_0:      multi_shot_inline ([Shot N — Xs])      │
│     - seedance_1_5_pro:  time_coded ([0-Xs])                    │
│     - wan_2_7 / *_i2v:   i2v_motion (motion verbs only)         │
│     - vidu_q3:           single_descriptive                     │
│   Modes:                                                        │
│     - llm_mode=True  (default): 1 LLM call/shot (flexible)      │
│     - llm_mode=False:           deterministic build (no LLM)    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 3 — Video Worker V3                                       │
│   workers/video_worker.py                                       │
│   ┌─ For each shot in plan.shot_list (sequential):              │
│   │  • shot 0 OR no chain → ref_to_video (use bound refs)       │
│   │  • shot N with previous_shot_id + last_frame_url available  │
│   │      → swap to i2v variant + image=last_frame_url           │
│   │  • generate via vendors/atlascloud.generate_video()         │
│   │  • download clip + capture next last_frame_url              │
│   └─                                                            │
│   AssembleWorker:                                               │
│     • FFmpeg concat with aspect-aware scale                     │
│     • optional voiceover / SFX overlay                          │
│     • burn caption_vn (.ass subtitle)                           │
│   Color consistency pass (Bible-driven FFmpeg eq/curves)        │
│   → Final MP4                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Folder map

```
backend/
├── agent/
│   ├── schemas.py                Pydantic: ContinuityBible / Shot / DirectorPlan / EvalReport
│   ├── director_agent.py         ⭐ Layer 1 — singleton `director`
│   ├── continuity_manager.py     validate / normalize timeline / auto-chain / inject Bible
│   ├── scene_generation_agent.py ⭐ Layer 2 — SceneRenderJob builder
│   ├── evaluation_layer.py       Self-critique LLM call
│   ├── trend_cache.py            Optional VN-TikTok trend SQLite cache
│   ├── model_specs.py            Per-model AtlasCloud payload spec
│   ├── model_adapter.py          Cost / model metadata
│   ├── model_guide.py / model_demos.py
│   ├── image_specs.py            Seedream / Flux payload
│   ├── duration_extender.py
│   └── strategies/               Per-model legacy strategies (kept for jobs.py legacy)
│
├── system_prompts/               ⭐ Markdown prompts (load via `system_prompts.load("director")`)
│   ├── __init__.py               lru_cache loader
│   ├── director.md               Layer 1 — must output strict JSON DirectorPlan
│   ├── scene.md                  Layer 2 — model-aware prompt formats
│   └── evaluation.md             Strict scoring rubric
│
├── api/
│   ├── main.py                   Bootstrap, CORS, router mount
│   ├── schemas.py                Shared request/response schemas
│   └── routes/
│       ├── director.py           ⭐ V3 — /plan, /plan/stream, /storyboard, /generate, /jobs/{id}
│       ├── jobs.py               ⚠️ LEGACY — only accepts Director-approved input
│       ├── video_direct.py / image_direct.py / audio_direct.py
│       ├── media_upload.py / llm_direct.py / avatars.py
│
├── workers/
│   ├── video_worker.py           ⭐ Layer 3 V3 (Reference Chaining loop)
│   ├── assemble_worker.py        FFmpeg pipeline
│   ├── render_pipeline.py        ⚠️ LEGACY (used only by jobs.py)
│   └── trend_scanner.py          Cron scraper
│
├── vendors/
│   ├── atlascloud.py             ⭐ Refactored — `generate_video()` returns last_frame_url
│   │                              + new `generate_video_chain()` helper
│   ├── atlascloud_llm.py         LLM via AtlasCloud (DeepSeek/Qwen3-VL/Claude)
│   ├── llm_router.py             AtlasCloud primary + Anthropic fallback
│   ├── genmax.py                 VN TTS
│   ├── elevenlabs_sfx.py
│   ├── anthropic_client.py
│   └── _retry.py
│
├── core/
│   ├── config.py                 Pydantic settings (env)
│   ├── jobs_store.py             SQLite file-based job persistence
│   ├── idempotency.py            Stripe-style Idempotency-Key
│   ├── llm_cache.py / llm_redact.py / sanitize.py
│
├── data/                         SQLite WAL (gitignored)
└── requirements.txt
```

---

## 4. Setup

```bash
cd backend
pip install -r requirements.txt

# Env (root .env.local — both FE & BE read it)
ANTHROPIC_API_KEY=sk-ant-xxx
ATLASCLOUD_API_KEY=...           # image + video gen wallet (Pay-as-you-go)
ATLASCLOUD_LLM_API_KEY=...       # LLM wallet (Coding Plan)
GENMAX_API_KEY=...               # VN TTS
ELEVENLABS_API_KEY=...           # SFX (optional)

# LLM routing — default all via AtlasCloud (1 wallet)
LLM_PROVIDER=atlascloud
LLM_MODEL_ANALYZER=deepseek-v4-flash
LLM_MODEL_GENERATOR=deepseek-v4-pro
LLM_MODEL_VISION=qwen3-vl-30b-instruct
```

Run:

```bash
uvicorn api.main:app --reload --port 8000
# Swagger: http://localhost:8000/docs
```

---

## 5. API V3 endpoints

### `POST /api/v1/director/plan`

Sync — Layer 1 builds plan. ~10-30s, ~$0.04 / call.

```jsonc
// Request
{
  "product_input": { "url": null, "text_description": "Son lì matte 89k", "image_urls": [] },
  "reference_images": ["https://...", "data:image/png;base64,..."],   // 0-12
  "reference_videos": [],                                             // 0-1
  "user_brief": "Video TikTok 15s nữ Gen Z thử son ở bàn make-up...",
  "context_injection": {
    "pain_points": "...", "real_reviews": "...", "usps": "...",
    "forbidden_to_say": "...", "mood_hint": "..."
  },
  "settings": {
    "audio_mode": "dialogue_vo",
    "model": "seedance_2_0",
    "duration_s": 15, "aspect_ratio": "9:16", "resolution": "720p",
    "num_shots": null
  },
  "niche_hint": "beauty"   // free string, not enum
}

// Response — DirectorPlan
{
  "plan_id": "dp_abc123",
  "created_at": "2026-05-22T...Z",
  "continuity_bible": { ... },
  "shot_list": [ { "shot_id": "S1", ... }, ... ],
  "storyboard_grid": [ { "shot_id": "S1", "prompt": "...", "image_size": "1080*1920" }, ... ],
  "evaluation": { "overall_score": 7.8, "strengths": [...], "weaknesses": [...], "red_flags": [...] },
  "cost_estimate": { "plan_cost_usd": 0.04, "render_cost_usd": 1.44, ... },
  "llm_calls_total": 2,
  "elapsed_s": 18.3
}
```

### `POST /api/v1/director/plan/stream`

SSE version. Events:

```
event: open       — connection ready
event: stage      — { stage: "vision|director|evaluation", status: "running|done", message, ... }
event: complete   — full DirectorPlan JSON
event: error      — { error: "..." }
```

### `POST /api/v1/director/storyboard`

Fire Seedream image gen cho từng storyboard frame. Returns updated DirectorPlan với `generated_url` filled. Cost: ~$0.04 / frame × N shots.

### `POST /api/v1/director/generate`

Layer 3 — render an **approved** DirectorPlan (canonical Human-in-the-Loop path).

```jsonc
// Request
{
  "plan": { ...full DirectorPlan từ POST /plan, có thể đã edit... },
  "reference_images": [ ... ],
  "settings": { "audio_mode": "...", "model": "...", "duration_s": 15, ... },
  "audio_plan": null,
  "use_llm_scene_gen": true,
  // V3 §7 Cost Optimization:
  "cost_gate_mode": "off",          // "off" | "draft_first"
  "cost_gate_threshold": 7.0        // 0-10, pass threshold for draft_first mode
}

// Response
{
  "job_id": "job_xxxxx",
  "polling_url": "/api/v1/director/jobs/job_xxxxx",
  "estimated_duration_s": 15,
  "estimated_cost_usd": 1.48,
  "plan_id": "dp_...",
  "mode": "approved",
  "cost_gate_mode": "off"
}
```

Flow: server runs `continuity_manager.validate_plan()` → if any hard error, 400.
Soft warnings are kept on the job record and `sanitize_plan()` cleans bad refs.
Then `video_worker.render_plan()` is dispatched in the background.

**Cost gate** (`cost_gate_mode="draft_first"`): renders shot[0] with the Fast
tier (e.g. `seedance_2_0_fast`), evaluates consistency + brand_safety against
the Bible, and aborts before spending Standard-tier credits if the score is
below `cost_gate_threshold`. Failed jobs return `cost_gate.suggestions[]` so
the user knows what to fix.

### `POST /api/v1/director/plan-and-render`

One-shot escape hatch — build a plan AND render it without Human-in-the-Loop review.
Useful for automated batches / CLI jobs. Returns the same shape as `/generate`.

```jsonc
{
  "plan_request": { ...same shape as POST /plan body... },
  "audio_plan": null,
  "use_llm_scene_gen": true
}
```

Job state machine: `pending → planning → rendering → assembling → done`.

### `POST /api/v1/director/refine`

Re-render ONE shot from an approved plan (Evaluation-driven flow). Use when the
Evaluation Layer (or the user) flagged a specific shot as low-quality —
regenerate just that clip instead of the whole video.

```jsonc
// Request
{
  "plan": { ...full DirectorPlan with the shot to refine... },
  "shot_id": "S3",
  "reference_images": [ ... ],
  "settings": { ... },
  // Optional: pass the chain anchor frame from the original render so the
  // refined clip drops back into the timeline without identity drift.
  "previous_last_frame_url": "https://...",
  // Optional: nudge the shot before re-render (shallow-merged into plan.shot_list[i])
  "shot_overrides": {
    "visual": { "action": "now smiles softly" },
    "duration_s": 4
  }
}

// Response — same polling shape, status: pending → rendering → uploading → done
{
  "job_id": "refine_xxxxx",
  "polling_url": "/api/v1/director/jobs/refine_xxxxx",
  "shot_id": "S3",
  "estimated_duration_s": 4,
  "mode": "refine"
}
```

Cost: 1 shot × per-second model price (vs. full plan re-render). The refined
clip is uploaded to R2 (or `file://` fallback) at `refine/{job_id}/{shot_id}.mp4`.

### `GET /api/v1/director/jobs/{job_id}` · `POST .../cancel`

Poll status. Field: `status` (`pending|rendering|assembling|done|failed|cancelled`), `progress` 0-100, `current_step`, `output_path` (when done), `error_message`.

---

## 6. Legacy endpoints (scheduled removal)

`backend/api/routes/jobs.py` + `workers/render_pipeline.py` còn mount tại `/api/v1/jobs/*` để không phá tích hợp client cũ. Banner LEGACY rõ ràng trong source. Chỉ chấp nhận **Director-approved input** (`approved_shots` + `approved_character_sheet` required). Sẽ xoá sau khi mọi caller chuyển sang `/api/v1/director/generate`.

---

## 6.5. Scene Generation Agent (Layer 2)

`backend/agent/scene_generation_agent.py` produces one `SceneRenderJob` per shot
from the Continuity Bible. It is invoked **lazily per shot** by
`workers/video_worker.py` while the chain walks — so the LLM sees the live
`last_frame_url` and the active model key (ref vs i2v variant) for that step.

```python
job = generate_scene(
    bible=plan.continuity_bible,
    shot=plan.shot_list[i],
    model_key="seedance_2_0_ref" or "seedance_2_0_i2v",
    reference_images=all_uploaded_refs,
    last_frame_url=prev_shot_last_frame or None,
    llm_mode=True,                # 1 LLM call per shot (default)
    resolution="720p",
    is_last_shot=(i == len(shots) - 1),
)
atlas_client.generate_video(**job.to_atlas_kwargs())
```

Behaviour:

1. **LLM call** against `system_prompts/scene.md`. Output validated by
   `_SceneLLMOutput` Pydantic schema (prompt + negative_prompt + reference_image_indices
   + render_mode + chain_input_url + model_params). On JSON parse fail or schema
   mismatch, the call is retried ONCE with a lower temperature (0.55 → 0.35).
   If both attempts fail, falls back silently to the deterministic builder.
2. **Universal Reference binding** via `continuity_manager.references_for_shot()`.
   On `i2v_chain` mode the agent filters out `character_anchor` / `product_*`
   refs (chain frame already carries identity) and keeps only style / environment
   / brand_asset refs — preventing double-binding drift.
3. **Model-aware prompt format** via `MODEL_FORMAT_HINTS`:
   `seedance_2_0_*` → `multi_shot_inline`; `seedance_v15_pro_i2v` → `time_coded`;
   `wan_2_7_i2v` / `*_i2v` → `i2v_motion` (motion verbs only); `vidu_q3_*` →
   `single_descriptive`.
4. **Prompt length cap** per format — `multi_shot_inline` ≤ 1200 chars; others ≤
   600–800. Overflow gets safely truncated with an ellipsis.
5. **Negative prompt**: defaults to `continuity_manager.build_negative_prompt(bible)`
   (must_avoid + brand_safety + quality negatives). LLM may supply a tighter
   override.
6. **`return_last_frame`** is automatically set to `False` on the last shot, so
   we don't waste a frame extraction for the final clip.

The deterministic builder (`llm_mode=False`) is a pure function — same Bible +
Shot always produces the same prompt. Use it in cost-sensitive batches or for
unit tests of the renderer chain.

---

## 7. System prompts — iterate workflow

Mọi prompt sống trong `system_prompts/*.md`. Edit → reload server.

| File | Layer | Constraints chính |
|---|---|---|
| `director.md` | 1 | MUST output JSON `DirectorPlan` schema, no fences. Tag every reference. Time-budget shots = `tech_config.duration_s`. |
| `scene.md` | 2 | Embed `face_signature` + `visual_style`. Model-aware format. Negative prompt mandatory. |
| `evaluation.md` | Eval | Strict scoring 0-10 across 5 dims + `red_flags` block approval. |

Loader: `system_prompts.load("director")` (lru_cache). KHÔNG import từ `.py` khác.

---

## 8. Universal Reference + Reference Chaining

### Universal Reference

User upload N ảnh (max 12). Director tag mỗi ảnh:

```jsonc
{
  "index": 0,
  "url": "https://...",
  "role": "character_anchor | product_hero | product_detail | style_reference | environment | brand_asset | secondary_character | unknown",
  "apply_to_shots": ["S1", "S3", "S5"],
  "notes": "..."
}
```

Scene Gen lấy refs cho 1 shot qua `continuity_manager.references_for_shot(bible, shot)`:
- Union: explicit `shot.continuity.reference_indices` + universal `apply_to_shots` binding
- Sort priority: character_anchor → secondary_character → product_hero → product_detail → brand_asset → style_reference → environment → unknown

### Reference Chaining

Cho video dài / multi-shot consistency:

1. Director set `shot.continuity.previous_shot_id` = shot_id liền trước (auto-applied bởi `continuity_manager.auto_chain_shots()` nếu cùng character + cùng purpose family)
2. Render loop ở shot N (N>0): nếu `previous_shot_id` đã set AND prev shot trả `last_frame_url` → swap sang i2v variant của model + pass `image=last_frame_url`
3. Identity (face / outfit / lighting) inherit gần như 100% từ shot trước

Reset chain: leave `previous_shot_id=null` khi muốn cắt cảnh (location change / time jump / POV switch).

---

## 9. Color consistency pass

Sau khi `AssembleWorker.assemble()` concat clips, `_apply_color_consistency()` chạy 1 FFmpeg pass cuối map `bible.visual_style.color_grading` (string mô tả) → deterministic `eq`/`curves` filter chain:

| Bible color_grading chứa | Filter chain |
|---|---|
| `teal`, `orange` | `curves=preset=increase_contrast,eq=saturation=1.10:contrast=1.05` |
| `warm`, `filmic`, `golden` | `eq=gamma_r=1.06:gamma_b=0.95:saturation=1.05,curves=preset=lighter` |
| `pastel`, `airy`, `soft` | `eq=brightness=0.02:saturation=0.90:contrast=0.95` |
| `noir`, `desaturated`, `moody` | `eq=saturation=0.55:contrast=1.10` |
| `cinematic`, `35mm` | `curves=preset=increase_contrast,eq=saturation=1.05` |
| (anything else) | `eq=saturation=1.03` |

Mở rộng dễ: edit `workers/video_worker.py::_apply_color_consistency`.

---

## 10. Cost ballpark per plan-then-render

| Component | Cost |
|---|---|
| Director plan (1 LLM, ~2K out tokens) | $0.03-0.06 |
| Vision pass refs (Qwen3-VL, optional) | $0.01-0.02 |
| Evaluation (1 LLM analyzer) | $0.005 |
| Scene Gen LLM per shot × 8-15 | $0.05-0.15 (skip with `use_llm_scene_gen=false`) |
| Storyboard image gen (optional, $0.04/frame) | $0.30-0.60 |
| Video render (Seedance 2.0 @ 15s × $0.096) | ~$1.44 |
| TTS dialogue_vo | ~$0.01 |
| **Total** | **$1.5–$2.5 / 15s video** |

---

## 11. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Director LLM call failed: ...` | `ATLASCLOUD_LLM_API_KEY` thiếu hoặc 402 | Nạp wallet hoặc set `ANTHROPIC_API_KEY` để fallback |
| `Bible schema invalid: ...` | LLM output JSON sai schema | Inspect `[DirectorAgent] raw head` log; thường do quên cần field; retry |
| `Bible validation warnings: duration sum 17s lệch target 15s` | Director time-budget shots lệch | Tolerable ±2s; nếu lớn hơn → re-plan |
| Shot quên `previous_shot_id` → identity drift | LLM bỏ qua chain hint | `continuity_manager.auto_chain_shots()` auto fill, hoặc edit shot ở UI |
| `last_frame_url` null → chain shot fallback ref | AtlasCloud model không trả last_frame | Check `model_specs.py` model có support `return_last_frame=true` không |
| Color consistency pass fail | FFmpeg filter sai trên ungraded clip | Pass skip + log warning, MP4 vẫn xuất (chỉ thiếu grading) |

---

## 11.5. Cloudflare R2 storage

`backend/vendors/r2_storage.py` uploads the final MP4 (and refined shots) to R2
via boto3 (S3-compatible API). Configured via these env vars:

```
R2_ACCOUNT_ID=xxxxxxxx
R2_ACCESS_KEY_ID=xxxxxxxx
R2_SECRET_ACCESS_KEY=xxxxxxxx
R2_BUCKET_NAME=ugc-vietnam-output
R2_PUBLIC_URL=https://cdn.yourdomain.com   # optional custom domain
```

**Graceful fallback**: if any required var is missing, the worker returns a
`file://` URL pointing at the local clip — local dev works without Cloudflare.
Upload errors are caught and also fall back to `file://` (so a flaky R2 won't
kill the whole render).

The R2 object key is `video/{job_id}/final.mp4` for full renders and
`refine/{job_id}/{shot_id}.mp4` for single-shot refines. Set the bucket public
or front it with a Cloudflare Worker / custom domain to serve clips to users.

---

## 11.6. Reference Zones (v2.1 §5)

The frontend `components/studio/ReferenceZones.tsx` splits the single
`reference_images[]` upload into THREE buckets:

| Zone | Default role tag | What goes here |
|---|---|---|
| **Character** | `primary_subject` | Face / outfit anchor — applied to most shots |
| **Product / Props** | `product_hero` | The product or main prop being showcased |
| **Storyboard** | `style_reference` | Pre-composed frames for composition / style |

Frontend sends both `reference_images[]` (flat URL list) AND
`reference_role_hints[]` (parallel role list). The Director Agent uses the
hints to **skip the vision-pass classification** — saves an LLM call and
guarantees the role tag the user intended.

If `reference_role_hints` is omitted (or all-null), the Director falls back to
the vision-pass LLM (`agent.director_agent._vision_scan_refs`).

---

## 12. Migration notes (V2 → V3)

Đã xoá:

- `backend/templates/` (30 skeleton JSON)
- `backend/agent/personas/` (7 personas linear: director, copywriter, critic, …)
- `backend/agent/director_brain.py` (orchestrator linear)
- `backend/agent/proposal_builder.py`, `video_ref_analyzer.py`, `storyboard_keyframer.py`
- `backend/prompts/analyzer_system.md` + `generator_system.md`
- Routes `propose.py`, `storyboard.py`, `templates.py`, `enhance.py`

Đã thêm:

- `backend/agent/{director_agent,continuity_manager,scene_generation_agent,evaluation_layer,schemas,trend_cache}.py`
- `backend/system_prompts/{director,scene,evaluation}.md`
- `backend/api/routes/director.py`
- `backend/workers/video_worker.py`

Refactored:

- `backend/vendors/atlascloud.py` — `generate_video()` returns `last_frame_url`; new `generate_video_chain()` helper
- `backend/api/main.py` — V3 router mounted first; legacy `/jobs/*` still served
- `backend/api/routes/jobs.py` — banner LEGACY, only Director-approved input accepted
