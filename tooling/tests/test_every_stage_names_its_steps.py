# tooling/tests/test_every_stage_names_its_steps.py
"""Each stage names what builds its as-code side and its as-data record (G.79).

SEVEN STAGES, FOURTEEN SIDES, AND NOT ONE DECLARED LINK. G.63 bound every layer
to the steps producing its record and walks that chain; the stages carry id,
title, source, as_code, as_data and gate, and nothing saying which step builds
either half. Configuration as Code, Policy as Code, Governance as Code are named
on the sheet and owned by no one in the plan.

AN EVIDENCE GAP IS FLAGGED AS A MISSING CONTROL. 2026 audit practice weights
them equally: a control that works but cannot be shown to work is a gap, and a
capability matrix drifts behind implementation unless every capability marked
supported carries named evidence.

TWO SIDES, BECAUSE A LOOP WITH ONE IS THE CLASSIC FAILURE -- policy with no
verdicts, contracts with no evidence. The plan's own Loop contract already
refuses a loop with one side; the stages had neither.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.contracts.architecture import Architecture
from otsafety_tooling.contracts.files import read_yaml
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.planning.edit import load
from otsafety_tooling.planning.ledger import load_ledger

pytestmark = pytest.mark.requirement("G.79")

SOURCE = REPO_ROOT / "context" / "architecture.yaml"


def _architecture() -> Architecture:
    return read_yaml(SOURCE, Architecture)


def _links() -> list[tuple[str, str, str]]:
    """Every (stage, side, step) the document declares."""
    return [
        (stage.id, side, named)
        for stage in _architecture().stages
        for side, ids in (("code", stage.code_by), ("data", stage.data_by))
        for named in ids
    ]


def test_every_stage_names_both_sides() -> None:
    """A stage naming only one side is the half-loop the plan already refuses."""
    silent = sorted(
        f"{stage.id}:{side}"
        for stage in _architecture().stages
        for side, ids in (("code", stage.code_by), ("data", stage.data_by))
        if not ids
    )
    assert silent == [], f"stage sides naming no step: {silent}"


def test_every_named_step_is_in_the_plan() -> None:
    """A stage pointing at a step that does not exist is a broken link."""
    known = {step.id for step in load().steps}
    dangling = sorted(f"{s}:{side}->{n}" for s, side, n in _links() if n not in known)
    assert dangling == [], f"stages naming steps the plan does not hold: {dangling}"


def test_every_named_step_is_an_issued_id() -> None:
    """The ledger is where an id becomes real; the chain uses no other name."""
    issued = {entry.id for entry in load_ledger().issued}
    unissued = sorted(f"{s}:{side}->{n}" for s, side, n in _links() if n not in issued)
    assert unissued == [], f"stages naming ids never issued: {unissued}"


def test_the_stages_run_from_configuration_to_the_signed_card() -> None:
    """Seven, in order, from the pinned config to the attestation."""
    stages = _architecture().stages
    assert [stage.id for stage in stages] == [str(i) for i in range(7)], (
        "the stages are not zero through six in order"
    )
    assert "configuration" in stages[0].as_code.lower()
    assert "attestation" in stages[-1].as_data.lower()


def test_the_matrix_can_confirm_every_named_step() -> None:
    """A link is only as good as the requirement at its end."""
    from otsafety_tooling.planning.matrix import build

    rows = {row.id for row in build().requirements}
    missing = sorted({n for _, _, n in _links() if n not in rows})
    assert missing == [], f"named steps with no matrix row: {missing}"


def test_breaking_one_link_fails_the_gate() -> None:
    """THE LIVENESS CONTROL: a chain that cannot break has not been walked.

    Every assertion above reports an empty list, which is the expected result
    and therefore proves nothing alone. This points one side at a step that was
    never issued and checks the same rule refuses it.
    """
    from otsafety_tooling.contracts.architecture import Stage

    broken = Stage(
        id="0",
        title="CONFIGURATION",
        source="conf/config.yaml",
        as_code="Configuration as Code",
        as_data="Config as Data",
        gate=None,
        code_by=("Z.99",),
        data_by=("A.2",),
    )
    known = {step.id for step in load().steps}
    assert "Z.99" not in known, "the fixture's impossible id exists, so it proves nothing"
    dangling = [n for n in (*broken.code_by, *broken.data_by) if n not in known]
    assert dangling == ["Z.99"], "the rule does not see a step the plan lacks"
