# tooling/tests/test_evidence_names_its_method.py
"""Every completed step's evidence names the requirement it proves (G.54).

TWENTY-SEVEN COMPLETED STEPS READ AS UNCONFIRMED, and the first diagnosis was
wrong: the matrix has accepted inspection for non-Python evidence since it was
written -- a Python file confirms by CLAIMING the id through the registered
marker, and any other file confirms by containing it. Machinery was added for a
rule that already existed, and withdrawn.

THE FILES SIMPLY DO NOT NAME WHAT THEY PROVE. flake.nix does not say 4.2,
mise.toml does not say 6.3, lefthook.yml does not say 6.6. Each is correct and
none is traceable, which is the same defect G.21 closed for paths: a fact that
lives only in someone's memory of why the file exists.

A MATRIX WHOSE GAPS ARE HALF SPURIOUS STOPS BEING READ. That is the cost here --
not the twenty-seven rows themselves, but that ninety-nine unconfirmed rows meant
two different things at once and neither could be acted on.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.planning.edit import load
from otsafety_tooling.planning.matrix import build
from otsafety_tooling.planning.status import staged_facts, unmet

pytestmark = pytest.mark.requirement("G.54")


def test_no_completed_step_has_evidence_that_omits_its_id() -> None:
    """A step the plan shows done must have evidence that names it."""
    plan, facts = load(), staged_facts(REPO_ROOT)
    rows = {row.id: row for row in build().requirements}
    stranded = sorted(
        step.id
        for step in plan.steps
        if not unmet(plan, facts, step.id) and rows[step.id].unconfirmed
    )
    assert stranded == [], (
        f"{len(stranded)} completed steps have evidence that does not name them: {stranded[:8]}"
    )


def test_the_unconfirmed_count_means_one_thing() -> None:
    """Unconfirmed must mean 'not built yet', never 'built and untraceable'.

    Ninety-nine rows read unconfirmed while meaning both, which is how a
    diagnostic becomes noise.
    """
    plan, facts = load(), staged_facts(REPO_ROOT)
    rows = {row.id: row for row in build().requirements}
    unconfirmed = [s for s in plan.steps if rows[s.id].unconfirmed]
    for step in unconfirmed:
        assert unmet(plan, facts, step.id), (
            f"{step.id} is complete and unconfirmed, so the count means two things"
        )
