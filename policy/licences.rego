# policy/licences.rego
# Every source declares its terms, and a closed one names what must not ship.
package policy

sources := doc("context/sources.yaml").sources

# AN UNDECLARED LICENCE IS NOT PERMISSION. A source whose terms nobody recorded
# cannot be used, the same way an unknown identifier blocks ingestion elsewhere.
deny contains message if {
	some source in sources
	not source.licence
	message := sprintf("source %v records no licence", [source.id])
}

# KNOWING A SOURCE IS CLOSED IS NOT ENOUGH TO ACT ON. The terms name the
# artefacts that cannot be redistributed; naming them as patterns is what lets a
# gate observe their absence.
deny contains message if {
	some source in sources
	source.open == false
	count(source.withheld) == 0
	message := sprintf("source %v is not open and names nothing withheld", [source.id])
}

# THE CONSTRAINT THAT WAS A COMMENT. conf/config.yaml leaves the licensed
# hierarchy empty; a subscriber mounts one, and this repository ships none.
deny contains message if {
	doc("conf/config.yaml").endpoints.meddra_hierarchy != null
	message := "conf/config.yaml mounts a licensed MedDRA hierarchy, which cannot be redistributed"
}
