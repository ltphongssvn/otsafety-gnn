# tooling/tests/test_plan_writer.py
"""One writer for the plan, from the model, so there is one canonical form (G.44).

WHY THIS EXISTS. Steps were added by building a YAML block in a throwaway script
and splicing it in. 2026 practice for a file a program owns is the opposite: one
writer from the model, and a gate that the committed file equals what that writer
produces. Without it each edit invents its own field order and quoting, and the
drift is only visible later, across the file's history. The header comment is not
part of the model, so the reader hands it to the writer beside it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from otsafety_tooling.contracts.plan import PathEvidence, Serves, Step
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.planning.edit import add_step, canonical, header_of, load, save

PLAN = REPO_ROOT / "context" / "plan.yaml"


def _step(identifier: str = "Z.1") -> Step:
    return Step(
        id=identifier,
        title="a step",
        thread="G",
        phase="8G",
        source="a session finding",
        serves=(Serves(loop="constrain", side="code"),),
        done_when=(PathEvidence(kind="path", path="tooling/tests/test_plan_writer.py"),),
    )


def test_the_committed_plan_is_already_canonical() -> None:
    """The gate: a hand edit the writer would not produce is refused."""
    assert PLAN.read_text(encoding="utf-8") == canonical(load(PLAN), header_of(PLAN))


def test_the_header_is_carried_beside_the_model() -> None:
    header = header_of(PLAN)
    assert header.startswith("# context/plan.yaml"), "the header comment belongs to the file"
    assert "THE PLAN AS INTENT" in header


def test_adding_a_step_returns_a_plan_with_it(tmp_path: Path) -> None:
    plan = load(PLAN)
    grown = add_step(plan, _step())
    assert len(grown.steps) == len(plan.steps) + 1
    assert grown.steps[-1].id == "Z.1"
    assert [s.id for s in plan.steps] == [s.id for s in load(PLAN).steps], (
        "the original is untouched"
    )


def test_a_duplicate_id_is_refused() -> None:
    plan = load(PLAN)
    with pytest.raises(ValueError, match="G.1"):
        add_step(plan, _step("G.1"))


def test_a_written_plan_reads_back_identically(tmp_path: Path) -> None:
    plan = add_step(load(PLAN), _step())
    written = tmp_path / "plan.yaml"
    save(plan, written, header_of(PLAN))
    assert [s.id for s in load(written).steps] == [s.id for s in plan.steps]
    assert written.read_text(encoding="utf-8") == canonical(load(written), header_of(written))


def test_the_model_refuses_a_malformed_step() -> None:
    with pytest.raises(ValidationError):
        Step(id="Z.2", title="", thread="G", phase="8G", serves=(), done_when=())
