# tooling/tests/test_a_dependency_states_why.py
"""A dependency states why it exists, and the chain to a goal is visible (G.73).

9.1 WAITED ON G.12 AND RECORDED NO REASON. A Python workspace member waiting on
a policy release tag: they share no artefact, no ordering constraint and no side
effect. That one edge put four steps between this project and its first byte of
data, and nothing showed the chain, so it was invisible until someone asked what
the bottleneck was.

2026 PRACTICE IS EXPLICIT: add an edge for data, ordering or a controlled side
effect -- never because two things were historically adjacent. Unnecessary edges
lengthen the critical path, dependencies go stale, and a chain must be reviewed
periodically to remove links that no longer reflect reality.

SO TWO THINGS. A step that waits on something says why it exists, which is what
makes an edge reviewable at all; and the report walks the chain to any goal, so
a stale edge is seen rather than inferred.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.planning.edit import load

pytestmark = pytest.mark.requirement("G.73")


def test_the_narrow_rule_binds_every_crossing_edge() -> None:
    """G.73 asked every edge to justify itself; G.82 asks the ones that cross.

    THE FIRST RULE WAS OVER-BROAD AND RATCHETED. It demanded a reason for 2.2
    waiting on 2.1 -- a pull request needs GitFlow -- and, unable to satisfy
    that for fifty-six edges, bound only the steps issued after itself. A
    baseline that shrinks when somebody happens to convert one is the failure
    2026 reports describe: debt never worked down, and live defects found inside
    the grandfathered set rather than by the gate.

    AND IT WAS UNSATISFIABLE AS WRITTEN. `source` is one field per step, and
    11.1 waits on nine steps across three threads. The reason belongs to the
    edge, which is what `because` holds -- and every crossing edge carries one
    now, so there is nothing to grandfather and no ratchet left.
    """
    plan = load()
    by = {step.id: step for step in plan.steps}
    assert any(step.because for step in plan.steps), "no edge records a reason at all"
    silent = [
        f"{step.id}->{named}"
        for step in plan.steps
        for named in step.depends_on
        if named in by and by[named].thread != step.thread and named not in step.because
    ]
    assert silent == [], f"the narrow rule is not at zero: {silent[:5]}"


def test_the_workspace_member_no_longer_waits_on_a_release() -> None:
    """The measured edge: creating a package consumed nothing a tag produces."""
    step = next(s for s in load().steps if s.id == "9.1")
    assert "G.12" not in step.depends_on, (
        "9.1 still waits on a policy release it has no work relationship with"
    )


def test_the_chain_to_a_goal_is_reported() -> None:
    """A path nobody can see is a path nobody reviews."""
    from otsafety_tooling.planning.report import chain_to

    path = chain_to("9.3")
    assert path, "no chain is reported at all"
    assert path[0][0] == "9.3", "the chain does not start at the goal"
    assert any(state == "READY" for _, state in path), (
        "the chain reaches nothing ready, so it names no next action"
    )


def test_the_first_data_is_close_to_ready() -> None:
    """The bottleneck this step exists to remove, measured rather than asserted."""
    from otsafety_tooling.planning.report import chain_to

    assert len(chain_to("9.3")) <= 3, (
        f"the first data fetch is still {len(chain_to('9.3'))} steps deep"
    )
