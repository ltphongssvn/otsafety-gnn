# policy/requirements.rego
# An id is one object: the step, what justifies it, what proves it, who claims it.
# G.41: this file is that step's evidence, and carries its id so the inspection
# rule below can confirm the link rather than assume it.
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

# A LINK IS NOT VERIFIED UNTIL THE EVIDENCE ITSELF IS CONFIRMED. The builder
# confirms each entry by its kind -- a test file claims the id through its marker,
# any other file contains it, by inspection -- and reports what it could not.
deny contains msg if {
	some row in steps
	count(row.claimed_by) > 0
	count(row.unconfirmed) > 0
	msg := sprintf("%s: claimed done, but its evidence is unconfirmed: %v", [row.id, row.unconfirmed])
}
