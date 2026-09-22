// GENERATED from contracts/json/branch-prune.v1.schema.json by scripts/generate-contracts.ts.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod"

export const branchPruneV1Schema = z.object({ "contract": z.literal("branch-prune/v1"), "generated_at": z.string().datetime({ offset: true }), "repository": z.string().min(1), "source_report": z.union([z.string().regex(new RegExp("^\\d{8}T\\d{12}Z\\.json$")), z.null()]), "applied": z.boolean(), "decisions": z.array(z.object({ "branch": z.string().regex(new RegExp("^origin/.+")), "decision": z.enum(["delete","keep"]), "reason_code": z.enum(["DELETE_MERGED","KEEP_PROTECTED","KEEP_ALREADY_GONE","KEEP_NOT_MERGED"]), "message": z.string().min(1), "outcome": z.enum(["planned","deleted","failed","not_applicable"]) }).strict().describe("What was decided about one remote branch, why, and what happened.")), "verdict": z.enum(["pass","fail","unknown"]) }).strict().describe("One pruning run: the plan or its execution, recorded as data.")

