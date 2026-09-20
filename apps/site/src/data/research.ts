// apps/site/src/data/research.ts
// THE LADDER, THE DATA AND THE STACK, AS TYPED DATA.
// Rungs carry the model that occupies them, because "we compare several
// baselines" is not a falsifiable method: the first rung that is NOT beaten is
// the research answer, so a rung with no named model cannot be checked.

export type Rung = {
  n: string; name: string; asks: string;
  models: string; answers: string; ifNotBeaten: string;
};

export const RUNGS: Rung[] = [
  { n: "0", name: "Base rate", asks: "What does guessing the prior achieve?",
    models: "A prevalence constant, equivalent to sklearn DummyClassifier(strategy=\"prior\")",
    answers: "—",
    ifNotBeaten: "Anchors average precision. Anything not beating it is noise." },
  { n: "1", name: "Degree-only null", asks: "Does simple popularity explain performance?",
    models: "sklearn LogisticRegression on log1p(per-relation degree). No biology, no relations, no message passing.",
    answers: "Q1",
    ifNotBeaten: "The graph encodes study attention, not safety biology. The project returns a negative result, and that is a real finding." },
  { n: "2", name: "Non-graph model", asks: "Do target features alone explain performance?",
    models: "sklearn HistGradientBoostingClassifier and a tabular MLP on target annotations only: GTEx expression breadth, gnomAD pLI and LOEUF, protein family, subcellular localisation. Zero graph structure.",
    answers: "Q2",
    ifNotBeaten: "The graph adds nothing. Ship the cheaper tabular model and close the project." },
  { n: "2b", name: "Graph-topology GBM", asks: "Do hand-computed graph statistics suffice?",
    models: "sklearn HistGradientBoostingClassifier on personalised PageRank to known-risky targets, betweenness, k-core, clustering, degree. Graph-derived, but no learned representation.",
    answers: "Q2",
    ifNotBeaten: "A published comparator of this family reached ROC-AUC around 0.71 on target-level safety attrition. That is the bar a GNN must clear." },
  { n: "3", name: "Shallow KGE", asks: "Does embedding entities suffice, without message passing?",
    models: "PyKEEN ComplEx and PyKEEN RotatE: relation-typed scoring functions with no neighbourhood aggregation.",
    answers: "Q3",
    ifNotBeaten: "Relation-typed embedding is what helps; aggregation is not." },
  { n: "4", name: "Relation-agnostic GNN", asks: "Does connectivity alone help?",
    models: "PyG GraphSAGE (SAGEConv) and PyG GAT (GATConv) over a collapsed single adjacency, with edge types deliberately discarded.",
    answers: "Q3",
    ifNotBeaten: "The control that isolates relation types. Without it, no claim about relationships can be made at all." },
  { n: "5", name: "Relation-aware GNN", asks: "Do relation TYPES add information?",
    models: "PyG R-GCN (RGCNConv), CompGCN and PyG HGT (HGTConv), with a degree-offset head and a gradient-reversal adversary.",
    answers: "Q3",
    ifNotBeaten: "The difference between this rung and rung 4 IS the research answer. If it is near zero, connectivity matters and relation types do not." },
];

export const LADDER_RULE =
  "Every rung runs on the same split, the same negatives, the same endpoints, " +
  "and at least five seeds with bootstrap confidence intervals. One seed cannot " +
  "resolve a 0.02 difference in average precision, and most reported wins on " +
  "biomedical knowledge graphs sit inside that band.";

export type Source = {
  name: string; role: string; licence: string; open: boolean;
};

export const SOURCES: Source[] = [
  { name: "Open Targets Platform", open: true,
    role: "The substrate. Quarterly Parquet releases, jointly maintained by EMBL-EBI, the Sanger Institute and industry partners, carrying the target-safety widget that draws on ToxCast, AOPWiki and ClinPGx.",
    licence: "Open, redistributable. Pinned by release version and content hash in the run record." },
  { name: "Hetionet / PrimeKG", open: true,
    role: "Secondary graphs, used to replicate whatever result Open Targets gives on a different construction of the same biology.",
    licence: "Open, redistributable." },
  { name: "MedDRA", open: false,
    role: "The adverse-event terminology. FAERS reaction fields carry MedDRA preferred-term strings, and its hierarchy is what groups them into organ classes.",
    licence: "Proprietary, distributed under MSSO licence. The hierarchy and the Standardised MedDRA Queries CANNOT be redistributed, so this repository ships neither. The endpoint DAG is loaded from EFO, MONDO and HPO instead, and a licensed hierarchy can be mounted by a subscriber without any other change." },
  { name: "FAERS", open: true,
    role: "Spontaneous adverse-event reports, used only through indication-stratified disproportionality with a noisy-OR deconvolution onto targets.",
    licence: "Public. Confounded by indication by construction, which is why the crude and adjusted estimates are both reported." },
];

export type Tool = { name: string; version: string; why: string };

export const TOOLCHAIN: Tool[] = [
  { name: "uv", version: "0.12.7", why: "Python packaging and the interpreter itself, installed from the vendor's own release artifact." },
  { name: "bun", version: "1.4.2", why: "The JavaScript runtime and package manager. No Node is pinned, and none is needed." },
  { name: "gh", version: "2.101.0", why: "Every GitHub operation, reached through the tooling package rather than typed by hand." },
  { name: "mise", version: "2026.9.9", why: "The task runner. Every project operation is a task, on every environment." },
];

export const STACK_NOTE =
  "toolchain.json is the one declaration of executable versions: each entry is " +
  "the vendor's own release artifact for both aarch64-darwin and x86_64-linux, " +
  "with the sha256 that release published. nix flake check builds every tool, " +
  "runs it, and asserts the version it reports equals that file, so a wrong " +
  "artifact fails at check time rather than surfacing later as a confusing " +
  "difference between machines.";

export const RUNTIME = [
  { layer: "Site", what: "Astro 7.3.3 with React islands, static output, built by bun." },
  { layer: "Pipeline", what: "Python 3.13.15, PyTorch Geometric for the graph models, PyKEEN for the embedding rungs." },
  { layer: "Gates", what: "ruff, strict mypy on both platforms, pytest, typos, zizmor." },
  { layer: "Environments", what: "This laptop, GitHub Actions, and Lightning AI. Nix on the laptop; MISE_ENV=ood where Nix is not available." },
];
