# tooling/tests/test_pr_rerun.py
"""`pr` may be run again after its branch merged, and then does nothing harmful.

THE INCIDENT. Re-running `pr` on a merged branch pushed it, found no OPEN pull
request, and asked GitHub to create one: "No commits between develop and
feature/repo-settings". Worse, with delete-branch-on-merge enabled, that push
would re-create the branch GitHub had just deleted.

THE FIX DECIDES BEFORE PUSHING. Commits on the branch that origin/develop lacks
are counted first; with none, nothing is pushed and the run succeeds.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from otsafety_tooling.git.env import git
from otsafety_tooling.git.pr import RerunPlan, commits_ahead, plan_rerun


def _git(*args: str, cwd: Path) -> None:
    result = git(*args, cwd=cwd)
    assert result.returncode == 0, result.stderr


def test_commits_ahead_are_proposed() -> None:
    plan = plan_rerun(ahead=2, merged_pr=None)
    assert (plan.action, plan.ahead) == ("propose", 2)


def test_new_commits_are_proposed_even_after_an_earlier_merge() -> None:
    """A branch can merge, gain commits, and need a second pull request."""
    assert plan_rerun(ahead=1, merged_pr=13).action == "propose"


def test_a_merged_branch_with_nothing_new_is_already_merged() -> None:
    plan = plan_rerun(ahead=0, merged_pr=13)
    assert (plan.action, plan.merged_pr) == ("already_merged", 13)
    assert "#13" in plan.message


def test_a_branch_with_nothing_to_propose_says_so() -> None:
    plan = plan_rerun(ahead=0, merged_pr=None)
    assert plan.action == "nothing"
    assert plan.message


def test_a_plan_cannot_hold_impossible_counts() -> None:
    with pytest.raises(ValidationError):
        RerunPlan(action="propose", ahead=-1, merged_pr=None, message="x")
    with pytest.raises(ValidationError):
        RerunPlan(action="already_merged", ahead=0, merged_pr=0, message="x")


def test_commits_ahead_counts_only_work_origin_develop_lacks(tmp_path: Path) -> None:
    origin = tmp_path / "origin.git"
    _git("init", "-q", "--bare", "-b", "develop", str(origin), cwd=tmp_path)
    seed = tmp_path / "seed"
    _git("clone", "-q", str(origin), str(seed), cwd=tmp_path)
    _git("config", "user.email", "test@example.invalid", cwd=seed)
    _git("config", "user.name", "Test", cwd=seed)
    _git("commit", "-q", "--allow-empty", "-m", "base", cwd=seed)
    _git("push", "-q", "origin", "HEAD:develop", cwd=seed)

    repo = tmp_path / "repo"
    _git("clone", "-q", str(origin), str(repo), cwd=tmp_path)
    _git("config", "user.email", "test@example.invalid", cwd=repo)
    _git("config", "user.name", "Test", cwd=repo)
    _git("switch", "-q", "--no-track", "-c", "feature/x", "origin/develop", cwd=repo)
    assert commits_ahead(repo) == 0

    _git("commit", "-q", "--allow-empty", "-m", "work", cwd=repo)
    assert commits_ahead(repo) == 1

    _git("push", "-q", "origin", "HEAD:develop", cwd=repo)
    assert commits_ahead(repo) == 0
