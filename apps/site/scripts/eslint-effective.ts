// apps/site/scripts/eslint-effective.ts
// ESLINT'S RESOLVED CONFIGURATION, AS DATA. ESLint's configuration is JavaScript,
// which Conftest cannot parse, so this asks ESLint itself what it applies to
// each linted file and writes the answer as eslint-effective/v1 for the Rego
// policy. ESLint's API returns any: it goes straight into the generated schema's
// parse, and the result is validated again before it is written.
import { readdirSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";
import { ESLint } from "eslint";
import { eslintCalculatedConfigV1Schema } from "../src/contracts/eslint-calculated-config.v1.gen";
import { eslintEffectiveV1Schema } from "../src/contracts/eslint-effective.v1.gen";

const SITE = new URL("..", import.meta.url).pathname;
const ROOTS = ["src", "scripts"];
const LINTED = /\.(ts|tsx|mts|mjs|astro)$/;
const WORDS = ["off", "warn", "error"] as const;
type Severity = (typeof WORDS)[number];

function severityOf(value: unknown): Severity {
  if (typeof value === "number") {
    const word = WORDS[value];
    if (word !== undefined) return word;
  }
  if (value === "off" || value === "warn" || value === "error") return value;
  throw new Error(`unrecognised rule severity ${String(value)}`);
}

function candidates(): string[] {
  const found = ROOTS.flatMap((root) =>
    readdirSync(join(SITE, root), { recursive: true, encoding: "utf8" })
      .filter((name) => LINTED.test(name))
      .map((name) => join(SITE, root, name)),
  );
  return [...found, join(SITE, "eslint.config.mjs")];
}

const out = process.argv[2];
if (out === undefined) throw new Error("usage: eslint-effective.ts <output.json>");

const eslint = new ESLint({ cwd: SITE });
const files: Record<string, { no_inline_config: boolean; rules: Record<string, { severity: Severity; options: unknown[] }> }> = {};
for (const file of candidates()) {
  if (await eslint.isPathIgnored(file)) continue;
  const calculated = eslintCalculatedConfigV1Schema.parse(await eslint.calculateConfigForFile(file));
  const rules: Record<string, { severity: Severity; options: unknown[] }> = {};
  for (const [name, setting] of Object.entries(calculated.rules)) {
    const [head, ...options] = Array.isArray(setting) ? setting : [setting];
    rules[name] = { severity: severityOf(head), options };
  }
  files[join("apps/site", relative(SITE, file))] = { no_inline_config: calculated.linterOptions.noInlineConfig, rules };
}
writeFileSync(out, JSON.stringify(eslintEffectiveV1Schema.parse({ contract: "eslint-effective/v1", files }), null, 2) + "\n");
console.log(`wrote ${String(Object.keys(files).length)} files' effective configuration to ${out}`);
