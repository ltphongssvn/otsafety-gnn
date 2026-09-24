# tooling/tests/test_requirement_identity.py
"""An id is issued once, and everything hangs off it (G.41).

WHY THIS EXISTS. The team does not say "the setup bug", it says G.38: the
constraint, the observation that produced it, the evidence file and the
behavioural proof are one object, joined by an id. 2026 traceability practice is
blunt about what breaks that -- ids must be assigned once and never reused, even
after deletion, or every link silently points at the wrong thing -- and about
orphans: a requirement with no evidence, or an observation mapping to nothing,
is reported, never ignored.

The ledger is the record of every id ever issued. The matrix is generated from
the plan, its trace, the tree and the commits. The rules live in Rego, over both.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from otsafety_tooling.contracts.files import read_yaml
from otsafety_tooling.contracts.traceability import IdLedger, IssuedId
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.planning.edit import load
from otsafety_tooling.planning.ledger import issue, ledger_path, load_ledger, save_ledger

# THIS FILE PROVES G.41: the claim the requirement matrix joins on.
pytestmark = pytest.mark.requirement("G.41")

LEDGER = REPO_ROOT / "context" / "plan-ids.yaml"


def test_the_ledger_holds_every_id_the_plan_uses() -> None:
    plan = load()
    known = {entry.id for entry in load_ledger().issued}
    used = {s.id for s in plan.steps} | {d.id for d in plan.decisions}
    assert used <= known, f"ids in the plan but never issued: {sorted(used - known)}"


def test_a_retired_id_stays_in_the_ledger() -> None:
    """An id leaves the plan by being retired, never by disappearing."""
    ledger = load_ledger()
    retired = [entry.id for entry in ledger.issued if entry.retired]
    plan = load()
    live = {s.id for s in plan.steps} | {d.id for d in plan.decisions}
    assert not (set(retired) & live), "a retired id is not in the plan"


def test_issuing_an_id_twice_is_refused() -> None:
    ledger = IdLedger(issued=(IssuedId(id="G.1", first_title="a step"),))
    with pytest.raises(ValueError, match="G.1"):
        issue(ledger, IssuedId(id="G.1", first_title="another step"))


def test_issuing_appends_and_never_rewrites(tmp_path: Path) -> None:
    ledger = IdLedger(issued=(IssuedId(id="G.1", first_title="a step"),))
    grown = issue(ledger, IssuedId(id="G.2", first_title="another"))
    assert [e.id for e in grown.issued] == ["G.1", "G.2"]
    assert [e.id for e in ledger.issued] == ["G.1"], "the original is untouched"


def test_the_ledger_round_trips_through_its_contract(tmp_path: Path) -> None:
    written = save_ledger(load_ledger(), tmp_path / "plan-ids.yaml")
    assert read_yaml(written, IdLedger) == load_ledger()


def test_the_ledger_lives_where_the_plan_does() -> None:
    assert ledger_path() == LEDGER


def test_a_file_claims_a_requirement_with_a_marker() -> None:
    """A CLAIM, NOT A MENTION. The matrix joins evidence to proof through the
    registered `requirement` marker -- 2026 practice -- because scanning a file
    for an id cannot tell a claim from a passing reference: G.25's id appeared in
    a file that merely told its story, and not in the test that proves it.
    """
    from otsafety_tooling.planning.matrix import claims

    root = REPO_ROOT / "tooling" / "tests"
    assert claims(root / "test_no_any.py") == {"G.25"}
    assert claims(root / "test_fresh_checkout.py") == {"G.38", "G.39"}
    # This file mentions G.25 in prose above; mentioning is not claiming.
    assert "G.25" not in claims(Path(__file__))


def test_the_marker_is_registered_so_a_typo_is_not_silent() -> None:
    from otsafety_tooling.contracts.files import read_toml
    from otsafety_tooling.contracts.pyproject_config import WorkspacePyproject

    config = read_toml(REPO_ROOT / "tooling" / "pyproject.toml", WorkspacePyproject)
    pytest_config = config.tool.pytest
    assert pytest_config is not None and pytest_config.ini_options is not None
    assert any(m.startswith("requirement(") for m in pytest_config.ini_options.markers)
    # --strict-markers is what makes an unregistered claim an error, not a new marker.
    assert "--strict-markers" in pytest_config.ini_options.addopts


def test_evidence_is_confirmed_according_to_its_kind(tmp_path: Path) -> None:
    """A LINK IS NOT VERIFIED UNTIL THE EVIDENCE ITSELF IS CONFIRMED (2026 practice).

    A test file is confirmed by CLAIMING the id, through the registered marker. A
    file that cannot carry a marker -- a Rego policy, a configuration -- is
    confirmed by inspection: it must contain the id. Anything else is unconfirmed,
    and a step claimed done with unconfirmed evidence is denied.
    """
    from otsafety_tooling.planning.matrix import unconfirmed

    proof = tmp_path / "test_thing.py"
    claim = 'import pytest\n\npytestmark = pytest.mark.requirement("G.9")\n'
    proof.write_text(claim, encoding="utf-8")
    rego = tmp_path / "thing.rego"
    rego.write_text("# G.9: the rule this file carries.\npackage policy\n", encoding="utf-8")
    silent = tmp_path / "quiet.rego"
    silent.write_text("package policy\n", encoding="utf-8")

    assert unconfirmed("G.9", ("path:test_thing.py",), tmp_path) == ()
    assert unconfirmed("G.9", ("path:thing.rego",), tmp_path) == ()
    assert unconfirmed("G.9", ("path:quiet.rego",), tmp_path) == ("path:quiet.rego",)
    # A test file that does not claim the id is unconfirmed, even if it mentions it.
    mentions = tmp_path / "test_mentions.py"
    mentions.write_text('"""A story about G.9."""\n', encoding="utf-8")
    assert unconfirmed("G.9", ("path:test_mentions.py",), tmp_path) == ("path:test_mentions.py",)
    # A task, a pull request or a release is confirmed by plan:status, not here.
    assert unconfirmed("G.9", ("task:policy", "pr:41"), tmp_path) == ()
