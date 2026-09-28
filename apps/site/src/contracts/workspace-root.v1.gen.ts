// apps/site/src/contracts/workspace-root.v1.gen.ts
// GENERATED from contracts/json/workspace-root.v1.schema.json by otsafety_tooling.contracts.zod.
// Do not edit: change the Pydantic model and run mise run contracts:generate.
import { z } from "zod";

export const workspaceRootV1Schema = z.object({ "tool": z.object({ "uv": z.object({ "workspace": z.object({ "members": z.array(z.string()).min(1) }).describe("Which directories uv resolves as local editable packages.") }).describe("The uv table, of which only the workspace is read here."), "ruff": z.object({ "src": z.array(z.string()).min(1) }).describe("Ruff's first-party source roots.\n\nA MEMBER MISSING FROM src READS AS THIRD PARTY, so its own imports sort\ninto the wrong block and the formatter rewrites them on every run.") }).describe("The tool table of the workspace root.") }).describe("The virtual root: members and the settings they share.");
