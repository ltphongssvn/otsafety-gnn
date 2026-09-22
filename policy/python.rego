# The Python bans, proved present in the configuration that enforces them.
package policy

ruff := doc("pyproject.toml").tool.ruff

tooling := doc("tooling/pyproject.toml").tool

selected := {rule | some rule in ruff.lint.select}

plugins := {plugin | some plugin in tooling.mypy.plugins}

required_rules := {"TID251", "ANN401", "RUF100", "S", "T20", "BLE"}

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

deny contains msg if {
	some setting in ["strict", "disallow_any_explicit"]
	not tooling.mypy[setting] == true
	msg := sprintf("tooling/pyproject.toml: mypy must set %s", [setting])
}

deny contains "tooling/pyproject.toml: mypy must load pydantic.mypy" if not "pydantic.mypy" in plugins

deny contains msg if {
	some setting in ["init_typed", "init_forbid_extra"]
	not tooling["pydantic-mypy"][setting] == true
	msg := sprintf("tooling/pyproject.toml: pydantic-mypy must set %s", [setting])
}
