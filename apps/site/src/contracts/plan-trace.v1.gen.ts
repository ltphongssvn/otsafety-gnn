// GENERATED from contracts/json/plan-trace.v1.schema.json by scripts/generate-contracts.ts.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod"

export const planTraceV1Schema = z.object({ "contract": z.literal("plan-trace/v1"), "sources": z.array(z.object({ "id": z.string().regex(new RegExp("^[A-Z][A-Z0-9-]*$")), "title": z.string().min(1), "locator": z.string().min(1) }).strict()).min(1), "candidates": z.array(z.object({ "source": z.string().min(1), "ref": z.string().min(1), "text": z.string().min(1), "maps_to": z.array(z.string()).default([]), "not_a_plan_item": z.union([z.string().min(1), z.null()]).default(null) }).strict()).min(1) }).strict()

