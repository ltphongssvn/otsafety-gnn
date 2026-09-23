# Each denial fires on the input it describes, exercised from outside the policy.
package policy_test

import data.policy

world(requirements, orphans, issued) := [
	{
		"path": "/a/policy/requirement-matrix.json",
		"contents": {"requirements": requirements, "orphan_candidates": orphans},
	},
	{"path": "/a/context/plan-ids.yaml", "contents": {"issued": issued}},
]

row(overrides) := object.union(
	{
		"id": "G.1", "title": "x", "thread": "G", "phase": "8G", "kind": "step",
		"evidence": ["path:tooling/tests/test_g1.py"], "justified_by": ["a finding"],
		"named_in": ["tooling/tests/test_g1.py"], "referenced_by": [], "claimed_by": [],
	},
	overrides,
)

test_a_step_without_evidence_is_denied if {
	denied := policy.deny with input as world([row({"evidence": []})], [], [{"id": "G.1"}])
	some msg in denied
	contains(msg, "no evidence")
}

test_an_unjustified_step_is_denied if {
	denied := policy.deny with input as world([row({"justified_by": []})], [], [{"id": "G.1"}])
	some msg in denied
	contains(msg, "nothing in the trace justifies")
}

test_an_orphan_observation_is_denied if {
	denied := policy.deny with input as world([row({})], ["a finding -> G.99"], [{"id": "G.1"}])
	some msg in denied
	contains(msg, "not in the plan")
}

test_an_id_never_issued_is_denied if {
	denied := policy.deny with input as world([row({})], [], [{"id": "G.2"}])
	"G.1: used in the plan but never issued in context/plan-ids.yaml" in denied
}

test_a_retired_id_back_in_the_plan_is_denied if {
	denied := policy.deny with input as world([row({})], [], [{"id": "G.1", "retired": true}])
	some msg in denied
	contains(msg, "never reused")
}

test_a_claim_whose_evidence_does_not_name_it_is_denied if {
	claimed := row({"claimed_by": ["abc123456"], "named_in": ["tooling/tests/test_other.py"]})
	denied := policy.deny with input as world([claimed], [], [{"id": "G.1"}])
	some msg in denied
	contains(msg, "no file of its evidence names it")
}

# NOT count(deny) == 0: deny is the whole package, and a world of two inputs also
# denies the six that are missing. What this asserts is that nothing is denied
# ABOUT THIS REQUIREMENT.
test_a_complete_requirement_is_accepted if {
	denied := policy.deny with input as world([row({"claimed_by": ["abc123456"]})], [], [{"id": "G.1"}])
	every msg in denied {
		not contains(msg, "G.1")
	}
}
