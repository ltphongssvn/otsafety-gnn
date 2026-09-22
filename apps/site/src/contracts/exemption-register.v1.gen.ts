// GENERATED from contracts/json/exemption-register.v1.schema.json by scripts/generate-contracts.ts.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod"

export const exemptionRegisterV1Schema = z.object({ "contract": z.literal("exemption-register/v1"), "scoped": z.array(z.object({ "glob": z.string().min(1), "rules": z.array(z.string()).min(1), "reason": z.string().min(1) }).strict()), "inline": z.array(z.object({ "path": z.string().min(1), "rule": z.string().min(1), "count": z.number().int().gte(1), "reason": z.string().min(1) }).strict()), "eslint": z.array(z.object({ "path": z.string().min(1), "rules": z.array(z.string()).min(1), "reason": z.string().min(1) }).strict().describe("Protected ESLint rules a file does not enforce. ESLint allows no inline disables,\nso a file-scoped block in eslint.config.mjs is the only exemption; the Rego policy\nchecks each against ESLint's effective configuration, in both directions.")).default([]) }).strict()

