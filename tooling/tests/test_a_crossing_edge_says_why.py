# tooling/tests/test_a_crossing_edge_says_why.py
"""A dependency across threads carries its own reason (G.82).

G.73 ASKED EVERY EDGE TO JUSTIFY ITSELF, which is over-broad. 2.2 waits on 2.1
because a pull request needs GitFlow; 9.5 waits on 9.4 because you cannot split
data you have not ingested. Fifty-six such edges would each need a sentence, and
2026 practice is plain that burying the signal under notes is how the real
decisions get lost: justify what affects structure or is hard to reverse, and
skip what is obvious.

AND IT WAS UNSATISFIABLE AS WRITTEN. `source` is one field per STEP, so 11.1,
which waits on nine steps across three other threads, could record a single
sentence for all of them. The reason belongs to the EDGE.

WITHIN A THREAD THE ORDER IS THE WORK'S OWN. Across threads it is a commitment
one stream makes to another -- which is where 9.1 waited on a policy release for
no reason anybody recorded, and where a stale edge costs the most.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.planning.edit import load

pytestmark = pytest.mark.requirement("G.82")


def test_a_step_can_record_a_reason_per_dependency() -> None:
    """The contract must be able to express what the rule asks."""
    from otsafety_tooling.contracts.plan import Step

    assert "because" in Step.model_fields, "a step cannot say why any single edge exists"


def test_every_crossing_edge_says_why() -> None:
    """Across threads, the reason is recorded; within one, the order speaks."""
    plan = load()
    by = {step.id: step for step in plan.steps}
    silent = sorted(
        f"{step.id}->{named}"
        for step in plan.steps
        for named in step.depends_on
        if named in by and by[named].thread != step.thread and named not in step.because
    )
    assert silent == [], f"{len(silent)} crossing edges record no reason: {silent[:6]}"


def test_a_reason_names_an_edge_that_exists() -> None:
    """A reason for a dependency nobody has is a note pointing at nothing."""
    dangling = sorted(
        f"{step.id}->{named}"
        for step in load().steps
        for named in step.because
        if named not in step.depends_on
    )
    assert dangling == [], f"reasons naming absent dependencies: {dangling}"


def test_the_rule_is_confined_to_crossings() -> None:
    """Within a thread, the sequence IS the explanation; demanding more is noise.

    THE POSITIVE CONTROL: without same-thread edges present and unjustified, the
    rule above would be indistinguishable from one demanding every edge speak.
    """
    plan = load()
    by = {step.id: step for step in plan.steps}
    within = [
        (step.id, named)
        for step in plan.steps
        for named in step.depends_on
        if named in by and by[named].thread == step.thread
    ]
    assert within, "no same-thread edges at all; the confinement proves nothing"
    assert any(named not in by[step].because for step, named in within), (
        "every same-thread edge is justified too, so this rule is not the narrow one"
    )
