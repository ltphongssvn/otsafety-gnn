# tooling/tests/test_command_inventory.py
"""Every command emits an envelope, or says at its own line why it does not (G.42).

WHY AN INVENTORY AND NOT A LIST. A hand-kept list of commands drifts the moment
someone adds one, and the gate then passes by omission. This is read from the
syntax tree: a module with a main() is a command, and it emits an envelope only
if it CALLS the emitter -- a string search gave three false negatives, because
the emitter is imported under three names. The policy judges the inventory; this
proves the inventory itself is honest.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.contracts.inventory import CommandInventory
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.policy.inventory import build

pytestmark = pytest.mark.requirement("G.42")


def test_every_command_is_found_by_its_main() -> None:
    inventory = build(REPO_ROOT)
    names = {command.module for command in inventory.commands}
    assert "tooling/src/otsafety_tooling/git/pr.py" in names
    assert "scripts/check_all.py" in names
    assert not any(name.endswith("contracts/plan.py") for name in names), "a model is not a command"


def test_an_emitter_under_any_name_counts_as_emitting() -> None:
    """THE FALSE NEGATIVE THIS EXISTS TO PREVENT: pr imports it as emit_result,
    branches likewise, and the scripts define their own emit(). All three emit."""
    by_module = {command.module: command for command in build(REPO_ROOT).commands}
    for module in (
        "tooling/src/otsafety_tooling/git/pr.py",
        "tooling/src/otsafety_tooling/git/branches.py",
        "tooling/src/otsafety_tooling/planning/matrix.py",
        "scripts/check_all.py",
    ):
        assert by_module[module].emits, f"{module} emits an envelope"


def test_a_declared_exception_is_recorded_with_its_reason() -> None:
    by_module = {command.module: command for command in build(REPO_ROOT).commands}
    declared = (
        "tooling/src/otsafety_tooling/artifacts.py",
        "tooling/src/otsafety_tooling/runs.py",
    )
    for module in declared:
        command = by_module[module]
        assert not command.emits and command.exempt_because, f"{module} declares why"


def test_the_inventory_validates_as_its_contract() -> None:
    CommandInventory.model_validate(build(REPO_ROOT).model_dump(mode="json"))
