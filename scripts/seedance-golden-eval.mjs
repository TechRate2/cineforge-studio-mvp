import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const args = parseArgs(process.argv.slice(2));

if (args.help) {
  printHelp();
  process.exit(0);
}

const python = process.env.PYTHON || "python";
const pytestArgs = [
  "-m",
  "pytest",
  "backend/tests/test_seedance_golden_cases.py",
  args.quiet ? "-q" : "-vv",
];

if (args.caseFilter) {
  pytestArgs.push("-k", args.caseFilter);
}

console.log("[seedance golden eval]");
console.log(`Command: ${python} ${pytestArgs.join(" ")}`);

const startedAt = new Date().toISOString();
const result = spawnSync(python, pytestArgs, {
  cwd: process.cwd(),
  encoding: "utf8",
});
const finishedAt = new Date().toISOString();

if (result.stdout) process.stdout.write(result.stdout);
if (result.stderr) process.stderr.write(result.stderr);

const report = {
  status: result.status === 0 ? "pass" : "fail",
  exit_code: result.status,
  started_at: startedAt,
  finished_at: finishedAt,
  command: `${python} ${pytestArgs.join(" ")}`,
  case_filter: args.caseFilter || null,
};

console.log("[seedance golden eval summary]");
console.log(JSON.stringify(report, null, 2));

if (args.reportPath) {
  const reportPath = path.resolve(args.reportPath);
  fs.mkdirSync(path.dirname(reportPath), { recursive: true });
  fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  console.log(`Wrote report: ${reportPath}`);
}

process.exit(result.status ?? 1);

function parseArgs(argv) {
  const parsed = {
    caseFilter: "",
    reportPath: "",
    quiet: true,
    help: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--help" || arg === "-h") parsed.help = true;
    else if (arg === "--case") parsed.caseFilter = requiredValue(argv, ++index, "--case");
    else if (arg === "--report") parsed.reportPath = requiredValue(argv, ++index, "--report");
    else if (arg === "--verbose") parsed.quiet = false;
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
  console.log(`Usage: node scripts/seedance-golden-eval.mjs [options]

Options:
  --case <pytest-k>   Run only golden tests matching a pytest -k expression
  --report <path>     Write a JSON summary report
  --verbose           Use pytest -vv instead of -q
  --help              Show this message
`);
}
