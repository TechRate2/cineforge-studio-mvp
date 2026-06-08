import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const studioPage = path.join(root, "app", "studio", "page.tsx");
const source = fs.readFileSync(studioPage, "utf8");
const workflowFiles = [
  studioPage,
  path.join(root, "components", "studio", "SettingsBar.tsx"),
  path.join(root, "components", "studio", "ChatBriefComposer.tsx"),
  path.join(root, "components", "studio", "SmartReferenceTray.tsx"),
  path.join(root, "components", "studio", "ReferenceAssetCard.tsx"),
  path.join(root, "components", "studio", "ReferenceIntelligencePanel.tsx"),
  path.join(root, "components", "studio", "AgentPlanPreview.tsx"),
  path.join(root, "components", "studio", "StoryboardPreview.tsx"),
  path.join(root, "components", "studio", "VoiceAudioPlanPreview.tsx"),
  path.join(root, "components", "studio", "RenderTimeline.tsx"),
  path.join(root, "components", "studio", "StudioLanguageToggle.tsx"),
  path.join(root, "components", "studio", "studio-i18n.ts"),
];
const workflowSource = workflowFiles
  .filter((file) => fs.existsSync(file))
  .map((file) => fs.readFileSync(file, "utf8"))
  .join("\n");
const agentPlanPreviewSource = fs.readFileSync(path.join(root, "components", "studio", "AgentPlanPreview.tsx"), "utf8");
const renderTimelineSource = fs.readFileSync(path.join(root, "components", "studio", "RenderTimeline.tsx"), "utf8");
const jobResultModalSource = fs.readFileSync(path.join(root, "components", "studio", "JobResultModal.tsx"), "utf8");
const deliverableUrlSource = fs.readFileSync(path.join(root, "lib", "studio", "deliverable-url.ts"), "utf8");
const projectHistorySource = fs.readFileSync(path.join(root, "lib", "studio", "use-project-history.ts"), "utf8");
const recentGenerationsSource = fs.readFileSync(path.join(root, "components", "studio", "RecentGenerations.tsx"), "utf8");
const historyPageSource = fs.readFileSync(path.join(root, "app", "studio", "history", "page.tsx"), "utf8");
const shellFiles = [
  path.join(root, "app", "studio", "layout.tsx"),
  path.join(root, "app", "studio", "history", "page.tsx"),
  path.join(root, "app", "studio", "library", "page.tsx"),
  path.join(root, "components", "studio", "StudioTopbar.tsx"),
  path.join(root, "components", "studio", "StudioRail.tsx"),
  path.join(root, "components", "studio", "JobResultModal.tsx"),
  path.join(root, "components", "studio", "RecentGenerations.tsx"),
  path.join(root, "lib", "studio", "use-project-history.ts"),
];
const shellSource = shellFiles
  .filter((file) => fs.existsSync(file))
  .map((file) => fs.readFileSync(file, "utf8"))
  .join("\n");
const redirectOnlyRoutes = [
  path.join(root, "app", "studio", "text-to-video", "page.tsx"),
  path.join(root, "app", "studio", "image-to-video", "page.tsx"),
  path.join(root, "app", "studio", "voice", "page.tsx"),
  path.join(root, "app", "studio", "admin", "page.tsx"),
  path.join(root, "app", "studio", "docs", "page.tsx"),
];
const appApiSource = collectFiles(path.join(root, "app", "api"))
  .filter((file) => file.endsWith(".ts") || file.endsWith(".tsx"))
  .map((file) => fs.readFileSync(file, "utf8"))
  .join("\n");
const envExampleSource = fs.readFileSync(path.join(root, ".env.example"), "utf8");
const rootReadmeSource = fs.readFileSync(path.join(root, "README.md"), "utf8");
const backendReadmeSource = fs.readFileSync(path.join(root, "backend", "README.md"), "utf8");
const backendMainSource = fs.readFileSync(path.join(root, "backend", "api", "main.py"), "utf8");

