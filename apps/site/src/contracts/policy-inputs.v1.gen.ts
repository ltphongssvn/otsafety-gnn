// GENERATED from contracts/json/policy-inputs.v1.schema.json by otsafety_tooling.contracts.zod.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod";

export const policyInputsV1Schema = z.strictObject({ "contract": z.string(), "inputs": z.array(z.strictObject({ "path": z.string(), "why": z.string(), "generated": z.union([z.string(), z.null()]) }).describe("One file the policy reads, and how it comes to exist.")) }).describe("The whole input set: the source the task, the probe and the Rego read.");
