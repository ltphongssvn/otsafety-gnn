# tooling/tests/test_evidence_names_a_test.py
"""Evidence names the test that verifies a step, not a file containing it (G.77).

A PATH IS INSPECTION. A file exists, a task is declared, a pull request merged
-- each shows an artefact and none shows that a rule refuses anything. Nineteen
completed steps here claim to constrain and rest on exactly that: G.3 says raw
parsing is banned and is proved by a file existing; G.15 says secrets are
scanned and is proved by a task being named.

AND A PATH CANNOT SAY WHICH TEST. G.76 pointed at a file another step already
claimed, which the matrix read as complete and unconfirmed, because one module
claims one requirement and a path cannot distinguish the two tests inside it.

SO A PROOF NAMES path::test_name. Control practice separates checking from
validating -- checking confirms existence, validating confirms effectiveness --
and inquiry alone is insufficient evidence of a control's operation.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.requirement("G.77")


def test_a_proof_is_an_evidence_kind() -> None:
    """The contract can express a test as evidence."""
    from otsafety_tooling.contracts.plan import ProofEvidence

    proof = ProofEvidence(kind="proof", test="tooling/tests/test_x.py::test_it_refuses")
    assert proof.test.endswith("::test_it_refuses")


def test_a_proof_must_name_a_test_and_not_merely_a_file() -> None:
    """A path with no test named is inspection wearing another label."""
    from pydantic import ValidationError

    from otsafety_tooling.contracts.plan import ProofEvidence

    with pytest.raises(ValidationError):
        ProofEvidence(kind="proof", test="tooling/tests/test_x.py")


def test_every_proof_names_a_test_that_exists() -> None:
    """A proof pointing at a test nobody wrote is a promise, not evidence.

    THE POPULATION IS PROVED NON-EMPTY FIRST. A universal statement over an
    empty set is true for any predicate, so this passed while no step used a
    proof at all: zero elements, zero assertions, a green test that examined
    nothing. The remedy is a precondition, not a weaker assertion.
    """
    import ast as syntax

    from otsafety_tooling.paths import REPO_ROOT
    from otsafety_tooling.planning.edit import load

    proofs = [
        (step.id, named)
        for step in load().steps
        for item in step.done_when
        if (named := getattr(item, "test", None)) is not None
    ]
    assert proofs, "no step is proved by a test, so this rule examines nothing"

    missing: list[str] = []
    for step_id, named in proofs:
        path, _, function = named.partition("::")
        whole = REPO_ROOT / path
        if not whole.is_file():
            missing.append(f"{step_id}: {path} does not exist")
            continue
        tree = syntax.parse(whole.read_text(encoding="utf-8"))
        if not any(
            isinstance(node, syntax.FunctionDef) and node.name == function for node in tree.body
        ):
            missing.append(f"{step_id}: {path} has no {function}")
    assert missing == [], f"proofs naming tests that do not exist: {missing}"


def test_a_violating_fixture_is_refused_by_the_rule_it_violates() -> None:
    """THE PAIRED NEGATIVE: a rule is shown to fire, not assumed to.

    A NON-ZERO EXIT IS NOT THE RULE FIRING. A tool refuses malformed input with
    the same status it uses for a real violation, so the rule's own code must
    appear in what it said. Without that the harness proves the tool ran.
    """
    from otsafety_tooling.paired import refuses

    verdict = refuses(
        [
            "uv",
            "run",
            "--no-sync",
            "ruff",
            "check",
            "--select",
            "TID251",
            "--stdin-filename",
            "probe.py",
            "-",
        ],
        violating="import json\nx = json.loads('{}')\n",
        clean="from pathlib import Path\nx = Path('.')\n",
        naming="TID251",
    )
    assert verdict.fired_on_the_violation, verdict.why
    assert verdict.silent_on_the_clean_one, verdict.why


def test_the_harness_reports_a_rule_that_cannot_fire() -> None:
    """THE LIVENESS CONTROL: a harness that always says yes proves nothing."""
    from otsafety_tooling.paired import refuses

    verdict = refuses(
        [
            "uv",
            "run",
            "--no-sync",
            "ruff",
            "check",
            "--select",
            "TID251",
            "--stdin-filename",
            "probe.py",
            "-",
        ],
        violating="x = 1\n",
        clean="x = 1\n",
        naming="TID251",
    )
    assert not verdict.fired_on_the_violation, "the harness claims a rule fired on clean input"
