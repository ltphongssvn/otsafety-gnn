# tooling/tests/test_readme_is_generated.py
"""The README is generated, and the Markdown ban narrows to what is written (G.62).

THE REPOSITORY HAD NO FRONT PAGE. A visitor saw a file list. G.28 forbids every
Markdown file by suffix, and its reasoning is exact: prose beside the code
describes it from outside and nothing checks the two against each other -- a
merged commit once cited a context document never written.

A GENERATED FILE IS NOT THAT THING. It is checked, by the same drift gate that
guards the Zod and the site's content. 2026 practice reversed this very rule:
one project made its README a derived copy so a version bump could not ship with
stale docs, on the principle that every index is a build artifact and drift is a
failure rather than a chore.

SO THE BAN NARROWS RATHER THAN LIFTS. Hand-written Markdown is still refused;
a file the generator owns is permitted only while it matches what the generator
produces, and only because it is declared as generated.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.62")

README = REPO_ROOT / "README.md"


def test_the_readme_exists() -> None:
    assert README.is_file(), "the repository still has no front page"


def test_the_readme_is_what_the_generator_produces() -> None:
    """THE DRIFT GATE: a hand-edited README would pass every other test."""
    from otsafety_tooling.readme import render

    assert README.read_text(encoding="utf-8") == render(), (
        "README.md differs from the generator; run mise run readme"
    )


def test_a_hand_written_markdown_file_is_still_refused() -> None:
    """The ban narrows; it does not lift."""
    from otsafety_tooling.policy.markdown import forbidden

    assert forbidden(["notes.md"]) == ["notes.md"]
    assert forbidden(["docs/DESIGN.md"]) == ["docs/DESIGN.md"]


def test_the_generated_readme_is_permitted_by_name() -> None:
    """Permitted because it is declared generated, not because it is a README."""
    from otsafety_tooling.policy.markdown import forbidden

    assert forbidden(["README.md"]) == []
    assert forbidden(["readme.md"]) == ["readme.md"]


def test_the_readme_states_what_the_project_is_and_what_it_refuses() -> None:
    """A front page that omits the question answers nothing."""
    from otsafety_tooling.readme import render

    text = render()
    for named in ("relationships", "Open Targets", "degree", "negative result"):
        assert named in text, f"the README does not mention {named}"


def test_the_readme_carries_no_typed_number() -> None:
    """Its figures come from the facts, as the sheet's status does."""
    from otsafety_tooling.planning.sheet import collect
    from otsafety_tooling.readme import render

    seen = collect()
    assert str(seen.steps) in render(), "the step count is not the one observed"
