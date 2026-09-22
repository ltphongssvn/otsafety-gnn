// apps/site/scripts/generate-contracts.ts
// ZOD FROM THE COMMITTED JSON SCHEMAS, NEVER BY HAND.
//
// The Pydantic models are the single source: contracts:generate exports their
// JSON Schema into contracts/json/, and this turns each file into a Zod module.
// The site had hand-written types that drifted from the contracts -- four of five
// repository-settings fields misnamed -- and a generated file cannot.
import { jsonSchemaToZod } from "json-schema-to-zod";
import { readFileSync, readdirSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const root = new URL("../../..", import.meta.url).pathname;
const source = join(root, "contracts", "json");
// An optional directory argument writes elsewhere, so a test can regenerate and
// compare against the committed files without touching them.
const target = process.argv[2] ?? join(root, "apps", "site", "src", "contracts");
mkdirSync(target, { recursive: true });

for (const file of readdirSync(source).filter((f) => f.endsWith(".schema.json")).sort()) {
  const stem = file.replace(".schema.json", "");
  const name =
    stem.split(/[.-]/).map((p, i) => (i === 0 ? p : p.charAt(0).toUpperCase() + p.slice(1))).join("") +
    "Schema";
  const schema = JSON.parse(readFileSync(join(source, file), "utf-8"));
  // A JSON value, which the export marks x-json-value: Zod 4's z.json(), where
  // json-schema-to-zod would otherwise write z.any().
  const code = jsonSchemaToZod(schema, {
    name,
    module: "esm",
    parserOverride: (node) => ("x-json-value" in node ? "z.json()" : undefined),
  });
  const header =
    `// GENERATED from contracts/json/${file} by scripts/generate-contracts.ts.\n` +
    `// Do not edit: change the Pydantic model and run mise run contracts:generate.\n`;
  writeFileSync(join(target, `${stem}.gen.ts`), header + code + "\n");
  console.log(`wrote apps/site/src/contracts/${stem}.gen.ts (${name})`);
}
