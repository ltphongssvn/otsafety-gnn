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
    """Its content is derived, and from the document everything else reads.

    THIS TEST ONCE DEMANDED THE OPPOSITE. Written with G.62, it asserted the
    README states the observed step count -- and that figure is exactly what
    G.64 removed, because the commit carrying the page completes steps the page
    counts, so the copy is stale before it lands. Three pushes were refused for
    it in one day.

    WHAT SURVIVES IS THE PRINCIPLE, not the mechanism: nothing on the page is
    typed. The layers come from context/architecture.yaml, the stack from
    toolchain.json, and the figures that move are not stated at all -- the page
    names the command that measures them instead.
    """
    from otsafety_tooling.contracts.architecture import Architecture
    from otsafety_tooling.contracts.files import read_yaml
    from otsafety_tooling.readme import render

    text = render()
    architecture = read_yaml(REPO_ROOT / "context" / "architecture.yaml", Architecture)
    for layer in architecture.layers:
        assert layer.name in text, f"the README omits layer {layer.n}, {layer.name}"
        assert layer.as_data in text, f"the README omits what layer {layer.n} records"
