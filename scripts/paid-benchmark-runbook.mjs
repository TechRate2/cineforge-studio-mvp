import process from "node:process";

const DEFAULT_BASE = process.env.CINEJELLY_BASE_URL || "http://localhost:3000";
const focus = process.env.CINEJELLY_BENCHMARK_FOCUS || "sell_first";
const limit = Number.parseInt(process.env.CINEJELLY_BENCHMARK_LIMIT || "6", 10);
const outputs = Number.parseInt(process.env.CINEJELLY_BENCHMARK_OUTPUTS || "2", 10);

function buildUrl(path) {
  return `${DEFAULT_BASE.replace(/\/$/, "")}${path}`;
}

async function fetchJson(path) {
  const res = await fetch(buildUrl(path), { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} for ${path}`);
  }
  return res.json();
}

function compactList(items, max = 4) {
  if (!Array.isArray(items) || items.length === 0) return "none";
  const head = items.slice(0, max).join(", ");
  return items.length > max ? `${head}, +${items.length - max}` : head;
}

function renderRun(run, index) {
  const payload = run.render_payload_blueprint || {};
  const patch = run.benchmark_result_patch_after_render || {};
  const evidenceKeys = Object.keys(patch.evidence || {});
  return [
    `${index + 1}. ${run.run_id}`,
    `   niche/runtime/market: ${run.niche} / ${run.runtime_class} / ${run.target_market}`,
    `   model route: ${run.model_key}`,
    `   idea: ${run.idea}`,
    `   estimated cost: ${JSON.stringify(run.estimated_vendor_cost_usd)}`,
    `   create planned row: POST /api/v1/director/autonomous/benchmarks/results`,
    `   render: POST /api/v1/director/autonomous`,
    `   payload: ${JSON.stringify(payload)}`,
    `   after render patch: PATCH /api/v1/director/autonomous/benchmarks/results/{result_id}`,
    `   required evidence keys: ${compactList(evidenceKeys, 12)}`,
  ].join("\n");
}

async function main() {
  const manifestPath =
    `/api/v1/director/autonomous/paid-benchmark-manifest?focus=${encodeURIComponent(focus)}&limit=${limit}&outputs_per_route=${outputs}`;
  const [health, brief, manifest] = await Promise.all([
    fetchJson("/api/v1/director/autonomous/operator-brief"),
    fetchJson("/api/v1/director/autonomous/top-tier-completion-gate"),
    fetchJson(manifestPath),
  ]);

  const runs = Array.isArray(manifest.runs) ? manifest.runs : [];
  const firstRuns = runs.slice(0, Math.min(runs.length, 6));
  const atlasReady = Boolean(process.env.ATLASCLOUD_API_KEY);

  console.log("CineJelly paid benchmark runbook");
  console.log(`Base URL: ${DEFAULT_BASE}`);
  console.log(`Operator brief: ${health.schema_version || "unknown"}`);
  console.log(`Top-tier proven: ${Boolean(brief.verdict?.top_app_parity_proven)}`);
  console.log(`Atlas key present: ${atlasReady ? "yes" : "no"}`);
  console.log("");
  console.log("Batch summary");
  console.log(`Focus: ${manifest.focus}`);
  console.log(`Cases: ${manifest.summary?.case_count ?? 0}`);
  console.log(`Runs: ${manifest.summary?.paid_run_count ?? 0}`);
  console.log(`Outputs per route: ${manifest.summary?.outputs_per_route ?? outputs}`);
  console.log(`Sell-first niches: ${compactList(manifest.summary?.sell_first_niches, 12)}`);
  console.log(`Estimated vendor cost: ${JSON.stringify(manifest.summary?.estimated_vendor_cost_usd || {})}`);
  console.log("");
  console.log("Phases");
  for (const phase of manifest.operator_runbook_phases || []) {
    console.log(`- ${phase.phase}: ${phase.exit_gate}`);
  }
  console.log("");
  console.log("First runs");
  console.log(firstRuns.map(renderRun).join("\n\n"));
  console.log("");
  console.log("Promotion rule");
  console.log("A route is promoted only after at least two approved real outputs with complete evidence for the exact model+niche+runtime+market route.");
  if (!atlasReady) {
    console.log("");
    console.log("Set ATLASCLOUD_API_KEY before spending on real AtlasCloud benchmark renders.");
  }
  process.exit(0);
}

main().catch((error) => {
  console.error(`paid benchmark runbook failed: ${error.message}`);
  process.exit(1);
});
