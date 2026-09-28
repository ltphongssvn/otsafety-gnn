// apps/site/src/contracts/data-sources.v1.gen.ts
// GENERATED from contracts/json/data-sources.v1.schema.json by otsafety_tooling.contracts.zod.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod";

export const dataSourcesV1Schema = z.strictObject({ "contract": z.string().regex(new RegExp("^data-sources/v1$")), "sources": z.array(z.strictObject({ "id": z.string().regex(new RegExp("^[a-z][a-z0-9-]*$")), "name": z.string().min(2), "role": z.string().min(40), "licence": z.string().min(20), "open": z.boolean(), "withheld": z.array(z.string()), "release": z.union([z.string(), z.null()]) }).describe("One data source and the terms under which this project may use it.")).min(1) }).describe("Every source this project reads, with its terms.");
