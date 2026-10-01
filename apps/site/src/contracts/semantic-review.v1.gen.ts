// apps/site/src/contracts/semantic-review.v1.gen.ts
// GENERATED from contracts/json/semantic-review.v1.schema.json by otsafety_tooling.contracts.zod.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod";

export const semanticReviewV1Schema = z.strictObject({ "contract": z.literal("semantic-review/v1"), "reviewed_at": z.iso.datetime({ offset: true }), "step": z.string().min(1), "claim": z.string().min(1), "finding": z.enum(["covered", "partial", "uncovered", "unreadable", "split"]), "rationale": z.string().min(1), "judge": z.strictObject({ "model": z.string(), "rubric": z.string().regex(new RegExp("^[a-z0-9-]+/v\\d+$")), "prompt_sha256": z.string().regex(new RegExp("^[0-9a-f]{64}$")), "repeats": z.int().gt(0), "agreed": z.int().gt(0) }).describe("What produced a finding, in enough detail to ask for it again.") }).describe("One reading of whether a step's evidence establishes its claim.");
