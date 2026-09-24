// GENERATED from contracts/json/command-inventory.v1.schema.json by otsafety_tooling.contracts.zod.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod";

export const commandInventoryV1Schema = z.strictObject({ "contract": z.string(), "commands": z.array(z.strictObject({ "module": z.string(), "emits": z.boolean(), "exempt_because": z.union([z.string(), z.null()]) }).describe("One command: where it lives, whether it emits an envelope, and why not.")) }).describe("Every command found in the tree, for the policy to judge.");
