# Each denial fires on the input it describes, exercised from outside the policy.
package policy_test

import data.policy

inventory_world(commands) := [{
	"path": "/a/policy/command-inventory.json",
	"contents": {"contract": "command-inventory/v1", "commands": commands},
}]

test_a_silent_command_is_denied if {
	denied := policy.deny with input as inventory_world([{"module": "tooling/src/x.py", "emits": false}])
	some msg in denied
	contains(msg, "a command reports as data")
}

test_a_command_that_emits_is_accepted if {
	denied := policy.deny with input as inventory_world([{"module": "tooling/src/x.py", "emits": true}])
	every msg in denied {
		not contains(msg, "tooling/src/x.py")
	}
}

test_a_declared_exception_is_accepted if {
	exempt := {
		"module": "tooling/src/artifacts.py", "emits": false,
		"exempt_because": "its stdout is a value a shell substitutes",
	}
	denied := policy.deny with input as inventory_world([exempt])
	every msg in denied {
		not contains(msg, "artifacts.py")
	}
}

test_a_missing_inventory_is_denied if {
	denied := policy.deny with input as []
	"command-inventory.json: missing; run mise run policy:inputs" in denied
}
