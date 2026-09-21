# tooling/tests/test_pr_progress.py
"""Waiting for checks reports changes, not a redrawn screen.

THE DEFECT, AND WHY TWO FIXES MISSED IT. `gh pr checks --watch` re-emits the
COMPLETE status every few seconds by design; that is a screen for a human, not
a log. Inside a recorded run it became eighteen near-identical blocks and most
of the run's captured bytes. Giving the recorder a pseudo-terminal, and then
taking mise out of the way, both worked as intended and neither could change
this, because the watcher was never redrawing in the first place.

THE RULE 2026 TOOLS STATE PLAINLY: repaint only when stdout is a terminal,
append otherwise, and never animate while watching. `pr` already polls the
rollup itself, so it reports TRANSITIONS: one line when a check appears,
starts, or concludes, and nothing at all while nothing changes.
"""

from otsafety_tooling.git.pr import Check, describe_transitions


def _check(name: str, conclusion: str | None = None) -> Check:
    return Check.model_validate({"name": name, "conclusion": conclusion or ""})


def test_nothing_changing_says_nothing() -> None:
    checks = (_check("test-backend"), _check("pre-commit"))
    assert describe_transitions(checks, checks) == ()


def test_a_check_that_concluded_is_reported_once() -> None:
    before = (_check("test-backend"), _check("pre-commit"))
    after = (_check("test-backend", "SUCCESS"), _check("pre-commit"))

    lines = describe_transitions(before, after)

    assert len(lines) == 1
    assert "test-backend" in lines[0]
    assert "SUCCESS" in lines[0]


def test_a_newly_registered_check_is_announced() -> None:
    before = (_check("test-backend"),)
    after = (_check("test-backend"), _check("pre-commit-alls-green"))

    lines = describe_transitions(before, after)

    assert len(lines) == 1
    assert "pre-commit-alls-green" in lines[0]


def test_a_failure_is_distinguishable_from_a_success() -> None:
    before = (_check("pre-commit"),)
    after = (_check("pre-commit", "FAILURE"),)

    (line,) = describe_transitions(before, after)

    assert "FAILURE" in line


def test_every_change_in_one_poll_is_reported() -> None:
    before = (_check("a"), _check("b"))
    after = (_check("a", "SUCCESS"), _check("b", "SKIPPED"), _check("c"))

    lines = describe_transitions(before, after)

    assert len(lines) == 3


def test_transitions_are_ordered_by_name_so_runs_compare() -> None:
    before = (_check("zeta"), _check("alpha"))
    after = (_check("zeta", "SUCCESS"), _check("alpha", "SUCCESS"))

    lines = describe_transitions(before, after)

    assert [line.split()[0] for line in lines] == ["alpha", "zeta"]


def test_a_check_that_vanished_is_not_reported_as_a_change() -> None:
    """The rollup can drop a skipped job between polls; that is not news."""
    before = (_check("a"), _check("gone"))
    after = (_check("a"),)

    assert describe_transitions(before, after) == ()
