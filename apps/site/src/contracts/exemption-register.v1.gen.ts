// GENERATED from contracts/json/exemption-register.v1.schema.json by otsafety_tooling.contracts.zod.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod";

export const exemptionRegisterV1Schema = z.strictObject({ "contract": z.literal("exemption-register/v1"), "scoped": z.array(z.strictObject({ "glob": z.string().min(1), "rules": z.array(z.string()).min(1), "reason": z.string().min(1) })), "inline": z.array(z.strictObject({ "path": z.string().min(1), "rule": z.string().min(1), "count": z.int().gte(1), "reason": z.string().min(1) })), "eslint": z.array(z.strictObject({ "path": z.string().min(1), "rules": z.array(z.string()).min(1), "reason": z.string().min(1) }).describe("Protected ESLint rules a file does not enforce. ESLint allows no inline disables,\nso a file-scoped block in eslint.config.mjs is the only exemption; the Rego policy\nchecks each against ESLint's effective configuration, in both directions.")).default([]) });
