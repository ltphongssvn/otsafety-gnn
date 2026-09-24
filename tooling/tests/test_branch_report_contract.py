# tooling/tests/test_branch_report_contract.py
"""The branch report contract: what a report IS, before anything produces one.

CONTRACT-FIRST. These tests fix the domain invariants of branch-report/v1 so
that no producer can write a report that contradicts itself, omits a fact's
context, or leaks a local path.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from otsafety_tooling.contracts.branch_report import BranchFact, BranchReport, Divergence, Finding

SHA = "a" * 40


def _fact(**overrides: object) -> dict[str, object]:
    fact: dict[str, object] = {
        "name": "develop",
        "kind": "local",
        "commit": SHA,
        "upstream": "origin/develop",
        "vs_upstream": {"ahead": 0, "behind": 0},
        "vs_develop": {"ahead": 0, "behind": 0},
        "merged_into_develop": True,
        "checked_out": True,
    }
    fact.update(overrides)
    return fact


def _finding(**overrides: object) -> dict[str, object]:
    finding: dict[str, object] = {
        "rule_id": "B001",
        "reason_code": "PROTECTED_BRANCH_BEHIND",
        "message": "develop is 1 commit behind origin/develop",
        "branch": "develop",
    }
    finding.update(overrides)
    return finding


def _report(**overrides: object) -> dict[str, object]:
    report: dict[str, object] = {
        "generated_at": datetime(2026, 9, 17, tzinfo=UTC),
        "repository": "otsafety-gnn",
        "head": SHA,
        "git_version": "2.55.0",
        "facts": [_fact()],
        "findings": [],
        "verdict": "pass",
    }
    report.update(overrides)
    return report


def test_a_valid_report_survives_a_json_round_trip() -> None:
    report = BranchReport.model_validate(_report(findings=[_finding()], verdict="fail"))
    assert report.contract == "branch-report/v1"
    assert BranchReport.model_validate_json(report.model_dump_json()) == report


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="extra"):
        BranchReport.model_validate(_report(surprise=1))


def test_a_report_cannot_be_changed_after_creation() -> None:
    report = BranchReport.model_validate(_report())
    with pytest.raises(ValidationError, match="frozen"):
        report.verdict = "fail"  # type: ignore[misc]


def test_findings_require_a_fail_verdict() -> None:
    with pytest.raises(ValidationError, match="verdict"):
        BranchReport.model_validate(_report(findings=[_finding()], verdict="pass"))


def test_a_fail_verdict_requires_findings() -> None:
    with pytest.raises(ValidationError, match="verdict"):
        BranchReport.model_validate(_report(verdict="fail"))


def test_a_pass_requires_at_least_one_fact() -> None:
    """An empty report must not claim that everything is in order."""
    with pytest.raises(ValidationError, match="fact"):
        BranchReport.model_validate(_report(facts=[]))


def test_counts_are_never_negative() -> None:
    with pytest.raises(ValidationError):
        Divergence.model_validate({"ahead": -1, "behind": 0})


def test_an_upstream_always_comes_with_its_counts() -> None:
    with pytest.raises(ValidationError, match="upstream"):
        BranchFact.model_validate(_fact(vs_upstream=None))


def test_a_remote_branch_has_no_upstream() -> None:
    with pytest.raises(ValidationError, match="remote"):
        BranchFact.model_validate(_fact(name="origin/develop", kind="remote"))


def test_commits_are_full_hashes() -> None:
    with pytest.raises(ValidationError):
        BranchFact.model_validate(_fact(commit="abc123"))


def test_timestamps_carry_a_time_zone() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        BranchReport.model_validate(_report(generated_at=datetime(2026, 9, 17)))


@pytest.mark.parametrize(
    "overrides",
    [
        {"rule_id": "B999"},
        {"reason_code": "behind"},
        {"branch": ""},
    ],
)
def test_findings_use_known_rules_and_queryable_codes(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Finding.model_validate(_finding(**overrides))


def test_facts_record_no_local_paths() -> None:
    """Worktree paths contain a username; only whether a branch is checked out is kept."""
    assert "worktree" not in BranchFact.model_fields
    with pytest.raises(ValidationError, match="extra"):
        BranchFact.model_validate(_fact(worktree="/Users/someone/repo"))
