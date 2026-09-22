// GENERATED from contracts/json/eslint-effective.v1.schema.json by scripts/generate-contracts.ts.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod"

export const eslintEffectiveV1Schema = z.object({ "contract": z.literal("eslint-effective/v1"), "files": z.record(z.string(), z.object({ "no_inline_config": z.boolean(), "rules": z.record(z.string(), z.object({ "severity": z.enum(["off","warn","error"]), "options": z.array(z.json()) }).strict()) }).strict()) }).strict().describe("What ESLint actually applies to each linted file, written for the policy.")

