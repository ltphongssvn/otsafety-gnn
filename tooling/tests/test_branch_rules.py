# tooling/tests/test_branch_rules.py
"""The GitFlow rules, as a pure function from facts to findings.

No git runs here: each test builds the facts it needs through the contract, so
every rule is checked on its own, including the cases it must NOT flag.
"""

import pytest

from otsafety_tooling.contracts.branch_report import BranchFact, Finding
from otsafety_tooling.git.branches import MINIMUM_GIT, evaluate, parse_git_version

SHA = "b" * 40


def _local(name: str, ahead: int, behind: int) -> BranchFact:
    return BranchFact.model_validate(
        {
            "name": name,
            "kind": "local",
            "commit": SHA,
            "upstream": f"origin/{name}",
            "vs_upstream": {"ahead": ahead, "behind": behind},
            "vs_develop": {"ahead": 0, "behind": 0},
            "merged_into_develop": True,
            "checked_out": False,
        }
    )


def _remote(name: str, **overrides: object) -> BranchFact:
    fact: dict[str, object] = {
        "name": name,
        "kind": "remote",
        "commit": SHA,
        "vs_develop": {"ahead": 0, "behind": 0},
        "merged_into_develop": True,
        "checked_out": False,
    }
    fact.update(overrides)
    return BranchFact.model_validate(fact)


def _ids(findings: tuple[Finding, ...]) -> list[tuple[str, str]]:
    return [(finding.rule_id, finding.branch) for finding in findings]


def test_in_sync_protected_branches_produce_no_findings() -> None:
    facts = (_local("develop", 0, 0), _local("main", 0, 0), _remote("origin/develop"))
    assert evaluate(facts) == ()


@pytest.mark.parametrize(
    ("ahead", "behind", "expected"),
    [
        (0, 2, ("B001", "PROTECTED_BRANCH_BEHIND")),
        (3, 0, ("B002", "PROTECTED_BRANCH_AHEAD")),
        (1, 1, ("B004", "PROTECTED_BRANCH_DIVERGED")),
    ],
)
def test_a_protected_branch_is_judged_against_its_upstream(
    ahead: int, behind: int, expected: tuple[str, str]
) -> None:
    (finding,) = evaluate((_local("main", ahead, behind),))
    assert (finding.rule_id, finding.reason_code) == expected
    assert finding.branch == "main"


def test_a_diverged_branch_is_not_also_reported_as_ahead_or_behind() -> None:
    assert _ids(evaluate((_local("develop", 2, 5),))) == [("B004", "develop")]


def test_local_feature_branches_are_not_judged() -> None:
    """Cleaning up feature branches is sync's job, not this report's."""
    assert evaluate((_local("feature/wip", 4, 0),)) == ()


def test_a_merged_remote_feature_branch_is_b003() -> None:
    findings = evaluate((_remote("origin/feature/done"),))
    assert _ids(findings) == [("B003", "origin/feature/done")]
    assert findings[0].reason_code == "MERGED_REMOTE_BRANCH_REMAINS"


def test_an_unmerged_remote_feature_branch_is_work_in_progress() -> None:
    fact = _remote(
        "origin/feature/wip",
        vs_develop={"ahead": 1, "behind": 0},
        merged_into_develop=False,
    )
    assert evaluate((fact,)) == ()


def test_the_remote_integration_branches_are_never_b003() -> None:
    assert evaluate((_remote("origin/develop"), _remote("origin/main"))) == ()


def test_main_ahead_of_develop_is_b005() -> None:
    fact = _remote(
        "origin/main",
        vs_develop={"ahead": 1, "behind": 0},
        merged_into_develop=False,
    )
    findings = evaluate((fact,))
    assert _ids(findings) == [("B005", "origin/main")]
    assert findings[0].reason_code == "MAIN_NOT_IN_DEVELOP"


def test_findings_are_ordered_by_rule_then_branch() -> None:
    facts = (
        _remote("origin/feature/zeta"),
        _local("main", 0, 1),
        _remote("origin/feature/alpha"),
        _local("develop", 1, 0),
    )
    assert _ids(evaluate(facts)) == [
        ("B001", "main"),
        ("B002", "develop"),
        ("B003", "origin/feature/alpha"),
        ("B003", "origin/feature/zeta"),
    ]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("git version 2.55.0\n", (2, 55, 0)),
        ("git version 2.43.0", (2, 43, 0)),
        ("git version 2.39.5 (Apple Git-154)", (2, 39, 5)),
        ("git version 2.41", (2, 41, 0)),
    ],
)
def test_git_versions_are_parsed(raw: str, expected: tuple[int, int, int]) -> None:
    assert parse_git_version(raw) == expected


def test_an_unreadable_version_is_refused() -> None:
    with pytest.raises(ValueError, match="git version"):
        parse_git_version("not git at all")


def test_the_minimum_git_has_the_ahead_behind_atom() -> None:
    """%(ahead-behind:<ref>) arrived in git 2.41; FAS OnDemand runs 2.43."""
    assert MINIMUM_GIT == (2, 41, 0)
    assert parse_git_version("git version 2.43.0") >= MINIMUM_GIT
    assert parse_git_version("git version 2.40.1") < MINIMUM_GIT
