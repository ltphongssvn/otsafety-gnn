// apps/site/src/contracts/sheet-facts.v1.gen.ts
// GENERATED from contracts/json/sheet-facts.v1.schema.json by otsafety_tooling.contracts.zod.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod";

export const sheetFactsV1Schema = z.strictObject({ "contract": z.literal("sheet-facts/v1"), "steps": z.int(), "steps_done": z.int(), "ids": z.int(), "requirements": z.int(), "unconfirmed": z.int(), "test_functions": z.int(), "merged_prs": z.int(), "tasks": z.int(), "phases": z.array(z.strictObject({ "id": z.string(), "title": z.string(), "done": z.int(), "total": z.int(), "state": z.enum(["done", "now", "todo"]) }).describe("One delivery phase and how far its steps have got.")), "threads": z.array(z.strictObject({ "id": z.string(), "title": z.string(), "done": z.int(), "total": z.int(), "percent": z.int(), "state": z.enum(["done", "active", "todo"]) }).describe("One workstream, with the share of its steps the plan shows complete.")) }).describe("Every number the sheet states, as observed when it was collected.");
