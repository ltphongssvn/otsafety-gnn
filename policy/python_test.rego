# Each denial fires on the input it describes, exercised from outside the policy.
#
# THE PYTHON RULES HAD NO TESTS. They have guarded ruff's bans and mypy's settings
# since G.4, and nothing proved any of them fires -- a rule that cannot fail passes
# vacuously, which two other rules in this policy were caught doing this session.
package policy_test

import data.policy

# --- one mypy configuration (G.30) -------------------------------------------

mypy_world(root_tool, tooling_tool, types_run) := [
	{"path": "pyproject.toml", "contents": {"tool": root_tool}},
	{"path": "tooling/pyproject.toml", "contents": {"tool": tooling_tool}},
	{"path": "mise.toml", "contents": {"tasks": {"types": {"run": types_run}}}},
]

strict_root := {
	"mypy": {"strict": true, "disallow_any_explicit": true, "plugins": ["pydantic.mypy"]},
	"pydantic-mypy": {"init_typed": true, "init_forbid_extra": true},
	"ruff": {"lint": {"select": []}},
}

test_a_second_mypy_section_is_denied if {
	denied := policy.deny with input as mypy_world(
		strict_root,
		{"mypy": {"strict": true}},
		"uv run mypy --config-file pyproject.toml src",
	)
	"tooling/pyproject.toml: must hold no mypy configuration" in denied
}

test_one_section_is_accepted if {
	denied := policy.deny with input as mypy_world(
		strict_root,
		{},
		"uv run mypy --config-file pyproject.toml src",
	)
	every msg in denied {
		not contains(msg, "mypy")
	}
}

test_an_invocation_without_config_file_is_denied if {
	denied := policy.deny with input as mypy_world(
		strict_root,
		{},
		"uv run --directory tooling mypy --platform darwin src tests",
	)
	some msg in denied
	contains(msg, "reads whatever is closest")
}

test_the_root_must_ban_explicit_any if {
	loose := {
		"mypy": {"strict": true, "plugins": ["pydantic.mypy"]},
		"pydantic-mypy": {"init_typed": true, "init_forbid_extra": true},
		"ruff": {"lint": {"select": []}},
	}
	denied := policy.deny with input as mypy_world(loose, {}, "uv run mypy --config-file pyproject.toml src")
	"pyproject.toml: mypy must set disallow_any_explicit" in denied
}
