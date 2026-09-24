# policy/policy_test.rego
# Each denial fires on the input it describes, exercised from outside the policy.
package policy_test

import data.policy

effective_input(files) := [{"path": "/a/policy/eslint-effective.json", "contents": {"files": files}}]

test_a_missing_input_is_denied if {
	"lefthook.yml: missing from the policy's inputs" in policy.deny with input as []
}

test_a_missing_ban_is_denied if {
	ruff := {"tool": {"ruff": {"lint": {"select": ["E"]}}}}
	denied := policy.deny with input as [{"path": "pyproject.toml", "contents": ruff}]
	"pyproject.toml: ruff must select ANN401" in denied
	"pyproject.toml: ruff must ban os.environ" in denied
}

test_an_unregistered_relaxation_is_denied if {
	denied := policy.deny with input as effective_input({"apps/site/x.ts": {"no_inline_config": true, "rules": {}}})
	some msg in denied
	startswith(msg, "apps/site/x.ts: not enforced")
}

test_inline_configuration_must_be_disabled if {
	denied := policy.deny with input as effective_input({"apps/site/x.ts": {"no_inline_config": false, "rules": {}}})
	"apps/site/x.ts: inline configuration must be disabled" in denied
}
