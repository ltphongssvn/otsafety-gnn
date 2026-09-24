# policy/python.rego
# The Python bans, proved present in the configuration that enforces them.
package policy

ruff := doc("pyproject.toml").tool.ruff

tooling := doc("tooling/pyproject.toml").tool

selected := {rule | some rule in ruff.lint.select}

root := doc("pyproject.toml").tool

mypy := root.mypy

plugins := {plugin | some plugin in mypy.plugins}

mypy_invocations := [line |
	some line in split(doc("mise.toml").tasks.types.run, "\n")
	contains(line, " mypy ")
]

required_rules := {
	"TID251", "ANN401", "RUF100", "S", "T20", "BLE",
	"ANN001", "ANN002", "ANN003", "ANN201", "ANN202", "ANN204",
}

banned := {
	"json.load", "json.loads", "yaml.load", "yaml.safe_load",
	"tomllib.load", "tomllib.loads", "os.environ", "os.getenv",
}

deny contains msg if {
	some rule in required_rules
	not rule in selected
	msg := sprintf("pyproject.toml: ruff must select %s", [rule])
}

deny contains msg if {
	some name in banned
	not ruff.lint["flake8-tidy-imports"]["banned-api"][name]
	msg := sprintf("pyproject.toml: ruff must ban %s", [name])
}

deny contains "pyproject.toml: ruff's target-version must be declared" if not ruff["target-version"]

deny contains "tooling/pyproject.toml: must hold no ruff configuration" if tooling.ruff

# RUFF'S RULE, APPLIED TO MYPY. Line 33 already required the tooling package to
# hold no ruff configuration, because ruff reads the closest file outright and a
# second one would replace the root's policy for that package. mypy behaves the
# same way and its documentation says so: there is no merging of configuration
# files. The tooling package had a full second section that had already drifted --
# the root permitted explicit Any and loaded no pydantic plugin, so scripts/ and
# the site's tests were checked under weaker rules than src/.
deny contains msg if {
	some setting in ["strict", "disallow_any_explicit"]
	not mypy[setting] == true
	msg := sprintf("pyproject.toml: mypy must set %s", [setting])
}

deny contains "pyproject.toml: mypy must load pydantic.mypy" if not "pydantic.mypy" in plugins

deny contains msg if {
	some setting in ["init_typed", "init_forbid_extra"]
	not root["pydantic-mypy"][setting] == true
	msg := sprintf("pyproject.toml: pydantic-mypy must set %s", [setting])
}

deny contains "tooling/pyproject.toml: must hold no mypy configuration" if tooling.mypy

# THE RULE THAT MAKES ONE CONFIGURATION TRUE. Without --config-file mypy reads
# whatever file is closest to where it runs, so an invocation that omits it
# bypasses the root's policy silently -- which is how the tooling was disarmed
# for one commit, caught by a probe rather than by reading.
deny contains msg if {
	some line in mypy_invocations
	not contains(line, "--config-file")
	msg := sprintf("mise.toml: this mypy invocation reads whatever is closest: %s", [trim_space(line)])
}

# THE HABIT, NOT THE INSTANCE. The exemption that hid sixty-one sites was a
# module-wide override with no count and no expiry: it permitted whatever anyone
# wrote next, and nobody had to look. A new one is refused here.
deny contains msg if {
	some override in mypy.overrides
	override.disallow_any_explicit == false
	msg := sprintf(
		"pyproject.toml: %v is exempt from the ban on explicit Any; an exemption with no count permits whatever comes next",
		[override.module],
	)
}
