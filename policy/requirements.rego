# An id is one object: the step, what justifies it, what proves it, who claims it.
package policy

matrix := d.contents if {
	some d in input
	endswith(d.path, "policy/requirement-matrix.json")
}

ledger := d.contents if {
	some d in input
	endswith(d.path, "context/plan-ids.yaml")
}

issued contains entry.id if some entry in ledger.issued

retired contains entry.id if {
	some entry in ledger.issued
	entry.retired
}

steps contains row if {
	some row in matrix.requirements
	row.kind == "step"
}

# THE ID IS THE JOIN KEY IN THE CODE, not only in the plan: the file that proves a
# step must CLAIM it, through the registered requirement marker. A mention is not
# a claim -- one id appeared in a file that told its story and not in the test that
# proves it -- so the proof and the constraint cannot drift apart unnoticed.
proves(row) if {
	some path in row.named_in
	some evidence in row.evidence
	endswith(evidence, path)
}

deny contains msg if {
	some row in steps
	count(row.evidence) == 0
	msg := sprintf("%s: a step with no evidence is a claim with nothing to prove it", [row.id])
}

deny contains msg if {
	some row in steps
	count(row.justified_by) == 0
	msg := sprintf("%s: nothing in the trace justifies this step", [row.id])
}

deny contains msg if {
	some orphan in matrix.orphan_candidates
	msg := sprintf("plan-trace.yaml: %s maps to an id that is not in the plan", [orphan])
}

deny contains msg if {
	some row in matrix.requirements
	not row.id in issued
	msg := sprintf("%s: used in the plan but never issued in context/plan-ids.yaml", [row.id])
}

deny contains msg if {
	some row in matrix.requirements
	row.id in retired
	msg := sprintf("%s: retired in the ledger, yet still in the plan; an id is never reused", [row.id])
}

deny contains msg if {
	some row in steps
	count(row.claimed_by) > 0
	not proves(row)
	msg := sprintf("%s: claimed done, but no file of its evidence names it", [row.id])
}
