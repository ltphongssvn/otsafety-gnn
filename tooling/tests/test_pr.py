# tooling/tests/test_pr.py
"""Merging is authorised by observed checks, never by intent.

THE UNIT TESTS COVER THE VERIFY STEP AND THE BOUNDARY MODELS, because those are
where a fail-open bug hides. The network sequence is exercised by using the
task, not by mocking gh into agreeing.

Ported from cscie103-olap-oltp (tests/test_pr.py).
"""

import pytest

from otsafety_tooling.git.pr import (
    PASSING_CONCLUSIONS,
    Check,
    CheckConclusion,
    MergeResult,
    PullRequest,
    parse_number,
    verify_checks,
    verify_target,
    view_args,
)


def _pr(**overrides: object) -> PullRequest:
    payload: dict[str, object] = {
        "number": 1,
        "state": "OPEN",
        "baseRefName": "develop",
        "mergeStateStatus": "CLEAN",
        "url": "https://example.invalid/pull/1",
        "statusCheckRollup": [{"name": "quality gate", "conclusion": "SUCCESS"}],
    }
    payload.update(overrides)
    return PullRequest.model_validate(payload)


def test_empty_conclusion_means_pending_not_unknown() -> None:
    check = Check.model_validate({"name": "quality gate", "conclusion": ""})
    assert check.conclusion is None


def test_unrecognised_conclusion_is_rejected() -> None:
    with pytest.raises(ValueError, match="conclusion"):
        Check.model_validate({"name": "x", "conclusion": "MOSTLY_FINE"})


def test_neutral_and_skipped_are_passing() -> None:
    """Playwright is skipped on workflow-only changes; that must not block."""
    assert CheckConclusion.NEUTRAL in PASSING_CONCLUSIONS
    assert CheckConclusion.SKIPPED in PASSING_CONCLUSIONS


def test_failure_is_not_passing() -> None:
    assert CheckConclusion.FAILURE not in PASSING_CONCLUSIONS
    assert CheckConclusion.CANCELLED not in PASSING_CONCLUSIONS
    assert CheckConclusion.TIMED_OUT not in PASSING_CONCLUSIONS


def test_no_checks_at_all_is_refused() -> None:
    with pytest.raises(SystemExit, match="no checks"):
        verify_checks(())


def test_pending_check_is_refused() -> None:
    with pytest.raises(SystemExit, match="still running"):
        verify_checks((Check(name="quality gate", conclusion=None),))


def test_failing_check_is_refused_and_named() -> None:
    checks = (
        Check(name="test-backend", conclusion=CheckConclusion.FAILURE),
        Check(name="lint", conclusion=CheckConclusion.SUCCESS),
    )
    with pytest.raises(SystemExit, match="test-backend"):
        verify_checks(checks)


def test_all_passing_is_allowed() -> None:
    verify_checks((Check(name="quality gate", conclusion=CheckConclusion.SUCCESS),))


def test_checks_settled_requires_at_least_one_check() -> None:
    assert _pr(statusCheckRollup=[]).checks_settled is False


def test_checks_settled_is_false_while_one_is_pending() -> None:
    pr = _pr(
        statusCheckRollup=[
            {"name": "quality gate", "conclusion": "SUCCESS"},
            {"name": "other", "conclusion": ""},
        ]
    )
    assert pr.checks_settled is False


def test_terminal_states_are_recognised() -> None:
    assert _pr(state="MERGED").is_terminal
    assert _pr(state="CLOSED").is_terminal
    assert not _pr(state="OPEN").is_terminal


def test_merge_result_forbids_extra_fields() -> None:
    with pytest.raises(ValueError, match="extra"):
        MergeResult.model_validate({"merged": True, "sha": "abc", "message": "ok", "surprise": 1})


def test_merge_result_rejects_a_missing_field() -> None:
    with pytest.raises(ValueError, match="sha"):
        MergeResult.model_validate({"merged": True, "message": "ok"})


def test_view_args_name_the_pull_request_when_given() -> None:
    """The regression: a number that is accepted must also be observed."""
    assert view_args(8)[:3] == ["pr", "view", "8"]


def test_view_args_default_to_the_current_branch() -> None:
    assert view_args(None)[:3] == ["pr", "view", "--json"]


def test_a_pull_request_into_develop_is_accepted() -> None:
    verify_target(_pr())


def test_a_pull_request_into_main_is_refused() -> None:
    """GitFlow: main changes only through release and hotfix branches."""
    with pytest.raises(SystemExit, match="main"):
        verify_target(_pr(baseRefName="main"))


def test_an_unknown_target_is_refused() -> None:
    with pytest.raises(SystemExit, match="unknown"):
        verify_target(_pr(baseRefName=""))


@pytest.mark.parametrize("argv", [[], ["0"], ["-3"], ["eight"], ["8", "9"]])
def test_merge_requires_one_positive_number(argv: list[str]) -> None:
    with pytest.raises(SystemExit, match="usage"):
        parse_number(argv)


def test_merge_number_is_parsed() -> None:
    assert parse_number(["8"]) == 8
