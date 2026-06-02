import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const studioPage = path.join(root, "app", "studio", "page.tsx");
const source = fs.readFileSync(studioPage, "utf8");
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
  .filter((item) => item.pattern.test(source))
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
    pattern: /Resolve blocked checks first/,
    reason: "Blocked preflight checks must be visible before approval.",
  },
  {
    pattern: /Conversational Preflight Agent/,
    reason: "Studio must keep the chat-first preflight agent as the primary creation surface.",
  },
  {
    pattern: /Approve script and storyboard/,
    reason: "Studio must require plan approval before rendering.",
  },
  {
    pattern: /Generate Full Video \(Autonomous\)/,
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
    pattern: /ScenePreviewWorkbench/,
    reason: "Studio must keep a no-paid scene preview workbench before final render.",
  },
  {
    pattern: /buildStudioPreviewScenes/,
    reason: "Studio must compile preflight output into previewable scene cards.",
  },
  {
    pattern: /Save draft only/,
    reason: "Studio must allow users to save/review scene drafts without starting render.",
  },
  {
    pattern: /Approve draft \(no render yet\)/,
    reason: "Studio must separate draft approval from the final paid render click.",
  },
  {
    pattern: /RenderBlockerPanel/,
    reason: "Studio must show exact blockers before the final render button.",
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
  if (!item.pattern.test(source)) failures.push(`- ${item.reason}`);
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
    pattern: /[\u00c2\u00c3\u00c4\u00c6\u00e2\ufffd]|\u00e1\u00ba|\u00e1\u00bb/,
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

console.log("PASS autonomous UI guard: /studio has no legacy manual Video Agent surface.");
