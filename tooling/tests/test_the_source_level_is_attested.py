# tooling/tests/test_the_source_level_is_attested.py
"""The SLSA Source Level is computed from evidence, and attested (G.85).

SLSA v1.2 APPROVED THE SOURCE TRACK IN NOVEMBER 2025, and its requirement is
explicit: an attestation MUST state the level of any revision at L1 or above.
A repository claiming a level without one claims nothing a consumer can check,
which is a README badge with extra steps.

THE LEVELS, AS THE SPECIFICATION DEFINES THEM:

    L1  version controlled
    L2  history continuous and immutable, no force-push, provenance per revision
    L3  the organisation's technical controls enforced on protected branches,
        and recorded
    L4  every change reviewed by two trusted people

WHAT A LEVEL IS NOT. It is not the highest requirement that happens to hold: a
level is reached only when every requirement below it holds too, because the
guarantees are cumulative. Reporting L3 while history can be rewritten would
describe a repository that does not exist.

AND L4 IS STATED, NOT OMITTED. One maintainer cannot have two reviewers, so the
attestation says so. An unreachable level quietly left out reads as an
oversight; named, it is a declared limit -- the same rule E.39 applies to the
model card's layer one.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.requirement("G.85")


def _controls(**overrides: bool) -> dict[str, bool]:
    """Every control true, so a test names only what it turns off."""
    return {
        "version_controlled": True,
        "history_immutable": True,
        "provenance_per_revision": True,
        "controls_enforced": True,
        "two_party_review": True,
        **overrides,
    }


def test_a_level_is_computed_not_claimed() -> None:
    """THE RULE: the level follows from the evidence, and nothing types it."""
    from otsafety_tooling.slsa.source import Controls, level_of

    assert level_of(Controls.model_validate(_controls())) == 4


def test_a_level_needs_every_requirement_below_it() -> None:
    """Cumulative: enforced controls do not make L3 while history can be rewritten."""
    from otsafety_tooling.slsa.source import Controls, level_of

    rewritable = Controls.model_validate(_controls(history_immutable=False))
    assert level_of(rewritable) == 1, "L3 was reported over a rewritable history"


def test_each_level_is_reachable() -> None:
    """THE CONTROL: a function returning one number always would pass the rest."""
    from otsafety_tooling.slsa.source import Controls, level_of

    seen = {
        level_of(Controls.model_validate(_controls(**off)))
        for off in (
            {"version_controlled": False},
            {"history_immutable": False},
            {"provenance_per_revision": False},
            {"controls_enforced": False},
            {"two_party_review": False},
            {},
        )
    }
    assert seen == {0, 1, 2, 3, 4}, f"levels reachable: {sorted(seen)}"


def test_an_unreachable_level_is_named_rather_than_omitted() -> None:
    """One maintainer cannot have two reviewers; the attestation says so."""
    from otsafety_tooling.slsa.source import Controls, unmet

    reasons = unmet(Controls.model_validate(_controls(two_party_review=False)))
    assert any("two" in reason for reason in reasons), reasons


def test_the_attestation_states_the_level_and_the_revision() -> None:
    """A verification summary names what was judged and what it concluded."""
    from otsafety_tooling.slsa.source import Controls, summarise

    summary = summarise(Controls.model_validate(_controls()), revision="a" * 40)
    assert summary.revision == "a" * 40
    assert summary.level == 4
    assert summary.predicate_type.startswith("https://slsa.dev/")


def test_a_revision_that_is_not_a_commit_is_refused() -> None:
    """The subject of an attestation is a revision, not whatever was passed."""
    from pydantic import ValidationError

    from otsafety_tooling.slsa.source import Controls, summarise

    with pytest.raises(ValidationError):
        summarise(Controls.model_validate(_controls()), revision="HEAD")


def test_the_controls_are_read_from_the_recorded_check() -> None:
    """DERIVED, NOT RETYPED. The settings check already records whether the
    remote refuses a force push, a deletion and a direct push, per branch. A
    second copy of those booleans beside it is the drift G.80 cost a fortnight.
    """
    from otsafety_tooling.contracts.repository_settings import BranchProtection
    from otsafety_tooling.slsa.source import controls_from

    protected = (
        BranchProtection(branch="develop"),
        BranchProtection(branch="main"),
    )
    controls = controls_from(protected, verdict="pass", reviewers=1)
    assert controls.version_controlled
    assert controls.history_immutable, "force pushes and deletions are refused"
    assert controls.controls_enforced, "a pull request is required and the check passes"
    assert not controls.two_party_review, "one maintainer is not two reviewers"


def test_a_branch_that_permits_a_force_push_is_not_immutable() -> None:
    """One unprotected branch is enough: the guarantee is about the history."""
    from otsafety_tooling.contracts.repository_settings import BranchProtection
    from otsafety_tooling.slsa.source import controls_from

    leaky = (
        BranchProtection(branch="develop"),
        BranchProtection(branch="main", allow_force_pushes=True),
    )
    assert not controls_from(leaky, verdict="pass", reviewers=1).history_immutable


def test_a_check_that_could_not_see_is_not_enforcement() -> None:
    """UNKNOWN IS NOT PASS, which the settings check already refuses to conflate.

    A verdict of unknown means GitHub would not show the settings; reading that
    as enforced would claim a control nobody observed.
    """
    from otsafety_tooling.contracts.repository_settings import BranchProtection
    from otsafety_tooling.slsa.source import controls_from

    protected = (BranchProtection(branch="develop"),)
    assert not controls_from(protected, verdict="unknown", reviewers=1).controls_enforced


def test_no_protected_branch_at_all_is_not_immutable() -> None:
    """The vacuous pass: all() over nothing is true, and nothing is protected."""
    from otsafety_tooling.slsa.source import controls_from

    assert not controls_from((), verdict="pass", reviewers=1).history_immutable


def test_a_reason_names_the_requirement_that_failed() -> None:
    """ONE REASON PER REQUIREMENT, not a disjunction covering a rung.

    L2 carries two requirements, and reporting "history can be rewritten OR no
    provenance is produced" names a cause that may not hold: here the history
    IS immutable and only provenance is missing. A finding that lists what
    might be wrong is the conflation G.48 removed from the plan's observer.
    """
    from otsafety_tooling.contracts.repository_settings import BranchProtection
    from otsafety_tooling.slsa.source import controls_from, unmet

    protected = (BranchProtection(branch="develop"),)
    reasons = unmet(controls_from(protected, verdict="pass", reviewers=1))

    assert not any(" or " in reason for reason in reasons), f"a reason hedges: {reasons}"
    assert any("provenance" in reason for reason in reasons)
    assert not any("rewritten" in reason for reason in reasons), (
        "the history is immutable here, and the reason says otherwise"
    )
