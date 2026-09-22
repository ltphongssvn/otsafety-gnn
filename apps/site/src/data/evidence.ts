// apps/site/src/data/evidence.ts
// EVIDENCE, READ FROM THE REPOSITORY AT BUILD TIME.
//
// .artifacts/ is ignored by git on purpose: records are produced by running the
// project, not authored. So the site reads whatever the machine that builds it
// has recorded, and renders an explicit empty state when there is nothing --
// never a silent blank, which looks identical to a broken query.
//
// A MALFORMED RECORD FAILS THE BUILD -- now true. It was claimed here and on the
// page while each file was cast with `as T`, which checks nothing: the settings
// type named four fields the contract does not have, and production rendered the
// real failing verdict with no date and blank findings. Every record is parsed
// with Zod generated from the Pydantic contract, so a mismatch stops the build
// with the file's path, and the types below are derived, never written.
import { projectSettingsV1Schema } from "../contracts/project-settings.v1.gen";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import { z } from "zod";
import { repositorySettingsCheckV1Schema } from "../contracts/repository-settings-check.v1.gen";
import { runRecordV1Schema } from "../contracts/run-record.v1.gen";

// src/data -> src -> apps/site -> apps -> repository root. The empty state
// rendered instead of records because this was one level short, and an empty
// directory and a wrong path produce the same page.
// OTSAFETY_ARTIFACTS OVERRIDES THE EVIDENCE ROOT, and the test build sets it.
// Without it the acceptance tests seeded fixtures into the real .artifacts/ --
// seven fabricated experiment records landed there, and every later local build
// of /results would have shown them as measured. It is also what makes the tests
// hermetic: they had seeded only when a folder was empty, so on CI the page
// showed fixtures and on a machine with real experiments it showed real data,
// and the same test asserted against different data on different machines.
// THE ENVIRONMENT IS A TRUST BOUNDARY, parsed through Zod generated from the one
// settings model; OTSAFETY_ARTIFACTS is defined once, in Pydantic.
const environment = projectSettingsV1Schema.parse(process.env);

export const ARTIFACTS =
  environment.OTSAFETY_ARTIFACTS ??
  new URL("../../../../../.artifacts", import.meta.url).pathname;

export type RunRecord = z.infer<typeof runRecordV1Schema>;
export type SettingsCheck = z.infer<typeof repositorySettingsCheckV1Schema>;

// THE TRUST BOUNDARY. Files on disk are input, whoever wrote them.
export function readRecords<S extends z.ZodType>(name: string, schema: S): z.infer<S>[] {
  const dir = join(ARTIFACTS, name);
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((f) => f.endsWith(".json"))
    .sort()
    .reverse()
    .map((f) => {
      const path = join(dir, f);
      const parsed = schema.safeParse(JSON.parse(readFileSync(path, "utf-8")));
      if (!parsed.success) {
        throw new Error(`${path} does not match its contract:\n${z.prettifyError(parsed.error)}`);
      }
      return parsed.data;
    });
}

export const runs = (): RunRecord[] => readRecords("runs", runRecordV1Schema);
export const settingsChecks = (): SettingsCheck[] =>
  readRecords("repo-settings", repositorySettingsCheckV1Schema);
