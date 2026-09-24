// GENERATED from contracts/json/eslint-calculated-config.v1.schema.json by otsafety_tooling.contracts.zod.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod";

export const eslintCalculatedConfigV1Schema = z.object({ "linterOptions": z.object({ "noInlineConfig": z.boolean().default(false) }), "rules": z.record(z.string(), z.json()) }).describe("ESLint's calculateConfigForFile result: only what the policy needs.");