const forbidden = [
  {
    pattern: /from ['"]@\/components\/studio\/PromptCardV2['"]/,
    reason: "PromptCardV2 is the old manual Video Agent card.",
  },
  {
    pattern: /from ['"]@\/components\/studio\/ReferenceZones['"]/,
    reason: "ReferenceZones is the old manual reference uploader.",
  },
  {
    pattern: /from ['"]@\/components\/studio\/SettingsPanel['"]/,
    reason: "SettingsPanel exposes manual model/aspect/audio/shot controls.",
  },
  {
    pattern: /from ['"]@\/components\/studio\/DirectorPlanModal['"]/,
    reason: "DirectorPlanModal belongs to the old manual director flow.",
  },
  {
    pattern: /from ['"]@\/components\/studio\/CostConfirmDialog['"]/,
    reason: "CostConfirmDialog belongs to manual price confirmation UI.",
  },
  {
    pattern: /from ['"]@\/lib\/studio\/use-enhance-brief['"]/,
    reason: "Enhance Brief is a manual prompt-improvement action.",
  },
  {
    pattern: /from ['"]@\/lib\/studio\/use-director-plan['"]/,
    reason: "useDirectorPlan is the old manual plan generation flow.",
  },
  {
    pattern: /\bVideo Agent\b/,
    reason: "Visible Video Agent copy should not return to /studio.",
  },
  {
    pattern: /\bEnhance\b/,
    reason: "Visible Enhance action should not return to autonomous-only /studio.",
  },
  {
    pattern: /\bmasterBoardEnabled\b|\bnumShots\b|\baudioMode\b/,
    reason: "Manual generation state should not return to autonomous-only /studio.",
  },
  {
    pattern: /\/api\/v1\/director\/autonomous\/(?:production-audit|operator-brief|top-tier-completion-gate|benchmarks\/plan)/,
    reason: "Internal audit/operator feeds must stay out of the user-facing Studio page.",
  },
  {
    pattern: /estimated_cost_usd|cost_estimate_usd|cost_actual_usd|estimated_vendor_cost|balance_usd|balance_credits/,
    reason: "Studio page must not expose internal vendor/cost accounting.",
  },
  {
    pattern: /const conversationMessages = useMemo\([\s\S]{0,180}=> chatMessages[\s\S]{0,180}\.filter\(\(message\) => message\.role === ['"]user['"]\)/,
    reason: "Conversational preflight must preserve assistant turns, not only user messages.",
  },
  {
    pattern: /slice\(-8\)|slice\(-10\)/,
    reason: "Studio chat history should use CHAT_HISTORY_LIMIT so long preflight context is preserved consistently.",
  },
  {
    pattern: /graph executor|production_graph|production graph|scene_memory_pack|CINEJELLY_ENABLE_GRAPH_LONG_FORM/i,
    reason: "Studio page must not expose internal long-form execution terms.",
  },
];

const failures = forbidden
  .filter((item) => item.pattern.test(workflowSource))
  .map((item) => `- ${item.reason}`);

const requiredStudioContracts = [
  {
    pattern: /approvedInputKey/,
    reason: "Studio render gating must keep an approved input snapshot.",
  },
  {
    pattern: /currentInputKey/,
    reason: "Studio render gating must compute a current input fingerprint.",
  },
  {
    pattern: /approvedInputKey\s*===\s*currentInputKey/,
    reason: "Render must stay disabled when the approved plan no longer matches the current inputs.",
  },
  {
    pattern: /approved_(?:plan|Plan)\?\.source_hash/,
    reason: "Render payload must be tied to the backend approved plan hash.",
  },
  {
    pattern: /intent\?:\s*['"]idea['"]\s*\|\s*['"]revision['"]/,
    reason: "Chat messages must preserve whether a turn is a new idea or a plan revision.",
  },
  {
    pattern: /message\.intent\s*\?\?\s*['"]idea['"]/,
    reason: "Conversation history fingerprints must include chat turn intent.",
  },
  {
    pattern: /Resolve blocked/,
    reason: "Blocked preflight checks must be visible before approval.",
  },
  {
    pattern: /ChatBriefComposer|Ý tưởng video|Video idea/,
    reason: "Studio must keep the chat-first preflight agent as the primary creation surface.",
  },
  {
    pattern: /Phê duyệt render|Approve render/,
    reason: "Studio must require plan approval before rendering.",
  },
  {
    pattern: /Bắt đầu render|Start render/,
    reason: "Studio must keep the autonomous render command visible as the only generation action.",
  },
  {
    pattern: /conversation_messages:\s*conversationMessages/,
    reason: "Preflight requests must include structured conversation context.",
  },
  {
    pattern: /approved_plan_id:\s*conversationalPreflight\?\.approved_plan\?\.id/,
    reason: "Render requests must include the approved plan id.",
  },
  {
    pattern: /approved_plan_source_hash:\s*conversationalPreflight\?\.approved_plan\?\.source_hash/,
    reason: "Render requests must include the approved plan source hash.",
  },
  {
    pattern: /approved_plan_source_length:\s*conversationalPreflight\?\.approved_plan\?\.source_length/,
    reason: "Render requests must include the approved plan source length.",
  },
  {
    pattern: /StoryboardPreview|Storyboard/,
    reason: "Studio must keep a no-paid scene preview workbench before final render.",
  },
  {
    pattern: /buildStudioPreviewScenes/,
    reason: "Studio must compile preflight output into previewable scene cards.",
  },
  {
    pattern: /AgentPlanPreview|Kế hoạch của Agent|Agent plan/,
    reason: "Studio must allow users to save/review scene drafts without starting render.",
  },
  {
    pattern: /onApprove=\{handleApprovePreflight\}|Phê duyệt render|Approve render/,
    reason: "Studio must separate draft approval from the final paid render click.",
  },
  {
    pattern: /RenderTimeline|Render blockers|Chặn render/,
    reason: "Studio must show exact blockers before the final render button.",
  },
  {
    pattern: /SmartReferenceTray|ReferenceIntelligencePanel|reference_intelligence|hard_failures/,
    reason: "Studio must surface Reference Intelligence and dry-run hard failures from real backend data.",
  },
  {
    pattern: /latestDirectorJob|onJobUpdate|render_execution|longform_render_execution/,
    reason: "Studio RenderTimeline must consume real polled job results for QA, repair, assembly, and delivery states.",
  },
  {
    pattern: /deliveryStatusFromJob|deliverableUrlFromJob|final_delivery_qa/,
    reason: "Studio delivery state must require a real deliverable URL or delivery QA signal, not just a local output path.",
  },
  {
    pattern: /benchmarkStatusFromEvidence|promotion_ready|missing_reasons/,
    reason: "Studio benchmark state must distinguish promotion-ready evidence from incomplete draft evidence.",
  },
  {
    pattern: /Sẵn sàng|Cần xem lại|Bị chặn|Kiểm tra trước render|Tự sửa lỗi|Video hoàn tất/,
    reason: "Studio must include Vietnamese-first labels for the chat-first render flow.",
  },
  {
    pattern: /generationBlockedByResponsibleGate/,
    reason: "Generate gating must preserve responsible-content blocking.",
  },
  {
    pattern: /generationNeedsClarification/,
    reason: "Generate gating must preserve niche-clarification blocking.",
  },
  {
    pattern: /preflightHasBlockedChecks/,
    reason: "Generate gating must preserve blocked preflight checklist handling.",
  },
];

for (const item of requiredStudioContracts) {
  if (!item.pattern.test(workflowSource)) failures.push(`- ${item.reason}`);
}

if (/use_vision_llm_for_tagging:\s*referenceImageUrls\.length\s*>\s*0/.test(source)) {
  failures.push("- Normal Studio dry-run/render must not auto-enable vision LLM role tagging; keep it behind explicit Deep Analyze opt-in.");
}
if (!/use_vision_llm_for_tagging:\s*false/.test(source)) {
  failures.push("- Normal Studio dry-run/render must keep vision role tagging disabled by default.");
}
if (!/allow_vision_llm:\s*referenceImageUrls\.length\s*>\s*0/.test(source)) {
  failures.push("- Deep Analyze should remain the explicit vision LLM opt-in lane for reference role suggestions.");
}
if (/NEXT_PUBLIC_API_BASE/.test(appApiSource) || /localhost:8000/.test(appApiSource)) {
  failures.push("- Next API proxy routes must use server-side BACKEND_URL with the backend dev default 127.0.0.1:8001.");
}
if (!/BACKEND_URL=http:\/\/127\.0\.0\.1:8001/.test(envExampleSource) || !/APP_PORT=8001/.test(envExampleSource)) {
  failures.push("- .env.example must align with npm run dev:backend and Next API proxy default port 8001.");
}
if (/--port 800[02]|127\.0\.0\.1:8002|localhost:8000\/docs/.test(rootReadmeSource + "\n" + backendReadmeSource + "\n" + backendMainSource)) {
  failures.push("- README/backend startup docs must use backend dev port 8001, not stale 8000/8002 values.");
}

const outputUrlFunction = renderTimelineSource.match(/function deliverableUrlFromJob[\s\S]*?function assemblyStatusFromJob/);
if (!outputUrlFunction || /output_path/.test(outputUrlFunction[0])) {
  failures.push("- RenderTimeline deliverableUrlFromJob must not treat local output_path as a delivery-ready URL.");
}
if (!/new URL\(text\)/.test(deliverableUrlSource) || !/localhost/.test(deliverableUrlSource) || !/127/.test(deliverableUrlSource)) {
  failures.push("- Shared deliverableUrl helper must parse URLs and reject localhost/loopback delivery evidence.");
}
if (!/protocol !== ['"]http:['"] && protocol !== ['"]https:['"]/.test(deliverableUrlSource)) {
  failures.push("- Shared deliverableUrl helper must reject file://, local paths, and non-HTTP(S) delivery evidence.");
}
if (!/from ['"]@\/lib\/studio\/deliverable-url['"]/.test(renderTimelineSource)) {
  failures.push("- RenderTimeline must use the shared deliverableUrl helper.");
}
if (!/from ['"]@\/lib\/studio\/deliverable-url['"]/.test(jobResultModalSource)) {
  failures.push("- JobResultModal must use the shared deliverableUrl helper.");
}
if (!/const videoUrl = deliverableUrl\(/.test(jobResultModalSource)) {
  failures.push("- JobResultModal must sanitize final video URLs with deliverableUrl before rendering video/download controls.");
}
if (!/isDelivered/.test(jobResultModalSource) || !/doneWithoutDelivery/.test(jobResultModalSource)) {
  failures.push("- JobResultModal must distinguish a delivered video from a done job that is still missing a valid public delivery URL.");
}
if (!/deliveryQaAccepted/.test(jobResultModalSource) || !/deliveredNeedsReview/.test(jobResultModalSource)) {
  failures.push("- JobResultModal must distinguish a delivery-ready video from a preview URL whose final delivery QA is pending or failed.");
}
if (!/deliveryQaWarning/.test(jobResultModalSource) || !/&& !deliveryQaWarning/.test(jobResultModalSource)) {
  failures.push("- JobResultModal must keep delivery QA warnings in review instead of treating them as download-ready.");
}
if (/deliveryQaAccepted[\s\S]{0,220}ready['"][,\]]/.test(jobResultModalSource) || /deliveryQaAccepted[\s\S]{0,220}completed['"][,\]]/.test(jobResultModalSource)) {
  failures.push("- JobResultModal must not treat generic ready/completed strings as accepted final delivery QA.");
}
if (!/Approved feedback is locked until final delivery QA passes without warnings/.test(jobResultModalSource)) {
  failures.push("- JobResultModal feedback must tell users approved evidence is locked until delivery QA passes cleanly.");
}
if (!/disabled = item\.id === ['"]approved['"] && !deliveryReady/.test(jobResultModalSource)) {
  failures.push("- JobResultModal feedback must disable Approved when delivery QA has not passed cleanly.");
}
if (!/rating === ['"]approved['"]\s*\?\s*\[['"]good['"]\]/.test(jobResultModalSource)) {
  failures.push("- JobResultModal feedback must send only the good tag for approved positive feedback.");
}
if (!/if \(rating === ['"]approved['"]\)[\s\S]{0,80}setRating\(['"]needs_work['"]\)/.test(jobResultModalSource)) {
  failures.push("- JobResultModal feedback must switch away from Approved when a problem tag is selected.");
}
if (/title=\{isDone \? ['"]Video ready['"]/.test(jobResultModalSource)) {
  failures.push("- JobResultModal must not label a job as Video ready from status=done alone.");
}
if (/title=\{isDelivered \? ['"]Video ready['"]/.test(jobResultModalSource)) {
  failures.push("- JobResultModal must not label a job as Video ready from a URL alone; final delivery QA must be accepted.");
}
if (!/Download MP4/.test(jobResultModalSource) || !/deliveryReady &&/.test(jobResultModalSource)) {
  failures.push("- JobResultModal must only show the MP4 download action after delivery QA is accepted.");
}
if (!/deliverableUrlOrNull/.test(projectHistorySource) || !/sanitizeHistoryItem/.test(projectHistorySource)) {
  failures.push("- Project history must sanitize output_url to HTTP(S) before RecentGenerations or History preview can render it.");
}
if (!/hasDeliverable/.test(recentGenerationsSource)) {
  failures.push("- RecentGenerations must distinguish completed jobs with real delivery URLs from done jobs still missing public delivery.");
}
if (!/doneWithoutDelivery/.test(historyPageSource)) {
  failures.push("- History page must show done-without-delivery as pending instead of preview-ready.");
}
if (/stepStatus\(Boolean\(benchmarkEvidence\)\)/.test(renderTimelineSource)) {
  failures.push("- RenderTimeline must not mark benchmark evidence ready just because a JSON evidence pack exists.");
}
if (!/feedback_integrity_not_safe/.test(renderTimelineSource) || !/launch evidence/.test(renderTimelineSource)) {
  failures.push("- RenderTimeline must translate feedback_integrity_not_safe into a readable benchmark blocker.");
}
if (!/final delivery QA is not attached yet/.test(renderTimelineSource)) {
  failures.push("- RenderTimeline must not mark delivery ready from URL alone when final delivery QA is missing.");
}
if (!/qaStatus === ['"]warning['"]/.test(renderTimelineSource)) {
  failures.push("- RenderTimeline must keep final delivery QA warning status in review instead of ready.");
}
if (/ready['"],\s*['"]completed/.test(renderTimelineSource)) {
  failures.push("- RenderTimeline must not treat generic ready/completed strings as accepted final delivery QA.");
}
if (/estimateSceneSpendUsd|spendUsd:/.test(workflowSource)) {
  failures.push("- Studio must not fabricate frontend USD cost estimates; use backend dry-run cost_estimate or show pending.");
}
if (!/buildSpendPreview/.test(workflowSource) || !/cost_estimate/.test(workflowSource)) {
  failures.push("- Studio spend preview must be derived from backend dry-run cost_estimate.");
}
if (!/source !== ['"]backend_dry_run['"]/.test(agentPlanPreviewSource)) {
  failures.push("- AgentPlanPreview must show pending when backend dry-run cost_estimate is unavailable.");
}
const mojibakePattern = /(?:Ã[\u0080-\u00bf]|Ä[\u0080-\u00bf]|Å[\u0080-\u00bf]|Æ[\u0080-\u00bf]|áº|á»)/;
if (mojibakePattern.test(workflowSource)) {
  failures.push("- Chat-first Studio components must not contain mojibake/encoding-corrupted Vietnamese copy.");
}

const shellForbidden = [
  {
    pattern: /Provider status|\bproviders\b|key_masked|useAdminCredits|AtlasCloud LLM|No key/,
    reason: "Provider/API-key status must stay out of the user-facing Studio shell.",
  },
  {
    pattern: /Internal model router|benchmark-evidence-pack|production-report|production-graph|Cost:|cost_actual_usd|Provider|API key/,
    reason: "JobResultModal must stay user-facing and hide internal operator/provider/cost diagnostics.",
  },
  {
    pattern: /cost_estimate_usd|cost_actual_usd|estimated_vendor_cost|balance_usd|balance_credits/,
    reason: "User-facing Studio surfaces must not expose internal vendor/cost accounting.",
  },
  {
    pattern: /(?:\u00c3[\u0080-\u00bf]|\u00c4[\u0080-\u00bf]|\u00c5[\u0080-\u00bf]|\u00c6[\u0080-\u00bf]|\u00e1\u00ba|\u00e1\u00bb|\ufffd)/,
    reason: "User-facing Studio copy must not contain mojibake.",
  },
  {
    pattern: /\/studio\/(?:text-to-video|image-to-video|voice|admin|docs)/,
    reason: "Manual playground/admin/docs links must not appear in the Studio shell.",
  },
];

for (const item of shellForbidden) {
  if (item.pattern.test(shellSource)) failures.push(`- ${item.reason}`);
}

for (const route of redirectOnlyRoutes) {
  if (!fs.existsSync(route)) {
    failures.push(`- Missing redirect route ${path.relative(root, route)}.`);
    continue;
  }
  const routeSource = fs.readFileSync(route, "utf8");
  if (!/from ['"]next\/navigation['"]/.test(routeSource) || !/redirect\(['"]\/studio['"]\)/.test(routeSource)) {
    failures.push(`- ${path.relative(root, route)} must redirect to /studio, not expose a manual UI.`);
  }
}

if (failures.length > 0) {
  console.error("Autonomous UI guard failed for app/studio/page.tsx:");
  console.error(failures.join("\n"));
  process.exit(1);
}

console.log("PASS autonomous UI guard: /studio chat-first, safety, delivery, benchmark, and copy contracts are intact.");

function collectFiles(dir) {
  if (!fs.existsSync(dir)) return [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectFiles(fullPath));
    } else if (entry.isFile()) {
      files.push(fullPath);
    }
  }
  return files;
}
