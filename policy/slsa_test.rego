# policy/slsa_test.rego
# The Source Level rule denies what it describes, exercised from outside.
package policy_test

import data.policy

slsa_record(fields) := [{"path": "/a/policy/slsa-source.json", "contents": fields}]

slsa_at_level(level) := slsa_record({
	"contract": "slsa-source/v1",
	"revision": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
	"level": level,
	"observed": {
		"version_controlled": true,
		"history_immutable": true,
		"provenance_per_revision": false,
		"controls_enforced": true,
		"two_party_review": false,
	},
	"unmet": ["no provenance is produced for each revision"],
})

# AN ABSENT SIGNAL READS AS NOT DETECTED, which would make a rule written to
# deny on detection allow instead. Deleting the record must fail the gate.
test_a_missing_slsa_record_is_denied if {
	"slsa-source.json: missing; run mise run slsa:source" in policy.deny with input as []
}

test_a_level_below_the_declared_floor_is_denied if {
	denied := policy.deny with input as slsa_at_level(0)
	some msg in denied
	startswith(msg, "slsa-source.json: level 0 is below the declared floor")
}

# A RECORD WITH NO LEVEL IS NOT A RECORD AT LEVEL ZERO. An expression over an
# absent field is undefined, and an undefined deny body does not fire -- which
# is how a policy gate becomes a rubber stamp.
test_a_record_stating_no_level_is_denied if {
	denied := policy.deny with input as slsa_record({"contract": "slsa-source/v1"})
	"slsa-source.json: states no level, so nothing was measured" in denied
}

test_a_record_naming_no_revision_is_denied if {
	denied := policy.deny with input as slsa_record({"contract": "slsa-source/v1", "level": 1})
	"slsa-source.json: names no revision, so it binds to nothing" in denied
}

# THE DECISION MUST AGREE WITH WHAT IT OBSERVED, or the record cannot be
# re-derived -- which is the point of carrying the observation at all.
test_a_level_disagreeing_with_its_observation_is_denied if {
	denied := policy.deny with input as slsa_at_level(4)
	some msg in denied
	startswith(msg, "slsa-source.json: claims level 4")
}

# THE CONTROL: a rule that denied everything would satisfy every test above.
test_the_measured_level_is_accepted if {
	denied := policy.deny with input as slsa_at_level(1)
	every msg in denied {
		not startswith(msg, "slsa-source.json")
	}
}
