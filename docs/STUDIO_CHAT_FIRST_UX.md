# Studio Chat First UX

## Product Shape

The main `/studio` screen should feel like a Vietnamese-first AI video agent: the user writes an idea, uploads optional references, reviews what the agent understood, approves a dry-run, then renders with visible QA, repair, delivery, and benchmark status when those backend signals exist.

The UI is organized into four primary zones:

1. `ChatBriefComposer`: natural Vietnamese or English idea entry, conversation history, starter prompts, product URL extraction, and optional deep analysis.
2. `SmartReferenceTray`: upload images, video, and audio; show role, confidence, locked state, readiness, warnings, and blockers.
3. `AgentPlanPreview`: simple producer/director plan with objective, niche, market, platform, concept, script, storyboard, voice/audio plan, prompt strategy, cost, and risk warnings.
4. `RenderTimeline`: readable render path from idea to delivery, including dry-run, ApprovalLock, render, QA, repair, final assembly, delivery, and benchmark evidence.

## Data Rules

- All UI values must come from typed frontend state, backend API payloads, or local upload state.
- Missing backend fields must render as `pending`, `unknown`, or `not available yet`, never as completed.
- `RenderDryRunReport.reference_intelligence`, `warnings`, and `hard_failures` are the source of truth for backend reference readiness after dry-run.
- Normal dry-run/render must submit `use_vision_llm_for_tagging=false`; Deep Analyze is the explicit opt-in lane for vision role suggestions, and those suggestions still require user/backend gate review.
- Prompt preview and negative prompt are advanced details. They are useful for operators and advanced users, but should not dominate the main flow.
- Benchmark summaries can be shown only when real benchmark evidence exists. A draft evidence pack is not benchmark success; the Studio timeline marks it ready only when the backend validator reports `promotion_ready: true` and feedback integrity remains promotion-safe. Raw benchmark rows remain admin/operator-only.
- Main UI cost estimates come only from backend dry-run `cost_estimate`. If the backend has not returned cost evidence yet, Studio shows pending instead of calculating a frontend USD estimate.

## Vietnamese First Copy

Minimum labels used by the chat-first Studio:

- Ý tưởng video
- Tải ảnh/video/âm thanh tham chiếu
- Tham chiếu thông minh
- Sản phẩm chính
- Nhân vật chính
- Phong cách tham khảo
- Chuyển động camera
- Logo/Thương hiệu
- Giọng đọc
- Nhạc nền
- Sẵn sàng
- Cần xem lại
- Bị chặn
- Kịch bản
- Storyboard
- Chiến lược prompt
- Kiểm tra trước render
- Phê duyệt render
- Bắt đầu render
- Đang kiểm tra chất lượng
- Tự sửa lỗi
- Video hoàn tất

## Honest Timeline Mapping

- Idea understood: complete when the user has a brief and preflight has returned.
- References checked: complete, review, or blocked only after dry-run Reference Intelligence exists.
- Script, storyboard, and prompt compiled: complete only when preflight scenes or dry-run shot payloads exist.
- Dry-run ready: complete only when `render_dry_run_report` exists.
- Approval locked: complete only when the frontend approved input snapshot still matches the current input and backend approved plan fields are attached.
- Rendering: active while the render request is in flight.
- QA, auto repair, final assembly, and delivery: update from the real polled job result when `render_execution`, `longform_render_execution`, `assembly_result`, or deliverable output URL fields exist. A local `output_path` or `file://` URL is not normal delivery evidence; show it as pending or dev-only unless backend delivery QA explicitly reports a development fallback. `JobResultModal`, Recent Generations, History, and `RenderTimeline` must only show video preview states when a valid public or presigned HTTP(S) deliverable URL is present. Download-ready / video-complete states require final delivery QA to pass with no warnings/errors. Delivery QA `warn`, missing QA, or a URL without delivery QA stays in review/pending.
- Benchmark: update only when the real job benchmark evidence-pack endpoint returns an evidence payload; show draft packs as review-needed until `evidence_validation_preview.promotion_ready` is true. The endpoint also folds feedback integrity into the validation preview, so older/operator-written positive feedback that lacks clean delivery QA keeps the pack out of launch-ready status.
- Timeline copy maps backend benchmark blockers such as `feedback_integrity_not_safe` into readable review reasons. Raw blocker IDs can remain in advanced/operator payloads, but the main timeline should explain why launch evidence is not usable.
- Output feedback: users can always record `needs_work`/`bad` feedback for repair learning when a real preview URL exists. `Approved`/`good` feedback and download-ready evidence stay locked until final delivery QA passes with no warnings/errors. Positive feedback must not include issue tags; selecting a problem tag moves the review back to `needs_work`. The feedback evidence endpoint reports integrity issues for older or externally written entries that violate these rules. Warning or pending delivery QA must not create positive benchmark-supporting evidence.

## Risks And Next Steps

- Job completion polling currently needs stronger typed exposure of QA reports, repair history, final assembly, delivery QA, and benchmark evidence in the main Studio state.
- Reference Intelligence V2 should add real multimodal analyzers before the product claims visual/audio understanding.
- Real launch readiness still requires paid vendor/R2 smoke and complete benchmark evidence.
