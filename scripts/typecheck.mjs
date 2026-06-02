import path from "node:path";
import process from "node:process";
import ts from "typescript";

const cwd = process.cwd();
const configPath = ts.findConfigFile(cwd, ts.sys.fileExists, "tsconfig.json");

if (!configPath) {
  console.error("Could not find tsconfig.json");
  process.exit(1);
}

const configFile = ts.readConfigFile(configPath, ts.sys.readFile);

if (configFile.error) {
  reportDiagnostics([configFile.error]);
  process.exit(1);
}

const parsed = ts.parseJsonConfigFileContent(
  configFile.config,
  ts.sys,
  path.dirname(configPath),
  { noEmit: true },
  configPath
);

if (parsed.errors.length > 0) {
  reportDiagnostics(parsed.errors);
  process.exit(1);
}

const program = ts.createProgram({
  rootNames: parsed.fileNames,
  options: parsed.options,
  projectReferences: parsed.projectReferences,
});

const diagnostics = ts.getPreEmitDiagnostics(program);

if (diagnostics.length > 0) {
  reportDiagnostics(diagnostics);
  process.exit(1);
}

function reportDiagnostics(diagnostics) {
  const host = {
    getCanonicalFileName: (fileName) => fileName,
    getCurrentDirectory: ts.sys.getCurrentDirectory,
    getNewLine: () => ts.sys.newLine,
  };

  console.error(ts.formatDiagnosticsWithColorAndContext(diagnostics, host));
}
