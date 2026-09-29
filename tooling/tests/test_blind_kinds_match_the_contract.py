# tooling/tests/test_blind_kinds_match_the_contract.py
"""The blind set names kinds as the contract spells them (G.80).

BLIND_AT_THE_INDEX HELD "tag" AND THE CONTRACT SAYS "release". The sets never
intersected, so the skip never applied and every step proved by a release tag
read unmet from the moment G.48 landed. F.4 and F.5 are done, their tags cut,
and the plan reported them blocked -- and a ready-set built on that number sent
a whole branch at the wrong step.

G.48 GOT THE INTENT RIGHT AND THE STRING WRONG. Its own comment says a merged
pull request AND A TAG cannot exist at the index. The pr half worked because
PrEvidence.kind happens to be "pr"; nothing checked the other.

DERIVED, NOT TYPED. A literal list of kind strings beside a contract that
declares them is the copy this repository has removed three times over, so the
test reads the discriminator's own values and the constant must be a subset.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.requirement("G.80")


def _declared_kinds() -> set[str]:
    """Every kind the Evidence union discriminates on, from the contract."""
    from otsafety_tooling.contracts.plan import (
        PathEvidence,
        PrEvidence,
        ReleaseEvidence,
        TaskEvidence,
    )

    kinds: set[str] = set()
    for model in (PrEvidence, ReleaseEvidence, PathEvidence, TaskEvidence):
        annotation = model.model_fields["kind"].annotation
        kinds.update(getattr(annotation, "__args__", ()))
    return kinds


def test_the_contract_declares_four_kinds() -> None:
    """The positive control: without it a typo'd set would pass vacuously."""
    assert _declared_kinds() == {"pr", "release", "path", "task"}


def test_every_blind_kind_is_one_the_contract_declares() -> None:
    """A kind nothing produces skips nothing, silently and forever."""
    from otsafety_tooling.planning.status import BLIND_AT_THE_INDEX

    unknown = sorted(BLIND_AT_THE_INDEX - _declared_kinds())
    assert unknown == [], f"blind kinds no evidence carries: {unknown}"


def test_the_index_is_blind_to_pull_requests_and_releases() -> None:
    """Neither can exist at the index, so neither may be judged there."""
    from otsafety_tooling.planning.status import BLIND_AT_THE_INDEX

    assert BLIND_AT_THE_INDEX == {"pr", "release"}


def test_a_cut_release_is_not_reported_missing_at_the_index() -> None:
    """THE DEFECT, as an observation: F.4's tag exists and read unmet."""
    from otsafety_tooling.paths import REPO_ROOT
    from otsafety_tooling.planning.edit import load
    from otsafety_tooling.planning.status import staged_facts, unmet

    plan, facts = load(), staged_facts(REPO_ROOT)
    assert facts.ref == "the index", "this observation is not the one that was blind"
    for step_id in ("F.4", "F.5"):
        problems = [p for p in unmet(plan, facts, step_id) if "tagged" in p]
        assert problems == [], f"{step_id} judges a release where none can be seen: {problems}"


def test_an_observation_that_sees_releases_still_judges_them() -> None:
    """The rule skips a blind observer, never a seeing one."""
    from otsafety_tooling.planning.status import Facts, blind_to

    seeing = Facts(
        ref="origin/develop",
        paths=frozenset({"README.md"}),
        tasks=frozenset({"check"}),
        merged_prs=frozenset({17}),
        tags=frozenset({"v1.0.0"}),
        branches_with_work=frozenset(),
    )
    assert blind_to(seeing) == frozenset(), "a seeing observation claims blindness"
