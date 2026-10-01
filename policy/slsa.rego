# policy/slsa.rego
# G.85: proves this step of the plan.
#
# THE SLSA SOURCE LEVEL THIS REPOSITORY MEASURED OF ITSELF. SLSA v1.2 approved
# the Source Track in November 2025 and requires an attestation to state the
# level of any revision at L1 or above. This judges the decision record that
# measurement writes: that it exists, that it binds to a revision, that it
# states a level, that the level agrees with what was observed, and that it is
# not below the floor this repository declares.
#
# NO METADATA BLOCK HERE. A package-scoped annotation may be declared once per
# package across every file, and inputs.rego already carries this package's.
package policy

# THE FLOOR, DECLARED RATHER THAN ASSUMED. L1 is what this repository measures
# today: the history is immutable and the controls are enforced, but no
# provenance is produced per revision, and L2 requires both. Raising this is a
# deliberate act, and the measurement refuses it until the evidence holds.
slsa_floor := 1

slsa := d.contents if {
	some d in input
	endswith(d.path, "policy/slsa-source.json")
}

# THE SAFE VALUE FIRST, which is what a default is for: it states the rule's
# contract before any condition, so a record whose observation cannot be read
# reaches zero rather than becoming undefined -- and an undefined comparison
# would make the agreement check below simply not fire.
default slsa_reached := 0

# THE LADDER, READ AS THE SPECIFICATION WRITES IT. Levels are cumulative, so
# each rung requires every rung below it; the chain says that in the order the
# table does. L2 carries two requirements, as the specification does.
slsa_reached := 4 if {
	slsa.observed.version_controlled
	slsa.observed.history_immutable
	slsa.observed.provenance_per_revision
	slsa.observed.controls_enforced
	slsa.observed.two_party_review
} else := 3 if {
	slsa.observed.version_controlled
	slsa.observed.history_immutable
	slsa.observed.provenance_per_revision
	slsa.observed.controls_enforced
} else := 2 if {
	slsa.observed.version_controlled
	slsa.observed.history_immutable
	slsa.observed.provenance_per_revision
} else := 1 if {
	slsa.observed.version_controlled
}

# AN ABSENT RECORD READS AS NOTHING DETECTED, which would turn a rule written
# to deny a bad level into one that allows a missing measurement. The absence
# is itself the denial.
deny contains "slsa-source.json: missing; run mise run slsa:source" if not slsa

deny contains "slsa-source.json: states no level, so nothing was measured" if {
	slsa
	not slsa.level
}

deny contains "slsa-source.json: names no revision, so it binds to nothing" if {
	slsa
	not slsa.revision
}

deny contains msg if {
	slsa.level < slsa_floor
	msg := sprintf(
		"slsa-source.json: level %d is below the declared floor of %d",
		[slsa.level, slsa_floor],
	)
}

# THE LEVEL MUST FOLLOW THE OBSERVATION. The record carries the controls it
# judged precisely so the verdict can be re-derived; a level disagreeing with
# them is a number nobody can check, which is the badge this replaces.
deny contains msg if {
	slsa.level != slsa_reached
	msg := sprintf(
		"slsa-source.json: claims level %d but its observation reaches %d",
		[slsa.level, slsa_reached],
	)
}
