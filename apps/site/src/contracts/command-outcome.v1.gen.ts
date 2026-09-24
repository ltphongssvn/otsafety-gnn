// GENERATED from contracts/json/command-outcome.v1.schema.json by otsafety_tooling.contracts.zod.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod";

export const commandOutcomeV1Schema = z.strictObject({ "contract": z.literal("command-outcome/v1"), "command": z.string().min(1), "outcome": z.enum(["success", "refused", "failed"]), "code": z.string().regex(new RegExp("^[a-z][a-z0-9_]*$")), "message": z.string().min(1), "data": z.record(z.string(), z.json()) }).describe("One command's result: the only thing it writes to stdout.");
