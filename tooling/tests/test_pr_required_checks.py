# tooling/tests/test_pr_required_checks.py
"""A merge waits for the checks the workflows promise, not whichever came first.

THE INCIDENT. PR #15 merged with one check registered -- GitGuardian, an external
app that reports in about a second -- before test-tooling, test-site or zizmor
existed. test-tooling then failed on develop. pr.py waited for checks to
REGISTER and to SETTLE, but never knew WHICH checks must exist: every sibling
repository carries the same gap and was protected only by a server ruleset.

DERIVED, NOT LISTED. 2026 practice, from an issue filed a day before this: a
hardcoded list drifts when a job is renamed and then blocks every merge or
waves one through. The required set is read from .github/workflows/: every job
in a workflow that runs on pull_request, named as GitHub names its check. A job
with its own `if:` may legitimately not run, so it is verified if present.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.git import pr
from otsafety_tooling.paths import REPO_ROOT


def _check(name: str, conclusion: str | None = "SUCCESS") -> pr.Check:
    return pr.Check.model_validate({"name": name, "conclusion": conclusion})


def test_the_required_set_is_read_from_the_workflows() -> None:
    """Pinned so a workflow change that alters it is visible in review."""
    assert pr.required_checks(REPO_ROOT) == frozenset({"test-tooling", "test-site", "Run zizmor"})


def test_a_workflow_that_never_runs_on_pull_requests_is_not_required() -> None:
    """release.yml runs on main only; waiting for it on a PR would wait forever."""
    assert "release" not in pr.required_checks(REPO_ROOT)


def test_the_incident_is_refused() -> None:
    """One external check green, every workflow missing: that is not a pass."""
    only_gitguardian = (_check("GitGuardian Security Checks"),)
    with pytest.raises(SystemExit, match="missing"):
        pr.verify_checks(only_gitguardian, pr.required_checks(REPO_ROOT))


def test_every_required_check_present_and_green_passes() -> None:
    checks = tuple(_check(n) for n in ("test-tooling", "test-site", "Run zizmor"))
    pr.verify_checks(
        (*checks, _check("GitGuardian Security Checks")), pr.required_checks(REPO_ROOT)
    )


def test_registration_waits_until_every_required_check_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first poll sees GitGuardian alone; returning there is the bug."""
    states = iter(
        [
            (_check("GitGuardian Security Checks"),),
            (_check("GitGuardian Security Checks"), _check("test-site", None)),
            tuple(
                _check(n, None)
                for n in ("GitGuardian Security Checks", "test-tooling", "test-site", "Run zizmor")
            ),
        ]
    )
    seen: list[int] = []

    def fake_state(number: int | None) -> pr.PullRequest:
        checks = next(states)
        seen.append(len(checks))
        return pr.PullRequest.model_validate(
            {"number": 1, "state": "OPEN", "statusCheckRollup": [c.model_dump() for c in checks]}
        )

    monkeypatch.setattr(pr, "pr_state", fake_state)
    monkeypatch.setattr(pr, "POLL_INTERVAL", 0)
    required = frozenset({"test-tooling", "test-site", "Run zizmor"})
    assert pr.wait_for_checks_to_register(float("inf"), 1, required)
    assert seen == [1, 2, 4], "returned before every required check had registered"
