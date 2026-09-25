// apps/site/src/content.config.ts
// G.20: every context and conf file reaches the site through the contracts
// pipeline, as a content collection validated by the Zod generated from the same
// Pydantic model that validated the YAML on the way out.
//
// ONE SOURCE, CHECKED ON BOTH SIDES. The plan, its trace, the ledger and the
// exemption register were read by Python alone, and the site restated parts of
// them in hand-written TypeScript. Now Python validates each file against its
// model and writes it as JSON; Astro loads that JSON and checks it again with
// the generated schema, so neither side can drift without a gate saying so.
//
// WHY A PARSER PER COLLECTION. file() parses JSON natively, but each document is
// nested -- plan.json holds threads, phases, loops, steps and decisions -- and
// file() wants an array of entries carrying a unique id. The parser names which
// array, which is the documented use of it.
import { defineCollection } from "astro:content";
import { file } from "astro/loaders";
import { projectPlanV1Schema } from "./contracts/project-plan.v1.gen";
import { planTraceV1Schema } from "./contracts/plan-trace.v1.gen";
import { idLedgerV1Schema } from "./contracts/id-ledger.v1.gen";
import { exemptionRegisterV1Schema } from "./contracts/exemption-register.v1.gen";
import { architectureV1Schema } from "./contracts/architecture.v1.gen";

const PLAN = "src/content/plan.json";

const threads = defineCollection({
  loader: file(PLAN, { parser: (text) => projectPlanV1Schema.parse(JSON.parse(text)).threads }),
});

const phases = defineCollection({
  loader: file(PLAN, { parser: (text) => projectPlanV1Schema.parse(JSON.parse(text)).phases }),
});

const steps = defineCollection({
  loader: file(PLAN, { parser: (text) => projectPlanV1Schema.parse(JSON.parse(text)).steps }),
});

const decisions = defineCollection({
  loader: file(PLAN, { parser: (text) => projectPlanV1Schema.parse(JSON.parse(text)).decisions }),
});

const candidates = defineCollection({
  loader: file("src/content/plan-trace.json", {
    // A candidate has no id of its own: its ref is unique within its source.
    parser: (text) =>
      planTraceV1Schema
        .parse(JSON.parse(text))
        .candidates.map((candidate, index) => ({ id: String(index), ...candidate })),
  }),
});

const issued = defineCollection({
  loader: file("src/content/plan-ids.json", {
    parser: (text) => idLedgerV1Schema.parse(JSON.parse(text)).issued,
  }),
});

const exemptions = defineCollection({
  loader: file("src/content/exemptions.json", {
    // Three kinds in one register, each keyed by what it exempts.
    parser: (text) => {
      const register = exemptionRegisterV1Schema.parse(JSON.parse(text));
      return [
        ...register.scoped.map((entry) => ({ id: "scoped:" + entry.glob, ...entry })),
        ...register.inline.map((entry) => ({ id: "inline:" + entry.path + ":" + entry.rule, ...entry })),
        ...register.eslint.map((entry) => ({ id: "eslint:" + entry.path, ...entry })),
      ];
    },
  }),
});

const ARCHITECTURE = "src/content/architecture.json";

const layers = defineCollection({
  schema: architectureV1Schema.shape.layers.element,
  loader: file(ARCHITECTURE, {
    parser: (text) =>
      architectureV1Schema.parse(JSON.parse(text)).layers,
  }),
});

const questions = defineCollection({
  schema: architectureV1Schema.shape.questions.element,
  loader: file(ARCHITECTURE, {
    parser: (text) =>
      architectureV1Schema.parse(JSON.parse(text)).questions,
  }),
});

const rungs = defineCollection({
  schema: architectureV1Schema.shape.rungs.element,
  loader: file(ARCHITECTURE, {
    parser: (text) =>
      architectureV1Schema.parse(JSON.parse(text)).rungs,
  }),
});

const stages = defineCollection({
  schema: architectureV1Schema.shape.stages.element,
  loader: file(ARCHITECTURE, {
    parser: (text) =>
      architectureV1Schema
        .parse(JSON.parse(text))
        .stages,
  }),
});

export const collections = {
  threads,
  phases,
  steps,
  decisions,
  candidates,
  issued,
  exemptions,
  layers,
  questions,
  rungs,
  stages,
};
