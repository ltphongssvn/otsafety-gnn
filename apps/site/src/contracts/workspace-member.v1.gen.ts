// apps/site/src/contracts/workspace-member.v1.gen.ts
// GENERATED from contracts/json/workspace-member.v1.schema.json by otsafety_tooling.contracts.zod.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod";

export const workspaceMemberV1Schema = z.object({ "project": z.object({ "name": z.string().min(1), "version": z.string().min(1), "requires-python": z.string().min(2) }).describe("What a member says about itself.") }).describe("A workspace member's own pyproject.");
