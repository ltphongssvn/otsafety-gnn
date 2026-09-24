// GENERATED from contracts/json/project-settings.v1.schema.json by otsafety_tooling.contracts.zod.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod";

export const projectSettingsV1Schema = z.object({ "OTSAFETY_ARTIFACTS": z.union([z.string(), z.null()]).default(null).describe("Evidence root override."), "WANDB_MODE": z.enum(["online", "offline", "disabled"]).default("offline"), "WANDB_PROJECT": z.union([z.string(), z.null()]).default(null), "WANDB_ENTITY": z.union([z.string(), z.null()]).default(null), "WANDB_API_KEY": z.union([z.string(), z.null()]).default(null), "WANDB_DIR": z.union([z.string(), z.null()]).default(null) });
