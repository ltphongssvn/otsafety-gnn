# tooling/tests/test_sync.py
"""Cleanup reports what it did NOT remove, and why.

DRIVEN BY THE STATE MODEL, so every branch gets a decision rather than the
loop stopping at the first refusal.

Ported from cscie103-olap-oltp (tests/test_sync.py), plus the single-clone
adaptation: a clone standing on its own finished branch leaves it for develop,
but only when nothing can be lost.

These fixtures exercise advance_develop's UNHELD path: develop exists in the
clone but no worktree has it checked out. The other paths -- held here, held by
another worktree, and real divergence -- are covered by test_sync_develop.py.
"""

from pathlib import Path

from otsafety_tooling.git.env import git as _run_git
from otsafety_tooling.git.state import Branch, RepositoryState, Worktree, gather
from otsafety_tooling.git.sync import (
    advance_develop,
    finished_branch_to_leave,
    is_linked_worktree,
    plan_cleanup,
)


def _git(*args: str, cwd: Path) -> None:
    """A git call that cannot be redirected by an inherited GIT_DIR."""
    result = _run_git(*args, cwd=cwd)
    assert result.returncode == 0, result.stderr


def _rev(root: Path, ref: str) -> str:
    return _run_git("rev-parse", ref, cwd=root).stdout.strip()


def _current_branch(root: Path) -> str:
    return _run_git("rev-parse", "--abbrev-ref", "HEAD", cwd=root).stdout.strip()


HELD_ELSEWHERE = Path("/nonexistent/worktrees/feature-x")
MAIN_CHECKOUT = Path("/nonexistent/repo")


def _state(*branches: Branch) -> RepositoryState:
    main = Worktree(path=MAIN_CHECKOUT, branch="develop", is_main=True, is_dirty=False)
    return RepositoryState(worktrees=(main,), branches=branches)


def _branch(**overrides: object) -> Branch:
    payload: dict[str, object] = {
        "name": "feature/x",
        "upstream_gone": True,
        "is_merged": True,
        "held_by": None,
    }
    payload.update(overrides)
    return Branch.model_validate(payload)


def _identity(root: Path) -> None:
    _git("config", "user.email", "test@example.invalid", cwd=root)
    _git("config", "user.name", "Test", cwd=root)


def test_plan_selects_only_deletable_branches() -> None:
    plan = plan_cleanup(_state(_branch(name="feature/done")))
    assert [branch.name for branch in plan.remove] == ["feature/done"]


def test_plan_keeps_protected_branches_out_of_both_lists() -> None:
    plan = plan_cleanup(_state(_branch(name="develop")))
    assert plan.remove == ()
    assert plan.blocked == ()


def test_plan_reports_a_branch_held_by_a_worktree() -> None:
    plan = plan_cleanup(_state(_branch(name="feature/held", held_by=HELD_ELSEWHERE)))
    assert plan.remove == ()
    assert [branch.name for branch in plan.blocked] == ["feature/held"]


def test_plan_ignores_branches_whose_upstream_still_exists() -> None:
    plan = plan_cleanup(_state(_branch(name="feature/wip", upstream_gone=False)))
    assert plan.remove == ()
    assert plan.blocked == ()


def test_plan_reports_unmerged_work_whose_upstream_vanished() -> None:
    plan = plan_cleanup(_state(_branch(name="feature/orphan", is_merged=False)))
    assert plan.remove == ()
    assert [branch.name for branch in plan.blocked] == ["feature/orphan"]


def test_plan_is_empty_for_an_empty_repository() -> None:
    plan = plan_cleanup(_state())
    assert plan.remove == ()
    assert plan.blocked == ()


def test_every_blocked_branch_can_explain_itself() -> None:
    plan = plan_cleanup(
        _state(
            _branch(name="feature/held", held_by=HELD_ELSEWHERE),
            _branch(name="feature/orphan", is_merged=False),
        )
    )
    for branch in plan.blocked:
        assert branch.blocked_because


def test_a_linked_worktree_is_recognised(tmp_path: Path) -> None:
    main = tmp_path / "main"
    main.mkdir()
    _git("init", "-q", "-b", "main", cwd=main)
    _identity(main)
    _git("commit", "-q", "--allow-empty", "-m", "initial", cwd=main)

    linked = tmp_path / "linked"
    _git("worktree", "add", "-q", "-b", "feature/z", str(linked), cwd=main)

    assert not is_linked_worktree(main)
    assert is_linked_worktree(linked)


