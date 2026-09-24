# policy/commands.rego
# G.42: every command reports as data, or says at its own line why it cannot.
package policy

inventory := d.contents if {
	some d in input
	endswith(d.path, "policy/command-inventory.json")
}

# A COMMAND IS A MODULE WITH A main(), read from the syntax tree rather than a
# list: a hand-kept list drifts the moment someone adds a command, and the gate
# then passes by omission. The builder resolves the emitter through each module's
# imports, because a string search gave three false negatives.
deny contains msg if {
	some command in inventory.commands
	not command.emits
	not command.exempt_because
	msg := sprintf(
		"%s: a command reports as data -- emit a command-outcome/v1 envelope, or say at the line why it cannot",
		[command.module],
	)
}

deny contains "command-inventory.json: missing; run mise run policy:inputs" if not inventory
