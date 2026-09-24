// apps/site/src/contracts/eslint-effective.v1.gen.ts
// GENERATED from contracts/json/eslint-effective.v1.schema.json by otsafety_tooling.contracts.zod.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod";

export const eslintEffectiveV1Schema = z.strictObject({ "contract": z.literal("eslint-effective/v1"), "files": z.record(z.string(), z.strictObject({ "no_inline_config": z.boolean(), "rules": z.record(z.string(), z.strictObject({ "severity": z.enum(["off", "warn", "error"]), "options": z.array(z.json()) })) })) }).describe("What ESLint actually applies to each linted file, written for the policy.");
