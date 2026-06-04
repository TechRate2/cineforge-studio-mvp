import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const ROOT = process.cwd();
const DEFAULT_KNOWLEDGE_DIR = path.join(ROOT, "backend", "seedance", "knowledge");
const DEFAULT_RULES_PATH = path.join(DEFAULT_KNOWLEDGE_DIR, "rules.jsonl");
const DEFAULT_EXAMPLES_PATH = path.join(DEFAULT_KNOWLEDGE_DIR, "examples.jsonl");

const args = parseArgs(process.argv.slice(2));

if (args.help) {
  printHelp();
  process.exit(0);
}

const rulesInputPath = path.resolve(args.rules || DEFAULT_RULES_PATH);
const examplesInputPath = path.resolve(args.examples || DEFAULT_EXAMPLES_PATH);
const outDir = path.resolve(args.outDir || DEFAULT_KNOWLEDGE_DIR);
const rulesOutputPath = path.join(outDir, "rules.jsonl");
const examplesOutputPath = path.join(outDir, "examples.jsonl");

const rules = readJsonl(rulesInputPath).map(normalizeRule);
const examples = readJsonl(examplesInputPath).map(normalizeExample);

validateUnique(rules, "rule_id", "rules");
validateUnique(examples, "example_id", "examples");

const summary = {
  mode: args.write ? "write" : "dry_run",
  rules: {
    input: rulesInputPath,
    output: rulesOutputPath,
    count: rules.length,
    source_repos: unique(rules.map((rule) => rule.source_repo)),
  },
  examples: {
    input: examplesInputPath,
    output: examplesOutputPath,
    count: examples.length,
    source_repos: unique(examples.map((example) => example.source_repo)),
    niches: unique(examples.map((example) => example.niche)),
  },
};

if (args.write) {
  fs.mkdirSync(outDir, { recursive: true });
  writeJsonl(rulesOutputPath, rules);
  writeJsonl(examplesOutputPath, examples);
}

console.log("[seedance knowledge import]");
console.log(JSON.stringify(summary, null, 2));
if (!args.write) {
  console.log("Dry-run only. Re-run with --write to update backend/seedance/knowledge/*.jsonl.");
}

function parseArgs(argv) {
  const parsed = {
    rules: "",
    examples: "",
    outDir: "",
    write: false,
    help: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--help" || arg === "-h") parsed.help = true;
    else if (arg === "--write") parsed.write = true;
    else if (arg === "--rules") parsed.rules = requiredValue(argv, ++index, "--rules");
    else if (arg === "--examples") parsed.examples = requiredValue(argv, ++index, "--examples");
    else if (arg === "--out-dir") parsed.outDir = requiredValue(argv, ++index, "--out-dir");
    else throw new Error(`Unknown argument: ${arg}`);
  }
  return parsed;
}

function requiredValue(argv, index, flag) {
  const value = argv[index];
  if (!value || value.startsWith("--")) {
    throw new Error(`${flag} requires a value`);
  }
  return value;
}

function printHelp() {
  console.log(`Usage: node scripts/import-seedance-knowledge.mjs [options]

Options:
  --rules <path>      JSONL rules input. Defaults to backend/seedance/knowledge/rules.jsonl
  --examples <path>   JSONL examples input. Defaults to backend/seedance/knowledge/examples.jsonl
  --out-dir <path>    Output directory for normalized rules.jsonl/examples.jsonl
  --write             Write normalized files. Default is validate-only dry-run
  --help              Show this message
`);
}

function readJsonl(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Knowledge file not found: ${filePath}`);
  }
  return fs.readFileSync(filePath, "utf8")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"))
    .map((line, index) => {
      try {
        return JSON.parse(line);
      } catch (error) {
        throw new Error(`${filePath}:${index + 1} invalid JSON: ${error.message}`);
      }
    });
}

function normalizeRule(raw) {
  requireFields(raw, ["rule_id", "source_repo", "source_url", "license"], "rule");
  const description = stringValue(raw.description || raw.summary);
  const appliedToFile = stringValue(raw.applied_to_file || first(raw.applies_to_files));
  const appliedToFunction = stringValue(raw.applied_to_function || first(raw.target_functions));
  const rule = {
    ...raw,
    description,
    applied_to_file: appliedToFile,
    applied_to_function: appliedToFunction,
    rule_type: stringValue(raw.rule_type || "quality_gate"),
    applies_to_files: arrayValue(raw.applies_to_files || [appliedToFile]),
    target_functions: arrayValue(raw.target_functions || [appliedToFunction]),
    summary: stringValue(raw.summary || description),
    implementation_notes: stringValue(raw.implementation_notes || ""),
    phase: stringValue(raw.phase || "5"),
    severity: stringValue(raw.severity || "info"),
    tags: arrayValue(raw.tags || []),
  };
  requireFields(rule, ["description", "applied_to_file", "applied_to_function", "summary"], "rule");
  return rule;
}

function normalizeExample(raw) {
  requireFields(raw, [
    "example_id",
    "source_repo",
    "source_url",
    "license",
    "niche",
    "duration_s",
    "asset_mode",
    "shot_count",
    "prompt_excerpt",
  ], "example");
  return {
    ...raw,
    duration_s: Number(raw.duration_s),
    shot_count: Number(raw.shot_count),
    prompt_hash: stringValue(raw.prompt_hash || sha256(stringValue(raw.prompt_excerpt))),
    style_tags: arrayValue(raw.style_tags || []),
    continuity_tags: arrayValue(raw.continuity_tags || []),
    camera_patterns: arrayValue(raw.camera_patterns || raw.camera_tags || []),
    audio_tags: arrayValue(raw.audio_tags || []),
    quality_tags: arrayValue(raw.quality_tags || []),
  };
}

function requireFields(row, fields, label) {
  for (const field of fields) {
    if (row[field] === undefined || row[field] === null || row[field] === "") {
      throw new Error(`${label} is missing required field: ${field}`);
    }
  }
}

function validateUnique(rows, key, label) {
  const seen = new Set();
  for (const row of rows) {
    if (seen.has(row[key])) throw new Error(`Duplicate ${label} ${key}: ${row[key]}`);
    seen.add(row[key]);
  }
}

function writeJsonl(filePath, rows) {
  fs.writeFileSync(
    filePath,
    `${rows.map((row) => JSON.stringify(row)).join("\n")}\n`,
    "utf8",
  );
}

function arrayValue(value) {
  if (Array.isArray(value)) return value.map((item) => String(item)).filter(Boolean);
  if (value === undefined || value === null || value === "") return [];
  return [String(value)];
}

function stringValue(value) {
  return String(value ?? "").trim();
}

function first(value) {
  return Array.isArray(value) ? value[0] : value;
}

function unique(values) {
  return [...new Set(values.filter(Boolean).map((value) => String(value)))].sort();
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}
