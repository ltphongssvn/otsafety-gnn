# tooling/tests/test_policy_inputs_manifest.py
"""The policy's input set is declared once, and every consumer reads it (G.42).

WHY. The set lived in three places: the policy task's command line, the probe's
own list, and the required set in inputs.rego. Adding the command inventory meant
three edits, and missing one failed late -- the divergence problem 2026 practice
names for duplicated policy configuration. One manifest is the source; the task
passes what it declares, the probe builds what it declares, and the Rego derives
its required set from the manifest itself, which is also one of the inputs.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.contracts.files import read_json, read_toml
from otsafety_tooling.contracts.mise_config import MiseConfig
from otsafety_tooling.contracts.policy_inputs import PolicyInputs
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.42")

MANIFEST = REPO_ROOT / "contracts" / "policy-inputs.json"


def _manifest() -> PolicyInputs:
    return read_json(MANIFEST, PolicyInputs)


def test_the_manifest_declares_every_input() -> None:
    declared = {entry.path for entry in _manifest().inputs}
    assert "lefthook.yml" in declared
    assert "context/plan-ids.yaml" in declared
    assert any(entry.generated for entry in _manifest().inputs), "generated inputs are marked"


def test_the_policy_task_names_no_input_of_its_own() -> None:
    """THE PARITY CHECK, STATED CORRECTLY. An earlier version asserted the task's
    command line CONTAINED every path, which is the duplication this removes. The
    task must name none of them and ask the manifest instead."""
    tasks = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks
    # A TASK MAY RUN SEVERAL COMMANDS, so the model types run as a string or a
    # tuple; both are read the same way here.
    run = tasks["policy"].run
    commands = [run] if isinstance(run, str) else list(run)
    line = next(
        one for command in commands for one in command.splitlines() if "conftest test" in one
    )
    assert "policy.inputs --paths" in line, "the task reads the declared set"
    for entry in _manifest().inputs:
        assert entry.path not in line, f"the task names {entry.path} itself, which drifts"


def test_the_declared_paths_are_what_a_run_would_read() -> None:
    """Every declared input resolves to a path, generated ones under the evidence root."""
    from otsafety_tooling.policy.inputs import paths

    resolved = paths()
    assert len(resolved) == len(_manifest().inputs)
    assert any(path.endswith("policy/command-inventory.json") for path in resolved)
    assert "lefthook.yml" in resolved


def test_the_probe_reads_the_manifest_rather_than_its_own_list() -> None:
    probe = (REPO_ROOT / "apps" / "site" / "tests" / "test_policy_probe.py").read_text()
    assert "policy-inputs.json" in probe, "the probe builds its world from the manifest"
    assert "INPUTS = [" not in probe, "a second list is the drift this removes"
