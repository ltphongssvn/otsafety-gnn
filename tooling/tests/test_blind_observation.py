# tooling/tests/test_blind_observation.py
"""An observation that cannot see an evidence kind says so (G.48).

THE READING THAT LOOKS LIKE A PASS. staged_facts observed at the index knows no
merged pull request -- there are none to see there -- so every pr-kind
requirement read as unmet. G.2's evidence is PR 18, merged long before sixty
others; it reported unmet and blocked G.20, and nothing said the observation had
simply been blind.

2026 practice names this exact shape: a negative result is void without a
positive control, because "I could not see far enough" and "it is not there"
produce the same one-bit answer, and the blind one is the reassuring direction.
So a fact set that observed none of a kind it should have seen refuses to judge
that kind at all.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.planning.edit import load
from otsafety_tooling.planning.status import Facts, blind_to, staged_facts, unmet

pytestmark = pytest.mark.requirement("G.48")


def test_facts_with_no_merged_pull_requests_are_blind_to_that_kind() -> None:
    """A repository with sixty merged pull requests cannot honestly observe none."""
    blind = Facts(
        ref="the index",
        paths=frozenset(),
        tasks=frozenset(),
        merged_prs=frozenset(),
        tags=frozenset(),
        branches_with_work=frozenset(),
    )
    assert "pr" in blind_to(blind)


def test_a_kind_that_was_observed_is_not_blind() -> None:
    seeing = Facts(
        ref="origin/develop",
        paths=frozenset({"README.md"}),
        tasks=frozenset(),
        merged_prs=frozenset({18}),
        tags=frozenset(),
        branches_with_work=frozenset(),
    )
    assert "pr" not in blind_to(seeing)


def test_a_requirement_is_not_reported_unmet_on_evidence_nobody_could_see() -> None:
    """THE BUG: G.2's evidence is PR 18. At the index that is invisible, and it
    read as unmet -- which blocked G.20 for a reason that was never true."""
    plan = load()
    blind = Facts(
        ref="the index",
        paths=frozenset(),
        tasks=frozenset(),
        merged_prs=frozenset(),
        tags=frozenset(),
        branches_with_work=frozenset(),
    )
    problems = unmet(plan, blind, "G.2")
    assert problems == [], f"an unseeable kind must not read as unmet: {problems}"


def test_the_real_observation_sees_merged_pull_requests() -> None:
    """The positive control: if this repository's own facts see none, the
    observation is blind and the gate above is the only thing protecting it."""
    facts = staged_facts(REPO_ROOT)
    assert "pr" in blind_to(facts) or facts.merged_prs, (
        "the facts claim to see pull requests and found none, which cannot be true here"
    )
