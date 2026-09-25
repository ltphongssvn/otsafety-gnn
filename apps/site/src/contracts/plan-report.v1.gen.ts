// apps/site/src/contracts/plan-report.v1.gen.ts
// GENERATED from contracts/json/plan-report.v1.schema.json by otsafety_tooling.contracts.zod.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod";

export const planReportV1Schema = z.strictObject({ "contract": z.literal("plan-report/v1"), "steps": z.int(), "steps_done": z.int(), "ready": z.int(), "blocked": z.int(), "ids": z.int(), "requirements": z.int(), "orphans": z.int(), "phases": z.array(z.strictObject({ "id": z.string(), "title": z.string(), "done": z.int(), "total": z.int(), "steps": z.array(z.strictObject({ "id": z.string(), "title": z.string(), "thread": z.string(), "state": z.enum(["DONE", "READY", "BLOCK"]), "after": z.array(z.string()), "evidence": z.array(z.string()), "unmet": z.array(z.string()) }).describe("One step, as a reader needs it: what it is, where it stands, what blocks it.")) }).describe("One phase and its steps, in plan order.")) }).describe("The whole plan, as the sheet prints it.");
