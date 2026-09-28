# tooling/tests/test_the_tour_shows_the_repository.py
"""One command shows the repository, grouped and marked (G.78).

SIXTY-SIX TASKS, ALPHABETICAL, is a wall rather than a menu. Nothing says which
three to run first, which only read, and which deploy or tag something. 2026
practice met this exactly -- a flat wall of twenty-five tasks regrouped by the
segment before the first colon -- and this repository has nearly triple.

THE CONTENT IS IN THE OUTPUT, not behind a pointer. A CLI that told its reader
to consult the documentation first was followed none of eight times, so the tour
prints what a reader needs rather than where to find it.

DERIVED FROM mise.toml, so it cannot drift: a task added tomorrow appears
without anyone remembering to list it, and G.67 already refuses a task no step
claims.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.contracts.files import read_toml
from otsafety_tooling.contracts.mise_config import MiseConfig
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.78")


def _declared() -> dict[str, str]:
    tasks = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks
    return {name: (task.description or "") for name, task in tasks.items()}


def test_every_task_appears() -> None:
    """A tour that omits a task sends a reader back to the wall."""
    from otsafety_tooling.tour import render

    text = render()
    missing = [name for name in _declared() if name not in text]
    assert missing == [], f"{len(missing)} tasks the tour does not show: {missing[:6]}"


def test_the_tasks_are_grouped_by_namespace() -> None:
    """The segment before the first colon, which is how the wall becomes a menu."""
    from otsafety_tooling.tour import groups

    found = groups(_declared())
    assert "site" in found and "plan" in found and "policy" in found
    assert len(found["site"]) >= 6, "the site's tasks did not group together"
    assert "" not in found, "ungrouped tasks need a heading of their own, not an empty one"


def test_every_group_says_what_it_is_for() -> None:
    """A heading with no description is a prefix, which the reader already had.

    I WROTE THE DESCRIPTIONS FROM MEMORY of the task list and missed two, so
    SHEET and TEST printed bare. That is the defect this repository refuses
    everywhere else -- a declaration nothing checks -- and it belongs in the
    gate rather than in my care.
    """
    from otsafety_tooling.tour import ABOUT, groups

    silent = sorted(
        prefix
        for prefix in groups(_declared())
        if not ABOUT.get("" if prefix == "core" else prefix, "").strip()
    )
    assert silent == [], f"groups with no description: {silent}"


def test_what_only_reads_is_told_apart_from_what_changes_the_world() -> None:
    """The distinction a demonstration depends on."""
    from otsafety_tooling.tour import CHANGES_THE_WORLD, reads_only

    assert reads_only("status") and reads_only("plan:report") and reads_only("lint")
    assert not reads_only("deploy:site")
    assert not reads_only("release:promote")
    assert not reads_only("commit")
    assert CHANGES_THE_WORLD, "nothing is marked as changing anything; the mark means nothing"


def test_the_tour_names_where_to_start() -> None:
    """Three commands, not sixty-six."""
    from otsafety_tooling.tour import START_HERE, render

    assert 2 <= len(START_HERE) <= 5, f"{len(START_HERE)} is not a place to start"
    text = render()
    for name, why in START_HERE:
        assert name in text and why[:30] in text, f"{name} is not shown as a starting point"


def test_the_task_exists_and_calls_the_module() -> None:
    """A tour nobody can run is a docstring."""
    tasks = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks
    assert "tour" in tasks, "no tour task"
    body = tasks["tour"].run
    body = body if isinstance(body, str) else "\n".join(body)
    assert "otsafety_tooling.tour" in body
