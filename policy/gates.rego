# Every floor in the hooks, and every ceiling in CI.
package policy

floors := {
	"mise run start:check", "mise run toolchain:verify", "mise run policy:no-markdown",
	"mise run policy:exemptions",
	"mise run lint", "mise run site:lint",
}

ceilings := {"mise run toolchain:verify", "mise run site:types", "mise run site:lint", "mise run policy"}

pre_commit_runs contains job.run if {
	some job in doc("lefthook.yml")["pre-commit"].jobs
}

site_ci_runs contains step.run if {
	some job in doc(".github/workflows/test-site.yml").jobs
	some step in job.steps
	step.run
}

trailers_checked if {
	some j in doc("lefthook.yml")["commit-msg"].jobs
	startswith(j.run, "mise run policy:trailers")
}

tooling_ci_runs contains step.run if {
	some job in doc(".github/workflows/test-tooling.yml").jobs
	some step in job.steps
	step.run
}

zizmor_pinned if {
	some job in doc(".github/workflows/zizmor.yml").jobs
	some step in job.steps
	startswith(step.uses, "zizmorcore/zizmor-action@")
	step["with"].version != "latest"
}

full_history if {
	some job in doc(".github/workflows/test-tooling.yml").jobs
	some s in job.steps
	startswith(s.uses, "actions/checkout@")
	s["with"]["fetch-depth"] == 0
}

deny contains msg if {
	some job in floors
	not job in pre_commit_runs
	msg := sprintf("lefthook.yml: pre-commit must run %s", [job])
}

deny contains msg if {
	some job in ceilings
	not job in site_ci_runs
	msg := sprintf("test-site.yml: CI must run %s", [job])
}

deny contains "lefthook.yml: commit-msg must run policy:trailers" if not trailers_checked

deny contains "test-tooling.yml: checkout must fetch full history" if not full_history

deny contains "test-tooling.yml: CI must run mise run toolchain:verify" if {
	not "mise run toolchain:verify" in tooling_ci_runs
}

deny contains "zizmor.yml: zizmor-action must pin zizmor itself; its default is latest" if not zizmor_pinned
