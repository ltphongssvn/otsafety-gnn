# tooling/tests/test_no_history_rewrite.py
"""This repository never rewrites lineage, and no command may (G.40).

WHY. worktree:refresh rebased an unpushed branch onto develop, which rewrites its
commits: the next push is a non-fast-forward, and only a force push resolves it.
The function knew that -- it refused a PUSHED branch for exactly that reason --
and rebased anyway when the branch happened to be local. The rule is uniform now:
refresh MERGES, so every commit stays reachable, and the pushed-branch refusal is
gone because a merge is safe either way.

The ban is proved rather than remembered: no module under tooling/src may call
git rebase, and a test reads that from the syntax tree.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

from otsafety_tooling.contracts.outcome import EXIT_CODES
from otsafety_tooling.git import worktree
from otsafety_tooling.git.env import git
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.40")


def test_no_command_rewrites_lineage() -> None:
    """THE BAN, READ FROM THE TREE: rebase, amend and force-push rewrite commits."""
    forbidden = {"rebase", "--amend", "--force", "--force-with-lease", "filter-branch"}
    offenders: list[str] = []
    for path in sorted((REPO_ROOT / "tooling" / "src").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            words = {
                a.value
                for a in node.args
                if isinstance(a, ast.Constant) and isinstance(a.value, str)
            }
            if words & forbidden:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
    assert offenders == [], f"these rewrite lineage: {offenders}"


def _world(tmp_path: Path) -> tuple[Path, Path]:
    """A clone with a worktree on a feature branch, and its origin."""
    origin = tmp_path / "origin.git"
    seed = tmp_path / "seed"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "develop", str(origin)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "develop", str(seed)], check=True)
    for name, value in (("user.email", "t@e.st"), ("user.name", "T")):
        assert git("config", name, value, cwd=seed).returncode == 0
    (seed / "seed.txt").write_text("one\n", encoding="utf-8")
    assert git("add", "seed.txt", cwd=seed).returncode == 0
    assert git("commit", "-qm", "seed", cwd=seed).returncode == 0
    assert git("remote", "add", "origin", str(origin), cwd=seed).returncode == 0
    assert git("push", "-q", "-u", "origin", "develop", cwd=seed).returncode == 0
    return seed, origin


def test_refresh_merges_and_keeps_every_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The branch's own commit is still reachable after refresh: nothing was rewritten."""
    repo, origin = _world(tmp_path)
    assert worktree.cmd_add("work", repo, setup=lambda _p: 0) == 0
    capsys.readouterr()
    work = repo.parent / f"{repo.name}-work"
    (work / "mine.txt").write_text("mine\n", encoding="utf-8")
    assert git("add", "mine.txt", cwd=work).returncode == 0
    assert git("commit", "-qm", "mine", cwd=work).returncode == 0
    mine = git("rev-parse", "HEAD", cwd=work).stdout.strip()

    # develop moves on, in the seed, and is pushed.
    (repo / "seed.txt").write_text("two\n", encoding="utf-8")
    assert git("add", "seed.txt", cwd=repo).returncode == 0
    assert git("commit", "-qm", "newer", cwd=repo).returncode == 0
    assert git("push", "-q", "origin", "develop", cwd=repo).returncode == 0

    assert worktree.cmd_refresh("work", repo) == 0
    contains = git("merge-base", "--is-ancestor", mine, "HEAD", cwd=work)
    assert contains.returncode == 0, "the branch's own commit must still be reachable"
    assert git("merge-base", "--is-ancestor", "origin/develop", "HEAD", cwd=work).returncode == 0


def test_a_pushed_branch_is_refreshed_too(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A MERGE IS SAFE EITHER WAY, so the pushed-branch refusal is gone."""
    repo, _ = _world(tmp_path)
    assert worktree.cmd_add("pushed", repo, setup=lambda _p: 0) == 0
    capsys.readouterr()
    work = repo.parent / f"{repo.name}-pushed"
    assert git("push", "-q", "-u", "origin", "feature/pushed", cwd=work).returncode == 0
    assert worktree.cmd_refresh("pushed", repo) != EXIT_CODES["refused"]
