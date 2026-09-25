// apps/site/src/contracts/in-toto-statement.v1.gen.ts
// GENERATED from contracts/json/in-toto-statement.v1.schema.json by otsafety_tooling.contracts.zod.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod";

export const inTotoStatementV1Schema = z.strictObject({ "_type": z.literal("https://in-toto.io/Statement/v1"), "subject": z.array(z.strictObject({ "name": z.string().min(1), "digest": z.strictObject({ "sha256": z.string().regex(new RegExp("^[0-9a-f]{64}$")) }).describe("How a subject is bound: by content, not by name.\n\nSHA-256 IS REQUIRED AND NOT MERELY ALLOWED. An empty digest map validates\nagainst a looser schema and binds the attestation to nothing at all.") }).describe("One artifact this attestation is about.")).min(1), "predicateType": z.string().regex(new RegExp("^https://\\S+$")), "predicate": z.record(z.string(), z.string()).refine((value) => Object.keys(value).length >= 1, { message: "at least 1 entries" }) }).describe("The claim: these artifacts, this predicate type, this content.");
