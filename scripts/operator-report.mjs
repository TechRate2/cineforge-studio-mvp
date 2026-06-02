import process from "node:process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

const BASE_URL = process.env.CINEJELLY_BASE_URL || "http://localhost:3000";
const OUTPUT_PATH = process.env.CINEJELLY_OPERATOR_REPORT_OUT
  || "docs/cinejelly_operator_report_latest.md";
const FULL_STDOUT = process.env.CINEJELLY_REPORT_STDOUT === "1";

function url(path) {
  return `${BASE_URL.replace(/\/$/, "")}${path}`;
}

async function fetchJson(path) {
  const res = await fetch(url(path), { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} for ${path}`);
  }
  return res.json();
}

function list(items, max = 8) {
  if (!Array.isArray(items) || items.length === 0) return "- none";
  return items.slice(0, max).map((item) => `- ${String(item)}`).join("\n");
}

function table(rows) {
  return rows.join("\n");
}

function json(value) {
  return JSON.stringify(value || {});
}

function formatNiche(name) {
  return String(name || "").replace(/_/g, " ");
}

function section(title, body) {
  return [`## ${title}`, body].join("\n\n");
}

async function main() {
  const [
    brief,
    audit,
    capability,
    playbook,
    atlas,
    research,
    manifest,
    gate,
    nicheAudit,
    workflowGuide,
    phase4,
  ] = await Promise.all([
    fetchJson("/api/v1/director/autonomous/operator-brief"),
    fetchJson("/api/v1/director/autonomous/production-audit"),
    fetchJson("/api/v1/director/autonomous/capability-matrix"),
    fetchJson("/api/v1/director/autonomous/niche-playbook-catalog"),
    fetchJson("/api/v1/director/autonomous/atlas-model-matrix"),
    fetchJson("/api/v1/director/autonomous/research"),
    fetchJson("/api/v1/director/autonomous/paid-benchmark-manifest?focus=sell_first&limit=6&outputs_per_route=2"),
    fetchJson("/api/v1/director/autonomous/top-tier-completion-gate"),
    fetchJson("/api/v1/director/autonomous/niche-audit?limit=23"),
    fetchJson("/api/v1/director/autonomous/workflow-niche-guide"),
    fetchJson("/api/v1/director/autonomous/phase4-completion-audit"),
  ]);

  const durationRows = (brief.duration_policy || []).map((item) =>
    `| ${item.duration || ""} | ${item.status || ""} | ${item.method || ""} |`,
  );
  const workflowRows = (brief.production_workflow_steps || []).map((step, index) =>
    `| ${index + 1} | ${step.id || ""} | ${step.agent_role || ""} | ${(step.output || []).slice(0, 3).join(", ")} | ${step.status || ""} |`,
  );
  const modelRows = (atlas.rows || []).slice(0, 12).map((row) =>
    `| ${row.model_key || ""} | ${row.lane || ""} | ${row.status || ""} | ${(row.best_for || []).slice(0, 2).join("; ")} |`,
  );
  const guideRows = (workflowGuide.workflow_steps || []).map((step) =>
    `| ${step.step || ""} | ${step.id || ""} | ${step.role || ""} | ${(step.quality_gate || []).slice(0, 2).join("; ")} | ${step.status || ""} |`,
  );
  const durationGuideRows = (workflowGuide.duration_strategy || []).map((item) =>
    `| ${item.duration || ""} | ${item.default_status || ""} | ${item.seedance_units || ""} | ${item.method || ""} |`,
  );
  const nicheCardRows = (workflowGuide.niche_fit?.cards || []).slice(0, 14).map((card) =>
    `| ${formatNiche(card.niche)} | ${card.launch_tier || ""} | ${card.best_runtime_today || ""} | ${card.primary_visual_model || ""} | ${(card.benchmark_before || []).slice(0, 2).join("; ")} |`,
  );
  const scenarioRows = (workflowGuide.scenario_route_examples || []).map((row) =>
    `| ${row.label || row.id || ""} | ${formatNiche(row.niche)} | ${row.runtime_class || ""} | ${row.primary_visual_model || ""} | ${row.graph_required ? "yes" : "no"} | ${row.auto_route_allowed ? "yes" : "no"} | ${row.manual_review_required ? "yes" : "no"} |`,
  );
  const longFormRows = (workflowGuide.long_form_blueprints || []).map((row) =>
    `| ${row.label || row.id || ""} | ${row.runtime_class || ""} | ${row.duration_s || ""} | ${row.scene_count ?? ""} | ${row.chunk_count ?? ""} | ${row.estimated_seedance_units ?? ""} | ${row.graph_required ? "yes" : "no"} | ${row.dialogue_required ? "yes" : "no"} |`,
  );
  const sourceRuleRows = (workflowGuide.seedance_2_usage?.core_rules || []).map((rule) =>
    `| ${rule.rule || ""} | ${rule.contract || ""} | ${rule.implementation || ""} |`,
  );
  const qaRows = (workflowGuide.qa_evidence_plan?.dimensions || []).map((row) =>
    `| ${row.id || ""} | ${Array.isArray(row.applies_to) ? row.applies_to.slice(0, 4).join(", ") : ""} | ${row.current_status || ""} | ${Array.isArray(row.evidence_required) ? row.evidence_required.slice(0, 4).join("; ") : ""} |`,
  );
  const researchUpgradeRows = (research.source_backed_upgrade_matrix || []).map((row) =>
    `| ${row.priority || ""} | ${row.upgrade || ""} | ${row.current_status || ""} | ${Array.isArray(row.implementation_target) ? row.implementation_target.slice(0, 3).join("; ") : ""} | ${row.promotion_gate || ""} |`,
  );

  const report = [
    "# CineJelly Autonomous Agent Operator Report",
    "",
    `Generated from live API: ${BASE_URL}`,
    `Schema: ${brief.schema_version || "unknown"}`,
    "",
    section(
      "Current Verdict",
      [
        `- Current level: ${brief.current_level || "unknown"}`,
        `- Top-tier proven: ${Boolean(brief.top_tier_proven)}`,
        `- Phase 4 no-paid complete: ${Boolean(phase4.verdict?.non_paid_phase4_complete)}`,
        `- Phase 4 claim level: ${phase4.verdict?.current_claim_level || "unknown"}`,
        `- Top-app comparison: ${brief.top_app_comparison?.verdict || "unknown"}`,
        `- Claim rule: ${brief.top_app_comparison?.claim_rule || "benchmark evidence required"}`,
        `- Plain answer: ${brief.plain_answer || audit.executive_verdict?.plain_answer || ""}`,
      ].join("\n"),
    ),
    section(
      "Phase 4 No-Paid Completion",
      [
        `- Non-paid infrastructure: ${phase4.verdict?.readiness_percentages?.non_paid_phase4_infrastructure ?? "unknown"}%`,
        `- Autonomous short-form engineering: ${phase4.verdict?.readiness_percentages?.autonomous_short_form_engineering ?? "unknown"}%`,
        `- Long-form contract: ${phase4.verdict?.readiness_percentages?.long_form_engineering_contract ?? "unknown"}%`,
        `- Proven output quality: ${phase4.verdict?.readiness_percentages?.proven_output_quality ?? "unknown"}%`,
        `- Vendor calls allowed by this audit: ${Boolean(phase4.vendor_call_policy?.vendor_calls_allowed_by_this_audit)}`,
        `- Paid output proof complete: ${Boolean(phase4.verdict?.paid_output_proof_complete)}`,
        `- Plain answer: ${phase4.verdict?.plain_answer || ""}`,
      ].join("\n"),
    ),
    section(
      "What Already Matches Top Apps",
      list(brief.top_app_comparison?.matches_top_apps_on, 12),
    ),
    section(
      "What Still Blocks Top-Tier Claims",
      list(brief.top_app_comparison?.still_behind_top_apps_until, 12),
    ),
    section(
      "Autonomous Workflow",
      table([
        "| # | Stage | Agent Role | Output | Status |",
        "|---|---|---|---|---|",
        ...workflowRows,
      ]),
    ),
    section(
      "Workflow Guide",
      [
        `- Architecture shape: ${workflowGuide.current_position?.architecture_shape || "unknown"}`,
        `- Output claim: ${workflowGuide.current_position?.output_claim || "unknown"}`,
        `- UI mode: ${workflowGuide.current_position?.ui_mode || "unknown"}`,
        `- Top-tier proven: ${Boolean(workflowGuide.current_position?.top_tier_proven)}`,
        `- Why not proven: ${workflowGuide.current_position?.why_not_proven || ""}`,
        "",
        "| # | Stage | Role | First Gates | Status |",
        "|---|---|---|---|---|",
        ...guideRows,
      ].join("\n"),
    ),
    section(
      "Duration Policy",
      table([
        "| Duration | Status | Method |",
        "|---|---|---|",
        ...durationRows,
      ]),
    ),
    section(
      "Duration Strategy From Workflow Guide",
      table([
        "| Duration | Default Status | Seedance Units | Method |",
        "|---|---|---|---|",
        ...durationGuideRows,
      ]),
    ),
    section(
      "Niche Fit",
      [
        `- Sell first: ${(brief.niche_fit_table?.sell_first || []).map(formatNiche).join(", ")}`,
        `- Benchmark next: ${(brief.niche_fit_table?.benchmark_next || []).map(formatNiche).join(", ")}`,
        `- Review locked: ${(brief.niche_fit_table?.review_locked || []).map(formatNiche).join(", ")}`,
        `- Rule: ${brief.niche_fit_table?.rule || ""}`,
        `- Playbook count: ${playbook.summary?.niche_count ?? "unknown"}`,
      ].join("\n"),
    ),
    section(
      "Niche Cards",
      table([
        "| Niche | Tier | Best Runtime Today | Visual Route | Benchmark Before |",
        "|---|---|---|---|---|",
        ...nicheCardRows,
      ]),
    ),
    section(
      "Scenario Route Examples",
      table([
        "| Scenario | Niche | Runtime | Visual Route | Graph | Auto | Review |",
        "|---|---|---|---|---|---|---|",
        ...scenarioRows,
      ]),
    ),
    section(
      "Live Niche Audit",
      [
        `- Niches audited: ${nicheAudit.summary?.niche_count ?? 0}`,
        `- Short auto-allowed: ${nicheAudit.summary?.short_auto_allowed ?? 0}`,
        `- Short review-required: ${nicheAudit.summary?.short_review_required ?? 0}`,
        `- Long 5m graph-required: ${nicheAudit.summary?.long_graph_required ?? 0}`,
        `- Long 5m auto-allowed: ${nicheAudit.summary?.long_auto_allowed ?? 0}`,
        `- Blocked rows: ${nicheAudit.summary?.blocked ?? 0}`,
        `- Any top-tier claim allowed: ${Boolean(nicheAudit.summary?.top_tier_claim_allowed)}`,
      ].join("\n"),
    ),
    section(
      "Seedance And Model Policy",
      [
        `- Primary family: ${atlas.verdict?.primary_family || brief.model_policy?.primary_family || "Seedance 2.0"}`,
        `- Default route: ${atlas.recommendation?.default_route || "seedance_2_0_fast_ref"}`,
        `- Premium route: ${atlas.recommendation?.premium_route || "seedance_2_0_ref"}`,
        `- User-facing model picker: ${atlas.recommendation?.keep_ui_model_picker === false ? "hidden" : "review"}`,
        "",
        "| Model | Lane | Status | Best For |",
        "|---|---|---|---|",
        ...modelRows,
      ].join("\n"),
    ),
    section(
      "Source-Backed Seedance Rules",
      table([
        "| Rule | Contract | Implementation |",
        "|---|---|---|",
        ...sourceRuleRows,
      ]),
    ),
    section(
      "Long-Form Rule",
      [
        `- Rule: ${brief.long_form_rule?.rule || "Never render a long film in one model call."}`,
        `- Guide hard rule: ${workflowGuide.long_form_rule?.hard_rule || ""}`,
        `- Guide status: ${workflowGuide.long_form_rule?.status || ""}`,
        list(brief.long_form_rule?.implementation, 12),
        "",
        "Proof needed:",
        list(workflowGuide.long_form_rule?.proof_needed, 8),
      ].join("\n"),
    ),
    section(
      "Long-Form Blueprints",
      table([
        "| Case | Runtime | Seconds | Scenes | Chunks | Seedance Units | Graph | Dialogue |",
        "|---|---|---:|---:|---:|---:|---|---|",
        ...longFormRows,
      ]),
    ),
    section(
      "QA Evidence Plan",
      [
        `- Dimensions: ${workflowGuide.qa_evidence_plan?.dimension_count ?? 0}`,
        `- Model-backed required before top-tier: ${Boolean(workflowGuide.qa_evidence_plan?.model_backed_required_before_top_tier)}`,
        `- Current blockers: ${(workflowGuide.qa_evidence_plan?.currently_top_tier_blocked_by || []).join(", ")}`,
        `- Rule: ${workflowGuide.qa_evidence_plan?.rule || ""}`,
        "",
        "| Dimension | Applies To | Status | Evidence Required |",
        "|---|---|---|---|",
        ...qaRows,
      ].join("\n"),
    ),
    section(
      "Paid Benchmark Batch",
      [
        `- Cases: ${manifest.summary?.case_count ?? 0}`,
        `- Runs: ${manifest.summary?.paid_run_count ?? 0}`,
        `- Outputs per route: ${manifest.summary?.outputs_per_route ?? 0}`,
        `- Estimated cost: ${json(manifest.summary?.estimated_vendor_cost_usd)}`,
        `- Top-tier after manifest alone: ${Boolean(manifest.summary?.top_tier_claim_after_manifest)}`,
      ].join("\n"),
    ),
    section(
      "Research Position",
      [
        `- Closest strength today: ${research.research_position?.closest_strength_today || ""}`,
        `- Largest remaining gap: ${research.research_position?.largest_remaining_gap || ""}`,
        `- Implementation score: ${json(research.implementation_score || brief.research_position?.implementation_score)}`,
      ].join("\n"),
    ),
    section(
      "Source-Backed Upgrade Matrix",
      table([
        "| Priority | Upgrade | Current Status | Implementation Target | Promotion Gate |",
        "|---|---|---|---|---|",
        ...researchUpgradeRows,
      ]),
    ),
    section(
      "Next Upgrade Order",
      list(brief.next_upgrade_order, 12),
    ),
    section(
      "Completion Gate",
      [
        `- Top-app parity proven: ${Boolean(gate.verdict?.top_app_parity_proven)}`,
        `- Passed: ${gate.verdict?.passed_count ?? 0}`,
        `- Partial: ${gate.verdict?.partial_count ?? 0}`,
        `- Failed: ${gate.verdict?.failed_count ?? 0}`,
        "",
        "Next proof order:",
        list(gate.next_proof_order, 12),
      ].join("\n"),
    ),
    section(
      "Evidence Endpoints",
      list(brief.evidence_endpoints, 20),
    ),
  ].join("\n\n");

  const outputPath = resolve(process.cwd(), OUTPUT_PATH);
  mkdirSync(dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, report, "utf8");

  if (FULL_STDOUT) {
    console.log(report);
    return;
  }

  console.log([
    "CineJelly operator report generated.",
    `File: ${outputPath}`,
    `Verdict: ${workflowGuide.current_position?.output_claim || "unknown"}`,
    `Niches: ${workflowGuide.niche_fit?.audit_summary?.niche_count ?? 0}`,
    `Short auto: ${workflowGuide.niche_fit?.audit_summary?.short_auto_allowed ?? 0}`,
    `5m graph-required: ${workflowGuide.niche_fit?.audit_summary?.long_graph_required ?? 0}`,
    "Use CINEJELLY_REPORT_STDOUT=1 to print the full Markdown report.",
  ].join("\n"));
}

main().catch((error) => {
  console.error(`operator report failed: ${error.message}`);
  process.exitCode = 1;
});
