// GENERATED from contracts/json/plan-status.v1.schema.json by scripts/generate-contracts.ts.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod"

export const planStatusV1Schema = z.object({ "contract": z.literal("plan-status/v1"), "ref": z.string(), "steps": z.array(z.object({ "id": z.string(), "state": z.enum(["done","in_progress","ready","blocked"]), "blocked_by": z.array(z.string()) }).strict()), "threads": z.record(z.string(), z.tuple([z.number().int(),z.number().int()])) }).strict()

