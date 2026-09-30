# tooling/tests/test_a_dependency_update_merges_itself.py
"""A dependency update merges itself, unless it is the kind a person must read (G.68).

WHY A TASK RATHER THAN A SERVER SETTING. GitHub's auto-merge arms only when a
pull request is already blocked, and it merges on the server with no record
here. This repository merges through pr.py, which observes the checks, verifies
every required one reported, acts, and then observes the result -- and
merge_existing exists for exactly this case: a pull request nobody has checked
out.

WHICH ONES WAIT. A major bump is not a dependency update, it is a change of
behaviour: actions/upload-artifact 4 to 7 crosses three majors, alters artifact
merge semantics and raises the minimum runner version. 2026 practice groups
patch and minor into one pull request and leaves majors standalone, so the
breaking-change review is honest. An update touching a workflow file waits too:
a green suite proves the tests still run, not that the new action is safe.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.requirement("G.68")


def test_a_patch_bump_merges_itself() -> None:
    from otsafety_tooling.git.deps import Update, may_merge

    assert may_merge(Update(number=1, kind="patch", touches_workflows=False)).allowed


def test_a_minor_bump_merges_itself() -> None:
    from otsafety_tooling.git.deps import Update, may_merge

    assert may_merge(Update(number=2, kind="minor", touches_workflows=False)).allowed


def test_a_major_bump_waits_for_a_person() -> None:
    """THE LIVE CASE: PR #68 bumps upload-artifact across three majors."""
    from otsafety_tooling.git.deps import Update, may_merge

    verdict = may_merge(Update(number=68, kind="major", touches_workflows=True))
    assert not verdict.allowed
    assert "major" in verdict.why


def test_an_update_touching_a_workflow_waits_even_when_small() -> None:
    """A green suite proves the tests ran, not that the new action is safe."""
    from otsafety_tooling.git.deps import Update, may_merge

    verdict = may_merge(Update(number=3, kind="patch", touches_workflows=True))
    assert not verdict.allowed
    assert "workflow" in verdict.why


def test_an_unknown_kind_is_refused_rather_than_assumed_small() -> None:
    """Fail closed: an update whose size nobody stated is not a patch.

    THROUGH model_validate, NOT A KEYWORD WITH AN IGNORE. mypy refuses
    kind="unknown" statically, and it is right to: typed code cannot produce
    that value. The real boundary is an untyped reading of what gh returned,
    which is a dict -- so the test models the boundary rather than suppressing
    the checker, as the plan contract's own tests already do.
    """
    from pydantic import ValidationError

    from otsafety_tooling.git.deps import Update

    with pytest.raises(ValidationError):
        Update.model_validate({"number": 4, "kind": "unknown", "touches_workflows": False})


def test_the_rule_is_not_vacuous() -> None:
    """THE CONTROL: if nothing were ever allowed, the tests above would pass anyway."""
    from otsafety_tooling.git.deps import Update, may_merge

    allowed = [
        may_merge(
            Update.model_validate({"number": n, "kind": kind, "touches_workflows": False})
        ).allowed
        for n, kind in ((1, "patch"), (2, "minor"), (3, "major"))
    ]
    assert allowed == [True, True, False], allowed


def test_the_update_type_is_read_from_the_commit_dependabot_writes() -> None:
    """Dependabot states the type in a trailer; nothing here parses its prose."""
    from otsafety_tooling.git.deps import kind_of

    assert kind_of("update-type: version-update:semver-major") == "major"
    assert kind_of("update-type: version-update:semver-minor") == "minor"
    assert kind_of("update-type: version-update:semver-patch") == "patch"


def test_a_commit_stating_no_type_is_refused_rather_than_guessed() -> None:
    """Fail closed: an update whose size nobody stated is not a patch."""
    from otsafety_tooling.git.deps import UpdateUnreadableError, kind_of

    with pytest.raises(UpdateUnreadableError):
        kind_of("Bumps something from 1 to 2, with no trailer at all")


def test_the_stated_type_is_checked_against_the_versions() -> None:
    """TWO READINGS, because one stated string is checked by nothing.

    G.80's lesson: a value repeated beside its source drifts silently. Here the
    trailer is authoritative and the version pair is the control, so a trailer
    that disagrees with its own versions is refused rather than believed.
    """
    from otsafety_tooling.git.deps import UpdateUnreadableError, kind_of

    honest = (
        "- dependency-name: actions/upload-artifact\n"
        "  dependency-version: 7.0.1\n"
        "  update-type: version-update:semver-major"
    )
    assert kind_of(honest, previous="4.6.2") == "major"

    lying = honest.replace("semver-major", "semver-patch")
    with pytest.raises(UpdateUnreadableError):
        kind_of(lying, previous="4.6.2")


def test_only_the_bots_pull_requests_are_considered() -> None:
    """A person's pull request is never merged unattended, whatever it changes."""
    from otsafety_tooling.git.deps import BOT, is_the_bot

    assert is_the_bot(BOT)
    assert not is_the_bot("ltphongssvn")
    assert not is_the_bot("dependabot-impersonator")


def test_the_bot_is_named_as_github_reports_it() -> None:
    """ONE ACTOR, TWO IDENTIFIERS, NAMED IN ONE PLACE.

    gh reports the pull request author as app/dependabot; a commit carries the
    address 49699333+dependabot[bot]@users.noreply.github.com. Neither contains
    the other, so a rule written against one cannot recognise the other -- and
    the trailer policy already had to learn the address form.

    They are declared together here, and the trailer policy reads this set
    rather than keeping a second copy: repeating the CLASS is checked by the
    type checker, repeating the STRING is checked by nothing.
    """
    from otsafety_tooling.git.deps import BOT, BOT_COMMIT_ADDRESSES
    from otsafety_tooling.policy.trailers import DEPENDENCY_BOTS

    assert BOT == "app/dependabot"
    assert DEPENDENCY_BOTS is BOT_COMMIT_ADDRESSES, (
        "the trailer policy keeps its own copy of the bot's address"
    )


def test_an_open_update_is_read_from_what_gh_reports() -> None:
    """The fields are taken from gh's JSON, not from its human output."""
    from otsafety_tooling.git.deps import read_update

    update = read_update(
        {
            "number": 68,
            "author": {"login": "app/dependabot"},
            "files": [{"path": ".github/workflows/test-site.yml"}],
        },
        commit_body=(
            "- dependency-name: actions/upload-artifact\n"
            "  dependency-version: 7.0.1\n"
            "  update-type: version-update:semver-major"
        ),
        previous="4.6.2",
    )
    assert update.number == 68
    assert update.kind == "major"
    assert update.touches_workflows


def test_a_pull_request_changing_no_workflow_says_so() -> None:
    from otsafety_tooling.git.deps import read_update

    update = read_update(
        {
            "number": 9,
            "author": {"login": "app/dependabot"},
            "files": [{"path": "apps/site/bun.lock"}],
        },
        commit_body="  update-type: version-update:semver-patch",
    )
    assert not update.touches_workflows
    assert update.kind == "patch"


def test_a_pull_request_from_a_person_is_refused_before_anything_else() -> None:
    """Not merely 'not allowed': it is not a dependency update at all."""
    from otsafety_tooling.git.deps import NotTheBotError, read_update

    with pytest.raises(NotTheBotError):
        read_update(
            {"number": 10, "author": {"login": "ltphongssvn"}, "files": []},
            commit_body="  update-type: version-update:semver-patch",
        )
