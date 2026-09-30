# tooling/tests/test_the_source_level_is_attested.py
"""The SLSA Source Level is computed from evidence, and recorded (G.85).

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
record says so. An unreachable level quietly left out reads as an oversight;
named, it is a declared limit -- the rule E.39 applies to the model card's
first layer.

THE RECORD IS THE PRODUCT, NOT THE PRINTOUT. A decision that exists only on
stdout leaves no trace, and 2026 audit practice is uniform on the shape: the
record carries its inputs as well as its output so the verdict can be
re-derived, it is written before anything acts on it, and no code path
overwrites a prior one.
"""

from __future__ import annotations

from pathlib import Path

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
    """One maintainer cannot have two reviewers; the record says so."""
    from otsafety_tooling.slsa.source import Controls, unmet

    reasons = unmet(Controls.model_validate(_controls(two_party_review=False)))
    assert any("two" in reason for reason in reasons), reasons


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


def test_the_summary_states_the_level_and_the_revision() -> None:
    """A verification summary names what was judged and what it concluded."""
    from otsafety_tooling.slsa.source import Controls, summarise

    summary = summarise(Controls.model_validate(_controls()), revision="a" * 40)
    assert summary.revision == "a" * 40
    assert summary.level == 4
    assert summary.predicate_type.startswith("https://slsa.dev/")


def test_a_revision_that_is_not_a_commit_is_refused() -> None:
    """The subject is a revision, not a name that resolves elsewhere tomorrow."""
    from pydantic import ValidationError

    from otsafety_tooling.slsa.source import Controls, summarise

    with pytest.raises(ValidationError):
        summarise(Controls.model_validate(_controls()), revision="HEAD")


def test_the_controls_are_read_from_the_recorded_check() -> None:
    """DERIVED, NOT RETYPED. repository-settings/v1 already declares, per
    branch, whether the remote refuses a force push, a deletion and a direct
    push. A second copy of those booleans is the drift G.80 cost a fortnight.
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


def test_the_decision_is_written_where_evidence_lives(tmp_path: Path) -> None:
    """STDOUT IS PRESENTATION; THE RECORD IS THE PRODUCT.

    summarise returned a model and nothing stored it, so a run left no trace --
    the shape every other gate here already refuses. It lands beside the
    settings checks and branch reports, in the shared evidence root.
    """
    from otsafety_tooling.slsa.source import Controls, record

    written = record(
        Controls.model_validate(_controls(provenance_per_revision=False)),
        revision="b" * 40,
        root=tmp_path,
    )
    assert written.is_file(), "the decision was not written"
    assert written.parent.name == "slsa-source"


def test_the_record_carries_what_it_judged(tmp_path: Path) -> None:
    """PROVENANCE-COMPLETE: re-evaluable from the record alone.

    A decision record carries its inputs, not only its output -- a level with
    no record of what was observed can be believed and never re-checked.
    """
    from otsafety_tooling.slsa.source import Controls, Summary, record

    controls = Controls.model_validate(_controls(two_party_review=False))
    written = record(controls, revision="c" * 40, root=tmp_path)

    read = Summary.model_validate_json(written.read_text(encoding="utf-8"))
    assert read.observed == controls, "the record cannot be re-evaluated"
    assert read.level == 3
    assert read.revision == "c" * 40


def test_two_runs_never_overwrite_each_other(tmp_path: Path) -> None:
    """APPEND-ONLY: no code path may silently replace a prior decision."""
    from otsafety_tooling.slsa.source import Controls, record

    controls = Controls.model_validate(_controls())
    first = record(controls, revision="d" * 40, root=tmp_path)
    second = record(controls, revision="e" * 40, root=tmp_path)

    assert first != second
    assert len(sorted(first.parent.glob("*.json"))) == 2


def test_the_same_revision_twice_is_still_two_records(tmp_path: Path) -> None:
    """THE HARDER CASE: re-judging one revision keeps both answers.

    Naming a record after its revision alone would overwrite the earlier
    verdict the moment a control changed -- losing exactly the transition an
    audit exists to show.
    """
    from otsafety_tooling.slsa.source import Controls, record

    revision = "f" * 40
    before = record(Controls.model_validate(_controls()), revision=revision, root=tmp_path)
    after = record(
        Controls.model_validate(_controls(history_immutable=False)),
        revision=revision,
        root=tmp_path,
    )
    assert before != after, "the second judgement replaced the first"
