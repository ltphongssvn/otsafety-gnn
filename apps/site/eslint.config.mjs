// apps/site/eslint.config.mjs
// SCHEMA-FIRST, ENFORCED BY THE LINTER. Every shape the site reads comes from Zod
// generated from a Pydantic model, and its type from z.infer. Raw data may exist
// only as the direct argument of a generated schema's .parse or .safeParse, so it
// is never held unvalidated. Assertions, any and @ts- comments are refused, and
// noInlineConfig means no comment can switch a rule off: an exemption lives in
// this file, with its reason, or nowhere.
//
// NOT BANNED: hand-written types for the site's own content. They cross no trust
// boundary and duplicate nothing, so forcing a schema onto them is the third
// trigger the schema-first rule forbids. The evidence page's drifted type was
// only possible through a cast of unchecked JSON, and both are refused below.
// Content types that do repeat a contract are derived by plan steps 7.8, 7.9, 8.5.
import js from "@eslint/js";
import { defineConfig } from "eslint/config";
import astro from "eslint-plugin-astro";
import globals from "globals";
import tseslint from "typescript-eslint";

const ZOD_BUILDERS =
  "^(object|strictObject|looseObject|enum|string|number|boolean|array|union|discriminatedUnion|literal|tuple|record|intersection)$";
const VALIDATED = "CallExpression[callee.property.name=/^(parse|safeParse)$/] > ";

export default defineConfig([
  { ignores: ["dist/**", ".astro/**", "node_modules/**", "src/contracts/*.gen.ts"] },
  { linterOptions: { noInlineConfig: true, reportUnusedDisableDirectives: "error" } },
  js.configs.recommended,
  tseslint.configs.strictTypeChecked,
  astro.configs.recommended,
  {
    languageOptions: {
      globals: globals.node,
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
  },
  {
    // astro-eslint-parser does not support projectService; it is told what it uses.
    files: ["**/*.astro"],
    languageOptions: { parserOptions: { projectService: false, project: true, extraFileExtensions: [".astro"] } },
  },
  {
    rules: {
      "@typescript-eslint/consistent-type-assertions": ["error", { assertionStyle: "never" }],
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/ban-ts-comment": "error",
      "no-restricted-syntax": [
        "error",
        { selector: `CallExpression[callee.object.name='JSON'][callee.property.name='parse']:not(${VALIDATED}CallExpression)`,
          message: "JSON.parse only as the direct argument of a generated schema's .parse or .safeParse" },
        { selector: `MemberExpression[object.name='process'][property.name='env']:not(${VALIDATED}MemberExpression)`,
          message: "process.env only as the direct argument of projectSettingsV1Schema.parse" },
        { selector: `CallExpression[callee.object.name='z'][callee.property.name=/${ZOD_BUILDERS}/]`,
          message: "Zod schemas are generated from the Pydantic models; import one from src/contracts" },
      ],
    },
  },
]);
