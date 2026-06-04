import process from "node:process";

const BASE_URL = process.env.CINEJELLY_BASE_URL || "http://localhost:3000";
const idea = process.env.CINEJELLY_IDEA ||
  "A Vietnamese creator tests a premium lipstick in a Saigon cafe with macro texture and mirror reveal.";
const targetMarket = process.env.CINEJELLY_MARKET || "auto";
const targetPlatform = process.env.CINEJELLY_PLATFORM || "tiktok";
const durationHint = Number.parseInt(process.env.CINEJELLY_DURATION || "30", 10);
const nicheHint = process.env.CINEJELLY_NICHE || "";
const speakerCount = Number.parseInt(process.env.CINEJELLY_SPEAKERS || "1", 10);
const imageRefs = Number.parseInt(process.env.CINEJELLY_IMAGE_REFS || "3", 10);
const videoRefs = Number.parseInt(process.env.CINEJELLY_VIDEO_REFS || "1", 10);
const audioRefs = Number.parseInt(process.env.CINEJELLY_AUDIO_REFS || "1", 10);

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

function line(label, value) {
  return `- ${label}: ${value === undefined || value === null || value === "" ? "n/a" : value}`;
}

function compact(items, max = 5) {
  if (!Array.isArray(items) || items.length === 0) return "none";
  return items.slice(0, max).join("; ");
}

async function main() {
  const payload = {
    user_idea: idea,
    target_market: targetMarket,
    target_platform: targetPlatform,
    duration_hint_s: durationHint,
    speaker_count: speakerCount,
    reference_counts: {
      images: imageRefs,
      videos: videoRefs,
      audios: audioRefs,
    },
  };
  if (nicheHint) payload.niche_hint = nicheHint;

  const decision = await fetchJson("/api/v1/director/autonomous/production-decision", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const d = decision.decision || {};
  const route = d.primary_model_route || {};
  const dialogue = d.dialogue_route_policy || {};
  const refs = decision.reference_sufficiency || {};
  const segment = decision.seedance_segment_inspector || {};
  const runtime = decision.niche_runtime_director || {};
  const routeScore = decision.route_quality_scorecard || {};
  const preflight = decision.responsible_content_gate || {};
  const upgrade = decision.autonomous_input_upgrade_plan || {};
  const grammar = decision.cinematic_grammar || {};

  console.log("# CineJelly Decision Preview");
  console.log("");
  console.log(`Idea: ${idea}`);
  console.log("");
  console.log("## Decision");
  console.log(line("Niche", d.niche));
  console.log(line("Runtime", `${d.runtime_class || "n/a"} / ${d.target_duration_s || durationHint}s`));
  console.log(line("Market", `${d.requested_target_market || targetMarket} -> ${d.target_market || "auto"}`));
  console.log(line("Graph required", Boolean(d.graph_required)));
  console.log(line("Dialogue required", Boolean(d.dialogue_required)));
  console.log(line("Render blocked", Boolean(d.render_blocked_by_responsible_gate)));
  console.log(line("Benchmark before top-tier", Boolean(d.benchmark_required_before_top_tier_claim)));
  console.log("");
  console.log("## Route");
  console.log(line("Primary visual model", route.primary_visual_model));
  console.log(line("Continuity model", route.continuity_model));
  console.log(line("Premium visual model", route.premium_visual_model));
  console.log(line("Dialogue route", dialogue.route_type));
  console.log(line("Dialogue candidate", dialogue.dialogue_candidate));
  console.log(line("Lip-sync/post candidate", dialogue.post_process_candidate));
  console.log(line("Auto route allowed", routeScore.auto_route_allowed));
  console.log(line("Top-tier claim allowed", routeScore.top_tier_claim_allowed));
  console.log("");
  console.log("## References And Seedance");
  console.log(line("Reference status", refs.status));
  console.log(line("Reference score", refs.score));
  console.log(line("Missing minimum", JSON.stringify(refs.missing_minimum || {})));
  console.log(line("Estimated Seedance units", segment.estimated_total_units));
  console.log(line("Preview segments", segment.preview_segment_count));
  console.log(line("Unit contract", JSON.stringify(segment.unit_contract || {})));
  console.log("");
  console.log("## Director Strategy");
  console.log(line("Director mode", runtime.director_mode));
  console.log(line("Opening", runtime.opening_contract?.first_3s));
  console.log(line("Story shape", runtime.story_shape?.rule));
  console.log(line("Camera language", compact(runtime.editorial_rhythm?.camera_palette)));
  console.log(line("Cinematic grammar", grammar.summary || grammar.schema_version));
  console.log("");
  console.log("## User Upgrade Advice");
  console.log(line("Renderable now", upgrade.renderable_now));
  console.log(line("Top-tier ready", upgrade.top_tier_ready));
  console.log(line("Message", upgrade.user_message));
  console.log(line("Priority actions", compact((upgrade.priority_actions || []).map((item) => `${item.priority}: ${item.action}`), 6)));
  console.log("");
  console.log("## Safety");
  console.log(line("Responsible status", preflight.status));
  console.log(line("Manual review", preflight.manual_review_required));
  console.log(line("Hard blockers", compact(preflight.hard_blockers, 6)));
  process.exit(0);
}

main().catch((error) => {
  console.error(`decision preview failed: ${error.message}`);
  process.exit(1);
});
