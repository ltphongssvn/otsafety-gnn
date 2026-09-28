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


def test_a_step_that_waits_on_something_says_why_it_exists() -> None:
    """Every edge added from here carries its reason.

    FIFTY-SEVEN EXISTING STEPS DO NOT, and backfilling them in this branch would
    produce plausible prose rather than recovered reasons -- the rubber stamp
    this repository refused at E.39, one level up. A gate satisfied by inventing
    content is worse than no gate.

    SO THE RULE BINDS THE STEPS ISSUED SINCE IT WAS WRITTEN, and G.74 records
    the backfill as its own work, where each reason can be read out of the
    commit that created the edge rather than guessed.
    """
    from otsafety_tooling.planning.ledger import load_ledger

    issued = {entry.id: index for index, entry in enumerate(load_ledger().issued)}
    mine = issued.get("G.73", 0)
    silent = sorted(
        step.id
        for step in load().steps
        if step.depends_on and not (step.source or "").strip() and issued.get(step.id, 0) >= mine
    )
    assert silent == [], f"steps issued since this rule and still silent: {silent}"


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