def test_the_integration_branch_is_advanced_without_being_checked_out(
    tmp_path: Path,
) -> None:
    origin = tmp_path / "origin"
    origin.mkdir()
    _git("init", "-q", "-b", "develop", cwd=origin)
    _identity(origin)
    _git("commit", "-q", "--allow-empty", "-m", "one", cwd=origin)

    clone = tmp_path / "clone"
    _git("clone", "-q", str(origin), str(clone), cwd=tmp_path)
    _git("switch", "-q", "-c", "feature/work", cwd=clone)

    _git("commit", "-q", "--allow-empty", "-m", "two", cwd=origin)
    advance_develop(clone)

    assert _rev(clone, "develop") == _rev(origin, "develop")
    assert _current_branch(clone) == "feature/work"


def test_a_branch_deleted_upstream_is_pruned(tmp_path: Path) -> None:
    """THE BUG INHERITED FROM cscie103-olap-oltp.

    `fetch --prune <refspec>` prunes only what the refspec covers, so a branch
    deleted on merge kept its remote-tracking ref and never reported [gone].
    """
    clone = _merged_and_deleted_upstream(tmp_path)
    remote_refs = _run_git("for-each-ref", "--format=%(refname)", "refs/remotes", cwd=clone)
    assert "refs/remotes/origin/feature/done" not in remote_refs.stdout.split()
    done = {branch.name: branch for branch in gather(clone).branches}["feature/done"]
    assert done.upstream_gone


# --- single-clone adaptation --------------------------------------------------


def _merged_and_deleted_upstream(tmp_path: Path) -> Path:
    """A clone standing on feature/done, which was merged and deleted upstream.

    Reproduces the state after a pull request merges on GitHub: the remote
    branch is gone, develop contains the work, and the clone is still on it.
    """
    origin = tmp_path / "origin"
    origin.mkdir()
    _git("init", "-q", "-b", "develop", cwd=origin)
    _identity(origin)
    _git("commit", "-q", "--allow-empty", "-m", "base", cwd=origin)

    clone = tmp_path / "clone"
    _git("clone", "-q", str(origin), str(clone), cwd=tmp_path)
    _identity(clone)
    _git("switch", "-q", "-c", "feature/done", cwd=clone)
    _git("commit", "-q", "--allow-empty", "-m", "work", cwd=clone)
    _git("push", "-q", "-u", "origin", "feature/done", cwd=clone)

    # "Merge the pull request": fast-forward develop on the origin, delete the branch.
    _git("merge", "-q", "--ff-only", "feature/done", cwd=origin)
    _git("branch", "-q", "-D", "feature/done", cwd=origin)

    advance_develop(clone)
    return clone


def test_a_finished_clean_branch_is_left_for_develop(tmp_path: Path) -> None:
    clone = _merged_and_deleted_upstream(tmp_path)
    leaving = finished_branch_to_leave(gather(clone), clone)
    assert leaving is not None
    assert leaving.name == "feature/done"


def test_a_dirty_tree_is_never_switched_away_from(tmp_path: Path) -> None:
    """Uncommitted work must not be carried or lost by an automatic switch."""
    clone = _merged_and_deleted_upstream(tmp_path)
    (clone / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")
    assert finished_branch_to_leave(gather(clone), clone) is None


def test_unfinished_work_is_never_switched_away_from(tmp_path: Path) -> None:
    """A branch whose upstream still exists is work in progress."""
    origin = tmp_path / "origin"
    origin.mkdir()
    _git("init", "-q", "-b", "develop", cwd=origin)
    _identity(origin)
    _git("commit", "-q", "--allow-empty", "-m", "base", cwd=origin)

    clone = tmp_path / "clone"
    _git("clone", "-q", str(origin), str(clone), cwd=tmp_path)
    _identity(clone)
    _git("switch", "-q", "-c", "feature/wip", cwd=clone)
    _git("commit", "-q", "--allow-empty", "-m", "wip", cwd=clone)
    _git("push", "-q", "-u", "origin", "feature/wip", cwd=clone)

    assert finished_branch_to_leave(gather(clone), clone) is None


def test_after_leaving_the_finished_branch_it_is_deletable(tmp_path: Path) -> None:
    """The whole point: once off the branch, the plan removes it."""
    clone = _merged_and_deleted_upstream(tmp_path)
    _git("switch", "-q", "develop", cwd=clone)
    plan = plan_cleanup(gather(clone))
    assert [branch.name for branch in plan.remove] == ["feature/done"]
