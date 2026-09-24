// GENERATED from contracts/json/requirement-matrix.v1.schema.json by otsafety_tooling.contracts.zod.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod";

export const requirementMatrixV1Schema = z.strictObject({ "contract": z.literal("requirement-matrix/v1"), "ref": z.string().min(1), "requirements": z.array(z.strictObject({ "id": z.string(), "title": z.string(), "thread": z.string(), "phase": z.string(), "kind": z.enum(["step", "decision"]), "evidence": z.array(z.string()), "justified_by": z.array(z.string()), "named_in": z.array(z.string()), "referenced_by": z.array(z.string()), "claimed_by": z.array(z.string()), "unconfirmed": z.array(z.string()) }).describe("One row of the matrix: everything that hangs off one id.")).min(1), "orphan_candidates": z.array(z.string()) }).describe("Generated from the plan, its trace, the tree and the commits: never written by hand.");
