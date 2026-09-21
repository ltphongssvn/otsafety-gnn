// GENERATED from contracts/json/repository-settings-check.v1.schema.json by scripts/generate-contracts.ts.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod"

export const repositorySettingsCheckV1Schema = z.object({ "contract": z.literal("repository-settings-check/v1"), "generated_at": z.string().datetime({ offset: true }), "repository": z.string().min(1), "findings": z.array(z.object({ "rule_id": z.enum(["S001","S002","S003"]), "reason_code": z.string(), "message": z.string().min(1), "setting": z.union([z.enum(["allow_merge_commit","allow_squash_merge","allow_rebase_merge","allow_auto_merge","delete_branch_on_merge"]), z.null()]), "expected": z.union([z.boolean(), z.null()]), "observed": z.union([z.boolean(), z.null()]) }).strict().describe("One reason the repository does not match its declared settings.")), "verdict": z.enum(["pass","fail","unknown"]) }).strict().describe("One settings check, recorded as data.")

