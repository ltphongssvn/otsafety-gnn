// apps/site/src/data/architecture.ts
// THE NINE LAYERS AND THE THREE NESTED QUESTIONS, AS DATA.
// The PDF is generated from the same tables in scripts/build_arch_onepager.py.
// Holding them here as typed data rather than as prose means the page and the
// PDF cannot drift into disagreeing about what the project is.




// STATED IN FULL, NEVER AS A BARE LABEL. The PDF's first draft named Q2 and Q3
// in a panel and defined them nowhere.

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



export const SCOPE_NOTE =
  "Secondary check required by the specification: the brief says \"important biomedical " +
  "endpoints, with a particular focus on drug safety\". That phrasing requires the method to " +
  "be endpoint-agnostic, so the same pipeline is run once on a non-safety endpoint \u2014 " +
  "target\u2013disease association \u2014 to test whether any success is method-general or " +
  "safety-specific.";
