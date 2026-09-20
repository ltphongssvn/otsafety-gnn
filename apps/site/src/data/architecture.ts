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

export const RESEARCH_QUESTION =
  "Do the typed relationships in a public, open-source biomedical knowledge graph " +
  "carry information that predicts drug-safety endpoints for protein targets \u2014 " +
  "over and above what is predictable from the graph's bare connectivity statistics, " +
  "and from target-level features that require no graph at all?";

export const RESEARCH_QUESTION_NOTE =
  "The operative word in the brief is whether: this is a feasibility question with an " +
  "admissible negative answer, not a maximise-the-metric question. The second is " +
  "relationships: the brief does not ask whether a neural network can predict safety, " +
  "but whether relational structure is what does the predicting.";

export const CENTRAL_GOAL =
  "Establish, under a leakage- and confound-controlled protocol, whether relation-aware " +
  "graph learning over a public biomedical knowledge graph yields a usable target-safety " +
  "prioritisation signal \u2014 and quantify how much of any observed performance is " +
  "attributable to the relationships, as opposed to node popularity or non-graph target " +
  "biology. The deliverable is a defensible answer plus its evidence, in either direction.";

export const ML_OBJECTIVE = [
  "Let the knowledge graph be a heterogeneous graph G = (V, E, R) with typed nodes and " +
    "typed edges. Let T be the protein targets and S the safety endpoints.",
  "Task: learn f : T \u00d7 S \u2192 [0,1], the probability that modulating target t is " +
    "associated with endpoint s.",
  "This is multi-label prediction over the target \u00d7 endpoint slice, not a binary " +
    "\"is this target risky\". The brief says endpoints, plural, and organ-class structure " +
    "is the clinically meaningful unit; a single collapsed label answers a different question.",
  "Evaluation: held-out target\u2013endpoint pairs under a temporal split \u2014 train on " +
    "the graph as of cutoff \u03c4, predict associations that became knowable after it \u2014 " +
    "plus a target-disjoint cold-start split.",
];

export type ScopeSection = { heading: string; items: string[] };

export const SCOPE: ScopeSection[] = [
  { heading: "In scope", items: [
    "Public, open-source knowledge graphs only. Open Targets is primary: it carries the " +
      "target-safety widget drawing on ToxCast, AOPWiki and ClinPGx.",
    "Hetionet and PrimeKG as secondary graphs, to replicate whatever result Open Targets gives.",
    "AstraZeneca BIKG is the architectural reference only. It is internal and is not usable as data.",
  ]},
  { heading: "Out of scope", items: [
    "Molecular structure prediction",
    "Compound-level toxicity from chemistry",
    "Clinical decision support",
    "Anything requiring non-public data",
  ]},
];

export const SCOPE_NOTE =
  "Secondary check required by the specification: the brief says \"important biomedical " +
  "endpoints, with a particular focus on drug safety\". That phrasing requires the method to " +
  "be endpoint-agnostic, so the same pipeline is run once on a non-safety endpoint \u2014 " +
  "target\u2013disease association \u2014 to test whether any success is method-general or " +
  "safety-specific.";
