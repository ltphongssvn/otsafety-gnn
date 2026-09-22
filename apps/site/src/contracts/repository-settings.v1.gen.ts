// GENERATED from contracts/json/repository-settings.v1.schema.json by scripts/generate-contracts.ts.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod"

export const repositorySettingsV1Schema = z.object({ "$comment": z.string().default(""), "contract": z.literal("repository-settings/v1"), "settings": z.object({ "allow_merge_commit": z.boolean(), "allow_squash_merge": z.boolean(), "allow_rebase_merge": z.boolean(), "allow_auto_merge": z.boolean(), "delete_branch_on_merge": z.boolean() }).strict().describe("The merge policy: merge commits only, and merged branches deleted.") }).strict().describe("contracts/repository-settings.json, as committed.")

