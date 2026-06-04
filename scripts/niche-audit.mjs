import process from "node:process";

const BASE_URL = process.env.CINEJELLY_BASE_URL || "http://localhost:3000";
const maxNiches = Number.parseInt(process.env.CINEJELLY_NICHE_AUDIT_LIMIT || "40", 10);
const includeLongForm = process.env.CINEJELLY_NICHE_AUDIT_LONG !== "0";

function url(path) {
  return `${BASE_URL.replace(/\/$/, "")}${path}`;
}

async function fetchJson(path, init) {
  const res = await fetch(url(path), init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} for ${path}: ${JSON.stringify(data)}`);
  }
  return data;
}

function row(item) {
  return [
    item.niche,
    item.runtime_class,
    item.primary_visual_model,
    item.graph_required ? "yes" : "no",
    item.dialogue_required ? "yes" : "no",
    `${item.reference_status || "unknown"}:${item.reference_score ?? "n/a"}`,
    item.auto_route_allowed ? "yes" : "no",
    item.manual_review_required ? "yes" : "no",
    item.blocked ? "yes" : "no",
  ].join(" | ");
}

async function main() {
  const audit = await fetchJson(
    `/api/v1/director/autonomous/niche-audit?limit=${maxNiches}&include_long_form=${includeLongForm ? "true" : "false"}`,
  );
  const summary = audit.summary || {};
  const shortRows = audit.short_30s || [];
  const longRows = audit.long_5m || [];

  console.log("# CineJelly Niche Audit");
  console.log("");
  console.log(`Base URL: ${BASE_URL}`);
  console.log(`Niches audited: ${summary.niche_count}`);
  console.log(`Short auto-allowed: ${summary.short_auto_allowed}`);
  console.log(`Short review-required: ${summary.short_review_required}`);
  console.log(`Long graph-required: ${summary.long_graph_required}`);
  console.log(`Long auto-allowed: ${summary.long_auto_allowed}`);
  console.log(`Blocked: ${summary.blocked}`);
  console.log(`Any top-tier claim allowed: ${summary.top_tier_claim_allowed}`);
  console.log("");
  console.log("## Short 30s");
  console.log("niche | runtime | route | graph | dialogue | refs | auto | review | blocked");
  console.log("--- | --- | --- | --- | --- | --- | --- | --- | ---");
  console.log(shortRows.map(row).join("\n"));
  if (includeLongForm) {
    console.log("");
    console.log("## Long 5m");
    console.log("niche | runtime | route | graph | dialogue | refs | auto | review | blocked");
    console.log("--- | --- | --- | --- | --- | --- | --- | --- | ---");
    console.log(longRows.map(row).join("\n"));
  }
  process.exit(0);
}

main().catch((error) => {
  console.error(`niche audit failed: ${error.message}`);
  process.exit(1);
});
