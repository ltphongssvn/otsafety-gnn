# METADATA
# title: The configuration that enforces this repository's policy
# description: |
#   Every ban, floor and ceiling, proved present in the configuration that
#   enforces it. All inputs are evaluated together, with --combine.
# entrypoint: true
package policy

required := {
	"pyproject.toml",
	"tooling/pyproject.toml",
	"lefthook.yml",
	".github/workflows/test-site.yml",
	".github/workflows/test-tooling.yml",
	".github/workflows/zizmor.yml",
	"context/exemptions.yaml",
}

doc(path) := d.contents if {
	some d in input
	d.path == path
}

effective := d.contents if {
	some d in input
	endswith(d.path, "policy/eslint-effective.json")
}

# THE PROOF CANNOT PASS VACUOUSLY: a missing input would make every rule about it
# match nothing, so its absence is itself a denial.
deny contains msg if {
	some path in required
	not doc(path)
	msg := sprintf("%s: missing from the policy's inputs", [path])
}

deny contains "eslint-effective.json: missing; run mise run policy:inputs" if not effective
