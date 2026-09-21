// apps/site/src/data/evidence.ts
// EVIDENCE, READ FROM THE REPOSITORY AT BUILD TIME.
//
// .artifacts/ is ignored by git on purpose: records are produced by running the
// project, not authored. So the site reads whatever the machine that builds it
// has recorded, and renders an explicit empty state when there is nothing --
// never a silent blank, which looks identical to a broken query.
//
// A MALFORMED RECORD FAILS THE BUILD. Reading files here rather than through an
// API means a record that does not match its contract stops the deploy instead
// of returning a 500 to a reader.
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";

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
export const ARTIFACTS =
  process.env.OTSAFETY_ARTIFACTS ??
  new URL("../../../../../.artifacts", import.meta.url).pathname;

export type RunRecord = {
  contract: string; id: string; task: string; arguments: string[];
  started_at: string; duration_ms: number; exit_code: number;
  outcome: string; repository: string; branch: string; commit: string;
  output_bytes: number; output_sha256: string; truncated: boolean;
};

export type SettingsFinding = { rule: string; code: string; detail: string };

export type SettingsCheck = {
  contract: string; verdict: string; repository: string;
  findings: SettingsFinding[]; recorded_at: string;
};

function readDir<T>(name: string): T[] {
  const dir = join(ARTIFACTS, name);
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((f) => f.endsWith(".json"))
    .sort()
    .reverse()
    .map((f) => JSON.parse(readFileSync(join(dir, f), "utf-8")) as T);
}

export const runs = (): RunRecord[] => readDir<RunRecord>("runs");
export const settingsChecks = (): SettingsCheck[] =>
  readDir<SettingsCheck>("repo-settings");
