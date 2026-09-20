# tooling/tests/test_repo_state.py
"""Deletability is a property of observed state, never a guess.

THESE TESTS BUILD REAL REPOSITORIES AND REAL WORKTREES: the behaviour under
test is git's own, and a mock would assert what I believe git does.

Ported from cscie103-olap-oltp (tests/test_repo_state.py).
"""

import subprocess
from pathlib import Path

from otsafety_tooling.git.state import Branch, gather

# A PATH THAT CANNOT EXIST AND IS NEVER OPENED; it only populates held_by.
HELD_ELSEWHERE = Path("/nonexistent/worktrees/feature-x")


def _run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


def _repo(tmp_path: Path) -> Path:
    """A repository with develop, main, and one commit, configured LOCALLY."""
    root = tmp_path / "repo"
    root.mkdir()
    _run("git", "init", "-q", "-b", "main", cwd=root)
    _run("git", "config", "user.email", "test@example.invalid", cwd=root)
    _run("git", "config", "user.name", "Test", cwd=root)
    (root / "README.md").write_text("x\n", encoding="utf-8")
    _run("git", "add", "README.md", cwd=root)
    _run("git", "commit", "-qm", "initial", cwd=root)
    _run("git", "branch", "develop", cwd=root)
    return root


def _branch(**overrides: object) -> Branch:
    payload: dict[str, object] = {
        "name": "feature/x",
        "upstream_gone": True,
        "is_merged": True,
        "held_by": None,
    }
    payload.update(overrides)
    return Branch.model_validate(payload)


def test_protected_branches_are_never_deletable() -> None:
    for name in ("develop", "main"):
        assert not _branch(name=name).is_deletable


def test_branch_with_live_upstream_is_not_deletable() -> None:
    assert not _branch(upstream_gone=False).is_deletable


def test_unmerged_branch_is_not_deletable() -> None:
    assert not _branch(is_merged=False).is_deletable


def test_branch_held_by_a_worktree_is_not_deletable() -> None:
    assert not _branch(held_by=HELD_ELSEWHERE).is_deletable


def test_fully_satisfied_branch_is_deletable() -> None:
    assert _branch().is_deletable


def test_blocked_because_names_the_worktree_path() -> None:
    reason = _branch(held_by=HELD_ELSEWHERE).blocked_because
    assert reason is not None
    assert str(HELD_ELSEWHERE) in reason
    assert "worktree:remove" in reason


def test_blocked_because_is_none_when_deletable() -> None:
    assert _branch().blocked_because is None


def test_protection_is_reported_before_other_reasons() -> None:
    assert _branch(name="main", is_merged=False).blocked_because == "protected branch"


def test_gather_finds_the_main_worktree(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    state = gather(root)
    assert len(state.worktrees) == 1
    assert state.worktrees[0].is_main
    assert state.worktrees[0].branch == "main"


def test_gather_detects_a_linked_worktree_holding_a_branch(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _run("git", "worktree", "add", "-q", "-b", "feature/y", str(tmp_path / "wt"), cwd=root)

    state = gather(root)
    held = {branch.name: branch.held_by for branch in state.branches}
    assert held["feature/y"] is not None
    assert not state.worktrees[0].is_linked
    assert state.worktrees[1].is_linked


def test_gather_reports_merged_branches(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _run("git", "branch", "feature/merged", cwd=root)

    state = gather(root)
    merged = {branch.name for branch in state.branches if branch.is_merged}
    assert "feature/merged" in merged


def test_gather_detects_a_dirty_worktree(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text("changed\n", encoding="utf-8")
    assert gather(root).worktrees[0].is_dirty


def test_blocked_excludes_protected_branches(tmp_path: Path) -> None:
    state = gather(_repo(tmp_path))
    assert all(not branch.is_protected for branch in state.blocked)


def _bare_layout(tmp_path: Path) -> tuple[Path, Path]:
    """A bare parent with one linked worktree, the layout the sibling uses."""
    bare = tmp_path / "parent.git"
    _run("git", "init", "-q", "--bare", "-b", "main", str(bare), cwd=tmp_path)

    seed = tmp_path / "seed"
    _run("git", "clone", "-q", str(bare), str(seed), cwd=tmp_path)
    _run("git", "config", "user.email", "test@example.invalid", cwd=seed)
    _run("git", "config", "user.name", "Test", cwd=seed)
    _run("git", "commit", "-q", "--allow-empty", "-m", "initial", cwd=seed)
    _run("git", "push", "-q", "origin", "main", cwd=seed)
    _run("git", "branch", "develop", cwd=seed)
    _run("git", "push", "-q", "origin", "develop", cwd=seed)

    linked = tmp_path / "linked"
    _run("git", "worktree", "add", "-q", str(linked), "develop", cwd=bare)
    return bare, linked


def test_gather_survives_a_bare_parent_worktree(tmp_path: Path) -> None:
    bare, _ = _bare_layout(tmp_path)
    assert gather(bare).worktrees


def test_the_bare_entry_is_identified(tmp_path: Path) -> None:
    bare, _ = _bare_layout(tmp_path)
    state = gather(bare)
    assert state.worktrees[0].is_bare
    assert state.worktrees[0].branch is None


def test_a_bare_worktree_is_never_dirty(tmp_path: Path) -> None:
    bare, _ = _bare_layout(tmp_path)
    assert not gather(bare).worktrees[0].is_dirty


def test_the_linked_worktree_is_still_observed(tmp_path: Path) -> None:
    bare, linked = _bare_layout(tmp_path)
    paths = {worktree.path.resolve() for worktree in gather(bare).worktrees}
    assert linked.resolve() in paths
