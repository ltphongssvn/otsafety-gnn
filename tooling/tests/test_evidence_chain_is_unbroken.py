# tooling/tests/test_evidence_chain_is_unbroken.py
"""The chain of accountability, walked rather than assumed (G.63).

NINE LAYERS, NINE RECORDS, AND NOT ONE DECLARED LINK. Every layer names an
as-data record -- the model-card limitation statement, the degree snapshot, the
release-pin hash, the attribution evidence, the per-target decisions, the
versioned label set, the split verdict, the metrics, the signed model card --
and every one of those records has a plan step that produces it. The binding was
inferable by a person reading two documents and by nothing else.

MATCHING BY KEYWORD FOUND SIX AND MISSED THREE THAT EXIST. 9.6 produces the
degree snapshot, 9.3 the release-pin digest, 9.9 the per-target tier decisions,
and a word-overlap guess reported all three as unowned. A guess is not a chain.

2026 PROVENANCE PRACTICE BINDS EACH STAGE TO THE NEXT, so a stage cannot be
reordered, removed or inserted without the break being detectable. Here the
binding is an id: each layer names the step that produces its record, the step
must exist in the plan, and its id must be in the ledger -- so renaming a step,
deleting one, or pointing a layer at nothing all fail this gate.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.contracts.architecture import Architecture
from otsafety_tooling.contracts.files import read_yaml
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.planning.edit import load
from otsafety_tooling.planning.ledger import load_ledger

pytestmark = pytest.mark.requirement("G.63")

SOURCE = REPO_ROOT / "context" / "architecture.yaml"


def _architecture() -> Architecture:
    return read_yaml(SOURCE, Architecture)


def test_every_layer_names_the_step_that_produces_its_record() -> None:
    """A record nobody is building is a link that will never close."""
    silent = [layer.n for layer in _architecture().layers if not layer.produced_by]
    assert silent == [], f"layers naming no producing step: {silent}"


def test_every_named_step_is_in_the_plan() -> None:
    """A layer pointing at a step that does not exist is a broken link."""
    known = {step.id for step in load().steps}
    dangling = sorted(
        f"{layer.n}->{named}"
        for layer in _architecture().layers
        for named in layer.produced_by
        if named not in known
    )
    assert dangling == [], f"layers naming steps the plan does not hold: {dangling}"


def test_every_named_step_is_an_issued_id() -> None:
    """The ledger is where an id becomes real; the chain uses no other name."""
    issued = {entry.id for entry in load_ledger().issued}
    unissued = sorted(
        f"{layer.n}->{named}"
        for layer in _architecture().layers
        for named in layer.produced_by
        if named not in issued
    )
    assert unissued == [], f"layers naming ids never issued: {unissued}"


def test_the_chain_runs_from_reality_to_the_signed_card() -> None:
    """Nine links, in order, from the limitation statement to the attestation."""
    layers = _architecture().layers
    assert [layer.n for layer in layers] == [str(i) for i in range(1, 10)], (
        "the layers are not one through nine in order"
    )
    assert "limitation" in layers[0].as_data.lower(), "layer 1 does not record the limitation"
    assert "model card" in layers[-1].as_data.lower(), "layer 9 does not record the signed card"


def test_the_matrix_can_confirm_every_producing_step() -> None:
    """A link is only as good as the requirement at its end."""
    from otsafety_tooling.planning.matrix import build

    rows = {row.id: row for row in build().requirements}
    missing = sorted(
        named
        for layer in _architecture().layers
        for named in layer.produced_by
        if named not in rows
    )
    assert missing == [], f"producing steps with no matrix row: {missing}"
