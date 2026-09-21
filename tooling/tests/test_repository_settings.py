# tooling/tests/test_repository_settings.py
"""Repository settings: compared, checked and configured, with every run recorded.

THE GITHUB PORT. `check` and `configure` talk to GitHub through a two-method
protocol; production uses `gh api`, and these tests use an in-memory repository.
That replaces the network, not this module's logic, which runs for real.

    S001  SETTING_DIFFERS      a visible setting is not the declared value
    S002  SETTING_NOT_VISIBLE  GitHub did not return the setting
    S003  GITHUB_UNREACHABLE   GitHub could not be asked at all

A fail is certain drift; an unknown is a check that could not see enough; only
a check that saw every setting at its declared value passes.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from otsafety_tooling.contracts.repository_settings import (
    MergeSettings,
    ObservedSettings,
    RepositoryResponse,
    SettingsCheckReport,
)
from otsafety_tooling.git.ghcli import NotAuthenticatedError
from otsafety_tooling.github.settings import check, compare, configure

POLICY: dict[str, bool] = {
    "allow_merge_commit": True,
    "allow_squash_merge": False,
    "allow_rebase_merge": False,
    "allow_auto_merge": False,
    "delete_branch_on_merge": True,
}
DESIRED = MergeSettings.model_validate(POLICY)


class InMemoryRepository:
    """A GitHub repository held in a dict, with the failure modes that matter."""

    def __init__(
        self,
        state: dict[str, bool],
        *,
        hidden: frozenset[str] = frozenset(),
        ignored: frozenset[str] = frozenset(),
        unreachable: bool = False,
    ) -> None:
        self.state = dict(state)
        self.hidden = hidden
        self.ignored = ignored
        self.unreachable = unreachable
        self.updates: list[dict[str, bool]] = []

    def read(self) -> RepositoryResponse:
        if self.unreachable:
            raise NotAuthenticatedError("gh is not authenticated (exit 4).")
        visible = {key: value for key, value in self.state.items() if key not in self.hidden}
        return RepositoryResponse.model_validate(
            {**visible, "full_name": "owner/repo", "private": True}
        )

    def update(self, changes: dict[str, bool]) -> RepositoryResponse:
        self.updates.append(dict(changes))
        for key, value in changes.items():
            if key not in self.ignored:
                self.state[key] = value
        return self.read()


def _report(artifacts: Path) -> SettingsCheckReport:
    files = sorted(artifacts.glob("*.json"))
    assert len(files) == 1, files
    return SettingsCheckReport.model_validate_json(files[0].read_text(encoding="utf-8"))


def _rules(report: SettingsCheckReport) -> list[tuple[str, str | None]]:
    return [(finding.rule_id, finding.setting) for finding in report.findings]


def test_matching_settings_produce_no_findings() -> None:
    assert compare(DESIRED, ObservedSettings.model_validate(POLICY)) == ()


def test_a_different_setting_is_s001_with_both_values() -> None:
    observed = ObservedSettings.model_validate({**POLICY, "delete_branch_on_merge": False})
    (finding,) = compare(DESIRED, observed)
    assert (finding.rule_id, finding.reason_code) == ("S001", "SETTING_DIFFERS")
    assert (finding.setting, finding.expected, finding.observed) == (
        "delete_branch_on_merge",
        True,
        False,
    )


def test_a_setting_github_did_not_return_is_s002() -> None:
    observed = ObservedSettings.model_validate(
        {key: value for key, value in POLICY.items() if key != "allow_auto_merge"}
    )
    (finding,) = compare(DESIRED, observed)
    assert (finding.rule_id, finding.setting, finding.observed) == (
        "S002",
        "allow_auto_merge",
        None,
    )


def test_a_repository_at_its_policy_passes_and_is_recorded(tmp_path: Path) -> None:
    assert check(InMemoryRepository(POLICY), DESIRED, tmp_path) == 0
    report = _report(tmp_path)
    assert (report.contract, report.verdict, report.repository) == (
        "repository-settings-check/v1",
        "pass",
        "owner/repo",
    )


def test_drift_fails_and_names_every_setting(tmp_path: Path) -> None:
    drifted = {**POLICY, "allow_squash_merge": True, "delete_branch_on_merge": False}
    assert check(InMemoryRepository(drifted), DESIRED, tmp_path) == 1
    report = _report(tmp_path)
    assert report.verdict == "fail"
    assert _rules(report) == [
        ("S001", "allow_squash_merge"),
        ("S001", "delete_branch_on_merge"),
    ]


def test_settings_github_hides_are_unknown_not_pass(tmp_path: Path) -> None:
    repository = InMemoryRepository(POLICY, hidden=frozenset(POLICY))
    assert check(repository, DESIRED, tmp_path) == 1
    report = _report(tmp_path)
    assert report.verdict == "unknown"
    assert {rule for rule, _ in _rules(report)} == {"S002"}


def test_an_unreachable_github_is_unknown_and_still_recorded(tmp_path: Path) -> None:
    assert check(InMemoryRepository(POLICY, unreachable=True), DESIRED, tmp_path) == 1
    report = _report(tmp_path)
    assert (report.verdict, _rules(report)) == ("unknown", [("S003", None)])


def test_configure_applies_the_policy_then_verifies_it(tmp_path: Path) -> None:
    repository = InMemoryRepository({**POLICY, "delete_branch_on_merge": False})
    assert configure(repository, DESIRED, tmp_path) == 0
    assert repository.updates == [POLICY]
    assert repository.state == POLICY
    assert _report(tmp_path).verdict == "pass"


def test_configure_catches_a_change_github_did_not_apply(tmp_path: Path) -> None:
    repository = InMemoryRepository(
        {**POLICY, "delete_branch_on_merge": False},
        ignored=frozenset({"delete_branch_on_merge"}),
    )
    assert configure(repository, DESIRED, tmp_path) == 1
    assert _rules(_report(tmp_path)) == [("S001", "delete_branch_on_merge")]


def _report_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "generated_at": datetime(2026, 9, 17, tzinfo=UTC),
        "repository": "owner/repo",
        "findings": [],
        "verdict": "pass",
    }
    payload.update(overrides)
    return payload


def test_a_report_cannot_pass_with_findings() -> None:
    finding = {
        "rule_id": "S002",
        "reason_code": "SETTING_NOT_VISIBLE",
        "message": "allow_auto_merge was not returned",
        "setting": "allow_auto_merge",
        "expected": False,
        "observed": None,
    }
    with pytest.raises(ValidationError, match="verdict"):
        SettingsCheckReport.model_validate(_report_payload(findings=[finding]))


def test_a_report_cannot_fail_without_a_difference() -> None:
    with pytest.raises(ValidationError, match="verdict"):
        SettingsCheckReport.model_validate(_report_payload(verdict="fail"))
