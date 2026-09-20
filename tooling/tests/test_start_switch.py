# tooling/tests/test_start_switch.py
"""Returning to an existing branch, and leaving a branch that adds nothing.

THE GAP. start:here creates a branch; nothing switched to one that already
exists. Freeing develop for sync left this checkout on feature/advance-develop,
an empty branch, with no task able to leave it.

THREE PARTS
    switch_command  prints `git switch <branch>` for the caller to eval, and
                    refuses an unknown branch, one another worktree holds, or a
                    DIRTY tree -- switching carried four uncommitted files onto
                    develop the first time this task was used
    finished        a branch with no commits of its own and no upstream is
                    finished by definition, so sync may leave it as well
"""

from pathlib import Path

import pytest

from otsafety_tooling.git.env import git
from otsafety_tooling.git.state import Branch, RepositoryState, Worktree, gather
from otsafety_tooling.git.sync import finished_branch_to_leave, switch_command

HELD_ELSEWHERE = Path("/nonexistent/worktrees/feature-x")
HERE = Path("/nonexistent/repo")


def _git(*args: str, cwd: Path) -> None:
    result = git(*args, cwd=cwd)
    assert result.returncode == 0, result.stderr


def _identity(root: Path) -> None:
    _git("config", "user.email", "test@example.invalid", cwd=root)
    _git("config", "user.name", "Test", cwd=root)


def _branch(name: str, **overrides: object) -> Branch:
    payload: dict[str, object] = {
        "name": name,
        "upstream_gone": False,
        "is_merged": True,
        "held_by": None,
    }
    payload.update(overrides)
    return Branch.model_validate(payload)


def _state(*branches: Branch) -> RepositoryState:
    here = Worktree(path=HERE, branch="feature/empty", is_main=True, is_dirty=False)
    return RepositoryState(worktrees=(here,), branches=branches)


def test_switching_to_an_existing_branch_is_printed_for_eval() -> None:
    state = _state(_branch("develop"), _branch("feature/empty"))
    assert switch_command("develop", state, HERE) == "git switch develop"


def test_an_unknown_branch_is_refused() -> None:
    with pytest.raises(SystemExit, match="feature/nope"):
        switch_command("feature/nope", _state(_branch("develop")), HERE)


def test_a_branch_another_worktree_holds_is_refused() -> None:
    """One branch, one worktree: git would refuse, so say so first."""
    state = _state(_branch("develop", held_by=HELD_ELSEWHERE))
    with pytest.raises(SystemExit, match="worktree"):
        switch_command("develop", state, HERE)


def test_an_empty_branch_name_is_refused() -> None:
    with pytest.raises(SystemExit, match="branch"):
        switch_command("", _state(_branch("develop")), HERE)


def _empty_branch_clone(tmp_path: Path) -> Path:
    """A clone standing on a branch that adds nothing to develop, never pushed."""
    origin = tmp_path / "origin"
    origin.mkdir()
    _git("init", "-q", "-b", "develop", cwd=origin)
    _identity(origin)
    _git("commit", "-q", "--allow-empty", "-m", "base", cwd=origin)

    clone = tmp_path / "clone"
    _git("clone", "-q", str(origin), str(clone), cwd=tmp_path)
    _identity(clone)
    _git("switch", "-q", "--no-track", "-c", "feature/empty", "develop", cwd=clone)
    return clone


def test_a_branch_that_adds_nothing_is_finished(tmp_path: Path) -> None:
    clone = _empty_branch_clone(tmp_path)
    leaving = finished_branch_to_leave(gather(clone), clone)
    assert leaving is not None
    assert leaving.name == "feature/empty"


def test_a_branch_with_its_own_commits_is_not_finished(tmp_path: Path) -> None:
    clone = _empty_branch_clone(tmp_path)
    _git("commit", "-q", "--allow-empty", "-m", "work", cwd=clone)
    assert finished_branch_to_leave(gather(clone), clone) is None


def test_an_empty_branch_with_a_dirty_tree_is_left_alone(tmp_path: Path) -> None:
    clone = _empty_branch_clone(tmp_path)
    (clone / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")
    assert finished_branch_to_leave(gather(clone), clone) is None


def test_develop_itself_is_never_left(tmp_path: Path) -> None:
    """A protected branch is not something to be switched away from."""
    clone = _empty_branch_clone(tmp_path)
    _git("switch", "-q", "develop", cwd=clone)
    assert finished_branch_to_leave(gather(clone), clone) is None


def _dirty_state(*branches: Branch) -> RepositoryState:
    here = Worktree(path=HERE, branch="feature/empty", is_main=True, is_dirty=True)
    return RepositoryState(worktrees=(here,), branches=branches)


def test_a_dirty_tree_refuses_the_switch() -> None:
    """THE DEFECT: switching carried uncommitted work onto develop."""
    dirty = _dirty_state(_branch("develop"), _branch("feature/empty"))
    with pytest.raises(SystemExit, match="uncommitted"):
        switch_command("develop", dirty, HERE)


def test_a_clean_tree_still_switches() -> None:
    state = _state(_branch("develop"), _branch("feature/empty"))
    assert switch_command("develop", state, HERE) == "git switch develop"
