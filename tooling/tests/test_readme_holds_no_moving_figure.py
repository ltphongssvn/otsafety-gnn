# tooling/tests/test_readme_holds_no_moving_figure.py
"""The README stores no figure its own commit changes (G.64).

THREE PUSHES REFUSED IN ONE DAY, each because the commit completed a step the
README counts. A stored figure that counts its own commit cannot be correct when
committed: regenerating clears it until the next one, which is a treadmill, not
a fix. G.53 reached the same conclusion for the sheet's facts and answered it by
not storing the file at all.

THE README MUST BE STORED, SO THE FIGURES GO. 2026 practice is settled: hard-
coded counts come out of a README in favour of signals that resolve when a
reader looks, after the same numbers were bumped across four pull requests and
conflicted on every rebase, and static badges were found reporting a fixed value
whatever the real standing.

WHAT STAYS IS WHAT DOES NOT MOVE: the question, the control, the method, the
stack pinned in toolchain.json, and a pointer to the command that measures.
"""

from __future__ import annotations

import re

import pytest

from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.64")

README = REPO_ROOT / "README.md"

# THE SHAPES A DERIVED COUNT TAKES HERE. Each was in the generated README and
# each moved with the commit that carried it.
MOVING = (
    re.compile(r"\b\d+\s+of\s+\d+\s+(plan\s+)?steps?\b", re.I),
    re.compile(r"\b\d+\s+(test\s+functions|merged\s+pull\s+requests|matrix\s+rows)\b", re.I),
    re.compile(r"\b\d+\s+(issued\s+)?requirement\s+ids?\b", re.I),
    re.compile(r"\b\d+\s*%\s*\|", re.I),
)


def test_the_readme_states_no_count_that_moves() -> None:
    """A number the next commit changes does not belong in a committed file."""
    text = README.read_text(encoding="utf-8")
    found = [pattern.pattern for pattern in MOVING if pattern.search(text)]
    assert found == [], f"the README states figures its own commit changes: {found}"


def test_the_generator_states_none_either() -> None:
    """The gate is on the source, so the idiom cannot return through it."""
    from otsafety_tooling.readme import render

    rendered = render()
    found = [pattern.pattern for pattern in MOVING if pattern.search(rendered)]
    assert found == [], f"the generator would write moving figures: {found}"


def test_the_reader_is_told_where_the_live_status_is() -> None:
    """Removing a number is only honest if the reader can still find it."""
    text = README.read_text(encoding="utf-8")
    assert "plan:status" in text, "the README does not name the command that measures"
    assert "plan-report" in text or "plan:report" in text, (
        "the README does not point at the step-level report"
    )


def test_what_does_not_move_is_still_stated() -> None:
    """The cure is not an empty page: the stable content stays."""
    text = README.read_text(encoding="utf-8")
    for named in ("relationships", "degree", "Open Targets", "negative result", "toolchain.json"):
        assert named in text, f"the README no longer states {named}"
