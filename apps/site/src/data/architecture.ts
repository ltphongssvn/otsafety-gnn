// apps/site/src/data/architecture.ts
// THE NINE LAYERS AND THE THREE NESTED QUESTIONS, AS DATA.
// The PDF is generated from the same tables in scripts/build_arch_onepager.py.
// Holding them here as typed data rather than as prose means the page and the
// PDF cannot drift into disagreeing about what the project is.

export type Layer = {
  n: string; name: string; question: string;
  failure: string; guard: string; added: boolean;
};

export const LAYERS: Layer[] = [
  { n: "1", name: "REALITY", added: false,
    question: "Does modulating target T actually cause endpoint E?",
    failure: "On-target biology conflated with drug pharmacology.",
    guard: "unresolvable; declared in the model card" },
  { n: "2", name: "SELECTION", added: true,
    question: "Which truths ever get the chance to become evidence?",
    failure: "Degree bias and confounding by indication are born here, not in the model.",
    guard: "audit/degree.py \u00b7 data/attribution.py" },
  { n: "3", name: "EVIDENCE", added: false,
    question: "What have we actually observed?",
    failure: "Undated edges admitted, making temporal claims unverifiable.",
    guard: "data/ingest.py" },
  { n: "4", name: "ATTRIBUTION", added: true,
    question: "Drug-level observation to target-level claim. Which target did it?",
    failure: "Uniform propagation makes the label a function of target degree.",
    guard: "data/attribution.py \u2014 noisy-OR + Mantel-Haenszel" },
  { n: "5", name: "LABELING RULE", added: false,
    question: "How do we interpret the evidence?",
    failure: "Unlabelled silently treated as negative; tiers pooled.",
    guard: "data/labels.py \u2014 three states, tiers never pooled" },
  { n: "6", name: "DATASET LABEL", added: false,
    question: "positive / earned-negative / unlabelled, per tier",
    failure: "Multiaxiality corrupts the label matrix.",
    guard: "data/ontology.py \u00b7 models/hierarchy.py" },
  { n: "7", name: "SPLIT", added: true,
    question: "Which labels does the model see, and which is it tested on?",
    failure: "An interpolation split behind an extrapolation claim.",
    guard: "data/splits.py \u00b7 audit/leakage.py" },
  { n: "8", name: "MODEL", added: false,
    question: "What can the GNN learn from it?",
    failure: "A popularity detector with an excellent AUROC.",
    guard: "models/hetero_gnn.py \u2014 degree offset, partial rho" },
  { n: "9", name: "VERDICT", added: true,
    question: "Promote or reject? At what operating point, on what evidence?",
    failure: "A score shipped where a decision was required.",
    guard: "eval/metrics.py \u00b7 pipeline.py" },
];

export type NestedQuestion = {
  id: string; question: string; contrast: string; whenTied: string;
};

// STATED IN FULL, NEVER AS A BARE LABEL. The PDF's first draft named Q2 and Q3
// in a panel and defined them nowhere.
export const QUESTIONS: NestedQuestion[] = [
  { id: "Q1", question: "Is there any signal beyond node popularity?",
    contrast: "GNN vs a degree-only null: logistic regression on log-degree, no biology, no relations.",
    whenTied: "The knowledge graph encodes study attention, not safety biology." },
  { id: "Q2", question: "Does the graph help beyond non-graph target features?",
    contrast: "GNN vs a tabular model on target annotations only: expression breadth, pLI and LOEUF, protein family.",
    whenTied: "Graph structure adds nothing. Ship the cheaper tabular model." },
  { id: "Q3", question: "Do the relation TYPES carry the signal?",
    contrast: "Relation-aware (R-GCN, CompGCN, HGT) vs relation-agnostic (GraphSAGE, GAT on a collapsed adjacency).",
    whenTied: "Connectivity matters; relationships per se do not. This is the literal research question." },
];
