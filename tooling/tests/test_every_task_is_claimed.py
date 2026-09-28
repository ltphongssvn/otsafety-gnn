# tooling/tests/test_every_task_is_claimed.py
"""Every task is claimed by a step, and an orphan fails (G.67).

FORTY-SIX OF SIXTY-SIX TASKS WERE NAMED BY NO STEP -- check, lint, test, fmt,
commit, sync, pr:merge among them. They run, they gate every commit, and nothing
recorded why they exist, when they should run, or what depends on them.

THE MATRIX ONLY EVER LOOKED ONE WAY. It proves a step has evidence; nothing
proved a task has a step. A capability with no requirement behind it is exactly
the orphan the sibling found, where pr:merge stayed invisible for weeks while
four dependency updates sat unmerged.

A STEP CLAIMS A TASK BY NAMING IT, in its evidence as task:<name> or in its own
words. Grouping is by capability rather than one step per command: the daily
loop, the gates, the release path.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.67")


def test_no_task_is_claimed_by_no_step() -> None:
    """An orphan is a capability nobody authorised."""
    from otsafety_tooling.policy.tasks import orphans

    found = orphans(REPO_ROOT)
    assert found == [], f"{len(found)} tasks no step claims: {found[:10]}"


def test_a_task_that_does_not_exist_is_not_claimable() -> None:
    """The other direction: a step naming a task the repository lost."""
    from otsafety_tooling.policy.tasks import phantoms

    found = phantoms(REPO_ROOT)
    assert found == [], f"steps naming tasks that do not exist: {found[:10]}"


def test_the_rule_is_not_vacuous() -> None:
    """A gate that cannot fail proves nothing."""
    from otsafety_tooling.policy.tasks import unclaimed

    assert unclaimed({"lint", "invented:task"}, {"lint"}) == ["invented:task"]
    assert unclaimed({"lint"}, {"lint"}) == []
