// GENERATED from contracts/json/id-ledger.v1.schema.json by otsafety_tooling.contracts.zod.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod";

export const idLedgerV1Schema = z.strictObject({ "contract": z.literal("id-ledger/v1"), "issued": z.array(z.strictObject({ "id": z.string().regex(new RegExp("^[A-Z0-9]+\\.[A-Za-z0-9]+$")), "first_title": z.string().min(1), "retired": z.boolean() }).describe("One identifier, issued once. Retired ids stay here so none is ever reused.")).min(1) }).describe("context/plan-ids.yaml: append-only. An id leaves this file only by being retired.");
