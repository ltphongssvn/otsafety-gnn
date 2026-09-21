# tooling/tests/test_pr_promote.py
"""Promotion from develop to main, ported from FleetManagement's promote.yml.

THE SAME VERIFIED MERGE AS EVERY FEATURE. FleetManagement's first promotion bug
was a silent no-op: error-masked shell reported success while nothing merged.
So promotion reuses merge_when_green unchanged -- registration wait, rollup
polling, fail-closed on zero checks, a parsed merge result -- rather than a
second, shell-based path.

UNDER THE PERSON'S OWN LOGIN, NOT A BOT. FleetManagement needed a GitHub App
because merges made with GITHUB_TOKEN emit no push event, so release.yml never
fired. A merge made with the person's gh login does emit one.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.git import pr


def _pull(base: str) -> pr.PullRequest:
    return pr.PullRequest.model_validate({"number": 7, "state": "OPEN", "baseRefName": base})


def test_a_promotion_must_target_main() -> None:
    pr.verify_target(_pull("main"), base="main")
    with pytest.raises(SystemExit, match="targets 'develop'"):
        pr.verify_target(_pull("develop"), base="main")


def test_a_feature_still_only_targets_develop() -> None:
    """The default is unchanged: nothing reaches main through `mise run pr`."""
    with pytest.raises(SystemExit, match="targets 'main'"):
        pr.verify_target(_pull("main"))


def test_nothing_is_promoted_when_main_already_has_everything() -> None:
    assert pr.plan_promotion(0).action == "nothing"
    assert pr.plan_promotion(48).action == "promote"


def test_the_back_merge_cannot_retrigger_ci() -> None:
    """FleetManagement's empty-release loop: a content-free back-merge re-ran CI."""
    assert "[skip ci]" in pr.BACK_MERGE_MESSAGE
    assert pr.BACK_MERGE_MESSAGE.startswith("chore: ")


def test_promote_is_a_subcommand(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_promote() -> int:
        calls.append("promote")
        return 0

    monkeypatch.setattr(pr, "promote", fake_promote)
    assert pr.main(["promote"]) == 0
    assert calls == ["promote"]
