# policy/eslint.rego
# ESLint's effective configuration: the protected rules enforced on every file,
# and every exception declared in the register, in both directions. Severity is
# what is read -- a disabled rule keeps its options -- and an absent rule counts
# as not enforced, so deleting one cannot slip through.
package policy

protected := {
	"@typescript-eslint/consistent-type-assertions", "@typescript-eslint/no-explicit-any",
	"@typescript-eslint/ban-ts-comment", "no-restricted-syntax",
	"@typescript-eslint/no-unsafe-assignment", "@typescript-eslint/no-unsafe-argument",
	"@typescript-eslint/no-unsafe-member-access", "@typescript-eslint/no-unsafe-call",
	"@typescript-eslint/no-unsafe-return",
}

needles := ["JSON.parse", "process.env", "generated from the Pydantic models"]

registered[entry.path] := {rule | some rule in entry.rules} if {
	some entry in doc("context/exemptions.yaml").eslint
}

enforced(path, rule) if effective.files[path].rules[rule].severity == "error"

refuses(file, needle) if {
	some option in file.rules["no-restricted-syntax"].options
	contains(option.message, needle)
}

relaxed(path) := {rule | some rule in protected; not enforced(path, rule)}

declared(path) := object.get(registered, path, set())

deny contains msg if {
	some path, _ in effective.files
	relaxed(path) != declared(path)
	msg := sprintf("%s: not enforced %v; the register declares %v", [path, relaxed(path), declared(path)])
}

deny contains msg if {
	some path, _ in registered
	not effective.files[path]
	msg := sprintf("context/exemptions.yaml: %s is registered but no longer linted", [path])
}

deny contains msg if {
	some path, file in effective.files
	not file.no_inline_config
	msg := sprintf("%s: inline configuration must be disabled", [path])
}

deny contains msg if {
	some path, file in effective.files
	enforced(path, "@typescript-eslint/consistent-type-assertions")
	not file.rules["@typescript-eslint/consistent-type-assertions"].options[0].assertionStyle == "never"
	msg := sprintf("%s: every type assertion must be refused", [path])
}

deny contains msg if {
	some path, file in effective.files
	enforced(path, "no-restricted-syntax")
	some needle in needles
	not refuses(file, needle)
	msg := sprintf("%s: no-restricted-syntax must refuse %s", [path, needle])
}

deny contains "eslint-effective.json: the evidence reader is not among the linted files" if {
	effective
	not effective.files["apps/site/src/data/evidence.ts"]
}
